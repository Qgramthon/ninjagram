import os
from telethon import TelegramClient, events

# الإعدادات من Railway
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION = os.getenv("SESSION")

account = TelegramClient('my_account', API_ID, API_HASH)

# ====== الأوامر الأساسية ======

@account.on(events.NewMessage(outgoing=True, pattern='.بنغ'))
async def ping(event):
    await event.edit("**✶ البنغ:** `جاري الحساب...`")

@account.on(events.NewMessage(outgoing=True, pattern='.وقتي'))
async def time_now(event):
    from datetime import datetime
    now = datetime.now().strftime("%I:%M %p")
    await event.edit(f"⏰ {now}")

@account.on(events.NewMessage(outgoing=True, pattern='.عريض (.+)'))
async def bold(event):
    text = event.pattern_match.group(1)
    await event.edit(f"**{text}**")

@account.on(events.NewMessage(outgoing=True, pattern='.مائل (.+)'))
async def italic(event):
    text = event.pattern_match.group(1)
    await event.edit(f"__{text}__")

@account.on(events.NewMessage(outgoing=True, pattern='.مشطوب (.+)'))
async def strike(event):
    text = event.pattern_match.group(1)
    await event.edit(f"~~{text}~~")

@account.on(events.NewMessage(outgoing=True, pattern='.قلب (.+)'))
async def flip_text(event):
    text = event.pattern_match.group(1)
    flipped = text[::-1]
    await event.edit(flipped)

@account.on(events.NewMessage(outgoing=True, pattern='.نيم (.+)'))
async def set_name(event):
    name = event.pattern_match.group(1)
    await account(UpdateProfileRequest(first_name=name))
    await event.edit(f"✅ تم تغيير الاسم إلى: {name}")

@account.on(events.NewMessage(outgoing=True, pattern='.بايو (.+)'))
async def set_bio(event):
    bio = event.pattern_match.group(1)
    await account(UpdateProfileRequest(about=bio))
    await event.edit(f"✅ تم تغيير البايو إلى: {bio}")

@account.on(events.NewMessage(outgoing=True, pattern='.مسح (.+)'))
async def delete_msgs(event):
    count = int(event.pattern_match.group(1))
    chat = await event.get_input_chat()
    messages = []
    async for msg in account.iter_messages(chat, limit=count + 1):
        messages.append(msg.id)
    await account.delete_messages(chat, messages)
    await event.respond(f"🗑️ تم مسح {count} رسالة")

@account.on(events.NewMessage(outgoing=True, pattern='.حذف'))
async def delete_chat(event):
    await event.delete()
    await event.respond("🗑️ تم حذف المحادثة")

@account.on(events.NewMessage(outgoing=True, pattern='.اوامر'))
async def show_commands(event):
    await event.edit("""
**✶ قائمة الأوامر ✶**
⚡ `.بنغ` - سرعة الاستجابة
⏰ `.وقتي` - عرض الوقت الحالي
✏️ `.عريض` + نص - كتابة عريضة
✏️ `.مائل` + نص - كتابة مائلة
✏️ `.مشطوب` + نص - كتابة مشطوبة
🔄 `.قلب` + نص - قلب النص
📝 `.نيم` + اسم - تغيير الاسم
📄 `.بايو` + نص - تغيير البايو
🗑️ `.مسح` + عدد - مسح رسائل
🚫 `.حذف` - حذف المحادثة
""")

# ====== تشغيل الحساب ======
print("⚡ تم تشغيل السورس بنجاح!")
account.start()
account.run_until_disconnected()
