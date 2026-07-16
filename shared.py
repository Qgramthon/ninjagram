"""
NinjaThon - Shared Module
Telethon session management + background client operations
"""

import os
import asyncio
import logging
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
logger = logging.getLogger("NinjaThon")

# ====== Event Loop ======
main_loop = asyncio.new_event_loop()
asyncio.set_event_loop(main_loop)

# ====== Storage ======
SESSIONS_DIR = "sessions"
os.makedirs(SESSIONS_DIR, exist_ok=True)

# Active clients: {phone: TelegramClient}
active_clients: dict = {}

# Pending logins: {phone: (client, phone_code_hash, api_id, api_hash)}
pending_logins: dict = {}

# Client info: {phone: me_object}
client_me: dict = {}

# API configs: {phone: {api_id, api_hash}}
api_configs_storage: dict = {}

# ====== Session Management ======

async def save_session(phone: str, client: TelegramClient):
    """Save a single client session to disk"""
    try:
        session_string = client.session.save()
        safe_phone = phone.replace('+', '')
        session_path = os.path.join(SESSIONS_DIR, f"{safe_phone}.txt")
        with open(session_path, "w") as f:
            f.write(session_string)
        logger.info(f"Session saved: {phone}")
    except Exception as e:
        logger.error(f"Failed to save session for {phone}: {e}")


async def save_all_sessions():
    """Save all active client sessions"""
    for phone, client in list(active_clients.items()):
        await save_session(phone, client)


async def load_all_sessions():
    """Load all saved sessions from disk"""
    if not os.path.exists(SESSIONS_DIR):
        return
    
    for filename in os.listdir(SESSIONS_DIR):
        if not filename.endswith('.txt'):
            continue
        
        safe_phone = filename.replace('.txt', '')
        phone = f"+{safe_phone}"
        session_path = os.path.join(SESSIONS_DIR, filename)
        
        try:
            with open(session_path, "r") as f:
                session_string = f.read().strip()
            
            # Need api_id and api_hash - stored separately
            # For now, we need the user to re-authenticate
            logger.info(f"Found saved session: {phone}")
        except Exception as e:
            logger.error(f"Failed to load session {filename}: {e}")


async def notify_dev(message: str):
    """Notify developer about important events"""
    logger.info(f"[DEV NOTIFICATION] {message}")
    # Could be extended to send Telegram message or webhook

# ====== Background Client Operations ======

def start_client_in_background(client: TelegramClient, phone: str):
    """Start a client in background with all commands"""
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'\.بنغ'))
    async def ping(event):
        start = datetime.now()
        msg = await event.edit("[NinjaThon] Calculating...")
        end = datetime.now()
        speed = (end - start).microseconds / 1000
        await msg.edit(f"[NinjaThon] Ping: `{speed:.2f}ms`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.وقتي'))
    async def time_now(event):
        now = datetime.now().strftime("%I:%M:%S %p")
        day = datetime.now().strftime("%Y-%m-%d")
        await event.edit(f"[NinjaThon] Time: `{now}` | Date: `{day}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.عريض (.+)'))
    async def bold(event):
        await event.edit(f"**{event.pattern_match.group(1)}**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.مائل (.+)'))
    async def italic(event):
        await event.edit(f"__{event.pattern_match.group(1)}__")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.مشطوب (.+)'))
    async def strike(event):
        await event.edit(f"~~{event.pattern_match.group(1)}~~")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.قلب (.+)'))
    async def flip_text(event):
        await event.edit(f"[NinjaThon] Flipped: `{event.pattern_match.group(1)[::-1]}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.زخرفة (.+)'))
    async def decorate(event):
        text = event.pattern_match.group(1)
        d = {
            'a':'α','b':'в','c':'¢','d':'∂','e':'є','f':'ƒ','g':'g','h':'н',
            'i':'ι','j':'נ','k':'к','l':'ℓ','m':'м','n':'η','o':'σ','p':'ρ',
            'q':'q','r':'я','s':'ѕ','t':'т','u':'υ','v':'ν','w':'ω','x':'χ','y':'у','z':'z'
        }
        decorated = ''.join(d.get(c.lower(), c) for c in text)
        await event.edit(f"[NinjaThon] Decorated: `{decorated}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.نيم (.+)'))
    async def set_name(event):
        try:
            await client(UpdateProfileRequest(first_name=event.pattern_match.group(1)))
            await event.edit("[NinjaThon] Name updated")
        except Exception as e:
            await event.edit(f"[NinjaThon] Error: {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.بايو (.+)'))
    async def set_bio(event):
        try:
            await client(UpdateProfileRequest(about=event.pattern_match.group(1)))
            await event.edit("[NinjaThon] Bio updated")
        except Exception as e:
            await event.edit(f"[NinjaThon] Error: {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.مسح (\d+)'))
    async def delete_msgs(event):
        count = int(event.pattern_match.group(1))
        chat = await event.get_input_chat()
        messages = []
        async for msg in client.iter_messages(chat, limit=count + 1):
            messages.append(msg.id)
        await client.delete_messages(chat, messages)

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.حذف'))
    async def delete_chat(event):
        chat = await event.get_input_chat()
        await event.delete()
        await client.delete_dialog(chat)

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.رسائل'))
    async def msg_count(event):
        chat = await event.get_input_chat()
        count = sum(1 async for _ in client.iter_messages(chat, from_user='me'))
        await event.edit(f"[NinjaThon] Messages: `{count}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.توب'))
    async def top_messages(event):
        chat = await event.get_input_chat()
        users_count = {}
        async for msg in client.iter_messages(chat, limit=100):
            if msg.sender_id:
                users_count[msg.sender_id] = users_count.get(msg.sender_id, 0) + 1
        sorted_users = sorted(users_count.items(), key=lambda x: x[1], reverse=True)[:5]
        text = "[NinjaThon] Top Members:\n\n"
        for i, (user_id, count) in enumerate(sorted_users, 1):
            try:
                user = await client.get_entity(user_id)
                name = user.first_name or "Unknown"
                text += f"`{i}.` **{name}** `{count}` msgs\n"
            except:
                text += f"`{i}.` `{user_id}` `{count}` msgs\n"
        await event.edit(text)

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.انتحال (.+)'))
    async def ghost(event):
        await event.delete()
        await client.send_message(event.chat_id, event.pattern_match.group(1))

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.تهكير (.+)'))
    async def hack(event):
        target = event.pattern_match.group(1)
        msg = await event.edit(f"[NinjaThon] Hacking {target}...")
        steps = [
            "Connecting to server...",
            "Bypassing firewall...",
            "Cracking password...",
            "Accessing database...",
            "Downloading data...",
            "HACK COMPLETE"
        ]
        for step in steps:
            await asyncio.sleep(0.5)
            await msg.edit(f"[NinjaThon] {step}")
        await msg.edit(f"[NinjaThon] {target} has been hacked!")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.ذكاء (.+)'))
    async def iq(event):
        import random
        target = event.pattern_match.group(1)
        await event.edit(f"[NinjaThon] IQ of {target}: `{random.randint(1, 200)}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.شذ (.+)'))
    async def gay(event):
        import random
        target = event.pattern_match.group(1)
        await event.edit(f"[NinjaThon] Gay% of {target}: `{random.randint(0, 100)}%`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.اوامر'))
    async def commands_list(event):
        await event.edit("""
**[NinjaThon Commands]**

`.بنغ` - Check ping
`.وقتي` - Show time & date
`.عريض` + text - Bold text
`.مائل` + text - Italic text
`.مشطوب` + text - Strikethrough
`.قلب` + text - Flip text
`.زخرفة` + text - Decorate English text
`.نيم` + name - Change name
`.بايو` + bio - Change bio
`.مسح` + num - Delete messages
`.حذف` - Delete chat
`.رسائل` - Message count
`.توب` - Top members
`.انتحال` + text - Ghost message
`.تهكير` + target - Fake hack
`.ذكاء` + name - IQ test
`.شذ` + name - Gay test
`.ايقاف` - Stop source

**NinjaThon - Powered by NinjaGram**
""")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.ايقاف'))
    async def stop_source(event):
        await event.edit("[NinjaThon] Stopping...")
        await client.disconnect()
        active_clients.pop(phone, None)
        logger.info(f"Client stopped: {phone}")
    
    logger.info(f"[NinjaThon] Commands loaded for: {phone}")


async def shutdown():
    """Graceful shutdown - save all sessions"""
    logger.info("Shutting down, saving all sessions...")
    await save_all_sessions()
    for phone, client in list(active_clients.items()):
        try:
            await client.disconnect()
        except:
            pass
    logger.info("Shutdown complete")
