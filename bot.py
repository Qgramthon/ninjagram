#!/usr/bin/env python3
"""
بوت تليجرام متعدد المهام - مع نظام الجلسات الآمن
"""

import os, sys, asyncio, logging, json, re, traceback
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
import yt_dlp, speedtest

# ==================== إعدادات أساسية ====================
Path("data").mkdir(parents=True, exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler('data/session_errors.log', encoding='utf-8'),
                              logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8879863328:AAH_PB_1i50hIyU-UI58TcD-dflHl4dBFqo")

# ==================== تشفير ====================
def get_key():
    key_file = Path("data/encryption_key.txt")
    if key_file.exists(): return key_file.read_text().strip().encode()
    key = os.environ.get("ENCRYPTION_KEY","")
    if key:
        try:
            Fernet(key.encode())
            return key.encode()
        except: pass
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
            try: return json.loads(self.filepath.read_text())
            except: return {}
        return {}
    def _save(self): self.filepath.write_text(json.dumps(self.data, indent=2))
    def get(self, uid): return self.data.get(str(uid))
    def set(self, uid, data): self.data[str(uid)] = data; self._save()
    def delete(self, uid):
        if str(uid) in self.data: del self.data[str(uid)]; self._save()
    def get_all(self): return self.data

db = SessionDB()
active_bots = {}
login_states = {}

# ==================== أدوات ====================
def detect_language(text):
    return 'ar' if len(re.findall(r'[\u0600-\u06FF]', text)) > len(text)*0.3 else 'en'

def translate_text(text, target='en'):
    try:
        if target == 'en': return GoogleTranslator(source='ar', target='en').translate(text)
        else: return GoogleTranslator(source='en', target='ar').translate(text)
    except: return "فشلت الترجمة"

def analyze_session_error(error):
    msg = str(error)
    if isinstance(error, errors.rpcerrorlist.AuthKeyUnregisteredError):
        return "🔑 انتهت الجلسة - استخدم /logout ثم /login3"
    if isinstance(error, errors.rpcerrorlist.AuthKeyDuplicatedError):
        return "👥 جلسة مكررة - /stop ثم /run"
    if isinstance(error, errors.rpcerrorlist.SessionRevokedError):
        return "🚫 أُلغيت - أعد /login3"
    if isinstance(error, errors.rpcerrorlist.FloodWaitError):
        return f"⏳ انتظر {getattr(error, 'seconds', 0)} ث"
    return f"❌ {msg[:150]}"

# ==================== أوامر البوت ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = "✅ مسجل! /run" if db.get(uid) else "🔴 غير مسجل"
    await update.message.reply_text(f"""
👋 **مرحباً!**
حالتك: {st}

🔹 تسجيل الدخول المضمون:
• /gen_session - احصل على كود لاستخراج جلسة من جهازك
• /login3 - أدخل الجلسة هنا

🔸 أوامر: /run /stop /status /logout /logs

🎯 .ترجم .صوت .تحويل .بنغ .يوت .نص
""")

async def gen_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعطي المستخدم كود Python لإنشاء String Session على جهازه"""
    await update.message.reply_text(
        "📋 **استخراج جلسة (String Session)**\n\n"
        "1. شغّل الكود التالي على جهازك الشخصي:\n\n"
        "```python\n"
        "from telethon import TelegramClient\n"
        "from telethon.sessions import StringSession\n\n"
        "API_ID = 12345  # استبدله بـ api_id الخاص بك\n"
        "API_HASH = 'abc123...'  # استبدله بـ api_hash\n\n"
        "async def main():\n"
        "    client = TelegramClient(StringSession(), API_ID, API_HASH)\n"
        "    await client.start()  # ستصلك رسالة التحقق في تيليجرام\n"
        "    print(client.session.save())  # انسخ هذا السطر كاملاً\n\n"
        "import asyncio\n"
        "asyncio.run(main())\n"
        "```\n\n"
        "2. بعد تشغيله، سيطلب منك رقم هاتفك وكود التحقق (سيصلك في تيليجرام).\n"
        "3. سيعطيك سلسلة طويلة (String Session) – انسخها.\n"
        "4. ارجع هنا واستخدم /login3 والصق الجلسة.\n\n"
        "💡 **أسهل طريقة:** استخدم [مولد الجلسات](https://replit.com/@painor/Telethon-String-Session-Generator) أونلاين."
    )

async def login3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if db.get(uid):
        await update.message.reply_text("✅ مسجل مسبقاً")
        return
    login_states[uid] = {'step': 'session_string'}
    await update.message.reply_text(
        "📥 أرسل الـ **String Session** التي حصلت عليها:\n"
        "(استخدم /gen_session لمعرفة الطريقة)"
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in login_states:
        if 'c' in login_states[uid]:
            try: await login_states[uid]['c'].disconnect()
            except: pass
        del login_states[uid]
        await update.message.reply_text("✅ ألغيت")
    else:
        await update.message.reply_text("لا عملية جارية")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in active_bots:
        conn = "🟢 متصل" if active_bots[uid].is_connected() else "🟠 منفصل"
        await update.message.reply_text(f"✅ البوت شغال ({conn})")
    elif db.get(uid):
        await update.message.reply_text("🟡 مسجل لكن متوقف /run")
    else:
        await update.message.reply_text("🔴 غير مسجل")

async def logs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_file = Path("data/session_errors.log")
    if log_file.exists():
        lines = log_file.read_text(encoding='utf-8').splitlines()[-15:]
        await update.message.reply_text("📋 " + "\n".join(lines)[:3500] or "فارغ")
    else:
        await update.message.reply_text("لا سجلات")

# ==================== تشغيل اليوزربوت ====================
async def run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = db.get(uid)
    if not user:
        await update.message.reply_text("❌ سجل دخول: /login3")
        return
    if uid in active_bots:
        await update.message.reply_text("✅ شغال")
        return
    msg = await update.message.reply_text("🔄 تشغيل...")
    try:
        api_id = int(dec(user['api_id']))
        api_hash = dec(user['api_hash'])
        session_str = dec(user['session'])
        client = TelegramClient(StringSession(session_str), api_id, api_hash)
        await client.start()
        me = await client.get_me()

        @client.on(events.NewMessage(pattern=r'\.بنغ'))
        async def ping(e):
            try:
                await e.edit("📡 قياس...")
                st = speedtest.Speedtest(); st.get_best_server()
                dl = st.download()/1_000_000; ul = st.upload()/1_000_000; p = st.results.ping
                await e.edit(f"🏓 📥{dl:.1f} 📤{ul:.1f} 🕐{p:.0f}")
            except Exception as ex: await e.edit(f"❌ {ex}")

        @client.on(events.NewMessage(pattern=r'\.ترجم'))
        async def tr(e):
            r = await e.get_reply_message()
            if not r or not r.text: return await e.reply("❌ رد على رسالة")
            await e.edit("🔄 ترجمة...")
            txt = r.text; lang = detect_language(txt); target = 'en' if lang=='ar' else 'ar'
            await e.edit(f"{'🇬🇧' if target=='en' else '🇸🇦'} {translate_text(txt, target)}")

        @client.on(events.NewMessage(pattern=r'\.صوت'))
        async def audio(e):
            r = await e.get_reply_message()
            if not r or not r.video: return await e.reply("❌ رد على فيديو")
            await e.edit("🎵 معالجة...")
            path = await r.download_media()
            await e.client.send_file(e.chat_id, path, reply_to=r.id, caption="🎵 تم!", force_document=False)
            os.remove(path); await e.delete()

        @client.on(events.NewMessage(pattern=r'\.نص'))
        async def stt(e):
            r = await e.get_reply_message()
            if not r or (not r.voice and not r.audio): return await e.reply("❌ رد على صوتية")
            await e.edit("🎙️ استخراج...")
            path = await r.download_media()
            try:
                res = await client.transcribe_voice(e.chat_id, r.id)
                if res: await e.edit(f"📝 {res}")
            except: await e.edit("⚠️ استخدم زر Aa في تيليجرام بريميوم")
            if os.path.exists(path): os.remove(path)

        @client.on(events.NewMessage(pattern=r'\.تحويل'))
        async def convert(e):
            r = await e.get_reply_message()
            if not r or not r.media: return await e.reply("❌ رد على صورة/ستيكر")
            await e.edit("🔄 تحويل...")
            path = await r.download_media()
            await e.client.send_file(e.chat_id, path, reply_to=r.id, caption="✅ تم!")
            os.remove(path); await e.delete()

        @client.on(events.NewMessage(pattern=r'\.يوت (.+)'))
        async def yt(e):
            q = e.pattern_match.group(1)
            await e.edit(f"🔍 {q}")
            ydl_opts = {'format':'bestaudio[ext=m4a]/bestaudio/best','outtmpl':'%(title)s.%(ext)s','quiet':True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch:{q}", download=True)['entries'][0]
                title = info['title']; dur = info['duration']
                for f in Path().glob(f"{title}.*"):
                    if f.exists():
                        await e.edit("📤 رفع...")
                        await e.client.send_file(e.chat_id, str(f),
                            caption=f"🎵 {title}\n⏱️ {dur//60}:{dur%60:02d}",
                            attributes=[DocumentAttributeAudio(duration=dur, title=title, performer=info['uploader']),
                                        DocumentAttributeFilename(f.name)])
                        os.remove(str(f)); await e.delete(); return
                await e.edit("❌ فشل")

        async def keep_alive():
            while uid in active_bots:
                await asyncio.sleep(30)
                if uid in active_bots and not active_bots[uid].is_connected():
                    try: await active_bots[uid].connect()
                    except: pass

        asyncio.ensure_future(keep_alive())
        active_bots[uid] = client
        await msg.edit_text(f"✅ شغال! {me.first_name} @{me.username or ''}")

    except Exception as e:
        logger.error(f"run: {traceback.format_exc()}")
        await msg.edit_text(f"❌ {analyze_session_error(e)}")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in active_bots:
        try: await active_bots[uid].disconnect()
        except: pass
        del active_bots[uid]
        await update.message.reply_text("✅ تم الإيقاف")
    else:
        await update.message.reply_text("متوقف")

async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in active_bots:
        try: await active_bots[uid].disconnect()
        except: pass
        del active_bots[uid]
    db.delete(uid)
    await update.message.reply_text("✅ خروج + حذف الجلسة")

# ==================== معالج الرسائل ====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    if uid not in login_states: return
    s = login_states[uid]

    # --- login3: استقبال string session ---
    if s['step'] == 'session_string':
        try:
            # اختبار سريع للجلسة
            temp = TelegramClient(StringSession(text), 1, "x")
            await temp.connect()
            await temp.disconnect()
        except:
            await update.message.reply_text("❌ الجلسة غير صالحة، تأكد من نسخها كاملة.")
            return
        db.set(uid, {
            'api_id': enc('1'),
            'api_hash': enc('x'),
            'phone': enc('مستورد'),
            'session': enc(text),
            'saved_at': datetime.now().isoformat()
        })
        try:
            me = await TelegramClient(StringSession(text), 1, "x").get_me()
            await update.message.reply_text(f"✅ تم استيراد الجلسة!\n👤 {me.first_name}\n📱 {me.phone}\n🚀 /run")
        except:
            await update.message.reply_text("✅ مخزنة، لكن تأكد منها. /run")
        del login_states[uid]
        return

    # --- login العادي ---
    if s['step'] == 'api_id':
        try:
            s['api_id'] = int(text); s['step'] = 'api_hash'
            await update.message.reply_text("✅ الخطوة 2: أرسل API_HASH")
        except: await update.message.reply_text("❌ رقم غير صحيح")

    elif s['step'] == 'api_hash':
        s['api_hash'] = text; s['step'] = 'phone'
        await update.message.reply_text("✅ الخطوة 3: رقم الهاتف (+2012...)")

    elif s['step'] == 'phone':
        if not text.startswith('+'): return await update.message.reply_text("❌ يجب أن يبدأ بـ +")
        s['phone'] = text
        try:
            c = TelegramClient(StringSession(), s['api_id'], s['api_hash'])
            await c.connect()
            sent = await c.send_code_request(text)
            s['c'] = c; s['phone_code_hash'] = sent.phone_code_hash
            s['step'] = 'code'; s['code_attempts'] = 0
            await update.message.reply_text("✅ تم إرسال الكود. أرسله هنا.\n⚠️ إن لم يصلك، استخدم /login3")
        except Exception as e:
            logger.error(f"send code: {e}")
            await update.message.reply_text(f"❌ فشل: {e}\n💡 استخدم /login3 بدلاً من ذلك.")
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
                await update.message.reply_text("❌ فشل متكرر. استخدم /login3.")
                try: await s['c'].disconnect()
                except: pass
                del login_states[uid]
                return
            try:
                sent = await s['c'].send_code_request(s['phone'])
                s['phone_code_hash'] = sent.phone_code_hash
                await update.message.reply_text("🔄 كود جديد أرسل.")
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
    await update.message.reply_text(f"✅ تم! {me.first_name}\n🚀 /run")
    await s['c'].disconnect()
    del login_states[uid]

# ==================== تشغيل ====================
def main():
    print("🚀 البوت")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gen_session", gen_session))
    app.add_handler(CommandHandler("login3", login3))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("run", run))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("logout", logout))
    app.add_handler(CommandHandler("logs", logs_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ شغال")
    app.run_polling()

if __name__ == "__main__":
    main()
