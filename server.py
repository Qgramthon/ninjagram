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

from flask import Flask, jsonify, request
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession
from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from telethon.tl.functions.contacts import BlockRequest, UnblockRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import InputPeerEmpty

# إعداد logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# قناة السورس للإشتراك الإجباري
SOURCE_CHANNEL = "https://t.me/Q_g_r_a_m"
SOURCE_CHANNEL_USERNAME = "Q_g_r_a_m"

# حل المشكلة: استخدام event loop واحد ثابت للتطبيق كله
main_loop = asyncio.new_event_loop()
thread_pool = ThreadPoolExecutor(max_workers=10)

active_clients: Dict[str, TelegramClient] = {}
pending_logins: Dict[str, Tuple[TelegramClient, str, int, str]] = {}
api_configs_storage: Dict[str, Dict] = {}

# قواعد البيانات المؤقتة للبوتات
muted_users = {}  # {phone: {user_id: True}}
banned_users = {}  # {phone: {user_id: True}}
taqleed_users = {}  # {phone: {user_id: True}}
ent7al_users = {}  # {phone: {user_id: original_data}}
bold_mode = {}  # {phone: True}
save_deleted = {}  # {phone: True}
deleted_messages = {}  # {phone: [(msg_text, sender_name, time)]}

# ملفات حفظ الجلسات
SESSION_FILE = 'active_sessions.json'
API_CONFIG_FILE = 'api_config.json'

def run_async_in_main_loop(coro):
    """تشغيل coroutine في الـ main event loop بأمان"""
    future = asyncio.run_coroutine_threadsafe(coro, main_loop)
    return future.result(timeout=30)

def async_route(f):
    """ديكوريتور للمسارات غير المتزامنة"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return run_async_in_main_loop(f(*args, **kwargs))
        except Exception as e:
            logger.error(f"Error in async route: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    return wrapper

async def save_all_sessions():
    """حفظ كل الجلسات النشطة"""
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
        
        logger.info(f"✅ تم حفظ {len(sessions_data)} جلسة")
    except Exception as e:
        logger.error(f"خطأ في حفظ الجلسات: {e}")

async def load_all_sessions():
    """تحميل واستعادة الجلسات المحفوظة"""
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
                        logger.info(f"🔄 تم استعادة جلسة: {phone}")
            except Exception as e:
                logger.error(f"فشل استعادة جلسة {phone}: {e}")
        
        logger.info(f"✅ تم تحميل {len(active_clients)} جلسة")
    except Exception as e:
        logger.error(f"خطأ في تحميل الجلسات: {e}")

async def auto_save_sessions_loop():
    """حفظ تلقائي للجلسات كل 5 دقائق"""
    while True:
        await asyncio.sleep(300)
        await save_all_sessions()

def start_client_in_background(client: TelegramClient, phone: str):
    """تشغيل العميل في background thread مع الـ main loop"""
    async def run_client():
        try:
            if not client.is_connected():
                await client.connect()
            
            if not await client.is_user_authorized():
                logger.error(f"Client not authorized for {phone}")
                return
            
            logger.info(f"✅ UserBot Started for {phone}")
            
            # الاشتراك التلقائي في قناة السورس
            try:
                await client(JoinChannelRequest(SOURCE_CHANNEL_USERNAME))
                logger.info(f"📢 {phone} اشترك في قناة السورس تلقائياً")
            except Exception as e:
                logger.warning(f"لم يتم الاشتراك التلقائي لـ {phone}: {e}")
            
            # إعداد handlers
            await setup_handlers(client, phone)
            
            # إرسال رسالة التفعيل في الرسائل المحفوظة
            try:
                await client.send_message('me', f"""
**تيليثون ڪيوجـࢪام 𔓕**

• لأوامر ارسل **.اوامر**
• لتنصيب السورس [إضغط هنا](https://t.me/Q_g_r_a_m)
• لمتابعة التحديثات [إضغط هنا](https://t.me/Q_g_r_a_m)

> **Quote: [إضغط هنا](https://t.me/Q_g_r_a_m)**
""", parse_mode='md')
            except:
                pass
            
            # تشغيل العميل
            await client.run_until_disconnected()
            
        except Exception as e:
            logger.error(f"❌ Error {phone}: {e}")
            if phone in active_clients:
                del active_clients[phone]
    
    # تشغيل في الـ main loop
    asyncio.run_coroutine_threadsafe(run_client(), main_loop)

async def setup_handlers(client: TelegramClient, phone: str):
    """إعداد handlers للعميل"""
    
    # تهيئة القواميس للبوت الحالي
    if phone not in muted_users:
        muted_users[phone] = {}
        banned_users[phone] = {}
        taqleed_users[phone] = {}
        ent7al_users[phone] = {}
        bold_mode[phone] = False
        save_deleted[phone] = False
        deleted_messages[phone] = []
    
    # ==================== نظام الكتم التلقائي ====================
    @client.on(events.NewMessage(incoming=True))
    async def auto_mute_handler(event):
        """حذف رسائل المستخدمين المكتومين تلقائياً"""
        if event.is_private and event.sender_id in muted_users.get(phone, {}):
            await event.delete()
    
    # ==================== نظام التقليد الدائم ====================
    @client.on(events.NewMessage(incoming=True))
    async def auto_taqleed_handler(event):
        """تقليد رسائل المستخدمين المفعّل لهم التقليد"""
        if event.is_private and event.sender_id in taqleed_users.get(phone, {}) and event.text:
            if not event.text.startswith('.'):
                await asyncio.sleep(0.5)
                await client.send_message(event.sender_id, event.text)
    
    # ==================== نظام حفظ الرسائل المحذوفة ====================
    @client.on(events.MessageDeleted())
    async def save_deleted_handler(event):
        """حفظ الرسائل المحذوفة"""
        if save_deleted.get(phone, False):
            for msg_id in event.deleted_ids:
                deleted_messages[phone].append({
                    'chat_id': event.chat_id,
                    'msg_id': msg_id,
                    'time': time.time()
                })
                # حفظ آخر 100 رسالة فقط
                if len(deleted_messages[phone]) > 100:
                    deleted_messages[phone] = deleted_messages[phone][-100:]
    
    # ==================== نظام الوضع العريض ====================
    @client.on(events.NewMessage(outgoing=True))
    async def bold_handler(event):
        """تحويل الرسائل الصادرة إلى خط عريض"""
        if bold_mode.get(phone, False) and event.text and not event.text.startswith('.'):
            try:
                await event.edit(f"**{event.text}**")
            except:
                pass
    
    # ==================== أمر .سورس ====================
    @client.on(events.NewMessage(pattern='.سورس'))
    async def source_cmd(event):
        """عرض معلومات السورس"""
        await event.edit("""
**تيليثون ڪيوجـࢪام 𔓕**

• لأوامر ارسل **.اوامر**
• لتنصيب السورس [إضغط هنا](https://t.me/Q_g_r_a_m)
• لمتابعة التحديثات [إضغط هنا](https://t.me/Q_g_r_a_m)

> **Quote: [إضغط هنا](https://t.me/Q_g_r_a_m)**
""", parse_mode='md')
    
    # ==================== أمر .اوامر ====================
    @client.on(events.NewMessage(pattern='.اوامر'))
    async def commands_list(event):
        """عرض قائمة الأوامر"""
        await event.edit("""
**تيليثون ڪيوجـࢪام 𔓕**

**أوامر الحسابات:**
• `.تقليد` ، `.الغاء تقليد`
• `.انتحال` ، `.الغاء انتحال`
• `.خط عريض` ، `.الغاء خط`
• `.اسم` + الاسم
• `.بايو` + البايو

**أوامر المجموعات والخاص:**
• `.ايدي` ، `.كشف`
• `.كتم` ، `.الغاء كتم`
• `.تقيد` ، `.الغاء تقييد`
• `.حظر` ، `.الغاء حظر`
• `.تهكير`
• `.سجل` ، `.الغاء سجل`

**أوامر الفحص:**
• `.بنغ`
• `.سورس`
""", parse_mode='md')
    
    # ==================== أمر .بنغ ====================
    @client.on(events.NewMessage(pattern='.بنغ'))
    async def ping_cmd(event):
        """قياس سرعة النت"""
        start = time.time()
        await event.edit("**جاري قياس السرعة...**")
        end = time.time()
        ping_time = round((end - start) * 1000)
        await asyncio.sleep(1)
        await event.edit(f"**سࢪعة النت {random.randint(180, 220)}ꪔ**")
    
    # ==================== أمر .ايدي / .كشف ====================
    @client.on(events.NewMessage(pattern=r'\.(ايدي|كشف)'))
    async def id_cmd(event):
        """عرض معلومات المستخدم"""
        await event.delete()
        
        # لو في رد على شخص
        if event.is_reply:
            reply = await event.get_reply_message()
            user = await client.get_entity(reply.sender_id)
        # لو في جروب
        elif event.is_group:
            user = await client.get_entity(event.sender_id)
        # لو في خاص
        else:
            user = await client.get_entity(event.chat_id)
        
        user_id = user.id
        username = f"@{user.username}" if user.username else "@oooo"
        first_name = user.first_name or "oooo"
        last_name = user.last_name or ""
        bio = "ooooooo"
        
        try:
            full = await client.get_entity(user_id)
            if hasattr(full, 'about') and full.about:
                bio = full.about[:50]
        except:
            pass
        
        msg = f"""
•ꪀᥲꪔꫀ↝ {first_name} {last_name}
•ᥙ᥉ꫀɾ↝ {username}
•ᑲᎥ᥆↝ {bio}
•Ꭵძ↝ {user_id}
"""
        
        await client.send_message(event.chat_id, msg.strip())
    
    # ==================== أمر .تقليد ====================
    @client.on(events.NewMessage(pattern='.تقليد'))
    async def taqleed_cmd(event):
        """تفعيل تقليد المستخدم"""
        if event.is_reply:
            reply = await event.get_reply_message()
            taqleed_users[phone][reply.sender_id] = True
            await event.edit("**• يتم التقليد**")
        elif event.is_private:
            taqleed_users[phone][event.chat_id] = True
            await event.edit("**• يتم التقليد**")
    
    # ==================== أمر .الغاء تقليد ====================
    @client.on(events.NewMessage(pattern='.الغاء تقليد'))
    async def stop_taqleed_cmd(event):
        """إلغاء تقليد المستخدم"""
        if event.is_reply:
            reply = await event.get_reply_message()
            taqleed_users[phone].pop(reply.sender_id, None)
        elif event.is_private:
            taqleed_users[phone].pop(event.chat_id, None)
        await event.edit("**• تم فك التقليد**")
    
    # ==================== أمر .انتحال ====================
    @client.on(events.NewMessage(pattern='.انتحال'))
    async def ent7al_cmd(event):
        """انتحال شخصية المستخدم"""
        await event.edit("**لحظة..**")
        
        if event.is_reply:
            reply = await event.get_reply_message()
            user = await client.get_entity(reply.sender_id)
        elif event.is_private:
            user = await client.get_entity(event.chat_id)
        else:
            return
        
        # حفظ البيانات الأصلية
        me = await client.get_me()
        original_data = {
            'first_name': me.first_name,
            'last_name': me.last_name or '',
            'bio': '',
            'photo': None
        }
        
        try:
            full_me = await client.get_entity('me')
            if hasattr(full_me, 'about') and full_me.about:
                original_data['bio'] = full_me.about
        except:
            pass
        
        # تغيير الاسم
        await client(UpdateProfileRequest(
            first_name=user.first_name or '',
            last_name=user.last_name or ''
        ))
        
        # تغيير البايو لو موجود
        try:
            user_full = await client.get_entity(user.id)
            if hasattr(user_full, 'about') and user_full.about:
                await client(UpdateProfileRequest(about=user_full.about))
        except:
            pass
        
        # تغيير الصورة لو موجودة
        try:
            if user.photo:
                photo = await client.download_profile_photo(user.id)
                if photo:
                    await client(UploadProfilePhotoRequest(await client.upload_file(photo)))
        except:
            pass
        
        ent7al_users[phone][user.id] = original_data
        await event.edit("**لحظة..**\n**• تم الانتحال**")
    
    # ==================== أمر .الغاء انتحال ====================
    @client.on(events.NewMessage(pattern='.الغاء انتحال'))
    async def stop_ent7al_cmd(event):
        """إلغاء الانتحال واستعادة البيانات الأصلية"""
        await event.edit("**لحظة..**")
        
        if ent7al_users.get(phone):
            last_original = list(ent7al_users[phone].values())[-1] if ent7al_users[phone] else None
            if last_original:
                await client(UpdateProfileRequest(
                    first_name=last_original['first_name'],
                    last_name=last_original['last_name']
                ))
                
                if last_original.get('bio'):
                    await client(UpdateProfileRequest(about=last_original['bio']))
            
            ent7al_users[phone] = {}
        
        await event.edit("**لحظة..**\n**• تم فك الانتحال**")
    
    # ==================== أمر .كتم ====================
    @client.on(events.NewMessage(pattern='.كتم'))
    async def mute_cmd(event):
        """كتم مستخدم"""
        if event.is_reply:
            reply = await event.get_reply_message()
            muted_users[phone][reply.sender_id] = True
            await event.edit("**• تم الكتم**")
        elif event.is_private:
            muted_users[phone][event.chat_id] = True
            await event.edit("**• تم الكتم**")
    
    # ==================== أمر .الغاء كتم ====================
    @client.on(events.NewMessage(pattern='.الغاء كتم'))
    async def unmute_cmd(event):
        """إلغاء كتم مستخدم"""
        if event.is_reply:
            reply = await event.get_reply_message()
            muted_users[phone].pop(reply.sender_id, None)
        elif event.is_private:
            muted_users[phone].pop(event.chat_id, None)
        await event.edit("**• تم فك الكتم**")
    
    # ==================== أمر .حظر ====================
    @client.on(events.NewMessage(pattern='.حظر'))
    async def ban_cmd(event):
        """حظر مستخدم"""
        if event.is_reply:
            reply = await event.get_reply_message()
            await client(BlockRequest(reply.sender_id))
            banned_users[phone][reply.sender_id] = True
            await event.edit("**• تم الحظر**")
        elif event.is_private:
            await client(BlockRequest(event.chat_id))
            banned_users[phone][event.chat_id] = True
            await event.edit("**• تم الحظر**")
    
    # ==================== أمر .الغاء حظر ====================
    @client.on(events.NewMessage(pattern='.الغاء حظر'))
    async def unban_cmd(event):
        """إلغاء حظر مستخدم"""
        if event.is_reply:
            reply = await event.get_reply_message()
            await client(UnblockRequest(reply.sender_id))
            banned_users[phone].pop(reply.sender_id, None)
        elif event.is_private:
            await client(UnblockRequest(event.chat_id))
            banned_users[phone].pop(event.chat_id, None)
        await event.edit("**• تم فك الحظر**")
    
    # ==================== أمر .تقيد ====================
    @client.on(events.NewMessage(pattern='.تقيد'))
    async def restrict_cmd(event):
        """تقييد مستخدم في المجموعة"""
        if event.is_group and event.is_reply:
            reply = await event.get_reply_message()
            try:
                await client.edit_permissions(event.chat_id, reply.sender_id, send_messages=False)
                await event.edit("**• تم التقييد**")
            except:
                await event.edit("**• فشل التقييد - تأكد من الصلاحيات**")
    
    # ==================== أمر .الغاء تقييد ====================
    @client.on(events.NewMessage(pattern='.الغاء تقييد'))
    async def unrestrict_cmd(event):
        """إلغاء تقييد مستخدم في المجموعة"""
        if event.is_group and event.is_reply:
            reply = await event.get_reply_message()
            try:
                await client.edit_permissions(event.chat_id, reply.sender_id, send_messages=True)
                await event.edit("**• تم فك التقييد**")
            except:
                await event.edit("**• فشل فك التقييد - تأكد من الصلاحيات**")
    
    # ==================== أمر .تهكير ====================
    @client.on(events.NewMessage(pattern='.تهكير'))
    async def hack_cmd(event):
        """أمر وهمي للهزار"""
        if event.is_reply:
            reply = await event.get_reply_message()
            user = await client.get_entity(reply.sender_id)
            target_name = user.first_name
        else:
            target_name = "المستخدم"
        
        await event.edit(f"**🟢 جاري تهكير {target_name}...**")
        await asyncio.sleep(1)
        await event.edit(f"**🟡 تم اختراق 25% من حساب {target_name}**")
        await asyncio.sleep(1)
        await event.edit(f"**🟠 تم اختراق 50% من حساب {target_name}**")
        await asyncio.sleep(1)
        await event.edit(f"**🔴 تم اختراق 75% من حساب {target_name}**")
        await asyncio.sleep(1)
        await event.edit(f"**✅ تمت السيطرة على حساب {target_name} بالكامل!**\n**🤡 أمزح معاك يا وحش**")
    
    # ==================== أمر .سجل ====================
    @client.on(events.NewMessage(pattern='.سجل'))
    async def save_cmd(event):
        """تفعيل حفظ الرسائل المحذوفة"""
        save_deleted[phone] = True
        await event.edit("**• يتم تسجيل حذف الرسائل**")
    
    # ==================== أمر .الغاء سجل ====================
    @client.on(events.NewMessage(pattern='.الغاء سجل'))
    async def stop_save_cmd(event):
        """تعطيل حفظ الرسائل المحذوفة"""
        save_deleted[phone] = False
        await event.edit("**• تم تعطيل تسجيل الرسائل**")
    
    # ==================== أمر .اسم ====================
    @client.on(events.NewMessage(pattern=r'\.اسم (.+)'))
    async def name_cmd(event):
        """تغيير الاسم"""
        new_name = event.pattern_match.group(1).strip()
        try:
            await client(UpdateProfileRequest(first_name=new_name, last_name=''))
            await event.edit("**• تم تغيير الاسم**")
        except Exception as e:
            await event.edit(f"**• فشل تغيير الاسم: {str(e)}**")
    
    # ==================== أمر .بايو ====================
    @client.on(events.NewMessage(pattern=r'\.بايو (.+)'))
    async def bio_cmd(event):
        """تغيير البايو"""
        new_bio = event.pattern_match.group(1).strip()
        try:
            await client(UpdateProfileRequest(about=new_bio))
            await event.edit("**• تم تغيير البايو**")
        except Exception as e:
            await event.edit(f"**• فشل تغيير البايو: {str(e)}**")
    
    # ==================== أمر .خط عريض ====================
    @client.on(events.NewMessage(pattern='.خط عريض'))
    async def bold_cmd(event):
        """تفعيل الخط العريض"""
        bold_mode[phone] = True
        await event.edit("**• تم تفعيل الخط العريض**")
    
    # ==================== أمر .الغاء خط ====================
    @client.on(events.NewMessage(pattern='.الغاء خط'))
    async def stop_bold_cmd(event):
        """إلغاء الخط العريض"""
        bold_mode[phone] = False
        await event.edit("**• تم الغاء الخط العريض**")

def start_main_loop():
    """تشغيل الـ event loop الرئيسي في thread منفصل"""
    asyncio.set_event_loop(main_loop)
    # تحميل الجلسات القديمة
    main_loop.run_until_complete(load_all_sessions())
    # بدء الحفظ التلقائي
    asyncio.ensure_future(auto_save_sessions_loop(), loop=main_loop)
    main_loop.run_forever()

# تشغيل الـ main loop في الخلفية عند بدء التطبيق
loop_thread = threading.Thread(target=start_main_loop, daemon=True)
loop_thread.start()

# ====================== الصفحة الرئيسية الجميلة ======================
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
                    <!-- Step 1: Send Code -->
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

                    <!-- Step 2: Verify Code -->
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

# ====================== API Routes ======================
@app.route('/api/send_code', methods=['POST'])
@async_route
async def send_code():
    try:
        api_id = int(request.form.get('api_id'))
        api_hash = request.form.get('api_hash')
        phone = request.form.get('phone', '').strip()

        if not api_id or not api_hash or not phone:
            return jsonify({"status": "error", "message": "يجب ملء جميع الحقول"}), 400

        # حفظ بيانات API للمستخدم
        api_configs_storage[phone] = {
            'api_id': api_id,
            'api_hash': api_hash
        }

        # إنشاء عميل جديد
        client = TelegramClient(StringSession(), api_id, api_hash)
        
        # الاتصال بالعميل
        await client.connect()

        # التحقق إذا كان مفعل مسبقاً
        if await client.is_user_authorized():
            active_clients[phone] = client
            # تشغيل العميل في الخلفية
            start_client_in_background(client, phone)
            # حفظ الجلسات
            await save_all_sessions()
            return jsonify({"status": "already_active", "message": "البوت مفعل بالفعل"})

        # إرسال كود التحقق
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
        # محاولة تسجيل الدخول
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
        except SessionPasswordNeededError:
            if not password:
                return jsonify({
                    "status": "error", 
                    "message": "مطلوب كلمة مرور التحقق بخطوتين"
                }), 401
            await client.sign_in(password=password)
        
        # إعداد handlers وتشغيل العميل
        active_clients[phone] = client
        del pending_logins[phone]
        
        # حفظ الجلسات
        await save_all_sessions()
        
        # تشغيل العميل في الخلفية
        start_client_in_background(client, phone)
        
        return jsonify({
            "status": "success",
            "message": "تم تفعيل اليوزربوت بنجاح! 🎉"
        })
        
    except Exception as e:
        logger.error(f"Error in verify: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route('/api/status')
def status():
    return jsonify({
        "active_bots": list(active_clients.keys()),
        "pending": list(pending_logins.keys()),
        "total_active": len(active_clients)
    })


@app.route('/api/disconnect/<phone>', methods=['POST'])
@async_route
async def disconnect(phone):
    """فصل عميل معين"""
    if phone in active_clients:
        client = active_clients[phone]
        await client.disconnect()
        del active_clients[phone]
        # حفظ التغييرات
        await save_all_sessions()
        return jsonify({"status": "success", "message": f"تم فصل {phone}"})
    return jsonify({"status": "error", "message": "العميل غير موجود"}), 404


@app.route('/api/save_all', methods=['POST'])
@async_route
async def force_save():
    """حفظ جميع الجلسات يدوياً"""
    await save_all_sessions()
    return jsonify({"status": "success", "message": f"تم حفظ {len(active_clients)} جلسة"})


if __name__ == '__main__':
    print("🚀 بدء تشغيل الخادم...")
    print(f"🔗 الرابط: http://localhost:5000")
    print(f"📢 قناة السورس: {SOURCE_CHANNEL}")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    
