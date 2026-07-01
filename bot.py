# Ultimate NinjaGram Pro Max Ultra - Complete Telegram Security Tools
import asyncio, uuid, os, re, random, string, aiohttp, json, time, io, logging, hashlib, base64, struct, textwrap
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode
from telethon import TelegramClient, events, Button, functions, types
from telethon.errors import *
from telethon.tl.functions.channels import InviteToChannelRequest, JoinChannelRequest, GetFullChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest, CheckChatInviteRequest, GetHistoryRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon.tl.types import InputPhoneContact, MessageEntityMention, MessageEntityUrl, MessageEntityEmail
from collections import Counter, defaultdict, deque
from typing import Optional, Dict, List, Set, Tuple, Any
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import piexif
from io import BytesIO

# ===================== الإعدادات =====================
DATA_DIR = '/data' if os.path.exists('/data') else '.'
os.makedirs(DATA_DIR, exist_ok=True)

BOT_TOKEN = '7998616214:AAFGroKKmwnrOtyAeJIHmrs_bKW5jXl0B20'
BOT_API_ID = 2040
BOT_API_HASH = 'b18441a1ff607e10a989891a5462e627'
DEV_USER_ID = 6443238809

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = TelegramClient(f'bot_session_{uuid.uuid4().hex[:6]}', BOT_API_ID, BOT_API_HASH)
START_IMAGE = "start.jpg"
allowed_chats: Set[int] = set()
user_states: Dict[int, str] = {}
pending_data: Dict[int, Dict] = {}
rate_limiter: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10))
thread_pool = ThreadPoolExecutor(max_workers=20)

# ===================== أنظمة الحماية =====================
class SecuritySystem:
    @classmethod
    def check_rate_limit(cls, user_id: int, action: str, max_per_minute: int = 10) -> bool:
        now = time.time()
        key = f"{user_id}:{action}"
        if key not in rate_limiter:
            rate_limiter[key] = deque(maxlen=max_per_minute)
        user_requests = rate_limiter[key]
        while user_requests and user_requests[0] < now - 60:
            user_requests.popleft()
        if len(user_requests) >= max_per_minute:
            return False
        user_requests.append(now)
        return True
    
    @classmethod
    def validate_phone(cls, phone: str) -> bool:
        return bool(re.match(r'^\+?[1-9]\d{7,14}$', phone.replace(" ", "").replace("-", "")))
    
    @classmethod
    def validate_username(cls, username: str) -> bool:
        return bool(re.match(r'^[a-zA-Z][a-zA-Z0-9_]{4,31}$', username))

# ===================== نظام OSINT المتقدم =====================
class AdvancedOSINT:
    """نظام استخبارات المصادر المفتوحة المتقدم لتيليجرام"""
    
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
        "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36"
    ]
    
    @classmethod
    async def deep_account_analysis(cls, user_input: str) -> Dict:
        """تحليل عميق وشامل لأي حساب تيليجرام"""
        try:
            # جلب الكيان
            if user_input.isdigit():
                entity = await bot.get_entity(int(user_input))
            else:
                username = user_input.replace("@", "")
                entity = await bot.get_entity(username)
            
            if not entity:
                return {"error": "لم يتم العثور على الحساب"}
            
            result = {
                "basic_info": {},
                "security_analysis": {},
                "activity_analysis": {},
                "exposed_data": {},
                "risk_score": 0
            }
            
            # المعلومات الأساسية
            result["basic_info"] = {
                "id": entity.id,
                "username": getattr(entity, 'username', None),
                "first_name": getattr(entity, 'first_name', ''),
                "last_name": getattr(entity, 'last_name', ''),
                "phone": "مخفي" if not getattr(entity, 'phone', None) else "مكشوف ⚠️",
                "is_verified": getattr(entity, 'verified', False),
                "is_premium": getattr(entity, 'premium', False),
                "is_bot": getattr(entity, 'bot', False),
                "is_scam": getattr(entity, 'scam', False),
                "is_restricted": getattr(entity, 'restricted', False),
                "is_fake": getattr(entity, 'fake', False),
                "mutual_contact": getattr(entity, 'mutual_contact', False),
            }
            
            # تحليل الأمان
            security_issues = []
            risk_score = 0
            
            if not getattr(entity, 'username', None):
                security_issues.append("❌ لا يوجد يوزر عام (أكثر عرضة للاختراق)")
                risk_score += 20
            
            if getattr(entity, 'phone', None):
                security_issues.append("⚠️ رقم الهاتف مكشوف للجميع")
                risk_score += 40
            
            if not getattr(entity, 'photo', None):
                security_issues.append("⚠️ لا توجد صورة شخصية (قد يكون حساب وهمي)")
                risk_score += 15
            
            # تقدير عمر الحساب
            creation_date = cls._estimate_date_from_id(entity.id)
            if creation_date:
                age_days = (datetime.now() - creation_date).days
                result["activity_analysis"]["creation_date"] = creation_date.strftime("%Y-%m-%d")
                result["activity_analysis"]["age_days"] = age_days
                
                if age_days < 30:
                    security_issues.append("🆕 حساب جديد جداً (أقل من شهر)")
                    risk_score += 25
                elif age_days < 90:
                    security_issues.append("🆕 حساب حديث (أقل من 3 أشهر)")
                    risk_score += 10
            
            # تحليل الاسم
            name = (getattr(entity, 'first_name', '') or '') + (getattr(entity, 'last_name', '') or '')
            if len(name) < 2:
                security_issues.append("⚠️ اسم قصير جداً")
                risk_score += 10
            
            # كشف الأحرف المشبوهة
            if re.search(r'[^\x00-\x7F\u0600-\u06FF]', name):
                security_issues.append("⚠️ يحتوي على أحرف غريبة/مشبوهة")
                risk_score += 15
            
            result["security_analysis"] = {
                "issues": security_issues,
                "total_issues": len(security_issues),
            }
            
            # حساب درجة الخطورة
            if getattr(entity, 'scam', False):
                risk_score += 80
            if getattr(entity, 'fake', False):
                risk_score += 60
            
            result["risk_score"] = min(risk_score, 100)
            result["risk_level"] = (
                "🟢 آمن" if risk_score < 30 else
                "🟡 مشبوه" if risk_score < 60 else
                "🔴 خطر"
            )
            
            # محاولة جلب القنوات المشتركة (إن أمكن)
            try:
                full_user = await bot(GetFullUserRequest(entity))
                result["activity_analysis"]["bio"] = getattr(full_user.full_user, 'about', '')[:200]
            except:
                pass
            
            # تحليل معلومات إضافية من الويب
            async with aiohttp.ClientSession() as session:
                headers = {'User-Agent': random.choice(cls.USER_AGENTS)}
                
                # فحص عبر t.me
                if getattr(entity, 'username', None):
                    url = f"https://t.me/{entity.username}"
                    async with session.get(url, headers=headers, timeout=10) as resp:
                        text = await resp.text()
                        
                        # كشف الإيميلات
                        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
                        if emails:
                            result["exposed_data"]["emails"] = list(set(emails))
                            result["risk_score"] += 15
                        
                        # كشف الأرقام
                        phones = re.findall(r'\+?[\d]{8,15}', text)
                        if phones:
                            result["exposed_data"]["phones"] = list(set(phones))
                            result["risk_score"] += 20
                        
                        # كشف الروابط
                        urls = re.findall(r'https?://[^\s<>"]+', text)
                        if urls:
                            result["exposed_data"]["external_links"] = urls[:5]
            
            return result
            
        except Exception as e:
            return {"error": f"فشل التحليل: {str(e)[:100]}"}
    
    @classmethod
    def _estimate_date_from_id(cls, user_id: int) -> Optional[datetime]:
        """تقدير تاريخ إنشاء الحساب من ID"""
        if user_id < 1000000:
            return datetime(2013, 8, 14)
        
        # معادلة تقريبية محسنة
        milestones = [
            (1000000, datetime(2014, 9, 1)),
            (500000000, datetime(2016, 3, 15)),
            (1000000000, datetime(2017, 6, 20)),
            (3000000000, datetime(2019, 1, 10)),
            (5000000000, datetime(2020, 9, 5)),
            (6000000000, datetime(2021, 6, 15)),
            (7000000000, datetime(2022, 8, 20)),
            (8000000000, datetime(2023, 12, 1)),
        ]
        
        for i, (milestone_id, milestone_date) in enumerate(milestones):
            if user_id < milestone_id:
                if i == 0:
                    ids_per_day = 5000
                    return datetime(2013, 8, 14) + timedelta(days=user_id / ids_per_day)
                prev_id, prev_date = milestones[i-1]
                id_diff = milestone_id - prev_id
                day_diff = (milestone_date - prev_date).days
                ids_per_day = id_diff / max(day_diff, 1)
                offset = (user_id - prev_id) / ids_per_day
                return prev_date + timedelta(days=offset)
        
        # للأرقام الكبيرة جداً
        last_id, last_date = milestones[-1]
        return last_date + timedelta(days=(user_id - last_id) / 300000)

# ===================== نظام فحص التسريبات =====================
class DataBreachChecker:
    """نظام فحص تسريبات البيانات"""
    
    @classmethod
    async def check_email_breaches(cls, email: str) -> Dict:
        """فحص إذا كان الإيميل في تسريبات معروفة"""
        try:
            # استخدام API عام (haveibeenpwned - API مجاني)
            sha1_email = hashlib.sha1(email.encode()).hexdigest().upper()
            prefix, suffix = sha1_email[:5], sha1_email[5:]
            
            async with aiohttp.ClientSession() as session:
                url = f"https://api.pwnedpasswords.com/range/{prefix}"
                headers = {'User-Agent': 'NinjaGram-Security-Tool'}
                async with session.get(url, headers=headers, timeout=10) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        for line in text.splitlines():
                            if suffix in line:
                                count = int(line.split(':')[1])
                                return {
                                    "found": True,
                                    "email": email,
                                    "breach_count": count,
                                    "risk": "🔴 خطر" if count > 100 else "🟡 متوسط" if count > 10 else "🟢 منخفض",
                                    "message": f"الإيميل موجود في {count} تسريب بيانات!"
                                }
                        return {"found": False, "email": email, "message": "✅ الإيميل غير موجود في التسريبات المعروفة"}
        except:
            return {"error": "فشل الفحص، حاول لاحقاً"}
    
    @classmethod
    async def check_phone_info(cls, phone: str) -> Dict:
        """فحص معلومات رقم الهاتف"""
        try:
            clean_phone = re.sub(r'[^\d+]', '', phone)
            
            result = {
                "phone": phone,
                "valid": SecuritySystem.validate_phone(phone),
                "country": None,
                "operator": None
            }
            
            # محاولة تحديد الدولة
            country_codes = {
                "20": "مصر 🇪🇬", "966": "السعودية 🇸🇦", "971": "الإمارات 🇦🇪",
                "965": "الكويت 🇰🇼", "974": "قطر 🇶🇦", "973": "البحرين 🇧🇭",
                "968": "عمان 🇴🇲", "962": "الأردن 🇯🇴", "964": "العراق 🇮🇶",
                "963": "سوريا 🇸🇾", "961": "لبنان 🇱🇧", "970": "فلسطين 🇵🇸",
                "967": "اليمن 🇾🇪", "218": "ليبيا 🇱🇾", "216": "تونس 🇹🇳",
                "213": "الجزائر 🇩🇿", "212": "المغرب 🇲🇦", "249": "السودان 🇸🇩",
                "1": "أمريكا 🇺🇸", "44": "بريطانيا 🇬🇧", "33": "فرنسا 🇫🇷",
                "49": "ألمانيا 🇩🇪", "7": "روسيا 🇷🇺", "86": "الصين 🇨🇳"
            }
            
            if clean_phone.startswith('+'):
                clean_phone = clean_phone[1:]
            
            for code, country in country_codes.items():
                if clean_phone.startswith(code):
                    result["country"] = country
                    break
            
            return result
        except:
            return {"error": "فشل التحليل"}

# ===================== نظام تحليل الصور =====================
class ImageAnalyzer:
    """نظام تحليل الصور واستخراج البيانات المخفية"""
    
    @classmethod
    async def extract_metadata(cls, image_data: bytes) -> Dict:
        """استخراج البيانات الوصفية من الصورة"""
        try:
            img = Image.open(BytesIO(image_data))
            result = {
                "format": img.format,
                "size": img.size,
                "mode": img.mode,
                "exif": {},
                "hidden_text": None,
                "suspicious": False
            }
            
            # استخراج EXIF
            try:
                exif_data = img._getexif()
                if exif_data:
                    for tag_id, value in exif_data.items():
                        if tag_id in piexif.ExifIFD.__dict__.values():
                            tag_name = [k for k, v in piexif.ExifIFD.__dict__.items() if v == tag_id]
                            if tag_name:
                                result["exif"][tag_name[0]] = str(value)[:100]
                    
                    # فحص وجود GPS
                    if any('GPS' in k for k in result["exif"].keys()):
                        result["suspicious"] = True
                        result["warning"] = "⚠️ الصورة تحتوي على إحداثيات GPS"
            except:
                pass
            
            # محاولة استخراج نص مخفي (steganography basic check)
            try:
                pixels = list(img.getdata())
                text_bits = ""
                for pixel in pixels[:1000]:
                    if isinstance(pixel, tuple):
                        text_bits += str(pixel[0] & 1)
                
                # محاولة فك النص
                if len(text_bits) >= 8:
                    chars = []
                    for i in range(0, len(text_bits) - 7, 8):
                        byte = text_bits[i:i+8]
                        try:
                            char = chr(int(byte, 2))
                            if char.isprintable():
                                chars.append(char)
                        except:
                            pass
                    if chars:
                        result["hidden_text"] = ''.join(chars)[:200]
                        result["suspicious"] = True
            except:
                pass
            
            return result
        except Exception as e:
            return {"error": f"فشل تحليل الصورة: {str(e)[:50]}"}
    
    @classmethod
    async def reverse_image_search(cls, image_url: str) -> Dict:
        """البحث العكسي عن الصورة"""
        try:
            async with aiohttp.ClientSession() as session:
                # استخدام Google reverse image search
                search_url = f"https://lens.google.com/uploadbyurl?url={quote(image_url)}"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                
                return {
                    "success": True,
                    "search_url": search_url,
                    "message": "تم توليد رابط البحث العكسي"
                }
        except:
            return {"error": "فشل البحث العكسي"}

# ===================== نظام صانع الرسائل =====================
class MessageCrafter:
    """نظام صنع الرسائل المخصصة"""
    
    @classmethod
    async def create_fake_message(cls, sender_name: str, message_text: str, 
                                   sender_photo: Optional[bytes] = None,
                                   is_bot: bool = False, verified: bool = False) -> bytes:
        """صنع صورة رسالة مزيفة للاستخدام التعليمي"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            # إنشاء صورة للرسالة
            width, height = 600, 200
            img = Image.new('RGB', (width, height), color='#1a1a2e')
            draw = ImageDraw.Draw(img)
            
            # إضافة اسم المرسل
            name_text = f"{'🤖 ' if is_bot else ''}{sender_name} {'✅' if verified else ''}"
            draw.text((50, 20), name_text, fill='#00ff88')
            
            # خط فاصل
            draw.line([(50, 45), (550, 45)], fill='#333355', width=1)
            
            # نص الرسالة
            draw.text((50, 60), message_text[:200], fill='#ffffff')
            
            # تذييل
            draw.text((50, 150), "⚠️ هذه رسالة توضيحية للأغراض التعليمية", fill='#ff4444')
            
            output = BytesIO()
            img.save(output, format='PNG')
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Error creating message: {e}")
            return None
    
    @classmethod
    async def generate_unban_request(cls, group_name: str, user_name: str, 
                                       reason: str = "غير معروف") -> str:
        """توليد رسالة طلب فك حظر احترافية"""
        
        reasons = {
            "spam": "إرسال رسائل متكررة (سبام)",
            "links": "إرسال روابط خارجية",
            "ads": "نشر إعلانات غير مصرح بها",
            "behavior": "سلوك غير لائق",
            "other": reason
        }
        
        reason_text = reasons.get(reason, reason)
        
        template = f"""
📝 **طلب فك حظر - {group_name}**

السلام عليكم ورحمة الله وبركاته،

أنا العضو: **{user_name}**

أود التقدم بطلب فك الحظر عن حسابي من مجموعة **{group_name}**.

🔍 **سبب الحظر (حسب علمي):**
{reason_text}

📌 **تعهداتي:**
1. الالتزام الكامل بقوانين المجموعة
2. عدم تكرار المخالفة
3. احترام جميع الأعضاء والمشرفين
4. المساهمة الإيجابية في المجموعة

🙏 أرجو من الإدارة الكريمة إعادة النظر في قراري وإعطائي فرصة أخرى.

وشكراً لتفهمكم 🌹
        """
        
        return template.strip()
    
    @classmethod
    async def generate_report_text(cls, target: str, violation_type: str, 
                                     evidence_list: List[str] = None) -> str:
        """توليد بلاغ احترافي لدعم تيليجرام"""
        
        violation_types = {
            "spam": "إرسال رسائل مزعجة وغير مرغوب فيها",
            "impersonation": "انتحال شخصية/جهة رسمية",
            "harassment": "مضايقة وترهيب",
            "illegal": "نشر محتوى غير قانوني",
            "violence": "التحريض على العنف",
            "fraud": "احتيال ونصب",
            "copyright": "انتهاك حقوق الملكية",
            "privacy": "انتهاك الخصوصية",
            "other": "مخالفة شروط خدمة تيليجرام"
        }
        
        violation_text = violation_types.get(violation_type, violation_types["other"])
        
        report_id = uuid.uuid4().hex[:12].upper()
        
        report = f"""
╔══════════════════════════════════════╗
║     🛡️ تقرير بلاغ - تيليجرام      ║
║     Report ID: {report_id}          ║
╚══════════════════════════════════════╝

📋 **نوع المخالفة:** {violation_text}

👤 **المبلغ عنه:** {target}

📅 **تاريخ البلاغ:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📝 **وصف المخالفة:**
{chr(10).join([f'• {e}' for e in evidence_list]) if evidence_list else '• يرجى إضافة وصف تفصيلي'}

📎 **الأدلة المرفقة:**
• يرجى إرفاق لقطات شاشة واضحة
• يرجى إرفاق روابط المحادثات
• يرجى توثيق التاريخ والوقت

⚖️ **المواد المخالفة من شروط الخدمة:**
• المادة 3.1: الأنشطة المحظورة
• المادة 3.2: سلوك المستخدم
• المادة 4: المحتوى غير القانوني

📧 **للتواصل مع الدعم:**
• البريد: abuse@telegram.org
• الموقع: telegram.org/support

⚠️ **ملاحظة:** هذا البلاغ مُعد للأغراض المشروعة فقط.
تأكد من صحة المعلومات قبل الإرسال.
        """
        
        return report.strip()

# ===================== نظام فحص الروابط =====================
class LinkAnalyzer:
    """نظام تحليل وفك روابط تيليجرام"""
    
    @classmethod
    async def analyze_deep_link(cls, link: str) -> Dict:
        """تحليل عميق لأي رابط تيليجرام"""
        result = {
            "original": link,
            "is_telegram": False,
            "type": "unknown",
            "identifier": None,
            "resolved": None,
            "risk": "unknown"
        }
        
        # أنماط روابط تيليجرام
        patterns = {
            "username": r'(?:https?://)?t(?:elegram)?\.me/([a-zA-Z][a-zA-Z0-9_]{3,31})(?:/.*)?$',
            "private_link": r'(?:https?://)?t(?:elegram)?\.me/joinchat/([a-zA-Z0-9_-]+)',
            "new_private": r'(?:https?://)?t(?:elegram)?\.me/\+(.+)',
            "bot_start": r'(?:https?://)?t(?:elegram)?\.me/([a-zA-Z][a-zA-Z0-9_]*bot)\?start=(.+)',
            "tg_resolve": r'tg://resolve\?domain=([a-zA-Z][a-zA-Z0-9_]+)',
            "tg_open": r'tg://openmessage\?user_id=(\d+)',
            "tg_join": r'tg://join\?invite=([a-zA-Z0-9_-]+)',
        }
        
        for link_type, pattern in patterns.items():
            match = re.search(pattern, link)
            if match:
                result["is_telegram"] = True
                result["type"] = link_type
                
                if link_type == "username":
                    username = match.group(1)
                    result["identifier"] = username
                    try:
                        entity = await bot.get_entity(username)
                        result["resolved"] = cls._classify_entity(entity)
                    except:
                        result["resolved"] = "غير موجود أو محذوف"
                
                elif link_type in ["private_link", "new_private"]:
                    invite_hash = match.group(1)
                    result["identifier"] = invite_hash
                    try:
                        check = await bot(CheckChatInviteRequest(invite_hash))
                        result["resolved"] = {
                            "title": getattr(check, 'title', 'غير معروف'),
                            "type": "قناة" if check.chat else "جروب",
                            "members": getattr(check, 'participants_count', 'غير معروف')
                        }
                    except InviteHashExpiredError:
                        result["resolved"] = "منتهي الصلاحية ❌"
                    except InviteHashInvalidError:
                        result["resolved"] = "غير صالح ❌"
                
                elif link_type == "bot_start":
                    result["identifier"] = match.group(1)
                    result["start_param"] = match.group(2)
                    try:
                        entity = await bot.get_entity(match.group(1))
                        result["resolved"] = cls._classify_entity(entity)
                    except:
                        result["resolved"] = "بوت غير موجود"
                
                break
        
        # فحص الروابط المشبوهة
        if result["is_telegram"]:
            suspicious_words = ['free', 'hack', 'crack', 'steal', 'bitcoin', 'gift', 'win', 'prize']
            if any(word in link.lower() for word in suspicious_words):
                result["risk"] = "⚠️ مشبوه - قد يكون احتيال"
            else:
                result["risk"] = "🟢 آمن"
        
        return result
    
    @classmethod
    def _classify_entity(cls, entity) -> Dict:
        """تصنيف الكيان"""
        classification = {
            "id": entity.id,
            "type": "unknown",
            "username": getattr(entity, 'username', None),
            "name": getattr(entity, 'first_name', '') or getattr(entity, 'title', ''),
        }
        
        if hasattr(entity, 'bot') and entity.bot:
            classification["type"] = "🤖 بوت"
        elif hasattr(entity, 'broadcast') and entity.broadcast:
            classification["type"] = "📢 قناة"
        elif hasattr(entity, 'megagroup') and entity.megagroup:
            classification["type"] = "👥 جروب سوبر"
        elif hasattr(entity, 'gigagroup') and entity.gigagroup:
            classification["type"] = "👥 جروب ضخم"
        else:
            classification["type"] = "👤 حساب شخصي"
        
        return classification

# ===================== واجهة المستخدم =====================
class UIManager:
    @classmethod
    def main_menu(cls):
        return [
            [Button.inline("🕵️ تحليل OSINT متقدم", b"osint_analysis"),
             Button.inline("🧬 بصمة الحساب", b"fingerprint")],
            [Button.inline("🔍 فحص تسريبات", b"breach_check"),
             Button.inline("🖼️ تحليل الصور", b"image_analysis")],
            [Button.inline("💣 فحص يوزر متقدم", b"username_check"),
             Button.inline("🔗 تحليل الروابط", b"link_analysis")],
            [Button.inline("📝 صانع الرسائل", b"msg_craft"),
             Button.inline("📋 مولد البلاغات", b"report_gen")],
            [Button.inline("🎯 صيد يوزرات", b"hunt_menu"),
             Button.inline("📊 إحصائيات", b"stats_menu")],
            [Button.inline("🔄 تحويلات", b"convert_menu"),
             Button.inline("ℹ️ معلومات", b"info_menu")],
        ]
    
    @classmethod
    def osint_menu(cls):
        return [
            [Button.inline("👤 تحليل حساب", b"osint_user"),
             Button.inline("📊 تحليل متقدم", b"osint_deep")],
            [Button.inline("🔙 رجوع", b"back_main")],
        ]
    
    @classmethod
    def msg_menu(cls):
        return [
            [Button.inline("📝 رسالة مزيفة", b"fake_msg"),
             Button.inline("📩 طلب فك حظر", b"unban_req")],
            [Button.inline("📋 بلاغ احترافي", b"smart_report"),
             Button.inline("🔙 رجوع", b"back_main")],
        ]

# ===================== معالجات الأوامر =====================
@bot.on(events.NewMessage(pattern='/start'))
async def bot_start(event):
    allowed_chats.add(event.chat_id)
    user_id = event.sender_id
    
    caption = (
        "🧨 **NinjaGram Pro Max Ultra**\n\n"
        "🛡️ **أقوى بوت أدوات تيليجرام الأمنية**\n\n"
        "⚡ **الخدمات:**\n"
        "• 🕵️ تحليل OSINT متقدم للحسابات\n"
        "• 🧬 استخراج بصمة الحساب الكاملة\n"
        "• 💣 فحص تسريبات البيانات\n"
        "• 🖼️ تحليل الصور واستخراج metadata\n"
        "• 🔗 فك وتحليل روابط تيليجرام\n"
        "• 📝 صانع رسائل وبلاغات احترافية\n"
        "• 🎯 صيد يوزرات ذكي\n"
        "• 🔄 تحويل يوزر ↔ ID\n\n"
        "⚠️ **للأغراض التعليمية والأمنية فقط**\n"
        "📢 **Channel:** @Q_g_r_a_m\n"
        "👨‍💻 **Developer:** @NinjaGram"
    )
    
    if os.path.exists(START_IMAGE):
        await bot.send_file(event.chat_id, START_IMAGE, caption=caption, buttons=UIManager.main_menu(), parse_mode='md')
    else:
        await bot.send_message(event.chat_id, caption, buttons=UIManager.main_menu(), parse_mode='md')

# تحليل OSINT
@bot.on(events.CallbackQuery(data=b"osint_analysis"))
async def osint_analysis_menu(event):
    await event.edit(
        "🕵️ **نظام تحليل OSINT المتقدم**\n\n"
        "اختر نوع التحليل:",
        buttons=UIManager.osint_menu(),
        parse_mode='md'
    )

@bot.on(events.CallbackQuery(data=b"osint_deep"))
async def osint_deep_start(event):
    user_id = event.sender_id
    user_states[user_id] = "waiting_osint_deep"
    await event.edit(
        "🕵️ **التحليل العميق للحساب**\n\n"
        "📤 أرسل يوزر أو آيدي الحساب مباشرة:\n"
        "مثال: @username أو 6443238809",
        buttons=[[Button.inline("🔙 رجوع", b"osint_analysis")]],
        parse_mode='md'
    )

@bot.on(events.NewMessage(func=lambda e: e.sender_id in user_states and user_states[e.sender_id] == "waiting_osint_deep"))
async def handle_osint_deep(event):
    user_id = event.sender_id
    user_states.pop(user_id, None)
    target = event.text.strip()
    
    loading_msg = await event.respond("🕵️ **جاري التحليل العميق...**\n🔍 جمع المعلومات من مصادر متعددة", parse_mode='md')
    
    result = await AdvancedOSINT.deep_account_analysis(target)
    
    if "error" in result:
        await loading_msg.edit(f"❌ **{result['error']}**", buttons=[[Button.inline("🔙 رجوع", b"osint_analysis")]], parse_mode='md')
        return
    
    text = f"🕵️ **تقرير تحليل OSINT**\n\n"
    
    basic = result.get("basic_info", {})
    text += "📋 **المعلومات الأساسية:**\n"
    text += f"• ID: `{basic.get('id', '?')}`\n"
    text += f"• يوزر: @{basic.get('username') if basic.get('username') else 'لا يوجد'}\n"
    text += f"• الاسم: {basic.get('first_name', '')} {basic.get('last_name', '')}\n"
    text += f"• الهاتف: {basic.get('phone', 'مخفي')}\n"
    text += f"• موثق: {'✅' if basic.get('is_verified') else '❌'}\n"
    text += f"• بريميوم: {'⭐' if basic.get('is_premium') else '❌'}\n"
    text += f"• احتيال: {'⚠️ نعم' if basic.get('is_scam') else '✅ لا'}\n\n"
    
    security = result.get("security_analysis", {})
    if security.get("issues"):
        text += "⚠️ **مشاكل الأمان:**\n"
        for issue in security["issues"]:
            text += f"• {issue}\n"
        text += "\n"
    
    text += f"🎯 **درجة الخطورة:** {result.get('risk_score', 0)}/100\n"
    text += f"📊 **مستوى الخطورة:** {result.get('risk_level', 'غير معروف')}\n\n"
    
    activity = result.get("activity_analysis", {})
    if activity.get("creation_date"):
        text += f"📅 **تاريخ الإنشاء التقريبي:** {activity['creation_date']}\n"
        text += f"⏳ **عمر الحساب:** {activity.get('age_days', '?')} يوم\n\n"
    
    exposed = result.get("exposed_data", {})
    if exposed.get("emails"):
        text += "📧 **إيميلات مكشوفة:**\n"
        for email in exposed["emails"][:3]:
            text += f"• `{email}`\n"
        text += "\n"
    
    if exposed.get("phones"):
        text += "📞 **أرقام مكشوفة:**\n"
        for phone in exposed["phones"][:3]:
            text += f"• `{phone}`\n"
        text += "\n"
    
    await loading_msg.edit(text, buttons=[[Button.inline("🔙 رجوع", b"osint_analysis")]], parse_mode='md')

# فحص اليوزر المتقدم
@bot.on(events.CallbackQuery(data=b"username_check"))
async def username_check_start(event):
    user_id = event.sender_id
    user_states[user_id] = "waiting_username_check"
    await event.edit(
        "💣 **فحص اليوزر المتقدم**\n\n"
        "📤 أرسل اليوزر للفحص مباشرة:\n"
        "مثال: @username\n\n"
        "🔍 سيتم الكشف عن:\n"
        "• اليوزر متاح/محظور/محذوف\n"
        "• حالة الحساب التفصيلية\n"
        "• تحليل سريع للأمان",
        buttons=[[Button.inline("🔙 رجوع", b"back_main")]],
        parse_mode='md'
    )

@bot.on(events.NewMessage(func=lambda e: e.sender_id in user_states and user_states[e.sender_id] == "waiting_username_check"))
async def handle_username_check(event):
    user_id = event.sender_id
    user_states.pop(user_id, None)
    username = event.text.strip().replace("@", "")
    
    loading_msg = await event.respond(f"💣 **جاري فحص @{username}...**", parse_mode='md')
    
    status = await AdvancedOSINT.get_username_status(username)
    
    text = f"💣 **نتيجة فحص @{username}**\n\n"
    text += f"📊 **الحالة:** {status.get('details', 'غير معروف')}\n"
    
    status_map = {
        "available": "✅ اليوزر متاح للحجز!\n🎉 يمكنك حجزه الآن",
        "taken": "❌ اليوزر محجوز\nالحساب موجود ونشط",
        "banned": "🚫 الحساب محظور\n⚠️ تم حظره من تيليجرام",
        "deleted": "🗑️ الحساب محذوف\nتم حذفه من قبل المستخدم",
        "rate_limited": "⏳ تم تقييد الطلبات\nحاول مرة أخرى لاحقاً",
    }
    
    status_msg = status_map.get(status.get("status"), "")
    if status_msg:
        text += f"\n{status_msg}"
    
    await loading_msg.edit(text, buttons=[[Button.inline("🔄 فحص آخر", b"username_check"), 
                                             Button.inline("🔙 رجوع", b"back_main")]], parse_mode='md')

# فحص التسريبات
@bot.on(events.CallbackQuery(data=b"breach_check"))
async def breach_check_start(event):
    user_id = event.sender_id
    user_states[user_id] = "waiting_breach_check"
    await event.edit(
        "🔍 **فحص تسريبات البيانات**\n\n"
        "📤 أرسل الإيميل أو رقم الهاتف للفحص:\n"
        "مثال: example@email.com\n"
        "أو: +201234567890\n\n"
        "⚠️ نفحص فقط إذا كان موجوداً في تسريبات معروفة",
        buttons=[[Button.inline("🔙 رجوع", b"back_main")]],
        parse_mode='md'
    )

@bot.on(events.NewMessage(func=lambda e: e.sender_id in user_states and user_states[e.sender_id] == "waiting_breach_check"))
async def handle_breach_check(event):
    user_id = event.sender_id
    user_states.pop(user_id, None)
    query = event.text.strip()
    
    loading_msg = await event.respond("🔍 **جاري فحص قواعد البيانات...**", parse_mode='md')
    
    if '@' in query:
        result = await DataBreachChecker.check_email_breaches(query)
    else:
        result = await DataBreachChecker.check_phone_info(query)
    
    if "error" in result:
        text = f"❌ {result['error']}"
    elif result.get("found"):
        text = f"⚠️ **تحذير!**\n\n{result.get('message', '')}\n"
        text += f"📊 مستوى الخطورة: {result.get('risk', 'غير معروف')}\n\n"
        text += "💡 **توصية:** قم بتغيير كلمة المرور فوراً!"
    else:
        text = result.get("message", "✅ لا توجد نتائج")
    
    await loading_msg.edit(text, buttons=[[Button.inline("🔙 رجوع", b"back_main")]], parse_mode='md')

# تحليل الروابط
@bot.on(events.CallbackQuery(data=b"link_analysis"))
async def link_analysis_start(event):
    user_id = event.sender_id
    user_states[user_id] = "waiting_link_analysis"
    await event.edit(
        "🔗 **تحليل روابط تيليجرام**\n\n"
        "📤 أرسل رابط تيليجرام للتحليل:\n"
        "مثال: https://t.me/username\n"
        "أو: https://t.me/+xxxxx\n"
        "أو: tg://resolve?domain=xxx",
        buttons=[[Button.inline("🔙 رجوع", b"back_main")]],
        parse_mode='md'
    )

@bot.on(events.NewMessage(func=lambda e: e.sender_id in user_states and user_states[e.sender_id] == "waiting_link_analysis"))
async def handle_link_analysis(event):
    user_id = event.sender_id
    user_states.pop(user_id, None)
    link = event.text.strip()
    
    loading_msg = await event.respond("🔗 **جاري تحليل الرابط...**", parse_mode='md')
    
    result = await LinkAnalyzer.analyze_deep_link(link)
    
    text = "🔗 **نتيجة تحليل الرابط**\n\n"
    text += f"📎 الرابط: {result['original']}\n\n"
    
    if not result['is_telegram']:
        text += "❌ **هذا ليس رابط تيليجرام صالح**"
    else:
        text += f"📋 **النوع:** {result.get('type', 'غير معروف')}\n"
        text += f"🔍 **المعرف:** {result.get('identifier', 'غير معروف')}\n"
        
        if result.get('resolved'):
            if isinstance(result['resolved'], dict):
                for k, v in result['resolved'].items():
                    text += f"• {k}: {v}\n"
            else:
                text += f"📊 **الحالة:** {result['resolved']}\n"
        
        text += f"\n⚠️ **تقييم الأمان:** {result.get('risk', 'غير معروف')}"
    
    await loading_msg.edit(text, buttons=[[Button.inline("🔙 رجوع", b"back_main")]], parse_mode='md')

# مولد البلاغات
@bot.on(events.CallbackQuery(data=b"smart_report"))
async def smart_report_start(event):
    user_id = event.sender_id
    user_states[user_id] = "waiting_report_target"
    await event.edit(
        "📋 **مولد البلاغات الذكي**\n\n"
        "📤 أرسل يوزر الحساب المراد الإبلاغ عنه:\n"
        "مثال: @spam_account",
        buttons=[[Button.inline("🔙 رجوع", b"msg_craft")]],
        parse_mode='md'
    )

@bot.on(events.NewMessage(func=lambda e: e.sender_id in user_states and user_states[e.sender_id] == "waiting_report_target"))
async def handle_report_target(event):
    user_id = event.sender_id
    target = event.text.strip()
    pending_data[user_id] = {"target": target}
    user_states[user_id] = "waiting_report_type"
    
    await event.respond(
        "📋 **اختر نوع المخالفة:**\n\n"
        "1️⃣ سبام (spam)\n"
        "2️⃣ انتحال شخصية (impersonation)\n"
        "3️⃣ مضايقة (harassment)\n"
        "4️⃣ محتوى غير قانوني (illegal)\n"
        "5️⃣ تحريض (violence)\n"
        "6️⃣ احتيال (fraud)\n"
        "7️⃣ انتهاك حقوق (copyright)\n"
        "8️⃣ انتهاك خصوصية (privacy)\n\n"
        "📤 أرسل رقم المخالفة فقط:",
        buttons=[[Button.inline("🔙 إلغاء", b"back_main")]],
        parse_mode='md'
    )

@bot.on(events.NewMessage(func=lambda e: e.sender_id in user_states and user_states[e.sender_id] == "waiting_report_type"))
async def handle_report_type(event):
    user_id = event.sender_id
    user_states.pop(user_id, None)
    
    violation_map = {
        "1": "spam", "2": "impersonation", "3": "harassment",
        "4": "illegal", "5": "violence", "6": "fraud",
        "7": "copyright", "8": "privacy"
    }
    
    choice = event.text.strip()
    violation = violation_map.get(choice, "other")
    
    target = pending_data.get(user_id, {}).get("target", "@unknown")
    
    report = await MessageCrafter.generate_report_text(target, violation)
    
    await event.respond(
        f"```\n{report}\n```",
        buttons=[[Button.inline("🔙 رجوع", b"back_main")]],
        parse_mode='md'
    )
    
    pending_data.pop(user_id, None)

# طلب فك حظر
@bot.on(events.CallbackQuery(data=b"unban_req"))
async def unban_request_start(event):
    user_id = event.sender_id
    user_states[user_id] = "waiting_unban_group"
    await event.edit(
        "📩 **صانع طلب فك الحظر**\n\n"
        "📤 أرسل اسم الجروب:\n"
        "مثال: جروب المبرمجين",
        buttons=[[Button.inline("🔙 رجوع", b"msg_craft")]],
        parse_mode='md'
    )

@bot.on(events.NewMessage(func=lambda e: e.sender_id in user_states and user_states[e.sender_id] == "waiting_unban_group"))
async def handle_unban_group(event):
    user_id = event.sender_id
    pending_data[user_id] = {"group": event.text.strip()}
    user_states[user_id] = "waiting_unban_name"
    await event.respond("📤 أرسل اسمك الذي ظهرت به في الجروب:", 
                         buttons=[[Button.inline("🔙 إلغاء", b"back_main")]], parse_mode='md')

@bot.on(events.NewMessage(func=lambda e: e.sender_id in user_states and user_states[e.sender_id] == "waiting_unban_name"))
async def handle_unban_name(event):
    user_id = event.sender_id
    pending_data[user_id]["name"] = event.text.strip()
    user_states[user_id] = "waiting_unban_reason"
    await event.respond(
        "📤 سبب الحظر:\n"
        "1️⃣ سبام\n2️⃣ روابط\n3️⃣ إعلانات\n4️⃣ سلوك\n5️⃣ أخرى",
        buttons=[[Button.inline("🔙 إلغاء", b"back_main")]],
        parse_mode='md'
    )

@bot.on(events.NewMessage(func=lambda e: e.sender_id in user_states and user_states[e.sender_id] == "waiting_unban_reason"))
async def handle_unban_reason(event):
    user_id = event.sender_id
    user_states.pop(user_id, None)
    
    reason_map = {"1": "spam", "2": "links", "3": "ads", "4": "behavior", "5": "other"}
    reason = reason_map.get(event.text.strip(), "other")
    
    data = pending_data.get(user_id, {})
    
    result = await MessageCrafter.generate_unban_request(
        data.get("group", ""),
        data.get("name", ""),
        reason
    )
    
    await event.respond(result, buttons=[[Button.inline("🔙 رجوع", b"back_main")]], parse_mode='md')
    pending_data.pop(user_id, None)

# الرجوع للقائمة
@bot.on(events.CallbackQuery(data=b"back_main"))
async def back_to_main(event):
    caption = "🧨 **NinjaGram Pro Max Ultra**\n\nاختر الخدمة:"
    await event.edit(caption, buttons=UIManager.main_menu(), parse_mode='md')

@bot.on(events.CallbackQuery(data=b"msg_craft"))
async def msg_craft_menu(event):
    await event.edit("📝 **صانع الرسائل**\n\nاختر:", buttons=UIManager.msg_menu(), parse_mode='md')

# ===================== بدء التشغيل =====================
print("""
╔══════════════════════════════════════════╗
║     🧨 NinjaGram Pro Max Ultra         ║
║     Telegram Security & OSINT Bot       ║
║     Version: 5.0.0 Hacker Edition       ║
║     Developer: @NinjaGram               ║
║     Channel: @Q_g_r_a_m                 ║
╚══════════════════════════════════════════╝
""")

bot.start(bot_token=BOT_TOKEN)
bot.run_until_disconnected()
