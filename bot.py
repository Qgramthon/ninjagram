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

RESEND_COOLDOWN = 45
MAX_RETRIES = 4

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== KEEP ALIVE ====================
app = Flask(__name__)

@app.route('/')
def index():
    return "✅ Strong Telethon Bot | Running"

Thread(
    target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))),
    daemon=True
).start()

# ==================== GLOBALS ====================
bot = TelegramClient('bot_session', API_ID, API_HASH)
pending_users = {}
active_clients = {}
user_locks = {}

def get_lock(uid):
    uid = str(uid)
    if uid not in user_locks:
        user_locks[uid] = asyncio.Lock()
    return user_locks[uid]

# ==================== UTILS ====================
def normalize_phone(text: str) -> str:
    text = re.sub(r'\s+', '', text)
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
        logger.info(f"✅ User Source Started: {uid}")
    except Exception as e:
        logger.error(f"Failed to start {uid}: {e}")
        return

    # User Commands (مختصرة وقوية)
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بنغ$'))
    async def ping(event):
        start = datetime.now()
        msg = await event.edit("**✶ جاري الحساب...**")
        speed = (datetime.now() - start).microseconds / 1000
        await msg.edit(f"**✶ البنغ:** `{speed:.2f}ms`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.اوامر$'))
    async def commands(event):
        await event.edit("""
**╭━━━━━━━[ أوامر السورس ]━━━━━━━╮**
`.بنغ` — قياس السرعة
`.وقتي` — الوقت
`.عريض + نص`
`.مائل + نص`
`.مشطوب + نص`
`.زخرفة + نص`
`.نيم + اسم`
`.بايو + نص`
`.مسح + رقم`
`.حذف`
`.ايقاف`
**╰━━━━━━━━━━━━━━━━━━━━━━━━━━━╯**
        """)

    # باقي الأوامر يمكن إضافتها لاحقاً...

    try:
        await client.run_until_disconnected()
    except:
        pass
    finally:
        active_clients.pop(uid, None)

# ==================== BOT HANDLERS ====================
@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    uid = str(event.sender_id)
    if uid in active_clients:
        return await event.respond("**✅ السورس شغال!**")

    if load_session(uid):
        await event.respond("**⏳ جاري إعادة التشغيل...**")
        asyncio.create_task(launch_user_source(uid))
        return

    await event.respond(
        "**🚀 تنصيب سورس تيليثون قوي**\n\nاضغط على الزر أدناه:",
        buttons=[[Button.inline("🚀 بدء التنصيب", b"deploy")]]
    )

@bot.on(events.CallbackQuery(data=b"deploy"))
async def deploy_callback(event):
    uid = str(event.sender_id)
    pending_users[uid] = {"step": "api_id", "data": {}, "retries": 0, "client": None, "phone_code_hash": None}
    await event.edit("**📝 الخطوة 1/4: أرسل API_ID**")

@bot.on(events.NewMessage(func=lambda e: str(e.sender_id) in pending_users))
async def state_machine(event):
    uid = str(event.sender_id)
    lock = get_lock(uid)

    if lock.locked():
        return

    async with lock:
        if uid not in pending_users:
            return
        state = pending_users[uid]
        step = state["step"]
        text = event.text.strip()

        try:
            if step == "api_id":
                if not text.isdigit():
                    return await event.respond("❌ أرقام فقط!")
                state["data"]["api_id"] = int(text)
                state["step"] = "api_hash"
                await event.respond("✅ **الخطوة 2/4:** أرسل API_HASH")

            elif step == "api_hash":
                state["data"]["api_hash"] = text
                state["step"] = "phone"
                await event.respond("✅ **الخطوة 3/4:** أرسل رقم الهاتف\nمثال: `+201234567890`")

            elif step == "phone":
                phone = normalize_phone(text)
                state["data"]["phone"] = phone
                await send_login_code(event, uid, state)

            elif step == "code":
                if text.lower() in ["تجديد", "resend"]:
                    await send_login_code(event, uid, state, is_retry=True)
                else:
                    await verify_code(event, uid, state, normalize_phone(text))

            elif step == "password":
                await verify_2fa(event, uid, state, text)

        except Exception as e:
            logger.error(f"Error in state machine: {e}")
            await cleanup(uid)

# ==================== AUTH FUNCTIONS ====================
async def send_login_code(event, uid, state, is_retry=False):
    # ... (نفس الدالة السابقة مع تعديلات بسيطة)
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
        await event.respond("✅ **تم إرسال الكود**\nأرسله هنا:")
    except Exception as e:
        await event.respond(f"❌ {e}")
        state["step"] = "phone"

async def verify_code(event, uid, state, code):
    client = state.get("client")
    if not client: return
    try:
        await client.sign_in(state["data"]["phone"], code, phone_code_hash=state["phone_code_hash"])
        await finalize_login(event, uid, state)
    except SessionPasswordNeededError:
        state["step"] = "password"
        await event.respond("🔐 أرسل كلمة مرور التحقق بخطوتين:")
    except Exception as e:
        await event.respond(f"❌ {str(e)[:200]}")

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
    await event.respond("**🎉 تم التنصيب بنجاح!**\nالسورس يعمل الآن.")
    await cleanup(uid)
    asyncio.create_task(launch_user_source(uid))

async def cleanup(uid):
    pending_users.pop(str(uid), None)

# ==================== START ====================
async def main():
    await bot.start(bot_token=BOT_TOKEN)
    for file in SESSIONS_DIR.glob("*.txt"):
        asyncio.create_task(launch_user_source(file.stem))
    logger.info("🚀 Bot Started Successfully")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
