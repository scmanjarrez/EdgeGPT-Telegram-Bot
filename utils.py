# SPDX-License-Identifier: MIT

# Copyright (c) 2023 scmanjarrez. All rights reserved.
# This work is licensed under the terms of the MIT license.

from telegram import (constants, InlineKeyboardButton,
                      InlineKeyboardMarkup, KeyboardButton,
                      ReplyKeyboardMarkup, ReplyKeyboardRemove)
from telegram.ext import ContextTypes
from dateutil.parser import isoparse
from EdgeGPT import Chatbot
from telegram import Update

import logging
import json
import re

REF = re.compile(r'\[\^(\d+)\^\]')
FILE = {
    'cfg': '.config.json',
    'cookies': '.cookies.json',
    'allowed': '.allowed.txt'
}
DATA = {
    'cfg': None,
    'allowed': []
}
CONV = {}


def set_up() -> None:
    with open(FILE['cfg']) as f:
        DATA['cfg'] = json.load(f)
    try:
        with open(FILE['allowed']) as f:
            DATA['allowed'] = [int(_cid) for _cid in f.read().splitlines()]
    except FileNotFoundError:
        DATA['allowed'] = []


def settings(key: str) -> str:
    return DATA['cfg']['settings'][key]


def passwd_correct(passwd: str) -> bool:
    return passwd == DATA['cfg']['chats']['password']


def allowed(update: Update) -> bool:
    _cid = cid(update)
    return _cid in DATA['allowed'] or _cid in DATA['cfg']['chats']['id']


def cid(update: Update) -> int:
    return update.effective_chat.id


def unlock(chat_id: int) -> None:
    DATA['allowed'].append(chat_id)
    with open(FILE['allowed'], 'a') as f:
        f.write(f'{chat_id}\n')


def is_group(update: Update) -> bool:
    return update.effective_chat.id < 0


def reply_markup(buttons: list) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[KeyboardButton(bt)] for bt in buttons])


def inline_markup(buttons: list) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(bt[0], bt[1])] for bt in buttons])


async def _remove_conversation(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    await CONV[job.chat_id].close()
    del CONV[job.chat_id]


def delete_conversation(context: ContextTypes.DEFAULT_TYPE,
                        name: str, expiration: str) -> None:
    current_jobs = context.job_queue.get_jobs_by_name(name)
    for job in current_jobs:
        job.schedule_removal()
    context.job_queue.run_once(_remove_conversation,
                               isoparse(expiration),
                               chat_id=int(name),
                               name=name)


async def send(update: Update, text, quote=False, reply_markup=None) -> None:
    return await update.effective_message.reply_html(
        text, disable_web_page_preview=True,
        quote=quote, reply_markup=reply_markup)


async def is_active_conversation(update: Update, new=False) -> bool:
    _cid = cid(update)
    if new or _cid not in CONV:
        if _cid in CONV:
            await CONV[_cid].close()
        try:
            CONV[_cid] = Chatbot(cookiePath=FILE['cookies'])
        except Exception as e:
            logging.getLogger('EdgeGPT').error(e)
            await send(update,
                       "EdgeGPT API not available. Try again later.")
            return False
        else:
            missing = "No conversation found or expired. "
            group = ("Reply to any of my messages to interact with me.")
            await send(update,
                       (f"{missing if not new else ''}"
                        f"Starting new conversation... "
                        f"{group if is_group(update) else ''}"),
                       reply_markup=ReplyKeyboardRemove())
    return True


class Query:
    def __init__(self, update: Update,
                 context: ContextTypes.DEFAULT_TYPE) -> None:
        self.update = update
        self.context = context

    async def run(self) -> None:
        await self.update.effective_chat.send_chat_action(
            constants.ChatAction.TYPING)
        try:
            self._response = await CONV[cid(self.update)].ask(
                self.update.effective_message.text)
        except Exception as e:
            logging.getLogger('EdgeGPT').error(e)
            await send(self.update,
                       "EdgeGPT API not available. Try again later.")
        else:
            self.resp_id = self._response['invocationId']
            # I got a response without this field,
            # I'm not sure if something wrong happened
            if 'conversationExpiryTime' in self._response['item']:
                self.expiration = self._response[
                    'item']['conversationExpiryTime']
                delete_conversation(self.context, str(cid(self.update)),
                                    self.expiration)
            self.conv_id = self._response['item']['conversationId']
            await self.parse_message(self._response['item']['messages'][1])

    async def parse_message(self, message: dict) -> None:
        text = REF.sub(' <b>[\\1]</b>', message['text'])
        references = '\n'.join([
            f"- <b>[{idx}]</b>: <a href='{ref['seeMoreUrl']}'>"
            f"{ref['providerDisplayName']}</a>"
            for idx, ref in enumerate(message['sourceAttributions'], 1)
        ])
        msg_ref = f"\n\n<b>References</b>:\n{references}"
        suggestions = reply_markup(
            [sug['text'] for sug in message['suggestedResponses']])
        msg = f"{text}{msg_ref if references else ''}"
        await send(self.update, msg,
                   reply_markup=(None
                                 if is_group(self.update)
                                 else suggestions),
                   quote=True)
