#!/usr/bin/env python3

# SPDX-License-Identifier: MIT

# Copyright (c) 2023 scmanjarrez. All rights reserved.
# This work is licensed under the terms of the MIT license.

import logging
from pathlib import Path
import argparse

import asr
import tts
import utils as ut
from telegram import Update
from telegram.error import TimedOut
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    filters,
    MessageHandler,
    CallbackQueryHandler,
)


async def unlock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cid = ut.cid(update)
    if (
        context.args
        and ut.passwd_correct(context.args[0])
        and cid not in ut.DATA["allowed"]
    ):
        ut.unlock(cid)
        await ut.send(
            update, "Bot unlocked, enjoy the new ChatGPT experience."
        )


async def new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if ut.allowed(update):
        await ut.is_active_conversation(update, new=True)


async def voice_setting(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if ut.allowed(update):
        if len(context.args) > 0:
            await tts.set_voice_name(update)
        else:
            await tts.show_voice_name(update)


async def voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if ut.allowed(update):
        status = await ut.is_active_conversation(update)
        if status:
            query = ut.Query(update, context)
            query.text = await asr.voice_to_text(update)
            query.include_question = True
            await query.run()


async def message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if ut.allowed(update):
        status = await ut.is_active_conversation(update)
        if status:
            query = ut.Query(update, context)
            await query.run()


async def set_voice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    await tts.set_voice(update)


def setup_handlers(app: ApplicationBuilder) -> None:
    unlock_handler = CommandHandler("unlock", unlock)
    app.add_handler(unlock_handler)

    new_handler = CommandHandler("new", new)
    app.add_handler(new_handler)

    voice_handler = CommandHandler("voice", voice_setting)
    app.add_handler(voice_handler)

    message_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, message)
    application.add_handler(message_handler)

    voice_message_handler = MessageHandler(
        filters.VOICE & ~filters.COMMAND & ~filters.TEXT, voice
    )
    application.add_handler(voice_message_handler)

    application.add_handler(
        CallbackQueryHandler(set_voice, pattern="^voice:[A-Za-z0-9_-]*")
    )


async def edge_close(app: ApplicationBuilder) -> None:
    for chat in ut.CONV.values():
        await chat.close()


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c", type=str, help="configuration file path", default="."
    )
    args = parser.parse_args()

    for key, value in ut.FILE.items():
        ut.FILE[key] = Path(args.c, value).absolute()

    if Path(ut.FILE["cfg"]).exists() and Path(ut.FILE["cookies"]).exists():
        ut.set_up()
        application = (
            ApplicationBuilder()
            .token(ut.settings("token"))
            .post_shutdown(edge_close)
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
                "New setting 'webhook' required "
                f"in {ut.FILE['cfg']}. Check README for more info."
            )
    else:
        logging.error(
            f"{ut.FILE['cfg']} or {ut.FILE['cookies']} file missing."
        )
