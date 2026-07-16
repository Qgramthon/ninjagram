import os
import re
import time
import asyncio
import logging
from datetime import datetime
from pathlib import Path

from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import (
    FloodWaitError, PhoneCodeExpiredError, PhoneCodeInvalidError,
    SessionPasswordNeededError, PhoneNumberInvalidError
)

from flask import Flask
from threading import Thread

# ====================== CONFIG ======================
BOT_TOKEN = "8963454170:AAGlM4mHDAjtXMcTYQd9_RRMy0I6JgnMBwg"
API_ID = 6
API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"

SESSIONS_DIR = Path("sessions")
SESSIONS_DIR.mkdir(exist_ok=True)

# ====================== LOGGING ======================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

# ====================== FLASK KEEP-ALIVE ======================
app = Flask(__name__)
@app.route('/')
def index():
    return "✅ Strongest Telethon Installer | Running"

Thread(
    target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))),
    daemon=True
).start()

# ====================== GLOBALS ======================
bot = TelegramClient('bot_session', API_ID, API_HASH)
pending_users = {}   # uid -> state (client remains alive)
active_clients = {}

def get_lock(uid):
    if uid not in pending_users:
        pending_users[uid] = {"lock": asyncio.Lock()}
    return pending_users[uid]["lock"]

# ====================== UTILS ======================
def normalize_phone(text: str) -> str:
    text = re.sub(r'\s+', '', text.strip())
    text = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789"))
    if not text.startswith('+'):
        text = '+' + text.lstrip('+')
    return text

def save_session(uid: str, session_str: str):
    try:
        with open(SESSIONS_DIR / f"{uid}.txt", "w", encoding="utf-8") as f:
            f.write(session_str)
    except Exception as e:
        logger.error(f"Save session failed: {e}")

def load_session(uid: str):
    try:
        path = SESSIONS_DIR / f"{uid}.txt"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
    except:
        pass
    return None

# ====================== SAFE BOT START ======================
async def safe_bot_start():
    for attempt in range(8):
        try:
            await bot.start(bot_token=BOT_TOKEN)
            logger.info("✅ Bot Authorized Successfully")
            return True
        except FloodWaitError as e:
            wait = e.seconds + 10
            logger.warning(f"FloodWait → Waiting {wait}s (Attempt {attempt+1})")
            await asyncio.sleep(wait)
        except Exception as e:
            logger.error(f"Start error: {e}")
            await asyncio.sleep(15)
    logger.critical("Failed to start bot after multiple attempts")
    return False

# ====================== USER SOURCE ======================
async def launch_user_source(uid: str):
    uid = str(uid)
    if uid in active_clients:
        return
    session_str = load_session(uid)
    if not session_str:
        return

    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
    try:
        await client.start()
        active_clients[uid] = client
        logger.info(f"✅ User Source Started: {uid}")
    except Exception as e:
        logger.error(f"User {uid} start failed: {e}")

# ====================== HANDLERS ======================
@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    uid = str(event.sender_id)
    if load_session(uid):
        await event.respond("**✅ السورس شغال بالفعل**")
        asyncio.create_task(launch_user_source(uid))
        return

    await event.respond(
        "**ꪀɪꪀȷᥲƚһ᥆ꪀ — أقوى تنصيب تيليثون**\n\nاضغط لبدء:",
        buttons=[[Button.inline("🚀 بدء التنصيب", b"deploy")]]
    )

@bot.on(events.CallbackQuery(data=b"deploy"))
async def deploy_callback(event):
    uid = str(event.sender_id)
    pending_users[uid] = {
        "step": "api_id",
        "data": {},
        "client": None,
        "phone_code_hash": None,
        "last_code_time": 0
    }
    await event.edit("**📝 الخطوة 1/4: أرسل API_ID**")

@bot.on(events.NewMessage(func=lambda e: str(e.sender_id) in pending_users))
async def state_machine(event):
    uid = str(event.sender_id)
    async with get_lock(uid):
        state = pending_users.get(uid)
        if not state:
            return
        text = event.text.strip()

        if state["step"] == "api_id":
            if not text.isdigit():
                return await event.respond("❌ أرقام فقط!")
            state["data"]["api_id"] = int(text)
            state["step"] = "api_hash"
            await event.respond("**✅ أرسل API_HASH:**")

        elif state["step"] == "api_hash":
            state["data"]["api_hash"] = text
            state["step"] = "phone"
            await event.respond("**✅ أرسل رقم الهاتف**\nمثال: `+201234567890`")

        elif state["step"] == "phone":
            state["data"]["phone"] = normalize_phone(text)
            await send_code(event, uid, state)

        elif state["step"] == "code":
            if text.lower() in ["تجديد", "resend", "ارسال"]:
                await send_code(event, uid, state, is_retry=True)
            else:
                await verify_code(event, uid, state, normalize_phone(text))

        elif state["step"] == "password":
            await verify_2fa(event, uid, state, text)

# ====================== AUTH FUNCTIONS ======================
async def send_code(event, uid, state, is_retry=False):
    if state.get("client"):
        try: await state["client"].disconnect()
        except: pass

    client = TelegramClient(StringSession(), state["data"]["api_id"], state["data"]["api_hash"])
    state["client"] = client

    try:
        await client.connect()
        result = await client.send_code_request(state["data"]["phone"], force_sms=is_retry)
        state["phone_code_hash"] = result.phone_code_hash
        state["step"] = "code"
        state["last_code_time"] = time.time()

        await event.respond(
            "✅ **تم إرسال رمز التحقق**\n"
            "أرسل الرمز بدون مسافات\n"
            "اكتب `تجديد` إذا لم يصل"
        )
    except FloodWaitError as e:
        await event.respond(f"⏳ انتظر {e.seconds} ثانية")
    except Exception as e:
        await event.respond(f"❌ {e}")
        state["step"] = "phone"

async def verify_code(event, uid, state, code):
    client = state.get("client")
    if not client:
        return await event.respond("❌ ابدأ من جديد بـ /start")

    try:
        await client.sign_in(state["data"]["phone"], code, phone_code_hash=state["phone_code_hash"])
        await finalize(event, uid, state)
    except PhoneCodeExpiredError:
        await event.respond("❌ الكود انتهى. اكتب `تجديد`")
    except PhoneCodeInvalidError:
        await event.respond("❌ رمز خاطئ. حاول أو `تجديد`")
    except SessionPasswordNeededError:
        state["step"] = "password"
        await event.respond("🔐 أرسل كلمة مرور الـ 2FA:")
    except Exception as e:
        await event.respond(f"❌ {e}")

async def verify_2fa(event, uid, state, password):
    try:
        await state["client"].sign_in(password=password)
        await finalize(event, uid, state)
    except Exception as e:
        await event.respond(f"❌ كلمة مرور خاطئة: {e}")

async def finalize(event, uid, state):
    try:
        session_str = state["client"].session.save()
        save_session(uid, session_str)
        await state["client"].disconnect()
        pending_users.pop(uid, None)
        await event.respond("**🎉 تم التنصيب بنجاح!**\nالسورس يعمل الآن.")
        asyncio.create_task(launch_user_source(uid))
    except Exception as e:
        logger.error(f"Finalize error: {e}")

# ====================== MAIN ======================
async def main():
    if await safe_bot_start():
        # Restore previous users
        for file in SESSIONS_DIR.glob("*.txt"):
            asyncio.create_task(launch_user_source(file.stem))
        await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
