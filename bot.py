#!/usr/bin/env python3
"""
بوت تليجرام متعدد المهام - إصلاح مشكلة إرسال الكود
"""

import os
import sys
import asyncio
import logging
import json
import time
import io
import re
import subprocess
import traceback
from datetime import datetime
from pathlib import Path
from telethon import TelegramClient, events, types, errors
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeVideo, DocumentAttributeAudio, DocumentAttributeFilename
from cryptography.fernet import Fernet
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from deep_translator import GoogleTranslator
import yt_dlp
import speedtest
import requests

# ==================== مجلد البيانات ====================
Path("data").mkdir(parents=True, exist_ok=True)

# ==================== الإعدادات ====================
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
    key = os.environ.get("ENCRYPTION_KEY", "")
    if key:
        try:
            Fernet(key.encode())
            return key.encode()
        except:
            pass
    key_file = Path("data/encryption_key.txt")
    if key_file.exists():
        return key_file.read_text().strip().encode()
    new_key = Fernet.generate_key()
    key_file.write_text(new_key.decode())
    return new_key

cipher = Fernet(get_key())

def enc(t): return cipher.encrypt(t.encode()).decode() if t else None
def dec(t): return cipher.decrypt(t.encode()).decode() if t else None

# ==================== قاعدة البيانات ====================

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
    
    def get(self, user_id):
        return self.data.get(str(user_id))
    
    def set(self, user_id, data):
        self.data[str(user_id)] = data
        self._save()
    
    def delete(self, user_id):
        if str(user_id) in self.data:
            del self.data[str(user_id)]
            self._save()
    
    def get_all(self):
        return self.data

db = SessionDB()
active_bots = {}
login_states = {}
session_locks = {}

# ==================== المترجم ====================

def detect_language(text):
    arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
    return 'ar' if arabic_chars > len(text) * 0.3 else 'en'

def translate_text(text, source='auto', target='en'):
    try:
        if target == 'en':
            return GoogleTranslator(source='ar', target='en').translate(text)
        else:
            return GoogleTranslator(source='en', target='ar').translate(text)
    except:
        try:
            return GoogleTranslator(source='auto', target=target).translate(text)
        except Exception as e:
            return f"❌ خطأ: {e}"

# ==================== تحليل الأخطاء ====================

def analyze_session_error(error):
    error_name = type(error).__name__
    error_msg = str(error)
    
    analysis = {
        'error_type': error_name,
        'message': error_msg,
        'solution': '',
        'severity': 'unknown'
    }
    
    if isinstance(error, errors.rpcerrorlist.AuthKeyUnregisteredError):
        analysis['solution'] = "🔑 الجلسة انتهت - /logout ثم /login"
        analysis['severity'] = 'critical'
    elif isinstance(error, errors.rpcerrorlist.AuthKeyDuplicatedError):
        analysis['solution'] = "👥 جلسة مكررة - /stop ثم /run"
        analysis['severity'] = 'critical'
    elif isinstance(error, errors.rpcerrorlist.SessionRevokedError):
        analysis['solution'] = "🚫 الجلسة اتلغت - /logout ثم /login"
        analysis['severity'] = 'critical'
    elif isinstance(error, errors.rpcerrorlist.UserDeactivatedBanError):
        analysis['solution'] = "⛔ الحساب محظور"
        analysis['severity'] = 'fatal'
    elif isinstance(error, errors.rpcerrorlist.PhoneNumberBannedError):
        analysis['solution'] = "📵 الرقم محظور"
        analysis['severity'] = 'fatal'
    elif isinstance(error, errors.rpcerrorlist.FloodWaitError):
        seconds = getattr(error, 'seconds', 0)
        analysis['solution'] = f"⏳ استنى {seconds} ثانية"
        analysis['severity'] = 'warning'
    else:
        analysis['solution'] = f"❓ خطأ: {error_msg[:100]}"
        analysis['severity'] = 'unknown'
    
    return analysis

# ==================== أوامر البوت ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_data = db.get(uid)
    
    status_text = ""
    if user_data:
        status_text = "\n✅ **مسجل دخول!**\n🚀 /run للتشغيل"
    
    await update.message.reply_text(f"""
👋 **أهلاً بيك!**{status_text}

📋 **الأوامر:**
/login - تسجيل الدخول
/run - تشغيل اليوزربوت
/stop - إيقاف اليوزربوت
/status - حالة الجلسة
/logout - تسجيل الخروج
/logs - السجلات
/cancel - إلغاء

🎯 **الميزات:**
.ترجم - .صوت - .تحويل
.بنغ - .يوت - .نص
""")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""
📚 **شرح الأوامر:**
1. .ترجم - رد على رسالة للترجمة
2. .صوت - رد على فيديو لـ MP3
3. .تحويل - صورة↔ستيكر
4. .بنغ - سرعة النت
5. .يوت اسم - تحميل من يوتيوب
6. .نص - صوت لنص
""")

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    
    if db.get(uid):
        await update.message.reply_text("✅ مسجل دخول!\n🔄 /logout لو عايز تغير")
        return
    
    login_states[uid] = {'step': 'api_id'}
    await update.message.reply_text(
        "📱 **تسجيل الدخول - الخطوة 1/3**\n\n"
        "أرسل API_ID و API_HASH في رسالة واحدة\n"
        "مفصولين بمسافة:\n\n"
        "مثال:\n"
        "123456 a1b2c3d4e5f6...\n\n"
        "احصل عليهم من: my.telegram.org"
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in login_states:
        if 'c' in login_states[uid]:
            try: await login_states[uid]['c'].disconnect()
            except: pass
        del login_states[uid]
        await update.message.reply_text("✅ تم الإلغاء")
    else:
        await update.message.reply_text("لا توجد عملية")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_data = db.get(uid)
    
    if user_data and uid in active_bots:
        client = active_bots[uid]
        is_connected = client.is_connected()
        icon = "🟢" if is_connected else "🟠"
        txt = "متصل" if is_connected else "منفصل"
        await update.message.reply_text(f"{icon} **شغال** ({txt}) ✅")
    elif user_data:
        await update.message.reply_text("🟡 **متوقف** ⏸️\n🚀 /run")
    else:
        await update.message.reply_text("🔴 **غير مسجل** ❌\n📱 /login")

async def logs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_file = Path("data/session_errors.log")
    if log_file.exists():
        try:
            lines = log_file.read_text(encoding='utf-8').splitlines()
            last = lines[-15:] if len(lines) > 15 else lines
            txt = "\n".join(last)
            if txt.strip():
                await update.message.reply_text(f"📋 **آخر السجلات:**\n```\n{txt[:3000]}\n```")
            else:
                await update.message.reply_text("📋 فاضي")
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")
    else:
        await update.message.reply_text("📋 مفيش سجلات")

async def run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_data = db.get(uid)
    
    if not user_data:
        await update.message.reply_text("❌ سجل دخول: /login")
        return
    
    if uid in active_bots:
        await update.message.reply_text("✅ شغال!")
        return
    
    if uid in session_locks:
        await update.message.reply_text("⏳ استنى...")
        return
    
    session_locks[uid] = True
    msg = await update.message.reply_text("🔄 **جاري التشغيل...**")
    
    try:
        api_id = int(dec(user_data['api_id']))
        api_hash = dec(user_data['api_hash'])
        session_str = dec(user_data['session'])
        
        client = TelegramClient(StringSession(session_str), api_id, api_hash)
        
        try:
            await client.start()
        except errors.rpcerrorlist.AuthKeyUnregisteredError:
            await msg.edit_text("❌ الجلسة انتهت - /logout ثم /login")
            db.delete(uid)
            return
        except errors.rpcerrorlist.AuthKeyDuplicatedError:
            await msg.edit_text("❌ جلسة مكررة - /stop ثم /run")
            return
        except errors.rpcerrorlist.SessionRevokedError:
            await msg.edit_text("❌ الجلسة اتلغت - /logout ثم /login")
            db.delete(uid)
            return
        except Exception as e:
            await msg.edit_text(f"❌ فشل: {e}")
            return
        
        me = await client.get_me()
        
        # الأوامر
        @client.on(events.NewMessage(pattern=r'\.بنغ|\.ping'))
        async def ping_handler(event):
            try:
                await event.edit("📡 **قياس...**")
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
                await event.reply("❌ رد على رسالة")
                return
            await event.edit("🔄 **ترجمة...**")
            try:
                text = reply.text
                lang = detect_language(text)
                if lang == 'ar':
                    result = translate_text(text, target='en')
                    await event.edit(f"🇬🇧 {result}")
                else:
                    result = translate_text(text, target='ar')
                    await event.edit(f"🇸🇦 {result}")
            except Exception as e:
                await event.edit(f"❌ {e}")

        @client.on(events.NewMessage(pattern=r'\.صوت'))
        async def audio_extract(event):
            reply = await event.get_reply_message()
            if not reply or (not reply.video and not reply.document):
                await event.reply("❌ رد على فيديو")
                return
            await event.edit("🎵 **معالجة...**")
            try:
                path = await reply.download_media()
                await event.client.send_file(event.chat_id, path, reply_to=reply.id, caption="🎵 تم!", force_document=False)
                os.remove(path)
                await event.delete()
            except Exception as e:
                await event.edit(f"❌ {e}")

        @client.on(events.NewMessage(pattern=r'\.نص'))
        async def speech_to_text(event):
            reply = await event.get_reply_message()
            if not reply or (not reply.voice and not reply.audio):
                await event.reply("❌ رد على صوتية")
                return
            await event.edit("🎙️ **استخراج...**")
            try:
                path = await reply.download_media()
                try:
                    result = await client.transcribe_voice(event.chat_id, reply.id)
                    if result:
                        await event.edit(f"📝 {result}")
                    else:
                        raise Exception("No result")
                except:
                    await event.edit("⚠️ استخدم زر Aa في تيليجرام بريميوم")
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                await event.edit(f"❌ {e}")

        @client.on(events.NewMessage(pattern=r'\.تحويل'))
        async def convert_media(event):
            reply = await event.get_reply_message()
            if not reply or not reply.media:
                await event.reply("❌ رد على صورة/ستيكر")
                return
            await event.edit("🔄 **تحويل...**")
            try:
                path = await reply.download_media()
                await event.client.send_file(event.chat_id, path, reply_to=reply.id, caption="✅ تم!")
                if os.path.exists(path):
                    os.remove(path)
                await event.delete()
            except Exception as e:
                await event.edit(f"❌ {e}")

        @client.on(events.NewMessage(pattern=r'\.يوت (.+)'))
        async def youtube_download(event):
            query = event.pattern_match.group(1)
            await event.edit(f"🔍 **بحث:** {query}")
            try:
                ydl_opts = {'format': 'bestaudio[ext=m4a]/bestaudio/best', 'outtmpl': '%(title)s.%(ext)s', 'quiet': True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    await event.edit("📥 **تحميل...**")
                    info = ydl.extract_info(f"ytsearch:{query}", download=True)['entries'][0]
                    title = info['title']
                    dur = info['duration']
                    uploader = info['uploader']
                    for f in Path().glob(f"{title}.*"):
                        if f.exists():
                            await event.edit("📤 **رفع...**")
                            await event.client.send_file(
                                event.chat_id, str(f),
                                caption=f"🎵 {title}\n👤 {uploader}\n⏱️ {dur//60}:{dur%60:02d}",
                                attributes=[DocumentAttributeAudio(duration=dur, title=title, performer=uploader), DocumentAttributeFilename(f.name)]
                            )
                            os.remove(str(f))
                            await event.delete()
                            return
                    await event.edit("❌ مش لاقي")
            except Exception as e:
                await event.edit(f"❌ {str(e)[:200]}")

        # مراقبة الاتصال
        async def keep_alive():
            while uid in active_bots:
                await asyncio.sleep(30)
                try:
                    if uid in active_bots:
                        client = active_bots[uid]
                        if not client.is_connected():
                            try:
                                await client.connect()
                            except:
                                pass
                except:
                    pass
        
        asyncio.ensure_future(keep_alive())
        active_bots[uid] = client
        
        await msg.edit_text(f"✅ **شغال!**\n👤 {me.first_name}\n📱 {me.phone}")
        
    except Exception as e:
        await msg.edit_text(f"❌ فشل: {e}")
    finally:
        if uid in session_locks:
            del session_locks[uid]

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in active_bots:
        try:
            await active_bots[uid].disconnect()
        except:
            pass
        del active_bots[uid]
        await update.message.reply_text("✅ تم الإيقاف")
    else:
        await update.message.reply_text("متوقف")

async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in active_bots:
        try:
            await active_bots[uid].disconnect()
        except:
            pass
        del active_bots[uid]
    db.delete(uid)
    await update.message.reply_text("✅ تم الخروج")

# ==================== معالج الرسائل - تسجيل الدخول المبسط ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    
    if uid not in login_states:
        return
    
    s = login_states[uid]
    
    # الخطوة 1: استقبال api_id و api_hash مع بعض
    if s['step'] == 'api_id':
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text(
                "❌ **أرسل القيمتين مع بعض**\n\n"
                "api_id وبعده api_hash\n"
                "مفصولين بمسافة:\n\n"
                "مثال: 123456 a1b2c3d4e5f6"
            )
            return
        
        try:
            api_id = int(parts[0])
            api_hash = parts[1]
            
            s['api_id'] = api_id
            s['api_hash'] = api_hash
            s['step'] = 'phone'
            
            await update.message.reply_text(
                "✅ **تم استلام API**\n\n"
                "📱 **الخطوة 2/3**\n"
                "أرسل رقم الهاتف:\n"
                "مثال: +201234567890"
            )
        except:
            await update.message.reply_text("❌ api_id لازم يكون رقم")
    
    # الخطوة 2: استقبال رقم الهاتف وإرسال الكود
    elif s['step'] == 'phone':
        if not text.startswith('+'):
            await update.message.reply_text("❌ لازم يبدأ بـ +")
            return
        
        s['phone'] = text
        status_msg = await update.message.reply_text("🔄 **جاري إرسال الكود...**")
        
        try:
            # ✨ الأهم: إنشاء العميل وإرسال الكود
            c = TelegramClient(StringSession(), s['api_id'], s['api_hash'])
            await c.connect()
            
            # ✨ إرسال الكود
            sent_code = await c.send_code_request(text)
            
            s['c'] = c
            s['phone_code_hash'] = sent_code.phone_code_hash
            s['step'] = 'code'
            
            await status_msg.edit_text(
                "✅ **الخطوة 3/3**\n\n"
                "📱 تم إرسال الكود إلى:\n"
                f"**{text}**\n\n"
                "📨 شوف تيليجرام أو رسايل SMS\n"
                "⏰ الكود صالح 5 دقائق\n\n"
                "أرسل الكود هنا:"
            )
            
        except errors.rpcerrorlist.FloodWaitError as e:
            await status_msg.edit_text(f"⏳ استنى {e.seconds} ثانية\nثم /login")
            if 'c' in s:
                try: await s['c'].disconnect()
                except: pass
            del login_states[uid]
        except Exception as e:
            error_msg = str(e)
            logger.error(f"خطأ إرسال الكود: {error_msg}")
            
            if 'PHONE_NUMBER_INVALID' in error_msg:
                await status_msg.edit_text("❌ رقم الهاتف غير صحيح\nتأكد من الصيغة: +201234567890")
            elif 'PHONE_PASSWORD_FLOOD' in error_msg:
                await status_msg.edit_text("⏳ محاولات كتير - استنى شوية")
            elif 'API_ID_INVALID' in error_msg:
                await status_msg.edit_text("❌ api_id غير صحيح\nتأكد من my.telegram.org")
            elif 'API_ID_PUBLISHED_FLOOD' in error_msg:
                await status_msg.edit_text("❌ الـ api_id منتشر - استخدم واحد جديد")
            else:
                await status_msg.edit_text(f"❌ خطأ:\n{error_msg[:200]}\n\nتأكد من:\n• api_id و api_hash صح\n• الرقم صحيح\n\n🔄 /login للمحاولة")
            
            if 'c' in s:
                try: await s['c'].disconnect()
                except: pass
            del login_states[uid]
    
    # الخطوة 3: استقبال الكود
    elif s['step'] == 'code':
        status_msg = await update.message.reply_text("🔄 **جاري التحقق...**")
        
        try:
            await s['c'].sign_in(phone=s['phone'], code=text, phone_code_hash=s['phone_code_hash'])
            await status_msg.delete()
            await finish_login(update, s)
            
        except SessionPasswordNeededError:
            await status_msg.edit_text("🔒 تحقق بخطوتين - أرسل كلمة المرور:")
            s['step'] = 'pass'
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"خطأ الكود: {error_msg}")
            
            if 'expired' in error_msg.lower():
                await status_msg.edit_text(
                    "⏰ **الكود انتهى**\n\n"
                    "الكود اللي استخدمته قديم\n\n"
                    "🔄 استخدم /login من جديد\n"
                    "وهنبعت كود جديد"
                )
                try: await s['c'].disconnect()
                except: pass
                del login_states[uid]
            elif 'invalid' in error_msg.lower():
                await status_msg.edit_text(
                    "❌ **الكود غلط**\n\n"
                    "• تأكد من كتابة الكود صح\n"
                    "• استخدم أحدث كود وصلك\n\n"
                    "أرسل الكود الصحيح:"
                )
            else:
                await status_msg.edit_text(f"❌ خطأ: {error_msg[:150]}\nحاول تاني:")
    
    # الخطوة 4: كلمة المرور (التحقق بخطوتين)
    elif s['step'] == 'pass':
        try:
            await s['c'].sign_in(password=text)
            await finish_login(update, s)
        except Exception as e:
            await update.message.reply_text(f"❌ كلمة مرور غلط: {e}\nحاول تاني:")

async def finish_login(update: Update, s):
    uid = update.effective_user.id
    try:
        session_string = s['c'].session.save()
        
        db.set(uid, {
            'api_id': enc(str(s['api_id'])),
            'api_hash': enc(s['api_hash']),
            'phone': enc(s['phone']),
            'session': enc(session_string),
            'saved_at': datetime.now().isoformat()
        })
        
        me = await s['c'].get_me()
        await update.message.reply_text(
            f"✅ **تم بنجاح!**\n\n"
            f"👤 {me.first_name}\n"
            f"📱 {me.phone}\n\n"
            f"💾 الجلسة محفوظة\n"
            f"🚀 /run للتشغيل"
        )
        logger.info(f"✅ {uid} سجل دخول كـ {me.first_name}")
    except Exception as e:
        logger.error(f"خطأ حفظ {uid}: {e}")
        await update.message.reply_text(f"❌ {e}")
    finally:
        try: await s['c'].disconnect()
        except: pass
        del login_states[uid]

# ==================== تشغيل البوت ====================

def main():
    print("=" * 50)
    print("🚀 بوت تليجرام")
    print("=" * 50)
    
    Path("data").mkdir(parents=True, exist_ok=True)
    
    all_sessions = db.get_all()
    print(f"💾 {len(all_sessions)} جلسة")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("run", run))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("logout", logout))
    app.add_handler(CommandHandler("logs", logs_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ شغال!")
    print("=" * 50)
    
    app.run_polling()

if __name__ == "__main__":
    main()
