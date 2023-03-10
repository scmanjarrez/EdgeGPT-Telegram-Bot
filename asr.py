import asyncio
import logging
import tempfile

import aiohttp
import utils as ut
from telegram import constants, Update


async def send_record_voiceing(update: Update) -> None:
    bot = update.get_bot()
    await bot.send_chat_action(
        update.effective_chat.id, constants.ChatAction.RECORD_VOICE
    )


async def assemblyai_voice_to_text(
    filename: str, headers: dict, update: Update
) -> str:
    logger = logging.getLogger("EdgeGPT-ASR")
    text = ""
    with open(filename, "rb") as f:
        data = f.read()

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(
                "https://api.assemblyai.com/v2/upload", data=data
            ) as resp:
                json_body = await resp.json()
                upload_url = json_body["upload_url"]
                json = {"audio_url": upload_url}
            async with session.post(
                "https://api.assemblyai.com/v2/transcript", json=json
            ) as resp:
                json_body = await resp.json()
                upload_id = json_body["id"]
                status = json_body["status"]
                if status == "queued":
                    waiting_times = 0
                    while waiting_times < 5:
                        async with session.get(
                            f"https://api.assemblyai.com/v2/transcript/{upload_id}"
                        ) as resp:
                            json_body = await resp.json()
                            status = json_body["status"]
                            logger.info(f"{upload_id}:{status}")
                            if status == "completed":
                                text = json_body["text"]
                                break
                            await send_record_voiceing(update)
                            await asyncio.sleep(5)
                            waiting_times += 1
    return text


async def voice_to_text(update: Update) -> str:
    voicefile = await update.message.voice.get_file()
    temp_voice = tempfile.NamedTemporaryFile(suffix=".ogg", delete=False)
    await send_record_voiceing(update)
    await voicefile.download_to_drive(temp_voice.name)

    token = ut.settings("assemblyai_token")
    headers = {"authorization": token, "content-type": "application/json"}

    await send_record_voiceing(update)
    text = await assemblyai_voice_to_text(temp_voice.name, headers, update)
    return text


if __name__ == "__main__":
    token = ut.settings("assemblyai_token")
    headers = {"authorization": token, "content-type": "application/json"}
    asyncio.run(assemblyai_voice_to_text("a.ogg", headers))
