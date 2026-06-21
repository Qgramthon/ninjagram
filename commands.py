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
import random
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
from telethon.tl.functions.messages import AddChatUserRequest, GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
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

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False

try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False

_DOWNLOAD_EXECUTOR = ThreadPoolExecutor(max_workers=3, thread_name_prefix="dl")
message_cache = {}
active_animations = {}
MIN_FREE_SPACE_MB = 50

# ============== دوال المساحة ==============
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
    if bytes_size == 0: return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0: return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"

def clean_filename(name):
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name[:100]

# ============== دوال النصوص المزخرفة ==============
def make_bold(text):
    """تحويل النص إلى عريض"""
    bold_chars = {
        'a': '𝗮', 'b': '𝗯', 'c': '𝗰', 'd': '𝗱', 'e': '𝗲', 'f': '𝗳', 'g': '𝗴', 'h': '𝗵',
        'i': '𝗶', 'j': '𝗷', 'k': '𝗸', 'l': '𝗹', 'm': '𝗺', 'n': '𝗻', 'o': '𝗼', 'p': '𝗽',
        'q': '𝗾', 'r': '𝗿', 's': '𝘀', 't': '𝘁', 'u': '𝘂', 'v': '𝘃', 'w': '𝘄', 'x': '𝘅',
        'y': '𝘆', 'z': '𝘇', 'A': '𝗔', 'B': '𝗕', 'C': '𝗖', 'D': '𝗗', 'E': '𝗘', 'F': '𝗙',
        'G': '𝗚', 'H': '𝗛', 'I': '𝗜', 'J': '𝗝', 'K': '𝗞', 'L': '𝗟', 'M': '𝗠', 'N': '𝗡',
        'O': '𝗢', 'P': '𝗣', 'Q': '𝗤', 'R': '𝗥', 'S': '𝗦', 'T': '𝗧', 'U': '𝗨', 'V': '𝗩',
        'W': '𝗪', 'X': '𝗫', 'Y': '𝗬', 'Z': '𝗭', '0': '𝟬', '1': '𝟭', '2': '𝟮', '3': '𝟯',
        '4': '𝟰', '5': '𝟱', '6': '𝟲', '7': '𝟳', '8': '𝟴', '9': '𝟵'
    }
    return ''.join(bold_chars.get(c, c) for c in text)

def make_italic(text):
    """تحويل النص إلى مائل"""
    italic_chars = {
        'a': '𝘢', 'b': '𝘣', 'c': '𝘤', 'd': '𝘥', 'e': '𝘦', 'f': '𝘧', 'g': '𝘨', 'h': '𝘩',
        'i': '𝘪', 'j': '𝘫', 'k': '𝘬', 'l': '𝘭', 'm': '𝘮', 'n': '𝘯', 'o': '𝘰', 'p': '𝘱',
        'q': '𝘲', 'r': '𝘳', 's': '𝘴', 't': '𝘵', 'u': '𝘶', 'v': '𝘷', 'w': '𝘸', 'x': '𝘹',
        'y': '𝘺', 'z': '𝘻', 'A': '𝘈', 'B': '𝘉', 'C': '𝘊', 'D': '𝘋', 'E': '𝘌', 'F': '𝘍',
        'G': '𝘎', 'H': '𝘏', 'I': '𝘐', 'J': '𝘑', 'K': '𝘒', 'L': '𝘓', 'M': '𝘔', 'N': '𝘕',
        'O': '𝘖', 'P': '𝘗', 'Q': '𝘘', 'R': '𝘙', 'S': '𝘚', 'T': '𝘛', 'U': '𝘜', 'V': '𝘝',
        'W': '𝘞', 'X': '𝘟', 'Y': '𝘠', 'Z': '𝘡'
    }
    return ''.join(italic_chars.get(c, c) for c in text)

def make_strikethrough(text):
    """تحويل النص إلى مشطوب"""
    return ''.join(c + '̶' for c in text)

# ============== دوال النسب الوهمية ==============
def get_random_percentage():
    """نسبة عشوائية"""
    return random.randint(1, 100)

def get_love_comment(percentage):
    """تعليقات الحب"""
    if percentage >= 90:
        return "💘 حب من طرف واحد ولا اتنين يا عم"
    elif percentage >= 70:
        return "❤️‍🔥 فيه حب بس مش قد كده"
    elif percentage >= 50:
        return "💕 نص نص يا معلم"
    elif percentage >= 30:
        return "💔 الحب ضعيف شوية"
    else:
        return "💀 مفيش حب خالص يا عم"

def get_stupidity_comment(percentage):
    """تعليقات الغباء"""
    if percentage >= 90:
        return "🐄 هاتوله برسيم... شكل مفيش منك امل"
    elif percentage >= 70:
        return "🤪 غبي بس لسه فيه بصيص أمل"
    elif percentage >= 50:
        return "🤔 نص نص... مش متأكدين"
    elif percentage >= 30:
        return "🧐 لا يعم ده طلع بيفهم اهو"
    else:
        return "🧠 ده عبقري والله"

def get_lying_comment(percentage):
    """تعليقات الكذب"""
    if percentage >= 90:
        return "🤥 دنت كداب اوي يلا"
    elif percentage >= 70:
        return "😏 كداب ومحترف كمان"
    elif percentage >= 50:
        return "🤨 فيه كدب شوية"
    elif percentage >= 30:
        return "🙂 لا يعم ده غلبان صادق"
    else:
        return "😇 ده صادق جدا والله"

# ============== دوال التهكير والقتل الوهمية ==============
HACK_MESSAGES = [
    "🔓 جاري اختراق الحساب...",
    "📱 جاري الوصول للبيانات...",
    "🔑 تم كسر كلمة المرور: ******",
    "📸 جاري تحميل الصور الخاصة...",
    "💬 جاري قراءة المحادثات...",
    "📍 تم تحديد الموقع الجغرافي...",
    "💰 جاري سرقة الرصيد...",
    "✅ تم الاختراق بنجاح!",
    "😈 كنت بهزر معاك يسطا"
]

KILL_MESSAGES = [
    "🔫 جاري التصويب...",
    "💣 تم القاء قنبلة...",
    "🚀 صاروخ في الطريق...",
    "💀 الضربة القاضية...",
    "🪦 تم الدفن...",
    "👻 روحه طلعت...",
    "😇 البقاء لله...",
    "😂 كنت بهزر يا غلبان"
]

# ============== دوال الأنيمشن ==============
def create_animation_pattern(emoji_list):
    patterns = []
    for i in range(len(emoji_list)):
        shifted = emoji_list[i:] + emoji_list[:i]
        patterns.append(''.join(shifted))
    return patterns

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
    if animation_name not in ANIMATION_PATTERNS:
        return
    
    patterns = ANIMATION_PATTERNS[animation_name]
    chat_id = event.chat_id
    message = await event.get_reply_message() if event.is_reply else None
    
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
                    
                    if time.time() - start_time >= duration:
                        active_animations[anim_key] = False
                        break
                        
                except FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                except:
                    active_animations[anim_key] = False
                    break
                    
    except:
        pass
    finally:
        if anim_key in active_animations:
            del active_animations[anim_key]

# ============== دوال البحث عن الصور المحسنة ==============
def search_images_google(query: str, limit: int = 10) -> list:
    """بحث محسن في جوجل"""
    images = []
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        }
        
        # إضافة كلمة "صور" للبحث لتحسين الدقة
        search_query = f"{query} صور"
        url = f"https://www.google.com/search?q={requests.utils.quote(search_query)}&tbm=isch&hl=ar&safe=active&nfpr=1"
        resp = requests.get(url, headers=headers, timeout=15)
        
        if resp.status_code == 200:
            # استخراج روابط الصور من data-src أو src
            urls = re.findall(r'(?:data-src|src)="(https?://[^"]+\.(?:jpg|jpeg|png|webp|gif|bmp)[^"]*)"', resp.text, re.I)
            
            for url in urls:
                if 'google' not in url.lower() and 'gstatic' not in url.lower():
                    if not any(skip in url.lower() for skip in ['icon', 'avatar', 'logo', 'favicon']):
                        images.append(url)
                        if len(images) >= limit:
                            break
            
            logger.info(f"Google Images: {len(images)} صورة لـ '{query}'")
    except Exception as e:
        logger.error(f"خطأ بحث جوجل: {e}")
    
    return images

def search_images_brave(query: str, limit: int = 10) -> list:
    """بحث في Brave"""
    images = []
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        }
        
        url = f"https://search.brave.com/api/images?q={requests.utils.quote(query)}&count={limit}"
        resp = requests.get(url, headers=headers, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            for result in data.get('results', []):
                if 'url' in result:
                    images.append(result['url'])
    except:
        pass
    
    return images

def search_all_images(query: str, limit: int = 5) -> list:
    """بحث شامل مع تحسين الدقة"""
    all_images = []
    
    # محاولة DuckDuckGo أولاً (أفضل دقة)
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.images(f"{query} photo", max_results=limit))
            for img in results:
                if img.get("image"):
                    all_images.append(img["image"])
        logger.info(f"DuckDuckGo: {len(all_images)} صورة")
    except:
        pass
    
    # ثم جوجل
    if len(all_images) < limit:
        google_images = search_images_google(query, limit)
        all_images.extend(google_images)
    
    # ثم Bing
    if len(all_images) < limit:
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            url = f"https://www.bing.com/images/search?q={requests.utils.quote(query)}+image&first=1&count={limit}"
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                urls = re.findall(r'src="(https?://[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"', resp.text, re.I)
                for url in urls:
                    if 'bing' not in url.lower():
                        all_images.append(url)
        except:
            pass
    
    # إزالة التكرار
    seen = set()
    unique = []
    for url in all_images:
        if url not in seen and not any(s in url.lower() for s in ['icon', 'avatar', 'logo', 'favicon', 'thumb']):
            seen.add(url)
            unique.append(url)
    
    logger.info(f"إجمالي الصور الفريدة: {len(unique)}")
    return unique[:limit]

def download_image_direct(url: str, out_dir: str) -> str:
    """تحميل صورة"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.google.com/'}
        resp = requests.get(url, headers=headers, stream=True, timeout=30)
        if resp.status_code != 200:
            return None
        
        content_type = resp.headers.get('content-type', '').lower()
        ext = '.jpg'
        if 'png' in content_type: ext = '.png'
        elif 'webp' in content_type: ext = '.webp'
        elif 'gif' in content_type: ext = '.gif'
        
        filename = f"img_{int(time.time()*1000)}_{hashlib.md5(url.encode()).hexdigest()[:8]}{ext}"
        filepath = os.path.join(out_dir, filename)
        
        size = 0
        with open(filepath, 'wb') as f:
            for chunk in resp.iter_content(8192):
                if chunk:
                    f.write(chunk)
                    size += len(chunk)
                    if size > 10*1024*1024:
                        safe_remove(filepath)
                        return None
        
        if size < 512:
            safe_remove(filepath)
            return None
        
        return filepath
    except:
        return None

# ============== دوال يوتيوب ==============
def download_youtube_media(query: str, out_dir: str, audio_only: bool = False):
    if not YTDLP_AVAILABLE:
        raise ValueError("مكتبة yt-dlp غير مثبتة")
    
    has_space, _ = check_disk_space(100)
    if not has_space:
        raise ValueError("المساحة غير كافية")
    
    if not query.startswith("http"):
        query = f"ytsearch:{query}"
    
    timestamp = int(time.time())
    
    if audio_only:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(out_dir, f'audio_{timestamp}.%(ext)s'),
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
            'quiet': True, 'no_warnings': True, 'max_filesize': 50*1024*1024, 'extract_flat': False,
        }
    else:
        ydl_opts = {
            'format': 'best[height<=720]/best',
            'outtmpl': os.path.join(out_dir, f'video_{timestamp}.%(ext)s'),
            'quiet': True, 'no_warnings': True, 'max_filesize': 100*1024*1024,
            'merge_output_format': 'mp4', 'extract_flat': False,
        }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(query, download=False)
            if 'entries' in info_dict:
                info_dict = info_dict['entries'][0]
            
            title = info_dict.get('title', 'بدون عنوان')
            uploader = info_dict.get('uploader', 'غير معروف')
            duration = info_dict.get('duration', 0)
            
            info_dict = ydl.extract_info(query, download=True)
            
            prefix = 'audio_' if audio_only else 'video_'
            files = [f for f in os.listdir(out_dir) if f.startswith(f'{prefix}{timestamp}')]
            if not files:
                raise ValueError("لم يتم العثور على الملف")
            
            filepath = os.path.join(out_dir, files[0])
            if duration == 0:
                duration = info_dict.get('duration', 0)
            
            return {
                'title': title, 'uploader': uploader, 'duration': duration,
                'duration_str': format_duration(duration),
                'size': os.path.getsize(filepath), 'size_str': format_size(os.path.getsize(filepath)),
            }, filepath
    except Exception as e:
        for f in os.listdir(out_dir):
            if f.startswith(f'{prefix}{timestamp}'):
                safe_remove(os.path.join(out_dir, f))
        raise ValueError(f"فشل: {str(e)[:200]}")

def convert_video_to_audio(video_path: str, out_dir: str):
    if not os.path.exists(video_path):
        raise ValueError("الملف غير موجود")
    
    audio_path = os.path.join(out_dir, f"audio_conv_{int(time.time())}.mp3")
    
    try:
        result = subprocess.run([
            'ffmpeg', '-i', video_path, '-vn', '-acodec', 'libmp3lame',
            '-ab', '192k', '-ar', '44100', '-y', audio_path
        ], capture_output=True, timeout=120)
        
        if result.returncode != 0:
            raise ValueError("فشل التحويل")
        
        duration = 0
        try:
            probe = subprocess.run([
                'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1', video_path
            ], capture_output=True, timeout=10)
            if probe.returncode == 0:
                duration = float(probe.stdout.decode().strip())
        except:
            pass
        
        return {
            'path': audio_path, 'duration': duration,
            'duration_str': format_duration(duration),
            'size': os.path.getsize(audio_path), 'size_str': format_size(os.path.getsize(audio_path)),
        }
    except:
        safe_remove(audio_path)
        raise

# ============== دوال الانتحال ==============
async def get_user_info_full(client, user_id):
    try:
        user = await client.get_entity(user_id)
        name = user.first_name or ""
        if user.last_name: name += f" {user.last_name}"
        bio = ""
        try:
            full = await client(GetFullUserRequest(user_id))
            if full.full_user.about: bio = full.full_user.about
        except: pass
        return {'name': name.strip() or "غير معروف", 'first_name': user.first_name or '', 'last_name': user.last_name or '', 'bio': bio, 'id': user.id}
    except: return None

async def change_profile_photo(client, user_id, phone):
    try:
        bio = io.BytesIO()
        await client.download_profile_photo(user_id, file=bio); bio.seek(0)
        uploaded = await client.upload_file(bio, file_name="photo.jpg")
        result = await client(UploadProfilePhotoRequest(file=uploaded))
        await asyncio.sleep(2)
        if hasattr(result, 'photo') and hasattr(result.photo, 'id'): return True, result.photo.id
        return True, None
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds)
        try:
            bio = io.BytesIO(); await client.download_profile_photo(user_id, file=bio); bio.seek(0)
            uploaded = await client.upload_file(bio, file_name="photo.jpg")
            await client(UploadProfilePhotoRequest(file=uploaded))
            return True, None
        except: return False, None
    except: return False, None

# ============== إعداد المعالجات ==============
async def setup_handlers(client, phone):
    
    if phone not in muted_users: muted_users[phone] = {}
    if phone not in taqleed_users: taqleed_users[phone] = {}
    if phone not in ent7al_users: ent7al_users[phone] = False
    if phone not in ent7al_original: ent7al_original[phone] = {}

    # ============== أوامر النصوص ==============
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.عريض (.+)'))
    async def bold_text(event):
        text = event.pattern_match.group(1)
        await event.edit(make_bold(text))

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.مائل (.+)'))
    async def italic_text(event):
        text = event.pattern_match.group(1)
        await event.edit(make_italic(text))

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.مشطوب (.+)'))
    async def strikethrough_text(event):
        text = event.pattern_match.group(1)
        await event.edit(make_strikethrough(text))

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غ خط$'))
    async def normal_text(event):
        if event.is_reply:
            reply = await event.get_reply_message()
            if reply.text:
                # إزالة التنسيق
                clean_text = re.sub(r'[̶]', '', reply.text)
                clean_text = re.sub(r'[𝗮-𝗭𝘢-𝘻]', lambda m: chr(ord('a') + (ord(m.group()) - ord('𝗮')) % 26) if '𝗮' <= m.group() <= '𝗭' else m.group(), clean_text)
                await event.edit(clean_text)
            else:
                await event.edit("**• ❌ الرد على نص فقط**")
        else:
            await event.edit("**• ❌ يرجى الرد على رسالة**")

    # ============== أوامر النسب ==============
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.حب$'))
    async def love_calc(event):
        if not event.is_reply:
            await event.edit("**• ❌ يرجى الرد على شخص**")
            return
        
        reply = await event.get_reply_message()
        user = await client.get_entity(reply.sender_id)
        name = user.first_name or "المستخدم"
        
        percentage = get_random_percentage()
        comment = get_love_comment(percentage)
        
        result = f"💘 **نسبة حب {name}:**\n"
        result += f"{'█' * (percentage // 10)}{'░' * (10 - percentage // 10)} **{percentage}%**\n\n"
        result += f"**{comment}**"
        
        await event.edit(result)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غباء$'))
    async def stupidity_calc(event):
        if not event.is_reply:
            await event.edit("**• ❌ يرجى الرد على شخص**")
            return
        
        reply = await event.get_reply_message()
        user = await client.get_entity(reply.sender_id)
        name = user.first_name or "المستخدم"
        
        percentage = get_random_percentage()
        comment = get_stupidity_comment(percentage)
        
        result = f"🧠 **نسبة غباء {name}:**\n"
        result += f"{'█' * (percentage // 10)}{'░' * (10 - percentage // 10)} **{percentage}%**\n\n"
        result += f"**{comment}**"
        
        await event.edit(result)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.كدب$'))
    async def lying_calc(event):
        if not event.is_reply:
            await event.edit("**• ❌ يرجى الرد على شخص**")
            return
        
        reply = await event.get_reply_message()
        user = await client.get_entity(reply.sender_id)
        name = user.first_name or "المستخدم"
        
        percentage = get_random_percentage()
        comment = get_lying_comment(percentage)
        
        result = f"🤥 **نسبة كذب {name}:**\n"
        result += f"{'█' * (percentage // 10)}{'░' * (10 - percentage // 10)} **{percentage}%**\n\n"
        result += f"**{comment}**"
        
        await event.edit(result)

    # ============== أوامر المزاح ==============
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تهكير$'))
    async def fake_hack(event):
        if not event.is_reply:
            await event.edit("**• ❌ يرجى الرد على شخص**")
            return
        
        reply = await event.get_reply_message()
        user = await client.get_entity(reply.sender_id)
        name = user.first_name or "المستخدم"
        
        await event.edit(f"**🔓 جاري تهكير {name}...**")
        
        for msg in HACK_MESSAGES:
            await event.edit(f"**{msg}**")
            await asyncio.sleep(1.5)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.قتل$'))
    async def fake_kill(event):
        if not event.is_reply:
            await event.edit("**• ❌ يرجى الرد على شخص**")
            return
        
        reply = await event.get_reply_message()
        user = await client.get_entity(reply.sender_id)
        name = user.first_name or "المستخدم"
        
        await event.edit(f"**💀 جاري قتل {name}...**")
        
        for msg in KILL_MESSAGES:
            await event.edit(f"**{msg}**")
            await asyncio.sleep(1.5)

    # ============== أوامر الإحصائيات ==============
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.جروباتي$'))
    async def my_groups(event):
        await event.edit("**• 📊 جاري حساب الجروبات...**")
        
        groups = 0
        async for dialog in client.iter_dialogs():
            if dialog.is_group:
                groups += 1
        
        await event.edit(f"**📊 عدد الجروبات:** {groups}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.قنواتي$'))
    async def my_channels(event):
        await event.edit("**• 📊 جاري حساب القنوات...**")
        
        channels = 0
        async for dialog in client.iter_dialogs():
            if dialog.is_channel and not dialog.is_group:
                channels += 1
        
        await event.edit(f"**📊 عدد القنوات:** {channels}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تونزي$'))
    async def top_interactions(event):
        await event.edit("**• 📊 جاري تحليل التفاعلات...**")
        
        interactions = {}
        
        async for dialog in client.iter_dialogs():
            try:
                async for message in client.iter_messages(dialog.id, limit=100):
                    if message.sender_id and message.sender_id != (await client.get_me()).id:
                        sender = message.sender_id
                        interactions[sender] = interactions.get(sender, 0) + 1
            except:
                continue
        
        if not interactions:
            await event.edit("**• ❌ لا توجد تفاعلات كافية**")
            return
        
        top_user = max(interactions, key=interactions.get)
        top_count = interactions[top_user]
        
        try:
            user = await client.get_entity(top_user)
            name = user.first_name or "مستخدم"
        except:
            name = "مستخدم"
        
        await event.edit(f"**🏆 الأكثر تفاعلاً معك:**\n👤 **{name}**\n💬 **{top_count} رسالة**")

    # ============== أوامر الأنيمشن ==============
    for cmd_name in ['ضحك', 'قلب', 'غيمة', 'ورد', 'كوكب', 'شتاء', 'قمر']:
        @client.on(events.NewMessage(outgoing=True, pattern=rf'^\.{cmd_name}$'))
        async def animation_handler(event, name=cmd_name):
            await event.edit(f"**• جاري تشغيل أنيمشن {name}...**")
            asyncio.create_task(run_animation(event, name, duration=5))

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.وقف$'))
    async def stop_animation(event):
        stopped = 0
        for key in list(active_animations.keys()):
            if key.startswith(str(event.chat_id)):
                active_animations[key] = False
                stopped += 1
        
        await event.edit(f"**• ⏹️ تم إيقاف {stopped} أنيمشن**" if stopped else "**• ❌ لا يوجد أنيمشن**")

    # ============== أوامر التحميل ==============
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.يوت (.+)'))
    async def youtube_audio(event):
        if not YTDLP_AVAILABLE:
            await event.edit("**• ❌ مكتبة yt-dlp غير مثبتة**")
            return
        
        query = event.pattern_match.group(1).strip()
        has_space, _ = check_disk_space(80)
        if not has_space:
            await event.edit("**• ❌ المساحة غير كافية**")
            return
        
        await event.edit("**• 🎵 جاري التحميل...**")
        filepath = None
        
        try:
            info, filepath = await asyncio.get_event_loop().run_in_executor(
                _DOWNLOAD_EXECUTOR, download_youtube_media, query, TEMP_DIR, True
            )
            
            title = info['title'][:52] + '...' if len(info['title']) > 55 else info['title']
            caption = f"{title}\n• {info['duration_str']} | ᥲᥙძᎥ᥆"
            
            await client.send_file(event.chat_id, filepath, caption=caption,
                                   attributes=[DocumentAttributeAudio(duration=info['duration'], title=info['title'], performer=info['uploader'])],
                                   supports_streaming=True)
            await event.delete()
        except Exception as e:
            await event.edit(f"**• ❌ {str(e)[:200]}**")
        finally:
            safe_remove(filepath)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.فيد (.+)'))
    async def video_download(event):
        if not YTDLP_AVAILABLE:
            await event.edit("**• ❌ مكتبة yt-dlp غير مثبتة**")
            return
        
        query = event.pattern_match.group(1).strip()
        has_space, _ = check_disk_space(150)
        if not has_space:
            await event.edit("**• ❌ المساحة غير كافية**")
            return
        
        await event.edit("**• 🎬 جاري التحميل...**")
        filepath = None
        
        try:
            info, filepath = await asyncio.get_event_loop().run_in_executor(
                _DOWNLOAD_EXECUTOR, download_youtube_media, query, TEMP_DIR, False
            )
            
            title = info['title'][:52] + '...' if len(info['title']) > 55 else info['title']
            caption = f"{title}\n• {info['duration_str']} | ᥎Ꭵძꫀ᥆"
            
            await client.send_file(event.chat_id, filepath, caption=caption,
                                   attributes=[DocumentAttributeVideo(duration=info['duration'], w=0, h=0, supports_streaming=True)],
                                   supports_streaming=True)
            await event.delete()
        except Exception as e:
            await event.edit(f"**• ❌ {str(e)[:200]}**")
        finally:
            safe_remove(filepath)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.صوت$'))
    async def video_to_audio(event):
        if not event.is_reply:
            await event.edit("**• ❌ يرجى الرد على فيديو**")
            return
        
        reply = await event.get_reply_message()
        if not (reply.video or reply.document):
            await event.edit("**• ❌ يرجى الرد على فيديو**")
            return
        
        await event.edit("**• 🎵 جاري التحويل...**")
        video_path = None; audio_path = None
        
        try:
            video_path = os.path.join(TEMP_DIR, f"video_{phone}_{int(time.time())}.mp4")
            await client.download_media(reply, video_path)
            
            audio_info = await asyncio.get_event_loop().run_in_executor(
                _DOWNLOAD_EXECUTOR, convert_video_to_audio, video_path, TEMP_DIR
            )
            audio_path = audio_info['path']
            
            title = clean_filename("محول من فيديو")
            dur = audio_info['duration_str']
            
            await client.send_file(event.chat_id, audio_path,
                                   caption=f"{title}\n• {dur} | 🎵",
                                   attributes=[DocumentAttributeAudio(duration=int(audio_info['duration']), title=title)],
                                   supports_streaming=True)
            await event.delete()
        except Exception as e:
            await event.edit(f"**• ❌ {str(e)[:200]}**")
        finally:
            safe_remove(video_path); safe_remove(audio_path)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.نسخ$'))
    async def transcribe_voice(event):
        if not event.is_reply:
            await event.edit("**• ❌ يرجى الرد على صوتية**")
            return
        
        reply = await event.get_reply_message()
        if not (reply.voice or reply.audio):
            await event.edit("**• ❌ يرجى الرد على صوتية**")
            return
        
        if not SR_AVAILABLE:
            await event.edit("**• ❌ مكتبة SpeechRecognition غير مثبتة**")
            return
        
        await event.edit("**• 🎤 جاري التحويل...**")
        voice_path = None; wav_path = None
        
        try:
            voice_path = os.path.join(TEMP_DIR, f"voice_{phone}_{int(time.time())}.ogg")
            await client.download_media(reply, voice_path)
            wav_path = voice_path.replace('.ogg', '.wav')
            
            subprocess.run(['ffmpeg', '-i', voice_path, '-ac', '1', '-ar', '16000', '-sample_fmt', 's16', wav_path],
                          capture_output=True, timeout=30)
            
            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_path) as source:
                audio_data = recognizer.record(source)
            
            text = None
            for lang in ['ar-AR', 'en-US']:
                try:
                    text = recognizer.recognize_google(audio_data, language=lang)
                    break
                except: continue
            
            await event.edit(f"**📝 النص:**\n{text}" if text else "**• ❌ لم يتم التعرف على نص**")
        except Exception as e:
            await event.edit(f"**• ❌ {str(e)[:150]}**")
        finally:
            safe_remove(voice_path); safe_remove(wav_path)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.استيك$'))
    async def photo_to_sticker(event):
        if not event.is_reply:
            await event.edit("**• ❌ يرجى الرد على صورة**"); return
        
        reply = await event.get_reply_message()
        if not reply.photo:
            await event.edit("**• ❌ يرجى الرد على صورة**"); return
        
        if not PIL_AVAILABLE:
            await event.edit("**• ❌ مكتبة Pillow غير مثبتة**"); return
        
        await event.edit("**• 🔄 جاري التحويل...**")
        img_path = None; stick_path = None
        
        try:
            img_path = os.path.join(TEMP_DIR, f"img_{phone}_{int(time.time())}.jpg")
            await client.download_media(reply, img_path)
            stick_path = img_path.replace('.jpg', '.webp')
            
            im = Image.open(img_path).convert("RGBA")
            im.thumbnail((512, 512), Image.LANCZOS)
            im.save(stick_path, "WEBP", quality=80)
            
            await client.send_file(event.chat_id, stick_path, force_document=False)
            await event.delete()
        except Exception as e:
            await event.edit(f"**• ❌ {str(e)[:150]}**")
        finally:
            safe_remove(img_path); safe_remove(stick_path)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بيك$'))
    async def sticker_to_photo(event):
        if not event.is_reply:
            await event.edit("**• ❌ يرجى الرد على استيكر**"); return
        
        reply = await event.get_reply_message()
        if not reply.sticker:
            await event.edit("**• ❌ يرجى الرد على استيكر**"); return
        
        if not PIL_AVAILABLE:
            await event.edit("**• ❌ مكتبة Pillow غير مثبتة**"); return
        
        await event.edit("**• 🔄 جاري التحويل...**")
        stick_path = None; img_path = None
        
        try:
            stick_path = os.path.join(TEMP_DIR, f"sticker_{phone}_{int(time.time())}.webp")
            await client.download_media(reply, stick_path)
            img_path = stick_path.replace('.webp', '.png')
            
            Image.open(stick_path).convert("RGBA").save(img_path, "PNG")
            await client.send_file(event.chat_id, img_path)
            await event.delete()
        except Exception as e:
            await event.edit(f"**• ❌ {str(e)[:150]}**")
        finally:
            safe_remove(stick_path); safe_remove(img_path)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بن (.+)'))
    async def image_search(event):
        query = event.pattern_match.group(1).strip()
        
        if query.startswith('http'):
            await event.edit("**• 📷 جاري تحميل الصورة...**")
            filepath = await asyncio.get_event_loop().run_in_executor(_DOWNLOAD_EXECUTOR, download_image_direct, query, TEMP_DIR)
            if filepath:
                await client.send_file(event.chat_id, filepath)
                await event.delete()
                safe_remove(filepath)
            else:
                await event.edit("**• ❌ فشل التحميل**")
            return
        
        await event.edit(f"**• 🔍 جاري البحث عن '{query}'...**")
        
        urls = await asyncio.get_event_loop().run_in_executor(_DOWNLOAD_EXECUTOR, search_all_images, query, 5)
        
        if not urls:
            await event.edit(f"**• ❌ لم يتم العثور على صور لـ '{query}'**\n**• جرب كلمات بحث أدق**")
            return
        
        await event.edit(f"**• ✅ تم العثور على {len(urls)} صورة**\n**• 📥 جاري التحميل...**")
        
        success = 0
        for i, url in enumerate(urls[:3], 1):
            try:
                filepath = await asyncio.get_event_loop().run_in_executor(_DOWNLOAD_EXECUTOR, download_image_direct, url, TEMP_DIR)
                if filepath:
                    await client.send_file(event.chat_id, filepath)
                    success += 1
                    safe_remove(filepath)
                    await event.edit(f"**• 📤 تم إرسال {success} صورة...**")
                await asyncio.sleep(0.3)
            except:
                continue
        
        if success > 0:
            await event.delete()
        else:
            await event.edit(f"**• ❌ فشل تحميل صور '{query}'**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.المساحة$'))
    async def space_check(event):
        await event.edit("**• 📊 جاري الفحص...**")
        free_mb = get_free_space_mb()
        cleaned, _ = clean_temp_files()
        await event.edit(f"**📊 المساحة:** {get_free_space_mb():.1f} MB\n**🧹 تم تنظيف:** {cleaned} ملف")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تنظيف$'))
    async def force_clean(event):
        await event.edit("**• 🧹 جاري التنظيف...**")
        c, _ = clean_temp_files()
        await event.edit(f"**✅ تم التنظيف: {c} ملف**\n**المساحة:** {get_free_space_mb():.1f} MB")

    # ============== التقليد ==============
    @client.on(events.NewMessage(incoming=True))
    async def auto_taqleed(event):
        if event.sender_id in taqleed_users.get(phone, {}) and event.text and not event.text.startswith('.'):
            await asyncio.sleep(0.3)
            try: await event.reply(event.text)
            except: pass

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تقليد$'))
    async def taq(event):
        target = (await event.get_reply_message()).sender_id if event.is_reply else event.chat_id if event.is_private else None
        if target: taqleed_users[phone][target] = True; await event.edit("**• ✅ تم التقليد**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غ تقليد$'))
    async def notaq(event):
        target = (await event.get_reply_message()).sender_id if event.is_reply else event.chat_id if event.is_private else None
        if target and target in taqleed_users.get(phone, {}): del taqleed_users[phone][target]; await event.edit("**• ✅ تم فك التقليد**")

    # ============== الانتحال ==============
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.انتحال$'))
    async def ent7al(event):
        track_command(phone, ".انتحال")
        await event.edit("**• 🔄 جاري الانتحال...**")
        target_user = None
        if event.is_reply:
            try: target_user = await client.get_entity((await event.get_reply_message()).sender_id)
            except: pass
        elif event.is_private:
            try: target_user = await client.get_entity(event.chat_id)
            except: pass
        if not target_user: await event.edit("**• ❌ فشل**"); return
        
        target_info = await get_user_info_full(client, target_user.id)
        if not target_info: await event.edit("**• ❌ فشل**"); return
        
        me = await client.get_me(); client_me[phone] = me
        original = {'first_name': me.first_name or '', 'last_name': me.last_name or '', 'about': '', 'added_photo_id': None}
        try:
            fu = await client(GetFullUserRequest('me'))
            if fu.full_user.about: original['about'] = fu.full_user.about
        except: pass
        
        try:
            await client(UpdateProfileRequest(first_name=target_info['first_name'], last_name=target_info['last_name']))
            await asyncio.sleep(1)
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            try: await client(UpdateProfileRequest(first_name=target_info['first_name'], last_name=target_info['last_name']))
            except: pass
        except: pass
        
        try:
            await client(UpdateProfileRequest(about=target_info['bio'][:70] if target_info['bio'] else ''))
            await asyncio.sleep(0.5)
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
        except: pass
        
        photo_ok, added_id = await change_profile_photo(client, target_user.id, phone)
        if photo_ok and added_id: original['added_photo_id'] = added_id
        ent7al_original[phone] = original; ent7al_users[phone] = True
        await event.edit("**• ✅ تم الانتحال**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.الغاء انتحال$'))
    async def unent7al(event):
        if not ent7al_users.get(phone): await event.edit("**• ❌ لا يوجد انتحال**"); return
        original = ent7al_original[phone]
        try: await client(UpdateProfileRequest(first_name=original.get('first_name',''), last_name=original.get('last_name','')))
        except: pass
        if original.get('added_photo_id'):
            try: await client(DeletePhotosRequest(id=[InputPhoto(id=original['added_photo_id'], access_hash=0, file_reference=b'')]))
            except: pass
        try: await client(UpdateProfileRequest(about=original.get('about','')))
        except: pass
        ent7al_users[phone] = False; ent7al_original[phone] = {}
        await event.edit("**• ✅ تم إلغاء الانتحال**")

    # ============== مراقبة الخاص ==============
    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private and not e.out))
    async def cache_message(event):
        if event.sender_id == (await client.get_me()).id: return
        message_cache.setdefault(event.chat_id, {})[event.id] = event.text or "<وسائط>"

    @client.on(events.MessageEdited(incoming=True, func=lambda e: e.is_private and not e.out))
    async def notify_edit(event):
        if event.sender_id == (await client.get_me()).id: return
        user = await event.get_sender()
        name = user.first_name or ""; name += f" {user.last_name}" if user.last_name else ""
        old = message_cache.get(event.chat_id, {}).get(event.id, "نص غير معروف")
        await client.send_message("me", f"**📝 {name} عدل رسالة**\n**من:** {old}\n**إلى:** {event.text or '<وسائط>'}")
        message_cache.setdefault(event.chat_id, {})[event.id] = event.text or "<وسائط>"

    @client.on(events.MessageDeleted(incoming=True, func=lambda e: e.is_private and not e.out))
    async def notify_delete(event):
        for chat_id, msg_ids in event.deleted_ids.items():
            for msg_id in msg_ids:
                if chat_id in message_cache and msg_id in message_cache[chat_id]:
                    text = message_cache[chat_id][msg_id]
                    user_name = "مستخدم"
                    try: 
                        chat = await client.get_entity(chat_id)
                        user_name = chat.first_name or "مستخدم"
                    except: pass
                    await client.send_message("me", f"**🗑️ {user_name} حذف رسالة**\n**{text}**")
                    del message_cache[chat_id][msg_id]

    # ============== تنظيف دوري ==============
    async def auto_cleanup():
        while True:
            await asyncio.sleep(1800)
            if get_free_space_mb() < MIN_FREE_SPACE_MB * 2:
                clean_temp_files()
    
    asyncio.create_task(auto_cleanup())

    logger.info(f"✅ جميع الأوامر جاهزة لـ {phone}")
