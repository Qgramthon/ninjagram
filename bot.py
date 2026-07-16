import os
import re
import time
import asyncio
import logging
from datetime import datetime
from pathlib import Path

from telethon import TelegramClient, events, Button
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError, PhoneCodeExpiredError,
    PhoneCodeInvalidError, FloodWaitError, PhoneNumberInvalidError
)

from flask import Flask
from threading import Thread

# ==================== CONFIG ====================
BOT_TOKEN = "8963454170:AAGlM4mHDAjtXMcTYQd9_RRMy0I6JgnMBwg"
API_ID = 6
API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"

SESSIONS_DIR = Path("sessions")
SESSIONS_DIR.mkdir(exist_ok=True)

RESEND_COOLDOWN = 70
MAX_RETRIES = 5

# ==================== LOGGING ====================
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

# ==================== KEEP ALIVE ====================
app = Flask(__name__)
@app.route('/')
def index():
    return "✅ Strong Telethon Bot Running"

Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))), daemon=True).start()

# ==================== GLOBALS ====================
bot = TelegramClient('bot_session', API_ID, API_HASH)

pending_users = {}      # uid -> state (يحتوي على الـ client الحي)
active_clients = {}
user_locks = {}

def get_lock(uid):
    uid = str(uid)
    if uid not in user_locks:
        user_locks[uid] = asyncio.Lock()
    return user_locks[uid]

# ==================== UTILS ====================
def normalize_phone(text: str) -> str:
    text = re.sub(r'\s+', '', text.strip())
    text = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789"))
    if not text.startswith('+'):
        text = '+' + text.lstrip('+')
    return text

def save_session(uid: str, session_str: str):
    with open(SESSIONS_DIR / f"{uid}.txt", "w", encoding="utf-8") as f:
        f.write(session_str)

def load_session(uid: str):
    path = SESSIONS_DIR / f"{uid}.txt"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return None

# ==================== LAUNCH USER SOURCE ====================
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
        logger.info(f"✅ User Source {uid} Started")
    except Exception as e:
        logger.error(f"Failed to start {uid}: {e}")

    # Commands
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بنغ$'))
    async def ping(event):
        start = datetime.now()
        msg = await event.edit("**✶ جاري حساب البنغ...**")
        speed = (datetime.now() - start).microseconds / 1000
        await msg.edit(f"**✶ البنغ:** `{speed:.2f}ms`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.اوامر$'))
    async def commands(event):
        await event.edit("**✅ السورس شغال**\n`.بنغ` `.ايقاف` `.اوامر`")

# ==================== BOT HANDLERS ====================
@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    uid = str(event.sender_id)
    if load_session(uid):
        await event.respond("**✅ السورس شغال بالفعل**")
        asyncio.create_task(launch_user_source(uid))
        return

    await event.respond(
        "**🚀 تنصيب سورس تيليثون قوي**\n\nاضغط لبدء التنصيب:",
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
        "last_code_time": 0,
        "retries": 0
    }
    await event.edit("**📝 الخطوة 1/4: أرسل API_ID**")

# ==================== STATE MACHINE ====================
@bot.on(events.NewMessage(func=lambda e: str(e.sender_id) in pending_users))
async def state_machine(event):
    uid = str(event.sender_id)
    async with get_lock(uid):
        if uid not in pending_users:
            return
        state = pending_users[uid]
        text = event.text.strip()

        try:
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
                await send_login_code(event, uid, state)

            elif state["step"] == "code":
                if text.lower() in ["تجديد", "resend", "ارسال"]:
                    await send_login_code(event, uid, state, is_retry=True)
                else:
                    await verify_login_code(event, uid, state, normalize_phone(text))

            elif state["step"] == "password":
                await verify_2fa(event, uid, state, text)

        except Exception as e:
            logger.error(f"State error {uid}: {e}")
            await event.respond("❌ خطأ غير متوقع، جرب /start")

# ==================== CORE FUNCTIONS ====================
async def send_login_code(event, uid, state, is_retry=False):
    client = state.get("client")
    if client:
        try: await client.disconnect()
        except: pass

    if is_retry and time.time() - state.get("last_code_time", 0) < RESEND_COOLDOWN:
        return await event.respond(f"⏳ انتظر {RESEND_COOLDOWN} ثانية قبل طلب كود جديد")

    api_id = state["data"]["api_id"]
    api_hash = state["data"]["api_hash"]
    phone = state["data"]["phone"]

    client = TelegramClient(StringSession(), api_id, api_hash)
    state["client"] = client

    try:
        await client.connect()
        result = await client.send_code_request(phone, force_sms=is_retry)
        state["phone_code_hash"] = result.phone_code_hash
        state["step"] = "code"
        state["last_code_time"] = time.time()

        await event.respond(
            "✅ **تم إرسال رمز التحقق**\n"
            "أرسل الرمز هنا بدون مسافات\n"
            "اكتب `تجديد` إذا لم يصل"
        )
    except Exception as e:
        await event.respond(f"❌ {e}")
        state["step"] = "phone"

async def verify_login_code(event, uid, state, code):
    client = state.get("client")
    if not client:
        return await event.respond("❌ انتهت الجلسة، ابدأ من جديد")

    try:
        await client.sign_in(
            state["data"]["phone"],
            code,
            phone_code_hash=state["phone_code_hash"]
        )
        await finalize_login(event, uid, state)
    except PhoneCodeExpiredError:
        await event.respond("❌ **الكود انتهى صلاحيته**\nاكتب `تجديد` لطلب كود جديد")
    except PhoneCodeInvalidError:
        await event.respond("❌ رمز خاطئ. حاول مرة أخرى أو اكتب `تجديد`")
    except SessionPasswordNeededError:
        state["step"] = "password"
        await event.respond("🔐 أرسل كلمة مرور التحقق بخطوتين:")
    except Exception as e:
        await event.respond(f"❌ {e}")

async def verify_2fa(event, uid, state, password):
    try:
        await state["client"].sign_in(password=password)
        await finalize_login(event, uid, state)
    except Exception as e:
        await event.respond(f"❌ كلمة مرور خاطئة: {e}")

async def finalize_login(event, uid, state):
    session_str = state["client"].session.save()
    save_session(uid, session_str)
    await state["client"].disconnect()
    pending_users.pop(uid, None)
    await event.respond("**🎉 تم التنصيب بنجاح!**\nالسورس يعمل الآن.")
    asyncio.create_task(launch_user_source(uid))

# ==================== MAIN ====================
async def main():
    await bot.start(bot_token=BOT_TOKEN)
    # Restore previous sessions
    for file in SESSIONS_DIR.glob("*.txt"):
        asyncio.create_task(launch_user_source(file.stem))
    logger.info("🚀 Bot Started Successfully")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
