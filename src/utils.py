# SPDX-License-Identifier: MIT

# Copyright (c) 2023 scmanjarrez. All rights reserved.
# This work is licensed under the terms of the MIT license.


import json
import logging
import re

import traceback

from pathlib import Path
from typing import Dict, List, Union

import database as db

import edge_tts

from dateutil.parser import isoparse
from EdgeGPT import Chatbot

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
    "cookies": {"all": {}, "current": {}},
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
    db.update_db()
    rename_files()
    with open(path("config")) as f:
        DATA["config"] = json.load(f)
    for cookie in DATA["config"]["cookies"]:
        _path = Path(cookie)
        if _path.exists():
            with _path.open() as f:
                DATA["cookies"]["all"][_path.stem] = json.load(f)
    if "cookies" in DATA["config"]:
        _path = Path(PATH["dir"]).joinpath("current_cookie")
        if _path.exists():
            with _path.open() as f:
                DATA["cookies"]["current"] = f.read().strip()
        else:
            DATA["cookies"]["current"] = list(DATA["cookies"]["all"].keys())[0]
            with _path.open("w") as f:
                f.write(DATA["cookies"]["current"])
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


def delete_conversation(
    context: ContextTypes.DEFAULT_TYPE, name: str, expiration: str
) -> None:
    delete_job(context, name)
    context.job_queue.run_once(
        _remove_conversation,
        isoparse(expiration),
        data=name.split("_"),
        name=name,
    )


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


async def create_conversation(
    update: Update, chat_id: Union[int, None] = None
) -> str:
    if chat_id is None:
        chat_id = cid(update)
    try:
        if DATA["cookies"]["all"]:
            cur_cookies = DATA["cookies"]["current"]
            tmp = Chatbot(cookies=DATA["cookies"]["all"][cur_cookies])
        else:
            tmp = Chatbot()
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
    update: Update, new=False, finished=False
) -> bool:
    _cid = cid(update)
    if _cid not in CONV["all"]:
        CONV["all"][_cid] = {}
        CONV["current"][_cid] = ""
        RUN[_cid] = {}
    if new or finished or not CONV["current"][_cid]:
        if finished:
            await CONV["all"][_cid][CONV["current"][_cid]][0].close()
            del CONV["all"][_cid][CONV["current"][_cid]]
        status = await create_conversation(update)
        if not status:
            return False
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
