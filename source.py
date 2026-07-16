import os
import sys
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.functions.account import UpdateProfileRequest

# ====== التحقق من المتغيرات ======
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION = os.getenv("SESSION")

if not API_ID:
    print("❌ خطأ: API_ID غير موجود في المتغيرات")
    sys.exit(1)

if not API_HASH:
    print("❌ خطأ: API_HASH غير موجود في المتغيرات")
    sys.exit(1)

if not SESSION:
    print("❌ خطأ: SESSION غير موجود في المتغيرات")
    sys.exit(1)

try:
    API_ID = int(API_ID)
except ValueError:
    print("❌ خطأ: API_ID يجب أن يكون أرقام فقط")
    sys.exit(1)

print(f"✅ تم تحميل المتغيرات بنجاح")
print(f"⏳ جاري تشغيل السورس...")

# ====== تشغيل الحساب ======
account = TelegramClient('my_account', API_ID, API_HASH)

try:
    account.start()
    print("✅ تم تسجيل الدخول بنجاح!")
except Exception as e:
    print(f"❌ خطأ في تسجيل الدخول: {e}")
    sys.exit(1)

# ====== الأوامر الأساسية ======

@account.on(events.NewMessage(outgoing=True, pattern=r'\.بنغ'))
async def ping(event):
    start = datetime.now()
    msg = await event.edit("**✶ جاري حساب البنغ...**")
    end = datetime.now()
    speed = (end - start).microseconds / 1000
    await msg.edit(f"**✶ البنغ:** `{speed:.2f}ms`")

@account.on(events.NewMessage(outgoing=True, pattern=r'\.وقتي'))
async def time_now(event):
    now = datetime.now().strftime("%I:%M:%S %p")
    day = datetime.now().strftime("%Y-%m-%d")
    await event.edit(f"**⏰ الوقت:** `{now}`\n**📅 التاريخ:** `{day}`")

@account.on(events.NewMessage(outgoing=True, pattern=r'\.عريض (.+)'))
async def bold(event):
    text = event.pattern_match.group(1)
    await event.edit(f"**{text}**")

@account.on(events.NewMessage(outgoing=True, pattern=r'\.مائل (.+)'))
async def italic(event):
    text = event.pattern_match.group(1)
    await event.edit(f"__{text}__")

@account.on(events.NewMessage(outgoing=True, pattern=r'\.مشطوب (.+)'))
async def strike(event):
    text = event.pattern_match.group(1)
    await event.edit(f"~~{text}~~")

@account.on(events.NewMessage(outgoing=True, pattern=r'\.قلب (.+)'))
async def flip_text(event):
    text = event.pattern_match.group(1)
    flipped = text[::-1]
    await event.edit(f"**🔄 النص المقلوب:** `{flipped}`")

@account.on(events.NewMessage(outgoing=True, pattern=r'\.نيم (.+)'))
async def set_name(event):
    name = event.pattern_match.group(1)
    try:
        await account(UpdateProfileRequest(first_name=name))
        await event.edit(f"**✅ تم تغيير الاسم إلى:** `{name}`")
    except Exception as e:
        await event.edit(f"**❌ خطأ:** {e}")

@account.on(events.NewMessage(outgoing=True, pattern=r'\.بايو (.+)'))
async def set_bio(event):
    bio = event.pattern_match.group(1)
    try:
        await account(UpdateProfileRequest(about=bio))
        await event.edit(f"**✅ تم تغيير البايو إلى:** `{bio}`")
    except Exception as e:
        await event.edit(f"**❌ خطأ:** {e}")

@account.on(events.NewMessage(outgoing=True, pattern=r'\.مسح (\d+)'))
async def delete_msgs(event):
    count = int(event.pattern_match.group(1))
    chat = await event.get_input_chat()
    messages = []
    async for msg in account.iter_messages(chat, limit=count + 1):
        messages.append(msg.id)
    await account.delete_messages(chat, messages)
    await event.respond(f"**🗑️ تم مسح {count} رسالة**")

@account.on(events.NewMessage(outgoing=True, pattern=r'\.حذف'))
async def delete_chat(event):
    chat = await event.get_input_chat()
    await event.delete()
    await account.delete_dialog(chat)
    await event.respond("**🗑️ تم حذف المحادثة**")

@account.on(events.NewMessage(outgoing=True, pattern=r'\.رسائل'))
async def msg_count(event):
    chat = await event.get_input_chat()
    count = 0
    async for _ in account.iter_messages(chat, from_user='me'):
        count += 1
    await event.edit(f"**📊 عدد رسائلك هنا:** `{count}`")

@account.on(events.NewMessage(outgoing=True, pattern=r'\.توب'))
async def top_messages(event):
    chat = await event.get_input_chat()
    users_count = {}
    async for msg in account.iter_messages(chat, limit=100):
        if msg.sender_id:
            sender = msg.sender_id
            users_count[sender] = users_count.get(sender, 0) + 1
    
    sorted_users = sorted(users_count.items(), key=lambda x: x[1], reverse=True)[:5]
    text = "**🏆 توب المتفاعلين:**\n\n"
    for i, (user_id, count) in enumerate(sorted_users, 1):
        try:
            user = await account.get_entity(user_id)
            name = user.first_name or "بدون اسم"
            text += f"`{i}.` **{name}** → `{count}` رسالة\n"
        except:
            text += f"`{i}.` `{user_id}` → `{count}` رسالة\n"
    
    await event.edit(text)

@account.on(events.NewMessage(outgoing=True, pattern=r'\.انتحال (.+)'))
async def ghost(event):
    text = event.pattern_match.group(1)
    await event.delete()
    await account.send_message(event.chat_id, text)

@account.on(events.NewMessage(outgoing=True, pattern=r'\.زخرفة (.+)'))
async def decorate(event):
    text = event.pattern_match.group(1)
    decorations = {
        'a': 'α', 'b': 'в', 'c': '¢', 'd': '∂', 'e': 'є',
        'f': 'ƒ', 'g': 'g', 'h': 'н', 'i': 'ι', 'j': 'נ',
        'k': 'к', 'l': 'ℓ', 'm': 'м', 'n': 'η', 'o': 'σ',
        'p': 'ρ', 'q': 'q', 'r': 'я', 's': 'ѕ', 't': 'т',
        'u': 'υ', 'v': 'ν', 'w': 'ω', 'x': 'χ', 'y': 'у',
        'z': 'z'
    }
    decorated = ''.join(decorations.get(c.lower(), c) for c in text)
    await event.edit(f"**✨ الزخرفة:** `{decorated}`")

@account.on(events.NewMessage(outgoing=True, pattern=r'\.اوامر'))
async def show_commands(event):
    commands_text = """
**╭━━━━━━[ قائمة الأوامر ]━━━━━━╮**

**⚡ أوامر عامة:**
`.بنغ` - سرعة الاستجابة
`.وقتي` - الوقت والتاريخ
`.اوامر` - هذه القائمة

**✏️ أوامر تنسيق:**
`.عريض` + نص - كتابة عريضة
`.مائل` + نص - كتابة مائلة
`.مشطوب` + نص - كتابة مشطوبة
`.قلب` + نص - قلب النص
`.زخرفة` + نص - زخرفة إنجليزية

**👤 أوامر الحساب:**
`.نيم` + اسم - تغيير الاسم
`.بايو` + نص - تغيير البايو

**💬 أوامر المحادثة:**
`.مسح` + عدد - مسح رسائل
`.حذف` - حذف المحادثة
`.رسائل` - عدد رسائلك
`.توب` - الأكثر تفاعلاً
`.انتحال` + نص - إرسال نص بدون اسمك

**╰━━━━━━━━━━━━━━━━━━━━━━━━━━╯**
"""
    await event.edit(commands_text)

# ====== رسالة تأكيد التشغيل ======
print("""
╔══════════════════════════════════╗
║     ✅ السورس شغال بنجاح!        ║
║     💡 استخدم .اوامر للقائمة     ║
╚══════════════════════════════════╝
""")

# ====== تشغيل الحساب للأبد ======
account.run_until_disconnected()
