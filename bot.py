#!/usr/bin/env python3
"""
بوت تليجرام متعدد المهام - مبني على Telethon
يدعم ثلاث طرق لتسجيل الدخول، أنسبها لـ Railway هي login3 (استيراد جلسة)
"""

import os
import sys
import asyncio
import logging
import json
import traceback
from datetime import datetime
from pathlib import Path

from telethon import TelegramClient, events, errors
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeAudio, DocumentAttributeFilename

from cryptography.fernet import Fernet
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from deep_translator import GoogleTranslator
import yt_dlp
import speedtest
import re

# ==================== الإعدادات الأولية ====================
Path("data").mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data/session_errors.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8879863328:AAH_PB_1i50hIyU-UI58TcD-dflHl4dBFqo")

# ==================== التشفير ====================
def get_key():
    key_file = Path("data/encryption_key.txt")
    if key_file.exists():
        return key_file.read_text().strip().encode()
    key = os.environ.get("ENCRYPTION_KEY", "")
    if key:
        try:
            Fernet(key.encode())
            return key.encode()
        except:
            pass
    new_key = Fernet.generate_key()
    key_file.write_text(new_key.decode())
    return new_key

cipher = Fernet(get_key())
enc = lambda t: cipher.encrypt(t.encode()).decode() if t else None
dec = lambda t: cipher.decrypt(t.encode()).decode() if t else None

# ==================== قاعدة بيانات ====================
class SessionDB:
    def __init__(self, filepath="data/sessions.json"):
        self.filepath = Path(filepath)
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()
    
    def _load(self):
        if self.filepath.exists():
            try:
                return json.loads(self.filepath.read_text())
            except:
                return {}
        return {}
    
    def _save(self):
        self.filepath.write_text(json.dumps(self.data, indent=2))
    
    def get(self, uid):
        return self.data.get(str(uid))
    
    def set(self, uid, data):
        self.data[str(uid)] = data
        self._save()
    
    def delete(self, uid):
        if str(uid) in self.data:
            del self.data[str(uid)]
            self._save()
    
    def get_all(self):
        return self.data

db = SessionDB()
active_bots = {}
login_states = {}

# ==================== أدوات مساعدة ====================
def detect_language(text):
    arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
    return 'ar' if arabic_chars > len(text) * 0.3 else 'en'

def translate_text(text, target='en'):
    try:
        if target == 'en':
            return GoogleTranslator(source='ar', target='en').translate(text)
        else:
            return GoogleTranslator(source='en', target='ar').translate(text)
    except:
        return "فشلت الترجمة"

def analyze_session_error(error):
    msg = str(error)
    if isinstance(error, errors.rpcerrorlist.AuthKeyUnregisteredError):
        return "🔑 الجلسة انتهت صلاحيتها. استخدم /logout ثم /login3 (مضمونة)."
    elif isinstance(error, errors.rpcerrorlist.AuthKeyDuplicatedError):
        return "👥 الجلسة مفتوحة في مكان آخر. استخدم /stop ثم /run."
    elif isinstance(error, errors.rpcerrorlist.SessionRevokedError):
        return "🚫 الجلسة أُلغيت. أعد تسجيل الدخول."
    elif isinstance(error, errors.rpcerrorlist.FloodWaitError):
        return f"⏳ انتظر {getattr(error, 'seconds', 0)} ثانية."
    return f"❌ خطأ: {msg[:150]}"

# ==================== أوامر البوت ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    logged = "✅ مسجل دخول! /run للتشغيل" if db.get(uid) else "🔴 غير مسجل"
    
    await update.message.reply_text(f"""
👋 **مرحباً بك!**

📌 حالتك: {logged}

🔹 **طرق تسجيل الدخول:**
• /login - تقليدي (قد لا يصل الكود على السيرفرات)
• /login2 - سريع (نفس المشكلة)
• /login3 - **الأفضل** (إدخال جلسة جاهزة)

🔸 **أوامر التشغيل:**
/run - /stop - /status - /logout - /logs

🎯 **الميزات:**
.ترجم - .صوت - .تحويل - .بنغ - .يوت - .نص
""")

async def login3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تسجيل الدخول عبر String Session - الطريقة المضمونة"""
    uid = update.effective_user.id
    if db.get(uid):
        await update.message.reply_text("✅ مسجل دخول مسبقاً.")
        return
    
    await update.message.reply_text(
        "📋 **استيراد جلسة جاهزة**\n\n"
        "أرسل string session الخاصة بك.\n"
        "للحصول عليها، شغّل الكود التالي على جهازك الشخصي:\n\n"
        "```python\n"
        "from telethon import TelegramClient\n"
        "from telethon.sessions import StringSession\n\n"
        "API_ID = 12345\n"
        "API_HASH = 'abc123...'\n\n"
        "async def main():\n"
        "    client = TelegramClient(StringSession(), API_ID, API_HASH)\n"
        "    await client.start()\n"
        "    print(client.session.save())\n\n"
        "import asyncio\n"
        "asyncio.run(main())\n"
        "```\n\n"
        "أو استخدم أي مولد String Session.\n"
        "بعدها أرسل الـ session string هنا."
    )
    login_states[uid] = {'step': 'session_string'}

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in login_states:
        if 'c' in login_states[uid]:
            try: await login_states[uid]['c'].disconnect()
            except: pass
        del login_states[uid]
        await update.message.reply_text("✅ تم الإلغاء")
    else:
        await update.message.reply_text("لا توجد عملية جارية.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in active_bots:
        client = active_bots[uid]
        conn = "🟢 متصل" if client.is_connected() else "🟠 منفصل"
        await update.message.reply_text(f"✅ البوت شغال ({conn})")
    elif db.get(uid):
        await update.message.reply_text("🟡 مسجل لكن متوقف. /run")
    else:
        await update.message.reply_text("🔴 غير مسجل.")

async def logs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_file = Path("data/session_errors.log")
    if log_file.exists():
        lines = log_file.read_text(encoding='utf-8').splitlines()[-15:]
        await update.message.reply_text("📋 " + "\n".join(lines)[:3500] or "فارغ")
    else:
        await update.message.reply_text("لا توجد سجلات.")

# ==================== تشغيل اليوزربوت ====================
async def run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = db.get(uid)
    if not user:
        await update.message.reply_text("❌ سجل دخول أولاً (الأفضل /login3)")
        return
    if uid in active_bots:
        await update.message.reply_text("✅ البوت شغال بالفعل.")
        return
    
    msg = await update.message.reply_text("🔄 تشغيل...")
    try:
        api_id = int(dec(user['api_id']))
        api_hash = dec(user['api_hash'])
        session_str = dec(user['session'])
        
        client = TelegramClient(StringSession(session_str), api_id, api_hash)
        await client.start()
        me = await client.get_me()
        
        # ---- الأوامر ----
        @client.on(events.NewMessage(pattern=r'\.بنغ'))
        async def ping_handler(event):
            try:
                await event.edit("📡 قياس...")
                st = speedtest.Speedtest()
                st.get_best_server()
                dl = st.download() / 1_000_000
                ul = st.upload() / 1_000_000
                p = st.results.ping
                await event.edit(f"🏓 📥 {dl:.1f} 📤 {ul:.1f} 🕐 {p:.0f}")
            except Exception as e:
                await event.edit(f"❌ {e}")

        @client.on(events.NewMessage(pattern=r'\.ترجم'))
        async def translate_handler(event):
            reply = await event.get_reply_message()
            if not reply or not reply.text:
                return await event.reply("❌ رد على رسالة")
            await event.edit("🔄 ترجمة...")
            text = reply.text
            lang = detect_language(text)
            target = 'en' if lang == 'ar' else 'ar'
            result = translate_text(text, target)
            await event.edit(f"{'🇬🇧' if target=='en' else '🇸🇦'} {result}")

        @client.on(events.NewMessage(pattern=r'\.صوت'))
        async def audio_handler(event):
            reply = await event.get_reply_message()
            if not reply or not reply.video:
                return await event.reply("❌ رد على فيديو")
            await event.edit("🎵 معالجة...")
            path = await reply.download_media()
            await event.client.send_file(event.chat_id, path, reply_to=reply.id, caption="🎵 تم!", force_document=False)
            os.remove(path)
            await event.delete()

        @client.on(events.NewMessage(pattern=r'\.نص'))
        async def stt_handler(event):
            reply = await event.get_reply_message()
            if not reply or (not reply.voice and not reply.audio):
                return await event.reply("❌ رد على رسالة صوتية")
            await event.edit("🎙️ استخراج...")
            path = await reply.download_media()
            try:
                result = await client.transcribe_voice(event.chat_id, reply.id)
                if result:
                    await event.edit(f"📝 {result}")
            except:
                await event.edit("⚠️ استخدم زر Aa في تيليجرام بريميوم")
            if os.path.exists(path):
                os.remove(path)

        @client.on(events.NewMessage(pattern=r'\.تحويل'))
        async def convert_handler(event):
            reply = await event.get_reply_message()
            if not reply or not reply.media:
                return await event.reply("❌ رد على صورة/ستيكر")
            await event.edit("🔄 تحويل...")
            path = await reply.download_media()
            await event.client.send_file(event.chat_id, path, reply_to=reply.id, caption="✅ تم!")
            os.remove(path)
            await event.delete()

        @client.on(events.NewMessage(pattern=r'\.يوت (.+)'))
        async def yt_handler(event):
            query = event.pattern_match.group(1)
            await event.edit(f"🔍 {query}")
            ydl_opts = {'format': 'bestaudio[ext=m4a]/bestaudio/best', 'outtmpl': '%(title)s.%(ext)s', 'quiet': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch:{query}", download=True)['entries'][0]
                title = info['title']
                dur = info['duration']
                for f in Path().glob(f"{title}.*"):
                    if f.exists():
                        await event.edit("📤 رفع...")
                        await event.client.send_file(
                            event.chat_id, str(f),
                            caption=f"🎵 {title}\n⏱️ {dur//60}:{dur%60:02d}",
                            attributes=[DocumentAttributeAudio(duration=dur, title=title, performer=info['uploader']),
                                        DocumentAttributeFilename(f.name)]
                        )
                        os.remove(str(f))
                        await event.delete()
                        return
                await event.edit("❌ فشل")

        # ---- مراقبة الاتصال ----
        async def keep_alive():
            while uid in active_bots:
                await asyncio.sleep(30)
                if uid in active_bots and not active_bots[uid].is_connected():
                    try: await active_bots[uid].connect()
                    except: pass

        asyncio.ensure_future(keep_alive())
        active_bots[uid] = client
        await msg.edit_text(f"✅ شغال! {me.first_name}")
        
    except Exception as e:
        logger.error(f"run error: {traceback.format_exc()}")
        await msg.edit_text(f"❌ {analyze_session_error(e)}")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in active_bots:
        try: await active_bots[uid].disconnect()
        except: pass
        del active_bots[uid]
        await update.message.reply_text("✅ تم الإيقاف")
    else:
        await update.message.reply_text("متوقف بالفعل")

async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in active_bots:
        try: await active_bots[uid].disconnect()
        except: pass
        del active_bots[uid]
    db.delete(uid)
    await update.message.reply_text("✅ تم تسجيل الخروج وحذف الجلسة")

# ==================== معالج تسجيل الدخول (3 طرق) ====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    
    if uid not in login_states:
        return
    
    s = login_states[uid]
    
    # --- login3: استيراد string session ---
    if s['step'] == 'session_string':
        try:
            # محاولة بدء الجلسة للتأكد من صلاحيتها
            temp = TelegramClient(StringSession(text), 1, "x")  # api_id وهمي للاختبار
            await temp.connect()
        except:
            await update.message.reply_text("❌ الجلسة غير صالحة. تأكد من string session كاملة.")
            return
        
        # إذا نجح الاتصال، نخزن الجلسة مع بيانات وهمية (api_id=1, api_hash='x') لأن الجلسة تحويها
        db.set(uid, {
            'api_id': enc('1'),
            'api_hash': enc('x'),
            'phone': enc('مستورد'),
            'session': enc(text),
            'saved_at': datetime.now().isoformat()
        })
        try: await temp.disconnect()
        except: pass
        
        me = await TelegramClient(StringSession(text), 1, "x").get_me()
        await update.message.reply_text(f"✅ تم استيراد الجلسة!\n👤 {me.first_name}\n📱 {me.phone}\n\n🚀 استخدم /run")
        del login_states[uid]
        return
    
    # --- login & login2 ---
    if s['step'] == 'api_id':
        try:
            s['api_id'] = int(text)
            s['step'] = 'api_hash'
            await update.message.reply_text("✅ الخطوة 2/4: أرسل API_HASH")
        except:
            await update.message.reply_text("❌ رقم غير صحيح")
    
    elif s['step'] == 'api_hash':
        s['api_hash'] = text
        s['step'] = 'phone'
        await update.message.reply_text("✅ الخطوة 3/4: أرسل رقم الهاتف (+2012...)")
    
    elif s['step'] == 'phone':
        if not text.startswith('+'):
            return await update.message.reply_text("❌ يجب أن يبدأ بـ +")
        s['phone'] = text
        try:
            c = TelegramClient(StringSession(), s['api_id'], s['api_hash'])
            await c.connect()
            sent = await c.send_code_request(text)
            s['c'] = c
            s['phone_code_hash'] = sent.phone_code_hash
            s['step'] = 'code'
            s['code_attempts'] = 0
            await update.message.reply_text("✅ الخطوة 4/4: تم إرسال الكود. أرسله هنا.\n\n⚠️ إذا لم يصلك الكود خلال دقيقة، استخدم /login3 بدلاً من ذلك.")
        except Exception as e:
            logger.error(f"send code: {e}")
            await update.message.reply_text(f"❌ فشل إرسال الكود: {e}\n\n💡 الحل المضمون: استخدم /login3 مع جلسة جاهزة.")
            if 'c' in s: await s['c'].disconnect()
            del login_states[uid]
    
    elif s['step'] == 'code':
        s['code_attempts'] += 1
        try:
            await s['c'].sign_in(phone=s['phone'], code=text, phone_code_hash=s['phone_code_hash'])
            await finish_login(update, s)
        except SessionPasswordNeededError:
            s['step'] = 'pass'
            await update.message.reply_text("🔒 تحقق بخطوتين. أرسل كلمة المرور:")
        except Exception as e:
            logger.error(f"code error: {e}")
            if s['code_attempts'] >= 3:
                await update.message.reply_text("❌ فشل متكرر. استخدم /login3 بدلاً من ذلك.")
                try: await s['c'].disconnect()
                except: pass
                del login_states[uid]
                return
            try:
                sent = await s['c'].send_code_request(s['phone'])
                s['phone_code_hash'] = sent.phone_code_hash
                await update.message.reply_text("🔄 تم إرسال كود جديد. أرسله:")
            except:
                await update.message.reply_text("❌ خطأ. استخدم /login3.")
                del login_states[uid]
    
    elif s['step'] == 'pass':
        try:
            await s['c'].sign_in(password=text)
            await finish_login(update, s)
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ: {e}")

async def finish_login(update, s):
    uid = update.effective_user.id
    session_str = s['c'].session.save()
    db.set(uid, {
        'api_id': enc(str(s['api_id'])),
        'api_hash': enc(s['api_hash']),
        'phone': enc(s['phone']),
        'session': enc(session_str),
        'saved_at': datetime.now().isoformat()
    })
    me = await s['c'].get_me()
    await update.message.reply_text(f"✅ تم بنجاح! {me.first_name}\n🚀 /run")
    await s['c'].disconnect()
    del login_states[uid]

# ==================== التشغيل الرئيسي ====================
def main():
    print("🚀 بوت Telethon المحسن")
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login3", login3))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("run", run))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("logout", logout))
    app.add_handler(CommandHandler("logs", logs_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ جاهز")
    app.run_polling()

if __name__ == "__main__":
    main()
