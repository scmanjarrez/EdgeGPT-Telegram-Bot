import logging
import os
import tempfile

import edge_tts
import utils as ut
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup


def get_keyboard() -> InlineKeyboardMarkup:
    voice_list = ut.settings("voice_list")
    keyboard = [
        [InlineKeyboardButton(voice, callback_data=f"voice:{voice}")]
        for voice in voice_list
    ]
    return InlineKeyboardMarkup(keyboard)


async def generate_voice(text, voice="zh-CN-YunjianNeural") -> str:
    voice_text = ut.REF.sub("", text)
    voice_text = ut.BOLD.sub("\\1\\2", voice_text)
    logging.info(voice_text)
    OUTPUT_FILE = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    communicate = edge_tts.Communicate(voice_text, voice)
    await communicate.save(OUTPUT_FILE.name)
    return OUTPUT_FILE.name


async def send_voice(update: Update, voice: str) -> None:
    with open(voice, "rb") as f:
        await update.effective_message.reply_voice(f)
        os.remove(voice)


async def show_voice_name(update: Update) -> None:
    await update.effective_message.reply_text(
        "Current voice: " + ut.settings("voice"), reply_markup=get_keyboard()
    )


async def set_voice(update: Update) -> None:
    query = update.callback_query
    voice = query.data.split("voice:")[1]
    await query.answer("Change voice")
    save_voice_name(voice)
    text = f"Current voice: {voice}"
    await query.edit_message_text(text=text, reply_markup=get_keyboard())


async def set_voice_name(update: Update) -> None:
    voice = update.effective_message.text.split("voice ")[1]
    save_voice_name(voice)
    await show_voice_name(update)


def save_voice_name(voice: str) -> None:
    ut.DATA["cfg"]["settings"]["voice"] = voice
    ut.save_cfg()
