# SPDX-License-Identifier: MIT

# Copyright (c) 2023 scmanjarrez. All rights reserved.
# This work is licensed under the terms of the MIT license.

import asyncio
import html
import io
import logging
import re
import subprocess
import tempfile
import time
from functools import partial
from pathlib import Path
from typing import Any, Dict, Tuple, Union
from uuid import uuid4

import aiohttp

import database as db
import edge_tts
import openai
import utils as ut
from aiohttp.web import HTTPException
from EdgeGPT.EdgeGPT import ConversationStyle
from telegram import constants, InputMediaPhoto, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes


BCODE = re.compile(r"(?<!\()(```+)")
BCODE_LANG = re.compile(r"((```+)\w*\n*)")
CODE = re.compile(r"(?<!\()(`+)(.+?)\1(?!\))")
BOLD = re.compile(r"(?<![(`])(?:\*\*([^*`]+?)\*\*|__([^_`]+?)__)")
ITA = re.compile(r"(?<![(`*_])(?:\*([^*`]+?)\*|_([^_`]+?)_)")
REF = re.compile(r"\[\^(\d+)\^\]")
REF_SP = re.compile(r"(\w+)(\[\^\d+\^\])")
REF_INLINE = re.compile(r"[\n]*\[\^(\d+)\^\]:\s*(.+)")
REF_ST = re.compile(r"\[\^?(\d+)\^?\]")
REF_INLINE_ST = re.compile(r"[\n]*\[\^?(\d+)\^?\]:\s*(.+)")
GEN_RESP = re.compile(r".*Generating answers for you\.\.\.(.*)", re.DOTALL)
SRCH_RESP = re.compile(r"Searching the web for.*")
JSON_RESP = re.compile(r"```json(.*?)```", re.DOTALL)
IMG_RESP = re.compile(r"!\[image\d+\]\((.*?)\)")
ASR_API = "https://api.assemblyai.com/v2"
EDIT_DELAY = 0.5
CHAT_LIMIT = 3080


def parse_code(text: str) -> Union[Tuple[int, int, int, int], None]:
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


def markdown_to_html(text: str) -> str:
    text = REF_INLINE.sub("", text)
    text = REF_SP.sub("\\1 \\2", text)
    idx = 0
    code = []
    not_code = []
    for start, end, spad, epad in parse_code(text):
        not_code.append(text[idx:start])
        code.append(
            f"<code>" f"{html.escape(text[start+spad:end-epad])}" f"</code>"
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


async def send_tts_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    conv_id: str,
    msg_idx: str,
) -> None:
    job_name = ut.action_schedule(
        update, context, constants.ChatAction.RECORD_VOICE
    )
    text = REF.sub("", text)
    text = BOLD.sub("\\1\\2", text)
    if ut.DEBUG:
        logging.getLogger("Bot").info(f"\nMessage:\n{text}\n\n")
    comm = edge_tts.Communicate(text, db.voice(ut.cid(update)))
    with io.BytesIO() as out:
        async for message in comm.stream():
            if message["type"] == "audio":
                out.write(message["data"])
        out.seek(0)
        ut.delete_job(context, job_name)
        await update.effective_message.reply_voice(
            out, caption=f"{conv_id}_{msg_idx}.ogg"
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


class BingAI:
    def __init__(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        text: str = None,
        callback: str = None,
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
        self.conv_id = None
        self.last_edit = None
        self._response = None
        self.expiration = None
        self.user_msg = None
        self.user_msg_max = None

    async def run(self) -> None:
        if self.text.startswith("#note"):
            return
        self.conv_id = ut.CONV["current"][self.cid]
        if self.conv_id not in ut.CONV["all"][self.cid]:
            self.conv_id = await ut.create_conversation(self.update, self.cid)
        if self.callback is not None:
            await ut.remove_button(self.update, self.callback)
        if not self.inline:
            self.edit = await ut.send(
                self.update, f"<b>You</b>: {html.escape(self.text)}"
            )
            turn = str(uuid4())[:8]
            ut.RUN[self.cid][self.conv_id].append(turn)
            while turn != ut.RUN[self.cid][self.conv_id][0]:
                await asyncio.sleep(5)
            job_name = ut.action_schedule(
                self.update, self.context, constants.ChatAction.TYPING
            )
        ut.CONV["all"][self.cid][self.conv_id][1] = self.text
        start = time.time()
        edits = 0
        delay = EDIT_DELAY
        warned = False
        try:
            async for final, resp in ut.CONV["all"][self.cid][self.conv_id][
                0
            ].ask_stream(
                prompt=self.text,
                conversation_style=getattr(
                    ConversationStyle, db.style(self.cid)
                ),
            ):
                current = time.time()
                if current - start > delay and not final:
                    resp = JSON_RESP.sub("", resp)
                    resp = SRCH_RESP.sub("", resp)
                    resp = GEN_RESP.sub("\\1", resp)
                    resp = REF_INLINE_ST.sub("", resp)
                    resp = REF_ST.sub("", resp)
                    resp = resp.strip()
                    if resp:
                        text = (
                            f"<b>You</b>: {html.escape(self.text)}\n\n"
                            f"<b>Bing</b>: {html.escape(resp)}"
                        )
                        if len(text) < CHAT_LIMIT:
                            if not self.inline:
                                await ut.edit(self.edit, text)
                            else:
                                await ut.edit_inline(
                                    self.update, self.context, text
                                )
                            edits += 1
                            if not edits % 16:  # too many edits, slow down
                                delay = EDIT_DELAY * 16
                            elif not edits % 8:
                                delay = EDIT_DELAY * 8
                            else:
                                delay = EDIT_DELAY
                        elif not warned:
                            delay = 9999
                            msg = (
                                f"{text}\n\n<code>Message too long. "
                                f"Waiting full response...</code>"
                            )
                            if not self.inline:
                                await ut.edit(self.edit, msg)
                            else:
                                await ut.edit_inline(
                                    self.update, self.context, msg
                                )
                            warned = True
                            self.last_edit = text
                    start = current
                if final:
                    self._response = resp
        except Exception as e:
            await ut.send(self.update, e.args[0])
            ut.delete_job(self.context, job_name)
            return
        if not self.inline:
            ut.RUN[self.cid][self.conv_id].remove(turn)
            ut.delete_job(self.context, job_name)
        item = self._response["item"]
        if item["result"]["value"] == "Success":
            self.user_msg = item["throttling"]["numUserMessagesInConversation"]
            self.user_msg_max = item["throttling"][
                "maxNumUserMessagesInConversation"
            ]
            finished = True
            for message in item["messages"]:
                if message["author"] == "bot" and "messageType" not in message:
                    if message["contentOrigin"] == "TurnLimiter":
                        break
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
                    "Reached Bing chat daily quota. "
                    "Try again tomorrow, sorry!"
                )
            if not self.inline:
                await ut.send(self.update, f"EdgeGPT error: {msg}")

    def add_throttling(self, text: str) -> str:
        return (
            f"{text}\n\n<code>Message: "
            f"{self.user_msg}/{self.user_msg_max}</code>\n"
            f"<code>Conversation ID: {self.conv_id}</code>\n"
        )

    async def parse_message(self, message: Dict[str, Any]) -> None:
        self.message_md = message["text"]
        text = markdown_to_html(self.message_md)
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
        bt_lst = [
            [
                ("📄 Export", f"conv_export_{self.conv_id}"),
                ("❌ Delete", f"conv_delete_bt_{self.conv_id}"),
            ],
            [("✏️ New conversation", "conv_new")],
        ]
        if not tts:
            bt_lst[0].insert(
                0, ("🗣 TTS", f"tts_send_{self.conv_id}_{self.user_msg}")
            )
            if self.cid not in ut.DATA["msg"]:
                ut.DATA["msg"][self.cid] = {}
            ut.DATA["msg"][self.cid][self.conv_id] = message["text"]
        bt_lst = ut.button_list(bt_lst)
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
        msg = self.add_throttling(f"{question}{text}{extra}")
        if len(msg) < CHAT_LIMIT:
            if not self.inline:
                await ut.edit(self.edit, msg, reply_markup=suggestions)
            else:
                await ut.edit_inline(self.update, self.context, msg)
        else:
            if not self.inline:
                await ut.edit(
                    self.edit,
                    self.add_throttling(
                        f"{self.last_edit}\n\n"
                        f"<code>Sending full response as markdown "
                        f"file...</code>"
                    ),
                    reply_markup=suggestions,
                )
                await self.update.effective_message.reply_document(
                    io.BytesIO(self.message_md.encode()),
                    filename=f"{self.conv_id}_{self.user_msg}.md",
                    caption=html.escape(self.text[:1000]),  # max size is 1024
                )
            else:
                await ut.edit_inline(
                    self.update,
                    self.context,
                    self.add_throttling(
                        f"{self.last_edit}\n\n"
                        f"<code>Markdown file can't be sent through "
                        f"inline queries. Switch to this conversation "
                        f"in a private chat ans ask for the last "
                        f"answer</code>"
                    ),
                )

        if tts and not self.inline:
            await send_tts_audio(message["text"])

        if (
            "adaptiveCards" in message
            and "body" in message["adaptiveCards"][0]
        ):
            raw = message["adaptiveCards"][0]["body"][0]["text"]
            images = IMG_RESP.findall(raw)
            if images:
                if not self.inline:
                    media = [InputMediaPhoto(img) for img in images]
                    await self.update.effective_message.reply_media_group(
                        media,
                        caption=f"<b>You</b>: {self.text}",
                        parse_mode=ParseMode.HTML,
                    )
                else:
                    await asyncio.sleep(2)
                    await ut.edit_inline(
                        self.update,
                        self.context,
                        f"{msg}\n"
                        f"<code>Images can't be sent in addition to "
                        f"messages. Use 'image' inline query instead</code>",
                    )
