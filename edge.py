#!/usr/bin/env python3

# SPDX-License-Identifier: MIT

# Copyright (c) 2023 scmanjarrez. All rights reserved.
# This work is licensed under the terms of the MIT license.

from telegram.ext import (ApplicationBuilder, CommandHandler,
                          ContextTypes, filters, MessageHandler)
from telegram.error import TimedOut
from telegram import Update

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
        await ut.new_conversation(update, force=True)


async def message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if ut.allowed(update):
        await ut.new_conversation(update)

        if (not ut.is_group(update)
                or (ut.is_group(update) and ut.is_reply(update))):
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
    for chat, _ in ut.CONV.values():
        await chat.close()


if __name__ == "__main__":
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    ut.set_up()
    application = (ApplicationBuilder()
                   .token(ut.settings('token'))
                   .post_shutdown(edge_close)
                   .build())
    setup_handlers(application)
    try:
        application.run_polling()
    except TimedOut:
        logging.error("Bot could not be initialized. Try again later.")
