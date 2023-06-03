# SPDX-License-Identifier: MIT

# Copyright (c) 2023 scmanjarrez. All rights reserved.
# This work is licensed under the terms of the MIT license.

import asyncio
import html
import io
import logging
import re
import subprocess
import sys
import tempfile
from functools import partial
from multiprocessing import Process, Queue
from pathlib import Path
from typing import Any, Dict, Tuple, Union
from uuid import uuid4

import aiohttp

import database as db
import edge_tts
import openai
import utils as ut
from aiohttp.web import HTTPException
from BingImageCreator import ImageGen
from EdgeGPT import ConversationStyle
from telegram import constants, Update
from telegram.ext import ContextTypes


BCODE = re.compile(r"(?<!\()(```+)")
BCODE_LANG = re.compile(r"((```+)\w*\n*)")
CODE = re.compile(r"(?<!\()(`+)(.+?)\1(?!\))")
BOLD = re.compile(r"(?<![(`])(?:\*\*([^*`]+?)\*\*|__([^_`]+?)__)")
ITA = re.compile(r"(?<![(`*_])(?:\*([^*`]+?)\*|_([^_`]+?)_)")
REF = re.compile(r"\[\^(\d+)\^\]")
REF_SP = re.compile(r"(\w+)(\[\^\d+\^\])")
ASR_API = "https://api.assemblyai.com/v2"


class BingAI:
    def __init__(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        text: str = None,
        callback: bool = False,
        inline: bool = False,
    ) -> None:
        self.update = update
        self.context = context
        self.text = text
        self.callback = callback
        self.inline = inline
        self.edit = None
        self.cid = ut.cid(self.update)
        if self.text is None:
            self.text = update.effective_message.text
        self._response = None
        self.expiration = None

    async def run(self) -> None:
        cur_conv = ut.CONV["current"][self.cid]
        if self.callback:
            await self.update.effective_message.edit_reply_markup(None)
        if not self.inline:
            self.edit = await ut.send(
                self.update, f"<b>You</b>: {html.escape(self.text)}"
            )
            turn = str(uuid4())[:8]
            ut.RUN[self.cid][cur_conv].append(turn)
            while turn != ut.RUN[self.cid][cur_conv][0]:
                await asyncio.sleep(5)
            job_name = ut.action_schedule(
                self.update, self.context, constants.ChatAction.TYPING
            )
        ut.CONV["all"][self.cid][cur_conv][1] = self.text
        self._response = await ut.CONV["all"][self.cid][cur_conv][0].ask(
            prompt=self.text,
            conversation_style=getattr(ConversationStyle, db.style(self.cid)),
        )
        if not self.inline:
            ut.RUN[self.cid][cur_conv].remove(turn)
            ut.delete_job(self.context, job_name)
        item = self._response["item"]
        if item["result"]["value"] == "Success":
            self.expiration = item["conversationExpiryTime"]
            ut.delete_conversation(
                self.context, f"{self.cid}_{cur_conv}", self.expiration
            )
            finished = True
            for message in item["messages"]:
                if message["author"] == "bot" and "messageType" not in message:
                    finished = False
                    if "text" in message:
                        await self.parse_message(message)
                    else:
                        if not self.inline:
                            await ut.send(
                                self.update,
                                self.add_throttling(
                                    message["adaptiveCards"][0]["body"][0][
                                        "text"
                                    ]
                                ),
                                quote=True,
                            )
            if finished and not self.inline:
                await self.edit.delete()
                await ut.is_active_conversation(self.update, finished=finished)
                query = BingAI(self.update, self.context)
                await query.run()
        else:
            logging.getLogger("EdgeGPT").error(item["result"]["error"])
            msg = item["result"]["error"]
            if item["result"]["value"] == "Throttled":
                msg = (
                    "Reached Bing chat daily quota. Try again tomorrow, sorry!"
                )
            if not self.inline:
                await ut.send(self.update, f"EdgeGPT error: {msg}")

    def parse_code(self, text: str) -> Union[Tuple[int, int, int, int], None]:
        offset = -1
        while True:
            match = BCODE.search(text, offset + 1)
            if match is not None:
                offset = match.start()
                start = offset
                last = match.group(0)
                padding = 0
                match = BCODE_LANG.match(text[offset:])
                if match is not None:
                    padding = len(match.group(0))
                offset = text.find(last, offset + 1)
                offset += len(last)
                end = offset
                if start == -1 or end - len(last) == -1:
                    break
                yield start, end, padding, len(last)
            else:
                break

    def markdown_to_html(self, text: str) -> str:
        text = REF_SP.sub("\\1 \\2", text)
        idx = 0
        code = []
        not_code = []
        for start, end, spad, epad in self.parse_code(text):
            not_code.append(text[idx:start])
            code.append(
                f"<code>"
                f"{html.escape(text[start+spad:end-epad])}"
                f"</code>"
            )
            idx = end
        not_code.append(text[idx:])
        for idx, sub in enumerate(not_code):
            new = BOLD.sub("<b>\\1\\2</b>", sub)
            new = ITA.sub("<i>\\1\\2</i>", new)
            new = CODE.sub("<code>\\2</code>", new)
            not_code[idx] = new
        added = 0
        for idx, cc in enumerate(code, 1):
            not_code.insert(added + idx, cc)
            added += 1
        return "".join(not_code)

    def add_throttling(self, text: str) -> str:
        throttling = self._response["item"]["throttling"]
        return (
            f"{text}\n\n<code>Message: "
            f"{throttling['numUserMessagesInConversation']}/"
            f"{throttling['maxNumUserMessagesInConversation']}</code>\n"
            f"<code>Conversation ID: {ut.CONV['current'][self.cid]}</code>\n"
        )

    async def tts(self, text: str) -> None:
        job_name = ut.action_schedule(
            self.update, self.context, constants.ChatAction.RECORD_VOICE
        )
        text = REF.sub("", text)
        text = BOLD.sub("\\1\\2", text)
        if ut.DEBUG:
            logging.getLogger("Bot").info(f"\nMessage:\n{text}\n\n")
        comm = edge_tts.Communicate(text, db.voice(self.cid))
        with io.BytesIO() as out:
            async for message in comm.stream():
                if message["type"] == "audio":
                    out.write(message["data"])
            out.seek(0)
            ut.delete_job(self.context, job_name)
            await self.update.effective_message.reply_voice(out)

    async def parse_message(self, message: Dict[str, Any]) -> None:
        text = self.markdown_to_html(message["text"])
        extra = ""
        if "sourceAttributions" in message:
            references = {
                str(idx): ref["seeMoreUrl"]
                for idx, ref in enumerate(message["sourceAttributions"], 1)
            }
            full_ref = [
                f'<a href="{url}">[{idx}]</a>'
                for idx, url in references.items()
            ]
            if references:
                extra = f"\n\n<b>References</b>: {' '.join(full_ref)}"
            text = REF.sub(
                partial(ut.generate_link, references=references), text
            )
        text = f"<b>Bing</b>: {text}"
        tts = False
        if db.tts(self.cid) == 1:
            tts = True
        bt_lst = [ut.button([("🆕 New conversation", "conv_new")])]
        if not tts:
            bt_lst.insert(0, ut.button([("🗣 Text-to-Speech", "tts")]))
            ut.DATA["msg"][self.cid] = message["text"]
        if (
            "suggestedResponses" in message
            and not self.inline
            and not ut.is_group(self.update)
        ):
            for idx, sug in enumerate(message["suggestedResponses"]):
                bt_lst.insert(
                    idx, ut.button([(sug["text"], f"response_{idx}")])
                )
        suggestions = ut.markup(bt_lst)
        question = f"<b>You</b>: {html.escape(self.text)}\n\n"
        if not self.inline:
            await ut.edit(
                self.edit,
                self.add_throttling(f"{question}{text}{extra}"),
                reply_markup=suggestions,
            )
        else:
            await ut.edit_inline(
                self.update,
                self.context,
                self.add_throttling(f"{question}{text}{extra}"),
            )

        if tts and not self.inline:
            await self.tts(message["text"])


class BingImage(Process):
    def __init__(self, prompt: str, queue: Queue):
        Process.__init__(self)
        self.prompt = prompt
        self.queue = queue
        self.daemon = True

    def __exit__(self):
        sys.stdout.close()

    def run(self):
        sys.stdout = open("/dev/null", "w")
        auth = None
        if ut.DATA["cookies"]["all"]:
            cur_cookies = ut.DATA["cookies"]["current"]
            for ck in ut.DATA["cookies"]["all"][cur_cookies]:
                if ck["name"] == "_U":
                    auth = ck["value"]
                    break
            msg = "Invalid cookies"
            if auth is not None:
                image_gen = ImageGen(auth)
                images = None
                try:
                    images = image_gen.get_images(self.prompt)
                except Exception as e:  # noqa
                    logging.getLogger("BingImageCreator").error(msg)
                    msg = e.args[0]
                self.queue.put((images, msg))
            else:
                self.queue.put((None, msg))
        else:
            self.queue.put(
                (None, "Cookies required to use this functionality.")
            )


async def automatic_speech_recognition(
    cid: int, fid: str, data: bytearray
) -> Union[str, None]:
    if "apis" not in ut.DATA["config"]:
        logging.getLogger("Bot").error(
            "API section not defined. Check templates/config.json"
        )
    else:
        if db.asr_backend(cid) == "whisper":
            if not ut.apis("openai").startswith("sk-"):
                logging.getLogger("Bot").error("OpenAI token not defined")
            else:
                return await asr_whisper(fid, data)
        else:
            if ut.apis("assemblyai") == "assemblyai_token":
                logging.getLogger("Bot").error("AssemblyAI token not defined")
            else:
                return await asr_assemblyai(data)


async def asr_assemblyai(data: bytearray) -> str:
    text = "Could not connect to AssemblyAI API. Try again later."
    try:
        async with aiohttp.ClientSession(
            headers={"authorization": ut.apis("assemblyai")}
        ) as session:
            async with session.post(f"{ASR_API}/upload", data=data) as req:
                resp = await req.json()
                upload = {
                    "audio_url": resp["upload_url"],
                    "language_detection": True,
                }
            async with session.post(
                f"{ASR_API}/transcript", json=upload
            ) as req:
                resp = await req.json()
                upload_id = resp["id"]
                status = resp["status"]
                while status not in ("completed", "error"):
                    async with session.get(
                        f"{ASR_API}/transcript/{upload_id}"
                    ) as req2:
                        resp2 = await req2.json()
                        status = resp2["status"]
                        if ut.DEBUG:
                            logging.getLogger("AssemblyAI").info(
                                f"response: {resp2}"
                            )
                            logging.getLogger("AssemblyAI").info(
                                f"{upload_id}: {status}"
                            )
                        await asyncio.sleep(5)
                text = resp2["text"]
    except HTTPException:
        pass
    return text


async def asr_whisper(fid: str, data: bytearray) -> str:
    text = None
    with tempfile.NamedTemporaryFile(suffix=".oga", delete=False) as inp:
        inp.write(data)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as out:
        pass
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", inp.name, out.name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except:  # noqa
        logging.getLogger("FFmpeg").error(
            "Could not convert .oga voice file to .mp3. Check ffmpeg binary"
        )
    else:
        openai.api_key = ut.apis("openai")
        try:
            with open(out.name, "rb") as f:
                resp = await openai.Audio.atranscribe("whisper-1", f)
            text = resp["text"]
        except openai.error.AuthenticationError:
            logging.getLogger("Bot").error("Invalid OpenAI credentials")
        except Exception as e:
            logging.getLogger("OpenAI").error(e)
    Path(inp.name).unlink()
    Path(out.name).unlink()
    return text
