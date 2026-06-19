import asyncio
import threading
import logging
import time
import random
import json
import os
import sys
import uuid
from datetime import datetime

from flask import Flask
from telethon import TelegramClient, events, Button
from telethon.errors import (
    SessionPasswordNeededError, FloodWaitError, PhoneCodeInvalidError,
    PhoneCodeExpiredError, PhoneNumberInvalidError
)
from telethon.sessions import StringSession

# ======================== الإعدادات الأساسية ========================
BOT_TOKEN = '8887748662:AAFgLMUO2eXpYzityDj35-IDTLywtdO8S8Q'
BOT_API_ID = 2040
BOT_API_HASH = 'b18441a1ff607e10a989891a5462e627'

DATA_DIR = '/data' if os.path.exists('/data') else '.'
os.makedirs(DATA_DIR, exist_ok=True)
SESSION_FILE = os.path.join(DATA_DIR, 'active_sessions.json')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ======================== Flask للـ health check ========================
app = Flask(__name__)

@app.route('/')
def health():
    return "OK", 200

def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

# ======================== Main Loop (زي الموقع القديم) ========================
main_loop = asyncio.new_event_loop()

def run_in_main_loop(coro):
    """تشغيل coroutine في main_loop (نفس طريقة الموقع بالضبط)"""
    return asyncio.run_coroutine_threadsafe(coro, main_loop).result(timeout=180)

# ======================== المتغيرات العامة ========================
bot = TelegramClient(f'bot_session_{uuid.uuid4().hex[:6]}', BOT_API_ID, BOT_API_HASH)

active_clients = {}
pending_logins = {}

# ======================== بوت التنصيب ========================
@bot.on(events.NewMessage(pattern='/ping'))
async def bot_ping(event):
    await event.respond('Pong!')

@bot.on(events.NewMessage(pattern='/start'))
async def bot_start(event):
    buttons = [
        [Button.inline("START", b"start_setup")],
        [Button.inline("RESTART", b"restart_setup")]
    ]
    await event.respond(
        "**Rolex Telethon Setup**\n\n"
        "Press START to begin",
        buttons=buttons,
        parse_mode='md'
    )

@bot.on(events.CallbackQuery(data=b"start_setup"))
async def start_setup(event):
    pending_logins[event.sender_id] = {'state': 'api_id'}
    await event.edit(
        "**Send Your API ID**\n\n"
        "Please enter your API ID:",
        parse_mode='md'
    )
    await event.answer()

@bot.on(events.CallbackQuery(data=b"restart_setup"))
async def restart_setup(event):
    pending_logins[event.sender_id] = {'state': 'api_id'}
    await event.edit(
        "**Send Your API ID**\n\n"
        "Please enter your API ID:",
        parse_mode='md'
    )
    await event.answer()

@bot.on(events.NewMessage())
async def handle_setup(event):
    uid = event.sender_id
    if uid not in pending_logins:
        return

    state = pending_logins[uid].get('state')
    data = pending_logins[uid]

    if state == 'api_id':
        try:
            api_id = int(event.text.strip())
            data['api_id'] = api_id
            data['state'] = 'api_hash'
            await event.respond(
                "**Send Your API Hash**\n\n"
                "Please enter your API Hash:",
                parse_mode='md'
            )
        except:
            await event.respond("**Invalid API ID**\nPlease enter a valid number.")

    elif state == 'api_hash':
        data['api_hash'] = event.text.strip()
        data['state'] = 'phone'
        buttons = [
            [Button.request_phone("Share Phone Number", resize=True)]
        ]
        await event.respond(
            "**Send Your Phone Number**\n\n"
            "Press the button to share your phone number\n"
            "Or type it manually: +201234567890",
            buttons=buttons,
            parse_mode='md'
        )

    elif state == 'phone':
        if event.message.contact:
            phone = f"+{event.message.contact.phone_number}"
        else:
            phone = event.text.strip()
        
        data['phone'] = phone
        
        processing_msg = await event.respond("**Processing...**")
        
        # استخدام main_loop (نفس طريقة الموقع القديم)
        def send_code_sync():
            async def _send():
                client = TelegramClient(StringSession(), data['api_id'], data['api_hash'])
                await client.connect()
                
                if await client.is_user_authorized():
                    return client, None, True
                
                result = await client.send_code_request(phone)
                return client, result.phone_code_hash, False
            
            return run_in_main_loop(_send())
        
        try:
            client, phone_code_hash, already_active = send_code_sync()
            
            if already_active:
                session_str = client.session.save()
                if await start_userbot(phone, session_str, data['api_id'], data['api_hash']):
                    buttons = [[Button.inline("START", b"start_setup")]]
                    await processing_msg.edit(
                        "**Account Already Active!**",
                        buttons=buttons,
                        parse_mode='md'
                    )
                else:
                    await processing_msg.edit("**Failed to start account**")
                del pending_logins[uid]
                return
            
            data['client'] = client
            data['hash'] = phone_code_hash
            data['state'] = 'code'
            
            await processing_msg.edit(
                "**Send The Code**\n\n"
                "Verification code sent\n"
                "Please enter the code:",
                parse_mode='md'
            )
            
        except FloodWaitError as e:
            minutes = e.seconds // 60
            buttons = [[Button.inline("RETRY", b"restart_setup")]]
            await processing_msg.edit(
                f"**Rate Limited**\nWait {minutes} minutes",
                buttons=buttons,
                parse_mode='md'
            )
            del pending_logins[uid]
        except Exception as e:
            logger.error(f"Send code error: {type(e).__name__}: {e}")
            buttons = [[Button.inline("RETRY", b"restart_setup")]]
            await processing_msg.edit(
                f"**Error: {type(e).__name__}**",
                buttons=buttons,
                parse_mode='md'
            )
            del pending_logins[uid]

    elif state == 'code':
        code = event.text.strip()
        data = pending_logins[uid]
        
        processing_msg = await event.respond("**Verifying...**")
        
        def verify_sync():
            async def _verify():
                if not data['client'].is_connected():
                    await data['client'].connect()
                await data['client'].sign_in(
                    phone=data['phone'],
                    code=code,
                    phone_code_hash=data['hash']
                )
            return run_in_main_loop(_verify())
        
        try:
            verify_sync()
            
            buttons = [[Button.inline("START", b"start_setup")]]
            await processing_msg.edit(
                "**Verification Successful!**\n**Rolex Telethon**",
                buttons=buttons,
                parse_mode='md'
            )
            
        except SessionPasswordNeededError:
            data['state'] = 'password'
            await processing_msg.edit(
                "**2FA Password Required**\n\nPlease enter your password:",
                parse_mode='md'
            )
            return
        except PhoneCodeExpiredError:
            buttons = [[Button.inline("RESEND", b"resend_code")]]
            await processing_msg.edit(
                "**Code Expired**\nRequest a new code",
                buttons=buttons,
                parse_mode='md'
            )
            return
        except PhoneCodeInvalidError:
            await processing_msg.edit("**Invalid Code**\nPlease try again.")
            return
        except Exception as e:
            logger.error(f"Verify error: {type(e).__name__}: {e}")
            buttons = [[Button.inline("RETRY", b"restart_setup")]]
            await processing_msg.edit(
                f"**Error: {type(e).__name__}**",
                buttons=buttons,
                parse_mode='md'
            )
            del pending_logins[uid]
            return
        
        await finish_setup(event, uid)

    elif state == 'password':
        password = event.text.strip()
        data = pending_logins[uid]
        
        processing_msg = await event.respond("**Verifying...**")
        
        def verify_pass_sync():
            async def _verify_pass():
                await data['client'].sign_in(password=password)
            return run_in_main_loop(_verify_pass())
        
        try:
            verify_pass_sync()
            buttons = [[Button.inline("START", b"start_setup")]]
            await processing_msg.edit(
                "**Verification Successful!**",
                buttons=buttons,
                parse_mode='md'
            )
        except Exception as e:
            logger.error(f"Password error: {type(e).__name__}: {e}")
            await processing_msg.edit(f"**Error: {type(e).__name__}**")
            del pending_logins[uid]
            return
        
        await finish_setup(event, uid)

@bot.on(events.CallbackQuery(data=b"resend_code"))
async def resend_code_callback(event):
    uid = event.sender_id
    if uid not in pending_logins or 'phone' not in pending_logins[uid]:
        await event.answer("No active setup process")
        return
    
    data = pending_logins[uid]
    await event.edit("**Sending New Code...**", parse_mode='md')
    
    def resend_sync():
        async def _resend():
            if 'client' not in data or not data['client'].is_connected():
                client = TelegramClient(StringSession(), data['api_id'], data['api_hash'])
                await client.connect()
                data['client'] = client
            result = await data['client'].send_code_request(data['phone'])
            return result.phone_code_hash
        return run_in_main_loop(_resend())
    
    try:
        data['hash'] = resend_sync()
        await event.edit(
            "**Send The Code**\n\nNew code sent\nPlease enter the code:",
            parse_mode='md'
        )
    except Exception as e:
        logger.error(f"Resend error: {type(e).__name__}: {e}")
        buttons = [[Button.inline("RETRY", b"restart_setup")]]
        await event.edit(
            f"**Error: {type(e).__name__}**",
            buttons=buttons,
            parse_mode='md'
        )
    
    await event.answer()

async def finish_setup(event, uid):
    data = pending_logins[uid]
    client = data['client']
    phone = data['phone']
    api_id = data['api_id']
    api_hash = data['api_hash']
    session_str = client.session.save()
    del pending_logins[uid]

    if await start_userbot(phone, session_str, api_id, api_hash):
        if hasattr(event, 'edit'):
            await event.edit("**Setup Complete!**\n**Rolex Telethon**", parse_mode='md')
        else:
            await event.respond("**Setup Complete!**\n**Rolex Telethon**", parse_mode='md')
    else:
        if hasattr(event, 'edit'):
            await event.edit("**Failed to start account**", parse_mode='md')
        else:
            await event.respond("**Failed to start account**", parse_mode='md')

async def start_userbot(phone, session_str, api_id, api_hash):
    client = TelegramClient(StringSession(session_str), api_id, api_hash)
    await client.connect()
    if await client.is_user_authorized():
        active_clients[phone] = client
        await save_all_sessions()
        return True
    return False

async def save_all_sessions():
    sessions = {}
    for phone, client in active_clients.items():
        if client.is_connected():
            sessions[phone] = {
                'session': client.session.save(),
                'api_id': client.api_id,
                'api_hash': client.api_hash
            }
    with open(SESSION_FILE, 'w') as f:
        json.dump(sessions, f)

async def load_all_sessions():
    if not os.path.exists(SESSION_FILE):
        return
    with open(SESSION_FILE, 'r') as f:
        sessions = json.load(f)
    for phone, data in sessions.items():
        try:
            client = TelegramClient(StringSession(data['session']), data['api_id'], data['api_hash'])
            await client.connect()
            if await client.is_user_authorized():
                active_clients[phone] = client
                logger.info(f"Account loaded: {phone}")
        except Exception as e:
            logger.error(f"Failed to load account {phone}: {e}")

# ======================== بدء التشغيل ========================
def start_main_loop():
    asyncio.set_event_loop(main_loop)
    main_loop.run_forever()

async def main():
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask health check started")

    await bot.start(bot_token=BOT_TOKEN)
    logger.info("Bot connected and ready")
    await load_all_sessions()
    await bot.run_until_disconnected()

# تشغيل main_loop في خيط منفصل (نفس الموقع القديم)
loop_thread = threading.Thread(target=start_main_loop, daemon=True)
loop_thread.start()

if __name__ == '__main__':
    asyncio.run_coroutine_threadsafe(main(), main_loop)
    loop_thread.join()
