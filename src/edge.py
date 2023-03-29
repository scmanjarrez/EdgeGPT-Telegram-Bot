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
    CommandHandler,
    ContextTypes,
    filters,
    MessageHandler,
)
from version import __VERSION__

LEGACY_VERSION = "v0.1.3"


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = ut.cid(update)
    if db.cached(cid):
        query = update.callback_query
        await query.answer()
        if query.data == "new":
            await cmds.new(update, context, callback=True)
        if query.data == "tts":
            await cmds.tts(update, context)
        elif query.data == "settings_menu":
            await cmds.settings(update, context)
        elif query.data == "lang_menu":
            await cmds.lang_menu(update, context)
        elif query.data.startswith("gender_menu"):
            args = query.data.split("_")
            await cmds.gender_menu(update, context, args[-1])
        elif query.data.startswith("voice_menu"):
            args = query.data.split("_")
            await cmds.voice_menu(update, context, args[-2], args[-1])
        elif query.data.startswith("voice_set"):
            args = query.data.split("_")
            db.set_voice(cid, args[-1])
            await cmds.voice_menu(update, context, args[-3], args[-2])
        elif query.data == "style_menu":
            await cmds.style_menu(update, context)
        elif query.data.startswith("style_set"):
            args = query.data.split("_")
            db.set_style(cid, args[-1])
            await cmds.style_menu(update, context)
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


def setup_handlers(app: ApplicationBuilder) -> None:
    unlock_handler = CommandHandler("unlock", cmds.unlock)
    app.add_handler(unlock_handler)

    new_handler = CommandHandler("new", cmds.new)
    app.add_handler(new_handler)

    settings_handler = CommandHandler("settings", cmds.settings)
    app.add_handler(settings_handler)

    help_handler = CommandHandler("help", cmds.help)
    app.add_handler(help_handler)

    get_handler = CommandHandler("get", cmds.get_file)
    app.add_handler(get_handler)

    update_handler = CommandHandler("update", cmds.update_file)
    app.add_handler(update_handler)

    cancel_handler = CommandHandler("cancel", cmds.cancel)
    app.add_handler(cancel_handler)

    voice_message_handler = MessageHandler(filters.VOICE, cmds.voice)
    app.add_handler(voice_message_handler)

    message_handler = MessageHandler(
        filters.TEXT & ~filters.UpdateType.EDITED, cmds.message
    )
    app.add_handler(message_handler)

    file_handler = MessageHandler(
        filters.Document.MimeType(mimetypes.types_map[".json"]),
        cmds.process_file,
    )
    app.add_handler(file_handler)

    app.add_handler(CallbackQueryHandler(button_handler))


async def close_chats(application: Application) -> None:
    for chat in ut.CONV.values():
        await chat.close()


async def setup_commands(application: Application) -> None:
    await application.bot.set_my_commands(cmds.HELP)


def get_version():
    run_cmd = (
        lambda cmd: subprocess.check_output(cmd, shell=True).decode().strip()
    )
    try:
        version = run_cmd("git describe --tags --abbrev=0 HEAD")
        commit = run_cmd("git rev-parse --short HEAD")
    except:
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

    setup_parser()

    if ut.exists("config") and ut.exists("cookies"):
        ut.set_up()
        application = (
            ApplicationBuilder()
            .token(ut.settings("token"))
            .post_init(setup_commands)
            .post_shutdown(close_chats)
            .build()
        )
        setup_handlers(application)
        try:
            if ut.settings("webhook"):
                application.run_webhook(
                    listen=ut.settings("listen"),
                    port=ut.settings("port"),
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
