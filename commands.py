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
import tempfile
import json
from concurrent.futures import ThreadPoolExecutor
from telethon import events
from telethon.errors import FloodWaitError, ChatAdminRequiredError
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon.tl.types import (
    InputPhoto, DocumentAttributeAudio, DocumentAttributeVideo
)
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.messages import AddChatUserRequest
from shared import (
    active_clients, muted_users, taqleed_users, ent7al_users, ent7al_original,
    client_me, track_command, logger, TEMP_DIR
)

# ============== استيراد المكتبات ==============
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("⚠️ Pillow غير مثبتة")

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False
    logger.warning("⚠️ SpeechRecognition غير مثبتة")

try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False
    logger.warning("⚠️ yt-dlp غير مثبتة")

# ThreadPoolExecutor
_DOWNLOAD_EXECUTOR = ThreadPoolExecutor(max_workers=3, thread_name_prefix="dl")

# متغيرات مراقبة الخاص
message_cache = {}

# متغيرات التحكم في الأنميات
active_animations = {}

# الحد الأدنى للمساحة
MIN_FREE_SPACE_MB = 50

# ============== دوال إدارة المساحة ==============
def get_free_space_mb():
    try:
        temp_dir = TEMP_DIR if TEMP_DIR and os.path.exists(TEMP_DIR) else '/'
        disk_usage = shutil.disk_usage(temp_dir)
        return disk_usage.free / (1024 * 1024)
    except:
        return 999

def check_disk_space(min_mb=MIN_FREE_SPACE_MB):
    free_mb = get_free_space_mb()
    if free_mb < min_mb:
        clean_temp_files()
        free_mb = get_free_space_mb()
    return free_mb >= min_mb, free_mb

def clean_temp_files():
    cleaned = 0
    freed = 0
    if TEMP_DIR and os.path.exists(TEMP_DIR):
        for f in os.listdir(TEMP_DIR):
            fp = os.path.join(TEMP_DIR, f)
            if os.path.isfile(fp):
                try:
                    sz = os.path.getsize(fp)
                    os.remove(fp)
                    cleaned += 1
                    freed += sz
                except:
                    continue
    try:
        tmp = tempfile.gettempdir()
        for f in os.listdir(tmp):
            if f.startswith(('voice_', 'img_', 'sticker_', 'audio_', 'video_')):
                fp = os.path.join(tmp, f)
                if os.path.isfile(fp):
                    try:
                        sz = os.path.getsize(fp)
                        os.remove(fp)
                        cleaned += 1
                        freed += sz
                    except:
                        continue
    except:
        pass
    if cleaned > 0:
        logger.info(f"🧹 تنظيف: {cleaned} ملف, {freed/(1024*1024):.1f}MB")
    return cleaned, freed

def safe_remove(filepath):
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            return True
    except:
        pass
    return False

# ============== دوال التنسيق ==============
def format_duration(seconds):
    if not seconds: return "0:00"
    mins, secs = divmod(int(seconds), 60)
    return f"{mins}:{secs:02d}"

def format_size(bytes_size):
    if bytes_size == 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"

def clean_filename(name):
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name[:100]

# ============== دوال الأنيمشن المتحركة ==============
def create_animation_pattern(emoji_list):
    """إنشاء نمط الأنيمشن من قائمة الإيموجي"""
    patterns = []
    for i in range(len(emoji_list)):
        shifted = emoji_list[i:] + emoji_list[:i]
        patterns.append(''.join(shifted))
    return patterns

# تعريف أنماط الإيموجي لكل أمر
ANIMATION_PATTERNS = {
    'ضحك': create_animation_pattern(['😂', '🤣', '😂', '🤣']),
    'قلب': create_animation_pattern(['❤️', '💛', '💚', '💜']),
    'غيمة': create_animation_pattern(['☁️', '🌧️', '⛅', '🌩️']),
    'ورد': create_animation_pattern(['🌸', '🌹', '🌻', '🌺']),
    'كوكب': create_animation_pattern(['✨', '🌍', '🪐', '🌙']),
    'شتاء': create_animation_pattern(['⛄', '❄️', '☂️', '🌙']),
    'قمر': create_animation_pattern(['🌕', '🌖', '🌗', '🌘']),
}

async def run_animation(event, animation_name, duration=5):
    """تشغيل الأنيمشن لمدة محددة"""
    if animation_name not in ANIMATION_PATTERNS:
        return
    
    patterns = ANIMATION_PATTERNS[animation_name]
    chat_id = event.chat_id
    message = await event.get_reply_message() if event.is_reply else None
    
    # علامة للتحكم في الإيقاف
    anim_key = f"{chat_id}_{animation_name}"
    active_animations[anim_key] = True
    
    start_time = time.time()
    
    try:
        while active_animations.get(anim_key, False):
            for pattern in patterns:
                if not active_animations.get(anim_key, False):
                    break
                
                try:
                    if message:
                        await message.edit(pattern)
                    else:
                        await event.edit(pattern)
                    
                    await asyncio.sleep(0.5)
                    
                    # التوقف بعد المدة المحددة
                    if time.time() - start_time >= duration:
                        active_animations[anim_key] = False
                        break
                        
                except FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    logger.error(f"خطأ في الأنيمشن: {e}")
                    active_animations[anim_key] = False
                    break
                    
    except Exception as e:
        logger.error(f"خطأ في تشغيل الأنيمشن {animation_name}: {e}")
    finally:
        # تنظيف
        if anim_key in active_animations:
            del active_animations[anim_key]

# ============== دوال البحث عن الصور - المحسنة ==============
def search_images_google_direct(query: str, limit: int = 10) -> list:
    """البحث عن صور في جوجل مباشرة"""
    images = []
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ar,en-US;q=0.7,en;q=0.3',
        }
        
        url = f"https://www.google.com/search?q={requests.utils.quote(query)}&tbm=isch&hl=ar&safe=active"
        resp = requests.get(url, headers=headers, timeout=15)
        
        if resp.status_code == 200:
            urls = re.findall(r'data-src="(https?://[^"]+)"', resp.text)
            if not urls:
                urls = re.findall(r'"(https?://[^"]+\.(?:jpg|jpeg|png|webp|gif|bmp)[^"]*)"', resp.text, re.I)
            
            for url in urls:
                if url.startswith('http') and 'google' not in url.lower() and 'gstatic' not in url.lower():
                    if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']):
                        images.append(url)
                        if len(images) >= limit:
                            break
            
            logger.info(f"Google Images: تم العثور على {len(images)} صورة")
            
    except Exception as e:
        logger.error(f"خطأ في البحث عن صور جوجل: {e}")
    
    return images

def search_images_bing(query: str, limit: int = 10) -> list:
    """البحث عن صور في Bing"""
    images = []
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        }
        
        url = f"https://www.bing.com/images/search?q={requests.utils.quote(query)}&first=1&count={limit}"
        resp = requests.get(url, headers=headers, timeout=15)
        
        if resp.status_code == 200:
            urls = re.findall(r'<img[^>]+src="([^"]+)"', resp.text)
            
            for url in urls:
                if url.startswith('http') and 'bing.com' not in url.lower():
                    images.append(url)
                    if len(images) >= limit:
                        break
            
            logger.info(f"Bing Images: تم العثور على {len(images)} صورة")
            
    except Exception as e:
        logger.error(f"خطأ في البحث عن صور Bing: {e}")
    
    return images

def search_images_ddg(query: str, limit: int = 10) -> list:
    """البحث عن صور في DuckDuckGo"""
    images = []
    
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.images(query, max_results=limit))
            images = [img["image"] for img in results if img.get("image")]
        logger.info(f"DuckDuckGo: تم العثور على {len(images)} صورة")
    except ImportError:
        logger.warning("مكتبة duckduckgo_search غير مثبتة")
    except Exception as e:
        logger.error(f"خطأ في البحث عن صور DuckDuckGo: {e}")
    
    return images

def search_images_pixabay(query: str, limit: int = 10) -> list:
    """البحث عن صور في Pixabay"""
    images = []
    
    try:
        api_key = "25564984-2e3f8b5f6b6f6e5e5e5e5e5e"
        
        url = "https://pixabay.com/api/"
        params = {
            "key": api_key,
            "q": query,
            "image_type": "photo",
            "per_page": limit,
            "safesearch": "true",
            "orientation": "all",
        }
        
        resp = requests.get(url, params=params, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            for hit in data.get("hits", []):
                if "webformatURL" in hit:
                    images.append(hit["webformatURL"])
            
            logger.info(f"Pixabay: تم العثور على {len(images)} صورة")
            
    except Exception as e:
        logger.error(f"خطأ في البحث عن صور Pixabay: {e}")
    
    return images

def search_images_unsplash(query: str, limit: int = 10) -> list:
    """البحث عن صور في Unsplash"""
    images = []
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        }
        
        url = f"https://unsplash.com/napi/search/photos?query={requests.utils.quote(query)}&per_page={limit}"
        resp = requests.get(url, headers=headers, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            for result in data.get("results", []):
                if "urls" in result and "regular" in result["urls"]:
                    images.append(result["urls"]["regular"])
            
            logger.info(f"Unsplash: تم العثور على {len(images)} صورة")
            
    except Exception as e:
        logger.error(f"خطأ في البحث عن صور Unsplash: {e}")
    
    return images

def search_all_images(query: str, limit: int = 5) -> list:
    """البحث عن صور من جميع المصادر"""
    all_images = []
    
    search_engines = [
        ("Google", search_images_google_direct),
        ("Bing", search_images_bing),
        ("DuckDuckGo", search_images_ddg),
        ("Pixabay", search_images_pixabay),
        ("Unsplash", search_images_unsplash),
    ]
    
    for engine_name, search_func in search_engines:
        try:
            logger.info(f"جاري البحث في {engine_name}...")
            images = search_func(query, limit=10)
            
            if images:
                all_images.extend(images)
                logger.info(f"✅ {engine_name}: {len(images)} صورة")
                
                if len(all_images) >= limit:
                    break
                    
        except Exception as e:
            logger.error(f"❌ فشل البحث في {engine_name}: {e}")
            continue
    
    seen = set()
    unique_images = []
    for url in all_images:
        if url not in seen:
            seen.add(url)
            unique_images.append(url)
    
    logger.info(f"إجمالي الصور الفريدة: {len(unique_images)}")
    
    return unique_images[:limit]

# ============== دوال تحميل الصور ==============
def download_image_direct(url: str, out_dir: str) -> str:
    """تحميل صورة مباشرة"""
    has_space, free_mb = check_disk_space(10)
    if not has_space:
        clean_temp_files()
        has_space, free_mb = check_disk_space(10)
        if not has_space:
            return None
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'image/webp,image/*,*/*;q=0.8',
            'Referer': 'https://www.google.com/',
        }
        
        resp = requests.get(url, headers=headers, stream=True, timeout=30, allow_redirects=True)
        
        if resp.status_code != 200:
            logger.warning(f"فشل تحميل الصورة: {url} - Status: {resp.status_code}")
            return None
        
        content_type = resp.headers.get('content-type', '').lower()
        ext = '.jpg'
        if 'png' in content_type:
            ext = '.png'
        elif 'webp' in content_type:
            ext = '.webp'
        elif 'gif' in content_type:
            ext = '.gif'
        elif 'jpeg' in content_type or 'jpg' in content_type:
            ext = '.jpg'
        else:
            url_ext = os.path.splitext(url.split('?')[0])[1].lower()
            if url_ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']:
                ext = url_ext
        
        timestamp = int(time.time() * 1000)
        filename = f"img_{timestamp}_{hashlib.md5(url.encode()).hexdigest()[:8]}{ext}"
        filepath = os.path.join(out_dir, filename)
        
        total_size = 0
        with open(filepath, 'wb') as f:
            for chunk in resp.iter_content(8192):
                if chunk:
                    f.write(chunk)
                    total_size += len(chunk)
                    if total_size > 10 * 1024 * 1024:
                        safe_remove(filepath)
                        logger.warning(f"الصورة كبيرة جداً: {url}")
                        return None
        
        if total_size < 512:
            safe_remove(filepath)
            logger.warning(f"الصورة صغيرة جداً: {url}")
            return None
        
        logger.info(f"✅ تم تحميل الصورة: {filename} ({format_size(total_size)})")
        return filepath
        
    except requests.Timeout:
        logger.warning(f"انتهت مهلة تحميل الصورة: {url}")
        return None
    except Exception as e:
        logger.error(f"فشل تحميل الصورة: {e}")
        return None

# ============== دوال التحميل من يوتيوب ==============
def download_youtube_media(query: str, out_dir: str, audio_only: bool = False):
    """تحميل من يوتيوب مع استخراج المعلومات الصحيحة"""
    if not YTDLP_AVAILABLE:
        raise ValueError("مكتبة yt-dlp غير مثبتة")
    
    has_space, free_mb = check_disk_space(100)
    if not has_space:
        raise ValueError(f"المساحة غير كافية. المتاح: {free_mb:.1f}MB")
    
    if not query.startswith("http"):
        query = f"ytsearch:{query}"
    
    timestamp = int(time.time())
    
    if audio_only:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(out_dir, f'audio_{timestamp}.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
            'max_filesize': 50 * 1024 * 1024,
            'extract_flat': False,
        }
    else:
        ydl_opts = {
            'format': 'best[height<=720]/best',
            'outtmpl': os.path.join(out_dir, f'video_{timestamp}.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'max_filesize': 100 * 1024 * 1024,
            'merge_output_format': 'mp4',
            'extract_flat': False,
        }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(query, download=False)
            
            if 'entries' in info_dict:
                info_dict = info_dict['entries'][0]
            
            title = info_dict.get('title', 'بدون عنوان')
            uploader = info_dict.get('uploader', 'غير معروف')
            duration = info_dict.get('duration', 0)
            
            logger.info(f"تم استخراج المعلومات: {title} - {uploader} - {duration}s")
            
            info_dict = ydl.extract_info(query, download=True)
            
            prefix = 'audio_' if audio_only else 'video_'
            files = [f for f in os.listdir(out_dir) if f.startswith(f'{prefix}{timestamp}')]
            
            if not files:
                raise ValueError("لم يتم العثور على الملف المحمل")
            
            filepath = os.path.join(out_dir, files[0])
            
            if not os.path.exists(filepath) or os.path.getsize(filepath) < 1024:
                raise ValueError("الملف تالف")
            
            if duration == 0 and 'duration' in info_dict:
                duration = info_dict.get('duration', 0)
            
            return {
                'title': title,
                'uploader': uploader,
                'duration': duration,
                'duration_str': format_duration(duration),
                'size': os.path.getsize(filepath),
                'size_str': format_size(os.path.getsize(filepath)),
            }, filepath
            
    except Exception as e:
        prefix = 'audio_' if audio_only else 'video_'
        for f in os.listdir(out_dir):
            if f.startswith(f'{prefix}{timestamp}'):
                safe_remove(os.path.join(out_dir, f))
        raise ValueError(f"فشل التحميل: {str(e)[:200]}")

# ============== دالة تحويل الفيديو إلى صوت ==============
def convert_video_to_audio(video_path: str, out_dir: str):
    """تحويل ملف فيديو إلى صوت MP3"""
    if not os.path.exists(video_path):
        raise ValueError("ملف الفيديو غير موجود")
    
    has_space, free_mb = check_disk_space(30)
    if not has_space:
        raise ValueError(f"المساحة غير كافية. المتاح: {free_mb:.1f}MB")
    
    timestamp = int(time.time())
    audio_filename = f"audio_conv_{timestamp}.mp3"
    audio_path = os.path.join(out_dir, audio_filename)
    
    try:
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vn',
            '-acodec', 'libmp3lame',
            '-ab', '192k',
            '-ar', '44100',
            '-y',
            audio_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        
        if result.returncode != 0:
            error_msg = result.stderr.decode()[:200] if result.stderr else "خطأ غير معروف"
            raise ValueError(f"فشل تحويل الفيديو إلى صوت: {error_msg}")
        
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) < 1024:
            raise ValueError("الملف الصوتي الناتج تالف")
        
        duration = 0
        try:
            probe_cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ]
            probe_result = subprocess.run(probe_cmd, capture_output=True, timeout=10)
            if probe_result.returncode == 0:
                duration = float(probe_result.stdout.decode().strip())
        except:
            pass
        
        return {
            'path': audio_path,
            'duration': duration,
            'duration_str': format_duration(duration),
            'size': os.path.getsize(audio_path),
            'size_str': format_size(os.path.getsize(audio_path)),
        }
        
    except subprocess.TimeoutExpired:
        safe_remove(audio_path)
        raise ValueError("انتهت مهلة تحويل الفيديو")
    except Exception as e:
        safe_remove(audio_path)
        raise ValueError(f"فشل تحويل الفيديو: {str(e)[:200]}")

# ============== دوال الانتحال ==============
async def get_user_info_full(client, user_id):
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
        logger.error(f"فشل جلب معلومات المستخدم: {e}")
        return None

async def change_profile_photo(client, user_id, phone):
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
        
    except FloodWaitError as e:
        logger.warning(f"Flood wait {e.seconds}s")
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
        except:
            return False, None
    except Exception as e:
        logger.error(f"فشل تغيير الصورة: {e}")
        return False, None

# ============== إعداد المعالجات ==============
async def setup_handlers(client, phone):
    
    # تهيئة المتغيرات
    if phone not in muted_users:
        muted_users[phone] = {}
    if phone not in taqleed_users:
        taqleed_users[phone] = {}
    if phone not in ent7al_users:
        ent7al_users[phone] = False
    if phone not in ent7al_original:
        ent7al_original[phone] = {}

    # ============== أوامر الأنيمشن ==============
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ضحك$'))
    async def laugh_animation(event):
        """أنيمشن الضحك"""
        await event.edit("**• 😂 جاري تشغيل أنيمشن الضحك...**")
        asyncio.create_task(run_animation(event, 'ضحك', duration=5))

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.قلب$'))
    async def heart_animation(event):
        """أنيمشن القلب"""
        await event.edit("**• ❤️ جاري تشغيل أنيمشن القلب...**")
        asyncio.create_task(run_animation(event, 'قلب', duration=5))

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غيمة$'))
    async def cloud_animation(event):
        """أنيمشن الغيمة"""
        await event.edit("**• ☁️ جاري تشغيل أنيمشن الغيمة...**")
        asyncio.create_task(run_animation(event, 'غيمة', duration=5))

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ورد$'))
    async def flower_animation(event):
        """أنيمشن الورد"""
        await event.edit("**• 🌸 جاري تشغيل أنيمشن الورد...**")
        asyncio.create_task(run_animation(event, 'ورد', duration=5))

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.كوكب$'))
    async def planet_animation(event):
        """أنيمشن الكوكب"""
        await event.edit("**• ✨ جاري تشغيل أنيمشن الكوكب...**")
        asyncio.create_task(run_animation(event, 'كوكب', duration=5))

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.شتاء$'))
    async def winter_animation(event):
        """أنيمشن الشتاء"""
        await event.edit("**• ⛄ جاري تشغيل أنيمشن الشتاء...**")
        asyncio.create_task(run_animation(event, 'شتاء', duration=5))

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.قمر$'))
    async def moon_animation(event):
        """أنيمشن القمر"""
        await event.edit("**• 🌕 جاري تشغيل أنيمشن القمر...**")
        asyncio.create_task(run_animation(event, 'قمر', duration=5))

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.وقف$'))
    async def stop_animation(event):
        """إيقاف جميع الأنيمشن"""
        # إيقاف كل الأنيمشن النشطة
        stopped = 0
        for key in list(active_animations.keys()):
            if key.startswith(str(event.chat_id)):
                active_animations[key] = False
                stopped += 1
        
        if stopped > 0:
            await event.edit(f"**• ⏹️ تم إيقاف {stopped} أنيمشن**")
        else:
            await event.edit("**• ❌ لا يوجد أنيمشن نشط**")

    # ============== أمر .المساحة ==============
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.المساحة$'))
    async def space_check(event):
        await event.edit("**• 📊 جاري فحص المساحة...**")
        
        free_mb = get_free_space_mb()
        cleaned, freed = clean_temp_files()
        free_after = get_free_space_mb()
        
        msg = "**📊 حالة التخزين:**\n"
        msg += f"**• المساحة المتاحة:** {free_after:.1f} MB\n"
        
        if cleaned > 0:
            msg += f"**• 🧹 تم تنظيف {cleaned} ملف**\n"
            msg += f"**• 💾 تم تحرير: {format_size(freed)}**\n"
        
        if free_after < MIN_FREE_SPACE_MB:
            msg += "\n⚠️ **تحذير: المساحة منخفضة!**"
        else:
            msg += "\n✅ **المساحة كافية**"
        
        await event.edit(msg)

    # ============== أمر .تنظيف ==============
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تنظيف$'))
    async def force_clean(event):
        await event.edit("**• 🧹 جاري التنظيف...**")
        
        c1, s1 = clean_temp_files()
        await asyncio.sleep(1)
        c2, s2 = clean_temp_files()
        
        total_cleaned = c1 + c2
        total_freed = s1 + s2
        free_mb = get_free_space_mb()
        
        msg = "**✅ تم التنظيف:**\n"
        msg += f"**• الملفات المحذوفة:** {total_cleaned}\n"
        msg += f"**• المساحة المحررة:** {format_size(total_freed)}\n"
        msg += f"**• المساحة المتاحة الآن:** {free_mb:.1f} MB"
        
        await event.edit(msg)

    # ============== أمر .يوت (تحميل صوت) ==============
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.يوت (.+)'))
    async def youtube_audio(event):
        if not YTDLP_AVAILABLE:
            await event.edit("**• ❌ مكتبة yt-dlp غير مثبتة**\n**• استخدم: `pip install yt-dlp`**")
            return
        
        query = event.pattern_match.group(1).strip()
        
        has_space, free_mb = check_disk_space(80)
        if not has_space:
            await event.edit(f"**• ❌ المساحة غير كافية ({free_mb:.1f}MB)**\n**• استخدم .تنظيف**")
            return
        
        await event.edit("**• 🎵 جاري تحميل الصوت...**")
        
        filepath = None
        
        try:
            info, filepath = await asyncio.get_event_loop().run_in_executor(
                _DOWNLOAD_EXECUTOR, download_youtube_media, query, TEMP_DIR, True
            )
            
            title = info['title']
            if len(title) > 55:
                title = title[:52] + '...'
            dur = info['duration_str']
            caption = f"{title}\n• {dur} | ᥲᥙძᎥ᥆"
            
            await client.send_file(
                event.chat_id,
                filepath,
                caption=caption,
                attributes=[
                    DocumentAttributeAudio(
                        duration=info['duration'],
                        title=info['title'],
                        performer=info['uploader']
                    )
                ],
                supports_streaming=True
            )
            
            await event.delete()
            
        except Exception as e:
            await event.edit(f"**• ❌ {str(e)[:200]}**")
        finally:
            safe_remove(filepath)
            clean_temp_files()

    # ============== أمر .فيد (تحميل فيديو) ==============
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.فيد (.+)'))
    async def video_download(event):
        if not YTDLP_AVAILABLE:
            await event.edit("**• ❌ مكتبة yt-dlp غير مثبتة**\n**• استخدم: `pip install yt-dlp`**")
            return
        
        query = event.pattern_match.group(1).strip()
        
        has_space, free_mb = check_disk_space(150)
        if not has_space:
            await event.edit(f"**• ❌ المساحة غير كافية ({free_mb:.1f}MB)**\n**• استخدم .تنظيف**")
            return
        
        await event.edit("**• 🎬 جاري تحميل الفيديو...**")
        
        filepath = None
        
        try:
            info, filepath = await asyncio.get_event_loop().run_in_executor(
                _DOWNLOAD_EXECUTOR, download_youtube_media, query, TEMP_DIR, False
            )
            
            title = info['title']
            if len(title) > 55:
                title = title[:52] + '...'
            dur = info['duration_str']
            caption = f"{title}\n• {dur} | ᥎Ꭵძꫀ᥆"
            
            await client.send_file(
                event.chat_id,
                filepath,
                caption=caption,
                attributes=[
                    DocumentAttributeVideo(
                        duration=info['duration'],
                        w=0,
                        h=0,
                        supports_streaming=True
                    )
                ],
                supports_streaming=True
            )
            
            await event.delete()
            
        except Exception as e:
            await event.edit(f"**• ❌ {str(e)[:200]}**")
        finally:
            safe_remove(filepath)
            clean_temp_files()

    # ============== أمر .صوت (تحويل فيديو إلى صوت) ==============
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.صوت$'))
    async def video_to_audio(event):
        if not event.is_reply:
            await event.edit("**• ❌ يرجى الرد على فيديو**")
            return
        
        reply = await event.get_reply_message()
        
        if not (reply.video or reply.document):
            await event.edit("**• ❌ يرجى الرد على فيديو فقط**")
            return
        
        if reply.document:
            mime_type = reply.document.mime_type or ''
            if not mime_type.startswith('video/'):
                await event.edit("**• ❌ الملف المردود عليه ليس فيديو**")
                return
        
        has_space, free_mb = check_disk_space(30)
        if not has_space:
            await event.edit(f"**• ❌ المساحة غير كافية ({free_mb:.1f}MB)**\n**• استخدم .تنظيف**")
            return
        
        await event.edit("**• 🎵 جاري تحويل الفيديو إلى صوت...**")
        
        video_path = None
        audio_path = None
        
        try:
            video_filename = f"video_conv_{phone}_{int(time.time())}"
            if reply.video:
                video_filename += ".mp4"
            else:
                ext = os.path.splitext(reply.document.attributes[0].file_name or '')[-1] or '.mp4'
                video_filename += ext
            
            video_path = os.path.join(TEMP_DIR, video_filename)
            await client.download_media(reply, video_path)
            
            if not os.path.exists(video_path) or os.path.getsize(video_path) < 1024:
                raise ValueError("فشل تحميل الفيديو")
            
            original_name = "فيديو"
            if reply.video and hasattr(reply, 'message') and reply.message:
                original_name = reply.message[:100]
            elif reply.document:
                for attr in reply.document.attributes:
                    if hasattr(attr, 'file_name') and attr.file_name:
                        original_name = os.path.splitext(attr.file_name)[0]
                        break
            
            audio_info = await asyncio.get_event_loop().run_in_executor(
                _DOWNLOAD_EXECUTOR, convert_video_to_audio, video_path, TEMP_DIR
            )
            
            audio_path = audio_info['path']
            
            title = clean_filename(original_name)
            if len(title) > 55:
                title = title[:52] + '...'
            dur = audio_info['duration_str']
            caption = f"{title}\n• {dur} | 🎵 ᥲᥙძᎥ᥆ (محول من فيديو)"
            
            await client.send_file(
                event.chat_id,
                audio_path,
                caption=caption,
                attributes=[
                    DocumentAttributeAudio(
                        duration=int(audio_info['duration']),
                        title=title,
                        performer='محول من فيديو'
                    )
                ],
                supports_streaming=True
            )
            
            await event.delete()
            
        except Exception as e:
            await event.edit(f"**• ❌ {str(e)[:200]}**")
        finally:
            safe_remove(video_path)
            safe_remove(audio_path)
            clean_temp_files()

    # ============== أمر .نسخ (تحويل صوت لنص) ==============
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.نسخ$'))
    async def transcribe_voice(event):
        if not event.is_reply:
            await event.edit("**• ❌ يرجى الرد على رسالة صوتية**")
            return
        
        reply = await event.get_reply_message()
        if not (reply.voice or reply.audio):
            await event.edit("**• ❌ الرد على رسالة صوتية فقط**")
            return
        
        has_space, free_mb = check_disk_space(30)
        if not has_space:
            await event.edit(f"**• ❌ المساحة غير كافية ({free_mb:.1f}MB)**\n**• استخدم .تنظيف**")
            return
        
        if not SR_AVAILABLE:
            await event.edit("**• ❌ مكتبة SpeechRecognition غير مثبتة**")
            return
        
        await event.edit("**• 🎤 جاري تحويل الصوت إلى نص...**")
        
        voice_path = None
        wav_path = None
        
        try:
            voice_path = os.path.join(TEMP_DIR, f"voice_{phone}_{int(time.time())}.ogg")
            await client.download_media(reply, voice_path)
            
            if not os.path.exists(voice_path) or os.path.getsize(voice_path) < 100:
                raise ValueError("فشل تحميل الملف الصوتي")
            
            wav_path = voice_path.replace('.ogg', '.wav')
            
            result = subprocess.run(
                ['ffmpeg', '-i', voice_path, '-ac', '1', '-ar', '16000', 
                 '-sample_fmt', 's16', wav_path],
                capture_output=True,
                timeout=30
            )
            
            if result.returncode != 0 or not os.path.exists(wav_path):
                raise ValueError("فشل تحويل الصوت")
            
            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_path) as source:
                audio_data = recognizer.record(source)
            
            text = None
            for lang in ['ar-AR', 'en-US']:
                try:
                    text = recognizer.recognize_google(audio_data, language=lang)
                    break
                except:
                    continue
            
            if text:
                await event.edit(f"**📝 النص:**\n{text}")
            else:
                await event.edit("**• ❌ لم يتم التعرف على أي نص**")
                
        except subprocess.CalledProcessError as e:
            error_text = e.stderr.decode()[:100] if e.stderr else str(e)
            await event.edit(f"**• ❌ فشل التحويل: {error_text}**")
        except Exception as e:
            await event.edit(f"**• ❌ {str(e)[:150]}**")
        finally:
            safe_remove(voice_path)
            safe_remove(wav_path)
            clean_temp_files()

    # ============== أمر .استيك (صورة إلى استيكر) ==============
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.استيك$'))
    async def photo_to_sticker(event):
        if not event.is_reply:
            await event.edit("**• ❌ يرجى الرد على صورة**")
            return
        
        reply = await event.get_reply_message()
        if not reply.photo:
            await event.edit("**• ❌ الرد على صورة فقط**")
            return
        
        if not PIL_AVAILABLE:
            await event.edit("**• ❌ مكتبة Pillow غير مثبتة**")
            return
        
        has_space, free_mb = check_disk_space(10)
        if not has_space:
            await event.edit(f"**• ❌ المساحة غير كافية ({free_mb:.1f}MB)**")
            return
        
        await event.edit("**• 🔄 جاري التحويل...**")
        
        img_path = None
        stick_path = None
        
        try:
            img_path = os.path.join(TEMP_DIR, f"img_{phone}_{int(time.time())}.jpg")
            await client.download_media(reply, img_path)
            
            if not os.path.exists(img_path):
                raise ValueError("فشل تحميل الصورة")
            
            stick_path = img_path.replace('.jpg', '.webp')
            
            im = Image.open(img_path).convert("RGBA")
            im.thumbnail((512, 512), Image.LANCZOS)
            im.save(stick_path, "WEBP", quality=80)
            
            if os.path.exists(stick_path) and os.path.getsize(stick_path) > 0:
                await client.send_file(event.chat_id, stick_path, force_document=False)
                await event.delete()
            else:
                await event.edit("**• ❌ فشل إنشاء الاستيكر**")
                
        except Exception as e:
            await event.edit(f"**• ❌ {str(e)[:150]}**")
        finally:
            safe_remove(img_path)
            safe_remove(stick_path)

    # ============== أمر .بيك (استيكر إلى صورة) ==============
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بيك$'))
    async def sticker_to_photo(event):
        if not event.is_reply:
            await event.edit("**• ❌ يرجى الرد على استيكر**")
            return
        
        reply = await event.get_reply_message()
        if not reply.sticker:
            await event.edit("**• ❌ الرد على استيكر فقط**")
            return
        
        if not PIL_AVAILABLE:
            await event.edit("**• ❌ مكتبة Pillow غير مثبتة**")
            return
        
        has_space, free_mb = check_disk_space(10)
        if not has_space:
            await event.edit(f"**• ❌ المساحة غير كافية ({free_mb:.1f}MB)**")
            return
        
        await event.edit("**• 🔄 جاري التحويل...**")
        
        stick_path = None
        img_path = None
        
        try:
            stick_path = os.path.join(TEMP_DIR, f"sticker_{phone}_{int(time.time())}.webp")
            await client.download_media(reply, stick_path)
            
            if not os.path.exists(stick_path):
                raise ValueError("فشل تحميل الاستيكر")
            
            img_path = stick_path.replace('.webp', '.png')
            
            im = Image.open(stick_path).convert("RGBA")
            im.save(img_path, "PNG")
            
            if os.path.exists(img_path) and os.path.getsize(img_path) > 0:
                await client.send_file(event.chat_id, img_path)
                await event.delete()
            else:
                await event.edit("**• ❌ فشل التحويل**")
                
        except Exception as e:
            await event.edit(f"**• ❌ {str(e)[:150]}**")
        finally:
            safe_remove(stick_path)
            safe_remove(img_path)

    # ============== أمر .بن (تحميل صور) - المحسن ==============
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بن (.+)'))
    async def image_search_download(event):
        query = event.pattern_match.group(1).strip()
        
        has_space, free_mb = check_disk_space(20)
        if not has_space:
            await event.edit(f"**• ❌ المساحة غير كافية ({free_mb:.1f}MB)**\n**• استخدم .تنظيف**")
            return
        
        if query.startswith('http'):
            await event.edit("**• 📷 جاري تحميل الصورة...**")
            
            try:
                filepath = await asyncio.get_event_loop().run_in_executor(
                    _DOWNLOAD_EXECUTOR, download_image_direct, query, TEMP_DIR
                )
                
                if filepath and os.path.exists(filepath):
                    await client.send_file(event.chat_id, filepath)
                    await event.delete()
                    safe_remove(filepath)
                else:
                    await event.edit("**• ❌ فشل تحميل الصورة - تأكد من الرابط**")
                    
            except Exception as e:
                await event.edit(f"**• ❌ {str(e)[:150]}**")
            return
        
        await event.edit("**• 🔍 جاري البحث في محركات البحث...**")
        
        urls = await asyncio.get_event_loop().run_in_executor(
            _DOWNLOAD_EXECUTOR, search_all_images, query, 5
        )
        
        if not urls:
            await event.edit("**• ❌ لم يتم العثور على صور**\n**• جرب كلمات بحث مختلفة**")
            return
        
        await event.edit(f"**• ✅ تم العثور على {len(urls)} صورة**\n**• 📥 جاري التحميل...**")
        
        success = 0
        downloaded_paths = []
        
        for i, url in enumerate(urls, 1):
            try:
                await event.edit(f"**• 📥 جاري تحميل الصورة {i}/{len(urls)}...**")
                
                filepath = await asyncio.get_event_loop().run_in_executor(
                    _DOWNLOAD_EXECUTOR, download_image_direct, url, TEMP_DIR
                )
                
                if filepath and os.path.exists(filepath):
                    downloaded_paths.append(filepath)
                    success += 1
                
                if success >= 3:
                    break
                    
                await asyncio.sleep(0.3)
                
            except Exception as e:
                logger.error(f"فشل تحميل الصورة {i}: {e}")
                continue
        
        if downloaded_paths:
            await event.edit(f"**• 📤 جاري إرسال {len(downloaded_paths)} صورة...**")
            
            for filepath in downloaded_paths:
                try:
                    await client.send_file(event.chat_id, filepath)
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"فشل إرسال الصورة: {e}")
                finally:
                    safe_remove(filepath)
            
            await event.delete()
        else:
            await event.edit("**• ❌ فشل تحميل جميع الصور**\n**• جرب البحث عن شيء آخر**")

    # ============== التقليد ==============
    @client.on(events.NewMessage(incoming=True))
    async def auto_taqleed(event):
        if event.sender_id in taqleed_users.get(phone, {}) and event.text and not event.text.startswith('.'):
            await asyncio.sleep(0.5)
            try:
                await event.reply(event.text)
            except:
                pass

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تقليد$'))
    async def taq(event):
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
            await event.edit("**• ❌ يرجى الرد على رسالة**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غ تقليد$'))
    async def notaq(event):
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

    # ============== الانتحال ==============
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.انتحال$'))
    async def ent7al(event):
        track_command(phone, ".انتحال")
        await event.edit("**• 🔄 جاري الانتحال...**")
        
        target_user = None
        if event.is_reply:
            try:
                reply = await event.get_reply_message()
                target_user = await client.get_entity(reply.sender_id)
            except:
                pass
        elif event.is_private:
            try:
                target_user = await client.get_entity(event.chat_id)
            except:
                pass
        
        if not target_user:
            await event.edit("**• ❌ فشل الانتحال**")
            return
        
        target_info = await get_user_info_full(client, target_user.id)
        if not target_info:
            await event.edit("**• ❌ فشل جلب معلومات المستخدم**")
            return
        
        me = await client.get_me()
        client_me[phone] = me
        
        original = {
            'first_name': me.first_name or '',
            'last_name': me.last_name if me.last_name is not None else '',
            'about': '',
            'added_photo_id': None
        }
        
        try:
            fu = await client(GetFullUserRequest('me'))
            if fu.full_user.about:
                original['about'] = fu.full_user.about
        except:
            pass
        
        name_ok = False
        try:
            await client(UpdateProfileRequest(
                first_name=target_info['first_name'],
                last_name=target_info['last_name']
            ))
            await asyncio.sleep(1)
            name_ok = True
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            try:
                await client(UpdateProfileRequest(
                    first_name=target_info['first_name'],
                    last_name=target_info['last_name']
                ))
                name_ok = True
            except:
                pass
        except:
            pass
        
        bio_ok = False
        try:
            await client(UpdateProfileRequest(about=target_info['bio'][:70] if target_info['bio'] else ''))
            await asyncio.sleep(0.5)
            bio_ok = True
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            try:
                await client(UpdateProfileRequest(about=target_info['bio'][:70] if target_info['bio'] else ''))
                bio_ok = True
            except:
                pass
        except:
            pass
        
        photo_ok, added_id = await change_profile_photo(client, target_user.id, phone)
        if photo_ok and added_id:
            original['added_photo_id'] = added_id
        
        ent7al_original[phone] = original
        ent7al_users[phone] = True
        
        if name_ok and bio_ok and photo_ok:
            await event.edit("**• ✅ تم الانتحال**")
        elif name_ok or bio_ok or photo_ok:
            await event.edit("**• ⚠️ تم الانتحال جزئياً**")
        else:
            await event.edit("**• ❌ فشل الانتحال**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.الغاء انتحال$'))
    async def unent7al(event):
        track_command(phone, ".الغاء انتحال")
        await event.edit("**• 🔄 جاري إلغاء الانتحال...**")
        
        if not ent7al_users.get(phone) or not ent7al_original.get(phone):
            await event.edit("**• ❌ لا يوجد انتحال**")
            return
        
        original = ent7al_original[phone]
        
        for attempt in range(3):
            try:
                await client(UpdateProfileRequest(
                    first_name=original.get('first_name', ''),
                    last_name=original.get('last_name', '')
                ))
                await asyncio.sleep(1.5)
                break
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except:
                await asyncio.sleep(1)
        
        if original.get('added_photo_id'):
            try:
                await client(DeletePhotosRequest(id=[InputPhoto(
                    id=original['added_photo_id'],
                    access_hash=0,
                    file_reference=b''
                )]))
                await asyncio.sleep(2)
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except:
                pass
        
        try:
            await client(UpdateProfileRequest(about=original.get('about', '')))
        except:
            pass
        
        ent7al_users[phone] = False
        ent7al_original[phone] = {}
        await event.edit("**• ✅ تم إلغاء الانتحال**")

    # ============== مراقبة الخاص ==============
    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private and not e.out))
    async def cache_message(event):
        try:
            me = await client.get_me()
            if event.sender_id == me.id:
                return
            
            if event.chat_id not in message_cache:
                message_cache[event.chat_id] = {}
            
            message_cache[event.chat_id][event.id] = {
                'text': event.text or "<وسائط>",
                'time': time.time()
            }
        except:
            pass

    @client.on(events.MessageEdited(incoming=True, func=lambda e: e.is_private and not e.out))
    async def notify_edit(event):
        try:
            me = await client.get_me()
            if event.sender_id == me.id:
                return
            
            user = await event.get_sender()
            name = user.first_name or ""
            if user.last_name:
                name += f" {user.last_name}"
            
            old = "نص غير معروف"
            if event.chat_id in message_cache and event.id in message_cache[event.chat_id]:
                old = message_cache[event.chat_id][event.id]['text']
            
            new = event.text or "<وسائط>"
            
            await client.send_message("me", f"**📝 {name} عدل رسالة**\n\n**من:** {old}\n**إلى:** {new}")
            
            if event.chat_id not in message_cache:
                message_cache[event.chat_id] = {}
            message_cache[event.chat_id][event.id] = {'text': new, 'time': time.time()}
            
        except:
            pass

    @client.on(events.MessageDeleted(incoming=True, func=lambda e: e.is_private and not e.out))
    async def notify_delete(event):
        try:
            for chat_id, msg_ids in event.deleted_ids.items():
                for msg_id in msg_ids:
                    if chat_id in message_cache and msg_id in message_cache[chat_id]:
                        text = message_cache[chat_id][msg_id]['text']
                        
                        user_name = "مستخدم"
                        try:
                            chat = await client.get_entity(chat_id)
                            user_name = chat.first_name or "مستخدم"
                        except:
                            pass
                        
                        await client.send_message("me", f"**🗑️ {user_name} حذف رسالة**\n\n**{text}**")
                        
                        del message_cache[chat_id][msg_id]
        except:
            pass

    # ============== تنظيف دوري ==============
    async def auto_cleanup():
        while True:
            await asyncio.sleep(1800)
            free_mb = get_free_space_mb()
            if free_mb < MIN_FREE_SPACE_MB * 2:
                count, size = clean_temp_files()
                if count > 0:
                    logger.info(f"🧹 تنظيف تلقائي: {count} ملف, {format_size(size)}")
    
    asyncio.create_task(auto_cleanup())

    logger.info(f"✅ جميع الأوامر جاهزة لـ {phone} - المساحة: {get_free_space_mb():.1f}MB")
