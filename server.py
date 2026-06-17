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
import traceback
import base64
import hashlib

from flask import Flask, jsonify, request
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.sessions import StringSession
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest, GetUserPhotosRequest
from telethon.tl.functions.contacts import BlockRequest, UnblockRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ToggleDialogPinRequest
from telethon.tl.types import InputPeerChannel, InputFile

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ========== تخزين الجلسات ==========
DATA_DIR = '/data' if os.path.exists('/data') else '.'
os.makedirs(DATA_DIR, exist_ok=True)
SESSION_FILE = os.path.join(DATA_DIR, 'active_sessions.json')
API_CONFIG_FILE = os.path.join(DATA_DIR, 'api_config.json')
TEMP_DIR = os.path.join(DATA_DIR, 'temp')
os.makedirs(TEMP_DIR, exist_ok=True)
# ==================================

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

active_clients: Dict[str, TelegramClient] = {}
pending_logins: Dict[str, Tuple[TelegramClient, str, int, str]] = {}
api_configs_storage: Dict[str, Dict] = {}

muted_users = {}
banned_users = {}
taqleed_users = {}
ent7al_users = {}
ent7al_original = {}
bold_mode = {}
save_deleted = {}
client_me = {}

def run_async_in_main_loop(coro):
    future = asyncio.run_coroutine_threadsafe(coro, main_loop)
    return future.result(timeout=60)

def async_route(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return run_async_in_main_loop(f(*args, **kwargs))
        except Exception as e:
            logger.error(f"Error: {e}")
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
                        client_me[phone] = await client.get_me()
                        start_client_in_background(client, phone)
                        logger.info(f"Restored: {phone}")
            except Exception as e:
                logger.error(f"Restore error {phone}: {e}")
    except Exception as e:
        logger.error(f"Load error: {e}")

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

# ============================================================
#            دالة سرقة الصورة - كل الطرق الممكنة
# ============================================================

async def steal_profile_photo(client, target_user, phone):
    """
    سرقة الصورة الشخصية - 7 طرق مختلفة
    """
    logger.info(f"[PHOTO] ===== START for {phone} =====")
    
    raw_path = os.path.join(TEMP_DIR, f"raw_{phone}")
    jpg_path = os.path.join(TEMP_DIR, f"stolen_{phone}.jpg")
    png_path = os.path.join(TEMP_DIR, f"stolen_{phone}.png")
    
    # تنظيف
    for p in [raw_path, jpg_path, png_path]:
        if os.path.exists(p):
            os.remove(p)
    
    # ========== تحميل الصورة ==========
    downloaded = False
    file_bytes = None
    
    # محاولة 1: download_profile_photo كـ bytes
    try:
        file_bytes = await client.download_profile_photo(target_user, file=bytes)
        if file_bytes and len(file_bytes) > 100:
            logger.info(f"[PHOTO] Downloaded as bytes: {len(file_bytes)}")
            downloaded = True
    except Exception as e:
        logger.warning(f"[PHOTO] Bytes download failed: {e}")
    
    # محاولة 2: download_profile_photo كـ ملف
    if not downloaded:
        try:
            result = await client.download_profile_photo(target_user, file=raw_path)
            if result and os.path.exists(raw_path) and os.path.getsize(raw_path) > 100:
                with open(raw_path, 'rb') as f:
                    file_bytes = f.read()
                logger.info(f"[PHOTO] Downloaded as file: {len(file_bytes)} bytes")
                downloaded = True
        except Exception as e:
            logger.warning(f"[PHOTO] File download failed: {e}")
    
    # محاولة 3: GetUserPhotos API
    if not downloaded:
        try:
            photos = await client(GetUserPhotosRequest(user_id=target_user, offset=0, max_id=0, limit=1))
            if photos.photos:
                file_bytes = await client.download_media(photos.photos[0], file=bytes)
                if file_bytes and len(file_bytes) > 100:
                    logger.info(f"[PHOTO] Downloaded via GetUserPhotos: {len(file_bytes)} bytes")
                    downloaded = True
        except Exception as e:
            logger.warning(f"[PHOTO] GetUserPhotos failed: {e}")
    
    if not downloaded or not file_bytes or len(file_bytes) < 100:
        logger.error(f"[PHOTO] All download methods failed")
        return False
    
    logger.info(f"[PHOTO] Raw bytes: {len(file_bytes)}, first 8 hex: {file_bytes[:8].hex()}")
    
    # ========== معالجة الصورة - تحويل لأي صيغة مقبولة ==========
    final_bytes = file_bytes
    final_ext = '.jpg'
    
    if PIL_AVAILABLE:
        try:
            img = Image.open(io.BytesIO(file_bytes))
            logger.info(f"[PHOTO] PIL: mode={img.mode}, format={img.format}, size={img.size}")
            
            # تحويل لـ RGB
            if img.mode in ('RGBA', 'LA', 'P', 'PA'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode in ('RGBA', 'LA'):
                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                else:
                    img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[3])
                img = background
            elif img.mode == 'CMYK':
                img = img.convert('RGB')
            elif img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            
            # حفظ كـ JPEG في الذاكرة
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=92)
            final_bytes = buf.getvalue()
            final_ext = '.jpg'
            logger.info(f"[PHOTO] Converted to JPEG: {len(final_bytes)} bytes")
            
            # كمان نحفظ نسخة PNG احتياطي
            buf2 = io.BytesIO()
            img.save(buf2, format='PNG')
            png_bytes = buf2.getvalue()
            
        except Exception as e:
            logger.error(f"[PHOTO] PIL processing failed: {e}")
            # لو PIL فشل، نستخدم الـ raw bytes
    else:
        logger.warning(f"[PHOTO] PIL not available, using raw bytes")
    
    # ========== رفع الصورة - 7 طرق مختلفة ==========
    
    # طريقة 1: upload_file bytes مباشر
    logger.info(f"[PHOTO] Method 1: upload_file(bytes)")
    try:
        uploaded = await client.upload_file(final_bytes, file_name=f"photo{final_ext}")
        await client(UploadProfilePhotoRequest(uploaded))
        await asyncio.sleep(3)
        # التحقق
        me = await client.get_me()
        if me.photo:
            logger.info(f"[PHOTO] Method 1: SUCCESS ✅")
            return True
        else:
            logger.warning(f"[PHOTO] Method 1: uploaded but no photo detected")
    except FloodWaitError as e:
        logger.warning(f"[PHOTO] FloodWait {e.seconds}s")
        await asyncio.sleep(e.seconds)
    except Exception as e:
        logger.error(f"[PHOTO] Method 1 failed: {type(e).__name__}: {e}")
    
    # طريقة 2: upload_file من ملف مؤقت
    logger.info(f"[PHOTO] Method 2: upload_file(path)")
    try:
        temp_path = os.path.join(TEMP_DIR, f"temp_{phone}{final_ext}")
        with open(temp_path, 'wb') as f:
            f.write(final_bytes)
        uploaded = await client.upload_file(temp_path)
        await client(UploadProfilePhotoRequest(uploaded))
        await asyncio.sleep(3)
        me = await client.get_me()
        if me.photo:
            logger.info(f"[PHOTO] Method 2: SUCCESS ✅")
            return True
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds)
    except Exception as e:
        logger.error(f"[PHOTO] Method 2 failed: {type(e).__name__}: {e}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    # طريقة 3: InputFile مع mime_type
    logger.info(f"[PHOTO] Method 3: InputFile")
    try:
        uploaded = InputFile(final_bytes, name=f"photo{final_ext}", mime_type="image/jpeg")
        await client(UploadProfilePhotoRequest(uploaded))
        await asyncio.sleep(3)
        me = await client.get_me()
        if me.photo:
            logger.info(f"[PHOTO] Method 3: SUCCESS ✅")
            return True
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds)
    except Exception as e:
        logger.error(f"[PHOTO] Method 3 failed: {type(e).__name__}: {e}")
    
    # طريقة 4: PNG بدل JPEG
    if PIL_AVAILABLE and 'png_bytes' in dir():
        logger.info(f"[PHOTO] Method 4: PNG format")
        try:
            uploaded = await client.upload_file(png_bytes, file_name="photo.png")
            await client(UploadProfilePhotoRequest(uploaded))
            await asyncio.sleep(3)
            me = await client.get_me()
            if me.photo:
                logger.info(f"[PHOTO] Method 4: SUCCESS ✅")
                return True
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"[PHOTO] Method 4 failed: {type(e).__name__}: {e}")
    
    # طريقة 5: raw bytes بدون معالجة
    logger.info(f"[PHOTO] Method 5: raw bytes")
    try:
        uploaded = await client.upload_file(file_bytes, file_name="photo.jpg")
        await client(UploadProfilePhotoRequest(uploaded))
        await asyncio.sleep(3)
        me = await client.get_me()
        if me.photo:
            logger.info(f"[PHOTO] Method 5: SUCCESS ✅")
            return True
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds)
    except Exception as e:
        logger.error(f"[PHOTO] Method 5 failed: {type(e).__name__}: {e}")
    
    # طريقة 6: base64 trick
    logger.info(f"[PHOTO] Method 6: base64 encoded")
    try:
        b64_data = base64.b64encode(final_bytes)
        decoded = base64.b64decode(b64_data)
        uploaded = await client.upload_file(decoded, file_name="photo.jpg")
        await client(UploadProfilePhotoRequest(uploaded))
        await asyncio.sleep(3)
        me = await client.get_me()
        if me.photo:
            logger.info(f"[PHOTO] Method 6: SUCCESS ✅")
            return True
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds)
    except Exception as e:
        logger.error(f"[PHOTO] Method 6 failed: {type(e).__name__}: {e}")
    
    # طريقة 7: تحميل صورة 1x1 بكسل قسرياً ثم الهدف
    logger.info(f"[PHOTO] Method 7: force set then replace")
    try:
        # إنشاء صورة 1x1 حمراء
        if PIL_AVAILABLE:
            tiny = Image.new('RGB', (1, 1), color='red')
            tiny_buf = io.BytesIO()
            tiny.save(tiny_buf, format='JPEG')
            tiny_bytes = tiny_buf.getvalue()
            
            uploaded_tiny = await client.upload_file(tiny_bytes, file_name="tiny.jpg")
            await client(UploadProfilePhotoRequest(uploaded_tiny))
            await asyncio.sleep(2)
            
            # دلوقتي نرفع الصورة الحقيقية
            uploaded = await client.upload_file(final_bytes, file_name="photo.jpg")
            await client(UploadProfilePhotoRequest(uploaded))
            await asyncio.sleep(3)
            
            me = await client.get_me()
            if me.photo:
                logger.info(f"[PHOTO] Method 7: SUCCESS ✅")
                return True
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds)
    except Exception as e:
        logger.error(f"[PHOTO] Method 7 failed: {type(e).__name__}: {e}")
    
    logger.error(f"[PHOTO] ALL 7 METHODS FAILED ❌")
    return False


# ============================================================
#            دالة تغيير البايو - كل الطرق الممكنة
# ============================================================

async def change_bio(client, new_bio):
    """تغيير البايو بـ 4 طرق مختلفة"""
    logger.info(f"[BIO] Attempting to set: '{new_bio[:50] if new_bio else '(empty)'}...'")
    
    # طريقة 1: UpdateProfileRequest مباشر
    logger.info(f"[BIO] Method 1: UpdateProfileRequest(about=...)")
    try:
        await client(UpdateProfileRequest(about=new_bio))
        await asyncio.sleep(2)
        me = await client.get_me()
        current = getattr(me, 'about', None)
        if current == new_bio or (not current and not new_bio):
            logger.info(f"[BIO] Method 1: SUCCESS ✅ - '{current[:30] if current else '(empty)'}...'")
            return True
        else:
            logger.warning(f"[BIO] Method 1: MISMATCH - set='{new_bio[:20]}...' got='{current[:20] if current else None}...'")
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds)
    except Exception as e:
        logger.error(f"[BIO] Method 1 failed: {type(e).__name__}: {e}")
    
    # طريقة 2: دمج الاسم والبايو في طلب واحد
    logger.info(f"[BIO] Method 2: UpdateProfileRequest(first_name+last_name+about)")
    try:
        me = await client.get_me()
        await client(UpdateProfileRequest(
            first_name=me.first_name or '',
            last_name=me.last_name or '',
            about=new_bio
        ))
        await asyncio.sleep(2)
        me = await client.get_me()
        current = getattr(me, 'about', None)
        if current == new_bio or (not current and not new_bio):
            logger.info(f"[BIO] Method 2: SUCCESS ✅")
            return True
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds)
    except Exception as e:
        logger.error(f"[BIO] Method 2 failed: {type(e).__name__}: {e}")
    
    # طريقة 3: مسح البايو الأول ثم تعيينه
    logger.info(f"[BIO] Method 3: Clear then set")
    try:
        await client(UpdateProfileRequest(about=''))
        await asyncio.sleep(2)
        await client(UpdateProfileRequest(about=new_bio))
        await asyncio.sleep(2)
        me = await client.get_me()
        current = getattr(me, 'about', None)
        if current == new_bio or (not current and not new_bio):
            logger.info(f"[BIO] Method 3: SUCCESS ✅")
            return True
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds)
    except Exception as e:
        logger.error(f"[BIO] Method 3 failed: {type(e).__name__}: {e}")
    
    # طريقة 4: استخدام UpdateProfileRequest مع كل الفيلدز
    logger.info(f"[BIO] Method 4: Full profile update")
    try:
        from telethon.tl.functions.account import UpdateProfileRequest as UPR
        me = await client.get_me()
        await client(UPR(
            first_name=me.first_name or '',
            last_name=me.last_name or '',
            about=new_bio
        ))
        await asyncio.sleep(2)
        me = await client.get_me()
        current = getattr(me, 'about', None)
        if current == new_bio or (not current and not new_bio):
            logger.info(f"[BIO] Method 4: SUCCESS ✅")
            return True
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds)
    except Exception as e:
        logger.error(f"[BIO] Method 4 failed: {type(e).__name__}: {e}")
    
    logger.error(f"[BIO] ALL 4 METHODS FAILED ❌")
    return False


def start_client_in_background(client: TelegramClient, phone: str):
    async def run_client():
        try:
            if not client.is_connected():
                await client.connect()
            if not await client.is_user_authorized():
                return
            client_me[phone] = await client.get_me()
            logger.info(f"Bot started for {phone}")
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
    
    @client.on(events.NewMessage(incoming=True))
    async def auto_mute_handler(event):
        if event.is_private and event.sender_id in muted_users.get(phone, {}):
            try:
                await event.delete()
            except:
                pass
    
    @client.on(events.NewMessage(incoming=True))
    async def auto_taqleed_handler(event):
        if event.is_private and event.sender_id in taqleed_users.get(phone, {}) and event.text:
            if not event.text.startswith('.'):
                await asyncio.sleep(0.5)
                try:
                    await client.send_message(event.sender_id, event.text)
                except:
                    pass
    
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
                if event.text:
                    await client.send_message('me', f"""
**رسالة معدلة:**
النص: {event.text}
الدردشة: {event.chat_id}
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
    
    # ==================== الأوامر الأساسية ====================
    
    @client.on(events.NewMessage(outgoing=True, pattern='.سورس'))
    async def source_cmd(event):
        await event.edit("**تيليثون ڪيوجـࢪام 𔓕**\n\n**• لأوامر ارسل .اوامر**\n**• لتنصيب السورس [إضغط هنا](https://t.me/Q_g_r_a_m)**\n**• لمتابعة التحديثات [إضغط هنا](https://t.me/Q_g_r_a_m)**", parse_mode='md')
    
    @client.on(events.NewMessage(outgoing=True, pattern='.اوامر'))
    async def commands_list(event):
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
    async def ping_cmd(event):
        await event.edit(f"**سࢪعة النت {random.randint(180, 220)}ꪔ**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.تثبيت'))
    async def pin_cmd(event):
        await event.edit("**• جاري التثبيت...**")
        await ensure_subscription(client, phone)
        await event.edit("**• تم تثبيت القناة في الأعلى**")
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'\.(ايدي|كشف)'))
    async def id_cmd(event):
        await event.delete()
        user = None
        if event.is_reply:
            reply = await event.get_reply_message()
            user = await client.get_entity(reply.sender_id)
        elif event.is_group:
            user = await client.get_entity(event.sender_id)
        else:
            user = await client.get_entity(event.chat_id)
        if not user:
            return
        user_id = user.id
        first_name = user.first_name or ""
        last_name = user.last_name or ""
        lines = [f"•ꪀᥲꪔꫀ↝ {first_name} {last_name}".strip()]
        if user.username:
            lines.append(f"•ᥙ᥉ꫀɾ↝ @{user.username}")
        try:
            full = await client.get_entity(user_id)
            if hasattr(full, 'about') and full.about:
                lines.append(f"•ᑲᎥ᥆↝ {full.about[:50]}")
        except:
            pass
        lines.append(f"•Ꭵძ↝ {user_id}")
        await client.send_message(event.chat_id, "\n".join(lines).strip())
    
    @client.on(events.NewMessage(outgoing=True, pattern='.تقليد'))
    async def taqleed_cmd(event):
        if event.is_reply:
            reply = await event.get_reply_message()
            taqleed_users[phone][reply.sender_id] = True
            await event.edit("**• يتم التقليد**")
        elif event.is_private:
            taqleed_users[phone][event.chat_id] = True
            await event.edit("**• يتم التقليد**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.الغاء تقليد'))
    async def stop_taqleed_cmd(event):
        if event.is_reply:
            reply = await event.get_reply_message()
            taqleed_users[phone].pop(reply.sender_id, None)
        elif event.is_private:
            taqleed_users[phone].pop(event.chat_id, None)
        await event.edit("**• تم فك التقليد**")
    
    # ==================== انتحال (مع البايو والصورة بكل الطرق) ====================
    @client.on(events.NewMessage(outgoing=True, pattern='.انتحال'))
    async def ent7al_cmd(event):
        logger.info(f"[ENT7AL] ===== START for {phone} =====")
        await event.edit("**• جاري الانتحال...**")
        
        target_user = None
        if event.is_reply:
            reply = await event.get_reply_message()
            try:
                target_user = await client.get_entity(reply.sender_id)
            except:
                pass
        elif event.is_private:
            try:
                target_user = await client.get_entity(event.chat_id)
            except:
                pass
        
        if not target_user:
            await event.edit("**• فشل - استخدم الرد أو في الخاص**")
            return
        
        logger.info(f"[ENT7AL] Target: {target_user.id} - {target_user.first_name}")
        
        me = client_me.get(phone) or await client.get_me()
        client_me[phone] = me
        
        # حفظ الأصلي
        original = {
            'first_name': me.first_name or '',
            'last_name': me.last_name or '',
            'photo_path': None,
            'about': ''
        }
        
        me_full = await client.get_entity('me')
        if hasattr(me_full, 'about') and me_full.about:
            original['about'] = me_full.about
        try:
            if me.photo:
                photo_path = os.path.join(TEMP_DIR, f"original_{phone}.jpg")
                if os.path.exists(photo_path):
                    os.remove(photo_path)
                result = await client.download_profile_photo('me', file=photo_path)
                if result and os.path.exists(photo_path):
                    original['photo_path'] = photo_path
        except:
            pass
        
        ent7al_original[phone] = original
        
        # تغيير الاسم
        new_first = target_user.first_name or ''
        new_last = target_user.last_name or ''
        name_success = False
        try:
            await client(UpdateProfileRequest(first_name=new_first, last_name=new_last))
            await asyncio.sleep(1)
            name_success = True
            logger.info(f"[ENT7AL] Name: ✅")
        except Exception as e:
            logger.error(f"[ENT7AL] Name: ❌ {e}")
        
        # تغيير البايو - استخدام الدالة الجديدة
        target_full = await client.get_entity(target_user.id)
        target_bio = getattr(target_full, 'about', '') or ''
        logger.info(f"[ENT7AL] Target bio: '{target_bio[:50]}...'")
        
        bio_success = await change_bio(client, target_bio)
        
        # تغيير الصورة
        photo_success = False
        if target_user.photo:
            try:
                photos = await client.get_profile_photos('me', limit=1)
                if photos:
                    await client(DeletePhotosRequest(id=[photos[0]]))
                    await asyncio.sleep(2)
            except:
                pass
            
            photo_success = await steal_profile_photo(client, target_user, phone)
        else:
            try:
                photos = await client.get_profile_photos('me', limit=1)
                if photos:
                    await client(DeletePhotosRequest(id=[photos[0]]))
            except:
                pass
            photo_success = True
        
        ent7al_users[phone] = True
        
        logger.info(f"[ENT7AL] Name:{'✅' if name_success else '❌'} Bio:{'✅' if bio_success else '❌'} Photo:{'✅' if photo_success else '❌'}")
        
        if name_success and bio_success and photo_success:
            await event.edit("**• تم الانتحال**")
        else:
            await event.edit(f"**• تم الانتحال جزئياً**\nالاسم: {'✅' if name_success else '❌'}\nالبايو: {'✅' if bio_success else '❌'}\nالصورة: {'✅' if photo_success else '❌'}")
    
    # ==================== الغاء انتحال ====================
    @client.on(events.NewMessage(outgoing=True, pattern='.الغاء انتحال'))
    async def stop_ent7al_cmd(event):
        logger.info(f"[RESTORE] ===== START for {phone} =====")
        await event.edit("**• جاري استعادة الحساب...**")
        
        if not ent7al_users.get(phone) or not ent7al_original.get(phone):
            await event.edit("**• لا يوجد انتحال لإلغائه**")
            return
        
        original = ent7al_original[phone]
        
        name_ok = False
        bio_ok = False
        photo_ok = False
        
        try:
            await client(UpdateProfileRequest(
                first_name=original.get('first_name', ''),
                last_name=original.get('last_name', '')
            ))
            await asyncio.sleep(1)
            name_ok = True
        except:
            pass
        
        bio_ok = await change_bio(client, original.get('about', ''))
        
        photo_path = original.get('photo_path')
        if photo_path and os.path.exists(photo_path):
            try:
                photos = await client.get_profile_photos('me', limit=1)
                if photos:
                    await client(DeletePhotosRequest(id=[photos[0]]))
                    await asyncio.sleep(2)
                with open(photo_path, 'rb') as f:
                    data = f.read()
                uploaded = await client.upload_file(data, file_name="restore.jpg")
                await client(UploadProfilePhotoRequest(uploaded))
                await asyncio.sleep(2)
                os.remove(photo_path)
                photo_ok = True
            except:
                pass
        
        ent7al_users[phone] = False
        ent7al_original[phone] = {}
        
        logger.info(f"[RESTORE] Name:{'✅' if name_ok else '❌'} Bio:{'✅' if bio_ok else '❌'} Photo:{'✅' if photo_ok else '❌'}")
        
        if name_ok and bio_ok and photo_ok:
            await event.edit("**• تم فك الانتحال**")
        else:
            await event.edit(f"**• تم فك الانتحال جزئياً**\nالاسم: {'✅' if name_ok else '❌'}\nالبايو: {'✅' if bio_ok else '❌'}\nالصورة: {'✅' if photo_ok else '❌'}")
    
    # ==================== باقي الأوامر ====================
    
    @client.on(events.NewMessage(outgoing=True, pattern='.كتم'))
    async def mute_cmd(event):
        if event.is_reply:
            muted_users[phone][event.reply_to_msg_id] = True
            await event.edit("**• تم الكتم**")
        elif event.is_private:
            muted_users[phone][event.chat_id] = True
            await event.edit("**• تم الكتم**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.الغاء كتم'))
    async def unmute_cmd(event):
        if event.is_reply:
            muted_users[phone].pop(event.reply_to_msg_id, None)
        elif event.is_private:
            muted_users[phone].pop(event.chat_id, None)
        await event.edit("**• تم فك الكتم**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.حظر'))
    async def ban_cmd(event):
        tid = None
        if event.is_reply:
            r = await event.get_reply_message()
            tid = r.sender_id
        elif event.is_private:
            tid = event.chat_id
        if tid:
            try:
                await client(BlockRequest(tid))
                banned_users[phone][tid] = True
                await event.edit("**• تم الحظر**")
            except:
                await event.edit("**• فشل الحظر**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.الغاء حظر'))
    async def unban_cmd(event):
        tid = None
        if event.is_reply:
            r = await event.get_reply_message()
            tid = r.sender_id
        elif event.is_private:
            tid = event.chat_id
        if tid:
            try:
                await client(UnblockRequest(tid))
                banned_users[phone].pop(tid, None)
                await event.edit("**• تم فك الحظر**")
            except:
                await event.edit("**• فشل فك الحظر**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.تقيد'))
    async def restrict_cmd(event):
        if event.is_group and event.is_reply:
            r = await event.get_reply_message()
            try:
                await client.edit_permissions(event.chat_id, r.sender_id, send_messages=False)
                await event.edit("**• تم التقييد**")
            except:
                await event.edit("**• فشل التقييد**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.الغاء تقييد'))
    async def unrestrict_cmd(event):
        if event.is_group and event.is_reply:
            r = await event.get_reply_message()
            try:
                await client.edit_permissions(event.chat_id, r.sender_id, send_messages=True)
                await event.edit("**• تم فك التقييد**")
            except:
                await event.edit("**• فشل فك التقييد**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.تهكير'))
    async def hack_cmd(event):
        target_name = "الضحية"
        if event.is_reply:
            try:
                r = await event.get_reply_message()
                u = await client.get_entity(r.sender_id)
                target_name = u.first_name
            except:
                pass
        await event.edit("**جاري التهكير...**")
        await asyncio.sleep(1)
        await event.edit("**تم اختراق 50%**")
        await asyncio.sleep(1)
        await event.edit(f"**تم تهكير {target_name} بنجاح**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.سجل'))
    async def save_cmd(event):
        save_deleted[phone] = True
        await event.edit("**• يتم تسجيل حذف الرسائل**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.الغاء سجل'))
    async def stop_save_cmd(event):
        save_deleted[phone] = False
        await event.edit("**• تم تعطيل تسجيل الرسائل**")
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'\.اسم (.+)'))
    async def name_cmd(event):
        new_name = event.pattern_match.group(1).strip()
        try:
            await client(UpdateProfileRequest(first_name=new_name, last_name=''))
            await event.edit("**• تم تغيير الاسم**")
        except:
            await event.edit("**• فشل تغيير الاسم**")
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'\.بايو (.+)'))
    async def bio_cmd(event):
        new_bio = event.pattern_match.group(1).strip()
        success = await change_bio(client, new_bio)
        if success:
            await event.edit("**• تم تغيير البايو**")
        else:
            await event.edit("**• فشل تغيير البايو**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.خط عريض'))
    async def bold_cmd(event):
        bold_mode[phone] = True
        await event.edit("**• تم تفعيل الخط العريض**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.الغاء خط'))
    async def stop_bold_cmd(event):
        bold_mode[phone] = False
        await event.edit("**• تم الغاء الخط العريض**")
    
    # مراقبة القناة
    async def periodic_channel_check():
        while True:
            await asyncio.sleep(600)
            try:
                await ensure_subscription(client, phone)
            except:
                pass
    
    asyncio.ensure_future(periodic_channel_check(), loop=main_loop)
    
    logger.info(f"Handlers ready for {phone}")

def start_main_loop():
    asyncio.set_event_loop(main_loop)
    main_loop.run_until_complete(load_all_sessions())
    asyncio.ensure_future(auto_save_sessions_loop(), loop=main_loop)
    main_loop.run_forever()

threading.Thread(target=start_main_loop, daemon=True).start()

@app.route('/')
def home():
    return """<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>qgram-bot</title><script src="https://cdn.tailwindcss.com"></script><style>body{background:linear-gradient(135deg,#1e3a8a,#3b82f6)}.card{background:rgba(255,255,255,0.95)}</style></head><body class="min-h-screen flex items-center justify-center p-4"><div class="max-w-lg w-full"><div class="card rounded-3xl shadow-2xl p-8"><div class="text-center mb-8"><h1 class="text-4xl font-bold text-blue-700 mb-2">qgram-bot</h1><p class="text-gray-600">Telegram UserBot</p></div><div id="form-section"><div id="step1"><h2 class="text-2xl font-semibold mb-6 text-center">تسجيل الدخول</h2><form id="sendForm" class="space-y-5"><div><label class="block text-sm font-medium text-gray-700 mb-1">API ID</label><input type="text" name="api_id" placeholder="12345678" required class="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:border-blue-500"></div><div><label class="block text-sm font-medium text-gray-700 mb-1">API HASH</label><input type="text" name="api_hash" placeholder="0123456789abcdef..." required class="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:border-blue-500"></div><div><label class="block text-sm font-medium text-gray-700 mb-1">رقم الهاتف</label><input type="text" name="phone" placeholder="+201234567890" required class="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:border-blue-500"></div><button type="submit" class="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-4 rounded-2xl transition">إرسال كود التحقق</button></form></div><div id="step2" class="hidden"><h2 class="text-2xl font-semibold mb-6 text-center">أدخل كود التحقق</h2><form id="verifyForm" class="space-y-5"><input type="hidden" name="phone" id="verify_phone"><div><label class="block text-sm font-medium text-gray-700 mb-1">كود التحقق</label><input type="text" name="code" placeholder="12345" required maxlength="5" class="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:border-blue-500 text-center text-2xl tracking-widest"></div><div><label class="block text-sm font-medium text-gray-700 mb-1">2FA (اختياري)</label><input type="password" name="password" placeholder="••••••••" class="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:border-blue-500"></div><button type="submit" class="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-4 rounded-2xl transition">تفعيل</button></form><button onclick="backToStep1()" class="mt-4 w-full text-gray-500">← العودة</button></div></div><div id="result" class="mt-6 text-center hidden"></div></div><div class="text-center mt-6"><a href="/api/status" class="text-white hover:underline">عرض الحالة</a></div></div><script>async function showResult(m,s){const d=document.getElementById('result');d.className=`mt-6 p-4 rounded-2xl text-center font-medium ${s?'bg-green-100 text-green-700':'bg-red-100 text-red-700'}`;d.innerHTML=m;d.classList.remove('hidden')}document.getElementById('sendForm').addEventListener('submit',async(e)=>{e.preventDefault();const f=new FormData(e.target);try{const r=await fetch('/api/send_code',{method:'POST',body:f});const d=await r.json();if(d.status==='code_sent'){document.getElementById('verify_phone').value=f.get('phone');document.getElementById('step1').classList.add('hidden');document.getElementById('step2').classList.remove('hidden');showResult(d.message,true)}else{showResult(d.message||d.error||'حدث خطأ',false)}}catch(err){showResult('حدث خطأ',false)}});document.getElementById('verifyForm').addEventListener('submit',async(e)=>{e.preventDefault();const f=new FormData(e.target);try{const r=await fetch('/api/verify',{method:'POST',body:f});const d=await r.json();if(d.status==='success'){showResult(d.message,true);setTimeout(()=>location.reload(),3000)}else{showResult(d.message||'فشل التفعيل',false)}}catch(err){showResult('حدث خطأ',false)}});function backToStep1(){document.getElementById('step1').classList.remove('hidden');document.getElementById('step2').classList.add('hidden');document.getElementById('result').classList.add('hidden')}</script></body></html>"""

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
        api_configs_storage[phone] = {'api_id': api_id, 'api_hash': api_hash}
        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()
        if await client.is_user_authorized():
            active_clients[phone] = client
            client_me[phone] = await client.get_me()
            start_client_in_background(client, phone)
            await save_all_sessions()
            return jsonify({"status": "already_active", "message": "البوت مفعل بالفعل"})
        sent = await client.send_code_request(phone)
        pending_logins[phone] = (client, sent.phone_code_hash, api_id, api_hash)
        return jsonify({"status": "code_sent", "message": "تم إرسال كود التحقق"})
    except Exception as e:
        logger.error(f"Error: {e}")
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
                return jsonify({"status": "error", "message": "مطلوب كلمة مرور"}), 401
            await client.sign_in(password=password)
        active_clients[phone] = client
        client_me[phone] = await client.get_me()
        del pending_logins[phone]
        await save_all_sessions()
        start_client_in_background(client, phone)
        return jsonify({"status": "success", "message": "تم تفعيل اليوزربوت بنجاح"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/status')
def status():
    return jsonify({"active_bots": list(active_clients.keys()), "total_active": len(active_clients)})

@app.route('/api/disconnect/<phone>', methods=['POST'])
@async_route
async def disconnect(phone):
    if phone in active_clients:
        await active_clients[phone].disconnect()
        del active_clients[phone]
        await save_all_sessions()
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404

if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info(f"qgram UserBot - PIL: {PIL_AVAILABLE}")
    logger.info("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
