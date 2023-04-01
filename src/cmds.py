#!/usr/bin/env python3

# SPDX-License-Identifier: MIT

# Copyright (c) 2023 scmanjarrez. All rights reserved.
# This work is licensed under the terms of the MIT license.

import asyncio
import json
from multiprocessing import Queue
from queue import Empty

import backend

import database as db
import utils as ut
from EdgeGPT import ConversationStyle

from telegram import constants, InputMediaPhoto, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes


HELP = [
    ("new", "Start a new conversation with the bot"),
    ("image", "Generate images using Bing creator"),
    ("settings", "Change bot settings"),
    ("help", "List of commands"),
]


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


async def help(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    cid = ut.cid(update)
    ut.add_whitelisted(cid)
    if db.cached(cid):
        help_fmt = "\n".join([f"- /{cmd[0]} - {cmd[1]}" for cmd in HELP])
        await ut.send(
            update, f"The following commands are available:\n\n{help_fmt}"
        )


async def cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    cid = ut.cid(update)
    ut.add_whitelisted(cid)
    if db.cached(cid):
        if cid in ut.STATE:
            del ut.STATE[cid]
            await ut.send(update, "Current action cancelled")


async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cid = ut.cid(update)
    ut.add_whitelisted(cid)
    if db.cached(cid):
        btn_lst = [
            ut.button([("Languages/Voices", "langs_menu")]),
            ut.button([("Conversation styles", "styles_menu")]),
            ut.button([("Toggle TTS", "tts_menu")]),
            ut.button([("Backends", "backends_menu")]),
        ]
        resp = ut.send
        if update.callback_query is not None:
            resp = ut.edit
        await resp(
            update,
            "Bot settings",
            reply_markup=ut.markup(btn_lst),
        )


async def langs_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    cid = ut.cid(update)
    if db.cached(cid):
        voices = await ut.list_voices()
        cur_voice = db.voice(cid)
        btn_lst = [
            ut.button(
                [(lang.upper(), f"genders_menu_{lang}") for lang in chunk]
            )
            for chunk in ut.chunk(sorted(voices))
        ]
        btn_lst.append(ut.button([("« Back to Settings", "settings_menu")]))
        resp = ut.send
        if update.callback_query is not None:
            resp = ut.edit
        await resp(
            update,
            f"Your current voice is <b>{cur_voice}</b>\n\nLanguages list:",
            reply_markup=ut.markup(btn_lst),
        )


async def genders_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, language: str
) -> None:
    cid = ut.cid(update)
    if db.cached(cid):
        voices = await ut.list_voices()
        cur_voice = db.voice(cid)
        btn_lst = [
            ut.button([(gend, f"voices_menu_{language}_{gend}")])
            for gend in sorted(voices[language])
        ]
        btn_lst.append(
            ut.button(
                [
                    ("« Back to Languages", "langs_menu"),
                    ("« Back to Settings", "settings_menu"),
                ]
            )
        )
        resp = ut.send
        if update.callback_query is not None:
            resp = ut.edit
        await resp(
            update,
            f"Your current voice is <b>{cur_voice}</b>\n\nGenders list:",
            reply_markup=ut.markup(btn_lst),
        )


async def voices_menu(
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
                    ("« Back to Genders", f"genders_menu_{language}"),
                    ("« Back to Languages", "langs_menu"),
                    ("« Back to Settings", "settings_menu"),
                ]
            )
        )
        resp = ut.send
        if update.callback_query is not None:
            resp = ut.edit
        await resp(
            update,
            f"Your current voice is <b>{cur_voice}</b>\n\nVoices list:",
            reply_markup=ut.markup(btn_lst),
        )


async def styles_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    cid = ut.cid(update)
    if db.cached(cid):
        cur_style = db.style(cid)
        btn_lst = [
            ut.button(
                [
                    (
                        (
                            st.name.capitalize()
                            if st.name != cur_style
                            else f"» {st.name.capitalize()} «"
                        ),
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
            f"Your current conversation style is "
            f"<b>{cur_style.capitalize()}</b>\n\n"
            f"Conversation styles:",
            reply_markup=ut.markup(btn_lst),
        )


async def tts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cid = ut.cid(update)
    if db.cached(cid):
        cur_tts = db.tts(cid)
        state = "Yes" if cur_tts == 1 else "No"
        btn_lst = [
            ut.button([(f"Enabled: {state}", "tts_toggle")]),
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


async def backends_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    cid = ut.cid(update)
    if db.cached(cid):
        btn_lst = [
            # ut.button([("Chat", "backend_menu_chat")]),
            ut.button([("ASR", "backend_menu_asr")]),
            # ut.button([("Image", "backend_menu_image")]),
            ut.button([("« Back to Settings", "settings_menu")]),
        ]
        resp = ut.send
        if update.callback_query is not None:
            resp = ut.edit
        await resp(
            update,
            "Backends",
            reply_markup=ut.markup(btn_lst),
        )


async def backend_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, backend_type: str
) -> None:
    cid = ut.cid(update)
    if db.cached(cid):
        if backend_type == "chat":
            cur_back = db.chat_backend(cid)
            backends = db.CHAT_BACKENDS
        elif backend_type == "asr":
            cur_back = db.asr_backend(cid)
            backends = db.ASR_BACKENDS
        else:
            cur_back = db.image_backend(cid)
            backends = db.IMAGE_BACKENDS
        btype = (
            backend_type.capitalize()
            if backend_type != "asr"
            else backend_type.upper()
        )
        btn_lst = [
            ut.button(
                [
                    (
                        back if back != cur_back else f"» {back} «",
                        f"backend_set_{backend_type}_{back}",
                    )
                ]
            )
            for back in backends
        ]
        btn_lst.append(
            ut.button(
                [
                    ("« Back to Backends", "backends_menu"),
                    ("« Back to Settings", "settings_menu"),
                ]
            )
        )
        resp = ut.send
        if update.callback_query is not None:
            resp = ut.edit
        await resp(
            update,
            f"Your current {btype} backend is <b>{cur_back}</b>\n\n"
            f"{btype} backends:",
            reply_markup=ut.markup(btn_lst),
        )


async def tts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cid = ut.cid(update)
    if db.cached(cid):
        if cid in ut.DATA["msg"]:
            await ut.all_minus_tts_keyboard(update)
            query = backend.BingAI(update, context)
            await query.tts(ut.DATA["msg"][cid])
        else:
            await ut.new_keyboard(update)
            await ut.send(
                update, "I can't remember our last conversation, sorry!"
            )


async def voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cid = ut.cid(update)
    ut.add_whitelisted(cid)
    if db.cached(cid) and (ut.is_reply(update) or not ut.is_group(update)):
        status = await ut.is_active_conversation(update)
        if status:
            voice_file = await update.message.voice.get_file()
            data = await voice_file.download_as_bytearray()
            action = constants.ChatAction.RECORD_VOICE
            ut.action_schedule(update, context, action)
            transcription = await backend.automatic_speech_recognition(
                cid, voice_file.file_id, data
            )
            ut.delete_job(context, f"{action.name}_{cid}")
            if transcription is not None:
                query = backend.BingAI(update, context, transcription)
                await query.run()


async def message(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str = None
) -> None:
    cid = ut.cid(update)
    ut.add_whitelisted(cid)
    if db.cached(cid) and (ut.is_reply(update) or not ut.is_group(update)):
        status = await ut.is_active_conversation(update)
        if status:
            callback = False
            if text is not None:
                text = ut.button_query(update, text)
                callback = True
            query = backend.BingAI(update, context, text, callback=callback)
            await query.run()


async def get_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cid = ut.cid(update)
    if cid in ut.chats("admin"):
        if context.args and context.args[0] in ("config", "cookies"):
            with ut.path(context.args[0]).open() as f:
                await update.effective_message.reply_document(f)
        else:
            await ut.send(
                update,
                "Tell me the file you want to get: "
                "config/cookies, e.g. /get config, /get cookies",
            )


async def update_file(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    cid = ut.cid(update)
    if cid in ut.chats("admin"):
        if context.args and context.args[0] in ("config", "cookies"):
            ut.STATE[cid] = context.args[0]
            await ut.send(update, f"Ok, send me {context.args[0]}.json file")
        else:
            await ut.send(
                update,
                "Tell me the file you want to update: "
                "config/cookies, e.g. /update config, /update cookies",
            )


async def process_file(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    cid = ut.cid(update)
    if cid in ut.STATE:
        doc = await update.message.document.get_file()
        data = await doc.download_as_bytearray()
        try:
            correct = json.loads(data)
        except json.decoder.JSONDecodeError:
            await ut.send(update, "Invalid JSON. Send me a valid JSON file.")
        else:
            with open(ut.path(ut.STATE[cid]), "w") as f:
                json.dump(correct, f, indent=2)
            if ut.STATE[cid] == "config":
                ut.DATA["config"] = correct
            else:
                for conv in ut.CONV:
                    await ut.CONV[conv].close()
                    ut.CONV[conv] = ut.Chatbot(cookiePath=ut.path("cookies"))
            await ut.send(
                update,
                f"File {ut.STATE[cid]}.json updated successfully",
                quote=True,
            )
            del ut.STATE[cid]


async def image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cid = ut.cid(update)
    if db.cached(cid):
        if context.args:
            asyncio.ensure_future(
                gather_images(update, context, " ".join(context.args))
            )
        else:
            await ut.send(
                update,
                "Give me the prompt on the command, "
                "e.g. /image a friendly shark logo",
                quote=True,
            )


async def gather_images(
    update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str
) -> None:
    img_queue = Queue()
    img_gen = backend.BingImage(prompt, img_queue)
    img_gen.start()
    action = constants.ChatAction.UPLOAD_PHOTO
    ut.action_schedule(update, context, action)
    while True:
        try:
            data = img_queue.get_nowait()
            ut.delete_job(context, f"{action.name}_{ut.cid(update)}")
            media = [InputMediaPhoto(image) for image in data[0]]
            await update.effective_message.reply_media_group(
                media,
                caption=f"<b>You</b>: {prompt}",
                parse_mode=ParseMode.HTML,
            )
            break
        except Empty:
            await asyncio.sleep(3)
