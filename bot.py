#!/usr/bin/env python3
"""
بوت تليجرام متعدد المهام - مع حفظ الجلسات الدائمة
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
from datetime import datetime
from pathlib import Path
from telethon import TelegramClient, events, types
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeVideo, DocumentAttributeAudio
from cryptography.fernet import Fernet
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from deep_translator import GoogleTranslator
import yt_dlp
import speedtest
import requests

# ==================== الإعدادات ====================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = "8879863328:AAH_PB_1i50hIyU-UI58TcD-dflHl4dBFqo"

# ==================== التشفير ====================

def get_key():
    """الحصول على مفتاح التشفير أو إنشاء واحد وحفظه"""
    key_file = Path("data/encryption_key.txt")
    
    # لو المفتاح موجود في ملف، نستخدمه
    if key_file.exists():
        return key_file.read_text().strip().encode()
    
    # لو موجود في متغيرات البيئة
    key = os.environ.get("ENCRYPTION_KEY", "")
    if key:
        try:
            Fernet(key.encode())
            return key.encode()
        except:
            pass
    
    # إنشاء مفتاح جديد وحفظه
    Path("data").mkdir(parents=True, exist_ok=True)
    new_key = Fernet.generate_key()
    key_file.write_text(new_key.decode())
    return new_key

cipher = Fernet(get_key())

def enc(t): return cipher.encrypt(t.encode()).decode() if t else None
def dec(t): return cipher.decrypt(t.encode()).decode() if t else None

# ==================== قاعدة بيانات بسيطة ====================

class SessionDB:
    """قاعدة بيانات بسيطة لحفظ الجلسات"""
    
    def __init__(self, filepath="data/sessions.json"):
        self.filepath = Path(filepath)
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()
    
    def _load(self):
        """تحميل البيانات من الملف"""
        if self.filepath.exists():
            try:
                return json.loads(self.filepath.read_text())
            except:
                return {}
        return {}
    
    def _save(self):
        """حفظ البيانات للملف"""
        self.filepath.write_text(json.dumps(self.data, indent=2))
    
    def get(self, user_id):
        """استرجاع بيانات مستخدم"""
        return self.data.get(str(user_id))
    
    def set(self, user_id, data):
        """حفظ بيانات مستخدم"""
        self.data[str(user_id)] = data
        self._save()
    
    def delete(self, user_id):
        """حذف بيانات مستخدم"""
        if str(user_id) in self.data:
            del self.data[str(user_id)]
            self._save()
    
    def get_all(self):
        """استرجاع كل المستخدمين"""
        return self.data

# تهيئة قاعدة البيانات
db = SessionDB()

# ==================== تخزين مؤقت ====================

active_bots = {}
login_states = {}

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

# ==================== أوامر البوت ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب"""
    uid = update.effective_user.id
    user_data = db.get(uid)
    
    status_text = ""
    if user_data:
        status_text = "\n✅ **أنت مسجل دخول!**\n🚀 استخدم /run لتشغيل البوت"
    
    await update.message.reply_text(f"""
👋 **مرحباً بك في البوت الخارق!**{status_text}

📋 **الأوامر الأساسية:**
/login - تسجيل الدخول
/run - تشغيل اليوزربوت
/stop - إيقاف اليوزربوت
/status - حالة الجلسة

🎯 **الأوامر المتقدمة:**
.ترجم - ترجمة (رد على رسالة)
.صوت - تحويل فيديو لصوت
.تحويل - تحويل صورة لستيكر والعكس
.بنغ - قياس سرعة النت
.يوت + اسم - تحميل صوت من يوتيوب

🛠️ /logout - /cancel - /help
""")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""
📚 **شرح الأوامر:**

1️⃣ **.ترجم** - رد على رسالة للترجمة (عربي↔إنجليزي)
2️⃣ **.صوت** - رد على فيديو لتحويله لـ MP3
3️⃣ **.تحويل** - صورة↔ستيكر (رد على الوسائط)
4️⃣ **.بنغ** - قياس سرعة الإنترنت الحقيقية
5️⃣ **.يوت اغنية** - تحميل الصوت من يوتيوب

💾 **الجلسات محفوظة تلقائياً!**
حتى لو البوت اتحدث، بياناتك هتفضل موجودة.
""")

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تسجيل الدخول"""
    uid = update.effective_user.id
    user_data = db.get(uid)
    
    if user_data:
        await update.message.reply_text(
            "✅ أنت مسجل دخول بالفعل!\n"
            "🔄 استخدم /logout لو عايز تسجل بحساب تاني."
        )
        return
    
    login_states[uid] = {'step': 'api_id'}
    await update.message.reply_text(
        "📱 **الخطوة 1/4**\nأرسل API_ID من my.telegram.org"
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
        await update.message.reply_text("لا توجد عملية جارية")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حالة الجلسة"""
    uid = update.effective_user.id
    user_data = db.get(uid)
    
    if user_data and uid in active_bots:
        await update.message.reply_text("🟢 **مسجل دخول والبوت شغال** ✅")
    elif user_data:
        await update.message.reply_text("🟡 **مسجل دخول والبوت متوقف** ⏸️\n🚀 استخدم /run للتشغيل")
    else:
        await update.message.reply_text("🔴 **غير مسجل دخول** ❌\n📱 استخدم /login")

async def run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تشغيل اليوزربوت"""
    uid = update.effective_user.id
    user_data = db.get(uid)
    
    if not user_data:
        await update.message.reply_text("❌ سجل دخول أولاً: /login")
        return
    
    if uid in active_bots:
        await update.message.reply_text("✅ البوت شغال بالفعل!")
        return
    
    try:
        # فك تشفير البيانات
        api_id = int(dec(user_data['api_id']))
        api_hash = dec(user_data['api_hash'])
        session_str = dec(user_data['session'])
        
        # إنشاء عميل جديد
        client = TelegramClient(StringSession(session_str), api_id, api_hash)
        await client.start()
        
        # ========== الأوامر ==========
        
        @client.on(events.NewMessage(pattern=r'\.بنغ|\.ping'))
        async def ping_handler(event):
            await event.edit("📡 **جاري قياس السرعة...**")
            try:
                st = speedtest.Speedtest()
                st.get_best_server()
                download_speed = st.download() / 1_000_000
                upload_speed = st.upload() / 1_000_000
                ping = st.results.ping
                
                result = f"""
🏓 **نتائج قياس السرعة:**

📥 **التحميل:** {download_speed:.2f} Mbps
📤 **الرفع:** {upload_speed:.2f} Mbps
🕐 **البنج:** {ping:.0f} ms
🌐 **السيرفر:** {st.results.server['sponsor']}
"""
                await event.edit(result)
            except Exception as e:
                await event.edit(f"❌ خطأ: {e}")
        
        @client.on(events.NewMessage(pattern=r'\.ترجم'))
        async def translate_handler(event):
            reply = await event.get_reply_message()
            if not reply or not reply.text:
                await event.reply("❌ استخدم الأمر كرد على رسالة")
                return
            
            await event.edit("🔄 **جاري الترجمة...**")
            
            try:
                text = reply.text
                lang = detect_language(text)
                
                if lang == 'ar':
                    result_text = translate_text(text, target='en')
                    result = f"🇬🇧 **الترجمة للإنجليزية:**\n\n{result_text}"
                else:
                    result_text = translate_text(text, target='ar')
                    result = f"🇸🇦 **الترجمة للعربية:**\n\n{result_text}"
                
                await event.edit(result)
            except Exception as e:
                await event.edit(f"❌ خطأ: {e}")
        
        @client.on(events.NewMessage(pattern=r'\.صوت'))
        async def audio_extract(event):
            reply = await event.get_reply_message()
            if not reply or not reply.video:
                await event.reply("❌ استخدم الأمر كرد على فيديو")
                return
            
            await event.edit("🎵 **جاري استخراج الصوت...**")
            
            try:
                video_path = await reply.download_media()
                audio_path = video_path.rsplit('.', 1)[0] + '.mp3'
                
                try:
                    cmd = f'ffmpeg -i "{video_path}" -q:a 0 -map a "{audio_path}" -y'
                    subprocess.run(cmd, shell=True, check=True, capture_output=True)
                    await event.client.send_file(event.chat_id, audio_path, reply_to=reply.id, caption="🎵 تم استخراج الصوت!")
                    os.remove(audio_path)
                except:
                    await event.client.send_file(event.chat_id, video_path, reply_to=reply.id, caption="⚠️ ffmpeg غير متوفر")
                
                os.remove(video_path)
                await event.delete()
            except Exception as e:
                await event.edit(f"❌ خطأ: {e}")
        
        @client.on(events.NewMessage(pattern=r'\.تحويل'))
        async def convert_media(event):
            reply = await event.get_reply_message()
            if not reply or not reply.media:
                await event.reply("❌ استخدم الأمر كرد على صورة أو ستيكر")
                return
            
            await event.edit("🔄 **جاري التحويل...**")
            
            try:
                file_path = await reply.download_media()
                
                if reply.sticker:
                    await event.client.send_file(event.chat_id, file_path, reply_to=reply.id)
                elif reply.photo:
                    await event.client.send_file(event.chat_id, file_path, force_document=False, reply_to=reply.id)
                elif reply.video:
                    gif_path = file_path.rsplit('.', 1)[0] + '.gif'
                    try:
                        cmd = f'ffmpeg -i "{file_path}" -vf "fps=10,scale=320:-1:flags=lanczos" "{gif_path}" -y'
                        subprocess.run(cmd, shell=True, check=True, capture_output=True)
                        await event.client.send_file(event.chat_id, gif_path, reply_to=reply.id)
                        os.remove(gif_path)
                    except:
                        await event.client.send_file(event.chat_id, file_path, reply_to=reply.id)
                
                os.remove(file_path)
                await event.delete()
            except Exception as e:
                await event.edit(f"❌ خطأ: {e}")
        
        @client.on(events.NewMessage(pattern=r'\.يوت (.+)'))
        async def youtube_download(event):
            query = event.pattern_match.group(1)
            await event.edit(f"🔍 **جاري البحث عن:** {query}")
            
            try:
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
                    'outtmpl': '%(title)s.%(ext)s',
                    'quiet': True,
                    'no_warnings': True,
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    await event.edit("📥 **جاري التحميل...**")
                    info = ydl.extract_info(f"ytsearch:{query}", download=True)['entries'][0]
                    
                    title = info['title']
                    duration = info['duration']
                    uploader = info['uploader']
                    mp3_path = f"{title}.mp3"
                    
                    if os.path.exists(mp3_path):
                        await event.edit("📤 **جاري الرفع...**")
                        await event.client.send_file(
                            event.chat_id,
                            mp3_path,
                            caption=f"🎵 **{title}**\n👤 {uploader}\n⏱️ {duration//60}:{duration%60:02d}",
                            attributes=[DocumentAttributeAudio(duration=duration, title=title, performer=uploader)]
                        )
                        os.remove(mp3_path)
                        await event.delete()
                    else:
                        await event.edit("❌ لم يتم العثور على الملف")
            except Exception as e:
                await event.edit(f"❌ خطأ: {str(e)[:200]}")
        
        active_bots[uid] = client
        await update.message.reply_text("✅ **تم تشغيل البوت بجميع الميزات!**\n💾 الجلسة محفوظة تلقائياً")
        
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إيقاف اليوزربوت"""
    uid = update.effective_user.id
    if uid in active_bots:
        await active_bots[uid].disconnect()
        del active_bots[uid]
        await update.message.reply_text("✅ تم إيقاف البوت")
    else:
        await update.message.reply_text("البوت متوقف بالفعل")

async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تسجيل الخروج"""
    uid = update.effective_user.id
    if uid in active_bots:
        try: await active_bots[uid].disconnect()
        except: pass
        del active_bots[uid]
    
    db.delete(uid)
    await update.message.reply_text("✅ تم تسجيل الخروج وحذف الجلسة")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة خطوات تسجيل الدخول"""
    uid = update.effective_user.id
    text = update.message.text
    
    if uid not in login_states:
        return
    
    s = login_states[uid]
    
    if s['step'] == 'api_id':
        try:
            s['api_id'] = int(text)
            s['step'] = 'api_hash'
            await update.message.reply_text("✅ **الخطوة 2/4**\nأرسل API_HASH:")
        except:
            await update.message.reply_text("❌ رقم خطأ")
    
    elif s['step'] == 'api_hash':
        s['api_hash'] = text
        s['step'] = 'phone'
        await update.message.reply_text("✅ **الخطوة 3/4**\nأرسل رقم الهاتف:\nمثال: +201234567890")
    
    elif s['step'] == 'phone':
        if not text.startswith('+'):
            await update.message.reply_text("❌ لازم يبدأ بـ +")
            return
        s['phone'] = text
        try:
            c = TelegramClient(StringSession(), s['api_id'], s['api_hash'])
            await c.connect()
            code = await c.send_code_request(text)
            s['c'] = c
            s['hash'] = code.phone_code_hash
            s['step'] = 'code'
            await update.message.reply_text("✅ **الخطوة 4/4**\nتم إرسال الكود. أرسله هنا:")
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ: {e}")
            del login_states[uid]
    
    elif s['step'] == 'code':
        try:
            await s['c'].sign_in(phone=s['phone'], code=text, phone_code_hash=s['hash'])
            await finish_login(update, s)
        except SessionPasswordNeededError:
            s['step'] = 'pass'
            await update.message.reply_text("🔒 تحقق بخطوتين. أرسل كلمة المرور:")
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ: {e}")
    
    elif s['step'] == 'pass':
        try:
            await s['c'].sign_in(password=text)
            await finish_login(update, s)
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ: {e}")

async def finish_login(update: Update, s):
    """إكمال تسجيل الدخول وحفظ الجلسة"""
    uid = update.effective_user.id
    try:
        session_string = s['c'].session.save()
        
        # حفظ مشفر في قاعدة البيانات
        db.set(uid, {
            'api_id': enc(str(s['api_id'])),
            'api_hash': enc(s['api_hash']),
            'phone': enc(s['phone']),
            'session': enc(session_string),
            'saved_at': datetime.now().isoformat()
        })
        
        me = await s['c'].get_me()
        await update.message.reply_text(
            f"✅ **تم تسجيل الدخول بنجاح!**\n\n"
            f"👤 الاسم: {me.first_name}\n"
            f"📱 الهاتف: {me.phone}\n\n"
            f"💾 **الجلسة محفوظة تلقائياً**\n"
            f"حتى لو البوت اتحدث، بياناتك هتفضل موجودة!\n\n"
            f"🚀 استخدم /run للتشغيل"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ في الحفظ: {e}")
    finally:
        try: await s['c'].disconnect()
        except: pass
        del login_states[uid]

# ==================== تشغيل ====================

def main():
    """تشغيل البوت مع استعادة الجلسات السابقة"""
    print("=" * 50)
    print("🚀 جاري تشغيل البوت...")
    
    # استعادة الجلسات المحفوظة
    all_sessions = db.get_all()
    print(f"💾 تم تحميل {len(all_sessions)} جلسة محفوظة")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("run", run))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("logout", logout))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ البوت الخارق شغال!")
    print("💾 نظام حفظ الجلسات مفعل")
    print("=" * 50)
    
    app.run_polling()

if __name__ == "__main__":
    main()


