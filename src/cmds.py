#!/usr/bin/env python3

# SPDX-License-Identifier: MIT

# Copyright (c) 2023 scmanjarrez. All rights reserved.
# This work is licensed under the terms of the MIT license.

import asyncio
import json
from multiprocessing import Queue
from queue import Empty
from uuid import uuid4

import backend

import database as db
import utils as ut
from EdgeGPT import ConversationStyle

from telegram import (
    constants,
    InlineQueryResultArticle,
    InlineQueryResultPhoto,
    InputMediaPhoto,
    InputTextMessageContent,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import ContextTypes


HELP = [
    ("new_conversation", "Start a new conversation with the bot"),
    ("change_conversation", "Change your current conversation"),
    ("delete_conversation", "Delete an open conversation"),
    ("image", "Generate images using Bing creator"),
    ("settings", "Change bot settings"),
    ("help", "List of commands"),
]

HIDDEN = [
    ("unlock", "Unlock bot functionalities with a password"),
    (
        "get <code>&lt;config/cookies&gt;</code>",
        "Retrieve config.json or cookies.json, respectively",
    ),
    (
        "update <code>&lt;config/cookies&gt;</code>",
        "Update config.json or cookies.json, respectively",
    ),
    ("cancel", "Cancel current update action"),
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


async def new_conversation(
    update: Update, context: ContextTypes.DEFAULT_TYPE, callback: bool = False
) -> None:
    cid = ut.cid(update)
    ut.add_whitelisted(cid)
    if db.cached(cid):
        if callback:
            await ut.remove_keyboard(update)
        await ut.is_active_conversation(update, new=True)


async def change_conversation(
    update: Update, context: ContextTypes.DEFAULT_TYPE, callback: bool = False
) -> None:
    cid = ut.cid(update)
    ut.add_whitelisted(cid)
    if db.cached(cid):
        resp = ut.send
        if callback:
            resp = ut.edit
        if cid in ut.CONV["all"]:
            cur_conv = ut.CONV["current"][cid]
            btn_lst = [
                ut.button(
                    [
                        (
                            conv if conv != cur_conv else f"» {conv} «",
                            f"conv_set_{conv}",
                        )
                    ]
                )
                for conv in ut.CONV["all"][cid].keys()
            ]
            msg = (
                f"Your current conversation is <b>{cur_conv}</b>\n\n"
                f"<b>Last conversation prompt</b>: "
                f"<code>{ut.CONV['all'][cid][cur_conv][1]}</code>"
                if cur_conv
                else "You don't have an active conversation"
            )
            msg2 = "\n\nOpen conversations:" if btn_lst else ""
            await resp(
                update,
                f"{msg}{msg2}",
                reply_markup=ut.markup(btn_lst) if btn_lst else None,
            )
        else:
            await resp(update, "You don't have open conversations")


async def delete_conversation(
    update: Update, context: ContextTypes.DEFAULT_TYPE, callback: bool = False
) -> None:
    cid = ut.cid(update)
    ut.add_whitelisted(cid)
    if db.cached(cid):
        resp = ut.send
        if callback:
            resp = ut.edit
        if cid in ut.CONV["all"] and ut.CONV["all"][cid]:
            btn_lst = [
                ut.button([(conv, f"conv_del_{conv}")])
                for conv in ut.CONV["all"][cid].keys()
            ]
            msg = "Open conversations" if btn_lst else ""
            await resp(
                update,
                f"{msg}",
                reply_markup=ut.markup(btn_lst) if btn_lst else None,
            )
        else:
            msg = "You don't have open conversations"
            if callback:
                msg = "No more open conversations"
            await resp(update, msg)


async def help_usage(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    cid = ut.cid(update)
    ut.add_whitelisted(cid)
    if db.cached(cid):
        help_fmt = [f"- /{cmd[0]} - {cmd[1]}" for cmd in HELP]
        if cid in ut.chats("admin"):
            help_fmt.append("\nHidden commands:\n")
            for cmd in HIDDEN:
                text = f"- /{cmd[0]} - {cmd[1]}"
                if cmd[0] == "unlock":
                    text = (
                        f"{text}. Current password: "
                        f"<code>{ut.chats('password')}</code>"
                    )
                help_fmt.append(text)
        help_fmt = "\n".join(help_fmt)
        await ut.send(
            update,
            f"The following commands are available:\n\n{help_fmt}",
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
                        _voice if _voice != cur_voice else f"» {_voice} «",
                        f"voice_set_{language}_{gender}_{_voice}",
                    )
                ]
            )
            for _voice in sorted(voices[language][gender])
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
            job_name = ut.action_schedule(update, context, action)
            transcription = await backend.automatic_speech_recognition(
                cid, voice_file.file_id, data
            )
            ut.delete_job(context, job_name)
            if transcription is not None:
                query = backend.BingAI(update, context, transcription)
                asyncio.ensure_future(query.run())


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
            asyncio.ensure_future(query.run())


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
                for _cid, convs in ut.CONV["all"].items():
                    to_del = []
                    for conv_id, (conv, _) in convs.items():
                        await conv.close()
                        to_del.append(conv_id)
                    for conv_id in to_del:
                        del ut.CONV["all"][cid][conv_id]
                    status = await ut.create_conversation(update, _cid)
                    if not status:
                        break
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
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    prompt: str,
    inline: bool = False,
) -> None:
    img_queue = Queue()
    img_gen = backend.BingImage(prompt, img_queue)
    img_gen.start()
    action = constants.ChatAction.UPLOAD_PHOTO
    if not inline:
        job_name = ut.action_schedule(update, context, action)
    while True:
        try:
            data = img_queue.get_nowait()
            if not inline:
                ut.delete_job(context, job_name)
            if data[0] is not None:
                media = [InputMediaPhoto(img) for img in data[0]]
                if not inline:
                    await update.effective_message.reply_media_group(
                        media,
                        caption=f"<b>You</b>: {prompt}",
                        parse_mode=ParseMode.HTML,
                    )
                else:
                    _cid = update.chosen_inline_result.inline_message_id
                    uuid = update.chosen_inline_result.result_id
                    _text = " ".join(
                        update.chosen_inline_result.query.split()[1:]
                    )
                    if _cid not in ut.MEDIA:
                        ut.MEDIA[_cid] = {}
                    ut.MEDIA[_cid][uuid] = (_text, media)
                    await context.bot.edit_message_media(
                        media[0],
                        inline_message_id=_cid,
                        reply_markup=ut.markup(
                            [
                                ut.button(
                                    [
                                        ("<", f"inline_0_{uuid}_-1"),
                                        (">", f"inline_0_{uuid}_1"),
                                    ]
                                )
                            ]
                        ),
                    )
            else:
                if not inline:
                    await ut.send(
                        update,
                        data[1],
                        quote=True,
                    )
                else:
                    await ut.edit_inline(update, context, data[1])
            break
        except Empty:
            await asyncio.sleep(3)


async def inline_query(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.inline_query.query
    if not query:
        return

    args = query.split()
    if len(args) > 1:
        _cmd = args[0].lower()
        _text = " ".join(args[1:])
        results = []
        if _cmd == "query":
            results.append(
                InlineQueryResultArticle(
                    id="query",
                    title=f"Query: {_text}",
                    input_message_content=InputTextMessageContent(
                        "<code>Generating answer...</code>",
                        parse_mode=ParseMode.HTML,
                    ),
                    reply_markup=ut.markup(
                        [ut.button([("🔃 Update 🔃", "nop")])]
                    ),
                )
            )
        elif _cmd == "image":
            uuid = uuid4()
            results.append(
                InlineQueryResultPhoto(
                    id=uuid,
                    title=f"Image: {_text}",
                    photo_url=ut.BING,
                    thumb_url=ut.BING,
                    caption="<code>Generating images...</code>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=ut.markup(
                        [ut.button([("🔃 Update 🔃", "nop")])]
                    ),
                )
            )
        await update.inline_query.answer(results, cache_time=5)


async def inline_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    cid = ut.cid(update)
    if db.cached(cid):
        _args = update.chosen_inline_result.query.split()
        _cmd = _args[0]
        _text = " ".join(_args[1:])
        if _cmd == "query":
            if cid not in ut.CONV["all"]:
                ut.CONV["all"][cid] = {}
                ut.CONV["current"][cid] = ""
            status = await ut.create_conversation(update, cid)
            if status:
                query = backend.BingAI(update, context, _text, inline=True)
                asyncio.ensure_future(query.run())
        else:
            asyncio.ensure_future(
                gather_images(update, context, _text, inline=True)
            )


async def switch_inline_image(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    index: int,
    uuid: str,
    direction: int,
) -> None:
    _cid = update.callback_query.inline_message_id
    if _cid not in ut.MEDIA or uuid not in ut.MEDIA[_cid]:
        await context.bot.edit_message_caption(
            caption=(
                f"<b>You</b>: {ut.MEDIA[_cid][uuid]}\n"
                f"Could not get other images. Try another query."
            ),
            inline_message_id=_cid,
            reply_markup=None,
        )
    else:
        new_idx = (index + direction) % len(ut.MEDIA[_cid][uuid][1])
        await context.bot.edit_message_media(
            ut.MEDIA[_cid][uuid][1][new_idx],
            inline_message_id=_cid,
            reply_markup=ut.markup(
                [
                    ut.button(
                        [
                            ("<", f"inline_{new_idx}_{uuid}_-1"),
                            (">", f"inline_{new_idx}_{uuid}_1"),
                        ]
                    )
                ]
            ),
        )
