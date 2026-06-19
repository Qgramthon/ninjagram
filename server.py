import asyncio
import threading
import logging
import json
import os
import sys
import uuid
from datetime import datetime

from flask import Flask
from telethon import TelegramClient, events, Button
from telethon.errors import (
    SessionPasswordNeededError, FloodWaitError, PhoneCodeInvalidError,
    PhoneCodeExpiredError, PasswordHashInvalidError
)
from telethon.sessions import StringSession
from telethon.network.connection.tcpfull import ConnectionTcpFull

# ======================== CONFIG (من Railway Environment Variables) ========================
BOT_TOKEN = os.getenv('BOT_TOKEN')
BOT_API_ID = int(os.getenv('BOT_API_ID', 2040))
BOT_API_HASH = os.getenv('BOT_API_HASH')

if not BOT_TOKEN or not BOT_API_HASH:
    raise ValueError("❌ BOT_TOKEN أو BOT_API_HASH غير موجودين في Environment Variables")

DATA_DIR = '/data'
os.makedirs(DATA_DIR, exist_ok=True)
SESSION_FILE = os.path.join(DATA_DIR, 'active_sessions.json')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ======================== Flask ========================
app = Flask(__name__)

@app.route('/')
def health():
    return f"✅ Rolex Telethon Running | Active Accounts: {len(active_clients)}", 200

@app.route('/status')
def status():
    return {
        "status": "running",
        "active_accounts": len(active_clients),
        "pending": len(pending_logins)
    }

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ======================== Global Variables ========================
bot = None
active_clients = {}   # phone -> client
active_tasks = {}     # phone -> task
pending_logins = {}   # user_id -> data

# ======================== Userbot Management ========================
async def start_userbot(phone: str, session_str: str, api_id: int, api_hash: str) -> bool:
    try:
        if phone in active_clients:
            await stop_userbot(phone)

        client = TelegramClient(
            StringSession(session_str),
            api_id,
            api_hash,
            connection=ConnectionTcpFull,
            flood_sleep_threshold=60,
            device_model="Railway Rolex",
            app_version="1.0"
        )

        await client.connect()
        if not await client.is_user_authorized():
            logger.warning(f"Account {phone} not authorized")
            return False

        active_clients[phone] = client
        task = asyncio.create_task(keep_userbot_alive(phone, client))
        active_tasks[phone] = task

        await save_all_sessions()
        logger.info(f"✅ Userbot started successfully: {phone}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to start {phone}: {e}")
        return False


async def keep_userbot_alive(phone: str, client: TelegramClient):
    try:
        while True:
            if not client.is_connected():
                await client.connect()
                logger.info(f"🔄 Reconnected: {phone}")
            await asyncio.sleep(45)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Userbot {phone} died: {e}")


async def stop_userbot(phone: str):
    if phone in active_tasks:
        active_tasks[phone].cancel()
        try:
            await active_tasks[phone]
        except:
            pass
        del active_tasks[phone]

    if phone in active_clients:
        try:
            await active_clients[phone].disconnect()
        except:
            pass
        del active_clients[phone]

    await save_all_sessions()


async def save_all_sessions():
    sessions = {}
    for phone, client in active_clients.items():
        try:
            sessions[phone] = {
                'session': client.session.save(),
                'api_id': client.api_id,
                'api_hash': client.api_hash
            }
        except:
            pass
    try:
        with open(SESSION_FILE, 'w', encoding='utf-8') as f:
            json.dump(sessions, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Save sessions error: {e}")


async def load_all_sessions():
    if not os.path.exists(SESSION_FILE):
        return
    try:
        with open(SESSION_FILE, 'r', encoding='utf-8') as f:
            sessions = json.load(f)
        for phone, data in sessions.items():
            await start_userbot(phone, data['session'], data['api_id'], data['api_hash'])
    except Exception as e:
        logger.error(f"Load sessions error: {e}")

# ======================== Bot Handlers ========================
@bot.on(events.NewMessage(pattern=r'^/ping$', func=lambda e: e.is_private))
async def bot_ping(event):
    await event.respond('🏓 **Pong!** البوت شغال بنجاح')


@bot.on(events.NewMessage(pattern=r'^/start$', func=lambda e: e.is_private))
async def bot_start(event):
    buttons = [
        [Button.inline("🚀 بدء التنصيب", b"start_setup")],
        [Button.inline("🔄 إعادة تنصيب", b"restart_setup")]
    ]
    await event.respond(
        "**Rolex Telethon - Railway**\n\n"
        "اضغط على **بدء التنصيب** لإضافة حساب حقيقي",
        buttons=buttons,
        parse_mode='md'
    )


@bot.on(events.CallbackQuery(data=b"start_setup"))
async def start_setup(event):
    pending_logins[event.sender_id] = {'state': 'api_id'}
    await event.edit("**أرسل API ID**\nاحصل عليه من my.telegram.org", parse_mode='md')


@bot.on(events.CallbackQuery(data=b"restart_setup"))
async def restart_setup(event):
    uid = event.sender_id
    if uid in pending_logins:
        del pending_logins[uid]
    await start_setup(event)


@bot.on(events.NewMessage(func=lambda e: e.is_private))
async def handle_setup(event):
    uid = event.sender_id
    if uid not in pending_logins:
        return

    data = pending_logins[uid]
    state = data.get('state')

    try:
        if state == 'api_id':
            data['api_id'] = int(event.text.strip())
            data['state'] = 'api_hash'
            await event.respond("**أرسل API Hash**:", parse_mode='md')

        elif state == 'api_hash':
            data['api_hash'] = event.text.strip()
            data['state'] = 'phone'
            buttons = [[Button.request_phone("📱 مشاركة رقم الهاتف", resize=True)]]
            await event.respond(
                "**أرسل رقم الهاتف**\nاضغط على الزر أو اكتب الرقم كاملاً (+201...)",
                buttons=buttons,
                parse_mode='md'
            )

        elif state == 'phone':
            phone = f"+{event.message.contact.phone_number}" if event.message.contact else event.text.strip()
            data['phone'] = phone

            await event.respond("**جاري إرسال كود التحقق...**", parse_mode='md')

            client = TelegramClient(StringSession(), data['api_id'], data['api_hash'])
            await client.connect()
            data['client'] = client

            result = await client.send_code_request(phone)
            data['hash'] = result.phone_code_hash
            data['state'] = 'code'

            await event.respond("**✅ تم إرسال الكود**\nأرسل الكود الذي وصلك:", parse_mode='md')

        elif state == 'code':
            code = event.text.strip()
            client = data['client']
            if not client.is_connected():
                await client.connect()

            await client.sign_in(phone=data['phone'], code=code, phone_code_hash=data['hash'])
            await finish_setup(event, uid)

        elif state == 'password':
            password = event.text.strip()
            await data['client'].sign_in(password=password)
            await finish_setup(event, uid)

    except FloodWaitError as e:
        await event.respond(f"**⏳ Rate Limit**\nانتظر {e.seconds//60} دقيقة", parse_mode='md')
        pending_logins.pop(uid, None)

    except SessionPasswordNeededError:
        data['state'] = 'password'
        await event.respond("**🔐 أدخل كلمة مرور التحقق (2FA)**", parse_mode='md')

    except (PhoneCodeInvalidError, PhoneCodeExpiredError):
        await event.respond("**❌ الكود خاطئ أو منتهي**\nحاول مرة أخرى", parse_mode='md')

    except Exception as e:
        logger.error(f"Setup Error: {e}")
        await event.respond("**❌ حدث خطأ أثناء التنصيب**", parse_mode='md')
        pending_logins.pop(uid, None)


async def finish_setup(event, uid):
    try:
        data = pending_logins[uid]
        client = data['client']
        phone = data['phone']
        session_str = client.session.save()

        pending_logins.pop(uid, None)

        if await start_userbot(phone, session_str, data['api_id'], data['api_hash']):
            await event.respond("**🎉 تم تنصيب الحساب بنجاح!**\nالحساب الآن نشط.", parse_mode='md')
        else:
            await event.respond("**❌ فشل تشغيل الحساب**", parse_mode='md')
    except Exception as e:
        logger.error(f"Finish setup error: {e}")
        await event.respond("**❌ خطأ في الإنهاء**", parse_mode='md')


# ======================== Main ========================
async def main():
    global bot
    # Flask
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"Flask started on port {os.environ.get('PORT', 5000)}")

    # Bot
    bot = TelegramClient(f'bot_session_{uuid.uuid4().hex[:8]}', BOT_API_ID, BOT_API_HASH)
    await bot.start(bot_token=BOT_TOKEN)
    logger.info("✅ Bot connected successfully")

    await load_all_sessions()
    logger.info("🚀 Rolex Telethon is ready on Railway!")

    await bot.run_until_disconnected()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        for phone in list(active_clients.keys()):
            asyncio.create_task(stop_userbot(phone))
    except Exception as e:
        logger.critical(f"Critical error: {e}")
