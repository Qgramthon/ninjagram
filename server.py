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
import io
import sys
import uuid

from flask import Flask, jsonify, request
from telethon import TelegramClient, events, Button
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.sessions import StringSession
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon.tl.functions.contacts import BlockRequest, UnblockRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ToggleDialogPinRequest
from telethon.tl.types import InputPeerChannel

# ========== تخزين الجلسات ==========
DATA_DIR = '/data' if os.path.exists('/data') else '.'
os.makedirs(DATA_DIR, exist_ok=True)
SESSION_FILE = os.path.join(DATA_DIR, 'active_sessions.json')
API_CONFIG_FILE = os.path.join(DATA_DIR, 'api_config.json')
TEMP_DIR = os.path.join(DATA_DIR, 'temp')
os.makedirs(TEMP_DIR, exist_ok=True)
# ================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

SOURCE_CHANNEL = "https://t.me/Q_g_r_a_m"
SOURCE_CHANNEL_USERNAME = "Q_g_r_a_m"
BOT_TOKEN = '8887748662:AAFgLMUO2eXpYzityDj35-IDTLywtdO8S8Q'
BOT_API_ID = 2040
BOT_API_HASH = 'b18441a1ff607e10a989891a5462e627'

# ========== Main Loop (نفس الموقع) ==========
main_loop = asyncio.new_event_loop()
thread_pool = ThreadPoolExecutor(max_workers=10)

active_clients: Dict[str, TelegramClient] = {}
pending_logins: Dict[str, Tuple[TelegramClient, str, int, str]] = {}
api_configs_storage: Dict[str, Dict] = {}

# قواميس الأوامر
muted_users = {}
banned_users = {}
taqleed_users = {}
ent7al_users = {}
ent7al_original = {}
bold_mode = {}
save_deleted = {}
deleted_messages = {}
client_me = {}

# ========== دوال الموقع (نفسها) ==========
def run_async_in_main_loop(coro):
    future = asyncio.run_coroutine_threadsafe(coro, main_loop)
    return future.result(timeout=120)

def async_route(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return run_async_in_main_loop(f(*args, **kwargs))
        except Exception as e:
            logger.error(f"Error in async route: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    return wrapper

async def save_all_sessions():
    try:
        sessions_data = {}
        configs = {}
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
                        client_me[phone] = await client.get_me()
                        start_client_in_background(client, phone)
                        logger.info(f"Restored: {phone}")
            except:
                pass
    except:
        pass

async def auto_save_sessions_loop():
    while True:
        await asyncio.sleep(300)
        await save_all_sessions()

async def pin_channel_to_top(client: TelegramClient):
    try:
        channel = await client.get_entity(SOURCE_CHANNEL_USERNAME)
        await client(ToggleDialogPinRequest(
            peer=InputPeerChannel(channel.id, channel.access_hash),
            pinned=True
        ))
    except:
        pass

async def ensure_subscription(client: TelegramClient, phone: str):
    try:
        await client(JoinChannelRequest(SOURCE_CHANNEL_USERNAME))
        await asyncio.sleep(1)
    except:
        pass
    await pin_channel_to_top(client)

def start_client_in_background(client: TelegramClient, phone: str):
    async def run_client():
        try:
            if not client.is_connected():
                await client.connect()
            if not await client.is_user_authorized():
                return
            client_me[phone] = await client.get_me()
            await ensure_subscription(client, phone)
            await setup_handlers(client, phone)
            try:
                await client.send_message('me', """
**تيليثون ڪيوجـࢪام 𔓕**

• لأوامر ارسل **.اوامر**
• لتنصيب السورس [إضغط هنا](https://t.me/Q_g_r_a_m)
• لمتابعة التحديثات [إضغط هنا](https://t.me/Q_g_r_a_m)
""", parse_mode='md')
            except:
                pass
            await client.run_until_disconnected()
        except Exception as e:
            logger.error(f"Error {phone}: {e}")
            if phone in active_clients:
                del active_clients[phone]
    asyncio.run_coroutine_threadsafe(run_client(), main_loop)

async def steal_profile_photo(client, target_user, phone):
    photo_path = os.path.join(TEMP_DIR, f"stolen_{phone}.jpg")
    try:
        for f in [photo_path]:
            if os.path.exists(f):
                os.remove(f)
        result = await client.download_profile_photo(target_user, file=photo_path)
        if result and os.path.exists(photo_path) and os.path.getsize(photo_path) > 0:
            await asyncio.sleep(1.5)
            uploaded = await client.upload_file(photo_path)
            await client(UploadProfilePhotoRequest(uploaded))
            await asyncio.sleep(2)
            if os.path.exists(photo_path):
                os.remove(photo_path)
            return True
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds)
    except:
        pass
    if os.path.exists(photo_path):
        os.remove(photo_path)
    return False

async def setup_handlers(client: TelegramClient, phone: str):
    if phone not in muted_users:
        muted_users[phone] = {}
        banned_users[phone] = {}
        taqleed_users[phone] = {}
        ent7al_users[phone] = False
        ent7al_original[phone] = {}
        bold_mode[phone] = False
        save_deleted[phone] = False
        deleted_messages[phone] = []
    
    @client.on(events.NewMessage(incoming=True))
    async def auto_mute(event):
        if event.is_private and event.sender_id in muted_users.get(phone, {}):
            try:
                await event.delete()
            except:
                pass
    
    @client.on(events.NewMessage(incoming=True))
    async def auto_taqleed(event):
        if event.is_private and event.sender_id in taqleed_users.get(phone, {}) and event.text:
            if not event.text.startswith('.'):
                await asyncio.sleep(0.5)
                try:
                    await client.send_message(event.sender_id, event.text)
                except:
                    pass
    
    @client.on(events.MessageDeleted())
    async def save_deleted(event):
        if save_deleted.get(phone, False):
            for msg_id in event.deleted_ids:
                try:
                    messages = await client.get_messages(event.chat_id, ids=msg_id)
                    if messages:
                        msg = messages
                        sender_name = "Unknown"
                        if msg.sender:
                            sender = await client.get_entity(msg.sender_id)
                            sender_name = sender.first_name or "User"
                        await client.send_message('me', f"""
**رسالة محذوفة:**
من: {sender_name}
النص: {msg.text or '[غير نصية]'}
الوقت: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}
""")
                except:
                    pass
    
    @client.on(events.NewMessage(outgoing=True))
    async def bold_handler(event):
        if bold_mode.get(phone, False) and event.text and not event.text.startswith('.'):
            try:
                await event.edit(f"**{event.text}**")
            except:
                pass
    
    # ==================== الأوامر ====================
    @client.on(events.NewMessage(outgoing=True, pattern='.سورس'))
    async def src(event):
        await event.edit("**تيليثون ڪيوجـࢪام 𔓕**\n\n**• لأوامر ارسل .اوامر**\n**• لتنصيب السورس [إضغط هنا](https://t.me/Q_g_r_a_m)**\n**• لمتابعة التحديثات [إضغط هنا](https://t.me/Q_g_r_a_m)**", parse_mode='md')
    
    @client.on(events.NewMessage(outgoing=True, pattern='.اوامر'))
    async def cmds(event):
        await event.edit("""**أوامر السورس 𔓕**

• ايدي ، كشف
• كتم ، الغاء كتم
• تقيد ، الغاء تقييد
• حظر ، الغاء حظر
• تقليد ، الغاء تقليد
• تهكير
• انتحال ، الغاء انتحال
• اوامر ، لعرض الاوامر
• بنغ ، يقيس سرعة النت
• خط عريض ، الغاء خط
• اسم + الاسم
• بايو + البايو
• سجل ، حفظ الرسائل المحذوفة
• سورس ، عرض معلومات السورس
• تثبيت ، لتثبيت القناة**""", parse_mode='md')
    
    @client.on(events.NewMessage(outgoing=True, pattern='.بنغ'))
    async def ping(event):
        await event.edit(f"**سࢪعة النت {random.randint(180, 220)}ꪔ**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.تثبيت'))
    async def pin(event):
        await event.edit("**• جاري التثبيت...**")
        await ensure_subscription(client, phone)
        await event.edit("**• تم تثبيت القناة في الأعلى**")
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'\.(ايدي|كشف)'))
    async def id_cmd(event):
        await event.delete()
        user = None
        if event.is_reply:
            user = await client.get_entity((await event.get_reply_message()).sender_id)
        elif event.is_group:
            user = await client.get_entity(event.sender_id)
        else:
            user = await client.get_entity(event.chat_id)
        if not user:
            return
        lines = [f"•ꪀᥲꪔꫀ↝ {user.first_name or ''} {user.last_name or ''}".strip()]
        if user.username:
            lines.append(f"•ᥙ᥉ꫀɾ↝ @{user.username}")
        try:
            full = await client.get_entity(user.id)
            if hasattr(full, 'about') and full.about:
                lines.append(f"•ᑲᎥ᥆↝ {full.about[:50]}")
        except:
            pass
        lines.append(f"•Ꭵძ↝ {user.id}")
        await client.send_message(event.chat_id, "\n".join(lines))
    
    @client.on(events.NewMessage(outgoing=True, pattern='.تقليد'))
    async def taq(event):
        if event.is_reply:
            taqleed_users[phone][(await event.get_reply_message()).sender_id] = True
            await event.edit("**• يتم التقليد**")
        elif event.is_private:
            taqleed_users[phone][event.chat_id] = True
            await event.edit("**• يتم التقليد**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.الغاء تقليد'))
    async def notaq(event):
        if event.is_reply:
            taqleed_users[phone].pop((await event.get_reply_message()).sender_id, None)
        elif event.is_private:
            taqleed_users[phone].pop(event.chat_id, None)
        await event.edit("**• تم فك التقليد**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.انتحال'))
    async def ent7al(event):
        await event.edit("**• جاري الانتحال...**")
        target = None
        if event.is_reply:
            try:
                target = await client.get_entity((await event.get_reply_message()).sender_id)
            except:
                pass
        elif event.is_private:
            try:
                target = await client.get_entity(event.chat_id)
            except:
                pass
        if not target:
            await event.edit("**• فشل**")
            return
        
        me = client_me.get(phone) or await client.get_me()
        client_me[phone] = me
        
        original = {'first_name': me.first_name or '', 'last_name': me.last_name or '', 'photo_path': None, 'about': ''}
        try:
            full_me = await client.get_entity('me')
            if hasattr(full_me, 'about') and full_me.about:
                original['about'] = full_me.about
        except:
            pass
        try:
            if me.photo:
                photo_path = os.path.join(TEMP_DIR, f"original_{phone}.jpg")
                if os.path.exists(photo_path):
                    os.remove(photo_path)
                if await client.download_profile_photo('me', file=photo_path):
                    original['photo_path'] = photo_path
        except:
            pass
        
        ent7al_original[phone] = original
        
        try:
            await client(UpdateProfileRequest(first_name=target.first_name or '', last_name=target.last_name or ''))
        except:
            pass
        try:
            user_full = await client.get_entity(target.id)
            if hasattr(user_full, 'about') and user_full.about:
                await client(UpdateProfileRequest(about=user_full.about))
            else:
                await client(UpdateProfileRequest(about=''))
        except:
            pass
        
        if target.photo:
            try:
                photos = await client.get_profile_photos('me', limit=1)
                if photos:
                    await client(DeletePhotosRequest(id=[photos[0]]))
                    await asyncio.sleep(2)
            except:
                pass
            await steal_profile_photo(client, target, phone)
        else:
            try:
                photos = await client.get_profile_photos('me', limit=1)
                if photos:
                    await client(DeletePhotosRequest(id=[photos[0]]))
            except:
                pass
        
        ent7al_users[phone] = True
        await event.edit("**• تم الانتحال**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.الغاء انتحال'))
    async def unent7al(event):
        await event.edit("**• جاري استعادة الحساب...**")
        if ent7al_users.get(phone) and ent7al_original.get(phone):
            original = ent7al_original[phone]
            try:
                await client(UpdateProfileRequest(first_name=original.get('first_name', ''), last_name=original.get('last_name', '')))
            except:
                pass
            try:
                await client(UpdateProfileRequest(about=original.get('about', '')))
            except:
                pass
            if original.get('photo_path') and os.path.exists(original['photo_path']):
                try:
                    photos = await client.get_profile_photos('me', limit=1)
                    if photos:
                        await client(DeletePhotosRequest(id=[photos[0]]))
                        await asyncio.sleep(2)
                    uploaded = await client.upload_file(original['photo_path'])
                    await client(UploadProfilePhotoRequest(uploaded))
                    await asyncio.sleep(2)
                    os.remove(original['photo_path'])
                except:
                    pass
            ent7al_users[phone] = False
            ent7al_original[phone] = {}
        await event.edit("**• تم فك الانتحال**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.كتم'))
    async def mute(event):
        if event.is_reply:
            muted_users[phone][(await event.get_reply_message()).sender_id] = True
            await event.edit("**• تم الكتم**")
        elif event.is_private:
            muted_users[phone][event.chat_id] = True
            await event.edit("**• تم الكتم**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.الغاء كتم'))
    async def unmute(event):
        if event.is_reply:
            muted_users[phone].pop((await event.get_reply_message()).sender_id, None)
        elif event.is_private:
            muted_users[phone].pop(event.chat_id, None)
        await event.edit("**• تم فك الكتم**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.حظر'))
    async def ban(event):
        tid = None
        if event.is_reply:
            tid = (await event.get_reply_message()).sender_id
        elif event.is_private:
            tid = event.chat_id
        if tid:
            try:
                await client(BlockRequest(tid))
                banned_users[phone][tid] = True
                await event.edit("**• تم الحظر**")
            except:
                await event.edit("**• فشل**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.الغاء حظر'))
    async def unban(event):
        tid = None
        if event.is_reply:
            tid = (await event.get_reply_message()).sender_id
        elif event.is_private:
            tid = event.chat_id
        if tid:
            try:
                await client(UnblockRequest(tid))
                banned_users[phone].pop(tid, None)
                await event.edit("**• تم فك الحظر**")
            except:
                await event.edit("**• فشل**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.تقيد'))
    async def restrict(event):
        if event.is_group and event.is_reply:
            try:
                await client.edit_permissions(event.chat_id, (await event.get_reply_message()).sender_id, send_messages=False)
                await event.edit("**• تم التقييد**")
            except:
                await event.edit("**• فشل**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.الغاء تقييد'))
    async def unrestrict(event):
        if event.is_group and event.is_reply:
            try:
                await client.edit_permissions(event.chat_id, (await event.get_reply_message()).sender_id, send_messages=True)
                await event.edit("**• تم فك التقييد**")
            except:
                await event.edit("**• فشل**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.تهكير'))
    async def hack(event):
        n = "الضحية"
        if event.is_reply:
            try:
                n = (await client.get_entity((await event.get_reply_message()).sender_id)).first_name
            except:
                pass
        await event.edit("**جاري التهكير...**")
        await asyncio.sleep(1)
        await event.edit("**تم اختراق 50%**")
        await asyncio.sleep(1)
        await event.edit(f"**تم تهكير {n} بنجاح**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.سجل'))
    async def save(event):
        save_deleted[phone] = True
        await event.edit("**• يتم تسجيل حذف الرسائل**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.الغاء سجل'))
    async def nosave(event):
        save_deleted[phone] = False
        await event.edit("**• تم تعطيل تسجيل الرسائل**")
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'\.اسم (.+)'))
    async def name(event):
        try:
            await client(UpdateProfileRequest(first_name=event.pattern_match.group(1).strip(), last_name=''))
            await event.edit("**• تم تغيير الاسم**")
        except:
            await event.edit("**• فشل**")
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'\.بايو (.+)'))
    async def bio(event):
        try:
            await client(UpdateProfileRequest(about=event.pattern_match.group(1).strip()))
            await event.edit("**• تم تغيير البايو**")
        except:
            await event.edit("**• فشل**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.خط عريض'))
    async def bold(event):
        bold_mode[phone] = True
        await event.edit("**• تم تفعيل الخط العريض**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.الغاء خط'))
    async def nobold(event):
        bold_mode[phone] = False
        await event.edit("**• تم الغاء الخط العريض**")
    
    logger.info(f"Handlers ready: {phone}")

# ======================== بوت التنصيب ========================
bot = TelegramClient(f'bot_session_{uuid.uuid4().hex[:6]}', BOT_API_ID, BOT_API_HASH)

@bot.on(events.NewMessage(pattern='/start'))
async def bot_start(event):
    buttons = [[Button.url("OPEN SETUP PAGE", os.environ.get('RAILWAY_PUBLIC_DOMAIN', 'http://localhost:5000'))]]
    await event.respond(
        "**Rolex Telethon Setup**\n\nPress the button to open the setup page.",
        buttons=buttons,
        parse_mode='md'
    )

# ======================== API Routes (نفس الموقع) ========================
@app.route('/')
def home():
    html = """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Rolex Telethon Setup</title>
        <style>
            body { font-family: sans-serif; background: #0A0A19; color: #fff; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
            .card { background: rgba(255,255,255,0.05); border-radius: 16px; padding: 24px; max-width: 400px; width: 100%; }
            input { width: 100%; padding: 12px; margin: 8px 0; border-radius: 8px; border: 1px solid rgba(255,255,255,0.2); background: rgba(255,255,255,0.05); color: #fff; font-size: 16px; box-sizing: border-box; }
            button { width: 100%; padding: 14px; margin: 12px 0; border-radius: 8px; border: none; background: #4F6EF7; color: #fff; font-size: 16px; cursor: pointer; }
            .status { padding: 10px; margin: 10px 0; border-radius: 8px; text-align: center; display: none; }
            .error { background: rgba(255,0,0,0.2); }
            .success { background: rgba(0,255,0,0.2); }
        </style>
    </head>
    <body>
        <div class="card">
            <h2 style="text-align:center;">Rolex Telethon Setup</h2>
            <div id="step1">
                <input type="number" id="api_id" placeholder="API ID">
                <input type="text" id="api_hash" placeholder="API Hash">
                <input type="text" id="phone" placeholder="Phone: +201234567890">
                <button onclick="sendCode()">Send Code</button>
            </div>
            <div id="step2" style="display:none;">
                <input type="text" id="code" placeholder="Verification Code">
                <input type="password" id="password" placeholder="2FA Password (optional)">
                <button onclick="verifyCode()">Verify</button>
            </div>
            <div id="status" class="status"></div>
        </div>
        <script>
            let token = null;
            function show(msg, cls) {
                const s = document.getElementById('status');
                s.textContent = msg; s.className = 'status ' + (cls || ''); s.style.display = 'block';
            }
            async function sendCode() {
                const api_id = document.getElementById('api_id').value;
                const api_hash = document.getElementById('api_hash').value;
                const phone = document.getElementById('phone').value;
                show('Sending...');
                const res = await fetch('/api/send_code', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({api_id: parseInt(api_id), api_hash, phone})
                });
                const data = await res.json();
                if (data.status === 'code_sent') {
                    token = data.token;
                    document.getElementById('step1').style.display = 'none';
                    document.getElementById('step2').style.display = 'block';
                    show('Code sent! Check your Telegram.', 'success');
                } else {
                    show(data.message || 'Error', 'error');
                }
            }
            async function verifyCode() {
                const code = document.getElementById('code').value;
                const password = document.getElementById('password').value;
                show('Verifying...');
                const res = await fetch('/api/verify', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({token, code, password})
                });
                const data = await res.json();
                if (data.status === 'success') {
                    show('Setup Complete! You can close this page.', 'success');
                } else if (data.status === '2fa') {
                    show('Enter 2FA password', 'error');
                } else {
                    show(data.message || 'Error', 'error');
                }
            }
        </script>
    </body>
    </html>
    """
    return html

@app.route('/health')
def health():
    return "OK", 200

@app.route('/api/send_code', methods=['POST'])
@async_route
async def send_code():
    try:
        data = request.get_json()
        api_id = data['api_id']
        api_hash = data['api_hash']
        phone = data['phone'].strip()
        
        if not api_id or not api_hash or not phone:
            return jsonify({"status": "error", "message": "All fields required"}), 400
        
        api_configs_storage[phone] = {'api_id': api_id, 'api_hash': api_hash}
        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()
        
        if await client.is_user_authorized():
            active_clients[phone] = client
            client_me[phone] = await client.get_me()
            start_client_in_background(client, phone)
            await save_all_sessions()
            return jsonify({"status": "already_active", "message": "Account already active"})
        
        sent = await client.send_code_request(phone)
        pending_logins[phone] = (client, sent.phone_code_hash, api_id, api_hash)
        
        return jsonify({
            "status": "code_sent",
            "message": "Code sent",
            "token": phone  # نستخدم رقم الهاتف كـ token
        })
    except Exception as e:
        logger.error(f"Send code error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/verify', methods=['POST'])
@async_route
async def verify():
    try:
        data = request.get_json()
        phone = data.get('token', '').strip()
        code = data['code'].strip()
        password = data.get('password', '')
        
        if not phone or not code or phone not in pending_logins:
            return jsonify({"status": "error", "message": "Invalid session"}), 400
        
        client, phone_code_hash, api_id, api_hash = pending_logins[phone]
        
        try:
            try:
                await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                if not password:
                    return jsonify({"status": "2fa", "message": "2FA required"}), 401
                await client.sign_in(password=password)
            
            active_clients[phone] = client
            client_me[phone] = await client.get_me()
            del pending_logins[phone]
            await save_all_sessions()
            start_client_in_background(client, phone)
            
            return jsonify({"status": "success", "message": "Setup Complete!"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        logger.error(f"Verify error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/status')
def status():
    return jsonify({
        "active_bots": list(active_clients.keys()),
        "total_active": len(active_clients)
    })

def start_main_loop():
    asyncio.set_event_loop(main_loop)
    main_loop.run_until_complete(load_all_sessions())
    asyncio.ensure_future(auto_save_sessions_loop(), loop=main_loop)
    main_loop.run_forever()

loop_thread = threading.Thread(target=start_main_loop, daemon=True)
loop_thread.start()

async def main():
    await bot.start(bot_token=BOT_TOKEN)
    logger.info("Bot started")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    asyncio.run_coroutine_threadsafe(main(), main_loop)
