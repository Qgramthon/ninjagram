import os
import re
import asyncio
from datetime import datetime
from telethon import TelegramClient, events, Button
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    FloodWaitError
)
from flask import Flask
from threading import Thread

# ====== إعدادات ======
BOT_TOKEN = "8963454170:AAGlM4mHDAjtXMcTYQd9_RRMy0I6JgnMBwg"
API_ID = 6
API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"
SESSIONS_FOLDER = "sessions"

os.makedirs(SESSIONS_FOLDER, exist_ok=True)

# ====== سيرفر وهمي ======
app = Flask(__name__)

@app.route('/')
def home():
    return "OK"

Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))).start()

# ====== البوت ======
print("⏳ جاري تشغيل البوت...")

try:
    bot = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
    print("✅ البوت شغال!")
except Exception as e:
    print(f"❌ خطأ في تشغيل البوت: {e}")
    exit(1)

users = {}
running_users = {}

# ====== تشغيل سورس المستخدم ======
def run_user_source(user_id):
    try:
        with open(f"{SESSIONS_FOLDER}/{user_id}.txt", "r") as f:
            session_string = f.read().strip()
        
        user_client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        user_client.start()
        running_users[user_id] = user_client
        
        @user_client.on(events.NewMessage(outgoing=True, pattern=r'\.بنغ'))
        async def ping(event):
            start = datetime.now()
            msg = await event.edit("**✶ جاري حساب البنغ...**")
            end = datetime.now()
            speed = (end - start).microseconds / 1000
            await msg.edit(f"**✶ البنغ:** `{speed:.2f}ms`")

        @user_client.on(events.NewMessage(outgoing=True, pattern=r'\.وقتي'))
        async def time_now(event):
            now = datetime.now().strftime("%I:%M:%S %p")
            await event.edit(f"**⏰ الوقت:** `{now}`")

        @user_client.on(events.NewMessage(outgoing=True, pattern=r'\.عريض (.+)'))
        async def bold(event):
            await event.edit(f"**{event.pattern_match.group(1)}**")

        @user_client.on(events.NewMessage(outgoing=True, pattern=r'\.مائل (.+)'))
        async def italic(event):
            await event.edit(f"__{event.pattern_match.group(1)}__")

        @user_client.on(events.NewMessage(outgoing=True, pattern=r'\.مشطوب (.+)'))
        async def strike(event):
            await event.edit(f"~~{event.pattern_match.group(1)}~~")

        @user_client.on(events.NewMessage(outgoing=True, pattern=r'\.قلب (.+)'))
        async def flip_text(event):
            await event.edit(f"**🔄:** `{event.pattern_match.group(1)[::-1]}`")

        @user_client.on(events.NewMessage(outgoing=True, pattern=r'\.زخرفة (.+)'))
        async def decorate(event):
            text = event.pattern_match.group(1)
            d = {'a':'α','b':'в','c':'¢','d':'∂','e':'є','f':'ƒ','g':'g','h':'н',
                 'i':'ι','j':'נ','k':'к','l':'ℓ','m':'м','n':'η','o':'σ','p':'ρ',
                 'q':'q','r':'я','s':'ѕ','t':'т','u':'υ','v':'ν','w':'ω','x':'χ','y':'у','z':'z'}
            await event.edit(f"**✨:** `{''.join(d.get(c.lower(),c) for c in text)}`")

        @user_client.on(events.NewMessage(outgoing=True, pattern=r'\.نيم (.+)'))
        async def set_name(event):
            try:
                await user_client(UpdateProfileRequest(first_name=event.pattern_match.group(1)))
                await event.edit("**✅ تم تغيير الاسم!**")
            except:
                await event.edit("**❌ خطأ**")

        @user_client.on(events.NewMessage(outgoing=True, pattern=r'\.بايو (.+)'))
        async def set_bio(event):
            try:
                await user_client(UpdateProfileRequest(about=event.pattern_match.group(1)))
                await event.edit("**✅ تم تغيير البايو!**")
            except:
                await event.edit("**❌ خطأ**")

        @user_client.on(events.NewMessage(outgoing=True, pattern=r'\.مسح (\d+)'))
        async def delete_msgs(event):
            count = int(event.pattern_match.group(1))
            chat = await event.get_input_chat()
            messages = []
            async for msg in user_client.iter_messages(chat, limit=count + 1):
                messages.append(msg.id)
            await user_client.delete_messages(chat, messages)

        @user_client.on(events.NewMessage(outgoing=True, pattern=r'\.حذف'))
        async def delete_chat(event):
            chat = await event.get_input_chat()
            await user_client.delete_dialog(chat)

        @user_client.on(events.NewMessage(outgoing=True, pattern=r'\.رسائل'))
        async def msg_count(event):
            chat = await event.get_input_chat()
            count = sum(1 async for _ in user_client.iter_messages(chat, from_user='me'))
            await event.edit(f"**📊 رسائلك:** `{count}`")

        @user_client.on(events.NewMessage(outgoing=True, pattern=r'\.انتحال (.+)'))
        async def ghost(event):
            await event.delete()
            await user_client.send_message(event.chat_id, event.pattern_match.group(1))

        @user_client.on(events.NewMessage(outgoing=True, pattern=r'\.اوامر'))
        async def commands(event):
            await event.edit("""
**╭━━━━━━[ قائمة الأوامر ]━━━━━━╮**

`.بنغ` - سرعة الاستجابة
`.وقتي` - الوقت والتاريخ
`.عريض` + نص - كتابة عريضة
`.مائل` + نص - كتابة مائلة
`.مشطوب` + نص - كتابة مشطوبة
`.قلب` + نص - قلب النص
`.زخرفة` + نص - زخرفة إنجليزية
`.نيم` + اسم - تغيير الاسم
`.بايو` + نص - تغيير البايو
`.مسح` + عدد - مسح رسائل
`.حذف` - حذف المحادثة
`.رسائل` - عدد رسائلك
`.انتحال` + نص - إرسال بدون اسمك
`.ايقاف` - إيقاف السورس

**╰━━━━━━━━━━━━━━━━━━━━━━━━━━╯**
""")

        @user_client.on(events.NewMessage(outgoing=True, pattern=r'\.ايقاف'))
        async def stop_user(event):
            await event.edit("**👋 جاري إيقاف السورس...**")
            await user_client.disconnect()
            if user_id in running_users:
                del running_users[user_id]

        print(f"✅ سورس {user_id} شغال")
        user_client.run_until_disconnected()
        
    except Exception as e:
        print(f"❌ خطأ {user_id}: {e}")

# ====== أمر البداية ======
@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    user_id = str(event.sender_id)
    
    if os.path.exists(f"{SESSIONS_FOLDER}/{user_id}.txt"):
        if user_id not in running_users:
            Thread(target=run_user_source, args=(user_id,)).start()
            await event.respond("**✅ تم تشغيل السورس!**\n**💡 استخدم `.اوامر` للقائمة**")
        else:
            await event.respond("**✅ السورس شغال!**\n**💡 استخدم `.اوامر` للقائمة**")
        return
    
    await event.respond("""
**╭━━━━━━━[ تـنـصـيـب تـيـلـيـثـون ]━━━━━━━╮**

**👋 أهلاً بك! اضغط على بدء التنصيب**

**📋 المطلوب:**
• API_ID من my.telegram.org
• API_HASH من my.telegram.org
• رقم هاتفك
• رمز التحقق

**╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯**
""", buttons=[
        [Button.inline("🚀 بدء التنصيب", b"deploy")],
        [Button.url("🔑 احصل على api", "https://my.telegram.org")]
    ])

# ====== بدء التنصيب ======
@bot.on(events.CallbackQuery(data=b"deploy"))
async def deploy(event):
    users[event.sender_id] = {
        "step": 1,
        "try_count": 0  # عدد محاولات إرسال الكود
    }
    await event.edit("**📝 الخطوة 1/4: أرسل API_ID (أرقام فقط):**")

# ====== استقبال البيانات ======
@bot.on(events.NewMessage(func=lambda e: e.sender_id in users))
async def handle_steps(event):
    user_id = event.sender_id
    user = users[user_id]
    step = user.get("step", 0)
    
    # ====== الخطوة 1: API_ID ======
    if step == 1:
        if not event.text.isdigit():
            return await event.respond("❌ أرقام فقط! حاول مرة أخرى:")
        user["api_id"] = int(event.text)
        user["step"] = 2
        await event.respond("✅ تم!\n**📝 الخطوة 2/4: أرسل API_HASH:**")
    
    # ====== الخطوة 2: API_HASH ======
    elif step == 2:
        user["api_hash"] = event.text.strip()
        user["step"] = 3
        await event.respond("✅ تم!\n**📱 الخطوة 3/4: أرسل رقم الهاتف\nمثال: +201234567890**")
    
    # ====== الخطوة 3: رقم الهاتف وإرسال الكود ======
    elif step == 3:
        phone = event.text.strip()
        user["phone"] = phone
        user["step"] = 4
        
        await send_code_to_user(event, user, user_id, is_retry=False)
    
    # ====== الخطوة 4: استقبال الكود ======
    elif step == 4:
        code = event.text.strip()
        
        # لو المستخدم كتب "تجديد" نعيد إرسال الكود
        if code.lower() in ["تجديد", "resend", "ارسال"]:
            await send_code_to_user(event, user, user_id, is_retry=True)
            return
        
        msg = await event.respond("⏳ جاري التحقق من الكود...")
        await verify_code(msg, user, user_id, code)

# ====== دالة إرسال الكود ======
async def send_code_to_user(event, user, user_id, is_retry=False):
    """إرسال رمز التحقق مع مهلة ومعالجة الأخطاء"""
    
    if is_retry:
        msg = await event.respond("🔄 جاري إعادة إرسال رمز التحقق...")
        user["try_count"] = user.get("try_count", 0) + 1
        await asyncio.sleep(2)  # مهلة قبل إعادة الإرسال
    else:
        msg = await event.respond("📲 جاري إرسال رمز التحقق...\n⏳ انتظر لحظة...")
        await asyncio.sleep(1)  # مهلة بسيطة
    
    try:
        # إنشاء عميل مؤقت
        client = TelegramClient(f'temp_{user_id}', user["api_id"], user["api_hash"])
        await client.connect()
        user["client"] = client
        
        # إرسال طلب الكود
        sent = await client.send_code_request(user["phone"])
        user["hash"] = sent.phone_code_hash
        
        # نجاح - نخبر المستخدم
        if is_retry:
            await msg.edit("✅ تم إعادة إرسال رمز التحقق!\n\n**📲 تفقد تيليجرام وأرسل الرمز الجديد:**\n\n⚠️ اكتب `تجديد` لإعادة الإرسال مرة أخرى")
        else:
            await msg.edit("✅ تم إرسال رمز التحقق!\n\n**📲 تفقد تيليجرام وأرسل الرمز (5 أرقام):**\n\n⚠️ اكتب `تجديد` لإعادة الإرسال\n⚠️ الرمز صالح لمدة 5 دقائق")
    
    except FloodWaitError as e:
        seconds = e.seconds
        minutes = seconds // 60
        await msg.edit(f"⏳ **انتظر {minutes} دقيقة قبل المحاولة مرة أخرى**\n\nتم تقييد الطلب مؤقتاً من تيليجرام")
        user["step"] = 3
    
    except Exception as e:
        await msg.edit(f"❌ **خطأ في إرسال الرمز:**\n`{str(e)}`\n\n⚠️ تأكد من:\n• صحة api_id و api_hash\n• صحة رقم الهاتف\n• عدم وجود حظر على الرقم")
        user["step"] = 3

# ====== دالة التحقق من الكود ======
async def verify_code(msg, user, user_id, code):
    """التحقق من رمز التحقق مع معالجة كل الحالات"""
    
    try:
        # محاولة تسجيل الدخول
        await user["client"].sign_in(
            user["phone"],
            code,
            phone_code_hash=user["hash"]
        )
        
        # نجاح - استخراج الجلسة
        session_string = await user["client"].export_session_string()
        
        # حفظ الجلسة
        with open(f"{SESSIONS_FOLDER}/{user_id}.txt", "w") as f:
            f.write(session_string)
        
        # تشغيل السورس
        Thread(target=run_user_source, args=(str(user_id),)).start()
        
        await msg.edit("""
**🎉 مبروك! تم التنصيب بنجاح!**

**✅ السورس شغال على حسابك حالاً**

**💡 الأوامر المتاحة:**
`.اوامر` - عرض كل الأوامر
`.بنغ` - سرعة الاستجابة
`.وقتي` - الوقت
`.نيم` + اسم - تغيير الاسم
`.بايو` + نص - تغيير البايو
`.مسح` + عدد - مسح رسائل
`.حذف` - حذف المحادثة
`.انتحال` + نص - إرسال بدون اسمك

**🛑 `.ايقاف` لإيقاف السورس**
**🔄 `/start` للتشغيل مجدداً**
""")
    
    except PhoneCodeExpiredError:
        # الكود منتهي الصلاحية
        await msg.edit("❌ **انتهت صلاحية رمز التحقق!**\n\n**📲 سيتم إرسال رمز جديد تلقائياً...**")
        await asyncio.sleep(2)
        # إعادة إرسال الكود تلقائياً
        fake_event = type('obj', (object,), {'sender_id': user_id, 'text': 'تجديد', 'respond': msg.respond})()
        await send_code_to_user(fake_event, user, user_id, is_retry=True)
    
    except PhoneCodeInvalidError:
        # كود خاطئ
        await msg.edit("❌ **رمز التحقق غير صحيح!**\n\n📲 أرسل الرمز الصحيح:\n⚠️ اكتب `تجديد` لاستلام رمز جديد")
    
    except SessionPasswordNeededError:
        # يحتاج تحقق بخطوتين
        user["step"] = 5
        user["awaiting_password"] = True
        await msg.edit("🔐 **حسابك مفعل عليه التحقق بخطوتين**\n\n📝 أرسل كلمة المرور (الرمز السري):")
    
    except FloodWaitError as e:
        seconds = e.seconds
        await msg.edit(f"⏳ **انتظر {seconds} ثانية** قبل المحاولة مرة أخرى\n\nتم تقييد الطلب مؤقتاً")
    
    except Exception as e:
        await msg.edit(f"❌ **خطأ غير متوقع:**\n`{str(e)}`\n\n🔄 اكتب `تجديد` للمحاولة مرة أخرى")

# ====== استقبال كلمة مرور التحقق بخطوتين ======
@bot.on(events.NewMessage(func=lambda e: e.sender_id in users and users[e.sender_id].get("step") == 5))
async def handle_password(event):
    user_id = event.sender_id
    user = users[user_id]
    password = event.text.strip()
    
    msg = await event.respond("⏳ جاري التحقق من كلمة المرور...")
    
    try:
        await user["client"].sign_in(password=password)
        session_string = await user["client"].export_session_string()
        
        with open(f"{SESSIONS_FOLDER}/{user_id}.txt", "w") as f:
            f.write(session_string)
        
        Thread(target=run_user_source, args=(str(user_id),)).start()
        
        await msg.edit("""
**🎉 مبروك! تم التنصيب بنجاح!**

**✅ السورس شغال على حسابك حالاً**
**💡 استخدم `.اوامر` لعرض القائمة**
""")
    
    except Exception as e:
        await msg.edit(f"❌ **كلمة المرور غير صحيحة:**\n`{str(e)}`\n\n🔐 أرسل كلمة المرور الصحيحة:")
    
    finally:
        if "awaiting_password" in user:
            del user["awaiting_password"]

# ====== تشغيل الجلسات القديمة ======
for f in os.listdir(SESSIONS_FOLDER):
    if f.endswith('.txt'):
        uid = f.replace('.txt', '')
        if uid not in running_users:
            Thread(target=run_user_source, args=(uid,)).start()
            print(f"🔄 تم تشغيل جلسة قديمة: {uid}")

print("""
╔══════════════════════════════════╗
║   ✅ البوت جاهز لاستقبال الرسائل  ║
║   🤖 أرسل /start للبدء          ║
╚══════════════════════════════════╝
""")

bot.run_until_disconnected()
