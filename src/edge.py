#!/usr/bin/env python3

# SPDX-License-Identifier: MIT

# Copyright (c) 2023 scmanjarrez. All rights reserved.
# This work is licensed under the terms of the MIT license.

import argparse
import logging
import mimetypes
import subprocess

import cmds

import database as db
import utils as ut

from telegram import Update
from telegram.error import TimedOut
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    ChosenInlineResultHandler,
    CommandHandler,
    ContextTypes,
    filters,
    InlineQueryHandler,
    MessageHandler,
)

LEGACY_VERSION = "v1.2.1"


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = ut.cid(update)
    if db.cached(cid):
        query = update.callback_query
        await query.answer()
        if query.data == "conv_new":
            await cmds.new_conversation(update, context, callback=True)
        elif query.data == "conv_change":
            await cmds.change_conversation(update, context)
        elif query.data == "conv_delete":
            await cmds.delete_conversation(update, context)
        elif query.data.startswith("conv_set"):
            args = query.data.split("_")
            if cid in ut.CONV["current"]:
                ut.CONV["current"][cid] = args[-1]
            await cmds.change_conversation(update, context, callback=True)
        elif query.data.startswith("conv_del"):
            args = query.data.split("_")
            if cid in ut.CONV["all"]:
                await ut.CONV["all"][cid][args[-1]][0].close()
                del ut.CONV["all"][cid][args[-1]]
                cur_conv = ut.CONV["current"][cid]
                if cur_conv == args[-1]:
                    ut.CONV["current"][cid] = ""
            await cmds.delete_conversation(update, context, callback=True)
        elif query.data == "tts":
            await cmds.tts(update, context)
        elif query.data == "settings_menu":
            await cmds.settings(update, context)
        elif query.data == "langs_menu":
            await cmds.langs_menu(update, context)
        elif query.data.startswith("genders_menu"):
            args = query.data.split("_")
            await cmds.genders_menu(update, context, args[-1])
        elif query.data.startswith("voices_menu"):
            args = query.data.split("_")
            await cmds.voices_menu(update, context, args[-2], args[-1])
        elif query.data.startswith("voice_set"):
            args = query.data.split("_")
            db.set_voice(cid, args[-1])
            await cmds.voices_menu(update, context, args[-3], args[-2])
        elif query.data == "styles_menu":
            await cmds.styles_menu(update, context)
        elif query.data.startswith("style_set"):
            args = query.data.split("_")
            db.set_style(cid, args[-1])
            await cmds.styles_menu(update, context)
        elif query.data.startswith("response"):
            args = query.data.split("_")
            await cmds.message(update, context, args[-1])
        elif query.data == "tts":
            await cmds.tts(update, context)
        elif query.data == "tts_menu":
            await cmds.tts_menu(update, context)
        elif query.data == "tts_toggle":
            db.toggle_tts(cid)
            await cmds.tts_menu(update, context)
        elif query.data == "backends_menu":
            await cmds.backends_menu(update, context)
        elif query.data.startswith("backend_menu"):
            args = query.data.split("_")
            await cmds.backend_menu(update, context, args[-1])
        elif query.data.startswith("backend_set"):
            args = query.data.split("_")
            if args[-2] == "chat":
                db.set_chat_backend(cid, args[-1])
            elif args[-2] == "asr":
                db.set_asr_backend(cid, args[-1])
            else:
                db.set_image_backend(cid, args[-1])
            await cmds.backend_menu(update, context, args[-2])
        elif query.data.startswith("inline"):
            args = query.data.split("_")
            await cmds.switch_inline_image(
                update, context, int(args[-3]), args[-2], int(args[-1])
            )


def setup_handlers(app: Application) -> None:
    unlock_handler = CommandHandler("unlock", cmds.unlock)
    app.add_handler(unlock_handler)

    new_handler = CommandHandler("new_conversation", cmds.new_conversation)
    app.add_handler(new_handler)

    change_handler = CommandHandler(
        "change_conversation", cmds.change_conversation
    )
    app.add_handler(change_handler)

    delete_handler = CommandHandler(
        "delete_conversation", cmds.delete_conversation
    )
    app.add_handler(delete_handler)

    image_handler = CommandHandler("image", cmds.image)
    app.add_handler(image_handler)

    settings_handler = CommandHandler("settings", cmds.settings)
    app.add_handler(settings_handler)

    help_handler = CommandHandler("help", cmds.help_usage)
    app.add_handler(help_handler)

    get_handler = CommandHandler("get", cmds.get_file)
    app.add_handler(get_handler)

    update_handler = CommandHandler("update", cmds.update_file)
    app.add_handler(update_handler)

    cancel_handler = CommandHandler("cancel", cmds.cancel)
    app.add_handler(cancel_handler)

    voice_message_handler = MessageHandler(filters.VOICE, cmds.voice)
    app.add_handler(voice_message_handler)

    unrecognized_handler = MessageHandler(filters.COMMAND, cmds.help_usage)
    app.add_handler(unrecognized_handler)

    message_handler = MessageHandler(
        filters.TEXT & ~filters.UpdateType.EDITED & ~filters.VIA_BOT,
        cmds.message,
    )
    app.add_handler(message_handler)

    file_handler = MessageHandler(
        filters.Document.MimeType(mimetypes.types_map[".json"]),
        cmds.process_file,
    )
    app.add_handler(file_handler)

    app.add_handler(CallbackQueryHandler(button_handler))

    app.add_handler(InlineQueryHandler(cmds.inline_query))

    app.add_handler(ChosenInlineResultHandler(cmds.inline_message))


async def close_conversations(app: Application) -> None:
    for convs in ut.CONV["all"].values():
        for conv, _ in convs.values():
            await conv.close()


async def setup_commands(app: Application) -> None:
    await app.bot.set_my_commands(cmds.HELP)


def get_version():
    run_cmd = (
        lambda cmd: subprocess.check_output(cmd, shell=True).decode().strip()
    )
    try:
        version = run_cmd("git describe --tags --abbrev=0 HEAD")
        commit = run_cmd("git rev-parse --short HEAD")
    except subprocess.CalledProcessError:
        return f"{LEGACY_VERSION} (legacy)"
    return f"v{version} - {commit} (git)"


def setup_parser() -> None:
    parser = argparse.ArgumentParser(prog="edge-gpt-telegram-bot")
    parser.add_argument(
        "-d",
        "--dir",
        default="config",
        help="Configuration directory. Default: config",
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config.json",
        help="Configuration file path. Default: config.json",
    )
    parser.add_argument(
        "-k",
        "--cookies",
        default="cookies.json",
        help="Cookies file path. Default: cookies.json",
    )
    parser.add_argument(
        "-b",
        "--database",
        default="edge.db",
        help="Database path. Default: edge.db",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help=(
            "Log debug messages, i.e. EdgeGPT responses, "
            "asr transcriptions..."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {get_version()}"
    )
    args = parser.parse_args()

    for k, v in vars(args).items():
        if k == "debug":
            ut.DEBUG = v
        elif k != "version":
            ut.PATH[k] = v


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    logging.getLogger("apscheduler.executors.default").addFilter(ut.NoLog())
    logging.getLogger("apscheduler.scheduler").addFilter(ut.NoLog())
    logging.getLogger("openai").addFilter(ut.NoLog())

    setup_parser()

    if ut.exists("config"):
        ut.set_up()
        application = (
            ApplicationBuilder()
            .token(ut.settings("token"))
            .post_init(setup_commands)
            .post_shutdown(close_conversations)
            .build()
        )
        setup_handlers(application)
        try:
            if ut.settings("webhook"):
                application.run_webhook(
                    listen=ut.settings("listen"),
                    port=int(ut.settings("port")),
                    url_path=ut.settings("token"),
                    cert=ut.settings("cert"),
                    webhook_url=(
                        f"https://{ut.settings('ip')}/{ut.settings('token')}"
                    ),
                )
            else:
                application.run_polling()
        except TimedOut:
            logging.getLogger("telegram.ext._application").error(
                "Bot could not be initialized. Try again later."
            )
        except KeyError:
            logging.error(
                "New 'webhook' setting required "
                f"in {ut.PATH['config']}. Check README for more info."
            )
    else:
        logging.error(
            f"{ut.PATH['config']} or {ut.PATH['cookies']} file missing."
        )
