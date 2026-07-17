"""
Vought International - Shared Module
The Boys Edition - Telethon Setup
"""

import os
import asyncio
import logging
import json
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    FloodWaitError,
)

# ====== Logging ======
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Vought")

# ====== Event Loop ======
main_loop = asyncio.new_event_loop()

# ====== Storage ======
SESSIONS_DIR = "sessions"
CONFIG_DIR = "configs"
os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)

active_clients: dict = {}
pending_logins: dict = {}
client_me: dict = {}
api_configs_storage: dict = {}

# ====== Config Management ======

def save_config(phone: str, api_id: int, api_hash: str):
    safe_phone = phone.replace('+', '')
    config_path = os.path.join(CONFIG_DIR, f"{safe_phone}.json")
    with open(config_path, "w") as f:
        json.dump({"api_id": api_id, "api_hash": api_hash, "phone": phone}, f)

def load_config(phone: str) -> dict | None:
    safe_phone = phone.replace('+', '')
    config_path = os.path.join(CONFIG_DIR, f"{safe_phone}.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return json.load(f)
    return None

# ====== Session Management ======

async def save_session(phone: str, client: TelegramClient):
    try:
        session_string = client.session.save()
        safe_phone = phone.replace('+', '')
        session_file = os.path.join(SESSIONS_DIR, f"{safe_phone}.txt")
        lock_file = os.path.join(SESSIONS_DIR, f"{safe_phone}.lock")
        
        with open(lock_file, "w") as f:
            f.write(str(os.getpid()))
        
        temp_file = session_file + ".tmp"
        with open(temp_file, "w") as f:
            f.write(session_string)
        os.replace(temp_file, session_file)
    except Exception as e:
        logger.error(f"Failed to save session {phone}: {e}")

async def save_all_sessions():
    for phone, client in list(active_clients.items()):
        await save_session(phone, client)

async def load_and_start_all_sessions():
    if not os.path.exists(SESSIONS_DIR):
        return
    
    loaded = 0
    for filename in os.listdir(SESSIONS_DIR):
        if not filename.endswith('.txt'):
            continue
        
        safe_phone = filename.replace('.txt', '')
        phone = f"+{safe_phone}"
        
        if phone in active_clients:
            continue
        
        lock_file = os.path.join(SESSIONS_DIR, f"{safe_phone}.lock")
        if os.path.exists(lock_file):
            try:
                with open(lock_file, "r") as f:
                    pid = int(f.read().strip())
                try:
                    os.kill(pid, 0)
                    continue
                except OSError:
                    os.remove(lock_file)
            except:
                os.remove(lock_file)
        
        config = load_config(phone)
        if not config:
            continue
        
        try:
            session_file = os.path.join(SESSIONS_DIR, filename)
            with open(session_file, "r") as f:
                session_string = f.read().strip()
            
            if not session_string:
                continue
            
            client = TelegramClient(StringSession(session_string), config["api_id"], config["api_hash"])
            await client.connect()
            
            if await client.is_user_authorized():
                with open(lock_file, "w") as f:
                    f.write(str(os.getpid()))
                
                active_clients[phone] = client
                client_me[phone] = await client.get_me()
                api_configs_storage[phone] = {
                    "api_id": config["api_id"],
                    "api_hash": config["api_hash"]
                }
                start_client_in_background(client, phone)
                loaded += 1
            else:
                await client.disconnect()
                cleanup_session_files(phone)
                
        except Exception as e:
            logger.error(f"Failed to load {phone}: {e}")
            cleanup_session_files(phone)

def cleanup_session_files(phone: str):
    safe_phone = phone.replace('+', '')
    files_to_remove = [
        os.path.join(SESSIONS_DIR, f"{safe_phone}.txt"),
        os.path.join(SESSIONS_DIR, f"{safe_phone}.lock"),
        os.path.join(CONFIG_DIR, f"{safe_phone}.json")
    ]
    for file_path in files_to_remove:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass

async def notify_dev(message: str):
    logger.info(message)

async def periodic_save():
    while True:
        await asyncio.sleep(300)
        await save_all_sessions()

async def cleanup_expired():
    while True:
        await asyncio.sleep(600)
        for phone, client in list(active_clients.items()):
            try:
                if not await client.is_user_authorized():
                    await client.disconnect()
                    del active_clients[phone]
                    client_me.pop(phone, None)
                    api_configs_storage.pop(phone, None)
                    cleanup_session_files(phone)
            except:
                pass

# ====== Translation Function ======

async def translate_text(text: str) -> str:
    try:
        import urllib.parse
        import urllib.request
        
        has_arabic = any('\u0600' <= c <= '\u06ff' for c in text)
        
        if has_arabic:
            source, target = 'ar', 'en'
        else:
            source, target = 'en', 'ar'
        
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            'client': 'gtx',
            'sl': source,
            'tl': target,
            'dt': 't',
            'q': text
        }
        
        full_url = url + '?' + urllib.parse.urlencode(params)
        req = urllib.request.Request(full_url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            translated = ''.join([part[0] for part in data[0] if part[0] is not None])
            return translated
    except Exception as e:
        return f"Error: {e}"

# ====== Commands ======

def start_client_in_background(client: TelegramClient, phone: str):
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بنغ$'))
    async def ping(event):
        start = datetime.now()
        msg = await event.edit("...")
        end = datetime.now()
        speed = (end - start).microseconds / 1000
        await msg.edit(f"`{speed:.2f}ms`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.وقت$'))
    async def time_now(event):
        now = datetime.now().strftime("%I:%M %p")
        day = datetime.now().strftime("%Y-%m-%d")
        await event.edit(f"`{now}` - `{day}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.عريض (.+)$'))
    async def bold(event):
        await event.edit(f"**{event.pattern_match.group(1)}**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.مائل (.+)$'))
    async def italic(event):
        await event.edit(f"__{event.pattern_match.group(1)}__")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.مشطوب (.+)$'))
    async def strike(event):
        await event.edit(f"~~{event.pattern_match.group(1)}~~")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.قلب (.+)$'))
    async def flip_text(event):
        await event.edit(event.pattern_match.group(1)[::-1])

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.زخرفة (.+)$'))
    async def decorate(event):
        text = event.pattern_match.group(1)
        d = {'a':'α','b':'в','c':'¢','d':'∂','e':'є','f':'ƒ','g':'g','h':'н','i':'ι','j':'נ','k':'к','l':'ℓ','m':'м','n':'η','o':'σ','p':'ρ','q':'q','r':'я','s':'ѕ','t':'т','u':'υ','v':'ν','w':'ω','x':'χ','y':'у','z':'z'}
        await event.edit(''.join(d.get(c.lower(),c) for c in text))

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.اسم (.+)$'))
    async def set_name(event):
        try:
            await client(UpdateProfileRequest(first_name=event.pattern_match.group(1)))
            await event.edit("Done")
        except Exception as e:
            await event.edit(f"Error: {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بايو (.+)$'))
    async def set_bio(event):
        try:
            await client(UpdateProfileRequest(about=event.pattern_match.group(1)))
            await event.edit("Done")
        except Exception as e:
            await event.edit(f"Error: {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.مسح (\d+)$'))
    async def delete_msgs(event):
        count = int(event.pattern_match.group(1))
        chat = await event.get_input_chat()
        messages = []
        async for msg in client.iter_messages(chat, limit=count + 1):
            messages.append(msg.id)
        await client.delete_messages(chat, messages)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.حذف$'))
    async def delete_chat(event):
        chat = await event.get_input_chat()
        await event.delete()
        await client.delete_dialog(chat)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.رسائل$'))
    async def msg_count(event):
        chat = await event.get_input_chat()
        count = sum(1 async for _ in client.iter_messages(chat, from_user='me'))
        await event.edit(f"`{count}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.توب$'))
    async def top_messages(event):
        chat = await event.get_input_chat()
        users_count = {}
        async for msg in client.iter_messages(chat, limit=100):
            if msg.sender_id:
                users_count[msg.sender_id] = users_count.get(msg.sender_id, 0) + 1
        sorted_users = sorted(users_count.items(), key=lambda x: x[1], reverse=True)[:5]
        text = ""
        for i, (user_id, count) in enumerate(sorted_users, 1):
            try:
                user = await client.get_entity(user_id)
                name = user.first_name or "Unknown"
                text += f"`{i}.` **{name}** `{count}`\n"
            except:
                text += f"`{i}.` `{user_id}` `{count}`\n"
        await event.edit(text)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.انتحال (.+)$'))
    async def ghost(event):
        await event.delete()
        await client.send_message(event.chat_id, event.pattern_match.group(1))

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تهكير (.+)$'))
    async def hack(event):
        target = event.pattern_match.group(1)
        msg = await event.edit("...")
        steps = ["Connecting", "Bypassing", "Cracking", "Accessing", "Downloading", "Done"]
        for step in steps:
            await asyncio.sleep(0.4)
            await msg.edit(f"`{step}...`")
        await msg.edit(f"**{target}** hacked")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ذكاء (.+)$'))
    async def iq(event):
        import random
        await event.edit(f"**{event.pattern_match.group(1)}** IQ: `{random.randint(1,200)}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تحليل (.+)$'))
    async def analyze(event):
        import random
        await event.edit(f"**{event.pattern_match.group(1)}**: `{random.randint(0,100)}%`")

    # ====== Translation ======
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ترجم (.+)$'))
    async def translate_cmd(event):
        text = event.pattern_match.group(1)
        msg = await event.edit("...")
        result = await translate_text(text)
        await msg.edit(result)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ترجم$'))
    async def translate_reply(event):
        if not event.is_reply:
            await event.edit("Reply to a message")
            return
        
        reply = await event.get_reply_message()
        if not reply or not reply.text:
            await event.edit("No text found")
            return
        
        msg = await event.edit("...")
        result = await translate_text(reply.text)
        await msg.edit(result)

    # ====== Help ======
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.اوامر$'))
    async def commands_list(event):
        await event.edit("""
`.بنغ` `.وقت` `.عريض` `.مائل` `.مشطوب`
`.قلب` `.زخرفة` `.اسم` `.بايو` `.مسح`
`.حذف` `.رسائل` `.توب` `.انتحال`
`.تهكير` `.ذكاء` `.تحليل`
`.ترجم` text/reply `.ايقاف`
""")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ايقاف$'))
    async def stop_source(event):
        await event.edit("Done")
        await client.disconnect()
        active_clients.pop(phone, None)
        cleanup_session_files(phone)

async def shutdown():
    await save_all_sessions()
    
    for filename in os.listdir(SESSIONS_DIR):
        if filename.endswith('.lock'):
            try:
                os.remove(os.path.join(SESSIONS_DIR, filename))
            except:
                pass
    
    for phone, client in list(active_clients.items()):
        try:
            await client.disconnect()
        except:
            pass
    
    active_clients.clear()
    client_me.clear()
    api_configs_storage.clear()
