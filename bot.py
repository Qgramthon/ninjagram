import os
import re
import asyncio
from telethon import TelegramClient, events, Button
from flask import Flask
from threading import Thread

# تشغيل سيرفر وهمي لـ Railway
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# إعدادات البوت
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

bot = TelegramClient('deploy_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# تخزين مؤقت
users = {}

# رسالة البداية
START_TEXT = """
**✯ بوت تنصيب تيليثون ✯**

• اضغط **بدء التنصيب** للمتابعة
• لازم تجهز api_id و api_hash من my.telegram.org
"""

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.respond(START_TEXT, buttons=[
        [Button.inline("🚀 بدء التنصيب", "deploy")],
        [Button.url("🔑 احصل على api", "https://my.telegram.org")]
    ])

@bot.on(events.CallbackQuery(data="deploy"))
async def deploy(event):
    users[event.sender_id] = {}
    await event.edit("**📝 أرسل api_id:**")
    bot.add_event_handler(get_api_id, events.NewMessage(func=lambda e: e.sender_id in users and "api_id" not in users[e.sender_id]))

async def get_api_id(event):
    if not event.text.isdigit():
        return await event.respond("❌ أرقام فقط!")
    users[event.sender_id]["api_id"] = int(event.text)
    await event.respond("**📝 أرسل api_hash:**")
    bot.add_event_handler(get_api_hash, events.NewMessage(func=lambda e: e.sender_id in users and "api_hash" not in users[e.sender_id]))

async def get_api_hash(event):
    users[event.sender_id]["api_hash"] = event.text.strip()
    await event.respond("**📱 أرسل رقم الهاتف (مثال: +201234567890):**")
    bot.add_event_handler(get_phone, events.NewMessage(func=lambda e: e.sender_id in users and "phone" not in users[e.sender_id]))

async def get_phone(event):
    phone = event.text.strip()
    if not re.match(r'^\+[0-9]{7,15}$', phone):
        return await event.respond("❌ رقم غير صالح!")
    users[event.sender_id]["phone"] = phone
    
    await event.respond("**⏳ جاري إرسال رمز التحقق...**")
    
    client = TelegramClient(f'session_{event.sender_id}', 
                           users[event.sender_id]["api_id"],
                           users[event.sender_id]["api_hash"])
    await client.connect()
    users[event.sender_id]["client"] = client
    
    try:
        sent = await client.send_code_request(phone)
        users[event.sender_id]["hash"] = sent.phone_code_hash
        await event.respond("**📲 أرسل رمز التحقق:**")
        bot.add_event_handler(get_code, events.NewMessage(func=lambda e: e.sender_id in users and "code" not in users[e.sender_id]))
    except Exception as e:
        await event.respond(f"❌ خطأ: {str(e)}")

async def get_code(event):
    user = users[event.sender_id]
    code = event.text.strip()
    user["code"] = code
    
    msg = await event.respond("**⏳ جاري تسجيل الدخول...**")
    
    try:
        await user["client"].sign_in(user["phone"], user["code"], phone_code_hash=user["hash"])
        string = await user["client"].export_session_string()
        
        await msg.edit(f"""
**✅ تم التنصيب بنجاح!**

**📋 كود الجلسة:** (انسخه واحفظه)
`{string}`

**📂 ارفع ملف `source.py` على Railway**
**⚙️ ضع كود الجلسة في متغير اسمه `SESSION`**
        """)
    except Exception as e:
        await msg.edit(f"**❌ خطأ في تسجيل الدخول:** {str(e)}")
    finally:
        await user["client"].disconnect()
        del users[event.sender_id]

# تشغيل فلاسك مع البوت
Thread(target=run_flask).start()
print("✅ البوت شغال...")
bot.run_until_disconnected()
