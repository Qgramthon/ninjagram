# NinjaGram Pro Max Ultra - Telegram Security Tools Bot (WORKING VERSION)
import asyncio, uuid, os, re, random, string, aiohttp, json, time, io, logging, hashlib, base64
from datetime import datetime, timedelta
from urllib.parse import quote
from telethon import TelegramClient, events, Button, functions, types
from telethon.errors import *
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.messages import CheckChatInviteRequest
from collections import defaultdict, deque
from typing import Optional, Dict, List, Set, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import asyncio

# ==================== الإعدادات ====================
DATA_DIR = '/data' if os.path.exists('/data') else '.'
os.makedirs(DATA_DIR, exist_ok=True)

BOT_TOKEN = '7998616214:AAFGroKKmwnrOtyAeJIHmrs_bKW5jXl0B20'
BOT_API_ID = 2040
BOT_API_HASH = 'b18441a1ff607e10a989891a5462e627'
DEV_USER_ID = 6443238809

# ==================== التهيئة ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# إنشاء عميل تيليجرام
bot = TelegramClient('bot_session_main', BOT_API_ID, BOT_API_HASH)

# متغيرات عامة
user_states: Dict[int, str] = {}
pending_data: Dict[int, Dict] = {}
rate_limiter: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10))
allowed_chats: Set[int] = set()
username_cache: Dict[str, Tuple[float, Optional[str]]] = {}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36"
]

# ==================== دوال مساعدة ====================
def is_dev(user_id: int) -> bool:
    return user_id == DEV_USER_ID

def check_rate(user_id: int, action: str, max_req: int = 10) -> bool:
    """فحص معدل الطلبات"""
    now = time.time()
    key = f"{user_id}:{action}"
    if key not in rate_limiter:
        rate_limiter[key] = deque(maxlen=max_req)
    user_reqs = rate_limiter[key]
    while user_reqs and user_reqs[0] < now - 60:
        user_reqs.popleft()
    if len(user_reqs) >= max_req:
        return False
    user_reqs.append(now)
    return True

def validate_username(username: str) -> bool:
    """التحقق من صحة اليوزر"""
    return bool(re.match(r'^[a-zA-Z][a-zA-Z0-9_]{3,31}$', username))

# ==================== نظام OSINT ====================
class OSINT:
    @staticmethod
    async def analyze_account(entity) -> Dict:
        """تحليل شامل للحساب"""
        try:
            result = {
                "basic": {},
                "security": [],
                "risk_score": 0,
                "creation_date": None,
                "age_days": None,
                "emails": [],
                "phones": []
            }
            
            # معلومات أساسية
            result["basic"] = {
                "id": entity.id,
                "username": getattr(entity, 'username', None),
                "first_name": getattr(entity, 'first_name', ''),
                "last_name": getattr(entity, 'last_name', ''),
                "phone_visible": getattr(entity, 'phone', None) is not None,
                "verified": getattr(entity, 'verified', False),
                "premium": getattr(entity, 'premium', False),
                "bot": getattr(entity, 'bot', False),
                "scam": getattr(entity, 'scam', False),
                "fake": getattr(entity, 'fake', False),
            }
            
            # تقدير عمر الحساب
            result["creation_date"] = OSINT._estimate_date(entity.id)
            if result["creation_date"]:
                result["age_days"] = (datetime.now() - result["creation_date"]).days
            
            # تحليل الأمان
            risk = 0
            if not result["basic"]["username"]:
                result["security"].append("❌ لا يوجد يوزر عام")
                risk += 20
            if result["basic"]["phone_visible"]:
                result["security"].append("⚠️ رقم الهاتف مكشوف")
                risk += 40
            if result["basic"]["scam"]:
                result["security"].append("🚫 حساب احتيال")
                risk += 80
            if result["basic"]["fake"]:
                result["security"].append("⚠️ حساب مزيف")
                risk += 60
            if result["age_days"] and result["age_days"] < 30:
                result["security"].append("🆕 حساب جديد (< 30 يوم)")
                risk += 25
            
            result["risk_score"] = min(risk, 100)
            
            # جلب معلومات إضافية
            async with aiohttp.ClientSession() as session:
                headers = {'User-Agent': random.choice(USER_AGENTS)}
                
                if result["basic"]["username"]:
                    url = f"https://t.me/{result['basic']['username']}"
                    try:
                        async with session.get(url, headers=headers, timeout=10) as resp:
                            text = await resp.text()
                            
                            # استخراج الإيميلات
                            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
                            result["emails"] = list(set(emails))[:5]
                            
                            # استخراج الأرقام
                            phones = re.findall(r'\+?[\d]{8,15}', text)
                            result["phones"] = list(set(phones))[:5]
                            
                            if emails or phones:
                                risk += 20
                                result["security"].append("⚠️ بيانات حساسة مكشوفة في البايو")
                    except:
                        pass
            
            result["risk_score"] = min(risk, 100)
            
            return result
            
        except Exception as e:
            logger.error(f"OSINT Error: {e}")
            return {"error": str(e)[:100]}
    
    @staticmethod
    def _estimate_date(user_id: int) -> Optional[datetime]:
        """تقدير تاريخ إنشاء الحساب"""
        milestones = {
            1000000: datetime(2014, 9, 1),
            1000000000: datetime(2017, 6, 20),
            3000000000: datetime(2019, 1, 10),
            5000000000: datetime(2020, 9, 5),
            6000000000: datetime(2021, 6, 15),
            7000000000: datetime(2022, 8, 20),
            8000000000: datetime(2024, 1, 1),
        }
        
        for mid, mdate in milestones.items():
            if user_id < mid:
                return mdate
        
        return datetime(2024, 6, 1)

# ==================== القوائم والأزرار ====================
def main_menu():
    return [
        [Button.inline("🕵️ تحليل OSINT", b"osint_menu"),
         Button.inline("💣 فحص يوزر", b"check_user")],
        [Button.inline("🔍 فحص تسريبات", b"breach_menu"),
         Button.inline("🔗 تحليل رابط", b"link_menu")],
        [Button.inline("📝 صانع رسائل", b"msg_menu"),
         Button.inline("📋 بلاغات", b"report_menu")],
        [Button.inline("🎯 صيد يوزرات", b"hunt_menu"),
         Button.inline("📊 إحصائيات", b"stats")],
        [Button.inline("ℹ️ معلومات", b"info")]
    ]

def osint_menu_buttons():
    return [
        [Button.inline("👤 تحليل يوزر", b"osint_username"),
         Button.inline("🆔 تحليل ID", b"osint_id")],
        [Button.inline("📊 تحليل شامل", b"osint_full")],
        [Button.inline("🔙 رجوع", b"main_menu")]
    ]

def msg_menu_buttons():
    return [
        [Button.inline("📩 طلب فك حظر", b"unban_request"),
         Button.inline("📝 رسالة مخصصة", b"custom_msg")],
        [Button.inline("🔙 رجوع", b"main_menu")]
    ]

def report_menu_buttons():
    return [
        [Button.inline("📋 بلاغ سبام", b"report_spam"),
         Button.inline("📋 بلاغ احتيال", b"report_fraud")],
        [Button.inline("📋 بلاغ انتحال", b"report_impersonation"),
         Button.inline("📋 بلاغ مضايقة", b"report_harassment")],
        [Button.inline("🔙 رجوع", b"main_menu")]
    ]

def hunt_menu_buttons():
    return [
        [Button.inline("🎯 صيد ذكي", b"hunt_smart"),
         Button.inline("⚡ صيد سريع", b"hunt_fast")],
        [Button.inline("🔙 رجوع", b"main_menu")]
    ]

# ==================== معالج البداية ====================
@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    """معالج أمر البداية"""
    try:
        user_id = event.sender_id
        user_name = event.sender.first_name or "مستخدم"
        allowed_chats.add(event.chat_id)
        
        caption = f"""
🧨 **NinjaGram Pro Max Ultra**

مرحباً {user_name}! 👋

🛡️ **أقوى بوت أدوات تيليجرام الأمنية**

⚡ **الخدمات المتاحة:**
• 🕵️ تحليل OSINT متقدم للحسابات
• 🧬 استخراج بصمة الحساب الكاملة
• 💣 فحص يوزرات (متاح/محظور/محذوف)
• 🔍 فحص تسريبات البيانات
• 🔗 تحليل وفك روابط تيليجرام
• 📝 صانع رسائل وطلبات فك حظر
• 📋 مولد بلاغات احترافية
• 🎯 صيد يوزرات ذكي

⚠️ **للأغراض التعليمية والأمنية فقط**

📢 **Channel:** @Q_g_r_a_m
👨‍💻 **Developer:** @NinjaGram
        """
        
        # محاولة إرسال الصورة إذا وجدت
        start_img = "start.jpg"
        if os.path.exists(start_img):
            await bot.send_file(
                event.chat_id,
                start_img,
                caption=caption,
                buttons=main_menu(),
                parse_mode='md'
            )
        else:
            await event.respond(
                caption,
                buttons=main_menu(),
                parse_mode='md'
            )
            
        logger.info(f"User {user_id} ({user_name}) started the bot")
        
    except Exception as e:
        logger.error(f"Start Error: {e}")
        await event.respond("✅ **البوت يعمل!**\n\nاختر الخدمة:", buttons=main_menu(), parse_mode='md')

# ==================== الرجوع للقائمة الرئيسية ====================
@bot.on(events.CallbackQuery(data=b"main_menu"))
async def back_to_main(event):
    try:
        await event.edit(
            "🧨 **NinjaGram Pro Max Ultra**\n\nاختر الخدمة المطلوبة:",
            buttons=main_menu(),
            parse_mode='md'
        )
    except Exception as e:
        logger.error(f"Main menu error: {e}")

# ==================== تحليل OSINT ====================
@bot.on(events.CallbackQuery(data=b"osint_menu"))
async def osint_menu(event):
    await event.edit(
        "🕵️ **نظام تحليل OSINT**\n\nاختر نوع التحليل:",
        buttons=osint_menu_buttons(),
        parse_mode='md'
    )

@bot.on(events.CallbackQuery(data=b"osint_username"))
async def osint_username(event):
    user_id = event.sender_id
    user_states[user_id] = "osint_username"
    await event.edit(
        "🕵️ **تحليل حساب باليوزر**\n\n📤 أرسل اليوزر مباشرة:\nمثال: @username أو username",
        buttons=[[Button.inline("🔙 رجوع", b"osint_menu")]],
        parse_mode='md'
    )

@bot.on(events.CallbackQuery(data=b"osint_id"))
async def osint_id(event):
    user_id = event.sender_id
    user_states[user_id] = "osint_id"
    await event.edit(
        "🕵️ **تحليل حساب بالـ ID**\n\n📤 أرسل الآيدي الرقمي:\nمثال: 6443238809",
        buttons=[[Button.inline("🔙 رجوع", b"osint_menu")]],
        parse_mode='md'
    )

@bot.on(events.CallbackQuery(data=b"osint_full"))
async def osint_full(event):
    user_id = event.sender_id
    user_states[user_id] = "osint_full"
    await event.edit(
        "🕵️ **تحليل شامل**\n\n📤 أرسل اليوزر أو الآيدي:\nمثال: @username أو 6443238809",
        buttons=[[Button.inline("🔙 رجوع", b"osint_menu")]],
        parse_mode='md'
    )

# ==================== معالج رسائل المستخدمين ====================
@bot.on(events.NewMessage(func=lambda e: e.sender_id in user_states and not e.text.startswith('/')))
async def handle_user_input(event):
    user_id = event.sender_id
    state = user_states.get(user_id)
    
    if not state:
        return
    
    user_input = event.text.strip()
    
    try:
        if state.startswith("osint_"):
            await handle_osint_input(event, user_id, state, user_input)
        
        elif state == "check_username":
            await handle_check_username(event, user_id, user_input)
        
        elif state == "check_breach":
            await handle_breach_check(event, user_id, user_input)
        
        elif state == "link_analysis":
            await handle_link_analysis(event, user_id, user_input)
        
        elif state.startswith("unban_"):
            await handle_unban_flow(event, user_id, state, user_input)
        
        elif state.startswith("report_"):
            await handle_report_flow(event, user_id, state, user_input)
        
        elif state.startswith("hunt_"):
            await handle_hunt(event, user_id, state, user_input)
        
        else:
            user_states.pop(user_id, None)
            
    except Exception as e:
        logger.error(f"Input handler error: {e}")
        await event.respond(f"❌ حدث خطأ: {str(e)[:100]}", buttons=[[Button.inline("🔙 رجوع", b"main_menu")]])

# ==================== معالج OSINT ====================
async def handle_osint_input(event, user_id, state, user_input):
    """معالجة طلبات OSINT"""
    
    loading_msg = await event.respond("🕵️ **جاري التحليل...** ⏳", parse_mode='md')
    
    try:
        # جلب الكيان
        if user_input.replace("@", "").isdigit() or state == "osint_id":
            if user_input.startswith('@'):
                user_input = user_input[1:]
            if user_input.isdigit():
                entity = await bot.get_entity(int(user_input))
            else:
                entity = await bot.get_entity(user_input)
        else:
            username = user_input.replace("@", "")
            entity = await bot.get_entity(username)
        
        if not entity:
            await loading_msg.edit("❌ لم يتم العثور على الحساب", buttons=[[Button.inline("🔙 رجوع", b"osint_menu")]])
            user_states.pop(user_id, None)
            return
        
        # تحليل الحساب
        result = await OSINT.analyze_account(entity)
        
        if "error" in result:
            await loading_msg.edit(f"❌ {result['error']}", buttons=[[Button.inline("🔙 رجوع", b"osint_menu")]])
            user_states.pop(user_id, None)
            return
        
        # بناء التقرير
        basic = result["basic"]
        text = "🕵️ **تقرير التحليل الأمني**\n\n"
        text += "═" * 30 + "\n\n"
        
        text += "📋 **المعلومات الأساسية:**\n"
        text += f"• 🆔 ID: `{basic['id']}`\n"
        text += f"• 🔖 يوزر: @{basic['username'] if basic['username'] else 'لا يوجد'}\n"
        text += f"• 👤 الاسم: {basic['first_name']} {basic['last_name']}\n"
        text += f"• 📞 الهاتف: {'⚠️ مكشوف' if basic['phone_visible'] else '✅ مخفي'}\n"
        text += f"• ✅ موثق: {'نعم' if basic['verified'] else 'لا'}\n"
        text += f"• ⭐ بريميوم: {'نعم' if basic['premium'] else 'لا'}\n"
        text += f"• 🤖 بوت: {'نعم' if basic['bot'] else 'لا'}\n"
        text += f"• 🚫 احتيال: {'⚠️ نعم' if basic['scam'] else '✅ لا'}\n"
        text += f"• ⚠️ مزيف: {'نعم' if basic['fake'] else 'لا'}\n\n"
        
        if result["creation_date"]:
            text += f"📅 **تاريخ الإنشاء التقريبي:** {result['creation_date'].strftime('%Y-%m-%d')}\n"
            text += f"⏳ **عمر الحساب:** {result['age_days']} يوم\n\n"
        
        if result["security"]:
            text += "⚠️ **تحليل الأمان:**\n"
            for issue in result["security"]:
                text += f"• {issue}\n"
            text += "\n"
        
        text += f"🎯 **درجة الخطورة:** {result['risk_score']}/100\n"
        
        if result['risk_score'] < 30:
            text += "📊 **التصنيف:** 🟢 آمن"
        elif result['risk_score'] < 60:
            text += "📊 **التصنيف:** 🟡 مشبوه"
        else:
            text += "📊 **التصنيف:** 🔴 خطر"
        
        if result["emails"]:
            text += f"\n\n📧 **إيميلات مكشوفة:**\n" + "\n".join([f"• `{e}`" for e in result["emails"]])
        
        if result["phones"]:
            text += f"\n\n📞 **أرقام مكشوفة:**\n" + "\n".join([f"• `{p}`" for p in result["phones"]])
        
        await loading_msg.edit(text, buttons=[[Button.inline("🔄 تحليل آخر", b"osint_menu"), 
                                                  Button.inline("🔙 الرئيسية", b"main_menu")]], parse_mode='md')
        
    except ValueError:
        await loading_msg.edit("❌ لم يتم العثور على الحساب", buttons=[[Button.inline("🔙 رجوع", b"osint_menu")]])
    except Exception as e:
        await loading_msg.edit(f"❌ خطأ: {str(e)[:100]}", buttons=[[Button.inline("🔙 رجوع", b"osint_menu")]])
    finally:
        user_states.pop(user_id, None)

# ==================== فحص يوزر ====================
@bot.on(events.CallbackQuery(data=b"check_user"))
async def check_user_start(event):
    user_id = event.sender_id
    user_states[user_id] = "check_username"
    await event.edit(
        "💣 **فحص اليوزر**\n\n📤 أرسل اليوزر للفحص:\nمثال: @username",
        buttons=[[Button.inline("🔙 رجوع", b"main_menu")]],
        parse_mode='md'
    )

async def handle_check_username(event, user_id, username):
    username = username.replace("@", "")
    
    if not validate_username(username):
        await event.respond("❌ يوزر غير صالح", buttons=[[Button.inline("🔙 رجوع", b"main_menu")]])
        user_states.pop(user_id, None)
        return
    
    loading_msg = await event.respond(f"💣 **جاري فحص @{username}...**", parse_mode='md')
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {'User-Agent': random.choice(USER_AGENTS)}
            url = f"https://t.me/{username}"
            
            async with session.get(url, headers=headers, timeout=10) as resp:
                status = resp.status
                text = await resp.text()
                
                result_text = f"💣 **نتيجة فحص @{username}**\n\n"
                
                if status == 404:
                    result_text += "✅ **اليوزر متاح للحجز!** 🎉\n\nيمكنك حجز هذا اليوزر الآن"
                
                elif status == 200:
                    if "tgme_page" in text:
                        if "account has been suspended" in text.lower():
                            result_text += "🚫 **الحساب محظور من تيليجرام**\n\nتم تعليق هذا الحساب من قبل إدارة تيليجرام"
                        elif "Deactivated Account" in text:
                            result_text += "🗑️ **الحساب محذوف**\n\nتم حذف هذا الحساب من قبل صاحبه"
                        else:
                            result_text += "❌ **اليوزر محجوز**\n\nالحساب موجود ونشط ✅"
                    else:
                        result_text += "❌ **اليوزر محجوز**\n\nالحساب موجود ✅"
                
                else:
                    result_text += f"⚠️ حالة غير متوقعة: {status}"
                
                await loading_msg.edit(result_text, 
                    buttons=[[Button.inline("🔄 فحص آخر", b"check_user"), 
                             Button.inline("🔙 رجوع", b"main_menu")]], 
                    parse_mode='md')
    
    except Exception as e:
        await loading_msg.edit(f"❌ خطأ في الفحص: {str(e)[:100]}", 
            buttons=[[Button.inline("🔙 رجوع", b"main_menu")]])
    finally:
        user_states.pop(user_id, None)

# ==================== فحص تسريبات ====================
@bot.on(events.CallbackQuery(data=b"breach_menu"))
async def breach_menu(event):
    user_id = event.sender_id
    user_states[user_id] = "check_breach"
    await event.edit(
        "🔍 **فحص تسريبات البيانات**\n\n"
        "📤 أرسل الإيميل أو رقم الهاتف:\n"
        "مثال: example@email.com\n"
        "أو: +201234567890",
        buttons=[[Button.inline("🔙 رجوع", b"main_menu")]],
        parse_mode='md'
    )

async def handle_breach_check(event, user_id, query):
    loading_msg = await event.respond("🔍 **جاري الفحص...**", parse_mode='md')
    
    try:
        if '@' in query:
            # فحص إيميل
            sha1_email = hashlib.sha1(query.encode()).hexdigest().upper()
            prefix = sha1_email[:5]
            suffix = sha1_email[5:]
            
            async with aiohttp.ClientSession() as session:
                url = f"https://api.pwnedpasswords.com/range/{prefix}"
                headers = {'User-Agent': 'NinjaGram'}
                async with session.get(url, headers=headers, timeout=10) as resp:
                    text = await resp.text()
                    
                    found = False
                    count = 0
                    for line in text.splitlines():
                        if suffix in line:
                            count = int(line.split(':')[1])
                            found = True
                            break
                    
                    if found:
                        risk = "🔴 خطر" if count > 100 else "🟡 متوسط" if count > 10 else "🟢 منخفض"
                        result_text = f"⚠️ **تحذير!**\n\n"
                        result_text += f"📧 الإيميل: `{query}`\n"
                        result_text += f"🔢 عدد التسريبات: {count}\n"
                        result_text += f"📊 مستوى الخطورة: {risk}\n\n"
                        result_text += "💡 **توصية:** قم بتغيير كلمة المرور فوراً!"
                    else:
                        result_text = f"✅ **جيد!**\n\nالإيميل `{query}` غير موجود في التسريبات المعروفة"
        else:
            # تحليل رقم هاتف
            clean = re.sub(r'[^\d+]', '', query)
            result_text = f"📞 **تحليل رقم الهاتف**\n\n"
            result_text += f"الرقم: {query}\n"
            result_text += f"صالح: {'✅' if len(clean) >= 8 else '❌'}\n"
            
            country_codes = {
                "20": "مصر 🇪🇬", "966": "السعودية 🇸🇦", "971": "الإمارات 🇦🇪",
                "965": "الكويت 🇰🇼", "974": "قطر 🇶🇦", "973": "البحرين 🇧🇭",
                "968": "عمان 🇴🇲", "962": "الأردن 🇯🇴", "964": "العراق 🇮🇶",
                "963": "سوريا 🇸🇾", "961": "لبنان 🇱🇧", "970": "فلسطين 🇵🇸",
            }
            
            if clean.startswith('+'):
                clean = clean[1:]
            
            for code, country in country_codes.items():
                if clean.startswith(code):
                    result_text += f"الدولة: {country}\n"
                    break
        
        await loading_msg.edit(result_text, 
            buttons=[[Button.inline("🔄 فحص آخر", b"breach_menu"), 
                     Button.inline("🔙 رجوع", b"main_menu")]], 
            parse_mode='md')
    
    except Exception as e:
        await loading_msg.edit(f"❌ خطأ: {str(e)[:100]}", 
            buttons=[[Button.inline("🔙 رجوع", b"main_menu")]])
    finally:
        user_states.pop(user_id, None)

# ==================== تحليل الروابط ====================
@bot.on(events.CallbackQuery(data=b"link_menu"))
async def link_menu(event):
    user_id = event.sender_id
    user_states[user_id] = "link_analysis"
    await event.edit(
        "🔗 **تحليل روابط تيليجرام**\n\n"
        "📤 أرسل رابط تيليجرام:\n"
        "مثال: https://t.me/username\n"
        "أو: https://t.me/+xxxxx",
        buttons=[[Button.inline("🔙 رجوع", b"main_menu")]],
        parse_mode='md'
    )

async def handle_link_analysis(event, user_id, link):
    loading_msg = await event.respond("🔗 **جاري تحليل الرابط...**", parse_mode='md')
    
    try:
        result_text = "🔗 **نتيجة التحليل**\n\n"
        result_text += f"📎 الرابط: {link}\n\n"
        
        # استخراج المعلومات
        patterns = {
            "public": r'(?:https?://)?t(?:elegram)?\.me/([a-zA-Z][a-zA-Z0-9_]{3,31})',
            "private_old": r'(?:https?://)?t(?:elegram)?\.me/joinchat/([a-zA-Z0-9_-]+)',
            "private_new": r'(?:https?://)?t(?:elegram)?\.me/\+(.+)',
            "tg_resolve": r'tg://resolve\?domain=([a-zA-Z][a-zA-Z0-9_]+)',
        }
        
        found = False
        for link_type, pattern in patterns.items():
            match = re.search(pattern, link)
            if match:
                found = True
                identifier = match.group(1)
                
                if link_type in ["private_old", "private_new"]:
                    result_text += "🔒 **رابط دعوة خاص**\n"
                    result_text += f"🔑 المعرف: `{identifier}`\n"
                    
                    try:
                        check = await bot(CheckChatInviteRequest(identifier))
                        result_text += f"📝 الاسم: {getattr(check, 'title', 'غير معروف')}\n"
                        result_text += f"👥 الأعضاء: {getattr(check, 'participants_count', 'غير معروف')}\n"
                    except InviteHashExpiredError:
                        result_text += "⚠️ الرابط منتهي الصلاحية\n"
                    except:
                        result_text += "⚠️ تعذر التحقق من الرابط\n"
                
                else:
                    result_text += f"🔖 **يوزر: @{identifier}**\n"
                    
                    try:
                        entity = await bot.get_entity(identifier)
                        if hasattr(entity, 'bot') and entity.bot:
                            entity_type = "🤖 بوت"
                        elif hasattr(entity, 'broadcast') and entity.broadcast:
                            entity_type = "📢 قناة"
                        elif hasattr(entity, 'megagroup') and entity.megagroup:
                            entity_type = "👥 جروب"
                        else:
                            entity_type = "👤 حساب شخصي"
                        
                        result_text += f"📋 النوع: {entity_type}\n"
                        result_text += f"🆔 ID: `{entity.id}`\n"
                    except:
                        result_text += "⚠️ تعذر الوصول للكيان\n"
                
                break
        
        if not found:
            result_text += "❌ **هذا ليس رابط تيليجرام صالح**"
        
        await loading_msg.edit(result_text, 
            buttons=[[Button.inline("🔄 تحليل آخر", b"link_menu"), 
                     Button.inline("🔙 رجوع", b"main_menu")]], 
            parse_mode='md')
    
    except Exception as e:
        await loading_msg.edit(f"❌ خطأ: {str(e)[:100]}", 
            buttons=[[Button.inline("🔙 رجوع", b"main_menu")]])
    finally:
        user_states.pop(user_id, None)

# ==================== صانع الرسائل وطلبات فك الحظر ====================
@bot.on(events.CallbackQuery(data=b"msg_menu"))
async def msg_menu_handler(event):
    await event.edit(
        "📝 **صانع الرسائل**\n\nاختر الخدمة:",
        buttons=msg_menu_buttons(),
        parse_mode='md'
    )

@bot.on(events.CallbackQuery(data=b"unban_request"))
async def unban_start(event):
    user_id = event.sender_id
    pending_data[user_id] = {}
    user_states[user_id] = "unban_group"
    await event.edit(
        "📩 **صانع طلب فك الحظر**\n\n"
        "📤 أرسل اسم الجروب أولاً:\n"
        "مثال: جروب المبرمجين العرب",
        buttons=[[Button.inline("🔙 رجوع", b"msg_menu")]],
        parse_mode='md'
    )

async def handle_unban_flow(event, user_id, state, user_input):
    if state == "unban_group":
        pending_data[user_id]["group"] = user_input
        user_states[user_id] = "unban_name"
        await event.respond(
            "📤 الآن أرسل اسمك الذي ظهرت به في الجروب:",
            buttons=[[Button.inline("🔙 إلغاء", b"msg_menu")]]
        )
    
    elif state == "unban_name":
        pending_data[user_id]["name"] = user_input
        user_states[user_id] = "unban_reason"
        await event.respond(
            "📤 ما سبب الحظر؟\n"
            "1️⃣ سبام\n2️⃣ روابط\n3️⃣ إعلانات\n4️⃣ سلوك غير لائق\n5️⃣ أخرى",
            buttons=[[Button.inline("🔙 إلغاء", b"msg_menu")]]
        )
    
    elif state == "unban_reason":
        reason_map = {"1": "سبام", "2": "روابط", "3": "إعلانات", "4": "سلوك غير لائق", "5": "أخرى"}
        reason = reason_map.get(user_input, user_input)
        
        data = pending_data.pop(user_id, {})
        user_states.pop(user_id, None)
        
        template = f"""
📩 **طلب فك حظر**

السلام عليكم ورحمة الله،

أنا العضو: **{data.get('name', '')}**

أتقدم بطلب فك الحظر من جروب: **{data.get('group', '')}**

سبب الحظر: {reason}

أتعهد بالالتزام بقوانين الجروب وعدم تكرار المخالفة.

وشكراً لتفهمكم 🌹
        """
        
        await event.respond(
            template.strip(),
            buttons=[[Button.inline("🔙 رجوع", b"msg_menu")]],
            parse_mode='md'
        )

# ==================== مولد البلاغات ====================
@bot.on(events.CallbackQuery(data=b"report_menu"))
async def report_menu_handler(event):
    await event.edit(
        "📋 **مولد البلاغات**\n\nاختر نوع البلاغ:",
        buttons=report_menu_buttons(),
        parse_mode='md'
    )

@bot.on(events.CallbackQuery(data=re.compile(rb"report_(.+)")))
async def report_type_handler(event):
    report_type = event.data.decode().replace("report_", "")
    user_id = event.sender_id
    
    pending_data[user_id] = {"type": report_type}
    user_states[user_id] = f"report_target"
    
    type_names = {
        "spam": "سبام", "fraud": "احتيال", 
        "impersonation": "انتحال شخصية", "harassment": "مضايقة"
    }
    
    await event.edit(
        f"📋 **بلاغ {type_names.get(report_type, report_type)}**\n\n"
        "📤 أرسل يوزر الحساب المبلغ عنه:\n"
        "مثال: @bad_account",
        buttons=[[Button.inline("🔙 رجوع", b"report_menu")]],
        parse_mode='md'
    )

async def handle_report_flow(event, user_id, state, user_input):
    if state == "report_target":
        data = pending_data.get(user_id, {})
        report_type = data.get("type", "spam")
        target = user_input.replace("@", "")
        
        type_descriptions = {
            "spam": "إرسال رسائل مزعجة وغير مرغوب فيها (سبام)",
            "fraud": "الاحتيال والنصب على المستخدمين",
            "impersonation": "انتحال شخصية/جهة رسمية",
            "harassment": "مضايقة وترهيب المستخدمين"
        }
        
        report_id = uuid.uuid4().hex[:8].upper()
        
        report_text = f"""
📋 **تقرير بلاغ - تيليجرام**
Report ID: #{report_id}

👤 **المبلغ عنه:** @{target}
⚠️ **نوع المخالفة:** {type_descriptions.get(report_type, '')}
📅 **تاريخ البلاغ:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

📝 **وصف المخالفة:**
• {type_descriptions.get(report_type, '')}

📎 **يرجى إرفاق:**
• لقطات شاشة للمخالفة
• روابط المحادثات
• أي أدلة إضافية

📧 **إرسال البلاغ إلى:**
• abuse@telegram.org
• @NoedScam (للاحتيال)
• Telegram Support

⚠️ هذا البلاغ مُعد للأغراض المشروعة فقط
        """
        
        user_states.pop(user_id, None)
        pending_data.pop(user_id, None)
        
        await event.respond(
            report_text.strip(),
            buttons=[[Button.inline("📋 بلاغ آخر", b"report_menu"), 
                     Button.inline("🔙 رجوع", b"main_menu")]],
            parse_mode='md'
        )

# ==================== صيد اليوزرات ====================
@bot.on(events.CallbackQuery(data=b"hunt_menu"))
async def hunt_menu_handler(event):
    await event.edit(
        "🎯 **صيد اليوزرات**\n\nاختر طريقة الصيد:",
        buttons=hunt_menu_buttons(),
        parse_mode='md'
    )

@bot.on(events.CallbackQuery(data=re.compile(rb"hunt_(.+)")))
async def hunt_handler(event):
    hunt_type = event.data.decode().replace("hunt_", "")
    user_id = event.sender_id
    
    if not check_rate(user_id, "hunt", 5):
        await event.answer("⏳ انتظر قليلاً قبل المحاولة مرة أخرى", alert=True)
        return
    
    if hunt_type == "smart":
        count = 500
        await event.edit("🧠 **جاري الصيد الذكي...**\n⏳ قد يستغرق دقيقتين", parse_mode='md')
    else:
        count = 300
        await event.edit("⚡ **جاري الصيد السريع...**", parse_mode='md')
    
    # توليد يوزرات
    pool = set()
    letters = "abcdefghijklmnopqrstuvwxyz"
    vowels = "aeiou"
    consonants = "bcdfghjklmnpqrstvwxyz"
    lucky = ["777", "888", "999", "111", "333", "555"]
    
    for _ in range(count):
        c1, c2 = random.choice(consonants), random.choice(consonants)
        v = random.choice(vowels)
        n = random.choice("1379")
        l = random.choice(lucky)
        pool.update([f"{c1}{v}{c2}", f"{c1}{v}{n}", f"{c1}{l}", f"{l}{c1}", f"{c1}{c2}{n}"])
    
    pool = {u for u in pool if 3 <= len(u) <= 15}
    
    # فحص اليوزرات
    found = []
    checked = 0
    
    async with aiohttp.ClientSession() as session:
        sem = asyncio.Semaphore(30)
        
        async def check_one(u):
            nonlocal checked
            async with sem:
                try:
                    headers = {'User-Agent': random.choice(USER_AGENTS)}
                    url = f"https://t.me/{u}"
                    async with session.get(url, headers=headers, timeout=5) as resp:
                        if resp.status == 404:
                            found.append(u)
                except:
                    pass
                checked += 1
        
        tasks = [check_one(u) for u in list(pool)]
        await asyncio.gather(*tasks)
    
    if found:
        text = f"🎉 **نتائج الصيد**\n\n✅ تم العثور على {len(found)} يوزر متاح\n\n"
        text += "🏆 **أفضل اليوزرات:**\n"
        for i, u in enumerate(found[:20], 1):
            text += f"{i}. @{u}\n"
    else:
        text = "❌ لم يتم العثور على يوزرات متاحة، جرب مرة أخرى"
    
    await event.edit(text, 
        buttons=[[Button.inline("🔄 صيد مرة أخرى", b"hunt_menu"), 
                 Button.inline("🔙 رجوع", b"main_menu")]], 
        parse_mode='md')

# ==================== إحصائيات ومعلومات ====================
@bot.on(events.CallbackQuery(data=b"stats"))
async def stats_handler(event):
    active_users = len([u for u in user_states if user_states[u]])
    
    text = f"""
📊 **إحصائيات البوت**

👥 المستخدمين النشطين: {active_users}
💾 الكاش: {len(username_cache)}
🕵️ تحليلات OSINT: جاهز
💣 فحص يوزرات: جاهز
🔍 فحص تسريبات: جاهز
🔗 تحليل روابط: جاهز
📝 صانع رسائل: جاهز
📋 بلاغات: جاهز
🎯 صيد يوزرات: جاهز

⚡ **الإصدار:** v5.0
👨‍💻 **المطور:** @NinjaGram
📢 **القناة:** @Q_g_r_a_m
    """
    
    await event.edit(text, buttons=[[Button.inline("🔙 رجوع", b"main_menu")]], parse_mode='md')

@bot.on(events.CallbackQuery(data=b"info"))
async def info_handler(event):
    text = """
ℹ️ **عن البوت**

🧨 **NinjaGram Pro Max Ultra**
🛡️ بوت أدوات تيليجرام الأمنية

⚠️ **تنبيه مهم:**
هذا البوت للأغراض التعليمية والأمنية فقط.
أي استخدام غير أخلاقي يتحمل مسؤوليته المستخدم.

👨‍💻 **المطور:** @NinjaGram
📢 **القناة:** @Q_g_r_a_m
    """
    
    await event.edit(text, buttons=[[Button.inline("🔙 رجوع", b"main_menu")]], parse_mode='md')

# ==================== تشغيل البوت ====================
async def main():
    """الدالة الرئيسية لتشغيل البوت"""
    try:
        print("""
╔══════════════════════════════════════════╗
║     🧨 NinjaGram Pro Max Ultra         ║
║     Telegram Security & OSINT Bot       ║
║     Version: 5.0.0                      ║
║     Developer: @NinjaGram               ║
║     Channel: @Q_g_r_a_m                 ║
╚══════════════════════════════════════════╝
        """)
        
        logger.info("Starting bot...")
        
        # تشغيل البوت
        await bot.start(bot_token=BOT_TOKEN)
        
        # الحصول على معلومات البوت
        me = await bot.get_me()
        logger.info(f"Bot started as @{me.username} ({me.first_name})")
        print(f"✅ Bot is running as @{me.username}")
        print("📡 Waiting for commands...")
        
        # إبقاء البوت يعمل
        await bot.run_until_disconnected()
        
    except Exception as e:
        logger.error(f"Main error: {e}")
        print(f"❌ Error: {e}")
        
    finally:
        await bot.disconnect()

if __name__ == '__main__':
    # تشغيل البوت
    asyncio.run(main())
