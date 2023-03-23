#!/usr/bin/env python3

# SPDX-License-Identifier: MIT

# Copyright (c) 2023 scmanjarrez. All rights reserved.
# This work is licensed under the terms of the MIT license.

import logging

import database as db
import utils as ut
from EdgeGPT import ConversationStyle

from telegram import constants, Update
from telegram.ext import ContextTypes


async def unlock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cid = ut.cid(update)
    ut.add_whitelisted(cid)
    if (
        context.args
        and ut.passwd_correct(context.args[0])
        and not db.cached(cid)
    ):
        db.add_user(cid)
        await ut.send(update, "Bot unlocked. Start a conversation with /new")


async def new(
    update: Update, context: ContextTypes.DEFAULT_TYPE, callback: bool = False
) -> None:
    cid = ut.cid(update)
    ut.add_whitelisted(cid)
    if db.cached(cid):
        if callback:
            await ut.remove_keyboard(update)
        await ut.is_active_conversation(update, new=True)


async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cid = ut.cid(update)
    ut.add_whitelisted(cid)
    if db.cached(cid):
        btn_lst = [
            ut.button([("Language/Voice", "lang_menu")]),
            ut.button([("Conversation style", "style_menu")]),
            ut.button([("Toggle TTS", "tts_menu")]),
        ]
        resp = ut.send
        if update.callback_query is not None:
            resp = ut.edit
        await resp(
            update,
            "Bot settings",
            reply_markup=ut.markup(btn_lst),
        )


async def lang_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    cid = ut.cid(update)
    if db.cached(cid):
        voices = await ut.list_voices()
        cur_voice = db.voice(cid)
        btn_lst = [
            ut.button(
                [(lang.upper(), f"gender_menu_{lang}") for lang in chunk]
            )
            for chunk in ut.chunk(sorted(voices))
        ]
        btn_lst.append(ut.button([("« Back to Settings", "settings_menu")]))
        resp = ut.send
        if update.callback_query is not None:
            resp = ut.edit
        await resp(
            update,
            f"Your current voice is <b>{cur_voice}</b>\n\n" f"Languages",
            reply_markup=ut.markup(btn_lst),
        )


async def gender_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, language: str
) -> None:
    cid = ut.cid(update)
    if db.cached(cid):
        voices = await ut.list_voices()
        cur_voice = db.voice(cid)
        btn_lst = [
            ut.button([(gend, f"voice_menu_{language}_{gend}")])
            for gend in sorted(voices[language])
        ]
        btn_lst.append(
            ut.button(
                [
                    ("« Back to Languages", "lang_menu"),
                    ("« Back to Settings", "settings_menu"),
                ]
            )
        )
        resp = ut.send
        if update.callback_query is not None:
            resp = ut.edit
        await resp(
            update,
            f"Your current voice is <b>{cur_voice}</b>\n\n" f"Genders",
            reply_markup=ut.markup(btn_lst),
        )


async def voice_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    language: str,
    gender: str,
) -> None:
    cid = ut.cid(update)
    if db.cached(cid):
        voices = await ut.list_voices()
        cur_voice = db.voice(cid)
        btn_lst = [
            ut.button(
                [
                    (
                        voice if voice != cur_voice else f"» {voice} «",
                        f"voice_set_{language}_{gender}_{voice}",
                    )
                ]
            )
            for voice in sorted(voices[language][gender])
        ]
        btn_lst.append(
            ut.button(
                [
                    ("« Back to Genders", f"gender_menu_{language}"),
                    ("« Back to Languages", "lang_menu"),
                    ("« Back to Settings", "settings_menu"),
                ]
            )
        )
        resp = ut.send
        if update.callback_query is not None:
            resp = ut.edit
        await resp(
            update,
            f"Your current voice is <b>{cur_voice}</b>\n\n" f"Voices",
            reply_markup=ut.markup(btn_lst),
        )


async def style_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    cid = ut.cid(update)
    if db.cached(cid):
        cur_style = db.style(cid)
        btn_lst = [
            ut.button(
                [
                    (
                        st.name if st.name != cur_style else f"» {st.name} «",
                        f"style_set_{st.name}",
                    )
                ]
            )
            for st in ConversationStyle
        ]
        btn_lst.append(ut.button([("« Back to Settings", "settings_menu")]))
        resp = ut.send
        if update.callback_query is not None:
            resp = ut.edit
        await resp(
            update,
            f"Your current conversation style is <b>{cur_style}</b>\n\n"
            f"Styles",
            reply_markup=ut.markup(btn_lst),
        )


async def tts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cid = ut.cid(update)
    if db.cached(cid):
        cur_tts = db.tts(cid)
        state = "ON" if cur_tts == 1 else "OFF"
        btn_lst = [
            ut.button([(f"TTS: {state}", "tts_toggle")]),
            ut.button([("« Back to Settings", "settings_menu")]),
        ]
        resp = ut.send
        if update.callback_query is not None:
            resp = ut.edit
        await resp(
            update,
            "Automatic Text-to-Speech",
            reply_markup=ut.markup(btn_lst),
        )


async def tts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cid = ut.cid(update)
    if db.cached(cid):
        if cid in ut.DATA["msg"]:
            await ut.all_minus_tts_keyboard(update)
            query = ut.Query(update, context)
            await query.tts(ut.DATA["msg"][cid])
        else:
            await ut.new_keyboard(update)
            await ut.send(
                update, "I can't remember our last conversation, sorry!"
            )


async def voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cid = ut.cid(update)
    ut.add_whitelisted(cid)
    if db.cached(cid):
        status = await ut.is_active_conversation(update)
        if status:
            try:
                token = ut.settings("assemblyai_token")
            except KeyError:
                logging.getLogger("EdgeGPT").error(
                    "assemblyai_token not defined"
                )
            else:
                if token != "assemblyai_token":
                    status = await ut.is_active_conversation(update)
                    if status:
                        voice_file = await update.message.voice.get_file()
                        data = await voice_file.download_as_bytearray()
                        action = constants.ChatAction.RECORD_VOICE
                        ut.action_schedule(update, context, action)
                        transcription = await ut.automatic_speech_recognition(
                            data
                        )
                        ut.delete_job(context, f"{action.name}_{cid}")
                        query = ut.Query(update, context, transcription)
                        await query.run()
                else:
                    logging.getLogger("EdgeGPT").info(
                        "assemblyai_token invalid"
                    )


async def message(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str = None
) -> None:
    cid = ut.cid(update)
    ut.add_whitelisted(cid)
    if db.cached(cid):
        status = await ut.is_active_conversation(update)
        if status:
            callback = False
            if text is not None:
                text = ut.button_query(update, text)
                callback = True
            query = ut.Query(update, context, text, callback=callback)
            await query.run()


async def update_cookies_file(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    cid = ut.cid(update)
    if cid in ut.settings("admin"):
        if db.cached(cid):
            if update.message.document:
                file = await update.message.document.get_file()
                await file.download_to_drive(custom_path=ut.path("cookies"))
                await update.effective_message.reply_text(
                    "updated cookies.json"
                )
            else:
                await ut.send(update, "Please send a file to save")
