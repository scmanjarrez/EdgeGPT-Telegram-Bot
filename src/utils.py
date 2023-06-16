# SPDX-License-Identifier: MIT

# Copyright (c) 2023 scmanjarrez. All rights reserved.
# This work is licensed under the terms of the MIT license.


import asyncio
import json
import logging
import re

import traceback

from pathlib import Path
from threading import Thread
from typing import Dict, List, Union

import aiohttp

import database as db

import edge_tts

from EdgeGPT.EdgeGPT import Chatbot
from EdgeGPT.request import ChatHubRequest

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
DATA = {
    "config": None,
    "cookies": {"all": {}, "current": {}, "_U": {}},
    "tts": None,
    "msg": {},
}
CONV = {"all": {}, "current": {}}
RUN = {}
LOG_FILT = [
    "Removed job",
    "Added job",
    "Job",
    "Running job",
    "message=",
    "HTTP Request",
]
DEBUG = False
STATE = {}
MEDIA = {}
BING = (
    "http://upload.wikimedia.org/wikipedia/commons/thumb/9/9c/"
    "Bing_Fluent_Logo.svg/32px-Bing_Fluent_Logo.svg.png"
)
CHAT_END = [
    "https://www.bing.com/turing/conversation/chats",
    {
        "x-ms-useragent": (
            "azsdk-js-api-client-factory/"
            "1.0.0-beta.1 core-rest-pipeline/1.10.3 OS/Windows"
        ),
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 "
            "Safari/537.36 Edg/114.0.1823.41"
        ),
    },
]


class NoLog(logging.Filter):
    def filter(self, record: logging.LogRecord):
        logged = True
        for lf in LOG_FILT:
            if lf in record.getMessage():
                logged = False
                break
        return logged


def no_log(loggers: List[str]) -> None:
    for logger in loggers:
        logging.getLogger(logger).addFilter(NoLog())


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


def init_chat(chat_id: int) -> None:
    if chat_id not in CONV["all"]:
        CONV["all"][chat_id] = {}
        CONV["current"][chat_id] = ""
        RUN[chat_id] = {}


def load_chat(conv_data: List, chat_id: int = None) -> None:
    short = conv_data[0]["conversation_id"].split("|")[2][:10]
    if chat_id is None:
        chat_id = chats("admin")[0]
    init_chat(chat_id)
    if short not in CONV["all"][chat_id]:
        tmp = create_chatbot()
        tmp.chat_hub.request = ChatHubRequest(**conv_data[0])
        CONV["all"][chat_id][short] = [tmp, conv_data[1]]
        RUN[chat_id][short] = []


async def retrieve_history() -> None:
    curr = DATA["cookies"]["current"]
    head = CHAT_END[1].copy()
    head["Cookie"] = "SUID=A; _U={};".format(DATA["cookies"]["_U"][curr])
    async with aiohttp.ClientSession(headers=head) as session:
        async with session.get(CHAT_END[0]) as resp:
            data = json.loads(await resp.text())
            if data["chats"]:
                client_id = data["clientId"]
                CONV["all"].clear()
                CONV["current"].clear()
                RUN.clear()
                for chat in data["chats"]:
                    name = chat["chatName"]
                    conversation_id = chat["conversationId"]
                    signature = chat["conversationSignature"]
                    thread = Thread(
                        target=load_chat,
                        args=(
                            [
                                {
                                    "conversation_id": conversation_id,
                                    "conversation_signature": signature,
                                    "client_id": client_id,
                                    "invocation_id": 4,
                                },
                                name,
                            ],
                        ),
                        daemon=True,
                    )
                    thread.start()


def setup() -> None:
    Path(PATH["dir"]).mkdir(exist_ok=True)
    db.setup_db()
    db.update_db()
    rename_files()
    missing = False
    with open(path("config")) as f:
        DATA["config"] = json.load(f)
    if "remove_chats_on_stop" not in DATA["config"]["chats"]:
        DATA["config"]["chats"]["remove_chats_on_stop"] = False
        missing = True
    if "history" not in DATA["config"]["chats"]:
        DATA["config"]["chats"]["history"] = True
        missing = True
    if missing:
        logging.error(
                "New setting is missing, using default value. "
                "Check README for more info."
            )
    for cookie in DATA["config"]["cookies"]:
        _path = Path(cookie)
        if _path.exists():
            with _path.open() as f:
                DATA["cookies"]["all"][_path.stem] = json.load(f)
            for ck in DATA["cookies"]["all"][_path.stem]:
                if ck["name"] == "_U":
                    DATA["cookies"]["_U"][_path.stem] = ck["value"]
                    break
    if DATA["cookies"]["all"]:
        _path = Path(PATH["dir"]).joinpath("current_cookie")
        if _path.exists():
            with _path.open() as f:
                DATA["cookies"]["current"] = f.read().strip()
        else:
            DATA["cookies"]["current"] = list(DATA["cookies"]["all"].keys())[0]
            with _path.open("w") as f:
                f.write(DATA["cookies"]["current"])
        if chats("history"):
            _path = Path(PATH["dir"]).joinpath("history.json")
            if not _path.exists():
                loop = asyncio.get_event_loop()
                loop.create_task(retrieve_history())
            else:
                added = []
                with _path.open() as f:
                    hist = json.load(f)
                    for chat_id, conv in hist.items():
                        chat_id = int(chat_id)
                        for _, (conv_metadata, prompt) in conv.items():
                            thread = Thread(
                                target=load_chat,
                                args=([conv_metadata, prompt], chat_id),
                                daemon=True,
                            )
                            thread.start()
                            added.append(conv_metadata["conversation_id"])
    try:
        logging.getLogger().setLevel(settings("log_level").upper())
    except KeyError:
        pass


def settings(key: str) -> Union[str, List]:
    return DATA["config"]["settings"][key]


def apis(key: str) -> str:
    return DATA["config"]["apis"][key]


def chats(key: str) -> Union[str, List]:
    return DATA["config"]["chats"][key]


def path(key: str) -> Path:
    return Path(PATH["dir"]).joinpath(PATH[key])


def exists(key: str) -> bool:
    return Path(".").joinpath(f".{PATH[key]}").exists() or path(key).exists()


def passwd_correct(passwd: str) -> bool:
    return passwd == DATA["config"]["chats"]["password"]


def whitelisted(_cid: int) -> bool:
    return _cid in chats("id")


def add_whitelisted(_cid: int) -> None:
    if whitelisted(_cid) and not db.cached(_cid):
        db.add_user(_cid)


def cid(update: Update) -> int:
    try:
        return update.effective_chat.id
    except AttributeError:
        try:
            return update.chosen_inline_result.from_user.id
        except AttributeError:
            return update.callback_query.from_user.id


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
    _cid, conv_id = context.job.data
    _cid = int(_cid)
    await CONV["all"][_cid][conv_id][0].close()
    del CONV["all"][_cid][conv_id]
    CONV["current"][_cid] = ""


def delete_job(context: ContextTypes.DEFAULT_TYPE, name: str) -> None:
    current_jobs = context.job_queue.get_jobs_by_name(name)
    for job in current_jobs:
        job.schedule_removal()


async def send(
    update: Update,
    text: str,
    quote: bool = False,
    reply_markup: InlineKeyboardMarkup = None,
) -> Message:
    message = update.effective_message
    return await message.reply_html(
        text,
        disable_web_page_preview=True,
        quote=quote,
        reply_markup=reply_markup,
        message_thread_id=(
            message.message_thread_id if message.is_topic_message else None
        ),
    )


async def no_permissions(update: Update) -> None:
    await send(update, "🙅 You don't have permissions to run this command")


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
                _cid = update_message.effective_message.chat.id
            else:
                _cid = update_message.chat.id
            print(
                f"***  Exception caught in edit ({_cid}): ",
                br,
            )
            traceback.print_stack()


async def edit_inline(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str
) -> None:
    await context.bot.edit_message_text(
        text,
        inline_message_id=update.chosen_inline_result.inline_message_id,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def edit_inline_media(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, media: list
) -> None:
    await context.bot.edit_message_text(
        text,
        inline_message_id=update.chosen_inline_result.inline_message_id,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


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


def create_chatbot() -> Chatbot:
    if DATA["cookies"]["all"]:
        cur_cookies = DATA["cookies"]["current"]
        tmp = Chatbot(cookies=DATA["cookies"]["all"][cur_cookies])
    else:
        tmp = Chatbot()
    return tmp


async def create_conversation(
    update: Update, chat_id: Union[int, None] = None
) -> str:
    if chat_id is None:
        chat_id = cid(update)
    try:
        tmp = create_chatbot()
    except Exception as e:
        logging.getLogger("EdgeGPT").error(e)
        await send(update, f"EdgeGPT error: {e.args[0]}")
        return ""
    else:
        conv_id = tmp.chat_hub.request.conversation_id.split("|")[2][:10]
        CONV["all"][chat_id][conv_id] = [tmp, ""]
        CONV["current"][chat_id] = conv_id
        RUN[chat_id][conv_id] = []
    return conv_id


async def is_active_conversation(
    update: Update,
    new: bool = False,
    finished: bool = False,
    quiet: bool = False,
) -> bool:
    _cid = cid(update)
    init_chat(_cid)
    if new or finished or not CONV["current"][_cid]:
        if finished:
            await CONV["all"][_cid][CONV["current"][_cid]][0].close()
            del CONV["all"][_cid][CONV["current"][_cid]]
        status = await create_conversation(update)
        if not status:
            return False
        group = "Reply to any of my messages to interact with me."
        if new and not quiet:
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
    action, thread_id = context.job.data
    await context.bot.send_chat_action(context.job.chat_id, action, thread_id)


def action_schedule(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    action: constants.ChatAction,
) -> str:
    _cid = cid(update)
    thread_id = None
    thread_text = ""
    try:
        if update.effective_message.is_topic_message:
            thread_id = update.effective_message.message_thread_id
            thread_text = f"_{thread_id}"
    except AttributeError:
        pass
    job_name = f"{action.name}_{_cid}{thread_text}"
    context.job_queue.run_repeating(
        send_action,
        7,
        first=1,
        chat_id=_cid,
        data=(action, thread_id),
        name=job_name,
    )
    return job_name


def generate_link(match: re.Match, references: dict) -> str:
    text = match.group(1)
    link = f"[{text}]"
    if text in references:
        link = f"<a href='{references[text]}'>[{text}]</a>"
    return link
