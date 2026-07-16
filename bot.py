import os
import re
import sys
from telethon import TelegramClient, events, Button
from flask import Flask
from threading import Thread

# ====== إعدادات البوت ======
BOT_TOKEN = "8963454170:AAGlM4mHDAjtXMcTYQd9_RRMy0I6JgnMBwg"
API_ID = 6
API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"

# ====== سيرفر وهمي ======
app = Flask(__name__)

@app.route('/')
def home():
    return "بوت التنصيب شغال ✅"

Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))).start()

# ====== تشغيل البوت ======
bot = TelegramClient('deploy_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
print("✅ بوت التنصيب شغال!")

users = {}

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.respond("""
**╭━━━━━━━[ بـوت تـنـصـيـب تـيـلـيـثـون ]━━━━━━━╮**

**👋 أهلاً بك! اضغط على بدء التنصيب للمتابعة**

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

@bot.on(events.CallbackQuery(data=b"deploy"))
async def deploy(event):
    users[event.sender_id] = {"step": 1}
    await event.edit("**📝 أرسل API_ID (أرقام فقط):**")

@bot.on(events.NewMessage(func=lambda e: e.sender_id in users))
async def handle_steps(event):
    user_id = event.sender_id
    user = users[user_id]
    step = user.get("step", 0)
    
    if step == 1:  # api_id
        if not event.text.isdigit():
            return await event.respond("❌ أرقام فقط! حاول مرة أخرى:")
        user["api_id"] = int(event.text)
        user["step"] = 2
        await event.respond("✅ تم!\n**📝 أرسل API_HASH:**")
    
    elif step == 2:  # api_hash
        if len(event.text.strip()) < 10:
            return await event.respond("❌ غير صالح! حاول مرة أخرى:")
        user["api_hash"] = event.text.strip()
        user["step"] = 3
        await event.respond("✅ تم!\n**📱 أرسل رقم الهاتف (مثال: +201234567890):**")
    
    elif step == 3:  # phone
        phone = event.text.strip()
        if not re.match(r'^\+[0-9]{7,15}$', phone):
            return await event.respond("❌ صيغة خاطئة! مثال: +201234567890")
        user["phone"] = phone
        user["step"] = 4
        
        msg = await event.respond("⏳ جاري إرسال رمز التحقق...")
        try:
            client = TelegramClient(f'temp_{user_id}', user["api_id"], user["api_hash"])
            await client.connect()
            user["client"] = client
            sent = await client.send_code_request(phone)
            user["hash"] = sent.phone_code_hash
            await msg.edit("✅ تم الإرسال!\n**📲 أرسل رمز التحقق (5 أرقام):**")
        except Exception as e:
            await msg.edit(f"❌ خطأ: {e}")
            user["step"] = 3
    
    elif step == 4:  # code
        code = event.text.strip()
        if not code.isdigit():
            return await event.respond("❌ أرقام فقط!")
        
        msg = await event.respond("⏳ جاري تسجيل الدخول...")
        try:
            await user["client"].sign_in(user["phone"], code, phone_code_hash=user["hash"])
            session = await user["client"].export_session_string()
            
            await msg.edit(f"""
**🎉 تم التنصيب بنجاح!**

**📋 كود الجلسة:**
`{session}`

**📦 للرفع على Railway:**
1️⃣ ارفع ملف `source.py`
2️⃣ أضف متغير `SESSION` = الكود أعلاه

⚠️ لا تشارك الكود مع أحد!
""")
        except Exception as e:
            await msg.edit(f"❌ خطأ: {e}\nتأكد من الرمز وحاول مرة أخرى")
        finally:
            try:
                await user["client"].disconnect()
            except:
                pass
            del users[user_id]

print("""
╔══════════════════════════════════╗
║   ✅ بوت التنصيب جاهز            ║
║   🤖 أرسل /start للبدء          ║
╚══════════════════════════════════╝
""")

bot.run_until_disconnected()
