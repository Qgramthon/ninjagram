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
from functools import wraps

from flask import Flask
from telethon import TelegramClient, events
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

# ======================== Main Event Loop (نفس طريقة الموقع) ========================
main_loop = asyncio.new_event_loop()

def run_coro(coro):
    """تشغيل coroutine في الـ main_loop (نفس الموقع بالضبط)"""
    future = asyncio.run_coroutine_threadsafe(coro, main_loop)
    return future.result(timeout=60)

# ======================== المتغيرات العامة ========================
bot = TelegramClient(f'bot_session_{uuid.uuid4().hex[:6]}', BOT_API_ID, BOT_API_HASH)

# العملاء النشطون (بعد التنصيب)
active_clients = {}
# التخزين المؤقت للعملاء اللي بيتنصبوا
pending_logins = {}

# ======================== بوت التنصيب (نضيف بس) ========================
@bot.on(events.NewMessage(pattern='/ping'))
async def bot_ping(event):
    await event.respond('Pong!')

@bot.on(events.NewMessage(pattern='/start'))
async def bot_start(event):
    await event.respond(
        "🜲 **مرحباً بك في بوت تنصيب Rolex Telethon**\n\n"
        "لتنصيب حسابك، أرسل:\n"
        "`/setup` واتبع التعليمات.\n\n"
        "بعد التنصيب، ارسل `.اوامر` من حسابك لرؤية الأوامر.\n\n"
        "للاستفسار: @Q_g_r_a_m",
        parse_mode='md'
    )

@bot.on(events.NewMessage(pattern='/setup'))
async def setup_init(event):
    pending_logins[event.sender_id] = {'state': 'api_id'}
    await event.respond("📝 **أرسل API ID الخاص بك:**")

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
            await event.respond("🔑 **أرسل API Hash الخاص بك:**")
        except:
            await event.respond("❌ يرجى إدخال رقم صحيح.")

    elif state == 'api_hash':
        data['api_hash'] = event.text.strip()
        data['state'] = 'phone'
        await event.respond("📱 **أرسل رقم الهاتف (بمفتاح الدولة):**\nمثال: `+201234567890`")

    elif state == 'phone':
        phone = event.text.strip()
        data['phone'] = phone
        try:
            # تأخير عشوائي لتجنب FloodWait
            await asyncio.sleep(random.uniform(1, 3))
            
            async def send_code():
                client = TelegramClient(StringSession(), data['api_id'], data['api_hash'])
                await client.connect()
                result = await client.send_code_request(phone, force_sms=False)
                return client, result.phone_code_hash
            
            client, phone_code_hash = run_coro(send_code())
            data['client'] = client
            data['hash'] = phone_code_hash
            data['state'] = 'code'
            await event.respond("📲 **تم إرسال كود التحقق. أرسله فوراً:**")
        except FloodWaitError as e:
            minutes = e.seconds // 60
            await event.respond(f"⏳ **تم حظر الطلب مؤقتاً**\nاستنى {minutes} دقيقة قبل ما تطلب كود تاني")
            del pending_logins[uid]
        except Exception as e:
            logger.error(f"Setup phone error: {type(e).__name__}: {e}")
            await event.respond(f"❌ خطأ: {type(e).__name__}: {str(e)[:100]}")
            del pending_logins[uid]

    elif state == 'code':
        code = event.text.strip()
        data = pending_logins[uid]
        try:
            async def verify_code():
                if not data['client'].is_connected():
                    await data['client'].connect()
                await data['client'].sign_in(phone=data['phone'], code=code, phone_code_hash=data['hash'])
            
            run_coro(verify_code())
        except SessionPasswordNeededError:
            data['state'] = 'password'
            await event.respond("🔐 **الحساب محمي بكلمة مرور.**\nأرسل كلمة المرور:")
            return
        except PhoneCodeExpiredError:
            await event.respond("⏰ **انتهت صلاحية الكود.**\nاطلب كود جديد باستخدام `/resend`")
            return
        except Exception as e:
            logger.error(f"Verify error: {type(e).__name__}: {e}")
            await event.respond(f"❌ فشل التفعيل: {type(e).__name__}: {str(e)[:100]}")
            del pending_logins[uid]
            return
        await finish_setup(event, uid)

    elif state == 'password':
        password = event.text.strip()
        try:
            async def verify_password():
                await data['client'].sign_in(password=password)
            run_coro(verify_password())
        except Exception as e:
            await event.respond(f"❌ فشل التفعيل: {str(e)[:100]}")
            del pending_logins[uid]
            return
        await finish_setup(event, uid)

@bot.on(events.NewMessage(pattern='/resend'))
async def resend_code(event):
    uid = event.sender_id
    if uid not in pending_logins or 'phone' not in pending_logins[uid]:
        await event.respond("⚠️ لم يتم بدء عملية التسجيل. أرسل /setup أولاً.")
        return
    data = pending_logins[uid]
    try:
        async def resend():
            if 'client' in data and data['client'].is_connected():
                result = await data['client'].send_code_request(data['phone'], force_sms=False)
                return result.phone_code_hash
            else:
                client = TelegramClient(StringSession(), data['api_id'], data['api_hash'])
                await client.connect()
                result = await client.send_code_request(data['phone'], force_sms=False)
                data['client'] = client
                return result.phone_code_hash
        
        data['hash'] = run_coro(resend())
        await event.respond("📲 **تم إرسال كود جديد. أرسله فوراً:**")
    except Exception as e:
        await event.respond(f"❌ خطأ: {str(e)[:100]}")

async def finish_setup(event, uid):
    data = pending_logins[uid]
    client = data['client']
    phone = data['phone']
    api_id = data['api_id']
    api_hash = data['api_hash']
    session_str = client.session.save()
    del pending_logins[uid]

    if await start_userbot(phone, session_str, api_id, api_hash):
        await event.respond("✅ **تم تنصيب حسابك بنجاح!**\n\nيمكنك الآن استخدام حسابك كـ UserBot.\nارسل `.اوامر` من حسابك لرؤية الأوامر.")
    else:
        await event.respond("❌ فشل تشغيل الحساب بعد التفعيل.")

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
                logger.info(f"✅ تم تحميل حساب: {phone}")
        except Exception as e:
            logger.error(f"❌ فشل تحميل حساب {phone}: {e}")

# ======================== بدء التشغيل ========================
def start_main_loop():
    asyncio.set_event_loop(main_loop)
    main_loop.run_forever()

async def main():
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("✅ Flask health check started")

    await bot.start(bot_token=BOT_TOKEN)
    logger.info("✅ البوت متصل وجاهز")
    await load_all_sessions()
    await bot.run_until_disconnected()

loop_thread = threading.Thread(target=start_main_loop, daemon=True)
loop_thread.start()

if __name__ == '__main__':
    asyncio.run_coroutine_threadsafe(main(), main_loop)
    loop_thread.join()
