# SPDX-License-Identifier: MIT

# Copyright (c) 2023 scmanjarrez. All rights reserved.
# This work is licensed under the terms of the MIT license.

import html
import io
import json
import logging
import re
import sys
from functools import partial
from multiprocessing import Process, Queue
from typing import Any, Dict, Tuple, Union

import database as db
import edge_tts
import utils as ut
from EdgeGPT import ConversationStyle
from ImageGen import ImageGen
from telegram import constants, Update
from telegram.ext import ContextTypes


BCODE = re.compile(r"(?<!\()(```+)")
BCODE_LANG = re.compile(r"((```+)\w*\n*)")
CODE = re.compile(r"(?<!\()(`+)(.+?)\1(?!\))")
BOLD = re.compile(r"(?<![\(`])(?:\*\*([^*`]+?)\*\*|__([^_`]+?)__)")
ITA = re.compile(r"(?<![\(`\*_])(?:\*([^*`]+?)\*|_([^_``]+?)_)")
REF = re.compile(r"\[\^(\d+)\^\]")
REF_SP = re.compile(r"(\w+)(\[\^\d+\^\])")


class Query:
    def __init__(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        text: str = None,
        callback: bool = False,
    ) -> None:
        self.update = update
        self.context = context
        self.text = text
        self.callback = callback
        self.edit = None
        self.cid = ut.cid(self.update)
        if self.text is None:
            self.text = update.effective_message.text

    async def run(self) -> None:
        if self.callback:
            await self.update.effective_message.edit_reply_markup(None)
        self.edit = await ut.send(self.update, f"<b>You</b>: {self.text}")
        ut.action_schedule(
            self.update, self.context, constants.ChatAction.TYPING
        )
        self._response = await ut.CONV[self.cid].ask(
            prompt=self.text,
            conversation_style=getattr(ConversationStyle, db.style(self.cid)),
        )
        ut.delete_job(
            self.context, f"{constants.ChatAction.TYPING.name}_{self.cid}"
        )
        item = self._response["item"]
        if item["result"]["value"] == "Success":
            self.expiration = item["conversationExpiryTime"]
            ut.delete_conversation(
                self.context, str(self.cid), self.expiration
            )
            finished = True
            for message in item["messages"]:
                if message["author"] == "bot":
                    finished = False
                    if "text" in message:
                        await self.parse_message(message)
                    else:
                        await ut.send(
                            self.update,
                            self.add_throttling(
                                message["adaptiveCards"][0]["body"][0]["text"]
                            ),
                            quote=True,
                        )
            if finished:
                await ut.is_active_conversation(self.update, finished=finished)
                query = Query(self.update, self.context)
                await query.run()
        else:
            logging.getLogger("EdgeGPT").error(item["result"]["error"])
            msg = "EdgeGPT API not available. Try again later."
            if item["result"]["value"] == "Throttled":
                msg = (
                    "Reached Bing chat daily quota. Try again tomorrow, sorry!"
                )
            await ut.send(self.update, msg)

    def code(self, text: str) -> Union[Tuple[int, int, int, int], None]:
        offset = -1
        last = None
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
        for start, end, spad, epad in self.code(text):
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
            f"{throttling['maxNumUserMessagesInConversation']}</code>"
        )

    async def tts(self, text: str) -> None:
        ut.action_schedule(
            self.update, self.context, constants.ChatAction.RECORD_VOICE
        )
        text = REF.sub("", text)
        text = BOLD.sub("\\1\\2", text)
        if ut.DEBUG:
            logging.getLogger("EdgeGPT - TTS").info(f"\nMessage:\n{text}\n\n")
        comm = edge_tts.Communicate(text, db.voice(self.cid))
        with io.BytesIO() as out:
            async for message in comm.stream():
                if message["type"] == "audio":
                    out.write(message["data"])
            out.seek(0)
            ut.delete_job(
                self.context,
                f"{constants.ChatAction.RECORD_VOICE.name}_{self.cid}",
            )
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
        bt_lst = [ut.button([("🆕 New topic", "new")])]
        if not tts:
            bt_lst.insert(0, ut.button([("🗣 Text-to-Speech", "tts")]))
            ut.DATA["msg"][self.cid] = message["text"]
        if "suggestedResponses" in message and not ut.is_group(self.update):
            for idx, sug in enumerate(message["suggestedResponses"]):
                bt_lst.insert(
                    idx, ut.button([(sug["text"], f"response_{idx}")])
                )
        suggestions = ut.markup(bt_lst)
        question = f"<b>You</b>: {self.text}\n\n"
        await ut.edit(
            self.edit,
            self.add_throttling(f"{question}{text}{extra}"),
            reply_markup=suggestions,
        )

        if tts:
            await self.tts(message["text"])


class QueryImage(Process):
    def __init__(self, prompt: str, queue: Queue):
        Process.__init__(self)
        self.prompt = prompt
        self.queue = queue
        self.daemon = True

    def __exit__(self):
        sys.stdout.close()

    def run(self):
        sys.stdout = open("/dev/null", "w")
        with open(ut.path("cookies")) as f:
            data = json.load(f)
        for ck in data:
            if ck["name"] == "_U":
                auth = ck["value"]
                break
        image_gen = ImageGen(auth)
        images = None
        try:
            images = image_gen.get_images(self.prompt)
        except:  # noqa
            pass
        self.queue.put((images,))
