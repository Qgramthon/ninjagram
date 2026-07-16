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
    PhoneCodeInvalidError, FloodWaitError, PhoneNumberInvalidError,
    AuthKeyUnregisteredError, UserDeactivatedBanError
)

from flask import Flask
from threading import Thread
import aiofiles

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
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ==================== KEEP ALIVE ====================
app = Flask(__name__)

@app.route('/')
def index():
    return "✅ Bot is Alive | Strong Telethon Installer"

Thread(
    target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))),
    daemon=True
).start()

# ==================== CLIENTS ====================
bot = TelegramClient('bot_session', API_ID, API_HASH)
pending_users = {}      # uid -> state
active_clients = {}     # uid -> client
user_locks = {}         # uid -> asyncio.Lock()

def get_lock(uid: str):
    uid = str(uid)
    if uid not in user_locks:
        user_locks[uid] = asyncio.Lock()
    return user_locks[uid]

# ==================== UTILS ====================
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

def normalize_phone(text: str) -> str:
    text = text.translate(ARABIC_DIGITS).strip()
    if not text.startswith('+'):
        text = '+' + text.lstrip('+')
    return re.sub(r'\s+', '', text)

async def save_session(uid: str, session_str: str):
    async with aiofiles.open(SESSIONS_DIR / f"{uid}.txt", "w") as f:
        await f.write(session_str)

async def load_session(uid: str):
    path = SESSIONS_DIR / f"{uid}.txt"
    if not path.exists():
        return None
    async with aiofiles.open(path, "r") as f:
        return await f.read().strip()

# ==================== LAUNCH USER SOURCE ====================
async def launch_user_source(uid: str):
    uid = str(uid)
    if uid in active_clients:
        return

    session_str = await load_session(uid)
    if not session_str:
        return

    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)

    try:
        await client.start()
        active_clients[uid] = client
        logger.info(f"✅ User Source Started: {uid}")
    except Exception as e:
        logger.error(f"❌ Failed to start user {uid}: {e}")
        return

    # ==================== USER COMMANDS ====================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بنغ$'))
    async def ping(event):
        start = datetime.now()
        msg = await event.edit("**✶ جاري حساب البنغ...**")
        speed = (datetime.now() - start).microseconds / 1000
        await msg.edit(f"**✶ البنغ:** `{speed:.2f}ms`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.وقتي$'))
    async def time_now(event):
        now = datetime.now().strftime("%I:%M:%S %p | %Y/%m/%d")
        await event.edit(f"**⏰ الوقت:** `{now}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.عريض (.+)'))
    async def bold(event):
        await event.edit(f"**{event.pattern_match.group(1)}**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.مائل (.+)'))
    async def italic(event):
        await event.edit(f"__{event.pattern_match.group(1)}__")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.مشطوب (.+)'))
    async def strike(event):
        await event.edit(f"~~{event.pattern_match.group(1)}~~")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.قلب (.+)'))
    async def flip(event):
        await event.edit(f"`{event.pattern_match.group(1)[::-1]}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.زخرفة (.+)'))
    async def zkhrafa(event):
        text = event.pattern_match.group(1).lower()
        fancy = {'a':'α','b':'в','c':'¢','d':'∂','e':'є','f':'ƒ','g':'ﻐ','h':'н','i':'ι',
                 'j':'נ','k':'к','l':'ℓ','m':'м','n':'η','o':'σ','p':'ρ','q':'q','r':'я',
                 's':'ѕ','t':'т','u':'υ','v':'ν','w':'ω','x':'χ','y':'у','z':'z'}
        result = ''.join(fancy.get(c, c) for c in text)
        await event.edit(f"**✨ {result}**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.نيم (.+)'))
    async def set_name(event):
        try:
            await client(UpdateProfileRequest(first_name=event.pattern_match.group(1)))
            await event.edit("**✅ تم تغيير الاسم بنجاح**")
        except Exception as e:
            await event.edit(f"**❌ خطأ:** {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بايو (.+)'))
    async def set_bio(event):
        try:
            await client(UpdateProfileRequest(about=event.pattern_match.group(1)))
            await event.edit("**✅ تم تغيير البايو**")
        except Exception as e:
            await event.edit(f"**❌ خطأ:** {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.مسح (\d+)'))
    async def delete_msgs(event):
        try:
            count = int(event.pattern_match.group(1))
            chat = await event.get_input_chat()
            msgs = [m.id async for m in client.iter_messages(chat, limit=count+1)]
            await client.delete_messages(chat, msgs)
            await event.delete()
        except Exception as e:
            await event.edit(f"❌ {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.حذف$'))
    async def delete_chat(event):
        try:
            chat = await event.get_input_chat()
            await client.delete_dialog(chat)
            await event.respond("**✅ تم حذف المحادثة**")
        except Exception:
            pass

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ايقاف$'))
    async def stop_source(event):
        await event.edit("**👋 جاري إيقاف السورس...**")
        try:
            await client.disconnect()
        except:
            pass
        active_clients.pop(uid, None)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.اوامر$'))
    async def commands(event):
        await event.edit("""
**╭━━━━━━━[ أوامر السورس ]━━━━━━━╮**
`.بنغ` — قياس السرعة
`.وقتي` — الوقت الحالي
`.عريض + نص` — نص عريض
`.مائل + نص` — نص مائل
`.مشطوب + نص` — نص مشطوب
`.قلب + نص` — قلب النص
`.زخرفة + نص` — زخرفة إنجليزية
`.نيم + اسم` — تغيير الاسم
`.بايو + نص` — تغيير البايو
`.مسح + رقم` — مسح رسائل
`.حذف` — حذف المحادثة
`.ايقاف` — إيقاف السورس
**╰━━━━━━━━━━━━━━━━━━━━━━━━━━━╯**
        """)

    try:
        await client.run_until_disconnected()
    except Exception as e:
        logger.warning(f"User client {uid} disconnected: {e}")
    finally:
        active_clients.pop(uid, None)
