import os
import asyncio
import logging
from flask import Flask
from threading import Thread
from telethon import TelegramClient, events, Button
from telethon.errors import FloodWaitError

# ====================== CONFIG ======================
BOT_TOKEN = "8879863328:AAH_PB_1i50hIyU-UI58TcD-dflHl4dBFqo"
API_ID = 6
API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"

# ====================== LOGGING ======================
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

# ====================== KEEP ALIVE ======================
app = Flask(__name__)
@app.route('/')
def index():
    return "✅ Bot is Running"

Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))), daemon=True).start()

# ====================== CLIENT ======================
bot = TelegramClient('bot_session', API_ID, API_HASH)

async def safe_start():
    for i in range(5):
        try:
            await bot.start(bot_token=BOT_TOKEN)
            logger.info("✅ Bot Started Successfully!")
            return True
        except FloodWaitError as e:
            wait = e.seconds + 10
            logger.warning(f"FloodWait: Waiting {wait} seconds...")
            await asyncio.sleep(wait)
        except Exception as e:
            logger.error(f"Start attempt {i+1} failed: {e}")
            await asyncio.sleep(8)
    return False

# ====================== HANDLERS ======================
@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await event.respond(
        "**✅ البوت شغال دلوقتي**\n\n"
        "اضغط على الزر لبدء تنصيب السورس:",
        buttons=[[Button.inline("🚀 بدء التنصيب", b"deploy")]]
    )

@bot.on(events.CallbackQuery(data=b"deploy"))
async def deploy(event):
    await event.edit("**🛠️ جاري تجهيز التنصيب...\n\nأرسل API_ID**")
    # هنا هتبدأ الـ state machine في النسخة الكاملة

@bot.on(events.NewMessage(pattern='/ping'))
async def ping(event):
    await event.respond("**✅ البوت رد عليك!**")

# ====================== MAIN ======================
async def main():
    success = await safe_start()
    if success:
        logger.info("Bot is ready to receive messages")
        await bot.run_until_disconnected()
    else:
        logger.error("Could not start bot")

if __name__ == "__main__":
    asyncio.run(main())
