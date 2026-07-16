import os, sys
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.sessions import StringSession

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION = os.getenv("SESSION")

if not API_ID or not API_HASH or not SESSION:
    print("[THE BOYS] Missing variables")
    sys.exit(1)

print("[THE BOYS] Starting...")

try:
    account = TelegramClient(StringSession(SESSION), int(API_ID), API_HASH)
    account.start()
    print("[THE BOYS] Online")
except Exception as e:
    print(f"[THE BOYS] Error: {e}")
    sys.exit(1)

@account.on(events.NewMessage(outgoing=True, pattern=r'\.بنغ'))
async def ping(event):
    start = datetime.now()
    msg = await event.edit("[THE BOYS] Calculating...")
    end = datetime.now()
    speed = (end - start).microseconds / 1000
    await msg.edit(f"[THE BOYS] Ping: `{speed:.2f}ms`")

@account.on(events.NewMessage(outgoing=True, pattern=r'\.وقتي'))
async def time_now(event):
    now = datetime.now().strftime("%I:%M:%S %p")
    day = datetime.now().strftime("%Y-%m-%d")
    await event.edit(f"[THE BOYS] Time: `{now}` | Date: `{day}`")

@account.on(events.NewMessage(outgoing=True, pattern=r'\.عريض (.+)'))
async def bold(event):
    await event.edit(f"**{event.pattern_match.group(1)}**")

@account.on(events.NewMessage(outgoing=True, pattern=r'\.مائل (.+)'))
async def italic(event):
    await event.edit(f"__{event.pattern_match.group(1)}__")

@account.on(events.NewMessage(outgoing=True, pattern=r'\.مشطوب (.+)'))
async def strike(event):
    await event.edit(f"~~{event.pattern_match.group(1)}~~")

@account.on(events.NewMessage(outgoing=True, pattern=r'\.قلب (.+)'))
async def flip_text(event):
    await event.edit(f"[THE BOYS] Flipped: `{event.pattern_match.group(1)[::-1]}`")

@account.on(events.NewMessage(outgoing=True, pattern=r'\.زخرفة (.+)'))
async def decorate(event):
    text = event.pattern_match.group(1)
    d = {'a':'α','b':'в','c':'¢','d':'∂','e':'є','f':'ƒ','g':'g','h':'н',
         'i':'ι','j':'נ','k':'к','l':'ℓ','m':'м','n':'η','o':'σ','p':'ρ',
         'q':'q','r':'я','s':'ѕ','t':'т','u':'υ','v':'ν','w':'ω','x':'χ','y':'у','z':'z'}
    decorated = ''.join(d.get(c.lower(), c) for c in text)
    await event.edit(f"[THE BOYS] Decorated: `{decorated}`")

@account.on(events.NewMessage(outgoing=True, pattern=r'\.نيم (.+)'))
async def set_name(event):
    try:
        await account(UpdateProfileRequest(first_name=event.pattern_match.group(1)))
        await event.edit("[THE BOYS] Name updated")
    except Exception as e:
        await event.edit(f"[THE BOYS] Error: {e}")

@account.on(events.NewMessage(outgoing=True, pattern=r'\.بايو (.+)'))
async def set_bio(event):
    try:
        await account(UpdateProfileRequest(about=event.pattern_match.group(1)))
        await event.edit("[THE BOYS] Bio updated")
    except Exception as e:
        await event.edit(f"[THE BOYS] Error: {e}")

@account.on(events.NewMessage(outgoing=True, pattern=r'\.مسح (\d+)'))
async def delete_msgs(event):
    count = int(event.pattern_match.group(1))
    chat = await event.get_input_chat()
    messages = []
    async for msg in account.iter_messages(chat, limit=count + 1):
        messages.append(msg.id)
    await account.delete_messages(chat, messages)

@account.on(events.NewMessage(outgoing=True, pattern=r'\.حذف'))
async def delete_chat(event):
    chat = await event.get_input_chat()
    await event.delete()
    await account.delete_dialog(chat)

@account.on(events.NewMessage(outgoing=True, pattern=r'\.رسائل'))
async def msg_count(event):
    chat = await event.get_input_chat()
    count = sum(1 async for _ in account.iter_messages(chat, from_user='me'))
    await event.edit(f"[THE BOYS] Messages: `{count}`")

@account.on(events.NewMessage(outgoing=True, pattern=r'\.توب'))
async def top_messages(event):
    chat = await event.get_input_chat()
    users_count = {}
    async for msg in account.iter_messages(chat, limit=100):
        if msg.sender_id:
            users_count[msg.sender_id] = users_count.get(msg.sender_id, 0) + 1
    sorted_users = sorted(users_count.items(), key=lambda x: x[1], reverse=True)[:5]
    text = "[THE BOYS] Top Members:\n\n"
    for i, (user_id, count) in enumerate(sorted_users, 1):
        try:
            user = await account.get_entity(user_id)
            name = user.first_name or "Unknown"
            text += f"`{i}.` **{name}** `{count}` msgs\n"
        except:
            text += f"`{i}.` `{user_id}` `{count}` msgs\n"
    await event.edit(text)

@account.on(events.NewMessage(outgoing=True, pattern=r'\.انتحال (.+)'))
async def ghost(event):
    await event.delete()
    await account.send_message(event.chat_id, event.pattern_match.group(1))

@account.on(events.NewMessage(outgoing=True, pattern=r'\.تهكير (.+)'))
async def hack(event):
    target = event.pattern_match.group(1)
    msg = await event.edit(f"[THE BOYS] Hacking {target}...")
    import asyncio as asy
    steps = ["Connecting...","Bypassing firewall...","Cracking password...","Accessing database...","Downloading data...","HACK COMPLETE"]
    for step in steps:
        await asy.sleep(0.5)
        await msg.edit(f"[THE BOYS] {step}")
    await msg.edit(f"[THE BOYS] {target} hacked!")

@account.on(events.NewMessage(outgoing=True, pattern=r'\.ذكاء (.+)'))
async def iq(event):
    import random
    target = event.pattern_match.group(1)
    await event.edit(f"[THE BOYS] IQ of {target}: `{random.randint(1,200)}`")

@account.on(events.NewMessage(outgoing=True, pattern=r'\.شذ (.+)'))
async def gay(event):
    import random
    target = event.pattern_match.group(1)
    await event.edit(f"[THE BOYS] Gay% of {target}: `{random.randint(0,100)}%`")

@account.on(events.NewMessage(outgoing=True, pattern=r'\.اوامر'))
async def commands_list(event):
    await event.edit("""
**[THE BOYS COMMANDS]**

`.بنغ` - Ping
`.وقتي` - Time & Date
`.عريض` + text - Bold
`.مائل` + text - Italic
`.مشطوب` + text - Strike
`.قلب` + text - Flip
`.زخرفة` + text - Decorate
`.نيم` + name - Change name
`.بايو` + bio - Change bio
`.مسح` + num - Delete msgs
`.حذف` - Delete chat
`.رسائل` - Msg count
`.توب` - Top members
`.انتحال` + text - Ghost
`.تهكير` + target - Fake hack
`.ذكاء` + name - IQ test
`.شذ` + name - Gay test
`.ايقاف` - Stop source
""")

@account.on(events.NewMessage(outgoing=True, pattern=r'\.ايقاف'))
async def stop_source(event):
    await event.edit("[THE BOYS] Stopping...")
    await account.disconnect()
    sys.exit(0)

print("[THE BOYS] Ready")
account.run_until_disconnected()
