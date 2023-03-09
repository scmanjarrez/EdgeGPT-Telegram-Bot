import logging
import os
import tempfile

import edge_tts
import utils as ut
from telegram import Update


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
    await update.effective_message.reply_text(ut.settings("voice"))


async def set_voice_name(update: Update) -> None:
    voice = update.effective_message.text.split("voice ")[1]
    ut.DATA["cfg"]["settings"]["voice"] = voice
    ut.save_cfg()
    await show_voice_name(update)
