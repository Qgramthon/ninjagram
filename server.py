import asyncio
import threading
import logging
import time
import random
import json
import os
import sys
import requests
import io
import uuid
from collections import Counter
from datetime import datetime, timedelta

from flask import Flask
from telethon import TelegramClient, events
from telethon.errors import (
    SessionPasswordNeededError, FloodWaitError, PhoneCodeInvalidError,
    PhoneCodeExpiredError, PhoneNumberInvalidError
)
from telethon.sessions import StringSession
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.contacts import BlockRequest, UnblockRequest, ImportContactsRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import (
    ToggleDialogPinRequest, GetHistoryRequest, GetDialogsRequest,
    EditChatDefaultBannedRightsRequest
)
from telethon.tl.functions.phone import RequestCallRequest
from telethon.tl.types import (
    InputPeerChannel, InputPeerUser, InputPhoneContact,
    ChatBannedRights, PhoneCallProtocol
)
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon.tl.functions.users import GetFullUserRequest

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ======================== الإعدادات الأساسية ========================
BOT_TOKEN = '8887748662:AAFgLMUO2eXpYzityDj35-IDTLywtdO8S8Q'
BOT_API_ID = 2040
BOT_API_HASH = 'b18441a1ff607e10a989891a5462e627'

DATA_DIR = '/data' if os.path.exists('/data') else '.'
os.makedirs(DATA_DIR, exist_ok=True)
SESSION_FILE = os.path.join(DATA_DIR, 'active_sessions.json')
BANK_FILE = os.path.join(DATA_DIR, 'bank.json')
TEMP_DIR = os.path.join(DATA_DIR, 'temp')
os.makedirs(TEMP_DIR, exist_ok=True)

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

active_clients = {}
client_me = {}
pending_logins = {}

muted_users = {}
taqleed_users = {}
banned_users = {}
bold_mode = {}
disabled_users = {}
ent7al_users = {}
ent7al_original = {}
command_stats = {}
user_info_cache = {}

bank_data = {}
bank_counter = 1000

# ======================== إطارات الأنيميشن ========================
LAUGH_FRAMES = [
    "😂🤣😭😹", "🤣😂😭😹", "🤣😭😂😹", "😭🤣😂😹",
    "😭🤣😹😂", "😭😹🤣😂", "😹😭🤣😂", "😹😂🤣😭"
]

CLOUD_FRAMES = [
    "☁️⛅🌤️☁️", "⛅☁️🌤️☁️", "⛅🌤️☁️☁️", "🌤️⛅☁️☁️"
]

HEART_FRAMES = [
    "❤️🧡💛💚", "🧡❤️💛💚", "🧡💛❤️💚", "💛🧡❤️💚"
]

ROSE_FRAMES = [
    "🌹🥀🌷🌸", "🥀🌹🌷🌸", "🥀🌷🌹🌸", "🌷🥀🌹🌸"
]

X_FRAMES = ["❌", "❎", "✖️", "❌❌", "❎❎", "✖️✖️"]
O_FRAMES = ["⭕", "⚪", "🔴", "🟢", "🔵", "⭕⭕"]

# ======================== دوال عامة ========================
def track_command(phone: str, command: str):
    if phone not in command_stats:
        command_stats[phone] = Counter()
    command_stats[phone][command] += 1

def is_dev(phone: str) -> bool:
    return phone == "+201096371454"

async def get_user_name(client, user_id):
    try:
        user = await client.get_entity(user_id)
        return user.first_name or "User"
    except:
        return "User"

async def animate_emojis(event, frames, speed=0.4):
    for frame in frames:
        await event.edit(f"**{frame}**")
        await asyncio.sleep(speed)

# ======================== Gemini AI ========================
GEMINI_API_KEY = "AQ.Ab8RN6IJ52RfamXKX6nNJOglTwDarnQyUIh9uzITyqK5iqwm7w"

def ask_gemini(question: str) -> str:
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
        headers = {'Content-Type': 'application/json'}
        data = {"contents": [{"parts": [{"text": question}]}]}
        response = requests.post(url, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text'][:2000]
    except:
        pass
    return None

# ======================== نظام البنك ========================
def load_bank():
    global bank_data, bank_counter
    try:
        if os.path.exists(BANK_FILE):
            with open(BANK_FILE, 'r') as f:
                data = json.load(f)
                bank_data = data.get('accounts', {})
                bank_counter = data.get('counter', 1000)
    except:
        bank_data = {}
        bank_counter = 1000

def save_bank():
    try:
        with open(BANK_FILE, 'w') as f:
            json.dump({'accounts': bank_data, 'counter': bank_counter}, f)
    except:
        pass

load_bank()

def get_bank_account(phone: str):
    return bank_data.get(phone)

def create_bank_account(phone: str, bank_name: str):
    global bank_counter
    bank_counter += 1
    account = {"phone": phone, "bank": bank_name, "account_number": str(bank_counter), "balance": 500, "fame": 0, "title": "مبتدئ", "last_gift": ""}
    bank_data[phone] = account
    save_bank()
    return account

def update_fame_title(acc):
    fame = acc['fame']
    if fame >= 500: acc['title'] = "اسطورة"
    elif fame >= 200: acc['title'] = "مشهور"
    elif fame >= 100: acc['title'] = "محبوب"
    elif fame >= 50: acc['title'] = "معروف"
    elif fame >= 20: acc['title'] = "نشيط"
    else: acc['title'] = "مبتدئ"

# ======================== إدارة الجلسات ========================
async def save_all_sessions():
    sessions = {}
    for phone, client in active_clients.items():
        if client.is_connected():
            sessions[phone] = {'session': client.session.save(), 'api_id': client.api_id, 'api_hash': client.api_hash}
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
                client_me[phone] = await client.get_me()
                asyncio.ensure_future(run_userbot(client, phone), loop=main_loop)
                logger.info(f"✅ تم تحميل حساب: {phone}")
        except Exception as e:
            logger.error(f"❌ فشل تحميل حساب {phone}: {e}")

# ======================== وظائف الانتحال ========================
async def get_user_info_full(client, user_id):
    try:
        user = await client.get_entity(user_id)
        name = user.first_name or "غير معروف"
        if user.last_name: name += f" {user.last_name}"
        username = f"@{user.username}" if user.username else "لا يوجد"
        bio = ""
        try:
            full = await client(GetFullUserRequest(user_id))
            if full.full_user.about: bio = full.full_user.about
        except: pass
        return {'name': name, 'first_name': user.first_name or '', 'last_name': user.last_name or '', 'username': username, 'bio': bio, 'id': user.id}
    except:
        return None

async def change_profile_photo(client, user_id, phone):
    try:
        old_photos = await client.get_profile_photos('me', limit=10)
        for p in old_photos:
            try: await client(DeletePhotosRequest(id=[p])); await asyncio.sleep(0.5)
            except: pass
        if old_photos: await asyncio.sleep(2)
        photo_bytes = await client.download_profile_photo(user_id, file=bytes)
        if not photo_bytes: return False
        for attempt in range(2):
            try:
                uploaded = await client.upload_file(photo_bytes, file_name="photo.jpg")
                await client(UploadProfilePhotoRequest(file=uploaded))
                await asyncio.sleep(2)
                me = await client.get_me()
                if me.photo: return True
                if PIL_AVAILABLE and attempt == 0:
                    img = Image.open(io.BytesIO(photo_bytes))
                    if img.mode != 'RGB': img = img.convert('RGB')
                    buf = io.BytesIO(); img.save(buf, format='JPEG', quality=85)
                    photo_bytes = buf.getvalue()
                else: break
            except FloodWaitError as e: await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"Upload error: {e}")
                break
        return False
    except Exception as e:
        logger.error(f"Photo change fatal error: {e}")
        return False

# ======================== تشغيل userbot ========================
async def run_userbot(client, phone):
    try:
        await setup_handlers(client, phone)
        me = await client.get_me()
        logger.info(f"🤖 UserBot نشط: {me.first_name} ({phone})")
        await client.run_until_disconnected()
    except Exception as e:
        logger.error(f"❌ خطأ في حساب {phone}: {e}")
    finally:
        if phone in active_clients:
            del active_clients[phone]

async def setup_handlers(client, phone):
    if phone not in muted_users:
        muted_users[phone] = {}
        taqleed_users[phone] = {}
        banned_users[phone] = {}
        bold_mode[phone] = False
        disabled_users[phone] = False
        ent7al_users[phone] = False
        ent7al_original[phone] = {}
        command_stats[phone] = Counter()

    @client.on(events.NewMessage(incoming=True))
    async def auto_mute(event):
        if event.is_private and event.sender_id in muted_users.get(phone, {}):
            try: await event.delete()
            except: pass

    @client.on(events.NewMessage(incoming=True))
    async def auto_taqleed(event):
        sender_id = event.sender_id
        if sender_id and sender_id in taqleed_users.get(phone, {}):
            if event.text and not event.text.startswith('.'):
                await asyncio.sleep(0.3)
                try: await event.reply(event.text)
                except: pass

    @client.on(events.NewMessage(outgoing=True))
    async def auto_bold(event):
        if bold_mode.get(phone, False) and event.text and not event.text.startswith('.'):
            try: await event.edit(f"**{event.text}**")
            except: pass

    # ==================== سورس ====================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.سورس$'))
    async def src(event):
        await event.edit("**⚜️ Rolex Telethon**\n\n• المطور: ƚᥲɦ᥆ᥙꪀ\n• قناة السورس: @Q_g_r_a_m\n• للأوامر: .اوامر", parse_mode='md')

    # ==================== اوامر ====================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.اوامر$'))
    async def cmds(event):
        await event.edit("""**اوامر السورس 𔓕**
ايدي ا | تقليد غ تقليد | خط غ خط
اسم + الاسم | بايو + البايو | ث غ ث
اضافة + عدد | عدد | حذف + عدد | رن
قفل فتح | كتم غ كتم | حظر غ حظر
تقيد غ تقييد | تهكير | انتحال الغاء انتحال
ذكاء + سؤال | بوت + سؤال | صراحة | كت
ضحك غيوم قلوب ورود | غباء | تحويل + رقم
رفع شحات حمار غبي سباك مالك ادمن
حسابي انشاء بنك | فلوسي توب فلوس
هدية قمار | نرد عملة | سرقة
توب شهرة شهرتي | شراء لقب | اكس او
اوامر سورس""", parse_mode='md')

    # ==================== ايدي ====================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.(ايدي|ا)$'))
    async def id_cmd(event):
        await event.delete()
        user = None
        if event.is_reply: user = await client.get_entity((await event.get_reply_message()).sender_id)
        elif event.is_group: user = await client.get_entity(event.sender_id)
        else: user = await client.get_entity(event.chat_id)
        if not user: return
        lines = [f"ꪀᥲꪔꫀ {user.first_name or ''} {user.last_name or ''}".strip()]
        if user.username: lines.append(f"ᥙ᥉ꫀɾ @{user.username}")
        try:
            full = await client.get_entity(user.id)
            if hasattr(full, 'about') and full.about: lines.append(f"ᑲᎥ᥆ {full.about[:50]}")
        except: pass
        lines.append(f"Ꭵძ {user.id}")
        await client.send_message(event.chat_id, "\n".join(lines))

    # ==================== تقليد ====================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تقليد$'))
    async def taq(event):
        target = None
        if event.is_reply: target = (await event.get_reply_message()).sender_id
        elif event.is_private: target = event.chat_id
        if target: taqleed_users[phone][target] = True; await event.edit("**• يتم التقليد**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غ تقليد$'))
    async def notaq(event):
        target = None
        if event.is_reply: target = (await event.get_reply_message()).sender_id
        elif event.is_private: target = event.chat_id
        if target and target in taqleed_users.get(phone, {}): del taqleed_users[phone][target]
        await event.edit("**• تم فك التقليد**")

    # ==================== خط ====================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.خط$'))
    async def bold(event): bold_mode[phone] = True; await event.edit("**• تم تفعيل الخط العريض**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غ خط$'))
    async def nobold(event): bold_mode[phone] = False; await event.edit("**• تم الغاء الخط العريض**")

    # ==================== اسم ====================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.اسم (.+)'))
    async def name(event):
        try: await client(UpdateProfileRequest(first_name=event.pattern_match.group(1).strip(), last_name='')); await event.edit("**• تم تغيير الاسم**")
        except: await event.edit("**• فشل**")

    # ==================== بايو ====================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بايو (.+)'))
    async def bio(event):
        try: await client(UpdateProfileRequest(about=event.pattern_match.group(1).strip())); await event.edit("**• تم تغيير البايو**")
        except: await event.edit("**• فشل**")

    # ==================== ث / غ ث ====================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ث$'))
    async def pin_msg(event):
        try:
            if event.is_reply: await (await event.get_reply_message()).pin(); await event.edit("**• تم التثبيت**")
            else: await client(ToggleDialogPinRequest(peer=event.input_chat, pinned=True)); await event.edit("**• تم تثبيت المحادثة**")
        except: await event.edit("**• فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غ ث$'))
    async def unpin_msg(event):
        try:
            if event.is_reply: await (await event.get_reply_message()).unpin(); await event.edit("**• تم الغاء التثبيت**")
            else: await client(ToggleDialogPinRequest(peer=event.input_chat, pinned=False)); await event.edit("**• تم الغاء تثبيت المحادثة**")
        except: await event.edit("**• فشل**")

    # ==================== ضحك ====================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ضحك$'))
    async def laugh(event): await animate_emojis(event, LAUGH_FRAMES, 0.4)

    # ==================== غيوم ====================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غيوم$'))
    async def clouds(event): await animate_emojis(event, CLOUD_FRAMES, 0.4)

    # ==================== قلوب ====================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.قلوب$'))
    async def hearts(event): await animate_emojis(event, HEART_FRAMES, 0.4)

    # ==================== ورود ====================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ورود$'))
    async def roses(event): await animate_emojis(event, ROSE_FRAMES, 0.4)

    # ==================== غباء ====================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غباء$'))
    async def stupidity(event):
        target_name = "User"
        if event.is_reply: target_name = await get_user_name(client, (await event.get_reply_message()).sender_id)
        elif event.is_private: target_name = await get_user_name(client, event.chat_id)
        await event.edit(f"**{target_name}'s stupidity: {random.randint(60, 100)}%**")

    # ==================== تحويل ====================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تحويل (\d+)'))
    async def transfer(event):
        amount = event.pattern_match.group(1)
        target_name = "User"
        if event.is_reply: target_name = await get_user_name(client, (await event.get_reply_message()).sender_id)
        elif event.is_private: target_name = await get_user_name(client, event.chat_id)
        await event.edit(f"**Sent {amount} USD to beggar {target_name}**")

    # ==================== رفع ====================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.رفع شحات$'))
    async def raf3_shahat(event):
        target_name = "User"
        if event.is_reply: target_name = await get_user_name(client, (await event.get_reply_message()).sender_id)
        elif event.is_private: target_name = await get_user_name(client, event.chat_id)
        await event.edit(f"**Promoted {target_name} to Beggar**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.رفع حمار$'))
    async def raf3_hmar(event):
        target_name = "User"
        if event.is_reply: target_name = await get_user_name(client, (await event.get_reply_message()).sender_id)
        elif event.is_private: target_name = await get_user_name(client, event.chat_id)
        await event.edit(f"**Promoted {target_name} to Donkey**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.رفع غبي$'))
    async def raf3_ghaby(event):
        target_name = "User"
        if event.is_reply: target_name = await get_user_name(client, (await event.get_reply_message()).sender_id)
        elif event.is_private: target_name = await get_user_name(client, event.chat_id)
        await event.edit(f"**Promoted {target_name} to Stupid**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.رفع سباك$'))
    async def raf3_sabbak(event):
        target_name = "User"
        if event.is_reply: target_name = await get_user_name(client, (await event.get_reply_message()).sender_id)
        elif event.is_private: target_name = await get_user_name(client, event.chat_id)
        await event.edit(f"**Promoted {target_name} to Plumber**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.رفع مالك$'))
    async def raf3_malek(event):
        target_name = "User"
        if event.is_reply: target_name = await get_user_name(client, (await event.get_reply_message()).sender_id)
        elif event.is_private: target_name = await get_user_name(client, event.chat_id)
        await event.edit(f"**Promoted {target_name} to King**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.رفع ادمن$'))
    async def raf3_admin(event):
        target_name = "User"
        if event.is_reply: target_name = await get_user_name(client, (await event.get_reply_message()).sender_id)
        elif event.is_private: target_name = await get_user_name(client, event.chat_id)
        await event.edit(f"**Promoted {target_name} to Admin**")

    # ==================== تهكير ====================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تهكير$'))
    async def hack(event):
        n = "الضحية"
        if event.is_reply:
            try: n = (await client.get_entity((await event.get_reply_message()).sender_id)).first_name
            except: pass
        await event.edit("**جاري التهكير**"); await asyncio.sleep(1)
        await event.edit("**تم اختراق 50%**"); await asyncio.sleep(1)
        await event.edit(f"**تم تهكير {n} بنجاح**")

    # ==================== ذكاء ====================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ذكاء (.+)'))
    async def ai_cmd(event):
        question = event.pattern_match.group(1).strip()
        await event.edit("**• جاري التفكير**")
        answer = await asyncio.get_event_loop().run_in_executor(None, ask_gemini, question)
        await event.edit(f"**{answer}**" if answer else "**• فشل**")

    # ==================== بوت ====================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بوت (.+)'))
    async def bot_cmd(event):
        question = event.pattern_match.group(1).strip()
        await event.edit("**• جاري التفكير**")
        prompt = f"أنت بوت تيليجرام اسمه كيوجرام. أجب بالعربية. {question}"
        answer = await asyncio.get_event_loop().run_in_executor(None, ask_gemini, prompt)
        await event.edit(f"**{answer}**" if answer else "**• فشل**")

    # ==================== صراحة ====================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.صراحة$'))
    async def sarah(event):
        await event.edit("**• جاري توليد سؤال صراحة**")
        prompt = "أعطني سؤال صراحة واحد فقط، سؤال جريء ومحرج للعبة الصراحة بين الأصدقاء. أجب بالسؤال فقط."
        answer = await asyncio.get_event_loop().run_in_executor(None, ask_gemini, prompt)
        await event.edit(f"**{answer}**" if answer else "**• فشل**")

    # ==================== كت ====================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.كت$'))
    async def kat(event):
        await event.edit("**• جاري توليد سؤال**")
        prompt = "أعطني سؤال واحد من أسئلة لعبة كت، سؤال جريء ومحرخ. أجب بالسؤال فقط."
        answer = await asyncio.get_event_loop().run_in_executor(None, ask_gemini, prompt)
        await event.edit(f"**{answer}**" if answer else "**• فشل**")

    # ==================== بنك ====================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.حسابي$'))
    async def bank_my_account(event):
        acc = get_bank_account(phone)
        if not acc: await event.edit("**• معندكش حساب**\n• .انشاء بنك + الاهلي/القاهرة/مصر")
        else: await event.edit(f"**🏦 حسابي**\n**البنك:** بنك {acc['bank']}\n**الرقم:** {acc['account_number']}\n**الرصيد:** {acc['balance']} جنيه\n**الشهرة:** {acc['fame']}\n**اللقب:** {acc['title']}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.انشاء بنك (.+)'))
    async def bank_create(event):
        bank_name = event.pattern_match.group(1).strip()
        if bank_name not in ["الاهلي", "القاهرة", "مصر"]: await event.edit("**• اختر: الاهلي, القاهرة, مصر**"); return
        if get_bank_account(phone): await event.edit("**• عندك حساب بالفعل**"); return
        acc = create_bank_account(phone, bank_name)
        await event.edit(f"**✅ تم فتح حسابك!**\n**البنك:** بنك {bank_name}\n**الرقم:** {acc['account_number']}\n**الرصيد:** 500 جنيه")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.فلوسي$'))
    async def bank_balance(event):
        acc = get_bank_account(phone)
        if not acc: await event.edit("**• معندكش حساب**")
        else: await event.edit(f"**💰 رصيدك: {acc['balance']} جنيه**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.توب فلوس$'))
    async def bank_top_money(event):
        if not bank_data: await event.edit("**• لا يوجد حسابات**"); return
        sorted_accs = sorted(bank_data.items(), key=lambda x: x[1]['balance'], reverse=True)
        text = "**🏆 توب الاغنياء:**\n\n"
        for i, (p, acc) in enumerate(sorted_accs[:10], 1):
            name = active_clients.get(p) and (await client_me[p]).first_name or p
            text += f"{i}. {name}: {acc['balance']} جنيه\n"
        await event.edit(text)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.هدية$'))
    async def bank_daily_gift(event):
        acc = get_bank_account(phone)
        if not acc: await event.edit("**• معندكش حساب**"); return
        today = datetime.now().strftime("%Y-%m-%d")
        if acc.get('last_gift') == today: await event.edit("**• استلمت هديتك النهاردة**"); return
        gift = random.randint(50, 300)
        acc['balance'] += gift; acc['last_gift'] = today; acc['fame'] += 1
        update_fame_title(acc); save_bank()
        await event.edit(f"**🎁 هديتك: {gift} جنيه**\n**💰 رصيدك: {acc['balance']}**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.قمار (\d+)'))
    async def bank_gamble(event):
        acc = get_bank_account(phone)
        if not acc: await event.edit("**• معندكش حساب**"); return
        amount = int(event.pattern_match.group(1))
        if amount > acc['balance']: await event.edit("**• فلوسك مش كفاية**"); return
        await event.edit("**🎰 جاري القمار...**"); await asyncio.sleep(1)
        if random.random() < 0.45:
            win = amount * 2; acc['balance'] += win; acc['fame'] += 2
            update_fame_title(acc); save_bank()
            await event.edit(f"**🎉 كسبت! +{win} جنيه**")
        else: acc['balance'] -= amount; save_bank(); await event.edit(f"**💔 خسرت {amount} جنيه**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.نرد$'))
    async def bank_dice(event):
        acc = get_bank_account(phone)
        if not acc: await event.edit("**• معندكش حساب**"); return
        my_roll = random.randint(1, 6); bot_roll = random.randint(1, 6)
        await event.edit(f"**🎲 انت: {my_roll} | البوت: {bot_roll}**")
        if my_roll > bot_roll: acc['balance'] += 50; save_bank(); await event.edit(f"**🎉 كسبت 50 جنيه!**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.عملة$'))
    async def bank_coin(event): await event.edit(f"**🪙 {random.choice(['ملك', 'كتابة'])}**")

    # ==================== ألعاب ====================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.اكس$'))
    async def game_x(event): await animate_emojis(event, X_FRAMES, 0.3)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.او$'))
    async def game_o(event): await animate_emojis(event, O_FRAMES, 0.3)

    # ==================== أوامر المالك ====================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.احصائيات$'))
    async def dev_stats(event):
        if not is_dev(phone): return
        await event.edit(f"**📊 احصائيات**\n**المستخدمين:** {len(active_clients)}\n**الاوامر:** {sum(len(c) for c in command_stats.values())}\n**حسابات بنك:** {len(bank_data)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.المستخدمين$'))
    async def dev_users(event):
        if not is_dev(phone): return
        users_list = [f"{p} - {client_me.get(p, {}).get('first_name', '???')}" for p in active_clients]
        await event.edit("**👥 المستخدمين:**\n" + "\n".join(users_list[:20]))

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ترند$'))
    async def dev_trend(event):
        if not is_dev(phone): return
        all_cmds = Counter()
        for p, cmds in command_stats.items(): all_cmds.update(cmds)
        text = "**📈 ترند:**\n"
        for i, (cmd, count) in enumerate(all_cmds.most_common(10), 1): text += f"{i}. {cmd}: {count}\n"
        await event.edit(text)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.اذاعة (.+)'))
    async def dev_broadcast(event):
        if not is_dev(phone): return
        msg = event.pattern_match.group(1)
        await event.edit(f"**• جاري الاذاعة لـ {len(active_clients)} مستخدم**")
        sent = 0
        for p, c in active_clients.items():
            try: await c.send_message('me', f"**📢 اذاعة:**\n{msg}"); sent += 1; await asyncio.sleep(0.5)
            except: pass
        await event.edit(f"**• تم الارسال لـ {sent} مستخدم**")

    logger.info(f"✅ تم تحميل جميع الأوامر لـ {phone}")

# ======================== بوت التنصيب ========================
@bot.on(events.NewMessage(pattern='/ping'))
async def bot_ping(event):
    await event.respond('Pong!')

@bot.on(events.NewMessage(pattern='/start'))
async def bot_start(event):
    await event.respond(
        "🜲 **مرحباً بك في بوت تنصيب Rolex Telethon**\n\n"
        "لتنصيب حسابك، أرسل:\n"
        "`/setup` واتبع التعليمات.\n\n"
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

async def finish_setup(event, uid):
    data = pending_logins[uid]
    client = data['client']
    phone = data['phone']
    api_id = data['api_id']
    api_hash = data['api_hash']
    session_str = client.session.save()
    del pending_logins[uid]

    if await start_userbot(phone, session_str, api_id, api_hash):
        await event.respond("✅ **تم تنصيب حسابك بنجاح!**\n\nيمكنك الآن استخدام أوامر السورس على حسابك.")
    else:
        await event.respond("❌ فشل تشغيل الحساب بعد التفعيل.")

async def start_userbot(phone, session_str, api_id, api_hash):
    client = TelegramClient(StringSession(session_str), api_id, api_hash)
    await client.connect()
    if await client.is_user_authorized():
        active_clients[phone] = client
        client_me[phone] = await client.get_me()
        asyncio.ensure_future(run_userbot(client, phone), loop=main_loop)
        await save_all_sessions()
        return True
    return False

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
