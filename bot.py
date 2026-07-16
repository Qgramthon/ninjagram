import os
import re
import sys
from telethon import TelegramClient, events, Button
from flask import Flask
from threading import Thread

# ====== إعدادات البوت (ثابتة) ======
BOT_TOKEN = "8963454170:AAGlM4mHDAjtXMcTYQd9_RRMy0I6JgnMBwg"
API_ID = 6  # api_id الرسمي لتطبيق تيليجرام
API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"  # api_hash الرسمي

# ====== تشغيل سيرفر وهمي لـ Railway ======
app = Flask(__name__)

@app.route('/')
def home():
    return "بوت التنصيب شغال ✅"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

Thread(target=run_flask).start()

# ====== تشغيل البوت ======
try:
    bot = TelegramClient('deploy_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
    print("✅ تم تشغيل بوت التنصيب بنجاح!")
except Exception as e:
    print(f"❌ خطأ في تشغيل البوت: {e}")
    sys.exit(1)

# ====== تخزين مؤقت للمستخدمين ======
users = {}

# ====== رسالة البداية ======
START_TEXT = """
**╭━━━━━━━[ بـوت تـنـصـيـب تـيـلـيـثـون ]━━━━━━━╮**

**👋 أهلاً بك!**

**هذا البوت يساعدك على استخراج كود جلسة تيليثون**
**لتشغيل حسابك الشخصي مع السورس الخفيف**

**📋 الخطوات:**
**1️⃣ اضغط على (بدء التنصيب)**
**2️⃣ أدخل api_id من my.telegram.org**
**3️⃣ أدخل api_hash**
**4️⃣ أدخل رقم هاتفك**
**5️⃣ أدخل رمز التحقق**
**6️⃣ استلم كود الجلسة**

**╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯**
"""

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    buttons = [
        [Button.inline("🚀 بدء التنصيب", b"start_deploy")],
        [Button.url("🔑 احصل على api_id", "https://my.telegram.org")]
    ]
    await event.respond(START_TEXT, buttons=buttons)

# ====== بدء التنصيب ======
@bot.on(events.CallbackQuery(data=b"start_deploy"))
async def start_deploy(event):
    user_id = event.sender_id
    users[user_id] = {"step": 1}
    
    await event.edit("""
**📝 الخطوة الأولى: إدخال api_id**

**أرسل api_id الخاص بك الآن**
**تحصل عليه من:** my.telegram.org

⚠️ يجب أن يكون أرقام فقط
""", buttons=[
        [Button.url("🔗 افتح my.telegram.org", "https://my.telegram.org")]
    ])

# ====== استقبال api_id ======
@bot.on(events.NewMessage(func=lambda e: e.sender_id in users and users[e.sender_id].get("step") == 1))
async def get_api_id(event):
    user_id = event.sender_id
    
    if not event.text.isdigit():
        await event.respond("**❌ خطأ: api_id يجب أن يكون أرقام فقط!**\nحاول مرة أخرى:")
        return
    
    users[user_id]["api_id"] = int(event.text)
    users[user_id]["step"] = 2
    
    await event.respond("**✅ تم استلام api_id بنجاح**\n\n**📝 الخطوة الثانية: إدخال api_hash**\nأرسل api_hash الآن:")

# ====== استقبال api_hash ======
@bot.on(events.NewMessage(func=lambda e: e.sender_id in users and users[e.sender_id].get("step") == 2))
async def get_api_hash(event):
    user_id = event.sender_id
    api_hash = event.text.strip()
    
    if len(api_hash) < 10:
        await event.respond("**❌ خطأ: api_hash غير صالح!**\nحاول مرة أخرى:")
        return
    
    users[user_id]["api_hash"] = api_hash
    users[user_id]["step"] = 3
    
    await event.respond("**✅ تم استلام api_hash بنجاح**\n\n**📱 الخطوة الثالثة: إدخال رقم الهاتف**\nأرسل رقم هاتفك مع رمز الدولة:\nمثال: `+201234567890`")

# ====== استقبال رقم الهاتف ======
@bot.on(events.NewMessage(func=lambda e: e.sender_id in users and users[e.sender_id].get("step") == 3))
async def get_phone(event):
    user_id = event.sender_id
    phone = event.text.strip()
    
    if not re.match(r'^\+[0-9]{7,15}$', phone):
        await event.respond("**❌ خطأ: صيغة الرقم غير صحيحة!**\nمثال: `+201234567890`\nحاول مرة أخرى:")
        return
    
    users[user_id]["phone"] = phone
    users[user_id]["step"] = 4
    
    # إنشاء عميل مؤقت
    try:
        client = TelegramClient(
            f'temp_{user_id}',
            users[user_id]["api_id"],
            users[user_id]["api_hash"]
        )
        await client.connect()
        users[user_id]["client"] = client
        
        # إرسال رمز التحقق
        sent = await client.send_code_request(phone)
        users[user_id]["phone_code_hash"] = sent.phone_code_hash
        
        await event.respond("**📲 تم إرسال رمز التحقق إلى تيليجرام**\n\n**🔢 الخطوة الرابعة: إدخال رمز التحقق**\nأرسل الرمز المكون من 5 أرقام:")
    
    except Exception as e:
        await event.respond(f"**❌ خطأ في إرسال رمز التحقق:**\n`{str(e)}`")
        users[user_id]["step"] = 3

# ====== استقبال رمز التحقق ======
@bot.on(events.NewMessage(func=lambda e: e.sender_id in users and users[e.sender_id].get("step") == 4))
async def get_code(event):
    user_id = event.sender_id
    code = event.text.strip()
    
    if not code.isdigit() or len(code) < 4:
        await event.respond("**❌ خطأ: رمز التحقق غير صالح!**\nحاول مرة أخرى:")
        return
    
    user = users[user_id]
    msg = await event.respond("**⏳ جاري تسجيل الدخول...**")
    
    try:
        # تسجيل الدخول
        await user["client"].sign_in(
            user["phone"],
            code,
            phone_code_hash=user["phone_code_hash"]
        )
        
        # استخراج كود الجلسة
        session_string = await user["client"].export_session_string()
        
        await msg.edit(f"""
**🎉 تم التنصيب بنجاح!**

**📋 كود الجلسة الخاص بك:**
