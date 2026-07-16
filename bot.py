import os
import re
import sys
import json
import shutil
from datetime import datetime
from telethon import TelegramClient, events, Button
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.sessions import StringSession
from flask import Flask
from threading import Thread

# ====== إعدادات ======
BOT_TOKEN = "8963454170:AAGlM4mHDAjtXMcTYQd9_RRMy0I6JgnMBwg"
API_ID = 6
API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"
SESSIONS_FOLDER = "sessions"

# ====== إنشاء مجلد الجلسات ======
os.makedirs(SESSIONS_FOLDER, exist_ok=True)

# ====== سيرفر وهمي ======
app = Flask(__name__)

@app.route('/')
def home():
    return "بوت التنصيب شغال ✅"

@app.route('/start/<user_id>')
def start_user(user_id):
    """تشغيل سورس المستخدم"""
    session_file = f"{SESSIONS_FOLDER}/{user_id}.txt"
    if os.path.exists(session_file):
        Thread(target=run_user_source, args=(user_id,)).start()
        return f"✅ تم تشغيل سورس المستخدم {user_id}"
    return "❌ لا توجد جلسة لهذا المستخدم"

Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))).start()

# ====== تشغيل البوت ======
bot = TelegramClient('deploy_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

users = {}
running_users = {}  # المستخدمين اللي سورسهم شغال

# ====== دوال تشغيل سورس المستخدم ======
def run_user_source(user_id):
    """تشغيل سورس المستخدم في خيط منفصل"""
    try:
        session_file = f"{SESSIONS_FOLDER}/{user_id}.txt"
        with open(session_file, "r") as f:
            session_string = f.read().strip()
        
        user_client = TelegramClient(
            StringSession(session_string), 
            API_ID, 
            API_HASH
        )
        user_client.start()
        
        # تخزين العميل
        running_users[user_id] = {
            "client": user_client,
            "started_at": datetime.now()
        }
        
        # ====== أوامر المستخدم ======
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
            day = datetime.now().strftime("%Y-%m-%d")
            await event.edit(f"**⏰ الوقت:** `{now}`\n**📅 التاريخ:** `{day}`")

        @user_client.on(events.NewMessage(outgoing=True, pattern=r'\.عريض (.+)'))
        async def bold(event):
            text = event.pattern_match.group(1)
            await event.edit(f"**{text}**")

        @user_client.on(events.NewMessage(outgoing=True, pattern=r'\.مائل (.+)'))
        async def italic(event):
            text = event.pattern_match.group(1)
            await event.edit(f"__{text}__")

        @user_client.on(events.NewMessage(outgoing=True, pattern=r'\.مشطوب (.+)'))
        async def strike(event):
            text = event.pattern_match.group(1)
            await event.edit(f"~~{text}~~")

        @user_client.on(events.NewMessage(outgoing=True, pattern=r'\.قلب (.+)'))
        async def flip_text(event):
            text = event.pattern_match.group(1)
            await event.edit(f"**🔄:** `{text[::-1]}`")

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
            except Exception as e:
                await event.edit(f"**❌ خطأ:** {e}")

        @user_client.on(events.NewMessage(outgoing=True, pattern=r'\.بايو (.+)'))
        async def set_bio(event):
            try:
                await user_client(UpdateProfileRequest(about=event.pattern_match.group(1)))
                await event.edit("**✅ تم تغيير البايو!**")
            except Exception as e:
                await event.edit(f"**❌ خطأ:** {e}")

        @user_client.on(events.NewMessage(outgoing=True, pattern=r'\.مسح (\d+)'))
        async def delete_msgs(event):
            count = int(event.pattern_match.group(1))
            chat = await event.get_input_chat()
            messages = []
            async for msg in user_client.iter_messages(chat, limit=count + 1):
                messages.append(msg.id)
            await user_client.delete_messages(chat, messages)
            await event.respond(f"**🗑️ تم مسح {count} رسالة**")

        @user_client.on(events.NewMessage(outgoing=True, pattern=r'\.حذف'))
        async def delete_chat(event):
            chat = await event.get_input_chat()
            await event.delete()
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

**╰━━━━━━━━━━━━━━━━━━━━━━━━━━╯**
""")

        @user_client.on(events.NewMessage(outgoing=True, pattern=r'\.ايقاف'))
        async def stop_user(event):
            await event.edit("**👋 جاري إيقاف السورس...**")
            await user_client.disconnect()
            if user_id in running_users:
                del running_users[user_id]

        print(f"✅ تم تشغيل سورس المستخدم {user_id}")
        user_client.run_until_disconnected()
        
    except Exception as e:
        print(f"❌ خطأ في تشغيل سورس المستخدم {user_id}: {e}")
        if user_id in running_users:
            del running_users[user_id]

# ====== أوامر البوت ======
@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    user_id = str(event.sender_id)
    
    # لو المستخدم عنده جلسة سابقة والسورس مش شغال
    if os.path.exists(f"{SESSIONS_FOLDER}/{user_id}.txt"):
        if user_id not in running_users:
            Thread(target=run_user_source, args=(user_id,)).start()
            await event.respond("**✅ تم تشغيل السورس تلقائياً!**\n**💡 استخدم `.اوامر` لعرض القائمة**")
        else:
            await event.respond("**✅ السورس شغال بالفعل!**\n**💡 استخدم `.اوامر` لعرض القائمة**")
        return
    
    await event.respond("""
**╭━━━━━━━[ بـوت تـنـصـيـب تـيـلـيـثـون ]━━━━━━━╮**

**👋 أهلاً بك!**

**هذا البوت سيقوم بتنصيب السورس على حسابك**
**كل اللي عليك اتباع الخطوات**

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
    await event.edit("**📝 الخطوة 1/4: أرسل API_ID (أرقام فقط):**")

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
        await event.respond("✅ تم!\n**📝 الخطوة 2/4: أرسل API_HASH:**")
    
    elif step == 2:  # api_hash
        if len(event.text.strip()) < 10:
            return await event.respond("❌ غير صالح! حاول مرة أخرى:")
        user["api_hash"] = event.text.strip()
        user["step"] = 3
        await event.respond("✅ تم!\n**📱 الخطوة 3/4: أرسل رقم الهاتف (مثال: +201234567890):**")
    
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
            await msg.edit("✅ تم الإرسال!\n**📲 الخطوة 4/4: أرسل رمز التحقق (5 أرقام):**")
        except Exception as e:
            await msg.edit(f"❌ خطأ: {e}")
            user["step"] = 3
    
    elif step == 4:  # code
        code = event.text.strip()
        if not code.isdigit():
            return await event.respond("❌ أرقام فقط!")
        
        msg = await event.respond("⏳ جاري تسجيل الدخول وتشغيل السورس...")
        try:
            await user["client"].sign_in(user["phone"], code, phone_code_hash=user["hash"])
            session_string = await user["client"].export_session_string()
            
            # حفظ الجلسة
            with open(f"{SESSIONS_FOLDER}/{user_id}.txt", "w") as f:
                f.write(session_string)
            
            # تشغيل السورس فوراً
            Thread(target=run_user_source, args=(str(user_id),)).start()
            
            await msg.edit("""
**🎉 مبروك! السورس شغال على حسابك!**

**✅ تم التنصيب والتشغيل بنجاح**

**💡 الأوامر المتاحة:**
`.اوامر` - عرض قائمة الأوامر
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

**⚠️ للتوقف عن استخدام السورس أرسل `.ايقاف`**
**🔄 للعودة أرسل /start مرة أخرى**
""")
        except Exception as e:
            await msg.edit(f"❌ خطأ: {e}\nتأكد من الرمز وحاول مرة أخرى")
        finally:
            try:
                await user["client"].disconnect()
            except:
                pass
            del users[user_id]

# ====== أمر إيقاف السورس ======
@bot.on(events.NewMessage(pattern='/stop'))
async def stop_bot(event):
    user_id = str(event.sender_id)
    if user_id in running_users:
        try:
            await running_users[user_id]["client"].disconnect()
            del running_users[user_id]
            await event.respond("**✅ تم إيقاف السورس!**\n**🔄 أرسل /start للتشغيل مرة أخرى**")
        except:
            await event.respond("**❌ حدث خطأ أثناء الإيقاف**")
    else:
        await event.respond("**ℹ️ السورس ليس قيد التشغيل**")

# ====== أمر عرض المستخدمين النشطين ======
@bot.on(events.NewMessage(pattern='/users'))
async def active_users(event):
    count = len(running_users)
    sessions_count = len([f for f in os.listdir(SESSIONS_FOLDER) if f.endswith('.txt')])
    await event.respond(f"""
**📊 إحصائيات البوت:**
• المستخدمين النشطين حالياً: `{count}`
• إجمالي الجلسات المخزنة: `{sessions_count}`
""")

print("""
╔══════════════════════════════════╗
║   ✅ بوت التنصيب جاهز            ║
║   🤖 أرسل /start للبدء          ║
║   👥 /users لعرض الإحصائيات     ║
╚══════════════════════════════════╝
""")

# تحميل الجلسات القديمة تلقائياً
for session_file in os.listdir(SESSIONS_FOLDER):
    if session_file.endswith('.txt'):
        user_id = session_file.replace('.txt', '')
        if user_id not in running_users:
            Thread(target=run_user_source, args=(user_id,)).start()

bot.run_until_disconnected()
