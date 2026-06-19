import asyncio
import threading
from functools import wraps
from typing import Dict, Tuple
from concurrent.futures import ThreadPoolExecutor
import logging
import time
import random
import json
import os
import sys
import requests
import io
import uuid
from collections import Counter
from datetime import datetime, timedelta

from flask import Flask, jsonify, request
from telethon import TelegramClient, events, Button
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.sessions import StringSession
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.contacts import BlockRequest, UnblockRequest, ImportContactsRequest
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.messages import ToggleDialogPinRequest, GetHistoryRequest, GetDialogsRequest, EditChatDefaultBannedRightsRequest
from telethon.tl.functions.phone import RequestCallRequest
from telethon.tl.types import InputPeerChannel, InputPeerUser, InputPhoneContact, ChatBannedRights, PhoneCallProtocol
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest, GetUserPhotosRequest
from telethon.tl.functions.users import GetFullUserRequest

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ======================== إعدادات ========================
BOT_TOKEN = '8887748662:AAFgLMUO2eXpYzityDj35-IDTLywtdO8S8Q'
BOT_API_ID = 2040
BOT_API_HASH = 'b18441a1ff607e10a989891a5462e627'

DATA_DIR = '/data' if os.path.exists('/data') else '.'
os.makedirs(DATA_DIR, exist_ok=True)
SESSION_FILE = os.path.join(DATA_DIR, 'active_sessions.json')
API_CONFIG_FILE = os.path.join(DATA_DIR, 'api_config.json')
BANK_FILE = os.path.join(DATA_DIR, 'bank.json')
TEMP_DIR = os.path.join(DATA_DIR, 'temp')
os.makedirs(TEMP_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

# ======================== Flask للـ health check ========================
app = Flask(__name__)

SOURCE_CHANNEL = "https://t.me/Q_g_r_a_m"
SOURCE_CHANNEL_USERNAME = "Q_g_r_a_m"
GEMINI_API_KEY = "AQ.Ab8RN6IJ52RfamXKX6nNJOglTwDarnQyUIh9uzITyqK5iqwm7w"
DEV_PHONE = "+201096371454"

# ======================== Main Loop (نفس الموقع بالضبط) ========================
main_loop = asyncio.new_event_loop()

active_clients: Dict[str, TelegramClient] = {}
pending_logins: Dict[str, Tuple[TelegramClient, str, int, str]] = {}
api_configs_storage: Dict[str, Dict] = {}

# ======================== دوال الموقع (نفسها بالضبط) ========================
def run_async_in_main_loop(coro):
    future = asyncio.run_coroutine_threadsafe(coro, main_loop)
    return future.result(timeout=300)

def async_route(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return run_async_in_main_loop(f(*args, **kwargs))
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    return wrapper

# ======================== دوال مساعدة ========================
async def save_all_sessions():
    try:
        sessions_data, configs = {}, {}
        for phone, client in active_clients.items():
            try:
                if client.is_connected():
                    sessions_data[phone] = client.session.save()
                    if phone in api_configs_storage:
                        configs[phone] = api_configs_storage[phone]
            except:
                continue
        with open(SESSION_FILE, 'w') as f:
            json.dump(sessions_data, f)
        with open(API_CONFIG_FILE, 'w') as f:
            json.dump(configs, f)
    except:
        pass

async def load_all_sessions():
    try:
        if not os.path.exists(SESSION_FILE):
            return
        with open(SESSION_FILE, 'r') as f:
            sessions = json.load(f)
        with open(API_CONFIG_FILE, 'r') as f:
            configs = json.load(f)
        for phone, session_str in sessions.items():
            try:
                if phone in configs:
                    api_id = configs[phone]['api_id']
                    api_hash = configs[phone]['api_hash']
                    client = TelegramClient(StringSession(session_str), api_id, api_hash)
                    await client.connect()
                    if await client.is_user_authorized():
                        active_clients[phone] = client
                        api_configs_storage[phone] = configs[phone]
                        asyncio.ensure_future(run_userbot(client, phone), loop=main_loop)
                        logger.info(f"Restored: {phone}")
            except:
                pass
    except:
        pass

def start_client_in_background(client, phone):
    async def run_client():
        try:
            if not client.is_connected():
                await client.connect()
            if not await client.is_user_authorized():
                return
            await run_userbot(client, phone)
            await client.run_until_disconnected()
        except Exception as e:
            logger.error(f"Error {phone}: {e}")
    asyncio.run_coroutine_threadsafe(run_client(), main_loop)

async def run_userbot(client, phone):
    # هنا بتحط كل أوامر الـ userbot (تقليد، انتحال، بنك، إلخ)
    # للاختبار هنحط أمر بسيط
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بنغ$'))
    async def ping(event):
        await event.edit("**Pong!**")
    
    logger.info(f"UserBot started: {phone}")

# ======================== بوت التنصيب (باستخدام main_loop) ========================
bot = TelegramClient(f'bot_session_{uuid.uuid4().hex[:6]}', BOT_API_ID, BOT_API_HASH)

# تخزين مؤقت لبيانات المستخدمين أثناء التنصيب عبر البوت
bot_pending = {}  # {user_id: {'state': ..., 'api_id': ..., 'api_hash': ..., 'phone': ..., 'client': ..., 'hash': ...}}

@bot.on(events.NewMessage(pattern='/ping'))
async def bot_ping(event):
    await event.respond('Pong!')

@bot.on(events.NewMessage(pattern='/start'))
async def bot_start(event):
    buttons = [
        [Button.inline("START SETUP", b"start_setup")]
    ]
    await event.respond(
        "**Rolex Telethon Setup Bot**\n\n"
        "Press the button to start setting up your account.",
        buttons=buttons,
        parse_mode='md'
    )

@bot.on(events.CallbackQuery(data=b"start_setup"))
async def start_setup(event):
    bot_pending[event.sender_id] = {'state': 'api_id'}
    await event.edit(
        "**Send your API ID**\n\n"
        "Enter your API ID from my.telegram.org:",
        parse_mode='md'
    )
    await event.answer()

@bot.on(events.NewMessage())
async def handle_bot_setup(event):
    uid = event.sender_id
    if uid not in bot_pending:
        return
    
    state = bot_pending[uid].get('state')
    data = bot_pending[uid]
    
    if state == 'api_id':
        try:
            api_id = int(event.text.strip())
            data['api_id'] = api_id
            data['state'] = 'api_hash'
            await event.respond(
                "**Send your API Hash**\n\n"
                "Enter your API Hash from my.telegram.org:",
                parse_mode='md'
            )
        except:
            await event.respond("**Invalid API ID. Must be a number.**")
    
    elif state == 'api_hash':
        data['api_hash'] = event.text.strip()
        data['state'] = 'phone'
        buttons = [[Button.request_phone("Share Phone Number", resize=True)]]
        await event.respond(
            "**Send your Phone Number**\n\n"
            "Press the button or type manually: +201234567890",
            buttons=buttons,
            parse_mode='md'
        )
    
    elif state == 'phone':
        if event.message.contact:
            phone = f"+{event.message.contact.phone_number}"
        else:
            phone = event.text.strip()
        
        data['phone'] = phone
        
        # استخدام نفس طريقة الموقع: run_async_in_main_loop
        async def send_code_request():
            api_id = data['api_id']
            api_hash = data['api_hash']
            
            api_configs_storage[phone] = {'api_id': api_id, 'api_hash': api_hash}
            client = TelegramClient(StringSession(), api_id, api_hash)
            await client.connect()
            
            if await client.is_user_authorized():
                active_clients[phone] = client
                start_client_in_background(client, phone)
                await save_all_sessions()
                return 'already_active', client, None
            
            sent = await client.send_code_request(phone)
            return 'code_sent', client, sent.phone_code_hash
        
        try:
            status, client, phone_code_hash = run_async_in_main_loop(send_code_request())
            
            if status == 'already_active':
                await event.respond("**Account already active!**")
                del bot_pending[uid]
                return
            
            data['client'] = client
            data['hash'] = phone_code_hash
            data['state'] = 'code'
            
            await event.respond(
                "**Code sent!**\n\n"
                "Check your Telegram app and enter the code:",
                parse_mode='md'
            )
            
        except Exception as e:
            logger.error(f"Send code error: {e}")
            await event.respond(f"**Error: {str(e)[:100]}**")
            del bot_pending[uid]
    
    elif state == 'code':
        code = event.text.strip()
        data = bot_pending[uid]
        
        async def sign_in():
            client = data['client']
            phone = data['phone']
            phone_code_hash = data['hash']
            
            try:
                await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                return '2fa_needed', None
            
            active_clients[phone] = client
            del bot_pending[uid]
            await save_all_sessions()
            start_client_in_background(client, phone)
            return 'success', None
        
        try:
            status, _ = run_async_in_main_loop(sign_in())
            
            if status == '2fa_needed':
                data['state'] = 'password'
                await event.respond(
                    "**2FA Password Required**\n\n"
                    "Enter your 2FA password:",
                    parse_mode='md'
                )
                return
            
            await event.respond(
                "**Setup Complete!**\n\n"
                "Your account is now active.\n"
                "Send `.بنغ` from your account to test.",
                parse_mode='md'
            )
            
        except Exception as e:
            logger.error(f"Sign in error: {e}")
            await event.respond(f"**Error: {str(e)[:100]}**")
            del bot_pending[uid]
    
    elif state == 'password':
        password = event.text.strip()
        data = bot_pending[uid]
        
        async def sign_in_with_password():
            client = data['client']
            phone = data['phone']
            await client.sign_in(password=password)
            active_clients[phone] = client
            del bot_pending[uid]
            await save_all_sessions()
            start_client_in_background(client, phone)
            return 'success'
        
        try:
            run_async_in_main_loop(sign_in_with_password())
            
            await event.respond(
                "**Setup Complete!**\n\n"
                "Your account is now active.\n"
                "Send `.بنغ` from your account to test.",
                parse_mode='md'
            )
            
        except Exception as e:
            logger.error(f"Password error: {e}")
            await event.respond(f"**Error: {str(e)[:100]}**")
            del bot_pending[uid]

# ======================== Flask Routes (للـ health check) ========================
@app.route('/')
def home():
    return "OK"

@app.route('/health')
def health():
    return "OK", 200

# ======================== بدء التشغيل ========================
def start_main_loop():
    asyncio.set_event_loop(main_loop)
    main_loop.run_until_complete(load_all_sessions())
    main_loop.run_forever()

threading.Thread(target=start_main_loop, daemon=True).start()

async def main():
    flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False), daemon=True)
    flask_thread.start()
    logger.info("Flask started")
    
    await bot.start(bot_token=BOT_TOKEN)
    logger.info("Bot started")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    # تشغيل البوت في الـ main_loop
    asyncio.run_coroutine_threadsafe(main(), main_loop)
    # انتظار
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
