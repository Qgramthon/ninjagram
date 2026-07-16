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
    FloodWaitError,
)
from flask import Flask
from threading import Thread

# ========== الإعدادات الثابتة ==========
BOT_TOKEN = "8963454170:AAGlM4mHDAjtXMcTYQd9_RRMy0I6JgnMBwg"  # توكن البوت
API_ID = 6                   # api_id الرسمي لتطبيق تيليجرام
API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"  # api_hash الرسمي
SESSIONS_FOLDER = "sessions"  # مجلد حفظ الجلسات
os.makedirs(SESSIONS_FOLDER, exist_ok=True)

# ========== خادم وهمي لـ Railway ==========
app = Flask(__name__)
@app.route('/')
def home():
    return "البوت يعمل ✅"
Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))), daemon=True).start()

# ========== بدء البوت ==========
bot = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
print("✅ تم تشغيل بوت التنصيب")

# ========== قواعد البيانات المؤقتة ==========
users = {}           # المستخدمون في مرحلة التنصيب
running_users = {}   # العملاء النشطون (حسابات المستخدمين)

# ========== دالة تشغيل سورس المستخدم ==========
def run_user_source(user_id):
    """تشغيل أوامر التيليثون للمستخدم بعد نجاح التنصيب"""
    session_file = f"{SESSIONS_FOLDER}/{user_id}.txt"
    if not os.path.exists(session_file):
        return

    with open(session_file, "r") as f:
        session_str = f.read().strip()

    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
    try:
        client.start()
        running_users[user_id] = client
        print(f"✅ تم تشغيل سورس المستخدم {user_id}")
    except Exception as e:
        print(f"❌ فشل تشغيل سورس {user_id}: {e}")
        return

    # ---- تعريف الأوامر ----
    @client.on(events.NewMessage(outgoing=True, pattern=r'\.بنغ'))
    async def ping(event):
        start = datetime.now()
        msg = await event.edit("**✶ جاري حساب البنغ...**")
        end = datetime.now()
        speed = (end - start).microseconds / 1000
        await msg.edit(f"**✶ البنغ:** `{speed:.2f}ms`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.وقتي'))
    async def time_now(event):
        now = datetime.now().strftime("%I:%M:%S %p")
        await event.edit(f"**⏰ الوقت:** `{now}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.عريض (.+)'))
    async def bold(event):
        text = event.pattern_match.group(1)
        await event.edit(f"**{text}**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.مائل (.+)'))
    async def italic(event):
        text = event.pattern_match.group(1)
        await event.edit(f"__{text}__")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.مشطوب (.+)'))
    async def strike(event):
        text = event.pattern_match.group(1)
        await event.edit(f"~~{text}~~")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.قلب (.+)'))
    async def flip_text(event):
        text = event.pattern_match.group(1)
        await event.edit(f"**🔄:** `{text[::-1]}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.زخرفة (.+)'))
    async def decorate(event):
        text = event.pattern_match.group(1)
        d = {'a':'α','b':'в','c':'¢','d':'∂','e':'є','f':'ƒ','g':'g','h':'н',
             'i':'ι','j':'נ','k':'к','l':'ℓ','m':'м','n':'η','o':'σ','p':'ρ',
             'q':'q','r':'я','s':'ѕ','t':'т','u':'υ','v':'ν','w':'ω','x':'χ','y':'у','z':'z'}
        decorated = ''.join(d.get(c.lower(), c) for c in text)
        await event.edit(f"**✨:** `{decorated}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.نيم (.+)'))
    async def set_name(event):
        try:
            await client(UpdateProfileRequest(first_name=event.pattern_match.group(1)))
            await event.edit("**✅ تم تغيير الاسم!**")
        except Exception as e:
            await event.edit(f"**❌ خطأ:** {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.بايو (.+)'))
    async def set_bio(event):
        try:
            await client(UpdateProfileRequest(about=event.pattern_match.group(1)))
            await event.edit("**✅ تم تغيير البايو!**")
        except Exception as e:
            await event.edit(f"**❌ خطأ:** {e}")

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
        await event.edit(f"**📊 رسائلك:** `{count}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.انتحال (.+)'))
    async def ghost(event):
        await event.delete()
        await client.send_message(event.chat_id, event.pattern_match.group(1))

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.اوامر'))
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

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.ايقاف'))
    async def stop_user(event):
        await event.edit("**👋 جاري إيقاف السورس...**")
        await client.disconnect()
        running_users.pop(user_id, None)

    client.run_until_disconnected()

# ========== أمر /start ==========
@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    user_id = str(event.sender_id)

    # التحقق من وجود جلسة سابقة
    if os.path.exists(f"{SESSIONS_FOLDER}/{user_id}.txt"):
        if user_id not in running_users:
            Thread(target=run_user_source, args=(user_id,)).start()
            await event.respond("**✅ تم إعادة تشغيل السورس!**\n**💡 استخدم `.اوامر` للقائمة**")
        else:
            await event.respond("**✅ السورس شغال بالفعل!**\n**💡 استخدم `.اوامر` للقائمة**")
        return

    # بدء تنصيب جديد
    await event.respond(
        "**╭━━━━━━━[ تـنـصـيـب تـيـلـيـثـون ]━━━━━━━╮**\n\n"
        "**👋 أهلاً بك! اضغط على بدء التنصيب**\n\n"
        "**📋 ستحتاج:**\n"
        "• API_ID من my.telegram.org\n"
        "• API_HASH من my.telegram.org\n"
        "• رقم هاتفك\n"
        "• رمز التحقق\n\n"
        "**╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯**",
        buttons=[
            [Button.inline("🚀 بدء التنصيب", b"deploy")],
            [Button.url("🔑 احصل على api", "https://my.telegram.org")]
        ]
    )

# ========== بدء التنصيب ==========
@bot.on(events.CallbackQuery(data=b"deploy"))
async def deploy(event):
    user_id = event.sender_id
    users[user_id] = {"step": "api_id", "data": {}, "retries": 0, "max_retries": 3}
    await event.edit("**📝 الخطوة 1/4: أرسل API_ID (أرقام فقط):**")

# ========== استقبال البيانات خطوة بخطوة ==========
@bot.on(events.NewMessage(func=lambda e: e.sender_id in users))
async def handle_steps(event):
    user_id = event.sender_id
    user = users[user_id]
    step = user["step"]
    text = event.text.strip()

    # --- API_ID ---
    if step == "api_id":
        if not text.isdigit():
            return await event.respond("❌ أرقام فقط! حاول مرة أخرى:")
        user["data"]["api_id"] = int(text)
        user["step"] = "api_hash"
        await event.respond("✅ تم!\n**📝 الخطوة 2/4: أرسل API_HASH:**")

    # --- API_HASH ---
    elif step == "api_hash":
        user["data"]["api_hash"] = text
        user["step"] = "phone"
        await event.respond("✅ تم!\n**📱 الخطوة 3/4: أرسل رقم الهاتف\nمثال: +201234567890**")

    # --- رقم الهاتف وإرسال الكود ---
    elif step == "phone":
        phone = text
        user["data"]["phone"] = phone
        user["step"] = "code"
        await send_code(event, user_id, user, is_retry=False)

    # --- استقبال رمز التحقق ---
    elif step == "code":
        if text.lower() in ["تجديد", "resend", "ارسال"]:
            if user["retries"] >= user["max_retries"]:
                await event.respond("❌ وصلت لأقصى عدد محاولات. ابدأ من جديد بـ /start")
                users.pop(user_id, None)
                return
            await send_code(event, user_id, user, is_retry=True)
            return

        msg = await event.respond("⏳ جاري التحقق من الرمز...")
        await verify_code(msg, user_id, user, text)

# ========== إرسال رمز التحقق ==========
async def send_code(event, user_id, user, is_retry):
    if is_retry:
        user["retries"] += 1
        msg = await event.respond("🔄 جاري إعادة إرسال رمز التحقق...")
        await asyncio.sleep(2)
    else:
        msg = await event.respond("📲 جاري إرسال رمز التحقق...")
        await asyncio.sleep(1)

    # إغلاق عميل سابق إن وجد
    if "client" in user:
        try:
            await user["client"].disconnect()
        except:
            pass

    api_id = user["data"]["api_id"]
    api_hash = user["data"]["api_hash"]
    phone = user["data"]["phone"]

    client = TelegramClient(f'temp_{user_id}', api_id, api_hash)
    try:
        await client.connect()
        user["client"] = client
        # إرسال طلب الكود (مع force_sms لضمان وصول رسالة)
        sent = await client.send_code_request(phone, force_sms=True)
        user["phone_code_hash"] = sent.phone_code_hash
        await msg.edit(
            f"✅ تم إرسال رمز التحقق{' (محاولة '+str(user["retries"])+')' if is_retry else ''}!\n\n"
            "**📲 تفقد تيليجرام وأرسل الرمز (5 أرقام):**\n"
            "⚠️ اكتب `تجديد` إذا لم يصلك الرمز أو انتهت صلاحيته"
        )
    except FloodWaitError as e:
        await msg.edit(f"⏳ **انتظر {e.seconds} ثانية** قبل المحاولة مرة أخرى.")
        user["step"] = "phone"
    except Exception as e:
        await msg.edit(f"❌ **خطأ:** {e}\nتأكد من صحة البيانات.")
        user["step"] = "phone"

# ========== التحقق من رمز التحقق ==========
async def verify_code(msg, user_id, user, code):
    client = user["client"]
    phone = user["data"]["phone"]
    phone_code_hash = user.get("phone_code_hash")

    try:
        await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
    except PhoneCodeExpiredError:
        if user["retries"] < user["max_retries"]:
            await msg.edit("❌ انتهت صلاحية الرمز. جاري إرسال رمز جديد تلقائياً...")
            await asyncio.sleep(2)
            user["retries"] += 1
            await send_code(msg, user_id, user, is_retry=True)
        else:
            await msg.edit("❌ انتهت صلاحية الرمز ووصلت للحد الأقصى. ابدأ من جديد بـ /start")
            users.pop(user_id, None)
        return
    except PhoneCodeInvalidError:
        await msg.edit("❌ رمز التحقق غير صحيح. أعد إدخاله:\n⚠️ اكتب `تجديد` لطلب رمز جديد")
        return
    except SessionPasswordNeededError:
        user["step"] = "password"
        await msg.edit("🔐 حسابك يتطلب التحقق بخطوتين. أرسل كلمة المرور:")
        return
    except FloodWaitError as e:
        await msg.edit(f"⏳ انتظر {e.seconds} ثانية.")
        return
    except Exception as e:
        await msg.edit(f"❌ خطأ: {e}\nحاول مرة أخرى أو اكتب `تجديد`")
        return

    # نجاح تسجيل الدخول
    session_str = await client.export_session_string()
    with open(f"{SESSIONS_FOLDER}/{user_id}.txt", "w") as f:
        f.write(session_str)
    await client.disconnect()
    users.pop(user_id, None)

    await msg.edit(
        "**🎉 مبروك! تم التنصيب بنجاح!**\n"
        "**✅ السورس شغال على حسابك حالاً**\n\n"
        "**💡 استخدم `.اوامر` لعرض القائمة**\n"
        "🛑 `.ايقاف` لإيقاف السورس\n"
        "🔄 `/start` للتشغيل مجدداً"
    )
    # تشغيل السورس في خيط منفصل
    Thread(target=run_user_source, args=(str(user_id),)).start()

# ========== استقبال كلمة مرور 2FA ==========
@bot.on(events.NewMessage(func=lambda e: e.sender_id in users and users[e.sender_id]["step"] == "password"))
async def handle_password(event):
    user_id = event.sender_id
    user = users[user_id]
    password = event.text.strip()

    msg = await event.respond("⏳ جاري التحقق من كلمة المرور...")
    client = user["client"]
    try:
        await client.sign_in(password=password)
    except Exception as e:
        await msg.edit(f"❌ كلمة المرور غير صحيحة: {e}")
        return

    session_str = await client.export_session_string()
    with open(f"{SESSIONS_FOLDER}/{user_id}.txt", "w") as f:
        f.write(session_str)
    await client.disconnect()
    users.pop(user_id, None)

    await msg.edit(
        "**🎉 مبروك! تم التنصيب بنجاح!**\n"
        "**✅ السورس شغال على حسابك حالاً**\n"
        "**💡 استخدم `.اوامر` لعرض القائمة**"
    )
    Thread(target=run_user_source, args=(str(user_id),)).start()

# ========== تشغيل الجلسات المحفوظة تلقائياً ==========
for filename in os.listdir(SESSIONS_FOLDER):
    if filename.endswith(".txt"):
        uid = filename[:-4]
        if uid not in running_users:
            Thread(target=run_user_source, args=(uid,)).start()

print("🚀 البوت جاهز لاستقبال الرسائل")
bot.run_until_disconnected()
