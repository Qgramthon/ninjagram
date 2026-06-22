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
from urllib.parse import quote, urlencode
from datetime import datetime
from telethon import events, functions, types, Button
from telethon.errors import (
    FloodWaitError, ChatAdminRequiredError, UserPrivacyRestrictedError,
    PeerFloodError, UserBannedInChannelError, UserNotMutualContactError,
    UserChannelsTooMuchError, UserKickedError, UserAlreadyParticipantError,
    UserNotParticipantError, ChatNotModifiedError
)
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.channels import (
    InviteToChannelRequest, EditAdminRequest, EditBannedRequest,
    GetParticipantsRequest, EditPhotoRequest
)
from telethon.tl.functions.messages import (
    AddChatUserRequest, GetDialogsRequest, DeleteChatUserRequest,
    DeleteHistoryRequest, EditChatDefaultBannedRightsRequest
)
from telethon.tl.functions.contacts import AddContactRequest, BlockRequest, UnblockRequest, GetBlockedRequest
from telethon.tl.types import (
    InputPhoto, DocumentAttributeAudio, DocumentAttributeVideo,
    InputPeerUser, InputPeerChat, InputPeerChannel, InputPeerEmpty,
    ChatBannedRights, ChatAdminRights, ChannelParticipantsAdmins,
    UserStatusOnline, UserStatusOffline,
    ChannelParticipantCreator, ChannelParticipantAdmin
)
from telethon.tl.functions.phone import CreateGroupCallRequest
from shared import (
    active_clients, muted_users, taqleed_users, ent7al_users, ent7al_original,
    client_me, track_command, logger, TEMP_DIR
)

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

_DOWNLOAD_EXECUTOR = ThreadPoolExecutor(max_workers=5, thread_name_prefix="dl")
message_cache = {}
active_animations = {}
MIN_FREE_SPACE_MB = 50
text_format_mode = {}
tagging_active = {}
stalking_active = {}

YOUTUBE_COOKIES = """# Netscape HTTP Cookie File
.youtube.com	TRUE	/	TRUE	0	__Secure-YNID	19.YT=HRSdnAgVoT7zPzNrfUD5fvX1jNNYq5AlRFC-i8h0tc8eZjJ933PO3qtkjxyXMg7NKWnWzcYqRE0gSJ_Un0WxhntqHQGVk9aQiOnVogSLQ_QexNBOTlx9nbr9wwsGn9Kvdoq_f4T0rmBsBR0AlegfZger099ztJJbRf6ABQwu0VjX7-vBFap_vnNa4Ap2ie0P-TTG5CxyCDu8IpWsQNo_Ulfd60VN5AxDGR3aHX0ho2ZpG4SbHE5gfuoYTaKgbvlerpigJdPViTPh_54eVGHtg8W1xu-FIEHqWezLrMyFP_JuxZscntxedEJ24ixMM--iVgRIBmwG8TEpSu6cm4NMaA
.youtube.com	TRUE	/	TRUE	0	GPS	1
.youtube.com	TRUE	/	TRUE	0	YSC	2ZqkBhu97kI
.youtube.com	TRUE	/	TRUE	0	VISITOR_INFO1_LIVE	5LStVsyOd1g
.youtube.com	TRUE	/	TRUE	0	PREF	f6=40000000&tz=Africa.Cairo
.youtube.com	TRUE	/	TRUE	0	__Secure-1PSIDTS	sidts-CjUByojQUx58ERvSDskWSihIxkWc2Q5-rTs-CVVAgIG1OG7ZeeC5L71HNU63M1x9ftH9i_Rt-RAA
.youtube.com	TRUE	/	TRUE	0	__Secure-3PSIDTS	sidts-CjUByojQUx58ERvSDskWSihIxkWc2Q5-rTs-CVVAgIG1OG7ZeeC5L71HNU63M1x9ftH9i_Rt-RAA
.youtube.com	TRUE	/	TRUE	0	HSID	A5D9LhXXu_4LzIw__
.youtube.com	TRUE	/	TRUE	0	SSID	AafW1KLt0V51k0CVP
.youtube.com	TRUE	/	TRUE	0	APISID	E7a4fljFYvBoLz7c/AG1z3-8QKvwCoHcOo
.youtube.com	TRUE	/	TRUE	0	SAPISID	Q4gM-6RWH58NbnQ_/AzZn1qKJn-AgVVjYB
.youtube.com	TRUE	/	TRUE	0	__Secure-1PAPISID	Q4gM-6RWH58NbnQ_/AzZn1qKJn-AgVVjYB
.youtube.com	TRUE	/	TRUE	0	__Secure-3PAPISID	Q4gM-6RWH58NbnQ_/AzZn1qKJn-AgVVjYB
.youtube.com	TRUE	/	TRUE	0	SID	g.a000_Qhz90DovCqzNrJ1Soq3jPMNKHeT2D7ShfKsQuCpjFwzmJcG5UbJsGxnxuPpxPDpNq6e0gACgYKAYMSARUSFQHGX2Mi7bcVBvpMJvV2h6e_cKJ_LhoVAUF8yKqmp3fmxC7M8Mx4_X6tu7Vw0076
.youtube.com	TRUE	/	TRUE	0	__Secure-1PSID	g.a000_Qhz90DovCqzNrJ1Soq3jPMNKHeT2D7ShfKsQuCpjFwzmJcGlo-E9cE6-UIPMnHaoYO7mgACgYKAcQSARUSFQHGX2MibIi_0Jo8oC22KeZkgq8mUhoVAUF8yKoLFNXzlWhq29Np3MdPs0420076
.youtube.com	TRUE	/	TRUE	0	__Secure-3PSID	g.a000_Qhz90DovCqzNrJ1Soq3jPMNKHeT2D7ShfKsQuCpjFwzmJcGB4p8fggE2G9on5Xa8unQMwACgYKAegSARUSFQHGX2MiPNNK5iTk-nCXwZ8CEvCPshoVAUF8yKrvYRK_NTykI7tjFG8wSh8N0076
.youtube.com	TRUE	/	TRUE	0	SIDCC	AKEyXzUEBm2k34rOtwoylCtotT0zr8yGBIeOv91yEpzaSZlN75w9CKZIFKY69T4X2E6bBtqn7Q
.youtube.com	TRUE	/	TRUE	0	__Secure-1PSIDCC	AKEyXzXJ3VFTXxlzIG2IHhMHJRHrHa53kbzltyIwKjBv17Kh9aSH-AXierVYwo09R2OLHLGsoQ
.youtube.com	TRUE	/	TRUE	0	__Secure-3PSIDCC	AKEyXzVFMhFMB1cT_GGwjP4QQO3LTxWoGXJ675c-md01l-MS9MjMNxbHpRPRfBNvYLH8qrUl
.youtube.com	TRUE	/	TRUE	0	LOGIN_INFO	AFmmF2swRQIhAOGjg2ygcc3k2_zaEIn8BRv46I_ODh7CzKYL7p-ZvjVlAiAaE1KIGnSNW-LA9nOzCsQiy1VD-1bt0_17eH9roWSbCg:QUQ3MjNmeWxqek9hVEV4MERQckdMYzV4SGdJS0N5MGlEdGkxT1cwSDRLVndxZjA4ZmJrbkZRMWx2a2hLWlBsaVlkRzFlRW5id1FKT0tPZXR2NmFDQVlsU1lyME1QXzdvVU5pYmJrRk9WUHZ2TGpOenBTUko3Tzk2RHdDajJUcDJlWFRhX2s2U2NKckF4SklObnFVaWRPd29fNkxJZkdhZWtB"""

def get_free_space_mb():
    try:
        temp_dir = TEMP_DIR if TEMP_DIR and os.path.exists(TEMP_DIR) else '/'
        return shutil.disk_usage(temp_dir).free / (1024 * 1024)
    except: return 999

def clean_temp_files():
    cleaned = 0
    if TEMP_DIR and os.path.exists(TEMP_DIR):
        for f in os.listdir(TEMP_DIR):
            fp = os.path.join(TEMP_DIR, f)
            if os.path.isfile(fp):
                try: os.remove(fp); cleaned += 1
                except: continue
    return cleaned

def safe_remove(filepath):
    try:
        if filepath and os.path.exists(filepath): os.remove(filepath); return True
    except: pass
    return False

def format_duration(seconds):
    if not seconds: return "0:00"
    mins, secs = divmod(int(seconds), 60)
    return f"{mins}:{secs:02d}"

def clean_filename(name):
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    return re.sub(r'\s+', ' ', name).strip()[:100]

def apply_telegram_format(text, format_type):
    if not text: return text
    if format_type == 'bold': return f"**{text}**"
    elif format_type == 'italic': return f"__{text}__"
    elif format_type == 'strike': return f"~~{text}~~"
    return text

DECORATION_STYLES = {
    'style1': dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz','𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇')),
    'style3': dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz','𝔸𝔹ℂ𝔻𝔼𝔽𝔾ℍ𝕀𝕁𝕂𝕃𝕄ℕ𝕆ℙℚℝ𝕊𝕋𝕌𝕍𝕎𝕏𝕐ℤ𝕒𝕓𝕔𝕕𝕖𝕗𝕘𝕙𝕚𝕛𝕜𝕝𝕞𝕟𝕠𝕡𝕢𝕣𝕤𝕥𝕦𝕧𝕨𝕩𝕪𝕫')),
}

def apply_decoration(text, style_name):
    if style_name not in DECORATION_STYLES: return text
    return ''.join(DECORATION_STYLES[style_name].get(c, c) for c in text)

def translate_text(text: str) -> str:
    try:
        source, target = ('ar', 'en') if re.search(r'[\u0600-\u06FF]', text) else ('en', 'ar')
        resp = requests.get(f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={source}&tl={target}&dt=t&q={quote(text)}", timeout=15)
        if resp.status_code == 200: return ''.join([s[0] for s in json.loads(resp.text)[0] if s[0]])
    except: pass
    return text

def get_random_percentage(): return random.randint(1, 100)

def get_love_comment(p):
    if p >= 90: return "💘 حب من طرف واحد ولا اتنين يا عم"
    if p >= 70: return "❤️‍🔥 فيه حب بس مش قد كده"
    if p >= 50: return "💕 نص نص يا معلم"
    if p >= 30: return "💔 الحب ضعيف شوية"
    return "💀 مفيش حب خالص يا عم"

def get_stupidity_comment(p):
    if p >= 90: return "🐄 هاتوله برسيم... شكل مفيش منك امل"
    if p >= 70: return "🤪 غبي بس لسه فيه بصيص أمل"
    if p >= 50: return "🤔 نص نص... مش متأكدين"
    if p >= 30: return "🧐 لا يعم ده طلع بيفهم اهو"
    return "🧠 ده عبقري والله"

def get_lying_comment(p):
    if p >= 90: return "🤥 دنت كداب اوي يلا"
    if p >= 70: return "😏 كداب ومحترف كمان"
    if p >= 50: return "🤨 فيه كدب شوية"
    if p >= 30: return "🙂 لا يعم ده غلبان صادق"
    return "😇 ده صادق جدا والله"

HACK_MESSAGES = ["🔓 **جاري فتح المنافذ...**","📡 **تم الاتصال بالخادم**","🔍 **جاري فحص الثغرات...**","💉 **تم حقن الكود**","🔑 **فك تشفير المرور...**","📂 **تم الوصول للبيانات**","📊 **جاري سحب المعلومات...**","🛡️ **تجاوز الحماية**","✅ **تم الاختراق!**","⚠️ **النظام تحت السيطرة**"]
KILL_METHODS = [
    ["🔪 **جاري الطعن...**","🩸 **تم الطعن في القلب**","☠️ **الضحية تنزف...**"],
    ["🔫 **جاري التصويب...**","💥 **تم إطلاق النار**","🎯 **إصابة في الرأس**"],
]

def create_animation_pattern(el): return [''.join(el[i:]+el[:i]) for i in range(len(el))]
ANIMATION_PATTERNS = {n: create_animation_pattern(e) for n,e in {'ضحك':['😂','🤣'],'قلب':['❤️','💛','💚','💜'],'قمر':['🌕','🌖','🌗','🌘']}.items()}

async def run_animation(event, name, duration=5):
    if name not in ANIMATION_PATTERNS: return
    patterns, chat_id = ANIMATION_PATTERNS[name], event.chat_id
    message = await event.get_reply_message() if event.is_reply else None
    key = f"{chat_id}_{name}"; active_animations[key] = True
    t = time.time()
    try:
        while active_animations.get(key):
            for p in patterns:
                if not active_animations.get(key): break
                try:
                    if message: await message.edit(p)
                    else: await event.edit(p)
                    await asyncio.sleep(0.5)
                    if time.time()-t >= duration: active_animations[key]=False; break
                except FloodWaitError as e: await asyncio.sleep(e.seconds)
                except: active_animations[key]=False; break
    except: pass
    finally:
        if key in active_animations: del active_animations[key]

def search_images(query: str, limit: int = 5) -> list:
    all_images = []
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs: all_images = [img["image"] for img in ddgs.images(query, max_results=limit) if img.get("image")]
    except:
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            resp = requests.get(f"https://www.google.com/search?q={quote(query)}&tbm=isch&hl=en", headers=headers, timeout=15)
            if resp.status_code == 200:
                for url in re.findall(r'"ou":"(https?://[^"]+)"', resp.text):
                    if not any(s in url.lower() for s in ['google','gstatic']): all_images.append(url)
        except: pass
    seen = set(); unique = []
    for url in all_images:
        url = url.strip()
        if url.startswith('http') and url not in seen: seen.add(url); unique.append(url)
        if len(unique) >= limit: break
    return unique[:limit]

def download_image(url: str, out_dir: str) -> str:
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, stream=True, timeout=30)
        if resp.status_code != 200: return None
        ext = '.jpg'
        ct = resp.headers.get('content-type','').lower()
        if 'png' in ct: ext='.png'
        elif 'webp' in ct: ext='.webp'
        elif 'gif' in ct: ext='.gif'
        fp = os.path.join(out_dir, f"img_{int(time.time()*1000)}_{hashlib.md5(url.encode()).hexdigest()[:8]}{ext}")
        sz = 0
        with open(fp,'wb') as f:
            for c in resp.iter_content(8192):
                if c: f.write(c); sz+=len(c)
                if sz>15*1024*1024: safe_remove(fp); return None
        if sz<2048: safe_remove(fp); return None
        return fp
    except: return None

def save_cookies():
    p = os.path.join(TEMP_DIR, 'yt_cookies.txt')
    try:
        with open(p,'w') as f: f.write(YOUTUBE_COOKIES)
        return p
    except: return None

def download_youtube_media(query: str, out_dir: str, audio_only: bool = False):
    if not YTDLP_AVAILABLE: raise ValueError("مكتبة yt-dlp غير مثبتة. استخدم: pip install yt-dlp")
    query = query.strip()
    if not query.startswith("http"): query = f"ytsearch:{query}"
    
    timestamp = int(time.time())
    prefix = 'audio_' if audio_only else 'video_'
    cookies_path = save_cookies()
    
    ydl_opts = {
        'quiet': True, 'no_warnings': True, 'no_color': True, 'noprogress': True,
        'format_sort': ['res:720', 'codec:h264:m4a'],
        'outtmpl': os.path.join(out_dir, f'{prefix}{timestamp}.%(ext)s'),
        'user_agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        'referer': 'https://www.youtube.com/',
        'extractor_args': {'youtube': {'player_client': ['android', 'web', 'tvhtml5'], 'player_skip': ['configs', 'webpage']}},
        'ignoreerrors': True, 'nooverwrites': True, 'continuedl': True,
        'retries': 10, 'fragment_retries': 10, 'skip_unavailable_fragments': True,
        'max_filesize': 100 * 1024 * 1024, 'socket_timeout': 60, 'extractor_retries': 5,
    }
    if cookies_path and os.path.exists(cookies_path): ydl_opts['cookiefile'] = cookies_path
    if audio_only: ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            if info and 'entries' in info:
                entries = [e for e in info['entries'] if e]
                if entries: info = entries[0]
            if not info: raise ValueError("لم يتم العثور على الفيديو")
            
            title = info.get('title') or 'بدون عنوان'
            uploader = info.get('uploader') or 'غير معروف'
            duration = info.get('duration') or 0
            
            files = sorted([f for f in os.listdir(out_dir) if f.startswith(f'{prefix}{timestamp}')],
                          key=lambda x: os.path.getsize(os.path.join(out_dir, x)), reverse=True)
            if not files: raise ValueError("لم يتم العثور على الملف المحمل")
            
            filepath = os.path.join(out_dir, files[0])
            if os.path.getsize(filepath) < 1024: safe_remove(filepath); raise ValueError("الملف تالف")
            
            return {'title': title, 'uploader': uploader, 'duration': duration, 'duration_str': format_duration(duration)}, filepath
    except Exception as e:
        for f in os.listdir(out_dir):
            if f.startswith(f'{prefix}{timestamp}'): safe_remove(os.path.join(out_dir, f))
        raise ValueError(f"فشل: {str(e)[:200]}")

def convert_video_to_audio(video_path: str, out_dir: str):
    if not os.path.exists(video_path): raise ValueError("الملف غير موجود")
    audio_path = os.path.join(out_dir, f"audio_conv_{int(time.time())}.mp3")
    try:
        r = subprocess.run(['ffmpeg','-i',video_path,'-vn','-acodec','libmp3lame','-ab','128k','-ar','44100','-y',audio_path], capture_output=True, timeout=120)
        if r.returncode != 0: raise ValueError("فشل التحويل")
        d = 0
        try:
            pr = subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',video_path], capture_output=True, timeout=10)
            if pr.returncode == 0: d = float(pr.stdout.decode().strip())
        except: pass
        return {'path': audio_path, 'duration': d, 'duration_str': format_duration(d)}
    except: safe_remove(audio_path); raise

async def get_user_info_full(client, user_id):
    try:
        user = await client.get_entity(user_id)
        name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        bio = ""
        try:
            full = await client(GetFullUserRequest(user_id))
            if full.full_user.about: bio = full.full_user.about
        except: pass
        return {'name': name or "غير معروف", 'first_name': user.first_name or '', 'last_name': user.last_name or '', 'bio': bio, 'id': user.id}
    except: return None

async def change_profile_photo(client, user_id, phone):
    try:
        bio = io.BytesIO(); await client.download_profile_photo(user_id, file=bio); bio.seek(0)
        result = await client(UploadProfilePhotoRequest(file=await client.upload_file(bio, file_name="photo.jpg")))
        await asyncio.sleep(2)
        return (True, result.photo.id) if hasattr(result, 'photo') and hasattr(result.photo, 'id') else (True, None)
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds)
        try:
            bio = io.BytesIO(); await client.download_profile_photo(user_id, file=bio); bio.seek(0)
            await client(UploadProfilePhotoRequest(file=await client.upload_file(bio, file_name="photo.jpg")))
            return True, None
        except: return False, None
    except: return False, None

async def resolve_user(event, client):
    if event.is_reply:
        try: return await client.get_entity((await event.get_reply_message()).sender_id)
        except: pass
    text = event.text.split()
    if len(text) >= 2:
        try: return await client.get_entity(text[1].strip('@'))
        except: pass
    return None

async def measure_speed():
    try:
        start = time.time(); requests.get("https://api.telegram.org", timeout=10)
        ping = int((time.time()-start)*1000)
        start = time.time()
        resp = requests.get("http://ipv4.download.thinkbroadband.com/5MB.zip", stream=True, timeout=30)
        size = sum(len(c) for c in resp.iter_content(8192) if time.time()-start < 8)
        speed = (size*8)/((time.time()-start)*1000000) if time.time()>start else 0
        return {'ping': ping, 'speed': speed, 'success': True}
    except: return {'success': False}

async def setup_handlers(client, phone):
    if phone not in muted_users: muted_users[phone] = {}
    if phone not in taqleed_users: taqleed_users[phone] = {}
    if phone not in ent7al_users: ent7al_users[phone] = False
    if phone not in ent7al_original: ent7al_original[phone] = {}
    if phone not in text_format_mode: text_format_mode[phone] = None
    if phone not in tagging_active: tagging_active[phone] = False
    if phone not in stalking_active: stalking_active[phone] = False

    @client.on(events.NewMessage(outgoing=True))
    async def auto_format_outgoing(event):
        if event.text and event.text.startswith('.'): return
        fmt = text_format_mode.get(phone)
        if fmt and event.text:
            ft = apply_telegram_format(event.text, fmt)
            if ft != event.text:
                try: await event.edit(ft, parse_mode='markdown')
                except: pass

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.عريض$'))
    async def t_bold(event):
        if text_format_mode.get(phone)=='bold': text_format_mode[phone]=None; await event.edit("**• ✅ تم إلغاء العريض**", parse_mode='markdown')
        else: text_format_mode[phone]='bold'; await event.edit("**• ✅ تم تفعيل العريض**", parse_mode='markdown')

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.مائل$'))
    async def t_italic(event):
        if text_format_mode.get(phone)=='italic': text_format_mode[phone]=None; await event.edit("**• ✅ تم إلغاء المائل**", parse_mode='markdown')
        else: text_format_mode[phone]='italic'; await event.edit("**• ✅ تم تفعيل المائل**", parse_mode='markdown')

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.مشطوب$'))
    async def t_strike(event):
        if text_format_mode.get(phone)=='strike': text_format_mode[phone]=None; await event.edit("**• ✅ تم إلغاء المشطوب**", parse_mode='markdown')
        else: text_format_mode[phone]='strike'; await event.edit("**• ✅ تم تفعيل المشطوب**", parse_mode='markdown')

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غ خط$'))
    async def t_reset(event): text_format_mode[phone]=None; await event.edit("**• ✅ تم إرجاع الخط**", parse_mode='markdown')

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.خفي$'))
    async def hide_name(event):
        try: await client(UpdateProfileRequest(first_name='ㅤ', last_name='')); await event.edit("**• ✅ تم إخفاء الاسم**")
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غ خفي$'))
    async def unhide_name(event):
        if phone in client_me:
            try:
                o = client_me[phone]
                await client(UpdateProfileRequest(first_name=o.first_name or '', last_name=o.last_name or ''))
                await event.edit("**• ✅ تم استرجاع الاسم**")
            except: await event.edit("**• ❌ فشل**")
        else: await event.edit("**• ❌ لم يتم حفظ الاسم**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.حب$'))
    async def love(event):
        if not event.is_reply: await event.edit("**• ❌ يرجى الرد على شخص**", parse_mode='markdown'); return
        u = await client.get_entity((await event.get_reply_message()).sender_id)
        p = get_random_percentage()
        await event.edit(f"💘 **نسبة حب {u.first_name or 'المستخدم'}:**\n{'█'*(p//10)}{'░'*(10-p//10)} **{p}%**\n\n**{get_love_comment(p)}**", parse_mode='markdown')

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غباء$'))
    async def stupidity(event):
        if not event.is_reply: await event.edit("**• ❌ يرجى الرد على شخص**", parse_mode='markdown'); return
        u = await client.get_entity((await event.get_reply_message()).sender_id)
        p = get_random_percentage()
        await event.edit(f"🧠 **نسبة غباء {u.first_name or 'المستخدم'}:**\n{'█'*(p//10)}{'░'*(10-p//10)} **{p}%**\n\n**{get_stupidity_comment(p)}**", parse_mode='markdown')

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.كدب$'))
    async def lying(event):
        if not event.is_reply: await event.edit("**• ❌ يرجى الرد على شخص**", parse_mode='markdown'); return
        u = await client.get_entity((await event.get_reply_message()).sender_id)
        p = get_random_percentage()
        await event.edit(f"🤥 **نسبة كذب {u.first_name or 'المستخدم'}:**\n{'█'*(p//10)}{'░'*(10-p//10)} **{p}%**\n\n**{get_lying_comment(p)}**", parse_mode='markdown')

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تهكير$'))
    async def hack(event):
        if not event.is_reply: await event.edit("**• ❌ يرجى الرد على شخص**", parse_mode='markdown'); return
        for m in HACK_MESSAGES: await event.edit(m, parse_mode='markdown'); await asyncio.sleep(1.2)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.قتل$'))
    async def kill(event):
        if not event.is_reply: await event.edit("**• ❌ يرجى الرد على شخص**", parse_mode='markdown'); return
        for m in random.choice(KILL_METHODS): await event.edit(f"**{m}**", parse_mode='markdown'); await asyncio.sleep(1.5)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.جروباتي$'))
    async def my_groups(event):
        await event.edit(f"**📊 عدد الجروبات:** {sum(1 async for d in client.iter_dialogs() if d.is_group)}", parse_mode='markdown')

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.قنواتي$'))
    async def my_channels(event):
        await event.edit(f"**📊 عدد القنوات:** {sum(1 async for d in client.iter_dialogs() if d.is_channel and not d.is_group)}", parse_mode='markdown')

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تونزي$'))
    async def top_interactions(event):
        interactions = {}
        async for dialog in client.iter_dialogs():
            try:
                async for message in client.iter_messages(dialog.id, limit=100):
                    if message.sender_id and message.sender_id != (await client.get_me()).id:
                        interactions[message.sender_id] = interactions.get(message.sender_id, 0) + 1
            except: continue
        if not interactions: await event.edit("**• ❌ لا توجد تفاعلات**", parse_mode='markdown'); return
        top = max(interactions, key=interactions.get)
        try: name = (await client.get_entity(top)).first_name or "مستخدم"
        except: name = "مستخدم"
        await event.edit(f"**🏆 الأكثر تفاعلاً:**\n👤 **{name}**\n💬 **{interactions[top]}**", parse_mode='markdown')

    for cmd in ['ضحك','قلب','قمر']:
        @client.on(events.NewMessage(outgoing=True, pattern=rf'^\.{cmd}$'))
        async def anim(event, name=cmd): asyncio.create_task(run_animation(event, name, 5))

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.وقف$'))
    async def stop_anim(event):
        stopped = sum(1 for k in list(active_animations.keys()) if k.startswith(str(event.chat_id)) and active_animations.pop(k, None))
        await event.edit(f"**• ⏹️ تم إيقاف {stopped}**" if stopped else "**• ❌ لا يوجد**", parse_mode='markdown')

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.يوت (.+)'))
    async def yt_audio(event):
        if not YTDLP_AVAILABLE: await event.edit("**• ❌ yt-dlp غير مثبتة**", parse_mode='markdown'); return
        q = event.pattern_match.group(1).strip()
        await event.edit("**• 🎵 جاري التحميل...**", parse_mode='markdown')
        fp = None
        try:
            info, fp = await asyncio.get_event_loop().run_in_executor(_DOWNLOAD_EXECUTOR, download_youtube_media, q, TEMP_DIR, True)
            t = info['title'][:52]+'...' if len(info['title'])>55 else info['title']
            await client.send_file(event.chat_id, fp, caption=f"{t}\n• {info['duration_str']} | ᥲᥙძᎥ᥆",
                                   attributes=[DocumentAttributeAudio(duration=info['duration'], title=info['title'], performer=info['uploader'])], supports_streaming=True)
            await event.delete()
        except Exception as e: await event.edit(f"**• ❌ {str(e)[:200]}**", parse_mode='markdown')
        finally: safe_remove(fp)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.فيد (.+)'))
    async def yt_video(event):
        if not YTDLP_AVAILABLE: await event.edit("**• ❌ yt-dlp غير مثبتة**", parse_mode='markdown'); return
        q = event.pattern_match.group(1).strip()
        await event.edit("**• 🎬 جاري التحميل...**", parse_mode='markdown')
        fp = None
        try:
            info, fp = await asyncio.get_event_loop().run_in_executor(_DOWNLOAD_EXECUTOR, download_youtube_media, q, TEMP_DIR, False)
            t = info['title'][:52]+'...' if len(info['title'])>55 else info['title']
            await client.send_file(event.chat_id, fp, caption=f"{t}\n• {info['duration_str']} | ᥎Ꭵძꫀ᥆",
                                   attributes=[DocumentAttributeVideo(duration=info['duration'], w=0, h=0, supports_streaming=True)], supports_streaming=True)
            await event.delete()
        except Exception as e: await event.edit(f"**• ❌ {str(e)[:200]}**", parse_mode='markdown')
        finally: safe_remove(fp)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.صوت$'))
    async def to_audio(event):
        if not event.is_reply: await event.edit("**• ❌ يرجى الرد على فيديو**", parse_mode='markdown'); return
        r = await event.get_reply_message()
        if not (r.video or r.document): await event.edit("**• ❌ يرجى الرد على فيديو**", parse_mode='markdown'); return
        await event.edit("**• 🎵 جاري التحويل...**", parse_mode='markdown')
        vp = ap = None
        try:
            vp = os.path.join(TEMP_DIR, f"v_{phone}_{int(time.time())}.mp4"); await client.download_media(r, vp)
            on = "فيديو محول"
            if r.video and hasattr(r,'message') and r.message: on = r.message[:100]
            elif r.document:
                for a in r.document.attributes:
                    if hasattr(a,'file_name') and a.file_name: on = os.path.splitext(a.file_name)[0]; break
            ai = await asyncio.get_event_loop().run_in_executor(_DOWNLOAD_EXECUTOR, convert_video_to_audio, vp, TEMP_DIR)
            ap = ai['path']
            t = clean_filename(on)[:52]+'...' if len(clean_filename(on))>55 else clean_filename(on)
            await client.send_file(event.chat_id, ap, caption=f"{t}\n• {ai['duration_str']} | ᥲᥙძᎥ᥆",
                                   attributes=[DocumentAttributeAudio(duration=int(ai['duration']), title=t, performer='محول')], supports_streaming=True)
            await event.delete()
        except Exception as e: await event.edit(f"**• ❌ {str(e)[:200]}**", parse_mode='markdown')
        finally: safe_remove(vp); safe_remove(ap)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.نسخ$'))
    async def transcribe(event):
        if not event.is_reply: await event.edit("**• ❌ يرجى الرد على صوتية/فيديو**", parse_mode='markdown'); return
        r = await event.get_reply_message()
        if not (r.voice or r.audio or r.video): await event.edit("**• ❌ يرجى الرد على صوتية/فيديو**", parse_mode='markdown'); return
        if not SR_AVAILABLE: await event.edit("**• ❌ مكتبة SpeechRecognition غير مثبتة**", parse_mode='markdown'); return
        await event.edit("**• 🎤 جاري التحويل...**", parse_mode='markdown')
        mp = wp = None
        try:
            mp = os.path.join(TEMP_DIR, f"m_{phone}_{int(time.time())}.ogg"); await client.download_media(r, mp)
            wp = mp.replace('.ogg','.wav').replace('.mp4','.wav')
            subprocess.run(['ffmpeg','-i',mp,'-ac','1','-ar','16000','-sample_fmt','s16',wp], capture_output=True, timeout=30)
            rec = sr.Recognizer()
            with sr.AudioFile(wp) as src: ad = rec.record(src)
            txt = None
            for l in ['ar-AR','en-US']:
                try: txt = rec.recognize_google(ad, language=l); break
                except: continue
            await event.edit(f"**📝 النص:**\n{txt}" if txt else "**• ❌ لم يتم التعرف**")
        except Exception as e: await event.edit(f"**• ❌ {str(e)[:150]}**")
        finally: safe_remove(mp); safe_remove(wp)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.استيك$'))
    async def to_sticker(event):
        if not event.is_reply or not PIL_AVAILABLE: await event.edit("**• ❌ يرجى الرد على صورة**", parse_mode='markdown'); return
        r = await event.get_reply_message()
        if not r.photo: await event.edit("**• ❌ الرد على صورة فقط**", parse_mode='markdown'); return
        await event.edit("**• 🔄 جاري التحويل...**", parse_mode='markdown')
        ip = sp = None
        try:
            ip = os.path.join(TEMP_DIR, f"i_{phone}_{int(time.time())}.jpg"); await client.download_media(r, ip)
            sp = ip.replace('.jpg','.webp')
            im = Image.open(ip).convert("RGBA"); im.thumbnail((512,512), Image.LANCZOS); im.save(sp, "WEBP", quality=80)
            await client.send_file(event.chat_id, sp, force_document=False); await event.delete()
        except Exception as e: await event.edit(f"**• ❌ {str(e)[:150]}**", parse_mode='markdown')
        finally: safe_remove(ip); safe_remove(sp)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بيك$'))
    async def to_photo(event):
        if not event.is_reply or not PIL_AVAILABLE: await event.edit("**• ❌ يرجى الرد على استيكر**", parse_mode='markdown'); return
        r = await event.get_reply_message()
        if not r.sticker: await event.edit("**• ❌ الرد على استيكر فقط**", parse_mode='markdown'); return
        await event.edit("**• 🔄 جاري التحويل...**", parse_mode='markdown')
        sp = ip = None
        try:
            sp = os.path.join(TEMP_DIR, f"s_{phone}_{int(time.time())}.webp"); await client.download_media(r, sp)
            ip = sp.replace('.webp','.png'); Image.open(sp).convert("RGBA").save(ip, "PNG")
            await client.send_file(event.chat_id, ip); await event.delete()
        except Exception as e: await event.edit(f"**• ❌ {str(e)[:150]}**", parse_mode='markdown')
        finally: safe_remove(sp); safe_remove(ip)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بن (.+)'))
    async def img_search(event):
        q = event.pattern_match.group(1).strip()
        if q.startswith('http'):
            await event.edit("**• 📷 جاري التحميل...**", parse_mode='markdown')
            fp = await asyncio.get_event_loop().run_in_executor(_DOWNLOAD_EXECUTOR, download_image, q, TEMP_DIR)
            if fp: await client.send_file(event.chat_id, fp); await event.delete(); safe_remove(fp)
            else: await event.edit("**• ❌ فشل**", parse_mode='markdown')
            return
        await event.edit(f"**• 🔍 جاري البحث...**", parse_mode='markdown')
        urls = await asyncio.get_event_loop().run_in_executor(_DOWNLOAD_EXECUTOR, search_images, q, 10)
        if not urls: await event.edit("**• ❌ لم يتم العثور**", parse_mode='markdown'); return
        s = 0
        for url in urls[:5]:
            try:
                fp = await asyncio.get_event_loop().run_in_executor(_DOWNLOAD_EXECUTOR, download_image, url, TEMP_DIR)
                if fp: await client.send_file(event.chat_id, fp); s+=1; safe_remove(fp)
                await asyncio.sleep(0.3)
            except: continue
        if s>0: await event.delete()
        else: await event.edit("**• ❌ فشل تحميل الصور**", parse_mode='markdown')

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ترجم(?: (.+))?$'))
    async def translate_cmd(event):
        text = None
        if event.is_reply: text = (await event.get_reply_message()).text
        if not text and event.pattern_match.group(1): text = event.pattern_match.group(1).strip()
        if not text: await event.edit("**• ❌ يرجى الرد أو كتابة نص**"); return
        await event.edit("**• 🔄 جاري الترجمة...**")
        translated = await asyncio.get_event_loop().run_in_executor(_DOWNLOAD_EXECUTOR, translate_text, text)
        await event.edit(f"**• الترجمة:**\n{translated}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.نت$'))
    async def speed_test(event):
        await event.edit("**• 📶 جاري القياس...**")
        r = await measure_speed()
        if r['success']: await event.edit(f"**📶 البنق:** {r['ping']}ms\n**• السرعة:** {r['speed']:.1f} Mbps")
        else: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.خرفة (.+)'))
    async def decorate(event):
        text = event.pattern_match.group(1).strip()
        if not text: await event.edit("**• ❌ اكتب نص**"); return
        res = [f"**🎨 زخرفة '{text}':**\n"]
        for i, s in enumerate(DECORATION_STYLES, 1): res.append(f"**{i}.** `{apply_decoration(text, s)}`")
        await event.edit('\n'.join(res), parse_mode='markdown')

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تاك$'))
    async def tag_all(event):
        if not event.is_group: await event.edit("**• ❌ للجروبات فقط**"); return
        tagging_active[phone] = True
        mentions = []
        async for u in client.iter_participants(event.chat_id):
            if not tagging_active.get(phone): break
            mentions.append(f"[\u200b](tg://user?id={u.id}){u.first_name or ''}")
        if mentions:
            for i in range(0, len(mentions), 5):
                if not tagging_active.get(phone): break
                await client.send_message(event.chat_id, ''.join(mentions[i:i+5])); await asyncio.sleep(1)
        await event.delete()

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غ تاك$'))
    async def stop_tag(event): tagging_active[phone]=False; await event.edit("**• ⏹️ تم إيقاف**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بلوكات$'))
    async def blocked(event):
        try:
            bl = await client(GetBlockedRequest(offset=0, limit=100))
            if not bl.users: await event.edit("**• 📋 لا يوجد**"); return
            res = "**📋 المحظورين:**\n"
            for u in bl.users[:20]: res += f"• [{u.first_name or ''}](tg://user?id={u.id})\n"
            await event.edit(res)
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.حظر$'))
    async def block(event):
        t = await resolve_user(event, client)
        if not t: await event.edit("**• ❌ يرجى الرد**"); return
        try: await client(BlockRequest(id=t)); await event.edit(f"**• 🚫 تم حظر {t.first_name or ''}**")
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غ حظر$'))
    async def unblock(event):
        t = await resolve_user(event, client)
        if not t: await event.edit("**• ❌ يرجى الرد**"); return
        try: await client(UnblockRequest(id=t)); await event.edit(f"**• ✅ تم فك حظر {t.first_name or ''}**")
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.كتم$'))
    async def mute(event):
        t = await resolve_user(event, client)
        if not t: await event.edit("**• ❌ يرجى الرد**"); return
        try:
            if event.is_group: await client(EditBannedRequest(event.chat_id, t.id, ChatBannedRights(until_date=None, send_messages=True)))
            muted_users[phone][t.id]=time.time()
            await event.edit(f"**• 🤐 تم كتم {t.first_name or ''}**")
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.قيد$'))
    async def restrict(event):
        if not event.is_group: await event.edit("**• ❌ للجروبات**"); return
        t = await resolve_user(event, client)
        if not t: await event.edit("**• ❌ يرجى الرد**"); return
        try:
            r = ChatBannedRights(until_date=None, send_messages=True, send_media=True, send_stickers=True, send_gifs=True, send_games=True, send_inline=True, embed_links=True)
            await client(EditBannedRequest(event.chat_id, t.id, r)); await event.edit(f"**• 🔒 تم تقييد {t.first_name or ''}**")
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.طرد$'))
    async def kick(event):
        if not event.is_group: await event.edit("**• ❌ للجروبات**"); return
        t = await resolve_user(event, client)
        if not t: await event.edit("**• ❌ يرجى الرد**"); return
        try: await client.kick_participant(event.chat_id, t.id); await event.edit(f"**• 👢 تم طرد {t.first_name or ''}**")
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.محظورين$'))
    async def banned_list(event):
        if not event.is_group: await event.edit("**• ❌ للجروبات فقط**"); return
        await event.edit("**• 📋 جاري الجلب...**")
        try:
            banned = await client(GetParticipantsRequest(event.chat_id, types.ChannelParticipantsKicked(), 0, 100, 0))
            if not banned.users: await event.edit("**• 📋 لا يوجد محظورين**"); return
            result = "**📋 المحظورين:**\n"
            for user in banned.users[:20]: result += f"• [{user.first_name or ''}](tg://user?id={user.id})\n"
            await event.edit(result)
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.فك محظور$'))
    async def unban_user(event):
        if not event.is_group: await event.edit("**• ❌ للجروبات فقط**"); return
        t = await resolve_user(event, client)
        if not t: await event.edit("**• ❌ يرجى الرد**"); return
        try: await client(EditBannedRequest(event.chat_id, t.id, ChatBannedRights(until_date=None))); await event.edit(f"**• ✅ تم فك حظر {t.first_name or ''}**")
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.فك محظورين$'))
    async def unban_all(event):
        if not event.is_group: await event.edit("**• ❌ للجروبات فقط**"); return
        await event.edit("**• 🔄 جاري فك حظر الجميع...**")
        try:
            banned = await client(GetParticipantsRequest(event.chat_id, types.ChannelParticipantsKicked(), 0, 200, 0))
            for user in banned.users:
                try: await client(EditBannedRequest(event.chat_id, user.id, ChatBannedRights(until_date=None))); await asyncio.sleep(0.5)
                except: continue
            await event.edit("**• ✅ تم فك حظر الجميع**")
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.فك كتم$'))
    async def unmute_user(event):
        if not event.is_group: await event.edit("**• ❌ للجروبات فقط**"); return
        t = await resolve_user(event, client)
        if not t: await event.edit("**• ❌ يرجى الرد**"); return
        try: await client(EditBannedRequest(event.chat_id, t.id, ChatBannedRights(until_date=None))); await event.edit(f"**• ✅ تم فك كتم {t.first_name or ''}**")
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.فك مكتومين$'))
    async def unmute_all(event):
        if not event.is_group: await event.edit("**• ❌ للجروبات فقط**"); return
        await event.edit("**• 🔄 جاري فك كتم الجميع...**")
        try:
            async for user in client.iter_participants(event.chat_id):
                try: await client(EditBannedRequest(event.chat_id, user.id, ChatBannedRights(until_date=None)))
                except: continue
            await event.edit("**• ✅ تم فك كتم الجميع**")
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.فك تقيد$'))
    async def unrestrict_user(event):
        if not event.is_group: await event.edit("**• ❌ للجروبات فقط**"); return
        t = await resolve_user(event, client)
        if not t: await event.edit("**• ❌ يرجى الرد**"); return
        try: await client(EditBannedRequest(event.chat_id, t.id, ChatBannedRights(until_date=None))); await event.edit(f"**• ✅ تم فك تقييد {t.first_name or ''}**")
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.فك مقيدين$'))
    async def unrestrict_all(event):
        if not event.is_group: await event.edit("**• ❌ للجروبات فقط**"); return
        await event.edit("**• 🔄 جاري فك تقييد الجميع...**")
        try:
            async for user in client.iter_participants(event.chat_id):
                try: await client(EditBannedRequest(event.chat_id, user.id, ChatBannedRights(until_date=None)))
                except: continue
            await event.edit("**• ✅ تم فك تقييد الجميع**")
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ايدي$'))
    async def get_id(event):
        t = await resolve_user(event, client)
        if not t: t = await client.get_entity(event.chat_id) if event.is_group else await client.get_me()
        info = f"**🆔 المعرفات:**\n**• الاسم:** {t.first_name or ''}"
        if t.last_name: info += f" {t.last_name}"
        info += f"\n**• اليوزر:** @{t.username}" if t.username else "\n**• اليوزر:** لا يوجد"
        info += f"\n**• ID:** `{t.id}`"
        await event.edit(info, parse_mode='markdown')

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.انشاء$'))
    async def creation_date(event):
        t = None
        if event.is_reply: t = await client.get_entity((await event.get_reply_message()).sender_id)
        elif event.is_private: t = await client.get_entity(event.chat_id)
        elif event.is_group or event.is_channel: t = await client.get_entity(event.chat_id)
        if not t: await event.edit("**• ❌ لا يمكن تحديد**"); return
        if hasattr(t,'date') and t.date:
            d = t.date.strftime('%Y-%m-%d %H:%M:%S')
            et = "الحساب" if hasattr(t,'username') and not t.broadcast else "القناة" if hasattr(t,'broadcast') and t.broadcast else "الجروب"
            await event.edit(f"**📅 تاريخ إنشاء {et}:**\n{d}")
        else: await event.edit("**• ❌ لا يمكن**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.عدد$'))
    async def msg_count(event):
        t = None
        if event.is_reply: t = await client.get_entity((await event.get_reply_message()).sender_id)
        else: t = await client.get_me()
        if not t: await event.edit("**• ❌ يرجى الرد**"); return
        c = 0
        try:
            async for m in client.iter_messages(event.chat_id, from_user=t.id):
                c+=1
                if c>=10000: break
        except:
            try:
                async for m in client.iter_messages(event.chat_id):
                    if m.sender_id==t.id: c+=1
                    if c>=10000: break
            except: pass
        await event.edit(f"**📊 عدد رسائل {t.first_name or 'المستخدم'}:** {c}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.رتبة$'))
    async def user_rank(event):
        if not event.is_group: await event.edit("**• ❌ للجروبات فقط**"); return
        t = await resolve_user(event, client)
        if not t: await event.edit("**• ❌ يرجى الرد على شخص**"); return
        try:
            participant = await client(functions.channels.GetParticipantRequest(event.chat_id, t.id))
            rank = "مالك" if isinstance(participant.participant, ChannelParticipantCreator) else "مشرف" if isinstance(participant.participant, ChannelParticipantAdmin) else "عضو"
            await event.edit(f"**🏅 رتبة {t.first_name or 'المستخدم'}:** {rank}")
        except: await event.edit(f"**🏅 رتبة {t.first_name or 'المستخدم'}:** عضو")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.حذف(?: (\d+))?$'))
    async def delete_msgs(event):
        c = int(event.pattern_match.group(1)) if event.pattern_match.group(1) else 1
        d = 0
        async for m in client.iter_messages(event.chat_id, limit=c+1):
            if m.out:
                try: await m.delete(); d+=1
                except: pass
        if d>0: await event.edit(f"**• 🗑️ تم حذف {d}**")
        else: await event.delete()

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.احذف$'))
    async def delete_chat(event):
        t = await resolve_user(event, client)
        if not t:
            if event.is_private: t = await client.get_entity(event.chat_id)
            else: await event.edit("**• ❌ يرجى الرد**"); return
        try: await client(DeleteHistoryRequest(peer=t, max_id=0, just_clear=False, revoke=True)); await event.edit("**• ✅ تم**")
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.فتح$'))
    async def open_group(event):
        if not event.is_group: await event.edit("**• ❌ للجروبات**"); return
        try: await client(EditChatDefaultBannedRightsRequest(event.chat_id, ChatBannedRights(until_date=None))); await event.edit("**• 🔓 تم الفتح**")
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.قفل$'))
    async def close_group(event):
        if not event.is_group: await event.edit("**• ❌ للجروبات**"); return
        try: await client(EditChatDefaultBannedRightsRequest(event.chat_id, ChatBannedRights(until_date=None, send_messages=True))); await event.edit("**• 🔒 تم القفل**")
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.مش$'))
    async def promote_mod(event):
        if not event.is_group: await event.edit("**• ❌ للجروبات**"); return
        t = await resolve_user(event, client)
        if not t: await event.edit("**• ❌ يرجى الرد**"); return
        try:
            r = ChatAdminRights(post_messages=True, delete_messages=True, ban_users=True, invite_users=True, pin_messages=True, add_admins=False, anonymous=False, manage_call=True)
            await client(EditAdminRequest(event.chat_id, t.id, r, "مشرف")); await event.edit(f"**• ⭐ تم رفع مشرف**")
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.اد$'))
    async def promote_admin(event):
        if not event.is_group: await event.edit("**• ❌ للجروبات**"); return
        t = await resolve_user(event, client)
        if not t: await event.edit("**• ❌ يرجى الرد**"); return
        try:
            r = ChatAdminRights(post_messages=True, delete_messages=True, ban_users=True, invite_users=True, pin_messages=True, add_admins=True, anonymous=False, manage_call=True, other=True)
            await client(EditAdminRequest(event.chat_id, t.id, r, "أدمن")); await event.edit(f"**• 👑 تم رفع أدمن**")
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.مالك$'))
    async def promote_owner(event):
        if not event.is_group: await event.edit("**• ❌ للجروبات**"); return
        t = await resolve_user(event, client)
        if not t: await event.edit("**• ❌ يرجى الرد**"); return
        try:
            r = ChatAdminRights(post_messages=True, delete_messages=True, ban_users=True, invite_users=True, pin_messages=True, add_admins=True, anonymous=True, manage_call=True, other=True)
            await client(EditAdminRequest(event.chat_id, t.id, r, "مالك")); await event.edit(f"**• 🤴 تم رفع مالك**")
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تن$'))
    async def demote(event):
        if not event.is_group: await event.edit("**• ❌ للجروبات**"); return
        t = await resolve_user(event, client)
        if not t: await event.edit("**• ❌ يرجى الرد**"); return
        try: await client(EditAdminRequest(event.chat_id, t.id, ChatAdminRights(), "")); await event.edit(f"**• ⬇️ تم التنزيل**")
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ضيف (\d+)$'))
    async def smart_add(event):
        if not event.is_group: await event.edit("**• ❌ للجروبات**"); return
        cnt = int(event.pattern_match.group(1))
        added = 0
        for d in await client.get_dialogs():
            if added>=cnt: break
            if d.is_group:
                try:
                    async for u in client.iter_participants(d.id, limit=5):
                        if added>=cnt: break
                        if u.bot or u.deleted: continue
                        try: await client(InviteToChannelRequest(event.chat_id, [u.id])); added+=1; await asyncio.sleep(3)
                        except FloodWaitError as e: await asyncio.sleep(e.seconds+1)
                        except: continue
                except: continue
        await event.edit(f"**• ✅ تم إضافة {added}**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غ ضيف$'))
    async def stop_add(event): await event.edit("**• ⏹️ تم إيقاف**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تسجيل$'))
    async def add_contact(event):
        t = await resolve_user(event, client)
        if not t: await event.edit("**• ❌ يرجى الرد**"); return
        try: await client(AddContactRequest(id=t, first_name=t.first_name or '', last_name=t.last_name or '', phone='', add_phone_privacy_exception=False)); await event.edit(f"**• 📇 تم**")
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ممول (\d+) (.+)$'))
    async def fund_add(event):
        if not event.is_group: await event.edit("**• ❌ للجروبات**"); return
        cnt, un = int(event.pattern_match.group(1)), event.pattern_match.group(2).strip('@')
        try: tg = await client.get_entity(un)
        except: await event.edit(f"**• ❌ لم يتم العثور**"); return
        added = 0
        try:
            async for u in client.iter_participants(event.chat_id, limit=cnt):
                if u.bot or u.deleted: continue
                try: await client(InviteToChannelRequest(tg, [u.id])); added+=1; await asyncio.sleep(2)
                except FloodWaitError as e: await asyncio.sleep(e.seconds+1)
                except: continue
        except: pass
        await event.edit(f"**• ✅ تم تسجيل {added}**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.اطردني$'))
    async def leave(event):
        if not event.is_group: await event.edit("**• ❌ للجروبات**"); return
        try: await client.delete_dialog(event.chat_id)
        except: pass

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ادمنز$'))
    async def admin_list(event):
        if not event.is_group: await event.edit("**• ❌ للجروبات**"); return
        admins = []
        async for a in client.iter_participants(event.chat_id, filter=ChannelParticipantsAdmins):
            admins.append(f"• {a.first_name or ''} {'@'+a.username if a.username else ''}")
        await event.edit("**👑 الأدمنز:**\n"+'\n'.join(admins[:20]) if admins else "**• ❌ لا يوجد**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.نيم (.+)'))
    async def set_name(event):
        nm = event.pattern_match.group(1).strip()
        if event.is_group:
            try: await client(EditAdminRequest(event.chat_id, (await client.get_me()).id, ChatAdminRights(), nm)); await event.edit("**• ✅ تم**")
            except: await event.edit("**• ❌ فشل**")
        else:
            try: await client(UpdateProfileRequest(first_name=nm)); await event.edit("**• ✅ تم**")
            except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بايو (.+)'))
    async def set_bio(event):
        try: await client(UpdateProfileRequest(about=event.pattern_match.group(1).strip()[:70])); await event.edit("**• ✅ تم**")
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.صورة$'))
    async def set_photo(event):
        if not event.is_reply: await event.edit("**• ❌ يرجى الرد على صورة**"); return
        r = await event.get_reply_message()
        if not r.photo: await event.edit("**• ❌ صورة فقط**"); return
        try:
            ph = await client.download_media(r); up = await client.upload_file(ph)
            if event.is_group: await client(EditPhotoRequest(event.chat_id, up))
            else: await client(UploadProfilePhotoRequest(file=up))
            await event.edit("**• ✅ تم**"); safe_remove(ph)
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تابع (.+)'))
    async def stalk(event):
        un = event.pattern_match.group(1).strip('@')
        try:
            t = await client.get_entity(un)
            await event.edit(f"**• 👀 جاري متابعة {t.first_name or un}...**")
            was_on, stalking_active[phone] = False, True
            while stalking_active.get(phone):
                e = await client.get_entity(t.id)
                if hasattr(e,'status'):
                    if isinstance(e.status, UserStatusOnline):
                        if not was_on: await event.edit(f"**• 🟢 {t.first_name or un} أونلاين!**"); was_on=True
                    elif was_on: await event.edit(f"**• 🔴 {t.first_name or un} أوفلاين**"); break
                await asyncio.sleep(10)
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غ تابع$'))
    async def stop_stalk(event): stalking_active[phone]=False; await event.edit("**• ⏹️ تم إيقاف**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ث$'))
    async def pin(event):
        if not event.is_reply: await event.edit("**• ❌ يرجى الرد**"); return
        try: await (await event.get_reply_message()).pin(); await event.edit("**• 📌 تم**")
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غ ث$'))
    async def unpin(event):
        if not event.is_reply: await event.edit("**• ❌ يرجى الرد**"); return
        try: await (await event.get_reply_message()).unpin(); await event.edit("**• ✅ تم**")
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.كول$'))
    async def create_call(event):
        if not event.is_group: await event.edit("**• ❌ للجروبات**"); return
        try: await client(CreateGroupCallRequest(event.chat_id, title='مكالمة')); await event.edit("**• 📞 تم**")
        except: await event.edit("**• ❌ فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.اوامر$'))
    async def cmds(event):
        await event.edit("""**📋 قائمة الأوامر:**
**🎨 التنسيق:** `.عريض` `.مائل` `.مشطوب` `.غ خط` `.خفي` `.غ خفي`
**😂 النسب:** `.حب` `.غباء` `.كدب`
**🎭 المزاح:** `.تهكير` `.قتل`
**📊 إحصائيات:** `.جروباتي` `.قنواتي` `.تونزي` `.بلوكات`
**🎪 أنيمشن:** `.ضحك` `.قلب` `.قمر` `.وقف`
**📥 تحميل:** `.يوت` `.فيد` `.صوت`
**🔧 تحويل:** `.نسخ` `.استيك` `.بيك` `.ترجم`
**🖼️ صور:** `.بن` `.صورة`
**👥 إدارة:** `.تاك` `.غ تاك` `.حظر` `.غ حظر` `.كتم` `.قيد` `.طرد`
**📝 معرفات:** `.ايدي` `.انشاء` `.عدد` `.رتبة`
**🗑️ حذف:** `.حذف` `.احذف`
**🚪 جروب:** `.فتح` `.قفل` `.ادمنز` `.اطردني` `.كول`
**👑 رفع:** `.مش` `.اد` `.مالك` `.تن`
**📇 جهات:** `.تسجيل` `.ممول` `.ضيف` `.غ ضيف`
**📌 تثبيت:** `.ث` `.غ ث`
**🔍 متابعة:** `.تابع` `.غ تابع`
**🎭 انتحال:** `.انتحل` `.غ انتحل`
**🎭 تقليد:** `.قلد` `.غ تقليد`
**🔤 زخرفة:** `.خرفة`
**📶 سرعة:** `.نت`
**ℹ️ معلومات:** `.اوامر` `.سورس` `.المساحة` `.تنظيف`""", parse_mode='markdown')

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.سورس$'))
    async def src(event): await event.edit("**👨‍💻 SOURCE:**\n**• ذكاء اصطناعي**\n**• نسخة 2024**", parse_mode='markdown')

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.المساحة$'))
    async def spc(event): await event.edit(f"**📊 المساحة:** {get_free_space_mb():.1f} MB", parse_mode='markdown')

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تنظيف$'))
    async def cln(event):
        c = clean_temp_files(); await event.edit(f"**✅ تم تنظيف {c} ملف**", parse_mode='markdown')

    @client.on(events.NewMessage(incoming=True))
    async def auto_taqleed(event):
        if event.sender_id in taqleed_users.get(phone, {}) and event.text and not event.text.startswith('.'):
            await asyncio.sleep(0.3)
            try: await event.reply(event.text)
            except: pass

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.قلد$'))
    async def taq(event):
        t = await resolve_user(event, client)
        if t: taqleed_users[phone][t.id]=True; await event.edit("**• ✅ تم**")
        elif event.is_reply: taqleed_users[phone][(await event.get_reply_message()).sender_id]=True; await event.edit("**• ✅ تم**")
        else: await event.edit("**• ❌ يرجى الرد**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غ تقليد$'))
    async def notaq(event):
        t = await resolve_user(event, client)
        if t and t.id in taqleed_users.get(phone,{}): del taqleed_users[phone][t.id]; await event.edit("**• ✅ تم**")
        else: await event.edit("**• ❌ لا يوجد**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.انتحل$'))
    async def ent7al(event):
        track_command(phone, ".انتحال"); await event.edit("**• 🔄 جاري...**", parse_mode='markdown')
        tu = await resolve_user(event, client)
        if not tu:
            if event.is_reply: tu = await client.get_entity((await event.get_reply_message()).sender_id)
            elif event.is_private: tu = await client.get_entity(event.chat_id)
        if not tu: await event.edit("**• ❌ فشل**", parse_mode='markdown'); return
        ti = await get_user_info_full(client, tu.id)
        if not ti: await event.edit("**• ❌ فشل**", parse_mode='markdown'); return
        me = await client.get_me(); client_me[phone]=me
        orig = {'first_name': me.first_name or '', 'last_name': me.last_name or '', 'about': '', 'added_photo_id': None}
        try:
            fu = await client(GetFullUserRequest('me'))
            if fu.full_user.about: orig['about']=fu.full_user.about
        except: pass
        try: await client(UpdateProfileRequest(first_name=ti['first_name'], last_name=ti['last_name'])); await asyncio.sleep(1)
        except FloodWaitError as e: await asyncio.sleep(e.seconds)
        except: pass
        try: await client(UpdateProfileRequest(about=ti['bio'][:70] if ti['bio'] else ''))
        except: pass
        ok, aid = await change_profile_photo(client, tu.id, phone)
        if ok and aid: orig['added_photo_id']=aid
        ent7al_original[phone]=orig; ent7al_users[phone]=True
        await event.edit("**• ✅ تم**", parse_mode='markdown')

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غ انتحل$'))
    async def unent7al(event):
        if not ent7al_users.get(phone): await event.edit("**• ❌ لا يوجد**", parse_mode='markdown'); return
        orig = ent7al_original[phone]
        try: await client(UpdateProfileRequest(first_name=orig.get('first_name',''), last_name=orig.get('last_name','')))
        except: pass
        if orig.get('added_photo_id'):
            try: await client(DeletePhotosRequest(id=[InputPhoto(id=orig['added_photo_id'], access_hash=0, file_reference=b'')]))
            except: pass
        try: await client(UpdateProfileRequest(about=orig.get('about','')))
        except: pass
        ent7al_users[phone]=False; ent7al_original[phone]={}
        await event.edit("**• ✅ تم**", parse_mode='markdown')

    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private and not e.out))
    async def cache_msg(event):
        if event.sender_id == (await client.get_me()).id: return
        message_cache.setdefault(event.chat_id, {})[event.id] = event.text or "<وسائط>"

    @client.on(events.MessageEdited(incoming=True, func=lambda e: e.is_private and not e.out))
    async def notify_edit(event):
        if event.sender_id == (await client.get_me()).id: return
        u = await event.get_sender()
        nm = f"{u.first_name or ''} {u.last_name or ''}".strip()
        old = message_cache.get(event.chat_id, {}).get(event.id, "غير معروف")
        new = event.text or "<وسائط>"
        await client.send_message("me", f"**📝 {nm} عدل رسالة**\n**من:** {old}\n**إلى:** {new}")
        message_cache.setdefault(event.chat_id, {})[event.id] = new

    @client.on(events.MessageDeleted(incoming=True, func=lambda e: e.is_private and not e.out))
    async def notify_delete(event):
        for cid, mids in event.deleted_ids.items():
            for mid in mids:
                if cid in message_cache and mid in message_cache[cid]:
                    txt = message_cache[cid][mid]
                    nm = "مستخدم"
                    try:
                        ch = await client.get_entity(cid)
                        nm = ch.first_name or "مستخدم"
                    except: pass
                    await client.send_message("me", f"**🗑️ {nm} حذف رسالة**\n**{txt}**")
                    del message_cache[cid][mid]

    async def auto_cleanup():
        while True:
            await asyncio.sleep(1800)
            if get_free_space_mb() < MIN_FREE_SPACE_MB * 2: clean_temp_files()
    asyncio.create_task(auto_cleanup())

    logger.info(f"✅ جميع الأوامر جاهزة لـ {phone}")
