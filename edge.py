#!/usr/bin/env python3

# SPDX-License-Identifier: MIT

# Copyright (c) 2023 scmanjarrez. All rights reserved.
# This work is licensed under the terms of the MIT license.

from telegram.ext import (ApplicationBuilder, CommandHandler,
                          ContextTypes, filters, MessageHandler)
from telegram.error import TimedOut
from telegram import Update
from pathlib import Path

import utils as ut
import logging


async def unlock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cid = ut.cid(update)
    if (context.args
            and ut.passwd_correct(context.args[0])
            and cid not in ut.DATA['allowed']):
        ut.unlock(cid)
        await ut.send(update,
                      "Bot unlocked, enjoy the new ChatGPT experience.")


async def new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if ut.allowed(update):
        await ut.is_active_conversation(update, new=True)


async def message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if ut.allowed(update):
        status = await ut.is_active_conversation(update)
        if status:
            query = ut.Query(update, context)
            await query.run()


def setup_handlers(app: ApplicationBuilder) -> None:
    unlock_handler = CommandHandler('unlock', unlock)
    app.add_handler(unlock_handler)

    new_handler = CommandHandler('new', new)
    app.add_handler(new_handler)

    message_handler = MessageHandler(filters.TEXT, message)
    application.add_handler(message_handler)


async def edge_close(app: ApplicationBuilder) -> None:
    for chat in ut.CONV.values():
        await chat.close()


if __name__ == "__main__":
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    if Path(ut.FILE['cfg']).exists() and Path(ut.FILE['cookies']).exists():
        ut.set_up()
        application = (ApplicationBuilder()
                       .token(ut.settings('token'))
                       .post_shutdown(edge_close)
                       .build())
        setup_handlers(application)
        try:
            if ut.settings('webhook'):
                application.run_webhook(listen=ut.settings('listen'),
                                        port=ut.settings('port'),
                                        url_path=ut.settings('token'),
                                        cert=ut.settings('cert'),
                                        webhook_url=(
                                            f"https://"
                                            f"{ut.settings('ip')}/"
                                            f"{ut.settings('token')}"))
            else:
                application.run_polling()
        except TimedOut:
            logging.getLogger(
                'telegram.ext._application').error(
                    "Bot could not be initialized. Try again later.")
        except KeyError:
            logging.error(f"New setting 'webhook' required "
                          f"in {ut.FILE['cfg']}. Check README for more info.")
    else:
        logging.error(f"{ut.FILE['cfg']} or "
                      f"{ut.FILE['cookies']} file missing.")
