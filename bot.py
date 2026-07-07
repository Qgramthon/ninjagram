#!/usr/bin/env python3
"""
بوت تسجيل دخول تليجرام بسيط
بيشتغل بالتوكن فقط - مش محتاج API_ID ولا API_HASH
"""

import os
import sys
import asyncio
import logging
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession
from cryptography.fernet import Fernet

# ==================== الإعدادات ====================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# توكن البوت فقط
BOT_TOKEN = "8879863328:AAH_PB_1i50hIyU-UI58TcD-dflHl4dBFqo"

# API_ID و API_HASH للبوت - ممكن أي قيم صالحة
# لو مش عايز تحطهم، استخدم القيم الافتراضية دي
API_ID = int(os.environ.get("API_ID", "2040"))  # رقم افتراضي معروف
API_HASH = os.environ.get("API_HASH", "b18441a1ff607e10a989891a5462e28b")  # هاش افتراضي معروف

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

# تخزين
sessions = {}
active_bots = {}
login_states = {}

def enc(t): 
    return cipher.encrypt(t.encode()).decode() if t else None

def dec(t): 
    return cipher.decrypt(t.encode()).decode() if t else None

# ==================== البوت ====================

bot = TelegramClient('bot', api_id=API_ID, api_hash=API_HASH)

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply("""
👋 **مرحباً بك!**

📋 **الأوامر:**
/login - تسجيل الدخول
/run - تشغيل اليوزربوت
/stop - إيقاف اليوزربوت
/status - حالة الجلسة
/logout - تسجيل الخروج
/cancel - إلغاء العملية
/help - مساعدة
""")

@bot.on(events.NewMessage(pattern='/login'))
async def login(event):
    uid = event.sender_id
    if uid in sessions:
        return await event.reply("✅ مسجل دخول بالفعل!")
    
    login_states[uid] = {'step': 'api_id'}
    await event.reply(
        "📱 **الخطوة 1/4**\n"
        "أرسل API_ID:\n"
        "احصل عليه من my.telegram.org"
    )

@bot.on(events.NewMessage(pattern='/cancel'))
async def cancel(event):
    uid = event.sender_id
    if uid in login_states:
        if 'c' in login_states[uid]:
            try: await login_states[uid]['c'].disconnect()
            except: pass
        del login_states[uid]
        await event.reply("✅ تم الإلغاء")

@bot.on(events.NewMessage(pattern='/status'))
async def status(event):
    uid = event.sender_id
    if uid in sessions and uid in active_bots:
        await event.reply("🟢 مسجل دخول والبوت شغال")
    elif uid in sessions:
        await event.reply("🟡 مسجل دخول والبوت متوقف")
    else:
        await event.reply("🔴 غير مسجل")

@bot.on(events.NewMessage(pattern='/run'))
async def run(event):
    uid = event.sender_id
    if uid not in sessions:
        return await event.reply("❌ سجل دخول أولاً: /login")
    if uid in active_bots:
        return await event.reply("✅ شغال بالفعل")
    
    try:
        d = sessions[uid]
        client = TelegramClient(
            StringSession(dec(d['s'])), 
            int(dec(d['a'])), 
            dec(d['h'])
        )
        await client.start()
        
        @client.on(events.NewMessage(pattern='.ping'))
        async def ping(e):
            await e.reply('🏓 Pong!')
        
        active_bots[uid] = client
        await event.reply("✅ **تم التشغيل!**\nجرب إرسال `.ping`")
    except Exception as e:
        await event.reply(f"❌ خطأ: {e}")

@bot.on(events.NewMessage(pattern='/stop'))
async def stop(event):
    uid = event.sender_id
    if uid in active_bots:
        await active_bots[uid].disconnect()
        del active_bots[uid]
        await event.reply("✅ تم الإيقاف")
    else:
        await event.reply("متوقف بالفعل")

@bot.on(events.NewMessage(pattern='/logout'))
async def logout(event):
    uid = event.sender_id
    if uid in active_bots:
        try: await active_bots[uid].disconnect()
        except: pass
        del active_bots[uid]
    if uid in sessions:
        del sessions[uid]
    await event.reply("✅ تم تسجيل الخروج")

@bot.on(events.NewMessage(pattern='/help'))
async def help_cmd(event):
    await event.reply("""
📚 **الخطوات:**
1. /login
2. أرسل API_ID
3. أرسل API_HASH
4. أرسل رقم الهاتف
5. أرسل كود التحقق
6. /run لتشغيل البوت
""")

@bot.on(events.NewMessage())
async def handle(event):
    uid = event.sender_id
    if not event.text or event.text.startswith('/'):
        return
    if uid not in login_states:
        return
    
    s = login_states[uid]
    t = event.text.strip()
    
    if s['step'] == 'api_id':
        try:
            s['api_id'] = int(t)
            s['step'] = 'api_hash'
            await event.reply("✅ **الخطوة 2/4**\nأرسل API_HASH:")
        except:
            await event.reply("❌ رقم خطأ. حاول تاني:")
    
    elif s['step'] == 'api_hash':
        s['api_hash'] = t
        s['step'] = 'phone'
        await event.reply("✅ **الخطوة 3/4**\nأرسل رقم الهاتف:\nمثال: +201234567890")
    
    elif s['step'] == 'phone':
        if not t.startswith('+'):
            return await event.reply("❌ لازم يبدأ بـ +")
        s['phone'] = t
        try:
            c = TelegramClient(StringSession(), s['api_id'], s['api_hash'])
            await c.connect()
            code = await c.send_code_request(t)
            s['c'] = c
            s['hash'] = code.phone_code_hash
            s['step'] = 'code'
            await event.reply("✅ **الخطوة 4/4**\nتم إرسال الكود. أرسله هنا:")
        except Exception as e:
            await event.reply(f"❌ خطأ: {e}")
            del login_states[uid]
    
    elif s['step'] == 'code':
        try:
            await s['c'].sign_in(phone=s['phone'], code=t, phone_code_hash=s['hash'])
            await done(event, s)
        except SessionPasswordNeededError:
            s['step'] = 'pass'
            await event.reply("🔒 تحقق بخطوتين. أرسل كلمة المرور:")
        except Exception as e:
            await event.reply(f"❌ خطأ: {e}")
    
    elif s['step'] == 'pass':
        try:
            await s['c'].sign_in(password=t)
            await done(event, s)
        except Exception as e:
            await event.reply(f"❌ خطأ: {e}")

async def done(event, s):
    uid = event.sender_id
    try:
        ss = s['c'].session.save()
        sessions[uid] = {
            'a': enc(str(s['api_id'])),
            'h': enc(s['api_hash']),
            'p': enc(s['phone']),
            's': enc(ss)
        }
        me = await s['c'].get_me()
        await event.reply(f"✅ **تم بنجاح!**\n👤 {me.first_name}\n📱 {me.phone}\n🚀 /run للتشغيل")
    except Exception as e:
        await event.reply(f"❌ خطأ: {e}")
    finally:
        try: await s['c'].disconnect()
        except: pass
        del login_states[uid]

# ==================== تشغيل ====================

async def main():
    print("جاري التشغيل...")
    await bot.start(bot_token=BOT_TOKEN)
    me = await bot.get_me()
    print(f"✅ شغال: @{me.username}")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
