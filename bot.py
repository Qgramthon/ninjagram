#!/usr/bin/env python3
"""
بوت تسجيل دخول تليجرام بسيط
Simple Telegram Login Bot
"""

import os
import sys
import asyncio
import logging
import base64
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession
from cryptography.fernet import Fernet

# ==================== الإعدادات ====================

# السجلات
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# توكن البوت
BOT_TOKEN = "8879863328:AAH_PB_1i50hIyU-UI58TcD-dflHl4dBFqo"

# ==================== التشفير ====================

def get_encryption_key():
    """الحصول على مفتاح تشفير صالح أو إنشاء واحد جديد"""
    key = os.environ.get("ENCRYPTION_KEY", "")
    
    if key:
        try:
            # محاولة استخدام المفتاح الموجود
            Fernet(key.encode() if isinstance(key, str) else key)
            return key.encode() if isinstance(key, str) else key
        except:
            logger.warning("مفتاح التشفير غير صالح، جاري إنشاء مفتاح جديد...")
    
    # إنشاء مفتاح جديد صالح
    new_key = Fernet.generate_key()
    logger.info(f"تم إنشاء مفتاح تشفير جديد: {new_key.decode()}")
    return new_key

# إعداد التشفير
ENCRYPTION_KEY = get_encryption_key()
cipher = Fernet(ENCRYPTION_KEY)

# تخزين مؤقت للجلسات والبيانات
sessions = {}  # user_id: session_string
active_bots = {}  # user_id: TelegramClient
login_states = {}  # user_id: dict

# ==================== دوال مساعدة ====================

def encrypt(text):
    """تشفير النص"""
    if not text:
        return None
    try:
        return cipher.encrypt(text.encode()).decode()
    except Exception as e:
        logger.error(f"خطأ في التشفير: {e}")
        return None

def decrypt(encrypted_text):
    """فك التشفير"""
    if not encrypted_text:
        return None
    try:
        return cipher.decrypt(encrypted_text.encode()).decode()
    except Exception as e:
        logger.error(f"خطأ في فك التشفير: {e}")
        return None

# ==================== البوت ====================

bot = TelegramClient('main_bot', api_id=1, api_hash='0'*32)

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    """رسالة ترحيب"""
    await event.reply("""
👋 **مرحباً بك في بوت تسجيل الدخول!**

📋 **الأوامر:**
/login - تسجيل الدخول لحسابك
/status - معرفة حالة جلستك
/run - تشغيل اليوزربوت
/stop - إيقاف اليوزربوت
/logout - تسجيل الخروج
/cancel - إلغاء العملية
/help - المساعدة

⚠️ لا تشارك بياناتك مع أحد
""")

@bot.on(events.NewMessage(pattern='/help'))
async def help_cmd(event):
    await event.reply("""
📚 **المساعدة:**

1. أرسل /login
2. أرسل API_ID
3. أرسل API_HASH  
4. أرسل رقم الهاتف
5. أرسل كود التحقق
6. أرسل كلمة المرور (إن وجدت)
7. أرسل /run لتشغيل البوت

🛑 /cancel لإلغاء أي خطوة
""")

@bot.on(events.NewMessage(pattern='/login'))
async def login(event):
    """بدء تسجيل الدخول"""
    user_id = event.sender_id
    
    if user_id in sessions:
        await event.reply("✅ أنت مسجل دخول بالفعل! استخدم /logout أولاً")
        return
    
    login_states[user_id] = {'step': 'api_id'}
    await event.reply(
        "📱 **الخطوة 1/4**\n"
        "أرسل API_ID الخاص بك\n"
        "احصل عليه من: https://my.telegram.org\n"
        "/cancel للإلغاء"
    )

@bot.on(events.NewMessage(pattern='/cancel'))
async def cancel(event):
    """إلغاء العملية"""
    user_id = event.sender_id
    if user_id in login_states:
        if 'client' in login_states[user_id]:
            try:
                await login_states[user_id]['client'].disconnect()
            except:
                pass
        del login_states[user_id]
        await event.reply("✅ تم الإلغاء")
    else:
        await event.reply("لا توجد عملية جارية")

@bot.on(events.NewMessage(pattern='/status'))
async def status(event):
    """حالة الجلسة"""
    user_id = event.sender_id
    if user_id in sessions and user_id in active_bots:
        await event.reply("🟢 **حالتك:** مسجل دخول والبوت شغال")
    elif user_id in sessions:
        await event.reply("🟡 **حالتك:** مسجل دخول والبوت متوقف")
    else:
        await event.reply("🔴 **حالتك:** غير مسجل دخول")

@bot.on(events.NewMessage(pattern='/run'))
async def run_bot(event):
    """تشغيل اليوزربوت"""
    user_id = event.sender_id
    
    if user_id not in sessions:
        await event.reply("❌ سجل دخول أولاً: /login")
        return
    
    if user_id in active_bots:
        await event.reply("✅ البوت شغال بالفعل")
        return
    
    try:
        # فك تشفير البيانات
        data = sessions[user_id]
        api_id = int(decrypt(data['api_id']))
        api_hash = decrypt(data['api_hash'])
        session_str = decrypt(data['session'])
        
        if not all([api_id, api_hash, session_str]):
            await event.reply("❌ بيانات الجلسة تالفة. سجل دخول مرة أخرى: /login")
            return
        
        # إنشاء عميل جديد
        client = TelegramClient(StringSession(session_str), api_id, api_hash)
        await client.start()
        
        # إضافة أمر ping بسيط
        @client.on(events.NewMessage(pattern='.ping'))
        async def ping(event):
            await event.reply('🏓 Pong!')
        
        active_bots[user_id] = client
        await event.reply("✅ **تم تشغيل البوت!**\nجرب إرسال `.ping` في أي محادثة")
        logger.info(f"Bot started for user {user_id}")
        
    except Exception as e:
        await event.reply(f"❌ خطأ: {e}")
        logger.error(f"Error starting bot: {e}")

@bot.on(events.NewMessage(pattern='/stop'))
async def stop_bot(event):
    """إيقاف اليوزربوت"""
    user_id = event.sender_id
    
    if user_id in active_bots:
        try:
            await active_bots[user_id].disconnect()
            del active_bots[user_id]
            await event.reply("✅ تم إيقاف البوت")
        except Exception as e:
            await event.reply(f"❌ خطأ: {e}")
    else:
        await event.reply("البوت متوقف بالفعل")

@bot.on(events.NewMessage(pattern='/logout'))
async def logout(event):
    """تسجيل الخروج"""
    user_id = event.sender_id
    
    # إيقاف البوت إذا كان شغال
    if user_id in active_bots:
        try:
            await active_bots[user_id].disconnect()
            del active_bots[user_id]
        except:
            pass
    
    # حذف الجلسة
    if user_id in sessions:
        del sessions[user_id]
    
    await event.reply("✅ تم تسجيل الخروج وحذف الجلسة")

@bot.on(events.NewMessage())
async def handle_steps(event):
    """معالجة خطوات تسجيل الدخول"""
    user_id = event.sender_id
    
    if event.text.startswith('/'):
        return
    
    if user_id not in login_states:
        return
    
    state = login_states[user_id]
    step = state['step']
    text = event.text.strip()
    
    # الخطوة 1: API_ID
    if step == 'api_id':
        try:
            api_id = int(text)
            state['api_id'] = api_id
            state['step'] = 'api_hash'
            await event.reply("✅ **الخطوة 2/4**\nأرسل API_HASH:")
        except:
            await event.reply("❌ يجب أن يكون رقماً. حاول مرة أخرى:")
    
    # الخطوة 2: API_HASH
    elif step == 'api_hash':
        state['api_hash'] = text
        state['step'] = 'phone'
        await event.reply("✅ **الخطوة 3/4**\nأرسل رقم الهاتف:\nمثال: +201234567890")
    
    # الخطوة 3: رقم الهاتف
    elif step == 'phone':
        if not text.startswith('+'):
            await event.reply("❌ يجب أن يبدأ بـ +")
            return
        
        state['phone'] = text
        
        try:
            # إنشاء عميل مؤقت
            client = TelegramClient(StringSession(), state['api_id'], state['api_hash'])
            await client.connect()
            
            # إرسال الكود
            sent = await client.send_code_request(text)
            state['client'] = client
            state['phone_code_hash'] = sent.phone_code_hash
            state['step'] = 'code'
            
            await event.reply("✅ **الخطوة 4/4**\nتم إرسال كود التحقق. أرسله هنا:")
            
        except Exception as e:
            await event.reply(f"❌ خطأ: {e}")
            del login_states[user_id]
    
    # الخطوة 4: كود التحقق
    elif step == 'code':
        try:
            await state['client'].sign_in(
                phone=state['phone'],
                code=text,
                phone_code_hash=state['phone_code_hash']
            )
            await finish_login(event, state)
            
        except SessionPasswordNeededError:
            state['step'] = 'password'
            await event.reply("🔒 حسابك مفعل عليه تحقق بخطوتين\nأرسل كلمة المرور:")
            
        except Exception as e:
            await event.reply(f"❌ خطأ: {e}\nحاول مرة أخرى أو /cancel")
    
    # الخطوة 5: كلمة المرور (تحقق بخطوتين)
    elif step == 'password':
        try:
            await state['client'].sign_in(password=text)
            await finish_login(event, state)
        except Exception as e:
            await event.reply(f"❌ كلمة مرور خاطئة: {e}")

async def finish_login(event, state):
    """إكمال تسجيل الدخول"""
    user_id = event.sender_id
    
    try:
        # حفظ الجلسة
        session_string = state['client'].session.save()
        
        # تشفير وتخزين البيانات
        sessions[user_id] = {
            'api_id': encrypt(str(state['api_id'])),
            'api_hash': encrypt(state['api_hash']),
            'phone': encrypt(state['phone']),
            'session': encrypt(session_string)
        }
        
        # معلومات الحساب
        me = await state['client'].get_me()
        
        await event.reply(
            f"✅ **تم تسجيل الدخول بنجاح!**\n\n"
            f"👤 الاسم: {me.first_name}\n"
            f"📱 الهاتف: {me.phone}\n"
            f"🆔 المعرف: {me.id}\n\n"
            f"🚀 أرسل /run لتشغيل البوت\n"
            f"📊 أرسل /status للحالة"
        )
        
    except Exception as e:
        await event.reply(f"❌ خطأ في الحفظ: {e}")
    
    finally:
        # تنظيف
        try:
            await state['client'].disconnect()
        except:
            pass
        del login_states[user_id]

# ==================== تشغيل البوت ====================

async def main():
    """تشغيل البوت"""
    print("=" * 50)
    print("جاري تشغيل البوت...")
    
    try:
        await bot.start(bot_token=BOT_TOKEN)
        me = await bot.get_me()
        
        print(f"✅ البوت شغال: @{me.username}")
        print(f"🆔 Bot ID: {me.id}")
        print("=" * 50)
        
        await bot.run_until_disconnected()
        
    except Exception as e:
        logger.error(f"خطأ في التشغيل: {e}")
        print(f"❌ خطأ: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 تم إيقاف البوت")
    except Exception as e:
        print(f"❌ خطأ: {e}")
