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
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.sessions import StringSession
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.contacts import BlockRequest, UnblockRequest, AddContactRequest, ImportContactsRequest
from telethon.tl.functions.channels import JoinChannelRequest, EditAdminRequest, EditPhotoRequest
from telethon.tl.functions.messages import ToggleDialogPinRequest, ExportChatInviteRequest, EditChatDefaultBannedRightsRequest
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.functions.phone import CreateGroupCallRequest, DiscardGroupCallRequest
from telethon.tl.functions.channels import CreateChannelRequest, EditAdminRequest, InviteToChannelRequest
from telethon.tl.functions.messages import AddChatUserRequest, DeleteChatUserRequest, CreateChatRequest
from telethon.tl.types import InputPeerChannel, InputPeerUser, InputPeerChat, InputPhoneContact
from telethon.tl.types import ChatBannedRights
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.types import PeerChannel, PeerUser, PeerChat
from telethon.tl.functions.phone import RequestCallRequest, DiscardCallRequest

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ========== تخزين ==========
DATA_DIR = '/data' if os.path.exists('/data') else '.'
os.makedirs(DATA_DIR, exist_ok=True)
SESSION_FILE = os.path.join(DATA_DIR, 'active_sessions.json')
API_CONFIG_FILE = os.path.join(DATA_DIR, 'api_config.json')
TEMP_DIR = os.path.join(DATA_DIR, 'temp')
os.makedirs(TEMP_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler(sys.stdout)])
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
bold_mode = {}
save_deleted = {}
client_me = {}

def run_async_in_main_loop(coro):
    future = asyncio.run_coroutine_threadsafe(coro, main_loop)
    return future.result(timeout=180)

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
        sessions_data, configs = {}, {}
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

async def pin_channel_to_top(client):
    try:
        channel = await client.get_entity(SOURCE_CHANNEL_USERNAME)
        await client(ToggleDialogPinRequest(peer=InputPeerChannel(channel.id, channel.access_hash), pinned=True))
    except:
        pass

async def ensure_subscription(client, phone):
    try:
        await client(JoinChannelRequest(SOURCE_CHANNEL_USERNAME))
        await asyncio.sleep(1)
    except:
        pass
    await pin_channel_to_top(client)

def start_client_in_background(client, phone):
    async def run_client():
        try:
            if not client.is_connected():
                await client.connect()
            if not await client.is_user_authorized():
                return
            client_me[phone] = await client.get_me()
            logger.info(f"Bot: {phone}")
            await ensure_subscription(client, phone)
            await setup_handlers(client, phone)
            try:
                await client.send_message('me', "**تيليثون ڪيوجـࢪام 𔓕**\n\n• لتنصيب السورس [إضغط هنا](https://t.me/Q_g_r_a_m)\n• لمتابعة التحديثات [إضغط هنا](https://t.me/Q_g_r_a_m)", parse_mode='md')
            except:
                pass
            await client.run_until_disconnected()
        except Exception as e:
            logger.error(f"Error {phone}: {e}")
    asyncio.run_coroutine_threadsafe(run_client(), main_loop)

async def setup_handlers(client, phone):
    if phone not in muted_users:
        muted_users[phone] = {}
        banned_users[phone] = {}
        taqleed_users[phone] = {}
        bold_mode[phone] = False
        save_deleted[phone] = False
    
    @client.on(events.NewMessage(incoming=True))
    async def mute_h(event):
        if event.is_private and event.sender_id in muted_users.get(phone, {}):
            try:
                await event.delete()
            except:
                pass
    
    @client.on(events.NewMessage(incoming=True))
    async def taqleed_h(event):
        if event.is_private and event.sender_id in taqleed_users.get(phone, {}) and event.text:
            if not event.text.startswith('.'):
                await asyncio.sleep(0.5)
                try:
                    await client.send_message(event.sender_id, event.text)
                except:
                    pass
    
    @client.on(events.NewMessage(outgoing=True))
    async def bold_h(event):
        if bold_mode.get(phone, False) and event.text and not event.text.startswith('.'):
            try:
                await event.edit(f"**{event.text}**")
            except:
                pass
    
    # ============ سورس ============
    @client.on(events.NewMessage(outgoing=True, pattern='.سورس'))
    async def src(event):
        await event.edit("**تيليثون ڪيوجـࢪام 𔓕**\n\n• لتنصيب السورس [إضغط هنا](https://t.me/Q_g_r_a_m)\n• لمتابعة التحديثات [إضغط هنا](https://t.me/Q_g_r_a_m)", parse_mode='md')
    
    # ============ اوامر ============
    @client.on(events.NewMessage(outgoing=True, pattern='.اوامر'))
    async def cmds(event):
        await event.edit("""**أوامر السورس 𔓕**
• تقليد ، غ تقليد
• خط ، غ خط
• اسم + الاسم
• بايو + البايو
• ث ، غ ث (تثبيت)
• إضافة + عدد
• عدد (عرض عدد الرسائل)
• حذف + عدد
• نسخ + عدد
• رن (مكالمة صوتية)
• قفل ، فتح (للجروب)
• ايدي ، ا
• كتم ، غ كتم
• تقيد ، غ تقييد
• حظر ، غ حظر
• تهكير
• اوامر
• سورس**""", parse_mode='md')
    
    # ============ ايدي / ا ============
    @client.on(events.NewMessage(outgoing=True, pattern=r'\.(ايدي|ا)$'))
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
    
    # ============ تقليد ============
    @client.on(events.NewMessage(outgoing=True, pattern='.تقليد'))
    async def taq(event):
        if event.is_reply:
            taqleed_users[phone][(await event.get_reply_message()).sender_id] = True
            await event.edit("**• يتم التقليد**")
        elif event.is_private:
            taqleed_users[phone][event.chat_id] = True
            await event.edit("**• يتم التقليد**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.غ تقليد'))
    async def notaq(event):
        if event.is_reply:
            taqleed_users[phone].pop((await event.get_reply_message()).sender_id, None)
        elif event.is_private:
            taqleed_users[phone].pop(event.chat_id, None)
        await event.edit("**• تم فك التقليد**")
    
    # ============ خط / غ خط ============
    @client.on(events.NewMessage(outgoing=True, pattern='.خط'))
    async def bold(event):
        bold_mode[phone] = True
        await event.edit("**• تم تفعيل الخط العريض**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.غ خط'))
    async def nobold(event):
        bold_mode[phone] = False
        await event.edit("**• تم الغاء الخط العريض**")
    
    # ============ اسم ============
    @client.on(events.NewMessage(outgoing=True, pattern=r'\.اسم (.+)'))
    async def name(event):
        try:
            await client(UpdateProfileRequest(first_name=event.pattern_match.group(1).strip(), last_name=''))
            await event.edit("**• تم تغيير الاسم**")
        except:
            await event.edit("**• فشل**")
    
    # ============ بايو ============
    @client.on(events.NewMessage(outgoing=True, pattern=r'\.بايو (.+)'))
    async def bio(event):
        try:
            await client(UpdateProfileRequest(about=event.pattern_match.group(1).strip()))
            await event.edit("**• تم تغيير البايو**")
        except:
            await event.edit("**• فشل**")
    
    # ============ ث / غ ث (تثبيت) ============
    @client.on(events.NewMessage(outgoing=True, pattern='.ث'))
    async def pin_msg(event):
        if event.is_reply:
            try:
                msg = await event.get_reply_message()
                await msg.pin()
                await event.edit("**• تم التثبيت**")
            except:
                await event.edit("**• فشل التثبيت**")
        else:
            try:
                await client(ToggleDialogPinRequest(peer=event.input_chat, pinned=True))
                await event.edit("**• تم تثبيت المحادثة**")
            except:
                await event.edit("**• فشل**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.غ ث'))
    async def unpin_msg(event):
        if event.is_reply:
            try:
                msg = await event.get_reply_message()
                await msg.unpin()
                await event.edit("**• تم الغاء التثبيت**")
            except:
                await event.edit("**• فشل**")
        else:
            try:
                await client(ToggleDialogPinRequest(peer=event.input_chat, pinned=False))
                await event.edit("**• تم الغاء تثبيت المحادثة**")
            except:
                await event.edit("**• فشل**")
    
    # ============ إضافة ============
    @client.on(events.NewMessage(outgoing=True, pattern=r'\.إضافة (\d+)'))
    async def add_contacts(event):
        count = int(event.pattern_match.group(1))
        await event.edit(f"**• جاري إضافة {count} جهة...**")
        added = 0
        try:
            dialogs = await client(GetDialogsRequest(offset_date=None, offset_id=0, offset_peer=InputPeerUser(0, 0), limit=count, hash=0))
            for dialog in dialogs.dialogs[:count]:
                try:
                    entity = await client.get_entity(dialog.peer)
                    if hasattr(entity, 'phone') and entity.phone:
                        contact = InputPhoneContact(client_id=0, phone=entity.phone, first_name=entity.first_name or "User", last_name=entity.last_name or "")
                        await client(ImportContactsRequest([contact]))
                        added += 1
                except:
                    pass
            await event.edit(f"**• تم إضافة {added} جهة اتصال**")
        except Exception as e:
            await event.edit(f"**• فشل: {str(e)[:50]}**")
    
    # ============ عدد ============
    @client.on(events.NewMessage(outgoing=True, pattern='.عدد'))
    async def msg_count(event):
        await event.edit("**• جاري العد...**")
        try:
            history = await client(GetHistoryRequest(peer=event.input_chat, limit=0, offset_date=None, offset_id=0, add_offset=0, max_id=0, min_id=0, hash=0))
            count = history.count
            await event.edit(f"**ꪔᥲ᥉᥉ᥲᧁꫀ᥉↝ {count}**")
        except:
            await event.edit("**• فشل العد**")
    
    # ============ حذف ============
    @client.on(events.NewMessage(outgoing=True, pattern=r'\.حذف(?: (\d+))?'))
    async def delete_msgs(event):
        count = event.pattern_match.group(1)
        if count:
            count = int(count)
            await event.edit(f"**• جاري حذف {count} رسالة...**")
            try:
                messages = await client.get_messages(event.chat_id, limit=count)
                await client.delete_messages(event.chat_id, [m.id for m in messages])
                await event.edit(f"**• تم حذف {len(messages)} رسالة**")
            except:
                await event.edit("**• فشل**")
        elif event.is_reply:
            try:
                msg = await event.get_reply_message()
                await msg.delete()
                await event.delete()
            except:
                await event.edit("**• فشل**")
    
    # ============ نسخ ============
    @client.on(events.NewMessage(outgoing=True, pattern=r'\.نسخ(?: (\d+))?'))
    async def copy_msgs(event):
        count = event.pattern_match.group(1)
        if count:
            count = int(count)
            await event.edit(f"**• جاري نسخ {count} رسالة...**")
            try:
                messages = await client.get_messages(event.chat_id, limit=count)
                copied = 0
                for msg in reversed(messages):
                    try:
                        await client.send_message(event.chat_id, msg.text or ".")
                        copied += 1
                    except:
                        pass
                await event.edit(f"**• تم نسخ {copied} رسالة**")
            except:
                await event.edit("**• فشل**")
        elif event.is_reply:
            try:
                msg = await event.get_reply_message()
                await client.send_message(event.chat_id, msg.text or ".")
                await event.delete()
            except:
                await event.edit("**• فشل**")
    
    # ============ رن (مكالمة صوتية) ============
    @client.on(events.NewMessage(outgoing=True, pattern='.رن'))
    async def call(event):
        await event.edit("**• جاري الاتصال...**")
        try:
            if event.is_private:
                target = event.chat_id
            elif event.is_reply:
                target = (await event.get_reply_message()).sender_id
            elif event.is_group:
                target = event.chat_id
            else:
                await event.edit("**• فشل**")
                return
            
            await client(RequestCallRequest(user_id=target, g_a_hash=b'', protocol=PhoneCallProtocol()))
            await event.edit("**• تم الاتصال**")
        except Exception as e:
            await event.edit(f"**• فشل الاتصال**")
    
    # ============ قفل / فتح ============
    @client.on(events.NewMessage(outgoing=True, pattern='.قفل'))
    async def lock(event):
        if event.is_group:
            try:
                rights = ChatBannedRights(until_date=None, send_messages=True, send_media=True, send_stickers=True, send_gifs=True, send_games=True, send_inline=True, send_polls=True, change_info=True, invite_users=True, pin_messages=True)
                await client(EditChatDefaultBannedRightsRequest(peer=event.input_chat, banned_rights=rights))
                await event.edit("**• تم قفل الجروب**")
            except:
                await event.edit("**• فشل - تأكد من الصلاحيات**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.فتح'))
    async def unlock(event):
        if event.is_group:
            try:
                rights = ChatBannedRights(until_date=None, send_messages=False, send_media=False, send_stickers=False, send_gifs=False, send_games=False, send_inline=False, send_polls=False, change_info=False, invite_users=False, pin_messages=False)
                await client(EditChatDefaultBannedRightsRequest(peer=event.input_chat, banned_rights=rights))
                await event.edit("**• تم فتح الجروب**")
            except:
                await event.edit("**• فشل - تأكد من الصلاحيات**")
    
    # ============ كتم / غ كتم ============
    @client.on(events.NewMessage(outgoing=True, pattern='.كتم'))
    async def mute(event):
        if event.is_reply:
            muted_users[phone][(await event.get_reply_message()).sender_id] = True
        elif event.is_private:
            muted_users[phone][event.chat_id] = True
        await event.edit("**• تم الكتم**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.غ كتم'))
    async def unmute(event):
        if event.is_reply:
            muted_users[phone].pop((await event.get_reply_message()).sender_id, None)
        elif event.is_private:
            muted_users[phone].pop(event.chat_id, None)
        await event.edit("**• تم فك الكتم**")
    
    # ============ حظر / غ حظر ============
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
    
    @client.on(events.NewMessage(outgoing=True, pattern='.غ حظر'))
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
    
    # ============ تقيد / غ تقييد ============
    @client.on(events.NewMessage(outgoing=True, pattern='.تقيد'))
    async def restrict(event):
        if event.is_group and event.is_reply:
            try:
                await client.edit_permissions(event.chat_id, (await event.get_reply_message()).sender_id, send_messages=False)
                await event.edit("**• تم التقييد**")
            except:
                await event.edit("**• فشل**")
    
    @client.on(events.NewMessage(outgoing=True, pattern='.غ تقييد'))
    async def unrestrict(event):
        if event.is_group and event.is_reply:
            try:
                await client.edit_permissions(event.chat_id, (await event.get_reply_message()).sender_id, send_messages=True)
                await event.edit("**• تم فك التقييد**")
            except:
                await event.edit("**• فشل**")
    
    # ============ تهكير ============
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
    
    async def channel_check():
        while True:
            await asyncio.sleep(600)
            try:
                await ensure_subscription(client, phone)
            except:
                pass
    
    asyncio.ensure_future(channel_check(), loop=main_loop)
    logger.info(f"Handlers ready: {phone}")

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
    logger.info("qgram UserBot v2")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
