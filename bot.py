#!/usr/bin/env python3
"""
بوت تسجيل دخول تليجرام بسيط
مع دعم Proxy لتخطي حظر Railway
"""

import os
import sys
import asyncio
import logging
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession
from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate
from cryptography.fernet import Fernet
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ==================== الإعدادات ====================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = "8879863328:AAH_PB_1i50hIyU-UI58TcD-dflHl4dBFqo"

# ==================== Proxy (حل مشكلة الحظر) ====================

# لو عايز تستخدم MTProto Proxy:
# MT_PROXY = ("proxy_ip", port, "secret")
# مثال:
# MT_PROXY = ("149.154.167.40", 443, "eeffaaddccbb99887766554433221100")

# Proxy مجاني للتجربة (MTProto):
MT_PROXY_HOST = os.environ.get("MT_PROXY_HOST", "")
MT_PROXY_PORT = int(os.environ.get("MT_PROXY_PORT", "443"))
MT_PROXY_SECRET = os.environ.get("MT_PROXY_SECRET", "")

# ==================== التشفير ====================

def get_key():
    key = os.environ.get("ENCRYPTION_KEY", "")
    if key:
        try:
            Fernet(key.encode())
            return key.encode()
        except:
            pass
    new_key = Fernet.generate_key()
    return new_key

cipher = Fernet(get_key())

def enc(t): 
    return cipher.encrypt(t.encode()).decode() if t else None

def dec(t): 
    return cipher.decrypt(t.encode()).decode() if t else None

# ==================== تخزين ====================

sessions = {}
active_bots = {}
login_states = {}

# ==================== أوامر البوت ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""
👋 **مرحباً بك!**

📋 **الأوامر:**
/login - تسجيل الدخول
/run - تشغيل اليوزربوت
/stop - إيقاف اليوزربوت
/status - حالة الجلسة
/logout - تسجيل الخروج
/cancel - إلغاء العملية
/help - مساعدة

🛡️ **Proxy مفعل لتخطي الحظر**
""")

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in sessions:
        await update.message.reply_text("✅ مسجل دخول بالفعل!")
        return
    
    login_states[uid] = {'step': 'api_id'}
    await update.message.reply_text(
        "📱 **الخطوة 1/4**\n"
        "أرسل API_ID الخاص بك\n"
        "احصل عليه من: https://my.telegram.org\n\n"
        "🛡️ سيتم استخدام Proxy لتخطي الحظر"
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
    uid = update.effective_user.id
    if uid in sessions and uid in active_bots:
        await update.message.reply_text("🟢 مسجل دخول والبوت شغال")
    elif uid in sessions:
        await update.message.reply_text("🟡 مسجل دخول والبوت متوقف")
    else:
        await update.message.reply_text("🔴 غير مسجل")

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
        
        # إنشاء عميل مع Proxy لو موجود
        client_kwargs = {
            'session': StringSession(dec(d['s'])),
            'api_id': int(dec(d['a'])),
            'api_hash': dec(d['h'])
        }
        
        # إضافة Proxy لو متوفر
        if MT_PROXY_HOST and MT_PROXY_SECRET:
            client_kwargs['connection'] = ConnectionTcpMTProxyRandomizedIntermediate
            client_kwargs['proxy'] = (MT_PROXY_HOST, MT_PROXY_PORT, MT_PROXY_SECRET)
            logger.info(f"Using MTProto Proxy: {MT_PROXY_HOST}")
        
        client = TelegramClient(**client_kwargs)
        await client.start()
        
        @client.on(events.NewMessage(pattern='.ping'))
        async def ping(e):
            await e.reply('🏓 Pong!')
        
        active_bots[uid] = client
        await update.message.reply_text("✅ **تم التشغيل!**\n🛡️ Proxy مفعل\nجرب إرسال `.ping`")
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in active_bots:
        await active_bots[uid].disconnect()
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
    if uid in sessions:
        del sessions[uid]
    await update.message.reply_text("✅ تم تسجيل الخروج")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""
📚 **الخطوات:**
1. /login
2. أرسل API_ID
3. أرسل API_HASH
4. أرسل رقم الهاتف
5. أرسل كود التحقق
6. /run لتشغيل البوت

🛡️ **Proxy:** مفعل تلقائياً لتخطي الحظر
""")

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
            await update.message.reply_text("❌ رقم خطأ. حاول تاني:")
    
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
            # إنشاء عميل مع Proxy لو متوفر
            client_kwargs = {
                'session': StringSession(),
                'api_id': s['api_id'],
                'api_hash': s['api_hash']
            }
            
            if MT_PROXY_HOST and MT_PROXY_SECRET:
                client_kwargs['connection'] = ConnectionTcpMTProxyRandomizedIntermediate
                client_kwargs['proxy'] = (MT_PROXY_HOST, MT_PROXY_PORT, MT_PROXY_SECRET)
            
            c = TelegramClient(**client_kwargs)
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
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("run", run))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("logout", logout))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    if MT_PROXY_HOST:
        print(f"🛡️ Proxy مفعل: {MT_PROXY_HOST}")
    else:
        print("⚠️ شغال بدون Proxy - ممكن تليجرام يحظر Railway")
    
    print("✅ البوت شغال...")
    app.run_polling()

if __name__ == "__main__":
    main()
