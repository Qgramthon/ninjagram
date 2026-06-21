import asyncio
import io
import os
import logging
import subprocess
import shutil
import requests
import re
import time
import hashlib
from concurrent.futures import ThreadPoolExecutor
from telethon import events, Button
from telethon.errors import (
    FloodWaitError, ChatAdminRequiredError, UserPrivacyRestrictedError,
    PeerFloodError, UserBannedInChannelError, UserNotMutualContactError,
    UserChannelsTooMuchError, UserKickedError
)
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon.tl.types import (
    InputPhoto, DocumentAttributeAudio, DocumentAttributeVideo,
    InputPeerUser, InputPeerChat, InputPeerChannel
)
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.messages import AddChatUserRequest
from shared import (
    active_clients, muted_users, taqleed_users, ent7al_users, ent7al_original,
    client_me, track_command, logger, TEMP_DIR
)

# ThreadPoolExecutor للتحميلات
_DOWNLOAD_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="dl")

# إضافة متغيرات لمراقبة الخاص
message_cache = {}

# تكوين logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def format_duration(seconds):
    """تنسيق المدة الزمنية"""
    if not seconds: 
        return "0:00"
    try:
        seconds = int(float(seconds))
        mins, secs = divmod(seconds, 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            return f"{hours}:{mins:02d}:{secs:02d}"
        return f"{mins}:{secs:02d}"
    except:
        return "0:00"

def sanitize_filename(filename):
    """تنظيف اسم الملف من الأحرف غير المسموحة"""
    return re.sub(r'[<>:"/\\|?*]', '_', filename)[:200]

# ────────────── دوال مساعدة للتأخير ──────────────
async def safe_sleep(seconds, event=None):
    """نوم آمن مع تحديث الرسالة"""
    for i in range(int(seconds)):
        if event and i % 5 == 0:
            try:
                await event.edit(f"**• ⏳ جاري الانتظار {int(seconds)-i} ثانية...**")
            except:
                pass
        await asyncio.sleep(1)

# ────────────── محركات البحث عن الصور ──────────────
def _search_images_google(query: str, limit: int = 5) -> list:
    """يبحث في Google Images"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        url = f"https://www.google.com/search?q={requests.utils.quote(query)}&tbm=isch&hl=ar"
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            raise ValueError("Google لم يستجب")
        
        # استخراج روابط الصور
        urls = re.findall(r'<img[^>]+src="([^"]+)"', resp.text)
        valid_urls = []
        for u in urls:
            if u.startswith("http") and "google" not in u and len(valid_urls) < limit:
                valid_urls.append(u)
        return valid_urls
    except Exception as e:
        raise ValueError(f"Google: {e}")

def _search_images_bing(query: str, limit: int = 5) -> list:
    """يبحث في Bing Images"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(
            "https://www.bing.com/images/search",
            params={"q": query, "first": 0, "count": limit},
            headers=headers, 
            timeout=15
        )
        if resp.status_code != 200:
            raise ValueError("Bing لم يستجب")
        
        matches = re.findall(r'<img[^>]+src="([^"]+)"', resp.text)
        urls = [m for m in matches if m.startswith("http") and not m.startswith("https://www.bing.com")][:limit]
        return urls or []
    except Exception as e:
        raise ValueError(f"Bing: {e}")

def _search_images_ddg(query: str, limit: int = 5) -> list:
    """يبحث في DuckDuckGo"""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.images(query, max_results=limit))
        return [img["image"] for img in results if img.get("image")]
    except ImportError:
        raise ValueError("مكتبة duckduckgo_search غير مثبتة")
    except Exception as e:
        raise ValueError(f"DuckDuckGo: {e}")

def _search_images_pixabay(query: str, limit: int = 5) -> list:
    """يبحث في Pixabay"""
    try:
        resp = requests.get(
            "https://pixabay.com/api/",
            params={
                "key": "25564984-2e3f8b5f6b6f6e5e5e5e5e5e",  # استبدل بمفتاح API خاص بك
                "q": query,
                "image_type": "photo",
                "per_page": limit,
                "safesearch": "true"
            },
            timeout=15
        )
        if resp.status_code != 200:
            raise ValueError("Pixabay لم يستجب")
        return [img["webformatURL"] for img in resp.json().get("hits", [])][:limit]
    except Exception as e:
        raise ValueError(f"Pixabay: {e}")

def _download_image(url: str, out_dir: str) -> str:
    """تحميل صورة من رابط"""
    try:
        resp = requests.get(url, stream=True, timeout=30)
        if resp.status_code != 200:
            return None
        
        # تحديد الامتداد
        ext = os.path.splitext(url.split('?')[0])[1] or '.jpg'
        if ext.lower() not in ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'):
            ext = '.jpg'
        
        # إنشاء اسم فريد للملف
        timestamp = str(int(time.time() * 1000))
        hash_str = hashlib.md5(url.encode()).hexdigest()[:8]
        filename = f"img_{timestamp}_{hash_str}{ext}"
        filepath = os.path.join(out_dir, filename)
        
        # تحميل الملف
        with open(filepath, 'wb') as f:
            for chunk in resp.iter_content(8192):
                if chunk:
                    f.write(chunk)
        
        # التحقق من حجم الملف
        if os.path.getsize(filepath) < 1024:  # أقل من 1KB
            os.remove(filepath)
            return None
            
        return filepath
    except Exception as e:
        logger.error(f"فشل تحميل الصورة من {url}: {e}")
        return None

# ────────────── خدمات تحميل الفيديو/الصوت ──────────────
def _search_youtube_link(query: str) -> str:
    """يبحث عن أول فيديو يوتيوب"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        # البحث في Google عن فيديو يوتيوب
        search_url = f"https://www.google.com/search?q={requests.utils.quote(query)}+site:youtube.com/watch&hl=ar"
        resp = requests.get(search_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None
        
        match = re.search(r"https?://(?:www\.)?youtube\.com/watch\?v=([\w-]{11})", resp.text)
        if match:
            return match.group(0)
        
        # محاولة البحث في Bing
        bing_url = f"https://www.bing.com/search?q={requests.utils.quote(query)}+site:youtube.com/watch"
        resp = requests.get(bing_url, headers=headers, timeout=15)
        if resp.status_code == 200:
            match = re.search(r"https?://(?:www\.)?youtube\.com/watch\?v=([\w-]{11})", resp.text)
            if match:
                return match.group(0)
    except:
        pass
    return None

def _cobalt_download(query: str, out_dir: str, audio_only: bool) -> tuple:
    """Cobalt API - طريقة تحميل سريعة"""
    if not query.startswith("http"):
        yt_url = _search_youtube_link(query)
        if not yt_url:
            raise ValueError("لم يتم العثور على الفيديو المطلوب")
        query = yt_url

    try:
        # إرسال طلب لـ Cobalt API
        api_url = "https://co.wuk.sh/api/json"
        payload = {
            "url": query,
            "filenamePattern": "basic",
            "downloadMode": "audio" if audio_only else "auto",
            "vQuality": "720" if not audio_only else "auto"
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        resp = requests.post(api_url, json=payload, headers=headers, timeout=45)
        if resp.status_code != 200:
            raise ValueError(f"Cobalt API رفض الطلب: {resp.status_code}")
        
        data = resp.json()
        if data.get("status") == "error":
            raise ValueError(f"Cobalt خطأ: {data.get('text', 'غير معروف')}")
        
        dl_url = data.get("url")
        if not dl_url:
            raise ValueError("Cobalt لم يرجع رابط تحميل")
        
        # تحميل الملف
        file_resp = requests.get(dl_url, stream=True, timeout=120)
        if file_resp.status_code != 200:
            raise ValueError("فشل تحميل الملف من الخادم")
        
        # تحديد الامتداد
        ext = "mp3" if audio_only else "mp4"
        timestamp = int(time.time() * 1000)
        filename = f"cobalt_{timestamp}.{ext}"
        filepath = os.path.join(out_dir, filename)
        
        # حفظ الملف
        total_size = 0
        with open(filepath, "wb") as f:
            for chunk in file_resp.iter_content(8192):
                if chunk:
                    f.write(chunk)
                    total_size += len(chunk)
        
        # التحقق من حجم الملف
        if total_size < 10240:  # أقل من 10KB
            os.remove(filepath)
            raise ValueError("الملف المحمل صغير جداً")
        
        title = data.get("filename", "cobalt_media")
        duration = data.get("duration", 0)
        uploader = data.get("uploader", "")
        
        return {
            "title": sanitize_filename(title),
            "duration": duration,
            "uploader": uploader
        }, filepath
        
    except Exception as e:
        raise ValueError(f"Cobalt: {str(e)}")

def _y2mate_download(query: str, out_dir: str, audio_only: bool) -> tuple:
    """Y2mate API - بديل احتياطي"""
    if not query.startswith("http"):
        yt_url = _search_youtube_link(query)
        if not yt_url:
            raise ValueError("لم يتم العثور على الفيديو المطلوب")
        query = yt_url

    try:
        # استخراج معرف الفيديو
        vid_patterns = [
            r"(?:v=|/)([\w-]{11})",
            r"youtu\.be/([\w-]{11})",
            r"youtube\.com/embed/([\w-]{11})"
        ]
        
        vid = None
        for pattern in vid_patterns:
            match = re.search(pattern, query)
            if match:
                vid = match.group(1)
                break
        
        if not vid:
            raise ValueError("رابط يوتيوب غير صالح")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        # الخطوة 1: جلب معلومات التحويل
        analyze_data = {
            "k_query": f"https://www.youtube.com/watch?v={vid}",
            "k_page": "home",
            "hl": "en",
            "q_auto": 1
        }
        
        resp = requests.post(
            "https://www.y2mate.com/mates/analyzeV2/ajax",
            data=analyze_data,
            headers=headers,
            timeout=15
        )
        
        if resp.status_code != 200:
            raise ValueError("Y2mate Analyze فشل")
        
        data = resp.json()
        video_id = data.get("vid")
        if not video_id:
            raise ValueError("Y2mate لم يعثر على الفيديو")

        # الخطوة 2: طلب التحميل
        convert_data = {
            "vid": video_id,
            "k": "mp3" if audio_only else "mp4"
        }
        
        resp2 = requests.post(
            "https://www.y2mate.com/mates/convertV2/index",
            data=convert_data,
            headers=headers,
            timeout=15
        )
        
        if resp2.status_code != 200:
            raise ValueError("Y2mate Convert فشل")
        
        data2 = resp2.json()
        dl_url = data2.get("dlink")
        if not dl_url:
            raise ValueError("Y2mate لم يرجع رابط تحميل")
        
        # تحميل الملف
        file_resp = requests.get(dl_url, stream=True, timeout=120)
        if file_resp.status_code != 200:
            raise ValueError("فشل تحميل الملف من Y2mate")
        
        # تحديد الامتداد
        ext = "mp3" if audio_only else "mp4"
        timestamp = int(time.time() * 1000)
        filename = f"y2mate_{timestamp}.{ext}"
        filepath = os.path.join(out_dir, filename)
        
        # حفظ الملف
        total_size = 0
        with open(filepath, "wb") as f:
            for chunk in file_resp.iter_content(8192):
                if chunk:
                    f.write(chunk)
                    total_size += len(chunk)
        
        # التحقق من حجم الملف
        if total_size < 10240:  # أقل من 10KB
            os.remove(filepath)
            raise ValueError("الملف المحمل صغير جداً")
        
        title = data2.get("title", "y2mate_media")
        duration = data2.get("duration", 0)
        uploader = data2.get("uploader", "")
        
        return {
            "title": sanitize_filename(title),
            "duration": duration,
            "uploader": uploader
        }, filepath
        
    except Exception as e:
        raise ValueError(f"Y2mate: {str(e)}")

# ────────────── دوال الانتحال ──────────────
async def get_user_info_full(client, user_id):
    """جلب معلومات المستخدم الكاملة"""
    try:
        user = await client.get_entity(user_id)
        name = user.first_name or ""
        if user.last_name:
            name += f" {user.last_name}"
        
        bio = ""
        try:
            full = await client(GetFullUserRequest(user_id))
            if full.full_user.about:
                bio = full.full_user.about
        except:
            pass
        
        return {
            'name': name.strip() or "غير معروف",
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
            'bio': bio,
            'id': user.id
        }
    except Exception as e:
        logger.error(f"فشل جلب معلومات المستخدم {user_id}: {e}")
        return None

async def change_profile_photo(client, user_id, phone):
    """تغيير صورة البروفايل"""
    try:
        # تحميل صورة المستخدم المستهدف
        bio = io.BytesIO()
        await client.download_profile_photo(user_id, file=bio)
        bio.seek(0)
        
        # رفع الصورة
        uploaded = await client.upload_file(bio, file_name="photo.jpg")
        result = await client(UploadProfilePhotoRequest(file=uploaded))
        await asyncio.sleep(2)
        
        if hasattr(result, 'photo') and hasattr(result.photo, 'id'):
            return True, result.photo.id
        return True, None
        
    except FloodWaitError as e:
        logger.warning(f"Flood wait {e.seconds} ثانية لتغيير الصورة")
        await asyncio.sleep(e.seconds)
        try:
            bio = io.BytesIO()
            await client.download_profile_photo(user_id, file=bio)
            bio.seek(0)
            uploaded = await client.upload_file(bio, file_name="photo.jpg")
            result = await client(UploadProfilePhotoRequest(file=uploaded))
            await asyncio.sleep(2)
            if hasattr(result, 'photo') and hasattr(result.photo, 'id'):
                return True, result.photo.id
            return True, None
        except Exception as e:
            logger.error(f"فشل تغيير الصورة بعد FloodWait: {e}")
            return False, None
            
    except Exception as e:
        logger.error(f"فشل تغيير الصورة: {e}")
        return False, None

# ────────────── دوال كتم المستخدمين ──────────────
async def mute_user(client, user_id, duration_minutes=None):
    """كتم مستخدم"""
    try:
        if phone not in muted_users:
            muted_users[phone] = {}
        muted_users[phone][user_id] = {
            'time': time.time(),
            'duration': duration_minutes * 60 if duration_minutes else None
        }
        return True
    except:
        return False

async def unmute_user(client, user_id):
    """فك كتم مستخدم"""
    try:
        if phone in muted_users and user_id in muted_users[phone]:
            del muted_users[phone][user_id]
            return True
        return False
    except:
        return False

def is_user_muted(phone, user_id):
    """التحقق مما إذا كان المستخدم مكتوماً"""
    if phone not in muted_users:
        return False
    if user_id not in muted_users[phone]:
        return False
    
    mute_info = muted_users[phone][user_id]
    if mute_info.get('duration'):
        if time.time() - mute_info['time'] > mute_info['duration']:
            del muted_users[phone][user_id]
            return False
    
    return True

# ────────────── إعداد المعالجات ──────────────
async def setup_handlers(client, phone):
    """إعداد جميع معالجات الأحداث"""
    
    # تهيئة المتغيرات
    if phone not in muted_users:
        muted_users[phone] = {}
    if phone not in taqleed_users:
        taqleed_users[phone] = {}
    if phone not in ent7al_users:
        ent7al_users[phone] = False
    if phone not in ent7al_original:
        ent7al_original[phone] = {}

    # ─ـ التقليد ─ـ
    @client.on(events.NewMessage(incoming=True))
    async def auto_taqleed(event):
        """تقليد تلقائي للرسائل"""
        try:
            if event.sender_id in taqleed_users.get(phone, {}) and event.text and not event.text.startswith('.'):
                await asyncio.sleep(0.5)
                try:
                    await event.reply(event.text)
                except Exception as e:
                    logger.error(f"فشل التقليد: {e}")
        except:
            pass

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تقليد$'))
    async def taq(event):
        """تفعيل التقليد"""
        try:
            target = None
            if event.is_reply:
                reply = await event.get_reply_message()
                target = reply.sender_id
            elif event.is_private:
                target = event.chat_id
            
            if target:
                taqleed_users[phone][target] = True
                await event.edit("**• ✅ تم تفعيل التقليد**")
            else:
                await event.edit("**• ❌ يرجى الرد على رسالة أو استخدام في الخاص**")
        except Exception as e:
            await event.edit(f"**• ❌ خطأ: {str(e)[:50]}**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غ تقليد$'))
    async def notaq(event):
        """إلغاء التقليد"""
        try:
            target = None
            if event.is_reply:
                reply = await event.get_reply_message()
                target = reply.sender_id
            elif event.is_private:
                target = event.chat_id
            
            if target and target in taqleed_users.get(phone, {}):
                del taqleed_users[phone][target]
                await event.edit("**• ✅ تم إلغاء التقليد**")
            else:
                await event.edit("**• ❌ لا يوجد تقليد نشط**")
        except Exception as e:
            await event.edit(f"**• ❌ خطأ: {str(e)[:50]}**")

    # ─ـ الانتحال ─ـ
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.انتحال$'))
    async def ent7al(event):
        """انتحال شخصية مستخدم"""
        track_command(phone, ".انتحال")
        await event.edit("**• 🔄 جاري الانتحال...**")
        
        target_user = None
        if event.is_reply:
            try:
                reply = await event.get_reply_message()
                target_user = await client.get_entity(reply.sender_id)
            except Exception as e:
                await event.edit(f"**• ❌ فشل جلب المستخدم: {str(e)[:50]}**")
                return
        elif event.is_private:
            try:
                target_user = await client.get_entity(event.chat_id)
            except Exception as e:
                await event.edit(f"**• ❌ فشل جلب المستخدم: {str(e)[:50]}**")
                return
        
        if not target_user:
            await event.edit("**• ❌ فشل الانتحال - يرجى الرد على مستخدم**")
            return
        
        target_info = await get_user_info_full(client, target_user.id)
        if not target_info:
            await event.edit("**• ❌ فشل جلب معلومات المستخدم**")
            return
        
        # حفظ المعلومات الأصلية
        me = await client.get_me()
        client_me[phone] = me
        
        original = {
            'first_name': me.first_name or '',
            'last_name': me.last_name if me.last_name is not None else '',
            'photo_bytes': None,
            'added_photo_id': None,
            'about': ''
        }
        
        try:
            fu = await client(GetFullUserRequest('me'))
            if fu.full_user.about:
                original['about'] = fu.full_user.about
        except:
            pass
        
        # تغيير الاسم
        name_ok = False
        try:
            await client(UpdateProfileRequest(
                first_name=target_info['first_name'],
                last_name=target_info['last_name']
            ))
            await asyncio.sleep(1)
            name_ok = True
        except FloodWaitError as e:
            await event.edit(f"**• ⏳ انتظار {e.seconds} ثانية...**")
            await asyncio.sleep(e.seconds)
            try:
                await client(UpdateProfileRequest(
                    first_name=target_info['first_name'],
                    last_name=target_info['last_name']
                ))
                name_ok = True
            except Exception as e2:
                logger.error(f"فشل تغيير الاسم بعد FloodWait: {e2}")
        except Exception as e:
            logger.error(f"فشل تغيير الاسم: {e}")
        
        # تغيير البايو
        bio_ok = False
        try:
            bio_text = target_info['bio'][:70] if target_info['bio'] else ''
            await client(UpdateProfileRequest(about=bio_text))
            await asyncio.sleep(0.5)
            bio_ok = True
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            try:
                bio_text = target_info['bio'][:70] if target_info['bio'] else ''
                await client(UpdateProfileRequest(about=bio_text))
                bio_ok = True
            except Exception as e2:
                logger.error(f"فشل تغيير البايو بعد FloodWait: {e2}")
        except Exception as e:
            logger.error(f"فشل تغيير البايو: {e}")
        
        # تغيير الصورة
        photo_ok, added_id = await change_profile_photo(client, target_user.id, phone)
        if photo_ok and added_id:
            original['added_photo_id'] = added_id
        
        # حفظ المعلومات الأصلية
        ent7al_original[phone] = original
        ent7al_users[phone] = True
        
        # عرض النتيجة
        if name_ok and bio_ok and photo_ok:
            await event.edit("**• ✅ تم الانتحال بنجاح**")
        elif name_ok or bio_ok or photo_ok:
            await event.edit("**• ⚠️ تم الانتحال جزئياً**")
        else:
            await event.edit("**• ❌ فشل الانتحال بالكامل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.الغاء انتحال$'))
    async def unent7al(event):
        """إلغاء الانتحال"""
        track_command(phone, ".الغاء انتحال")
        await event.edit("**• 🔄 جاري إلغاء الانتحال...**")
        
        if not ent7al_users.get(phone) or not ent7al_original.get(phone):
            await event.edit("**• ❌ لا يوجد انتحال نشط**")
            return
        
        original = ent7al_original[phone]
        first = original.get('first_name', '')
        last = original.get('last_name', '')
        
        # استعادة الاسم
        restored_name = False
        for attempt in range(3):
            try:
                await client(UpdateProfileRequest(first_name=first, last_name=last))
                await asyncio.sleep(1.5)
                
                me_now = await client.get_me()
                if me_now.first_name == first and (me_now.last_name or '') == last:
                    restored_name = True
                    break
                    
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"محاولة استعادة الاسم {attempt+1}: {e}")
                await asyncio.sleep(1)
        
        if not restored_name:
            logger.error(f"فشل استعادة الاسم بالكامل لـ {phone}")
        
        # حذف الصورة المضافة
        if original.get('added_photo_id'):
            try:
                await client(DeletePhotosRequest(
                    id=[InputPhoto(
                        id=original['added_photo_id'],
                        access_hash=0,
                        file_reference=b''
                    )]
                ))
                await asyncio.sleep(2)
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"فشل حذف الصورة المضافة: {e}")
        else:
            # حذف الصورة الحالية كبديل
            try:
                current_photos = await client.get_profile_photos('me', limit=1)
                if current_photos:
                    await client(DeletePhotosRequest(
                        id=[InputPhoto(
                            id=current_photos[0].id,
                            access_hash=current_photos[0].access_hash,
                            file_reference=current_photos[0].file_reference
                        )]
                    ))
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"فشل حذف الصورة الاحتياطية: {e}")
        
        # استعادة البايو
        try:
            await client(UpdateProfileRequest(about=original.get('about', '')))
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"فشل استعادة البايو: {e}")
        
        ent7al_users[phone] = False
        ent7al_original[phone] = {}
        await event.edit("**• ✅ تم إلغاء الانتحال**")

    # ─ـ إضافة أعضاء ─ـ
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.اضافة (\d+) (@?\w+)$'))
    async def add_members_from_group(event):
        """إضافة أعضاء من مجموعة إلى أخرى"""
        if not event.is_group:
            await event.edit("**• ❌ الأمر يعمل في المجموعات فقط**")
            return
        
        try:
            count = int(event.pattern_match.group(1))
            target_username = event.pattern_match.group(2).strip()
        except:
            await event.edit("**• ❌ صيغة خاطئة: `.اضافة [العدد] [المعرف]**")
            return
        
        await event.edit(f"**• 🔄 جاري سحب {count} عضو من {target_username}...**")
        
        # الحصول على المجموعة المصدر
        try:
            source_group = await client.get_entity(target_username)
        except Exception:
            await event.edit(f"**• ❌ لم يتم العثور على المجموعة {target_username}**")
            return
        
        # محاولة الانضمام للمجموعة المصدر
        try:
            await client.join_channel(source_group)
            await asyncio.sleep(3)
        except:
            pass
        
        added = 0
        failed = 0
        skipped = 0
        
        try:
            async for user in client.iter_participants(source_group, limit=count):
                # تخطي البوتات والحسابات المحذوفة
                if user.bot or user.deleted:
                    skipped += 1
                    continue
                
                try:
                    # إضافة المستخدم
                    if hasattr(event.chat, 'megagroup') and event.chat.megagroup:
                        await client(InviteToChannelRequest(
                            channel=event.chat_id,
                            users=[user.id]
                        ))
                    else:
                        await client(AddChatUserRequest(
                            chat_id=event.chat_id,
                            user_id=user.id,
                            fwd_limit=10
                        ))
                    
                    added += 1
                    await asyncio.sleep(1.5)
                    
                    # تحديث الرسالة كل 5 إضافات
                    if added % 5 == 0:
                        await event.edit(
                            f"**• 🔄 جاري الإضافة...**\n"
                            f"**• ✅ تم: {added}**\n"
                            f"**• ❌ فشل: {failed}**"
                        )
                        
                except FloodWaitError as e:
                    await event.edit(f"**• ⏳ انتظار {e.seconds} ثانية...**")
                    await asyncio.sleep(e.seconds)
                    try:
                        if hasattr(event.chat, 'megagroup') and event.chat.megagroup:
                            await client(InviteToChannelRequest(
                                channel=event.chat_id,
                                users=[user.id]
                            ))
                        else:
                            await client(AddChatUserRequest(
                                chat_id=event.chat_id,
                                user_id=user.id,
                                fwd_limit=10
                            ))
                        added += 1
                    except:
                        failed += 1
                        
                except ChatAdminRequiredError:
                    await event.edit("**• ❌ الصلاحيات غير كافية - يجب أن تكون مشرفاً**")
                    return
                    
                except (UserPrivacyRestrictedError, UserNotMutualContactError):
                    failed += 1
                    continue
                    
                except PeerFloodError:
                    await event.edit("**• ❌ تم الوصول للحد الأقصى من الإضافات**")
                    break
                    
                except Exception as e:
                    failed += 1
                    if "USER_PRIVACY_RESTRICTED" in str(e):
                        break
                    continue
            
            # رسالة النتيجة النهائية
            result_msg = f"**• ✅ تمت إضافة {added} عضو بنجاح**"
            if failed > 0:
                result_msg += f"\n**• ❌ فشل إضافة {failed} عضو**"
            if skipped > 0:
                result_msg += f"\n**• ⏭️ تم تخطي {skipped} (بوتات/محذوفة)**"
            
            await event.edit(result_msg)
            
        except ChatAdminRequiredError:
            await event.edit("**• ❌ لا تملك صلاحيات لسحب الأعضاء**")
        except Exception as e:
            await event.edit(f"**• ❌ فشل: {str(e)[:100]}**")

    # ─ـ تحويل الصوت إلى نص ─ـ
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.نسخ$'))
    async def transcribe_voice(event):
        """تحويل الرسالة الصوتية إلى نص"""
        if not event.is_reply:
            await event.edit("**• ❌ يرجى الرد على رسالة صوتية أو فيديو**")
            return
        
        reply = await event.get_reply_message()
        if not (reply.voice or reply.audio or (reply.video and reply.video.duration < 120)):
            await event.edit("**• ❌ الرد على رسالة صوتية أو فيديو قصير فقط**")
            return
        
        await event.edit("**• 🔄 جاري تحويل المقطع إلى نص...**")
        
        # التحقق من وجود المكتبات المطلوبة
        try:
            import speech_recognition as sr
        except ImportError:
            await event.edit("**• ❌ مكتبة SpeechRecognition غير مثبتة**\n**• استخدم: `pip install SpeechRecognition`**")
            return
        
        voice_path = None
        wav_path = None
        
        try:
            # تحميل الملف الصوتي
            voice_path = os.path.join(TEMP_DIR, f"voice_{phone}_{reply.id}_{int(time.time())}.ogg")
            await client.download_media(reply, voice_path)
            
            # التحقق من وجود ffmpeg
            try:
                subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                await event.edit("**• ❌ ffmpeg غير مثبت على النظام**")
                return
            
            # تحويل إلى WAV
            wav_path = voice_path.replace(".ogg", ".wav")
            result = subprocess.run(
                ["ffmpeg", "-i", voice_path, "-ac", "1", "-ar", "16000", wav_path],
                check=True,
                capture_output=True,
                timeout=30
            )
            
            if not os.path.exists(wav_path) or os.path.getsize(wav_path) < 1024:
                await event.edit("**• ❌ فشل تحويل الصوت**")
                return
            
            # التعرف على النص
            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_path) as source:
                audio_data = recognizer.record(source)
            
            try:
                # محاولة التعرف بالعربية
                text = recognizer.recognize_google(audio_data, language="ar-AR")
            except:
                try:
                    # محاولة التعرف بالإنجليزية
                    text = recognizer.recognize_google(audio_data, language="en-US")
                except sr.UnknownValueError:
                    await event.edit("**• ❌ لم يتم التعرف على أي كلام**")
                    return
                except sr.RequestError as e:
                    await event.edit(f"**• ❌ خطأ في خدمة التعرف: {e}**")
                    return
            
            if text:
                await event.edit(f"**النص:**\n{text}")
            else:
                await event.edit("**• ❌ لم يتم استخراج نص**")
                
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode()[:200] if e.stderr else str(e)
            await event.edit(f"**• ❌ فشل تحويل الصوت:**\n{error_msg}")
        except Exception as e:
            await event.edit(f"**• ❌ فشل: {str(e)[:100]}**")
        finally:
            # تنظيف الملفات المؤقتة
            for p in [voice_path, wav_path]:
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except:
                        pass

    # ─ـ تحويل الصورة إلى استيكر ─ـ
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.استيك$'))
    async def photo_to_sticker(event):
        """تحويل الصورة إلى استيكر"""
        if not event.is_reply:
            await event.edit("**• ❌ يرجى الرد على صورة**")
            return
        
        reply = await event.get_reply_message()
        if not reply.photo:
            await event.edit("**• ❌ الرد على صورة فقط**")
            return
        
        await event.edit("**• 🔄 جاري تحويل الصورة إلى استيكر...**")
        
        try:
            from PIL import Image
        except ImportError:
            await event.edit("**• ❌ مكتبة Pillow غير مثبتة**\n**• استخدم: `pip install Pillow`**")
            return
        
        img_path = None
        stick_path = None
        
        try:
            # تحميل الصورة
            img_path = os.path.join(TEMP_DIR, f"img_{phone}_{reply.id}_{int(time.time())}.jpg")
            await client.download_media(reply, img_path)
            
            # التحقق من الملف
            if not os.path.exists(img_path):
                await event.edit("**• ❌ فشل تحميل الصورة**")
                return
            
            # تحويل إلى استيكر
            stick_path = img_path.replace(".jpg", ".webp")
            im = Image.open(img_path).convert("RGBA")
            
            # تغيير الحجم مع الحفاظ على النسبة
            im.thumbnail((512, 512), Image.LANCZOS)
            
            # حفظ كـ WEBP
            im.save(stick_path, "WEBP", quality=90)
            
            # إرسال الاستيكر
            if os.path.exists(stick_path) and os.path.getsize(stick_path) > 0:
                await client.send_file(event.chat_id, stick_path, force_document=False)
                await event.delete()
            else:
                await event.edit("**• ❌ فشل إنشاء الاستيكر**")
                
        except Exception as e:
            await event.edit(f"**• ❌ فشل: {str(e)[:100]}**")
        finally:
            # تنظيف الملفات
            for p in [img_path, stick_path]:
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except:
                        pass

    # ─ـ تحويل الاستيكر إلى صورة ─ـ
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بيك$'))
    async def sticker_to_photo(event):
        """تحويل الاستيكر إلى صورة"""
        if not event.is_reply:
            await event.edit("**• ❌ يرجى الرد على استيكر**")
            return
        
        reply = await event.get_reply_message()
        if not reply.sticker:
            await event.edit("**• ❌ الرد على استيكر فقط**")
            return
        
        await event.edit("**• 🔄 جاري تحويل الاستيكر إلى صورة...**")
        
        try:
            from PIL import Image
        except ImportError:
            await event.edit("**• ❌ مكتبة Pillow غير مثبتة**\n**• استخدم: `pip install Pillow`**")
            return
        
        stick_path = None
        img_path = None
        
        try:
            # تحميل الاستيكر
            stick_path = os.path.join(TEMP_DIR, f"sticker_{phone}_{reply.id}_{int(time.time())}.webp")
            await client.download_media(reply, stick_path)
            
            if not os.path.exists(stick_path):
                await event.edit("**• ❌ فشل تحميل الاستيكر**")
                return
            
            # تحويل إلى PNG
            img_path = stick_path.replace(".webp", ".png")
            im = Image.open(stick_path)
            
            if im.mode != 'RGBA':
                im = im.convert('RGBA')
            
            im.save(img_path, "PNG")
            
            # إرسال الصورة
            if os.path.exists(img_path) and os.path.getsize(img_path) > 0:
                await client.send_file(event.chat_id, img_path)
                await event.delete()
            else:
                await event.edit("**• ❌ فشل تحويل الاستيكر**")
                
        except Exception as e:
            await event.edit(f"**• ❌ فشل: {str(e)[:100]}**")
        finally:
            for p in [stick_path, img_path]:
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except:
                        pass

    # ─ـ تحميل الصور ─ـ
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بن (.+)'))
    async def image_search_download(event):
        """البحث عن الصور وتحميلها"""
        query = event.pattern_match.group(1).strip()
        
        # إذا كان رابط مباشر
        if query.startswith("http"):
            await event.edit("**• 📷 جاري تحميل الصورة...**")
            loop = asyncio.get_event_loop()
            try:
                filepath = await loop.run_in_executor(
                    _DOWNLOAD_EXECUTOR, 
                    _download_image, 
                    query, 
                    TEMP_DIR
                )
                
                if filepath and os.path.exists(filepath):
                    await client.send_file(event.chat_id, filepath)
                    await event.delete()
                    os.remove(filepath)
                else:
                    await event.edit("**• ❌ فشل تحميل الصورة**")
            except Exception as e:
                await event.edit(f"**• ❌ فشل: {str(e)[:100]}**")
            return
        
        # البحث عن الصور
        await event.edit("**• 🔍 جاري البحث عن صور...**")
        loop = asyncio.get_event_loop()
        urls = []
        
        # تجربة جميع المحركات
        engines = [
            ("Google", _search_images_google),
            ("Bing", _search_images_bing),
            ("DuckDuckGo", _search_images_ddg),
            ("Pixabay", _search_images_pixabay)
        ]
        
        for engine_name, finder in engines:
            try:
                await event.edit(f"**• 🔍 جاري البحث في {engine_name}...**")
                urls = await loop.run_in_executor(_DOWNLOAD_EXECUTOR, finder, query, 5)
                if urls:
                    break
            except Exception as e:
                logger.warning(f"فشل البحث في {engine_name}: {e}")
                continue
        
        if not urls:
            await event.edit("**• ❌ لم يتم العثور على صور**")
            return
        
        await event.edit(f"**• 📥 جاري تحميل {min(len(urls), 5)} صورة...**")
        
        # تحميل الصور
        downloaded = []
        for i, url in enumerate(urls[:5], 1):
            path = await loop.run_in_executor(_DOWNLOAD_EXECUTOR, _download_image, url, TEMP_DIR)
            if path:
                downloaded.append(path)
                await event.edit(f"**• 📥 تم تحميل {i}/{min(len(urls), 5)} صورة...**")
        
        if not downloaded:
            await event.edit("**• ❌ فشل تحميل جميع الصور**")
            return
        
        # إرسال الصور
        await event.edit("**• 📤 جاري إرسال الصور...**")
        for i, path in enumerate(downloaded, 1):
            try:
                await client.send_file(
                    event.chat_id, 
                    path,
                    caption=f"**صورة {i}/{len(downloaded)}**"
                )
                os.remove(path)
            except Exception as e:
                logger.error(f"فشل إرسال الصورة {i}: {e}")
        
        await event.delete()

    # ─ـ تحميل الصوت ─ـ
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.يوت (.+)'))
    async def youtube_audio(event):
        """تحميل الصوت من يوتيوب"""
        query = event.pattern_match.group(1).strip()
        
        if not query:
            await event.edit("**• ❌ يرجى كتابة اسم المقطع أو الرابط**")
            return
        
        await event.edit("**• 🎵 جاري التحميل...**")
        loop = asyncio.get_event_loop()
        info = None
        filepath = None
        
        # تجربة Cobalt أولاً
        try:
            await event.edit("**• 🎵 جاري التحميل عبر Cobalt...**")
            info, filepath = await loop.run_in_executor(
                _DOWNLOAD_EXECUTOR, 
                _cobalt_download, 
                query, 
                TEMP_DIR, 
                True
            )
        except Exception as e:
            logger.warning(f"فشل Cobalt: {e}")
            
            # تجربة Y2mate
            try:
                await event.edit("**• 🎵 جاري التحميل عبر Y2mate...**")
                info, filepath = await loop.run_in_executor(
                    _DOWNLOAD_EXECUTOR, 
                    _y2mate_download, 
                    query, 
                    TEMP_DIR, 
                    True
                )
            except Exception as e2:
                logger.error(f"فشل Y2mate: {e2}")
                await event.edit(
                    f"**• ❌ فشل التحميل من جميع المصادر**\n"
                    f"**• حاول استخدام رابط مباشر أو كلمات بحث مختلفة**"
                )
                return
        
        # إرسال الملف
        if info and filepath and os.path.exists(filepath):
            try:
                title = info.get('title', 'بدون عنوان')
                if len(title) > 55:
                    title = title[:52] + '...'
                
                dur = format_duration(info.get('duration', 0))
                uploader = info.get('uploader', 'غير معروف')
                
                caption = f"**{title}**\n**• {dur} | {uploader}**"
                
                await client.send_file(
                    event.chat_id, 
                    filepath,
                    caption=caption,
                    attributes=[
                        DocumentAttributeAudio(
                            duration=int(info.get('duration', 0)) if info.get('duration') else 0,
                            title=title,
                            performer=uploader
                        )
                    ],
                    supports_streaming=True
                )
                await event.delete()
                
            except Exception as e:
                await event.edit(f"**• ❌ فشل الإرسال:**\n{str(e)[:200]}")
            finally:
                try:
                    os.remove(filepath)
                except:
                    pass
        else:
            await event.edit("**• ❌ فشل التحميل - لم يتم الحصول على الملف**")

    # ─ـ تحميل الفيديو ─ـ
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.فيد (.+)'))
    async def video_download(event):
        """تحميل الفيديو من يوتيوب"""
        query = event.pattern_match.group(1).strip()
        
        if not query:
            await event.edit("**• ❌ يرجى كتابة اسم الفيديو أو الرابط**")
            return
        
        await event.edit("**• 🎬 جاري تحميل الفيديو...**")
        loop = asyncio.get_event_loop()
        info = None
        filepath = None
        
        # تجربة Cobalt أولاً
        try:
            await event.edit("**• 🎬 جاري التحميل عبر Cobalt...**")
            info, filepath = await loop.run_in_executor(
                _DOWNLOAD_EXECUTOR, 
                _cobalt_download, 
                query, 
                TEMP_DIR, 
                False
            )
        except Exception as e:
            logger.warning(f"فشل Cobalt للفيديو: {e}")
            
            # تجربة Y2mate
            try:
                await event.edit("**• 🎬 جاري التحميل عبر Y2mate...**")
                info, filepath = await loop.run_in_executor(
                    _DOWNLOAD_EXECUTOR, 
                    _y2mate_download, 
                    query, 
                    TEMP_DIR, 
                    False
                )
            except Exception as e2:
                logger.error(f"فشل Y2mate للفيديو: {e2}")
                await event.edit(
                    f"**• ❌ فشل تحميل الفيديو من جميع المصادر**\n"
                    f"**• حاول استخدام رابط مباشر أو كلمات بحث مختلفة**"
                )
                return
        
        # إرسال الفيديو
        if info and filepath and os.path.exists(filepath):
            try:
                title = info.get('title', 'بدون عنوان')
                if len(title) > 55:
                    title = title[:52] + '...'
                
                dur = format_duration(info.get('duration', 0))
                
                caption = f"**{title}**\n**• {dur} | فيديو**"
                
                # إرسال مع دعم البث
                await client.send_file(
                    event.chat_id, 
                    filepath,
                    caption=caption,
                    attributes=[
                        DocumentAttributeVideo(
                            duration=int(info.get('duration', 0)) if info.get('duration') else 0,
                            w=0,
                            h=0,
                            supports_streaming=True
                        )
                    ],
                    supports_streaming=True
                )
                await event.delete()
                
            except Exception as e:
                await event.edit(f"**• ❌ فشل الإرسال:**\n{str(e)[:200]}")
            finally:
                try:
                    os.remove(filepath)
                except:
                    pass
        else:
            await event.edit("**• ❌ فشل التحميل - لم يتم الحصول على الملف**")

    # ─ـ مراقبة الخاص ─ـ
    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private and not e.out))
    async def cache_private_message(event):
        """تخزين الرسائل الخاصة للمراقبة"""
        try:
            me = await client.get_me()
            if event.sender_id == me.id:
                return
            
            if event.chat_id not in message_cache:
                message_cache[event.chat_id] = {}
            
            message_cache[event.chat_id][event.id] = {
                'text': event.text or "<وسائط>",
                'time': time.time(),
                'sender': event.sender_id
            }
        except:
            pass

    @client.on(events.MessageEdited(incoming=True, func=lambda e: e.is_private and not e.out))
    async def notify_edit(event):
        """إشعار بتعديل رسالة في الخاص"""
        try:
            me = await client.get_me()
            if event.sender_id == me.id:
                return
            
            user = await event.get_sender()
            name = user.first_name or ""
            if user.last_name:
                name += f" {user.last_name}"
            
            old_text = "نص غير معروف"
            if event.chat_id in message_cache and event.id in message_cache[event.chat_id]:
                old_text = message_cache[event.chat_id][event.id]['text']
            
            new_text = event.text or "<وسائط>"
            
            await client.send_message(
                "me",
                f"**📝 قام {name} بتعديل رسالة**\n\n"
                f"**النص القديم:** {old_text}\n"
                f"**النص الجديد:** {new_text}"
            )
            
            # تحديث الكاش
            if event.chat_id not in message_cache:
                message_cache[event.chat_id] = {}
            message_cache[event.chat_id][event.id] = {
                'text': new_text,
                'time': time.time(),
                'sender': event.sender_id
            }
            
        except Exception as e:
            logger.error(f"فشل إشعار التعديل: {e}")

    @client.on(events.MessageDeleted(incoming=True, func=lambda e: e.is_private and not e.out))
    async def notify_delete(event):
        """إشعار بحذف رسالة في الخاص"""
        try:
            for chat_id, msg_ids in event.deleted_ids.items():
                for msg_id in msg_ids:
                    if chat_id in message_cache and msg_id in message_cache[chat_id]:
                        old_text = message_cache[chat_id][msg_id]['text']
                        
                        # الحصول على اسم المستخدم
                        user_name = "مستخدم"
                        try:
                            chat = await client.get_entity(chat_id)
                            user_name = chat.first_name or "مستخدم"
                        except:
                            pass
                        
                        await client.send_message(
                            "me",
                            f"**🗑️ قام {user_name} بحذف رسالة**\n\n"
                            f"**النص:** {old_text}"
                        )
                        
                        # حذف من الكاش
                        del message_cache[chat_id][msg_id]
        except Exception as e:
            logger.error(f"فشل إشعار الحذف: {e}")

    logger.info(f"✅ تم إعداد جميع المعالجات لـ {phone}")
