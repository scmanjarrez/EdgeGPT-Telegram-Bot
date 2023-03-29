# SPDX-License-Identifier: MIT

# Copyright (c) 2023 scmanjarrez. All rights reserved.
# This work is licensed under the terms of the MIT license.

import asyncio
import html
import io
import json
import logging
import re

import traceback
from functools import partial
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

import aiohttp
import database as db
import edge_tts
from aiohttp.web import HTTPException
from dateutil.parser import isoparse
from EdgeGPT import Chatbot, ConversationStyle
from telegram import (
    constants,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    Update,
)

from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

PATH = {}
DATA = {"config": None, "tts": None, "msg": {}}
CONV = {}
LOG_FILT = ["Removed job", "Added job", "Job", "Running job"]
REF = re.compile(r"\[\^(\d+)\^\]")
REF_SP = re.compile(r"(\w+)(\[\^\d+\^\])")
BCODE = re.compile(r"(?<!\()(```+)")
BCODE_LANG = re.compile(r"((```+)\w*\n*)")
CODE = re.compile(r"(?<!\()(`+)(.+?)\1(?!\))")
BOLD = re.compile(r"(?<![\(`])(?:\*\*([^*`]+?)\*\*|__([^_`]+?)__)")
ITA = re.compile(r"(?<![\(`\*_])(?:\*([^*`]+?)\*|_([^_``]+?)_)")
DEBUG = False
ASR_API = "https://api.assemblyai.com/v2"
STATE = {}


class NoLog(logging.Filter):
    def filter(self, record: logging.LogRecord):
        logged = True
        for lf in LOG_FILT:
            if lf in record.getMessage():
                logged = False
                break
        return logged


def rename_files() -> None:
    cwd = Path(".")
    tmp = cwd.joinpath(".allowed.txt")
    if tmp.exists():
        for _cid in tmp.read_text().split():
            db.add_user(int(_cid))
        tmp.unlink()
    cfg = Path(PATH["dir"])
    for k, v in PATH.items():
        if k not in ("dir", "database"):
            tmp = cwd.joinpath(f".{v}")
            if tmp.exists():
                tmp.rename(cfg.joinpath(v))


def set_up() -> None:
    Path(PATH["dir"]).mkdir(exist_ok=True)
    db.setup_db()
    rename_files()
    with open(path("config")) as f:
        DATA["config"] = json.load(f)
    try:
        logging.getLogger().setLevel(settings("log_level").upper())
    except KeyError:
        pass


def settings(key: str) -> str:
    return DATA["config"]["settings"][key]


def chats(key: str) -> str:
    return DATA["config"]["chats"][key]


def path(key: str) -> str:
    return Path(PATH["dir"]).joinpath(PATH[key])


def exists(key: str) -> bool:
    return Path(".").joinpath(f".{PATH[key]}").exists() or path(key).exists()


def passwd_correct(passwd: str) -> bool:
    return passwd == DATA["config"]["chats"]["password"]


def whitelisted(cid: int) -> bool:
    return cid in chats("id")


def add_whitelisted(cid: int) -> None:
    if whitelisted(cid) and not db.cached(cid):
        db.add_user(cid)


def cid(update: Update) -> int:
    return update.effective_chat.id


def is_group(update: Update) -> bool:
    return update.effective_chat.id < 0


def is_reply(update: Update) -> bool:
    return (
        is_group(update)
        and update.effective_message.reply_to_message.from_user.is_bot
    )


def button(buttons) -> List[InlineKeyboardButton]:
    return [InlineKeyboardButton(bt[0], callback_data=bt[1]) for bt in buttons]


def markup(buttons: List[List[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(buttons)


def button_query(update: Update, index: str) -> str:
    for (kb,) in update.effective_message.reply_markup.inline_keyboard:
        if kb.callback_data == f"response_{index}":
            return kb.text


def chunk(lst: List[str], size: int = 6) -> List[str]:
    for idx in range(0, len(lst), size):
        yield lst[idx : idx + size]


async def list_voices() -> Dict[str, Dict[str, List[str]]]:
    if DATA["tts"] is None:
        DATA["tts"] = {}
        voices = await edge_tts.list_voices()
        for vc in voices:
            lang = vc["Locale"].split("-")[0]
            gend = vc["Gender"]
            if lang not in DATA["tts"]:
                DATA["tts"][lang] = {}
            if gend not in DATA["tts"][lang]:
                DATA["tts"][lang][gend] = []
            DATA["tts"][lang][gend].append(vc["ShortName"])
    return DATA["tts"]


async def _remove_conversation(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    await CONV[job.chat_id].close()
    del CONV[job.chat_id]


def delete_job(context: ContextTypes.DEFAULT_TYPE, name: str) -> None:
    current_jobs = context.job_queue.get_jobs_by_name(name)
    for job in current_jobs:
        job.schedule_removal()


def delete_conversation(
    context: ContextTypes.DEFAULT_TYPE, name: str, expiration: str
) -> None:
    delete_job(context, name)
    context.job_queue.run_once(
        _remove_conversation,
        isoparse(expiration),
        chat_id=int(name),
        name=name,
    )


async def send(
    update: Update,
    text: str,
    quote: bool = False,
    reply_markup: InlineKeyboardMarkup = None,
) -> Message:
    return await update.effective_message.reply_html(
        text,
        disable_web_page_preview=True,
        quote=quote,
        reply_markup=reply_markup,
    )


async def edit(
    update_message: Union[Update, Message],
    text: str,
    reply_markup: InlineKeyboardMarkup = None,
) -> None:
    try:
        if isinstance(update_message, Update):
            await update_message.callback_query.edit_message_text(
                text,
                ParseMode.HTML,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
        else:
            await update_message.edit_text(
                text,
                ParseMode.HTML,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
    except BadRequest as br:
        if not str(br).startswith("Message is not modified:"):
            if isinstance(update_message, Update):
                cid = update_message.effective_message.chat.id
            else:
                update_message.chat.id
            print(
                f"***  Exception caught in edit ({cid}): ",
                br,
            )
            traceback.print_stack()


async def remove_keyboard(update: Update) -> None:
    await update.effective_message.edit_reply_markup(None)


async def new_keyboard(update: Update) -> None:
    new_kb = []
    for (kb,) in update.effective_message.reply_markup.inline_keyboard:
        if kb.callback_data == "new":
            new_kb.append(button([(kb.text, kb.callback_data)]))
    await update.effective_message.edit_reply_markup(markup(new_kb))


async def all_minus_tts_keyboard(update: Update) -> None:
    new_kb = []
    for (kb,) in update.effective_message.reply_markup.inline_keyboard:
        if kb.callback_data != "tts":
            new_kb.append(button([(kb.text, kb.callback_data)]))
    await update.effective_message.edit_reply_markup(markup(new_kb))


async def is_active_conversation(
    update: Update, new=False, finished=False
) -> bool:
    _cid = cid(update)
    if new or finished or _cid not in CONV:
        if _cid in CONV:
            await CONV[_cid].close()
        try:
            CONV[_cid] = Chatbot(cookiePath=path("cookies"))
        except Exception as e:
            logging.getLogger("EdgeGPT").error(e)
            await send(update, "EdgeGPT API not available. Try again later.")
            return False
        else:
            group = "Reply to any of my messages to interact with me."
            if new:
                await send(
                    update,
                    (
                        f"Starting new conversation. "
                        f"Ask me anything..."
                        f"{group if is_group(update) else ''}"
                    ),
                )
    return True


async def send_action(context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_chat_action(context.job.chat_id, context.job.data)


def action_schedule(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    action: constants.ChatAction,
) -> None:
    _cid = cid(update)
    context.job_queue.run_repeating(
        send_action,
        7,
        first=1,
        chat_id=_cid,
        data=action,
        name=f"{action.name}_{_cid}",
    )


def generate_link(match: re.Match, references: dict) -> str:
    text = match.group(1)
    link = f"[{text}]"
    if text in references:
        link = f"<a href='{references[text]}'>[{text}]</a>"
    return link


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
        self.cid = cid(self.update)
        if self.text is None:
            self.text = update.effective_message.text

    async def run(self) -> None:
        if self.callback:
            await self.update.effective_message.edit_reply_markup(None)
        self.edit = await send(self.update, f"<b>You</b>: {self.text}")
        action_schedule(self.update, self.context, constants.ChatAction.TYPING)
        self._response = await CONV[self.cid].ask(
            prompt=self.text,
            conversation_style=getattr(ConversationStyle, db.style(self.cid)),
        )
        delete_job(
            self.context, f"{constants.ChatAction.TYPING.name}_{self.cid}"
        )
        item = self._response["item"]
        if item["result"]["value"] == "Success":
            self.expiration = item["conversationExpiryTime"]
            delete_conversation(self.context, str(self.cid), self.expiration)
            finished = True
            for message in item["messages"]:
                if message["author"] == "bot":
                    finished = False
                    if "text" in message:
                        await self.parse_message(message)
                    else:
                        await send(
                            self.update,
                            self.add_throttling(
                                message["adaptiveCards"][0]["body"][0]["text"]
                            ),
                            quote=True,
                        )
            if finished:
                await is_active_conversation(self.update, finished=finished)
                query = Query(self.update, self.context)
                await query.run()
        else:
            logging.getLogger("EdgeGPT").error(item["result"]["error"])
            msg = "EdgeGPT API not available. Try again later."
            if item["result"]["value"] == "Throttled":
                msg = (
                    "Reached Bing chat daily quota. Try again tomorrow, sorry!"
                )
            await send(self.update, msg)

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
        action_schedule(
            self.update, self.context, constants.ChatAction.RECORD_VOICE
        )
        text = REF.sub("", text)
        text = BOLD.sub("\\1\\2", text)
        if DEBUG:
            logging.getLogger("EdgeGPT - TTS").info(f"\nMessage:\n{text}\n\n")
        comm = edge_tts.Communicate(text, db.voice(self.cid))
        with io.BytesIO() as out:
            async for message in comm.stream():
                if message["type"] == "audio":
                    out.write(message["data"])
            out.seek(0)
            delete_job(
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
            text = REF.sub(partial(generate_link, references=references), text)
        text = f"<b>Bing</b>: {text}"
        tts = False
        if db.tts(self.cid) == 1:
            tts = True
        bt_lst = [button([("🆕 New topic", "new")])]
        if not tts:
            bt_lst.insert(0, button([("🗣 Text-to-Speech", "tts")]))
            DATA["msg"][self.cid] = message["text"]
        if "suggestedResponses" in message and not is_group(self.update):
            for idx, sug in enumerate(message["suggestedResponses"]):
                bt_lst.insert(idx, button([(sug["text"], f"response_{idx}")]))
        suggestions = markup(bt_lst)
        question = f"<b>You</b>: {self.text}\n\n"
        await edit(
            self.edit,
            self.add_throttling(f"{question}{text}{extra}"),
            reply_markup=suggestions,
        )

        if tts:
            await self.tts(message["text"])


async def automatic_speech_recognition(data: bytearray) -> str:
    text = "Could not connect to AssemblyAI API. Try again later."
    try:
        async with aiohttp.ClientSession(
            headers={"authorization": settings("assemblyai_token")}
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
                    ) as req:
                        resp = await req.json()
                        status = resp["status"]
                        if DEBUG:
                            logging.getLogger("EdgeGPT-ASR").info(
                                f"response: {resp}"
                            )
                            logging.getLogger("EdgeGPT-ASR").info(
                                f"{upload_id}: {status}"
                            )
                        await asyncio.sleep(5)
                text = resp["text"]
    except HTTPException:
        pass
    return text
