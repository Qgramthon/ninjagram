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

from flask import Flask, jsonify, request
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from telethon.tl.functions.contacts import BlockRequest, UnblockRequest
from telethon.tl.functions.channels import JoinChannelRequest

# ========== تخزين الجلسات في Railway Volume ==========
DATA_DIR = '/data' if os.path.exists('/data') else '.'
os.makedirs(DATA_DIR, exist_ok=True)
SESSION_FILE = os.path.join(DATA_DIR, 'active_sessions.json')
API_CONFIG_FILE = os.path.join(DATA_DIR, 'api_config.json')
# ======================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

SOURCE_CHANNEL = "https://t.me/Q_g_r_a_m"
SOURCE_CHANNEL_USERNAME = "Q_g_r_a_m"

main_loop = asyncio.new_event_loop()
thread_pool = ThreadPoolExecutor(max_workers=10)

active_clients: Dict[str, TelegramClient] = {}
pending_logins: Dict[str, Tuple[TelegramClient, str, int, str]] = {}
api_configs_storage: Dict[str, Dict] = {}

# كل قواميس البوتات - مفتاحها phone
muted_users = {}
banned_users = {}
taqleed_users = {}
ent7al_users = {}
ent7al_original = {}
bold_mode = {}
save_deleted = {}
deleted_messages = {}

# لتخزين الرسائل الأصلية قبل التحرير للخط العريض
original_messages = {}

def run_async_in_main_loop(coro):
    future = asyncio.run_coroutine_threadsafe(coro, main_loop)
    return future.result(timeout=30)

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
                    session_string = client.session.save()
                    sessions_data[phone] = session_string
                    
                    if phone in api_configs_storage:
                        configs[phone] = api_configs_storage[phone]
            except:
                continue
        
        with open(SESSION_FILE, 'w') as f:
            json.dump(sessions_data, f)
        
        with open(API_CONFIG_FILE, 'w') as f:
            json.dump(configs, f)
        
        logger.info(f"Saved {len(sessions_data)} sessions to Volume")
    except Exception as e:
        logger.error(f"Save error: {e}")

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
                        start_client_in_background(client, phone)
                        logger.info(f"Restored: {phone}")
            except Exception as e:
                logger.error(f"Restore error {phone}: {e}")
        
        logger.info(f"Loaded {len(active_clients)} sessions from Volume")
    except Exception as e:
        logger.error(f"Load error: {e}")

async def auto_save_sessions_loop():
    while True:
        await asyncio.sleep(300)
        await save_all_sessions()

def start_client_in_background(client: TelegramClient, phone: str):
    async def run_client():
        try:
            if not client.is_connected():
                await client.connect()
            
            if not await client.is_user_authorized():
                logger.error(f"Client not authorized for {phone}")
                return
            
            logger.info(f"UserBot Started for {phone}")
            
            try:
                await client(JoinChannelRequest(SOURCE_CHANNEL_USERNAME))
            except:
                pass
            
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
    async def auto_mute_handler(event):
        if event.is_private and event.sender_id in muted_users.get(phone, {}):
            await event.delete()
    
    @client.on(events.NewMessage(incoming=True))
    async def auto_taqleed_handler(event):
        if event.is_private and event.sender_id in taqleed_users.get(phone, {}) and event.text:
            if not event.text.startswith('.'):
                await asyncio.sleep(0.5)
                await client.send_message(event.sender_id, event.text)
    
    @client.on(events.MessageDeleted())
    async def save_deleted_handler(event):
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
    
    @client.on(events.MessageEdited())
    async def save_edited_handler(event):
        if save_deleted.get(phone, False):
            try:
                original = await client.get_messages(event.chat_id, ids=event.id)
                if original and original.text != event.text:
                    await client.send_message('me', f"""
**رسالة معدلة:**
قبل: {original.text or '[غير نصية]'}
بعد: {event.text or '[غير نصية]'}
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
    
    @client.on(events.NewMessage(pattern='.سورس'))
    async def source_cmd(event):
        await event.edit("**تيليثون ڪيوجـࢪام 𔓕**\n\n**• لأوامر ارسل .اوامر**\n**• لتنصيب السورس [إضغط هنا](https://t.me/Q_g_r_a_m)**\n**• لمتابعة التحديثات [إضغط هنا](https://t.me/Q_g_r_a_m)**", parse_mode='md')
    
    @client.on(events.NewMessage(pattern='.اوامر'))
    async def commands_list(event):
        await event.edit("""**أوامر السورس 𔓕**

• ايدي ، كشف
• كتم ، الغاء كتم
• تقيد ، الغاء تقييد
• حظر ، الغاء حظر
• تقليد ، الغاء تقليد
• تهكير ، وهمي للهزار
• انتحال ، الغاء انتحال
• اوامر ، لعرض الاوامر
• بنغ ، يقيس سرعة النت
• خط عريض ، الغاء خط
• اسم + الاسم المراد تعيينة
• بايو + البايو المراد تعيينة
• سجل ، حفظ الرسائل المحذوفة
• سورس ، عرض معلومات السورس**""", parse_mode='md')
    
    @client.on(events.NewMessage(pattern='.بنغ'))
    async def ping_cmd(event):
        await event.edit(f"**سࢪعة النت {random.randint(180, 220)}ꪔ**")
    
    @client.on(events.NewMessage(pattern=r'\.(ايدي|كشف)'))
    async def id_cmd(event):
        await event.delete()
        
        if event.is_reply:
            reply = await event.get_reply_message()
            user = await client.get_entity(reply.sender_id)
        elif event.is_group:
            user = await client.get_entity(event.sender_id)
        else:
            user = await client.get_entity(event.chat_id)
        
        user_id = user.id
        first_name = user.first_name or ""
        last_name = user.last_name or ""
        
        lines = []
        lines.append(f"•ꪀᥲꪔꫀ↝ {first_name} {last_name}".strip())
        
        if user.username:
            lines.append(f"•ᥙ᥉ꫀɾ↝ @{user.username}")
        
        try:
            full = await client.get_entity(user_id)
            if hasattr(full, 'about') and full.about:
                lines.append(f"•ᑲᎥ᥆↝ {full.about[:50]}")
        except:
            pass
        
        lines.append(f"•Ꭵძ↝ {user_id}")
        
        msg = "\n".join(lines)
        await client.send_message(event.chat_id, msg.strip())
    
    @client.on(events.NewMessage(pattern='.تقليد'))
    async def taqleed_cmd(event):
        if event.is_reply:
            reply = await event.get_reply_message()
            taqleed_users[phone][reply.sender_id] = True
            await event.edit("**• يتم التقليد**")
        elif event.is_private:
            taqleed_users[phone][event.chat_id] = True
            await event.edit("**• يتم التقليد**")
    
    @client.on(events.NewMessage(pattern='.الغاء تقليد'))
    async def stop_taqleed_cmd(event):
        if event.is_reply:
            reply = await event.get_reply_message()
            taqleed_users[phone].pop(reply.sender_id, None)
        elif event.is_private:
            taqleed_users[phone].pop(event.chat_id, None)
        await event.edit("**• تم فك التقليد**")
    
    @client.on(events.NewMessage(pattern='.انتحال'))
    async def ent7al_cmd(event):
        await event.edit("**• جاري الانتحال...**")
        
        if event.is_reply:
            reply = await event.get_reply_message()
            user = await client.get_entity(reply.sender_id)
        elif event.is_private:
            user = await client.get_entity(event.chat_id)
        else:
            return
        
        me = await client.get_me()
        
        # حفظ البيانات الأصلية
        ent7al_original[phone] = {
            'first_name': me.first_name,
            'last_name': me.last_name or '',
            'photo': None,
            'about': ''
        }
        
        try:
            full_me = await client.get_entity('me')
            if hasattr(full_me, 'about'):
                ent7al_original[phone]['about'] = full_me.about or ''
        except:
            pass
        
        # حفظ الصورة الأصلية
        try:
            if me.photo:
                original_photo = await client.download_profile_photo('me', file=bytes)
                if original_photo:
                    ent7al_original[phone]['photo'] = original_photo
        except Exception as e:
            logger.error(f"Save original photo error: {e}")
        
        # تغيير الاسم
        await client(UpdateProfileRequest(
            first_name=user.first_name or '',
            last_name=user.last_name or ''
        ))
        
        # تغيير البايو
        try:
            user_full = await client.get_entity(user.id)
            if hasattr(user_full, 'about') and user_full.about:
                await client(UpdateProfileRequest(about=user_full.about))
        except:
            pass
        
        # تغيير الصورة
        try:
            if user.photo:
                photo_data = await client.download_profile_photo(user.id, file=bytes)
                if photo_data:
                    uploaded_file = await client.upload_file(photo_data)
                    await client(UploadProfilePhotoRequest(uploaded_file))
                    await asyncio.sleep(1)
                    logger.info(f"Profile photo stolen successfully for {phone}")
        except Exception as e:
            logger.error(f"Photo steal error for {phone}: {e}")
        
        ent7al_users[phone] = True
        await event.edit("**• تم الانتحال**")
    
    @client.on(events.NewMessage(pattern='.الغاء انتحال'))
    async def stop_ent7al_cmd(event):
        await event.edit("**• جاري استعادة الحساب...**")
        
        if ent7al_users.get(phone) and ent7al_original.get(phone):
            original = ent7al_original[phone]
            
            # استعادة الاسم
            await client(UpdateProfileRequest(
                first_name=original['first_name'],
                last_name=original['last_name']
            ))
            
            # استعادة البايو
            try:
                await client(UpdateProfileRequest(about=original.get('about', '')))
            except:
                pass
            
            # استعادة الصورة
            if original.get('photo'):
                try:
                    uploaded_file = await client.upload_file(original['photo'])
                    await client(UploadProfilePhotoRequest(uploaded_file))
                    await asyncio.sleep(1)
                    logger.info(f"Original photo restored for {phone}")
                except Exception as e:
                    logger.error(f"Photo restore error: {e}")
            
            ent7al_users[phone] = False
            ent7al_original[phone] = {}
        
        await event.edit("**• تم فك الانتحال**")
    
    @client.on(events.NewMessage(pattern='.كتم'))
    async def mute_cmd(event):
        if event.is_reply:
            reply = await event.get_reply_message()
            muted_users[phone][reply.sender_id] = True
            await event.edit("**• تم الكتم**")
        elif event.is_private:
            muted_users[phone][event.chat_id] = True
            await event.edit("**• تم الكتم**")
    
    @client.on(events.NewMessage(pattern='.الغاء كتم'))
    async def unmute_cmd(event):
        if event.is_reply:
            reply = await event.get_reply_message()
            muted_users[phone].pop(reply.sender_id, None)
        elif event.is_private:
            muted_users[phone].pop(event.chat_id, None)
        await event.edit("**• تم فك الكتم**")
    
    @client.on(events.NewMessage(pattern='.حظر'))
    async def ban_cmd(event):
        if event.is_reply:
            reply = await event.get_reply_message()
            await client(BlockRequest(reply.sender_id))
            banned_users[phone][reply.sender_id] = True
            await event.edit("**• تم الحظر**")
        elif event.is_private:
            await client(BlockRequest(event.chat_id))
            banned_users[phone][event.chat_id] = True
            await event.edit("**• تم الحظر**")
    
    @client.on(events.NewMessage(pattern='.الغاء حظر'))
    async def unban_cmd(event):
        if event.is_reply:
            reply = await event.get_reply_message()
            await client(UnblockRequest(reply.sender_id))
            banned_users[phone].pop(reply.sender_id, None)
        elif event.is_private:
            await client(UnblockRequest(event.chat_id))
            banned_users[phone].pop(event.chat_id, None)
        await event.edit("**• تم فك الحظر**")
    
    @client.on(events.NewMessage(pattern='.تقيد'))
    async def restrict_cmd(event):
        if event.is_group and event.is_reply:
            reply = await event.get_reply_message()
            try:
                await client.edit_permissions(event.chat_id, reply.sender_id, send_messages=False)
                await event.edit("**• تم التقييد**")
            except:
                await event.edit("**• فشل التقييد**")
    
    @client.on(events.NewMessage(pattern='.الغاء تقييد'))
    async def unrestrict_cmd(event):
        if event.is_group and event.is_reply:
            reply = await event.get_reply_message()
            try:
                await client.edit_permissions(event.chat_id, reply.sender_id, send_messages=True)
                await event.edit("**• تم فك التقييد**")
            except:
                await event.edit("**• فشل فك التقييد**")
    
    @client.on(events.NewMessage(pattern='.تهكير'))
    async def hack_cmd(event):
        if event.is_reply:
            reply = await event.get_reply_message()
            user = await client.get_entity(reply.sender_id)
            target_name = user.first_name
        else:
            target_name = "الضحية"
        
        await event.edit("**جاري الاتصال بسيرفرات التهكير...**")
        await asyncio.sleep(1.5)
        await event.edit("**تم الاتصال بالسيرفر successfully**")
        await asyncio.sleep(1)
        await event.edit(f"**جاري تحديد عنوان IP الخاص بـ {target_name}...**")
        await asyncio.sleep(2)
        await event.edit(f"**تم تحديد العنوان: 192.168.{random.randint(1,255)}.{random.randint(1,255)}**")
        await asyncio.sleep(1.5)
        await event.edit("**جاري فتح المنافذ والتسلل إلى جهاز الضحية...**")
        await asyncio.sleep(2)
        await event.edit("**تم تجاوز جدار الحماية بنجاح**")
        await asyncio.sleep(1.5)
        await event.edit("**جاري استخراج بيانات الحساب...**")
        await asyncio.sleep(2)
        await event.edit("**تم استخراج البيانات بنجاح**")
        await asyncio.sleep(1)
        await event.edit("**جاري تحميل الصور والملفات...**")
        await asyncio.sleep(2)
        await event.edit(f"**تم تحميل {random.randint(50,500)} صورة و {random.randint(10,100)} ملف**")
        await asyncio.sleep(1.5)
        await event.edit("**جاري استخراج جهات الاتصال...**")
        await asyncio.sleep(2)
        await event.edit(f"**تم استخراج {random.randint(100,1000)} جهة اتصال**")
        await asyncio.sleep(1)
        await event.edit("**جاري تثبيت برنامج تجسس على جهاز الضحية...**")
        await asyncio.sleep(2.5)
        await event.edit("**تم تثبيت برنامج التجسس بنجاح**")
        await asyncio.sleep(1.5)
        await event.edit(f"**تمت السيطرة الكاملة على حساب {target_name}**\n**تم التهكير بنجاح**")
    
    @client.on(events.NewMessage(pattern='.سجل'))
    async def save_cmd(event):
        save_deleted[phone] = True
        await event.edit("**• يتم تسجيل حذف الرسائل**")
    
    @client.on(events.NewMessage(pattern='.الغاء سجل'))
    async def stop_save_cmd(event):
        save_deleted[phone] = False
        await event.edit("**• تم تعطيل تسجيل الرسائل**")
    
    @client.on(events.NewMessage(pattern=r'\.اسم (.+)'))
    async def name_cmd(event):
        new_name = event.pattern_match.group(1).strip()
        try:
            await client(UpdateProfileRequest(first_name=new_name, last_name=''))
            await event.edit("**• تم تغيير الاسم**")
        except Exception as e:
            await event.edit(f"**• فشل تغيير الاسم**")
    
    @client.on(events.NewMessage(pattern=r'\.بايو (.+)'))
    async def bio_cmd(event):
        new_bio = event.pattern_match.group(1).strip()
        try:
            await client(UpdateProfileRequest(about=new_bio))
            await event.edit("**• تم تغيير البايو**")
        except Exception as e:
            await event.edit(f"**• فشل تغيير البايو**")
    
    @client.on(events.NewMessage(pattern='.خط عريض'))
    async def bold_cmd(event):
        bold_mode[phone] = True
        await event.edit("**• تم تفعيل الخط العريض**")
    
    @client.on(events.NewMessage(pattern='.الغاء خط'))
    async def stop_bold_cmd(event):
        bold_mode[phone] = False
        await event.edit("**• تم الغاء الخط العريض**")

def start_main_loop():
    asyncio.set_event_loop(main_loop)
    main_loop.run_until_complete(load_all_sessions())
    asyncio.ensure_future(auto_save_sessions_loop(), loop=main_loop)
    main_loop.run_forever()

loop_thread = threading.Thread(target=start_main_loop, daemon=True)
loop_thread.start()

@app.route('/')
def home():
    html = """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>qgram-bot - Telegram UserBot</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            body { background: linear-gradient(135deg, #1e3a8a, #3b82f6); }
            .card { background: rgba(255,255,255,0.95); }
        </style>
    </head>
    <body class="min-h-screen flex items-center justify-center p-4">
        <div class="max-w-lg w-full">
            <div class="card rounded-3xl shadow-2xl p-8">
                <div class="text-center mb-8">
                    <h1 class="text-4xl font-bold text-blue-700 mb-2">qgram-bot</h1>
                    <p class="text-gray-600">Telegram UserBot</p>
                </div>

                <div id="form-section">
                    <div id="step1">
                        <h2 class="text-2xl font-semibold mb-6 text-center">تسجيل الدخول</h2>
                        <form id="sendForm" class="space-y-5">
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">API ID</label>
                                <input type="text" name="api_id" id="api_id" placeholder="12345678" required
                                       class="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:border-blue-500">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">API HASH</label>
                                <input type="text" name="api_hash" id="api_hash" placeholder="0123456789abcdef..." required
                                       class="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:border-blue-500">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">رقم الهاتف</label>
                                <input type="text" name="phone" id="phone" placeholder="+201234567890" required
                                       class="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:border-blue-500">
                            </div>
                            <button type="submit"
                                    class="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-4 rounded-2xl transition">
                                إرسال كود التحقق
                            </button>
                        </form>
                    </div>

                    <div id="step2" class="hidden">
                        <h2 class="text-2xl font-semibold mb-6 text-center">أدخل كود التحقق</h2>
                        <form id="verifyForm" class="space-y-5">
                            <input type="hidden" name="phone" id="verify_phone">
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">كود التحقق</label>
                                <input type="text" name="code" id="code" placeholder="12345" required maxlength="5"
                                       class="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:border-blue-500 text-center text-2xl tracking-widest">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">كلمة مرور الـ 2FA (اختياري)</label>
                                <input type="password" name="password" id="password" placeholder="••••••••"
                                       class="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:border-blue-500">
                            </div>
                            <button type="submit"
                                    class="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-4 rounded-2xl transition">
                                تفعيل اليوزربوت
                            </button>
                        </form>
                        <button onclick="backToStep1()" 
                                class="mt-4 w-full text-gray-500 hover:text-gray-700">← العودة</button>
                    </div>
                </div>

                <div id="result" class="mt-6 text-center hidden"></div>
            </div>
            
            <div class="text-center mt-6">
                <a href="/api/status" class="text-white hover:underline">عرض الحالة</a>
            </div>
        </div>

        <script>
            async function showResult(message, isSuccess) {
                const resultDiv = document.getElementById('result');
                resultDiv.className = `mt-6 p-4 rounded-2xl text-center font-medium ${isSuccess ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`;
                resultDiv.innerHTML = message;
                resultDiv.classList.remove('hidden');
            }

            document.getElementById('sendForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                
                try {
                    const res = await fetch('/api/send_code', { method: 'POST', body: formData });
                    const data = await res.json();

                    if (data.status === 'code_sent') {
                        document.getElementById('verify_phone').value = formData.get('phone');
                        document.getElementById('step1').classList.add('hidden');
                        document.getElementById('step2').classList.remove('hidden');
                        showResult(data.message, true);
                    } else {
                        showResult(data.message || data.error || 'حدث خطأ', false);
                    }
                } catch (error) {
                    showResult('حدث خطأ في الاتصال بالخادم', false);
                }
            });

            document.getElementById('verifyForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                
                try {
                    const res = await fetch('/api/verify', { method: 'POST', body: formData });
                    const data = await res.json();

                    if (data.status === 'success') {
                        showResult(data.message, true);
                        setTimeout(() => location.reload(), 3000);
                    } else {
                        showResult(data.message || 'فشل التفعيل', false);
                    }
                } catch (error) {
                    showResult('حدث خطأ في الاتصال بالخادم', false);
                }
            });

            function backToStep1() {
                document.getElementById('step1').classList.remove('hidden');
                document.getElementById('step2').classList.add('hidden');
                document.getElementById('result').classList.add('hidden');
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
        api_id = int(request.form.get('api_id'))
        api_hash = request.form.get('api_hash')
        phone = request.form.get('phone', '').strip()

        if not api_id or not api_hash or not phone:
            return jsonify({"status": "error", "message": "يجب ملء جميع الحقول"}), 400

        api_configs_storage[phone] = {
            'api_id': api_id,
            'api_hash': api_hash
        }

        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()

        if await client.is_user_authorized():
            active_clients[phone] = client
            start_client_in_background(client, phone)
            await save_all_sessions()
            return jsonify({"status": "already_active", "message": "البوت مفعل بالفعل"})

        sent = await client.send_code_request(phone)
        pending_logins[phone] = (client, sent.phone_code_hash, api_id, api_hash)

        return jsonify({
            "status": "code_sent",
            "message": "تم إرسال كود التحقق إلى حسابك على تيليجرام"
        })

    except Exception as e:
        logger.error(f"Error in send_code: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/verify', methods=['POST'])
@async_route
async def verify():
    phone = request.form.get('phone', '').strip()
    code = request.form.get('code', '').strip()
    password = request.form.get('password')

    if not phone or not code or phone not in pending_logins:
        return jsonify({"status": "error", "message": "بيانات غير صحيحة"}), 400

    client, phone_code_hash, api_id, api_hash = pending_logins[phone]

    try:
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
        except SessionPasswordNeededError:
            if not password:
                return jsonify({
                    "status": "error", 
                    "message": "مطلوب كلمة مرور التحقق بخطوتين"
                }), 401
            await client.sign_in(password=password)
        
        active_clients[phone] = client
        del pending_logins[phone]
        
        await save_all_sessions()
        start_client_in_background(client, phone)
        
        return jsonify({
            "status": "success",
            "message": "تم تفعيل اليوزربوت بنجاح"
        })
        
    except Exception as e:
        logger.error(f"Error in verify: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/status')
def status():
    logger.info(f"Status: {len(active_clients)} active bots")
    return jsonify({
        "active_bots": list(active_clients.keys()),
        "pending": list(pending_logins.keys()),
        "total_active": len(active_clients)
    })

@app.route('/api/disconnect/<phone>', methods=['POST'])
@async_route
async def disconnect(phone):
    if phone in active_clients:
        client = active_clients[phone]
        await client.disconnect()
        del active_clients[phone]
        await save_all_sessions()
        return jsonify({"status": "success", "message": f"تم فصل {phone}"})
    return jsonify({"status": "error", "message": "العميل غير موجود"}), 404

@app.route('/api/save_all', methods=['POST'])
@async_route
async def force_save():
    await save_all_sessions()
    return jsonify({"status": "success", "message": f"تم حفظ {len(active_clients)} جلسة"})

if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("Application starting...")
    logger.info(f"Volume directory: {DATA_DIR}")
    logger.info(f"Volume exists: {os.path.exists(DATA_DIR)}")
    logger.info("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
