#!/usr/bin/env python3
"""
بوت تليجرام متعدد المهام - مع حفظ الجلسات الدائمة ونظام مراقبة الأخطاء
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

# ==================== الإعدادات ====================

# إعداد التسجيل المتقدم
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data/session_errors.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8879863328:AAH_PB_1i50hIyU-UI58TcD-dflHl4dBFqo"

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
    Path("data").mkdir(parents=True, exist_ok=True)
    new_key = Fernet.generate_key()
    key_file.write_text(new_key.decode())
    return new_key

cipher = Fernet(get_key())

def enc(t): return cipher.encrypt(t.encode()).decode() if t else None
def dec(t): return cipher.decrypt(t.encode()).decode() if t else None

# ==================== قاعدة بيانات بسيطة ====================

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

# ==================== دوال مساعدة لتحليل الأخطاء ====================

def analyze_session_error(error):
    """تحليل خطأ الجلسة وإرجاع رسالة توضيحية مع الحل"""
    error_name = type(error).__name__
    error_msg = str(error)
    
    analysis = {
        'error_type': error_name,
        'message': error_msg,
        'solution': '',
        'severity': 'unknown'
    }
    
    if isinstance(error, errors.rpcerrorlist.AuthKeyUnregisteredError):
        analysis['solution'] = (
            "🔑 **تم إلغاء مفتاح التشفير**\n\n"
            "الأسباب المحتملة:\n"
            "• تم تغيير كلمة المرور\n"
            "• تم طلب كود تفعيل جديد من جهاز آخر\n"
            "• تم تفعيل التحقق بخطوتين أو تغييره\n\n"
            "🛠️ **الحل:** استخدم /logout ثم /login للتسجيل من جديد"
        )
        analysis['severity'] = 'critical'
        
    elif isinstance(error, errors.rpcerrorlist.AuthKeyDuplicatedError):
        analysis['solution'] = (
            "👥 **تم اكتشاف جلسة مكررة**\n\n"
            "نفس الجلسة تم فتحها في مكان آخر.\n\n"
            "🛠️ **الحل:**\n"
            "• تأكد من عدم تشغيل البوت من مكان آخر\n"
            "• استخدم /stop ثم /run مرة واحدة فقط"
        )
        analysis['severity'] = 'critical'
        
    elif isinstance(error, errors.rpcerrorlist.SessionRevokedError):
        analysis['solution'] = (
            "🚫 **تم إبطال الجلسة بالكامل**\n\n"
            "السيرفر رفض الجلسة بشكل نهائي.\n\n"
            "🛠️ **الحل:** استخدم /logout ثم /login للتسجيل من جديد"
        )
        analysis['severity'] = 'critical'
        
    elif isinstance(error, errors.rpcerrorlist.UserDeactivatedBanError):
        analysis['solution'] = (
            "⛔ **الحساب محظور**\n\n"
            "تم تعطيل الحساب أو حظره.\n\n"
            "🛠️ **الحل:** راجع دعم تليجرام"
        )
        analysis['severity'] = 'fatal'
        
    elif isinstance(error, errors.rpcerrorlist.PhoneNumberBannedError):
        analysis['solution'] = (
            "📵 **رقم الهاتف محظور**\n\n"
            "🛠️ **الحل:** لا يمكن استخدام هذا الرقم حالياً"
        )
        analysis['severity'] = 'fatal'
        
    elif isinstance(error, errors.rpcerrorlist.FloodWaitError):
        seconds = getattr(error, 'seconds', 0)
        analysis['solution'] = (
            f"⏳ **انتظر {seconds} ثانية**\n\n"
            f"تم الوصول لحد الطلبات المسموح به.\n"
            f"🛠️ **الحل:** انتظر {seconds} ثانية ثم حاول مجدداً"
        )
        analysis['severity'] = 'warning'
        
    elif isinstance(error, asyncio.TimeoutError):
        analysis['solution'] = (
            "⏱️ **انتهت مهلة الاتصال**\n\n"
            "🛠️ **الحل:** تحقق من اتصالك بالإنترنت وحاول مجدداً"
        )
        analysis['severity'] = 'warning'
        
    elif isinstance(error, ConnectionError):
        analysis['solution'] = (
            "🔌 **خطأ في الاتصال**\n\n"
            "🛠️ **الحل:** تحقق من اتصالك بالإنترنت"
        )
        analysis['severity'] = 'warning'
        
    else:
        analysis['solution'] = (
            f"❓ **خطأ غير معروف:** {error_name}\n\n"
            f"الرسالة: {error_msg}\n\n"
            f"🛠️ **الحل:** حاول إعادة التشغيل بـ /stop ثم /run"
        )
        analysis['severity'] = 'unknown'
    
    return analysis

# ==================== أوامر البوت ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
/logs - عرض آخر الأخطاء

🎯 **الأوامر المتقدمة:**
.ترجم - ترجمة (رد على رسالة)
.صوت - تحويل فيديو لصوت
.تحويل - تحويل صورة لستيكر والعكس
.بنغ - قياس سرعة النت
.يوت + اسم - تحميل صوت من يوتيوب
.نص - استخراج النص من الصوت

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
6️⃣ **.نص** - استخراج النص من رسالة صوتية

💾 **الجلسات محفوظة تلقائياً!**
🛡️ **نظام مراقبة الأخطاء نشط**
""")

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_data = db.get(uid)
    
    if user_data:
        await update.message.reply_text("✅ أنت مسجل دخول بالفعل!\n🔄 استخدم /logout لو عايز تسجل بحساب تاني.")
        return
    
    login_states[uid] = {'step': 'api_id'}
    await update.message.reply_text("📱 **الخطوة 1/4**\nأرسل API_ID من my.telegram.org")

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
    uid = update.effective_user.id
    user_data = db.get(uid)
    
    if user_data and uid in active_bots:
        client = active_bots[uid]
        is_connected = client.is_connected()
        status_icon = "🟢" if is_connected else "🟠"
        status_text = "متصل" if is_connected else "غير متصل"
        await update.message.reply_text(f"{status_icon} **مسجل دخول والبوت شغال** ({status_text}) ✅")
    elif user_data:
        await update.message.reply_text("🟡 **مسجل دخول والبوت متوقف** ⏸️\n🚀 استخدم /run للتشغيل")
    else:
        await update.message.reply_text("🔴 **غير مسجل دخول** ❌\n📱 استخدم /login")

async def logs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض آخر الأخطاء المسجلة"""
    log_file = Path("data/session_errors.log")
    if log_file.exists():
        try:
            lines = log_file.read_text(encoding='utf-8').splitlines()
            last_lines = lines[-20:] if len(lines) > 20 else lines
            log_text = "\n".join(last_lines)
            if log_text.strip():
                await update.message.reply_text(f"📋 **آخر السجلات:**\n\n```\n{log_text[:3500]}\n```")
            else:
                await update.message.reply_text("📋 لا توجد سجلات بعد")
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ في قراءة السجلات: {e}")
    else:
        await update.message.reply_text("📋 لا توجد سجلات بعد")

async def run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_data = db.get(uid)
    
    if not user_data:
        await update.message.reply_text("❌ سجل دخول أولاً: /login")
        return
    
    if uid in active_bots:
        await update.message.reply_text("✅ البوت شغال بالفعل!")
        return
    
    status_msg = await update.message.reply_text("🔄 **جاري تشغيل البوت...**")
    
    try:
        api_id = int(dec(user_data['api_id']))
        api_hash = dec(user_data['api_hash'])
        session_str = dec(user_data['session'])
        
        # إنشاء العميل مع معالجة الأخطاء
        try:
            client = TelegramClient(StringSession(session_str), api_id, api_hash)
            await client.start()
        except errors.rpcerrorlist.AuthKeyUnregisteredError as e:
            analysis = analyze_session_error(e)
            logger.error(f"AuthKeyUnregistered for user {uid}: {e}")
            await status_msg.edit_text(
                f"❌ **انتهت صلاحية الجلسة**\n\n"
                f"{analysis['solution']}\n\n"
                f"📝 الخطأ: `{analysis['error_type']}`"
            )
            # حذف الجلسة المنتهية تلقائياً
            db.delete(uid)
            return
        except errors.rpcerrorlist.AuthKeyDuplicatedError as e:
            analysis = analyze_session_error(e)
            logger.error(f"AuthKeyDuplicated for user {uid}: {e}")
            await status_msg.edit_text(
                f"❌ **جلسة مكررة**\n\n{analysis['solution']}"
            )
            return
        except errors.rpcerrorlist.SessionRevokedError as e:
            analysis = analyze_session_error(e)
            logger.error(f"SessionRevoked for user {uid}: {e}")
            await status_msg.edit_text(
                f"❌ **جلسة ملغاة**\n\n{analysis['solution']}"
            )
            db.delete(uid)
            return
        except Exception as e:
            analysis = analyze_session_error(e)
            logger.error(f"Failed to start client for user {uid}: {e}\n{traceback.format_exc()}")
            await status_msg.edit_text(
                f"❌ **فشل تشغيل الجلسة**\n\n"
                f"الخطأ: `{analysis['error_type']}`\n"
                f"الرسالة: {analysis['message']}\n\n"
                f"{analysis['solution']}"
            )
            return
        
        me = await client.get_me()
        logger.info(f"User {uid} started bot as {me.username or me.first_name}")
        
        # ==================== معالجات الأوامر ====================
        
        @client.on(events.NewMessage(pattern=r'\.بنغ|\.ping'))
        async def ping_handler(event):
            try:
                await event.edit("📡 **جاري قياس السرعة...**")
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
                logger.error(f"Ping error: {e}")
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
                logger.error(f"Translate error: {e}")
                await event.edit(f"❌ خطأ: {e}")

        @client.on(events.NewMessage(pattern=r'\.صوت'))
        async def audio_extract(event):
            reply = await event.get_reply_message()
            if not reply or (not reply.video and not reply.document):
                await event.reply("❌ استخدم الأمر كرد على فيديو")
                return
            
            await event.edit("🎵 **جاري معالجة الملف...**")
            
            try:
                file_path = await reply.download_media()
                
                await event.client.send_file(
                    event.chat_id,
                    file_path,
                    reply_to=reply.id,
                    caption="🎵 **تم استخراج الملف الصوتي!**",
                    force_document=False
                )
                
                os.remove(file_path)
                await event.delete()
                
            except Exception as e:
                logger.error(f"Audio extract error: {e}")
                await event.edit(f"❌ خطأ: {e}")

        @client.on(events.NewMessage(pattern=r'\.نص'))
        async def speech_to_text(event):
            reply = await event.get_reply_message()
            if not reply or (not reply.voice and not reply.audio):
                await event.reply("❌ استخدم الأمر كرد على رسالة صوتية")
                return
            
            await event.edit("🎙️ **جاري استخراج النص...**")
            
            try:
                voice_path = await reply.download_media()
                
                try:
                    result = await client.transcribe_voice(event.chat_id, reply.id)
                    if result:
                        await event.edit(f"📝 **النص المستخرج:**\n\n{result}")
                    else:
                        raise Exception("No result")
                except:
                    await event.edit(
                        "⚠️ **خاصية تحويل الصوت لنص**\n\n"
                        "📱 الطريقة البديلة:\n"
                        "1. افتح الرسالة الصوتية في تليجرام\n"
                        "2. اضغط على زر 'Aa' للتحويل للنص\n"
                        "💡 الخاصية متاحة في تليجرام بريميوم"
                    )
                
                if os.path.exists(voice_path):
                    os.remove(voice_path)
                
            except Exception as e:
                logger.error(f"Speech to text error: {e}")
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
                    await event.client.send_file(event.chat_id, file_path, reply_to=reply.id, caption="✅ تم تحويل الستيكر لصورة!")
                elif reply.photo:
                    await event.client.send_file(event.chat_id, file_path, force_document=False, reply_to=reply.id, caption="✅ تم تحويل الصورة!")
                elif reply.video:
                    await event.client.send_file(event.chat_id, file_path, reply_to=reply.id, caption="✅ تم معالجة الفيديو!")
                elif reply.gif:
                    await event.client.send_file(event.chat_id, file_path, reply_to=reply.id, caption="✅ تم إرسال الملف")
                else:
                    await event.edit("❌ نوع الملف غير مدعوم")
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    return
                
                if os.path.exists(file_path):
                    os.remove(file_path)
                await event.delete()
                
            except Exception as e:
                logger.error(f"Convert media error: {e}")
                await event.edit(f"❌ خطأ: {e}")

        @client.on(events.NewMessage(pattern=r'\.يوت (.+)'))
        async def youtube_download(event):
            query = event.pattern_match.group(1)
            await event.edit(f"🔍 **جاري البحث عن:** {query}")
            
            try:
                ydl_opts = {
                    'format': 'bestaudio[ext=m4a]/bestaudio/best',
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
                    
                    found = False
                    for f in Path().glob(f"{title}.*"):
                        if f.exists():
                            await event.edit("📤 **جاري الرفع...**")
                            await event.client.send_file(
                                event.chat_id,
                                str(f),
                                caption=f"🎵 **{title}**\n👤 {uploader}\n⏱️ {duration//60}:{duration%60:02d}\n✅ تم التحميل!",
                                attributes=[DocumentAttributeAudio(duration=duration, title=title, performer=uploader), DocumentAttributeFilename(f.name)]
                            )
                            os.remove(str(f))
                            found = True
                            break
                    
                    if found:
                        await event.delete()
                    else:
                        await event.edit("❌ لم يتم العثور على الملف")
                
            except Exception as e:
                logger.error(f"YouTube download error: {e}")
                await event.edit(f"❌ خطأ: {str(e)[:200]}")

        # ==================== مراقبة الأخطاء أثناء التشغيل ====================
        
        original_is_connected = client.is_connected
        
        @client.on(events.Disconnect)
        async def disconnection_handler(event):
            logger.warning(f"⚠️ انقطع اتصال اليوزربوت للمستخدم {uid}")
            try:
                await update.message.reply_text(
                    "⚠️ **انقطع اتصال البوت!**\n\n"
                    "جاري محاولة إعادة الاتصال تلقائياً...\n"
                    "إذا استمرت المشكلة، استخدم:\n"
                    "/stop ثم /run"
                )
            except:
                pass

        # ==================== مهمة فحص الاتصال الدورية ====================
        
        async def connection_monitor():
            """مراقبة الاتصال وإعادة المحاولة عند الانقطاع"""
            disconnect_count = 0
            while uid in active_bots:
                await asyncio.sleep(15)
                try:
                    if uid not in active_bots:
                        break
                    client = active_bots[uid]
                    if not client.is_connected():
                        disconnect_count += 1
                        logger.warning(f"🔄 محاولة إعادة الاتصال #{disconnect_count} للمستخدم {uid}")
                        try:
                            await client.connect()
                            logger.info(f"✅ تمت إعادة الاتصال للمستخدم {uid}")
                            disconnect_count = 0
                        except errors.rpcerrorlist.AuthKeyUnregisteredError as e:
                            logger.error(f"🔴 فشلت إعادة الاتصال - الجلسة منتهية: {e}")
                            analysis = analyze_session_error(e)
                            try:
                                await update.message.reply_text(
                                    f"🚫 **انتهت الجلسة أثناء التشغيل**\n\n{analysis['solution']}"
                                )
                            except:
                                pass
                            # إيقاف البوت تلقائياً
                            if uid in active_bots:
                                try:
                                    await active_bots[uid].disconnect()
                                except:
                                    pass
                                del active_bots[uid]
                            db.delete(uid)
                            break
                        except errors.rpcerrorlist.SessionRevokedError as e:
                            logger.error(f"🔴 فشلت إعادة الاتصال - الجلسة ملغاة: {e}")
                            analysis = analyze_session_error(e)
                            try:
                                await update.message.reply_text(
                                    f"🚫 **الجلسة ملغاة**\n\n{analysis['solution']}"
                                )
                            except:
                                pass
                            if uid in active_bots:
                                try:
                                    await active_bots[uid].disconnect()
                                except:
                                    pass
                                del active_bots[uid]
                            db.delete(uid)
                            break
                        except Exception as e:
                            logger.error(f"❌ فشلت إعادة الاتصال: {e}")
                            if disconnect_count >= 5:
                                logger.error(f"💀 فشلت 5 محاولات إعادة اتصال للمستخدم {uid}")
                                try:
                                    await update.message.reply_text(
                                        "💀 **فشلت كل محاولات إعادة الاتصال**\n\n"
                                        "استخدم /stop ثم /run للمحاولة مجدداً"
                                    )
                                except:
                                    pass
                                if uid in active_bots:
                                    try:
                                        await active_bots[uid].disconnect()
                                    except:
                                        pass
                                    del active_bots[uid]
                                break
                    else:
                        disconnect_count = 0
                except Exception as e:
                    logger.error(f"Error in connection monitor: {e}")
        
        # بدء مهمة المراقبة
        asyncio.ensure_future(connection_monitor())
        
        # حفظ العميل في القائمة النشطة
        active_bots[uid] = client
        
        await status_msg.edit_text(
            f"✅ **تم تشغيل البوت بنجاح!**\n\n"
            f"👤 **الحساب:** {me.first_name}\n"
            f"📱 **الهاتف:** {me.phone}\n"
            f"🛡️ **نظام المراقبة:** نشط\n\n"
            f"💡 **أوامر سريعة:**\n"
            f"• .ترجم - .صوت - .تحويل\n"
            f"• .بنغ - .يوت - .نص\n\n"
            f"📋 /status - /logs - /stop"
        )
        
    except Exception as e:
        logger.error(f"Failed to run bot for user {uid}: {e}\n{traceback.format_exc()}")
        await status_msg.edit_text(f"❌ فشل التشغيل: {e}")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in active_bots:
        try:
            await active_bots[uid].disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting bot for user {uid}: {e}")
        del active_bots[uid]
        await update.message.reply_text("✅ تم إيقاف البوت")
    else:
        await update.message.reply_text("البوت متوقف بالفعل")

async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in active_bots:
        try:
            await active_bots[uid].disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting bot for user {uid}: {e}")
        del active_bots[uid]
    
    db.delete(uid)
    await update.message.reply_text("✅ تم تسجيل الخروج وحذف الجلسة")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            
            sent_code = await c.send_code_request(text)
            
            s['c'] = c
            s['phone_code_hash'] = sent_code.phone_code_hash
            s['code_attempts'] = 0
            s['step'] = 'code'
            
            await update.message.reply_text("✅ **الخطوة 4/4**\nتم إرسال الكود. أرسله هنا:")
            
        except Exception as e:
            logger.error(f"Error sending code: {e}")
            await update.message.reply_text(f"❌ خطأ: {e}")
            if 'c' in s:
                try: await s['c'].disconnect()
                except: pass
            del login_states[uid]
    
    elif s['step'] == 'code':
        s['code_attempts'] = s.get('code_attempts', 0) + 1
        
        try:
            await s['c'].sign_in(
                phone=s['phone'],
                code=text,
                phone_code_hash=s['phone_code_hash']
            )
            await finish_login(update, s)
            
        except SessionPasswordNeededError:
            s['step'] = 'pass'
            await update.message.reply_text("🔒 حسابك مفعل عليه تحقق بخطوتين.\nأرسل كلمة المرور:")
            
        except Exception as e:
            logger.error(f"Code verification error: {e}")
            
            if s['code_attempts'] >= 3:
                await update.message.reply_text("❌ محاولات كتير غلط. ابدأ من جديد: /login")
                try: await s['c'].disconnect()
                except: pass
                del login_states[uid]
                return
            
            try:
                await update.message.reply_text("🔄 **جاري إرسال كود جديد...**\n\n💡 **ملاحظة:** استخدم أحدث كود وصلك مش القديم!")
                
                sent_code = await s['c'].send_code_request(s['phone'])
                s['phone_code_hash'] = sent_code.phone_code_hash
                
                await update.message.reply_text("✅ **تم إرسال كود جديد**\nأرسل أحدث كود وصلك:")
                
            except Exception as e2:
                logger.error(f"Error resending code: {e2}")
                await update.message.reply_text(f"❌ خطأ: {e2}\nابدأ من جديد: /login")
                try: await s['c'].disconnect()
                except: pass
                del login_states[uid]
    
    elif s['step'] == 'pass':
        try:
            await s['c'].sign_in(password=text)
            await finish_login(update, s)
        except Exception as e:
            logger.error(f"Password error: {e}")
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
            f"✅ **تم تسجيل الدخول بنجاح!**\n\n"
            f"👤 الاسم: {me.first_name}\n"
            f"📱 الهاتف: {me.phone}\n\n"
            f"💾 **الجلسة محفوظة تلقائياً**\n"
            f"🚀 استخدم /run للتشغيل"
        )
        logger.info(f"User {uid} logged in as {me.username or me.first_name}")
    except Exception as e:
        logger.error(f"Error saving session for user {uid}: {e}")
        await update.message.reply_text(f"❌ خطأ في الحفظ: {e}")
    finally:
        try: await s['c'].disconnect()
        except: pass
        del login_states[uid]

# ==================== تشغيل ====================

def main():
    print("=" * 50)
    print("🚀 جاري تشغيل البوت...")
    
    # إنشاء مجلد البيانات
    Path("data").mkdir(parents=True, exist_ok=True)
    
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
    app.add_handler(CommandHandler("logs", logs_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ البوت الخارق شغال!")
    print("💾 نظام حفظ الجلسات مفعل")
    print("🛡️ نظام مراقبة الأخطاء مفعل")
    print("📋 سجل الأخطاء: data/session_errors.log")
    print("=" * 50)
    
    app.run_polling()

if __name__ == "__main__":
    main()
