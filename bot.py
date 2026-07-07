#!/usr/bin/env python3
"""
بوت تليجرام متعدد المهام - نسخة Railway
"""

import os
import sys
import asyncio
import logging
import time
import io
import re
import subprocess
from datetime import datetime
from telethon import TelegramClient, events, types
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeVideo, DocumentAttributeAudio
from cryptography.fernet import Fernet
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from googletrans import Translator
import yt_dlp
import speedtest
import requests

# ==================== الإعدادات ====================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = "8879863328:AAH_PB_1i50hIyU-UI58TcD-dflHl4dBFqo"

# ==================== التشفير ====================

def get_key():
    key = os.environ.get("ENCRYPTION_KEY", "")
    if key:
        try:
            Fernet(key.encode())
            return key.encode()
        except:
            pass
    return Fernet.generate_key()

cipher = Fernet(get_key())

def enc(t): return cipher.encrypt(t.encode()).decode() if t else None
def dec(t): return cipher.decrypt(t.encode()).decode() if t else None

# ==================== تخزين ====================

sessions = {}
active_bots = {}
login_states = {}

# ==================== المترجم ====================

translator = Translator()

async def detect_language(text):
    try:
        detection = translator.detect(text)
        return detection.lang
    except:
        arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
        return 'ar' if arabic_chars > len(text) / 2 else 'en'

# ==================== أوامر البوت ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""
👋 **مرحباً بك في البوت الخارق!**

📋 **الأوامر الأساسية:**
/login - تسجيل الدخول
/run - تشغيل اليوزربوت
/stop - إيقاف اليوزربوت
/status - حالة الجلسة

🎯 **الأوامر المتقدمة:**
.ترجم - ترجمة (رد على رسالة)
.صوت - تحويل فيديو لصوت (رد على فيديو)
.نص - استخراج النص من الصوت (رد على ريكورد)
.تحويل - تحويل صورة لستيكر والعكس
.بنغ - قياس سرعة النت الحقيقية
.يوت + اسم - تحميل صوت من يوتيوب

🛠️ **أوامر التحكم:**
/logout - تسجيل الخروج
/cancel - إلغاء العملية
/help - مساعدة
""")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""
📚 **شرح الأوامر:**

1️⃣ **.ترجم** - رد على رسالة للترجمة (عربي↔إنجليزي)

2️⃣ **.صوت** - رد على فيديو لتحويله لـ MP3

3️⃣ **.نص** - رد على رسالة صوتية لاستخراج النص

4️⃣ **.تحويل** - رد على:
   • صورة ← ستيكر
   • ستيكر ← صورة

5️⃣ **.بنغ** - قياس سرعة الإنترنت

6️⃣ **.يوت اغنية** - تحميل الصوت من يوتيوب
""")

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in sessions:
        await update.message.reply_text("✅ مسجل دخول بالفعل!")
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

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in sessions and uid in active_bots:
        await update.message.reply_text("🟢 مسجل دخول والبوت شغال")
    elif uid in sessions:
        await update.message.reply_text("🟡 مسجل دخول والبوت متوقف")
    else:
        await update.message.reply_text("🔴 غير مسجل دخول")

async def run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in sessions:
        await update.message.reply_text("❌ سجل دخول أولاً: /login")
        return
    if uid in active_bots:
        await update.message.reply_text("✅ شغال بالفعل")
        return
    
    try:
        d = sessions[uid]
        client = TelegramClient(
            StringSession(dec(d['s'])), 
            int(dec(d['a'])), 
            dec(d['h'])
        )
        await client.start()
        
        # ========== الأوامر المتقدمة ==========
        
        @client.on(events.NewMessage(pattern=r'\.بنغ|\.ping'))
        async def ping_handler(event):
            """قياس سرعة الإنترنت الحقيقية"""
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
            """ترجمة النص"""
            reply = await event.get_reply_message()
            if not reply or not reply.text:
                await event.reply("❌ استخدم الأمر كرد على رسالة")
                return
            
            await event.edit("🔄 **جاري الترجمة...**")
            
            try:
                text = reply.text
                lang = await detect_language(text)
                
                if lang == 'ar':
                    translated = translator.translate(text, dest='en')
                    result = f"🇬🇧 **الترجمة للإنجليزية:**\n\n{translated.text}"
                else:
                    translated = translator.translate(text, dest='ar')
                    result = f"🇸🇦 **الترجمة للعربية:**\n\n{translated.text}"
                
                await event.edit(result)
                
            except Exception as e:
                await event.edit(f"❌ خطأ في الترجمة: {e}")
        
        @client.on(events.NewMessage(pattern=r'\.صوت'))
        async def audio_extract(event):
            """تحويل الفيديو لصوت"""
            reply = await event.get_reply_message()
            if not reply or not reply.video:
                await event.reply("❌ استخدم الأمر كرد على فيديو")
                return
            
            await event.edit("🎵 **جاري استخراج الصوت...**")
            
            try:
                # تحميل الفيديو
                video_path = await reply.download_media()
                audio_path = video_path.rsplit('.', 1)[0] + '.mp3'
                
                # استخدام ffmpeg لو موجود
                try:
                    cmd = f'ffmpeg -i "{video_path}" -q:a 0 -map a "{audio_path}" -y'
                    subprocess.run(cmd, shell=True, check=True, capture_output=True)
                except:
                    # لو ffmpeg مش موجود، نرسل الفيديو زي ما هو
                    await event.edit("⚠️ ffmpeg غير متوفر. جاري إرسال الملف كما هو...")
                    await event.client.send_file(event.chat_id, video_path, reply_to=reply.id)
                    os.remove(video_path)
                    return
                
                # إرسال الصوت
                await event.client.send_file(
                    event.chat_id,
                    audio_path,
                    reply_to=reply.id,
                    caption="🎵 تم استخراج الصوت!"
                )
                
                os.remove(video_path)
                os.remove(audio_path)
                await event.delete()
                
            except Exception as e:
                await event.edit(f"❌ خطأ: {e}")
        
        @client.on(events.NewMessage(pattern=r'\.نص'))
        async def speech_to_text(event):
            """استخراج النص من الصوت"""
            reply = await event.get_reply_message()
            if not reply or not reply.voice:
                await event.reply("❌ استخدم الأمر كرد على رسالة صوتية")
                return
            
            await event.edit("🎙️ **جاري استخراج النص...**")
            
            try:
                # نحمل الصوت ونستخدم Telegram API للتحويل
                voice_path = await reply.download_media()
                
                # نرسل الصوت لـ Telegram API للتحويل
                result = await event.client.transcribe_voice(
                    event.chat_id,
                    reply.id
                )
                
                if result:
                    await event.edit(f"📝 **النص المستخرج:**\n\n{result}")
                else:
                    await event.edit("❌ لم يتم التعرف على النص. جرب في بيئة هادئة.")
                
                os.remove(voice_path)
                
            except AttributeError:
                await event.edit("""
⚠️ **خاصية تحويل الصوت لنص غير متوفرة حالياً**

📱 **بديل:** استخدم تطبيق تليجرام الرسمي - فيه خاصية تحويل الصوت لنص مدمجة.
                """)
            except Exception as e:
                await event.edit(f"❌ خطأ: {e}")
        
        @client.on(events.NewMessage(pattern=r'\.تحويل'))
        async def convert_media(event):
            """تحويل الصور والستيكرات"""
            reply = await event.get_reply_message()
            if not reply or not reply.media:
                await event.reply("❌ استخدم الأمر كرد على صورة أو ستيكر")
                return
            
            await event.edit("🔄 **جاري التحويل...**")
            
            try:
                file_path = await reply.download_media()
                
                if reply.sticker:
                    # ستيكر ← صورة
                    await event.client.send_file(event.chat_id, file_path, reply_to=reply.id)
                    
                elif reply.photo:
                    # صورة ← ستيكر
                    await event.client.send_file(
                        event.chat_id,
                        file_path,
                        force_document=False,
                        reply_to=reply.id
                    )
                    
                elif reply.video:
                    # فيديو ← GIF/ستيكر متحرك
                    gif_path = file_path.rsplit('.', 1)[0] + '.gif'
                    try:
                        cmd = f'ffmpeg -i "{file_path}" -vf "fps=10,scale=320:-1:flags=lanczos" "{gif_path}" -y'
                        subprocess.run(cmd, shell=True, check=True, capture_output=True)
                        await event.client.send_file(event.chat_id, gif_path, reply_to=reply.id)
                        os.remove(gif_path)
                    except:
                        await event.client.send_file(event.chat_id, file_path, reply_to=reply.id)
                else:
                    await event.edit("❌ نوع الملف غير مدعوم")
                
                os.remove(file_path)
                await event.delete()
                
            except Exception as e:
                await event.edit(f"❌ خطأ: {e}")
        
        @client.on(events.NewMessage(pattern=r'\.يوت (.+)'))
        async def youtube_download(event):
            """تحميل من يوتيوب"""
            query = event.pattern_match.group(1)
            
            await event.edit(f"🔍 **جاري البحث عن:** {query}")
            
            try:
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
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
                            caption=f"""
🎵 **{title}**
👤 **القناة:** {uploader}
⏱️ **المدة:** {duration//60}:{duration%60:02d}

✅ تم التحميل بنجاح!
""",
                            attributes=[
                                DocumentAttributeAudio(
                                    duration=duration,
                                    title=title,
                                    performer=uploader
                                )
                            ]
                        )
                        
                        os.remove(mp3_path)
                        await event.delete()
                    else:
                        await event.edit("❌ لم يتم العثور على الملف")
                
            except Exception as e:
                await event.edit(f"❌ خطأ في التحميل: {str(e)[:200]}")
        
        active_bots[uid] = client
        await update.message.reply_text("✅ **تم تشغيل البوت بجميع الميزات!**")
        
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in active_bots:
        await active_bots[uid].disconnect()
        del active_bots[uid]
        await update.message.reply_text("✅ تم الإيقاف")

async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in active_bots:
        try: await active_bots[uid].disconnect()
        except: pass
        del active_bots[uid]
    if uid in sessions:
        del sessions[uid]
    await update.message.reply_text("✅ تم تسجيل الخروج")

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
    uid = update.effective_user.id
    try:
        ss = s['c'].session.save()
        sessions[uid] = {
            'a': enc(str(s['api_id'])),
            'h': enc(s['api_hash']),
            'p': enc(s['phone']),
            's': enc(ss)
        }
        me = await s['c'].get_me()
        await update.message.reply_text(
            f"✅ **تم بنجاح!**\n"
            f"👤 {me.first_name}\n"
            f"📱 {me.phone}\n"
            f"🚀 /run للتشغيل"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")
    finally:
        try: await s['c'].disconnect()
        except: pass
        del login_states[uid]

# ==================== تشغيل ====================

def main():
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
    app.run_polling()

if __name__ == "__main__":
    main()
