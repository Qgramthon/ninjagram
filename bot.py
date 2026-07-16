import os
import re
import time
import asyncio
import logging
from datetime import datetime
from telethon import TelegramClient, events, Button
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    FloodWaitError,
    PhoneNumberInvalidError,
)
from flask import Flask
from threading import Thread

# -------------------- الإعدادات --------------------
BOT_TOKEN = "8963454170:AAGlM4mHDAjtXMcTYQd9_RRMy0I6JgnMBwg"
API_ID = 6
API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"
SESSIONS_DIR = "sessions"
os.makedirs(SESSIONS_DIR, exist_ok=True)

# أقل فاصل زمني مسموح بيه بين إرسال كود وإعادة إرساله (بالثواني)
RESEND_COOLDOWN = 45

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# -------------------- خادم وهمي --------------------
app = Flask(__name__)
@app.route('/')
def index():
    return "OK"
Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))), daemon=True).start()

# -------------------- بدء البوت --------------------
bot = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
logger.info("✅ بوت التنصيب يعمل")

# -------------------- التخزين المؤقت --------------------
pending_users = {}      # المستخدمون في مرحلة التنصيب
active_clients = {}     # العملاء النشطون (حسابات المستخدمين)
user_locks = {}         # قفل مستقل لكل مستخدم لمنع التنفيذ المتوازي

def get_lock(uid) -> asyncio.Lock:
    uid = str(uid)
    if uid not in user_locks:
        user_locks[uid] = asyncio.Lock()
    return user_locks[uid]

# تطبيع الأرقام العربية/الفارسية إلى إنجليزية وإزالة أي مسافات
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

def normalize_digits(text: str) -> str:
    return text.translate(ARABIC_DIGITS).replace(" ", "").strip()

# -------------------- دالة تشغيل سورس المستخدم --------------------
async def launch_user_source(user_id: str):
    session_path = os.path.join(SESSIONS_DIR, f"{user_id}.txt")
    if not os.path.exists(session_path):
        return
    with open(session_path, "r") as f:
        session_str = f.read().strip()
    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
    try:
        await client.start()
    except Exception as e:
        logger.error(f"فشل بدء جلسة {user_id}: {e}")
        return
    active_clients[user_id] = client
    logger.info(f"✅ سورس {user_id} بدأ العمل")

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
        await event.edit(f"**{event.pattern_match.group(1)}**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.مائل (.+)'))
    async def italic(event):
        await event.edit(f"__{event.pattern_match.group(1)}__")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.مشطوب (.+)'))
    async def strike(event):
        await event.edit(f"~~{event.pattern_match.group(1)}~~")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.قلب (.+)'))
    async def flip_text(event):
        await event.edit(f"**🔄:** `{event.pattern_match.group(1)[::-1]}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.زخرفة (.+)'))
    async def decorate(event):
        text = event.pattern_match.group(1)
        d = {'a':'α','b':'в','c':'¢','d':'∂','e':'є','f':'ƒ','g':'g','h':'н',
             'i':'ι','j':'נ','k':'к','l':'ℓ','m':'м','n':'η','o':'σ','p':'ρ',
             'q':'q','r':'я','s':'ѕ','t':'т','u':'υ','v':'ν','w':'ω','x':'χ','y':'у','z':'z'}
        await event.edit(f"**✨:** `{''.join(d.get(c.lower(),c) for c in text)}`")

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
        active_clients.pop(user_id, None)

    await client.run_until_disconnected()

# -------------------- أوامر البوت --------------------
@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    uid = str(event.sender_id)
    if uid in active_clients:
        await event.respond("**✅ السورس شغال بالفعل!**\n**💡 استخدم `.اوامر` للقائمة**")
        return
    if os.path.exists(os.path.join(SESSIONS_DIR, f"{uid}.txt")):
        await event.respond("**⏳ جاري إعادة تشغيل السورس...**")
        asyncio.create_task(launch_user_source(uid))
        await event.respond("**✅ السورس عاد للعمل!**")
        return
    await event.respond(
        "**╭━━━━━━━[ تـنـصـيـب تـيـلـيـثـون ]━━━━━━━╮**\n\n"
        "**👋 أهلاً بك! اضغط على بدء التنصيب**\n\n"
        "**📋 المطلوب:**\n"
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

@bot.on(events.CallbackQuery(data=b"deploy"))
async def deploy_callback(event):
    uid = event.sender_id
    pending_users[uid] = {
        "step": "api_id",
        "data": {},
        "retries": 0,
        "max_retries": 3,
        "last_sent_at": 0,
    }
    await event.edit("**📝 الخطوة 1/4: أرسل API_ID (أرقام فقط):**")

# -------------------- آلة الحالة (محمية بقفل لكل مستخدم) --------------------
@bot.on(events.NewMessage(func=lambda e: e.sender_id in pending_users))
async def state_machine(event):
    uid = event.sender_id
    lock = get_lock(uid)

    if lock.locked():
        # في نفس اللحظة فيه عملية شغالة لنفس المستخدم، تجاهل التكرار
        return

    async with lock:
        if uid not in pending_users:
            return

        user_state = pending_users[uid]
        step = user_state["step"]
        text = event.text.strip()

        if step == "api_id":
            text_norm = normalize_digits(text)
            if not text_norm.isdigit():
                await event.respond("❌ أرقام فقط! حاول مرة أخرى:")
                return
            user_state["data"]["api_id"] = int(text_norm)
            user_state["step"] = "api_hash"
            await event.respond("✅ تم!\n**📝 الخطوة 2/4: أرسل API_HASH:**")

        elif step == "api_hash":
            user_state["data"]["api_hash"] = text
            user_state["step"] = "phone"
            await event.respond("✅ تم!\n**📱 الخطوة 3/4: أرسل رقم الهاتف\nمثال: +201234567890**")

        elif step == "phone":
            phone = normalize_digits(text)
            if not phone.startswith("+"):
                phone = "+" + phone.lstrip("+")
            user_state["data"]["phone"] = phone
            await send_login_code(event, uid, user_state, is_retry=False)

        elif step == "code":
            if text.lower() in ["تجديد", "resend", "ارسال"]:
                elapsed = time.time() - user_state.get("last_sent_at", 0)
                if elapsed < RESEND_COOLDOWN:
                    wait = int(RESEND_COOLDOWN - elapsed)
                    await event.respond(f"⏳ استنى **{wait} ثانية** الأول قبل ما تطلب كود جديد، عشان الكود القديم لسه ممكن يشتغل.")
                    return
                if user_state["retries"] >= user_state["max_retries"]:
                    await event.respond("❌ وصلت لأقصى عدد محاولات. ابدأ من جديد بـ /start")
                    await cleanup_user(uid, user_state)
                    return
                await send_login_code(event, uid, user_state, is_retry=True)
                return
            code = normalize_digits(text)
            msg = await event.respond("⏳ جاري التحقق...")
            await verify_login_code(msg, uid, user_state, code)

        elif step == "password":
            msg = await event.respond("⏳ جاري التحقق من كلمة المرور...")
            await verify_2fa_password(msg, uid, user_state, text)

# -------------------- تنظيف الحالة المؤقتة --------------------
async def cleanup_user(uid, state):
    client = state.get("client")
    if client:
        try:
            await client.disconnect()
        except Exception:
            pass
    pending_users.pop(uid, None)

# -------------------- إرسال رمز التحقق --------------------
async def send_login_code(event, uid, state, is_retry):
    # اقفل أي عميل مؤقت سابق قبل ما تفتح واحد جديد لنفس المستخدم
    old_client = state.get("client")
    if old_client:
        try:
            await old_client.disconnect()
        except Exception:
            pass
        state.pop("client", None)

    if is_retry:
        state["retries"] += 1
        msg = await event.respond("🔄 جاري إعادة إرسال رمز التحقق...")
    else:
        msg = await event.respond("📲 جاري إرسال رمز التحقق...")

    api_id = state["data"]["api_id"]
    api_hash = state["data"]["api_hash"]
    phone = state["data"]["phone"]

    # جلسة في الذاكرة فقط (بدون ملف)، عشان منمنعش تعارض ملفات session
    # بين محاولات متكررة لنفس المستخدم — ده كان سبب فتح جلسات جديدة بالغلط
    client = TelegramClient(StringSession(), api_id, api_hash)
    try:
        await client.connect()
        state["client"] = client
        # لأول مرة من غير force_sms، تليجرام هيختار أفضل وسيلة (تطبيق أو SMS)
        # ونجبرش SMS إلا لما المستخدم يطلب "تجديد" صراحة
        result = await client.send_code_request(phone, force_sms=is_retry)
        state["phone_code_hash"] = result.phone_code_hash
        state["step"] = "code"
        state["last_sent_at"] = time.time()
        retry_note = f" (محاولة {state['retries']})" if is_retry else ""
        await msg.edit(
            f"✅ تم إرسال رمز التحقق{retry_note}!\n\n"
            "**📲 تفقد تيليجرام وأرسل الرمز (بدون مسافات):**\n"
            f"⚠️ اكتب `تجديد` فقط لو مامعاكش رد بعد {RESEND_COOLDOWN} ثانية"
        )
    except PhoneNumberInvalidError:
        await msg.edit("❌ رقم الهاتف غير صحيح. أرسله تاني بالصيغة الدولية، مثال: +201234567890")
        state["step"] = "phone"
    except FloodWaitError as e:
        await msg.edit(f"⏳ **انتظر {e.seconds} ثانية** قبل المحاولة مرة أخرى.")
        state["step"] = "phone"
    except Exception as e:
        await msg.edit(f"❌ **خطأ:** {e}\nتأكد من صحة البيانات.")
        state["step"] = "phone"

# -------------------- التحقق من رمز التحقق --------------------
async def verify_login_code(msg, uid, state, code):
    client = state.get("client")
    if not client:
        await msg.edit("❌ انتهت الجلسة المؤقتة، اكتب `تجديد` أو ابدأ من جديد بـ /start")
        return

    phone = state["data"]["phone"]
    phone_code_hash = state.get("phone_code_hash")
    try:
        await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
    except PhoneCodeExpiredError:
        elapsed = time.time() - state.get("last_sent_at", 0)
        if elapsed < RESEND_COOLDOWN:
            await msg.edit(
                f"❌ الرمز منتهي الصلاحية بالفعل من عندك (اتبعت من {int(elapsed)} ثانية).\n"
                "تأكد إنك بتكتب آخر كود وصلك، وإن مفيش مسافات فيه. لو لسه بيحصل، اكتب `تجديد`."
            )
        else:
            await msg.edit("❌ انتهت صلاحية الرمز. اكتب `تجديد` لطلب رمز جديد.")
        return
    except PhoneCodeInvalidError:
        await msg.edit("❌ رمز التحقق غير صحيح. أعد إدخاله (أرقام إنجليزية بدون مسافات):\n⚠️ اكتب `تجديد` لطلب رمز جديد")
        return
    except SessionPasswordNeededError:
        state["step"] = "password"
        await msg.edit("🔐 حسابك يتطلب التحقق بخطوتين. أرسل كلمة المرور:")
        return
    except FloodWaitError as e:
        await msg.edit(f"⏳ انتظر {e.seconds} ثانية.")
        return
    except Exception as e:
        await msg.edit(f"❌ خطأ: {e}\nحاول مرة أخرى أو اكتب `تجديد`")
        return

    await finalize_login(msg, uid, state)

# -------------------- التحقق من كلمة مرور 2FA --------------------
async def verify_2fa_password(msg, uid, state, password):
    client = state.get("client")
    if not client:
        await msg.edit("❌ انتهت الجلسة المؤقتة، ابدأ من جديد بـ /start")
        return
    try:
        await client.sign_in(password=password)
    except Exception as e:
        await msg.edit(f"❌ كلمة المرور غير صحيحة: {e}")
        return
    await finalize_login(msg, uid, state)

# -------------------- إنهاء تسجيل الدخول وحفظ الجلسة --------------------
async def finalize_login(msg, uid, state):
    client = state["client"]
    session_str = client.session.save()
    with open(os.path.join(SESSIONS_DIR, f"{uid}.txt"), "w") as f:
        f.write(session_str)
    await client.disconnect()
    pending_users.pop(uid, None)

    await msg.edit(
        "**🎉 مبروك! تم التنصيب بنجاح!**\n"
        "**✅ السورس شغال على حسابك حالاً**\n\n"
        "**💡 الأوامر المتاحة:**\n"
        "`.اوامر` - عرض كل الأوامر\n"
        "`.بنغ` - سرعة الاستجابة\n"
        "`.وقتي` - الوقت\n"
        "`.نيم` + اسم - تغيير الاسم\n"
        "`.بايو` + نص - تغيير البايو\n"
        "`.مسح` + عدد - مسح رسائل\n"
        "`.حذف` - حذف المحادثة\n"
        "`.انتحال` + نص - إرسال بدون اسمك\n\n"
        "🛑 `.ايقاف` لإيقاف السورس\n"
        "🔄 `/start` للتشغيل مجدداً"
    )
    asyncio.create_task(launch_user_source(str(uid)))

# -------------------- إعادة تشغيل الجلسات المحفوظة تلقائيًا --------------------
async def restore_sessions():
    for filename in os.listdir(SESSIONS_DIR):
        if filename.endswith(".txt"):
            uid = filename[:-4]
            if uid not in active_clients:
                asyncio.create_task(launch_user_source(uid))

# -------------------- الدخول الرئيسي --------------------
async def main():
    await restore_sessions()
    logger.info("🚀 البوت جاهز لاستقبال الطلبات")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
