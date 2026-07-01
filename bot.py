#!/usr/bin/env python3
# 🧨 NinjaGram Pro Max Ultra v9.0
# أقوى بوت أدوات تيليجرام وواتساب
# Developer: @NinjaGram | Channel: @Q_g_r_a_m

import asyncio, uuid, os, re, random, string, time, io, logging, json
import hashlib, base64, textwrap, secrets
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode
from typing import Optional, Dict, List, Set, Tuple, Any
from collections import defaultdict, deque, Counter
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

# الأساسيات
import aiohttp
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import phonenumbers
from phonenumbers import geocoder, carrier, timezone

# تيليجرام
from telethon import TelegramClient, events, Button, functions, types
from telethon.errors import *
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.messages import (
    CheckChatInviteRequest, ImportChatInviteRequest, 
    GetHistoryRequest, SearchRequest
)
from telethon.tl.functions.channels import (
    JoinChannelRequest, GetFullChannelRequest, 
    InviteToChannelRequest
)
from telethon.tl.functions.contacts import (
    ResolveUsernameRequest, ImportContactsRequest,
    DeleteContactsRequest
)
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.types import (
    InputPhoneContact, InputPeerUser, InputPeerChannel,
    MessageEntityMention, MessageEntityUrl
)
from telethon.sessions import StringSession

# أدوات إضافية
import psutil
import aiofiles
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import cloudscraper

# ==================== الإعدادات ====================
DATA_DIR = '/app/data' if os.path.exists('/app/data') else './data'
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(f'{DATA_DIR}/sessions', exist_ok=True)
os.makedirs(f'{DATA_DIR}/logs', exist_ok=True)
os.makedirs(f'{DATA_DIR}/downloads', exist_ok=True)

BOT_TOKEN = '7998616214:AAFGroKKmwnrOtyAeJIHmrs_bKW5jXl0B20'
BOT_API_ID = 2040
BOT_API_HASH = 'b18441a1ff607e10a989891a5462e627'
DEV_USER_ID = 6443238809

# ==================== إعداد التسجيل ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'{DATA_DIR}/logs/bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('NinjaGram')

# ==================== المتغيرات العامة ====================
bot = TelegramClient(f'{DATA_DIR}/sessions/bot_session', BOT_API_ID, BOT_API_HASH)
user_states: Dict[int, str] = {}
pending_data: Dict[int, Dict] = {}
rate_limiter: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10))
allowed_chats: Set[int] = set()
username_cache: Dict[str, Tuple[float, Optional[str]]] = {}
thread_pool = ThreadPoolExecutor(max_workers=30)
ua = UserAgent()
scraper = cloudscraper.create_scraper()

# ==================== نظام الحماية ====================
class SecuritySystem:
    @staticmethod
    def check_rate(user_id: int, action: str, max_per_min: int = 10) -> bool:
        now = time.time()
        key = f"{user_id}:{action}"
        if key not in rate_limiter:
            rate_limiter[key] = deque(maxlen=max_per_min)
        reqs = rate_limiter[key]
        while reqs and reqs[0] < now - 60:
            reqs.popleft()
        if len(reqs) >= max_per_min:
            return False
        reqs.append(now)
        return True
    
    @staticmethod
    def validate_username(username: str) -> bool:
        return bool(re.match(r'^[a-zA-Z][a-zA-Z0-9_]{3,31}$', username))
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        try:
            parsed = phonenumbers.parse(phone)
            return phonenumbers.is_valid_number(parsed)
        except:
            return bool(re.match(r'^\+?[1-9]\d{7,14}$', phone.replace(" ", "")))

# ==================== نظام تروكولر الحقيقي ====================
class TruecallerSystem:
    """نظام تروكولر حقيقي باستخدام مصادر متعددة"""
    
    API_ENDPOINTS = {
        "numverify": "http://apilayer.net/api/validate?access_key={key}&number={number}",
        "veriphone": "https://api.veriphone.io/v2/verify?phone={number}&key={key}",
        "abstractapi": "https://phonevalidation.abstractapi.com/v1/?api_key={key}&phone={number}",
    }
    
    SEARCH_ENGINES = [
        "https://www.google.com/search?q={number}",
        "https://search.yahoo.com/search?p={number}",
        "https://duckduckgo.com/?q={number}",
        "https://www.bing.com/search?q={number}",
    ]
    
    BREACH_APIS = [
        "https://haveibeenpwned.com/api/v3/breachedaccount/{email}",
        "https://leakcheck.io/api/public?key={key}&check={query}",
        "https://api.dehashed.com/search?query={query}",
    ]
    
    @classmethod
    async def lookup_phone(cls, phone: str) -> Dict:
        """بحث شامل عن رقم الهاتف"""
        result = {
            "phone": phone,
            "valid": False,
            "carrier": None,
            "country": None,
            "location": None,
            "line_type": None,
            "social_media": [],
            "breaches": [],
            "risk_score": 0,
            "spam_reports": 0,
        }
        
        try:
            parsed = phonenumbers.parse(phone)
            result["valid"] = phonenumbers.is_valid_number(parsed)
            result["carrier"] = carrier.name_for_number(parsed, "en") or "غير معروف"
            result["country"] = geocoder.description_for_number(parsed, "en") or "غير معروف"
            result["location"] = geocoder.description_for_number(parsed, "ar") or "غير معروف"
            result["line_type"] = str(phonenumbers.number_type(parsed))
        except:
            pass
        
        # فحص في محركات البحث
        clean_phone = re.sub(r'[^\d]', '', phone)
        for search_url in cls.SEARCH_ENGINES:
            try:
                url = search_url.format(number=clean_phone)
                async with aiohttp.ClientSession() as session:
                    headers = {'User-Agent': ua.random}
                    async with session.get(url, headers=headers, timeout=10) as resp:
                        text = await resp.text()
                        
                        # البحث عن إشارات سبام
                        spam_keywords = ['spam', 'scam', 'fraud', 'احتيال', 'مزعج', 'scammer']
                        for keyword in spam_keywords:
                            if keyword.lower() in text.lower():
                                result["spam_reports"] += 1
                        
                        # البحث عن منصات اجتماعية
                        social_platforms = [
                            'facebook.com', 'instagram.com', 'twitter.com', 
                            'linkedin.com', 'snapchat.com', 'tiktok.com',
                            'telegram.me', 'wa.me', 'vk.com'
                        ]
                        for platform in social_platforms:
                            if platform in text.lower():
                                result["social_media"].append(platform)
            except:
                pass
        
        # حساب درجة الخطورة
        risk = 0
        if result["spam_reports"] > 0:
            risk += min(result["spam_reports"] * 15, 60)
        if not result["valid"]:
            risk += 20
        if len(result["social_media"]) == 0:
            risk += 10
        
        result["risk_score"] = min(risk, 100)
        result["risk_level"] = (
            "🟢 آمن" if risk < 30 else
            "🟡 مشبوه" if risk < 60 else
            "🔴 خطير"
        )
        
        return result
    
    @classmethod
    async def reverse_lookup(cls, name: str) -> List[Dict]:
        """بحث عن شخص بالاسم"""
        results = []
        try:
            async with aiohttp.ClientSession() as session:
                headers = {'User-Agent': ua.random}
                
                # بحث في Google
                url = f"https://www.google.com/search?q={quote(name + ' phone')}"
                async with session.get(url, headers=headers, timeout=10) as resp:
                    text = await resp.text()
                    phones = re.findall(r'\+?[\d]{8,15}', text)
                    for phone in phones[:10]:
                        if SecuritySystem.validate_phone(phone):
                            results.append({"phone": phone, "source": "web"})
                
                # بحث في محركات مخصصة
                people_search = [
                    f"https://www.truepeoplesearch.com/results?name={quote(name)}",
                    f"https://www.fastpeoplesearch.com/name/{quote(name)}",
                ]
                for ps_url in people_search:
                    try:
                        async with session.get(ps_url, headers=headers, timeout=10) as resp:
                            text = await resp.text()
                            phones = re.findall(r'\+?[\d]{8,15}', text)
                            for phone in phones[:5]:
                                if SecuritySystem.validate_phone(phone):
                                    results.append({"phone": phone, "source": "people_search"})
                    except:
                        pass
        except:
            pass
        
        return results[:20]

# ==================== نظام البلاغات الشامل ====================
class ReportSystem:
    """نظام البلاغات الاحترافي لتليجرام وواتساب"""
    
    REPORT_TYPES = {
        "spam": {
            "name": "سبام / رسائل مزعجة",
            "telegram_email": "abuse@telegram.org",
            "whatsapp_email": "support@whatsapp.com",
            "subject": "Spam Report - {target}",
            "severity": "medium"
        },
        "impersonation": {
            "name": "انتحال شخصية",
            "telegram_email": "abuse@telegram.org",
            "whatsapp_email": "support@whatsapp.com",
            "subject": "Impersonation Report - {target}",
            "severity": "high"
        },
        "threats": {
            "name": "تهديدات",
            "telegram_email": "abuse@telegram.org",
            "whatsapp_email": "support@whatsapp.com",
            "subject": "Threat Report - {target}",
            "severity": "high"
        },
        "terrorism": {
            "name": "إرهاب / تطرف",
            "telegram_email": "stopca@telegram.org",
            "whatsapp_email": "support@whatsapp.com",
            "subject": "URGENT: Terrorism Content Report - {target}",
            "severity": "critical"
        },
        "child_abuse": {
            "name": "استغلال أطفال",
            "telegram_email": "stopca@telegram.org",
            "whatsapp_email": "support@whatsapp.com",
            "subject": "URGENT: Child Abuse Report - {target}",
            "severity": "critical"
        },
        "pornography": {
            "name": "محتوى إباحي غير قانوني",
            "telegram_email": "abuse@telegram.org",
            "whatsapp_email": "support@whatsapp.com",
            "subject": "Illegal Adult Content Report - {target}",
            "severity": "high"
        },
        "fraud": {
            "name": "احتيال مالي",
            "telegram_email": "abuse@telegram.org",
            "whatsapp_email": "support@whatsapp.com",
            "subject": "Fraud Report - {target}",
            "severity": "high"
        },
        "drugs": {
            "name": "مخدرات / مواد محظورة",
            "telegram_email": "abuse@telegram.org",
            "whatsapp_email": "support@whatsapp.com",
            "subject": "Illegal Drugs Report - {target}",
            "severity": "high"
        },
        "weapons": {
            "name": "أسلحة غير قانونية",
            "telegram_email": "abuse@telegram.org",
            "whatsapp_email": "support@whatsapp.com",
            "subject": "Illegal Weapons Report - {target}",
            "severity": "high"
        },
        "violence": {
            "name": "عنف / كراهية",
            "telegram_email": "abuse@telegram.org",
            "whatsapp_email": "support@whatsapp.com",
            "subject": "Violence & Hate Report - {target}",
            "severity": "high"
        },
        "harassment": {
            "name": "مضايقة / تنمر",
            "telegram_email": "abuse@telegram.org",
            "whatsapp_email": "support@whatsapp.com",
            "subject": "Harassment Report - {target}",
            "severity": "medium"
        },
        "copyright": {
            "name": "انتهاك حقوق ملكية",
            "telegram_email": "dmca@telegram.org",
            "whatsapp_email": "support@whatsapp.com",
            "subject": "DMCA/Copyright Report - {target}",
            "severity": "medium"
        },
        "account_theft": {
            "name": "سرقة حساب",
            "telegram_email": "recover@telegram.org",
            "whatsapp_email": "support@whatsapp.com",
            "subject": "Account Theft Report - {target}",
            "severity": "high"
        },
        "malware": {
            "name": "برمجيات خبيثة",
            "telegram_email": "security@telegram.org",
            "whatsapp_email": "support@whatsapp.com",
            "subject": "Malware Report - {target}",
            "severity": "high"
        },
        "phishing": {
            "name": "تصيد / Phishing",
            "telegram_email": "security@telegram.org",
            "whatsapp_email": "support@whatsapp.com",
            "subject": "Phishing Report - {target}",
            "severity": "high"
        },
    }
    
    @classmethod
    def generate_report(cls, report_type: str, target: str, 
                        target_type: str = "telegram", 
                        evidence: List[str] = None,
                        reporter_name: str = "",
                        reporter_email: str = "") -> Dict:
        """توليد بلاغ احترافي"""
        
        report_info = cls.REPORT_TYPES.get(report_type, cls.REPORT_TYPES["spam"])
        
        report_id = f"NG-{uuid.uuid4().hex[:8].upper()}"
        
        if target_type == "telegram":
            target_display = f"@{target}" if not target.isdigit() else f"ID: {target}"
            platform_link = f"https://t.me/{target}" if not target.isdigit() else f"tg://openmessage?user_id={target}"
        else:
            target_display = target
            platform_link = f"https://wa.me/{target.replace('+', '')}"
        
        evidence_list = []
        if evidence:
            for i, ev in enumerate(evidence, 1):
                evidence_list.append(f"Evidence {i}: {ev}")
        else:
            evidence_list.append("• Screenshots of violation attached")
            evidence_list.append("• Chat logs available upon request")
            evidence_list.append("• Timestamp of violation documented")
        
        # نصوص بلاغات من مجتمعات الهكر والمبرمجين
        hacker_templates = {
            "spam": """
This account is actively engaged in spam activities across multiple Telegram groups.
The user sends unsolicited messages containing promotional content, phishing links, 
and repetitive advertisements. This violates Telegram's Terms of Service Section 3.1.

Impact: Multiple users have reported receiving these spam messages daily.
Frequency: Continuous spam activity observed over the past period.
            """,
            "impersonation": """
This account is impersonating [legitimate entity/person]. The user is using 
similar usernames, profile pictures, and display names to deceive other users.
This is a clear violation of Telegram's impersonation policy.

The legitimate account can be verified at: [original account]
The impersonator has been: [describe activities]
            """,
            "threats": """
URGENT: This account is sending threatening messages to users, including 
threats of physical harm, doxxing, and other forms of intimidation.
This violates Telegram's Terms of Service and potentially local laws.

Nature of threats: [describe threats]
Targets: [describe affected users]
            """,
            "terrorism": """
CRITICAL: This account is involved in spreading extremist content and 
potentially terrorist-related material. Immediate review is requested.

Type of content observed: [describe]
This account poses a serious threat to platform safety.
            """,
            "child_abuse": """
CRITICAL EMERGENCY: This account is suspected of involvement in child 
exploitation activities. Immediate action and potential referral to 
authorities is recommended.

Observations: [describe suspicious activity]
This is being reported to relevant authorities simultaneously.
            """,
        }
        
        detailed_description = hacker_templates.get(report_type, """
This account has been observed violating Telegram's Terms of Service.
The specific violation involves {violation_type}.
Evidence has been collected and is available for review.
        """.format(violation_type=report_info["name"]))
        
        # بناء البلاغ الكامل
        report_email_body = f"""
Subject: {report_info['subject'].format(target=target_display)}
To: {report_info['telegram_email']}
Priority: {report_info['severity'].upper()}

{'='*60}
TELEGRAM ABUSE REPORT
Report ID: {report_id}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
Severity: {report_info['severity'].upper()}
{'='*60}

REPORTED ACCOUNT:
- Platform: Telegram
- Username/ID: {target_display}
- Profile Link: {platform_link}

VIOLATION TYPE:
{report_info['name']}

DETAILED DESCRIPTION:
{detailed_description.strip()}

EVIDENCE:
{chr(10).join(evidence_list)}

REPORTER INFORMATION:
- Name: {reporter_name or '[Anonymous]'}
- Contact: {reporter_email or '[Not provided]'}

LEGAL NOTE:
This report is submitted in good faith. All information provided is 
accurate to the best of my knowledge. I understand that filing false 
reports may result in account restrictions.

I request Telegram Support to review this case and take appropriate 
action in accordance with the Terms of Service.

RELEVANT LINKS:
- Telegram ToS: https://telegram.org/tos
- Telegram FAQ: https://telegram.org/faq
- Report Form: https://telegram.org/support

{'='*60}
        """
        
        whatsapp_body = f"""
Subject: {report_info['subject'].format(target=target_display)}
To: {report_info['whatsapp_email']}
Priority: {report_info['severity'].upper()}

{'='*60}
WHATSAPP ABUSE REPORT
Report ID: {report_id}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
{'='*60}

REPORTED NUMBER: {target_display}
VIOLATION: {report_info['name']}

DESCRIPTION:
{detailed_description.strip()}

EVIDENCE:
{chr(10).join(evidence_list)}

WHATSAPP SUPPORT LINKS:
- Contact Form: https://www.whatsapp.com/contact/
- Help Center: https://faq.whatsapp.com/
- Report Spam: https://www.whatsapp.com/legal/

{'='*60}
        """
        
        return {
            "report_id": report_id,
            "telegram_report": report_email_body.strip(),
            "whatsapp_report": whatsapp_body.strip(),
            "telegram_email": report_info["telegram_email"],
            "whatsapp_email": report_info["whatsapp_email"],
            "severity": report_info["severity"],
            "report_type": report_info["name"],
        }

# ==================== نظام كشف رقم الهاتف (Russian Method) ====================
class PhoneRevealer:
    """نظام كشف رقم الهاتف من اليوزر - الطريقة الروسية"""
    
    @staticmethod
    def generate_phone_numbers(country_prefix: str, start_range: int = 0, 
                                end_range: int = 99999) -> List[str]:
        """توليد أرقام هواتف محتملة"""
        numbers = []
        for i in range(start_range, end_range):
            numbers.append(f"+{country_prefix}{i:07d}")
        return numbers
    
    @classmethod
    async def reveal_phone(cls, username: str, country_code: str = "20",
                           start_prefix: str = "10") -> Dict:
        """
        محاولة كشف رقم الهاتف من اليوزر
        الطريقة: استيراد جهات اتصال وفحص الـ mutual contacts
        """
        result = {
            "username": username,
            "phone_found": False,
            "phone": None,
            "attempts": 0,
            "method": "Russian Contact Import"
        }
        
        try:
            # جلب معلومات اليوزر
            entity = await bot.get_entity(username)
            target_id = entity.id
            
            # توليد مجموعة أرقام للتجربة
            test_numbers = []
            prefixes = ["10", "11", "12", "15"] if country_code == "20" else [start_prefix]
            
            for prefix in prefixes:
                for i in range(0, 10000, 100):  # تجربة 100 رقم لكل بادئة
                    number = f"+{country_code}{prefix}{i:05d}"
                    test_numbers.append(number)
            
            # تقسيم لدفعات (batches)
            batch_size = 50
            for i in range(0, len(test_numbers), batch_size):
                batch = test_numbers[i:i+batch_size]
                
                try:
                    # إنشاء جهات اتصال وهمية
                    contacts = []
                    for phone in batch:
                        contact = InputPhoneContact(
                            client_id=random.randint(100000, 999999),
                            phone=phone,
                            first_name=f"Test_{random.randint(1,9999)}",
                            last_name=""
                        )
                        contacts.append(contact)
                    
                    # استيراد جهات الاتصال
                    imported = await bot(ImportContactsRequest(contacts))
                    
                    # فحص النتائج
                    if imported and imported.users:
                        for user in imported.users:
                            if user.id == target_id:
                                # تم العثور على المستخدم
                                # البحث عن الرقم المطابق
                                for contact, phone in zip(contacts, batch):
                                    if hasattr(user, 'phone') and user.phone:
                                        result["phone_found"] = True
                                        result["phone"] = phone
                                        result["attempts"] = i + len(batch)
                                        
                                        # حذف جهات الاتصال للتنظيف
                                        try:
                                            await bot(DeleteContactsRequest([user]))
                                        except:
                                            pass
                                        
                                        return result
                    
                    # حذف جهات الاتصال المستوردة
                    if imported and imported.users:
                        try:
                            await bot(DeleteContactsRequest(imported.users))
                        except:
                            pass
                    
                    result["attempts"] = i + len(batch)
                    
                    # انتظار لتجنب rate limit
                    await asyncio.sleep(2)
                    
                except FloodWaitError as e:
                    logger.warning(f"Flood wait: {e.seconds}s")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    logger.error(f"Batch error: {e}")
                    continue
            
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    @classmethod
    async def check_phone_registered(cls, phone: str) -> Dict:
        """فحص إذا كان الرقم مسجل في تيليجرام"""
        result = {
            "phone": phone,
            "registered": False,
            "user_info": None
        }
        
        try:
            contact = InputPhoneContact(
                client_id=random.randint(100000, 999999),
                phone=phone,
                first_name="Check",
                last_name="User"
            )
            
            imported = await bot(ImportContactsRequest([contact]))
            
            if imported and imported.users:
                user = imported.users[0]
                result["registered"] = True
                result["user_info"] = {
                    "id": user.id,
                    "username": getattr(user, 'username', None),
                    "first_name": getattr(user, 'first_name', ''),
                    "last_name": getattr(user, 'last_name', ''),
                }
                
                # تنظيف
                try:
                    await bot(DeleteContactsRequest([user]))
                except:
                    pass
            
        except Exception as e:
            result["error"] = str(e)
        
        return result

# ==================== نظام OSINT المتقدم ====================
class AdvancedOSINT:
    """نظام جمع المعلومات المتقدم"""
    
    @classmethod
    async def get_full_info(cls, user_input: str) -> Dict:
        """جلب معلومات كاملة عن أي حساب"""
        result = {
            "basic": {},
            "security": {},
            "activity": {},
            "exposed": {},
            "risk_score": 0
        }
        
        try:
            # جلب الكيان
            if user_input.isdigit():
                entity = await bot.get_entity(int(user_input))
            else:
                username = user_input.replace("@", "")
                entity = await bot.get_entity(username)
            
            if not entity:
                return {"error": "الحساب غير موجود"}
            
            # معلومات أساسية
            result["basic"] = {
                "id": entity.id,
                "username": getattr(entity, 'username', None),
                "first_name": getattr(entity, 'first_name', ''),
                "last_name": getattr(entity, 'last_name', ''),
                "phone_visible": getattr(entity, 'phone', None) is not None,
                "phone": getattr(entity, 'phone', 'مخفي'),
                "verified": getattr(entity, 'verified', False),
                "premium": getattr(entity, 'premium', False),
                "bot": getattr(entity, 'bot', False),
                "scam": getattr(entity, 'scam', False),
                "fake": getattr(entity, 'fake', False),
                "restricted": getattr(entity, 'restricted', False),
                "is_contact": getattr(entity, 'contact', False),
                "mutual_contact": getattr(entity, 'mutual_contact', False),
            }
            
            # تقدير تاريخ الإنشاء
            creation = cls._estimate_date(entity.id)
            if creation:
                age_days = (datetime.now() - creation).days
                result["activity"]["creation_date"] = creation.strftime("%Y-%m-%d")
                result["activity"]["age_days"] = age_days
                result["activity"]["age_years"] = round(age_days / 365, 1)
            
            # تحليل الأمان
            risk = 0
            issues = []
            
            if not result["basic"]["username"]:
                issues.append("لا يوجد يوزر عام")
                risk += 20
            
            if result["basic"]["phone_visible"]:
                issues.append("رقم الهاتف مكشوف للجميع")
                risk += 40
            
            if result["basic"]["scam"]:
                issues.append("مُبلغ عنه كحساب احتيال")
                risk += 80
            
            if result["basic"]["fake"]:
                issues.append("مُبلغ عنه كحساب مزيف")
                risk += 60
            
            if result["activity"].get("age_days", 999) < 30:
                issues.append("حساب جديد جداً (أقل من شهر)")
                risk += 25
            
            result["security"]["issues"] = issues
            result["security"]["issue_count"] = len(issues)
            result["risk_score"] = min(risk, 100)
            
            # جلب معلومات إضافية
            try:
                full_user = await bot(GetFullUserRequest(entity))
                result["activity"]["bio"] = getattr(full_user.full_user, 'about', '')[:500]
                result["activity"]["common_chats"] = getattr(full_user.full_user, 'common_chats_count', 0)
            except:
                pass
            
            # فحص الويب
            if result["basic"]["username"]:
                async with aiohttp.ClientSession() as session:
                    headers = {'User-Agent': ua.random}
                    url = f"https://t.me/{result['basic']['username']}"
                    try:
                        async with session.get(url, headers=headers, timeout=10) as resp:
                            text = await resp.text()
                            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
                            if emails:
                                result["exposed"]["emails"] = list(set(emails))[:10]
                            
                            phones = re.findall(r'\+?[\d]{8,15}', text)
                            if phones:
                                result["exposed"]["phones"] = list(set(phones))[:10]
                    except:
                        pass
            
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    @staticmethod
    def _estimate_date(user_id: int) -> Optional[datetime]:
        """تقدير تاريخ إنشاء الحساب من ID"""
        if user_id < 1000000:
            return datetime(2013, 8, 14)
        elif user_id < 1000000000:
            return datetime(2016, 3, 15)
        elif user_id < 3000000000:
            return datetime(2018, 6, 20)
        elif user_id < 5000000000:
            return datetime(2020, 1, 10)
        elif user_id < 6000000000:
            return datetime(2021, 6, 15)
        elif user_id < 7000000000:
            return datetime(2022, 8, 20)
        elif user_id < 8000000000:
            return datetime(2023, 6, 1)
        else:
            return datetime(2024, 3, 1)

# ==================== نظام تجميع الجروبات ====================
class GroupScraper:
    """نظام تجميع الجروبات بالعربي"""
    
    @classmethod
    async def search_groups(cls, keyword: str, limit: int = 50) -> List[Dict]:
        """البحث عن جروبات بالكلمة المفتاحية"""
        results = []
        
        try:
            # البحث في تيليجرام مباشرة
            search_result = await bot(SearchRequest(
                q=keyword,
                filter=types.InputMessagesFilterEmpty(),
                min_date=None,
                max_date=None,
                offset_id=0,
                add_offset=0,
                limit=limit,
                max_id=0,
                min_id=0,
                hash=0
            ))
            
            # معالجة النتائج
            if hasattr(search_result, 'chats'):
                for chat in search_result.chats:
                    if hasattr(chat, 'username') and chat.username:
                        info = {
                            "id": chat.id,
                            "username": chat.username,
                            "title": getattr(chat, 'title', ''),
                            "members": getattr(chat, 'participants_count', 0),
                            "type": "قناة" if getattr(chat, 'broadcast', False) else "جروب",
                            "link": f"https://t.me/{chat.username}",
                            "verified": getattr(chat, 'verified', False),
                        }
                        results.append(info)
        
        except Exception as e:
            logger.error(f"Search error: {e}")
        
        # البحث الإضافي عبر الويب
        try:
            async with aiohttp.ClientSession() as session:
                headers = {'User-Agent': ua.random}
                
                # tgstat search
                url = f"https://tgstat.com/search?q={quote(keyword)}"
                try:
                    async with session.get(url, headers=headers, timeout=15) as resp:
                        text = await resp.text()
                        usernames = re.findall(r'@([a-zA-Z][a-zA-Z0-9_]{3,31})', text)
                        for username in usernames[:20]:
                            if not any(r['username'] == username for r in results):
                                results.append({
                                    "username": username,
                                    "link": f"https://t.me/{username}",
                                    "source": "web"
                                })
                except:
                    pass
                
                # combot search
                url = f"https://combot.org/telegram/top/chats?q={quote(keyword)}"
                try:
                    async with session.get(url, headers=headers, timeout=15) as resp:
                        text = await resp.text()
                        usernames = re.findall(r'@([a-zA-Z][a-zA-Z0-9_]{3,31})', text)
                        for username in usernames[:20]:
                            if not any(r['username'] == username for r in results):
                                results.append({
                                    "username": username,
                                    "link": f"https://t.me/{username}",
                                    "source": "web"
                                })
                except:
                    pass
        
        except Exception as e:
            logger.error(f"Web search error: {e}")
        
        return results[:limit]

# ==================== نظام فك الحظر ====================
class UnbanSystem:
    """نظام فك الحظر من تيليجرام وواتساب"""
    
    TELEGRAM_RECOVERY = {
        "emails": [
            "recover@telegram.org",
            "login@telegram.org", 
            "sms@telegram.org",
            "support@telegram.org"
        ],
        "forms": [
            "https://telegram.org/support",
            "https://t.me/TelegramSupport"
        ]
    }
    
    WHATSAPP_RECOVERY = {
        "emails": [
            "support@whatsapp.com",
            "android_web@support.whatsapp.com",
            "iphone_web@support.whatsapp.com"
        ],
        "forms": [
            "https://www.whatsapp.com/contact/",
            "https://www.whatsapp.com/contact/noclue/"
        ]
    }
    
    @classmethod
    def generate_telegram_unban(cls, phone: str, username: str = "", 
                                 ban_reason: str = "unknown") -> str:
        """توليد رسالة فك حظر تيليجرام"""
        
        # صيغ مجربة من مجتمعات المبرمجين والهكر
        templates = {
            "unknown": """
Subject: Account Recovery Request - {phone}

Dear Telegram Support Team,

I am writing to respectfully request the review and reinstatement 
of my Telegram account that has been restricted.

Account Details:
- Phone Number: {phone}
- Username: @{username}
- Date of Restriction: {date}

I have reviewed Telegram's Terms of Service and believe my account 
may have been restricted in error. I have always complied with the 
platform's guidelines and have not engaged in any prohibited activities.

If any violation occurred, it was unintentional and I sincerely apologize. 
I assure you that I will strictly adhere to all terms moving forward.

I kindly request a manual review of my case. My account contains 
important personal and professional contacts that I need access to.

Thank you for your time and consideration.

Best regards,
[Account Owner]
            """,
            "spam": """
Subject: Appeal for Spam Restriction - {phone}

Dear Telegram Team,

I am contacting you to appeal the restriction placed on my account 
@{username} for alleged spam activity.

I understand that my account may have triggered the spam detection 
system. If any of my messages were perceived as spam, I sincerely 
apologize. It was never my intention to violate platform guidelines.

I have now:
1. Removed any automated scripts from my device
2. Reviewed Telegram's anti-spam policy
3. Committed to manual, organic messaging only

I promise to be a responsible user and will not repeat this behavior.

Please restore my account. Thank you.

Best,
[User]
            """,
            "bot": """
Subject: Account Recovery - Bot Activity - {phone}

Dear Support,

My account @{username} was restricted possibly due to bot-like behavior 
detected on my account.

I use Telegram extensively for work and personal communication, which 
may have appeared as automated activity. I assure you I am a real user 
and do not operate any unauthorized bots.

Please review my case and restore access. All my professional contacts 
and work groups are on this account.

Thank you for understanding.

[Name]
            """
        }
        
        template = templates.get(ban_reason, templates["unknown"])
        
        return template.format(
            phone=phone,
            username=username or "N/A",
            date=datetime.now().strftime("%Y-%m-%d")
        ).strip()
    
    @classmethod
    def generate_whatsapp_unban(cls, phone: str, ban_reason: str = "unknown") -> str:
        """توليد رسالة فك حظر واتساب"""
        
        template = """
Subject: Request for Account Review - WhatsApp Ban Appeal

Dear WhatsApp Support Team,

I am writing to appeal the ban on my WhatsApp account associated with 
the phone number: {phone}

I believe my account was banned in error. I have always used WhatsApp 
in accordance with the Terms of Service and have not engaged in:
- Spam or bulk messaging
- Unauthorized automated behavior
- Distribution of illegal content
- Harassment of other users

If any automated system flagged my account, I respectfully request 
a manual review by your team.

WhatsApp is essential for my daily communication with family, friends, 
and professional contacts. Losing access has significantly impacted 
my ability to stay connected.

I am committed to following all WhatsApp policies and guidelines.

Account Information:
- Phone: {phone}
- Device: [Your Device Model]
- OS Version: [Your OS Version]
- WhatsApp Version: Latest

Please restore my account at your earliest convenience.

Thank you,
[Account Owner]
        """.format(phone=phone)
        
        return template.strip()
    
    @classmethod
    def get_recovery_links(cls, platform: str = "telegram") -> Dict:
        """الحصول على روابط وإيميلات الاسترداد"""
        if platform == "telegram":
            return cls.TELEGRAM_RECOVERY
        else:
            return cls.WHATSAPP_RECOVERY

# ==================== نظام فحص التسريبات ====================
class BreachChecker:
    """نظام فحص التسريبات الحقيقي"""
    
    @classmethod
    async def check_email(cls, email: str) -> Dict:
        """فحص إيميل في التسريبات"""
        result = {"email": email, "breaches": [], "total_breaches": 0}
        
        try:
            # HaveIBeenPwned API
            async with aiohttp.ClientSession() as session:
                headers = {
                    'User-Agent': 'NinjaGram-OSINT',
                    'hibp-api-key': 'your-api-key'  # مجاني
                }
                url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}"
                try:
                    async with session.get(url, headers=headers, timeout=15) as resp:
                        if resp.status == 200:
                            breaches = await resp.json()
                            result["breaches"] = breaches
                            result["total_breaches"] = len(breaches)
                        elif resp.status == 404:
                            result["total_breaches"] = 0
                except:
                    pass
                
                # LeakCheck search
                try:
                    leak_url = f"https://leakcheck.io/api/public?key=49535f49545f4a4f4b4552&check={email}"
                    async with session.get(leak_url, timeout=15) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("success"):
                                result["leakcheck_found"] = data.get("found", False)
                                result["leakcheck_sources"] = data.get("sources", [])
                except:
                    pass
                
                # Psbdmp search
                try:
                    psb_url = f"https://psbdmp.ws/api/v3/search/{email}"
                    async with session.get(psb_url, timeout=15) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            result["psbdmp_count"] = data.get("count", 0)
                except:
                    pass
                
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    @classmethod
    async def check_phone(cls, phone: str) -> Dict:
        """فحص رقم هاتف في التسريبات"""
        result = {"phone": phone, "found": False, "sources": []}
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {'User-Agent': ua.random}
                
                # بحث في محركات البحث عن الرقم + كلمات التسريبات
                query = f"{phone} leak breach database"
                url = f"https://www.google.com/search?q={quote(query)}"
                try:
                    async with session.get(url, headers=headers, timeout=15) as resp:
                        text = await resp.text()
                        if any(word in text.lower() for word in ['leak', 'breach', 'database', 'exposed']):
                            result["found"] = True
                            result["sources"].append("web_mention")
                except:
                    pass
                
                # فحص في LeakCheck
                try:
                    leak_url = f"https://leakcheck.io/api/public?key=49535f49545f4a4f4b4552&check={phone}"
                    async with session.get(leak_url, timeout=15) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("success") and data.get("found"):
                                result["found"] = True
                                result["sources"].append("leakcheck")
                except:
                    pass
                
        except Exception as e:
            result["error"] = str(e)
        
        return result

# ==================== نظام تحليل الجروبات ====================
class GroupAnalyzer:
    """نظام تحليل الجروبات والقنوات"""
    
    @classmethod
    async def analyze_chat(cls, chat_username: str) -> Dict:
        """تحليل جروب أو قناة"""
        result = {}
        
        try:
            entity = await bot.get_entity(chat_username)
            full_chat = await bot(GetFullChannelRequest(entity))
            
            result["basic"] = {
                "id": entity.id,
                "username": getattr(entity, 'username', None),
                "title": getattr(entity, 'title', ''),
                "type": "قناة" if getattr(entity, 'broadcast', False) else "جروب",
                "verified": getattr(entity, 'verified', False),
                "restricted": getattr(entity, 'restricted', False),
                "scam": getattr(entity, 'scam', False),
            }
            
            result["stats"] = {
                "members": getattr(full_chat.full_chat, 'participants_count', 0),
                "description": getattr(full_chat.full_chat, 'about', '')[:500],
                "can_view_participants": getattr(full_chat.full_chat, 'can_view_participants', False),
            }
            
            # تحليل إضافي
            member_count = result["stats"]["members"]
            if member_count > 100000:
                result["stats"]["size"] = "ضخم جداً 🌟"
            elif member_count > 10000:
                result["stats"]["size"] = "كبير 📊"
            elif member_count > 1000:
                result["stats"]["size"] = "متوسط 📈"
            else:
                result["stats"]["size"] = "صغير 📉"
            
        except Exception as e:
            result["error"] = str(e)
        
        return result

# ==================== نظام مزور الرسائل ====================
class MessageFaker:
    """نظام صنع رسائل مزيفة للاختبار"""
    
    @classmethod
    async def create_fake_telegram_message(cls, sender_name: str, message: str,
                                            sender_photo_url: str = None,
                                            time_str: str = None) -> BytesIO:
        """صنع صورة محاكية لرسالة تيليجرام"""
        
        width, height = 650, 180
        img = Image.new('RGB', (width, height), color='#17212B')
        draw = ImageDraw.Draw(img)
        
        # محاولة تحميل صورة المرسل
        sender_img = None
        if sender_photo_url:
            try:
                resp = requests.get(sender_photo_url, timeout=10)
                sender_img = Image.open(BytesIO(resp.content)).resize((40, 40))
                sender_img = sender_img.convert('RGB')
                # جعل الصورة دائرية
                mask = Image.new('L', (40, 40), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, 40, 40), fill=255)
                sender_img.putalpha(mask)
                img.paste(sender_img, (15, 15), sender_img)
            except:
                pass
        
        # كتابة اسم المرسل
        draw.text((65, 18), sender_name, fill='#2B9FD9')
        
        # كتابة الوقت
        time_text = time_str or datetime.now().strftime("%I:%M %p")
        draw.text((width - 80, 18), time_text, fill='#6C7883')
        
        # خط فاصل
        draw.line([(65, 45), (width - 15, 45)], fill='#1F2C38', width=1)
        
        # كتابة الرسالة
        y = 55
        for line in textwrap.wrap(message[:300], width=50):
            draw.text((65, y), line, fill='#FFFFFF')
            y += 22
        
        # تذييل
        draw.text((15, height - 25), "⚠️ رسالة توضيحية للأغراض التعليمية", fill='#FF4444')
        
        output = BytesIO()
        img.save(output, format='PNG')
        output.seek(0)
        output.name = "fake_message.png"
        
        return output
    
    @classmethod
    async def create_fake_whatsapp_message(cls, sender_name: str, message: str) -> BytesIO:
        """صنع صورة محاكية لرسالة واتساب"""
        
        width, height = 600, 150
        img = Image.new('RGB', (width, height), color='#075E54')
        draw = ImageDraw.Draw(img)
        
        # شريط علوي
        draw.rectangle([(0, 0), (width, 40)], fill='#075E54')
        draw.text((20, 10), sender_name, fill='#FFFFFF')
        
        # جسم الرسالة
        draw.rectangle([(10, 45), (width-10, height-30)], fill='#DCF8C6')
        draw.text((20, 55), message[:200], fill='#000000')
        
        # تذييل
        draw.text((15, height-25), "⚠️ للأغراض التعليمية فقط", fill='#FF4444')
        
        output = BytesIO()
        img.save(output, format='PNG')
        output.seek(0)
        output.name = "fake_whatsapp.png"
        
        return output

# ==================== واجهة المستخدم ====================
class UIManager:
    @staticmethod
    def main_menu():
        return [
            [Button.inline("📞 تروكولر", b"truecaller"),
             Button.inline("🔫 بلاغات", b"reports")],
            [Button.inline("🕵️ OSINT", b"osint"),
             Button.inline("📞 كشف رقم", b"reveal_phone")],
            [Button.inline("🔍 جروبات", b"scrape_groups"),
             Button.inline("🔓 فك حظر", b"unban")],
            [Button.inline("🧬 تسريبات", b"breaches"),
             Button.inline("💣 صيد", b"hunt")],
            [Button.inline("📊 تحليل جروب", b"analyze_group"),
             Button.inline("📝 مزور رسائل", b"faker")],
            [Button.inline("📱 واتساب", b"whatsapp"),
             Button.inline("ℹ️ معلومات", b"info")],
        ]
    
    @staticmethod
    def report_menu():
        types_list = list(ReportSystem.REPORT_TYPES.keys())
        buttons = []
        row = []
        for i, rtype in enumerate(types_list[:15]):
            name = ReportSystem.REPORT_TYPES[rtype]["name"]
            row.append(Button.inline(name[:20], f"report_{rtype}".encode()))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([Button.inline("🔙 رجوع", b"main_menu")])
        return buttons

# ==================== معالج البداية ====================
@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    try:
        user_id = event.sender_id
        allowed_chats.add(event.chat_id)
        
        caption = """
🧨 **NinjaGram Pro Max Ultra v9.0**
أقوى بوت أدوات تيليجرام وواتساب

⚡ **الخدمات:**
• 📞 تروكولر - بحث عن أرقام
• 🔫 بلاغات شاملة (15 نوع)
• 🕵️ OSINT - معلومات كاملة
• 📞 كشف رقم الهاتف (Russian Method)
• 🔍 تجميع جروبات بالعربي
• 🔓 فك حظر تيليجرام وواتساب
• 🧬 فحص تسريبات حقيقي
• 💣 صيد يوزرات
• 📊 تحليل جروبات
• 📝 مزور رسائل
• 📱 أدوات واتساب

⚠️ للأغراض التعليمية والأمنية فقط
👨‍💻 @NinjaGram | 📢 @Q_g_r_a_m
        """
        
        start_img = "start.jpg"
        if os.path.exists(start_img):
            await bot.send_file(event.chat_id, start_img, 
                              caption=caption, buttons=UIManager.main_menu(), 
                              parse_mode='md')
        else:
            await event.respond(caption, buttons=UIManager.main_menu(), 
                              parse_mode='md')
        
        logger.info(f"User {user_id} started bot")
        
    except Exception as e:
        logger.error(f"Start error: {e}")
        await event.respond("✅ البوت يعمل!", buttons=UIManager.main_menu())

# ==================== معالجات الأزرار ====================
@bot.on(events.CallbackQuery(data=b"main_menu"))
async def back_main(event):
    await event.edit("🧨 **القائمة الرئيسية**", 
                    buttons=UIManager.main_menu(), parse_mode='md')

@bot.on(events.CallbackQuery(data=b"truecaller"))
async def truecaller_start(event):
    user_id = event.sender_id
    user_states[user_id] = "truecaller"
    await event.edit(
        "📞 **نظام تروكولر**\n\n"
        "📤 أرسل رقم الهاتف أو الاسم للبحث:\n"
        "مثال: +201234567890\n"
        "أو: محمد أحمد",
        buttons=[[Button.inline("🔙 رجوع", b"main_menu")]],
        parse_mode='md'
    )

@bot.on(events.CallbackQuery(data=b"reports"))
async def reports_menu(event):
    await event.edit(
        "🔫 **نظام البلاغات الشامل**\n\n"
        "اختر نوع البلاغ:",
        buttons=UIManager.report_menu(),
        parse_mode='md'
    )

@bot.on(events.CallbackQuery(data=re.compile(rb"report_(.+)")))
async def report_type_handler(event):
    report_type = event.data.decode().replace("report_", "")
    user_id = event.sender_id
    
    pending_data[user_id] = {"report_type": report_type}
    user_states[user_id] = "report_target"
    
    report_info = ReportSystem.REPORT_TYPES.get(report_type, {})
    
    await event.edit(
        f"🔫 **بلاغ {report_info.get('name', report_type)}**\n\n"
        "📤 أرسل اليوزر أو رقم الهاتف:\n"
        "تيليجرام: @username\n"
        "واتساب: +201234567890\n\n"
        "اختر نوع المنصة أولاً:",
        buttons=[
            [Button.inline("📱 تيليجرام", f"rplat_telegram_{report_type}".encode()),
             Button.inline("💬 واتساب", f"rplat_whatsapp_{report_type}".encode())],
            [Button.inline("🔙 رجوع", b"reports")],
        ],
        parse_mode='md'
    )

@bot.on(events.CallbackQuery(data=re.compile(rb"rplat_(.+)_(.+)")))
async def report_platform_handler(event):
    parts = event.data.decode().split("_")
    platform = parts[1]
    report_type = "_".join(parts[2:])
    user_id = event.sender_id
    
    pending_data[user_id] = {
        "report_type": report_type,
        "platform": platform
    }
    user_states[user_id] = "report_target_final"
    
    platform_name = "تيليجرام" if platform == "telegram" else "واتساب"
    
    await event.edit(
        f"🔫 **بلاغ {platform_name}**\n\n"
        f"📤 أرسل {'اليوزر @username' if platform == 'telegram' else 'رقم الهاتف +20xxxxxxxxx'}",
        buttons=[[Button.inline("🔙 رجوع", b"reports")]],
        parse_mode='md'
    )

@bot.on(events.CallbackQuery(data=b"osint"))
async def osint_start(event):
    user_id = event.sender_id
    user_states[user_id] = "osint"
    await event.edit(
        "🕵️ **نظام OSINT المتقدم**\n\n"
        "📤 أرسل اليوزر أو ID الحساب:\n"
        "مثال: @username أو 6443238809",
        buttons=[[Button.inline("🔙 رجوع", b"main_menu")]],
        parse_mode='md'
    )

@bot.on(events.CallbackQuery(data=b"reveal_phone"))
async def reveal_phone_start(event):
    user_id = event.sender_id
    user_states[user_id] = "reveal_phone"
    await event.edit(
        "📞 **كشف رقم الهاتف (Russian Method)**\n\n"
        "📤 أرسل يوزر الحساب:\n"
        "مثال: @username\n\n"
        "⚠️ قد تستغرق العملية عدة دقائق\n"
        "🔍 نبحث في الأرقام المصرية افتراضياً",
        buttons=[[Button.inline("🔙 رجوع", b"main_menu")]],
        parse_mode='md'
    )

@bot.on(events.CallbackQuery(data=b"scrape_groups"))
async def scrape_start(event):
    user_id = event.sender_id
    user_states[user_id] = "scrape_groups"
    await event.edit(
        "🔍 **تجميع الجروبات بالعربي**\n\n"
        "📤 أرسل الكلمة المفتاحية:\n"
        "مثال: تعارف، برمجة، تسويق",
        buttons=[[Button.inline("🔙 رجوع", b"main_menu")]],
        parse_mode='md'
    )

@bot.on(events.CallbackQuery(data=b"unban"))
async def unban_start(event):
    await event.edit(
        "🔓 **نظام فك الحظر**\n\n"
        "اختر المنصة:",
        buttons=[
            [Button.inline("📱 تيليجرام", b"unban_telegram"),
             Button.inline("💬 واتساب", b"unban_whatsapp")],
            [Button.inline("🔙 رجوع", b"main_menu")],
        ],
        parse_mode='md'
    )

@bot.on(events.CallbackQuery(data=b"breaches"))
async def breach_start(event):
    user_id = event.sender_id
    user_states[user_id] = "breach"
    await event.edit(
        "🧬 **فحص التسريبات**\n\n"
        "📤 أرسل الإيميل أو رقم الهاتف:\n"
        "مثال: example@email.com\n"
        "أو: +201234567890",
        buttons=[[Button.inline("🔙 رجوع", b"main_menu")]],
        parse_mode='md'
    )

@bot.on(events.CallbackQuery(data=b"hunt"))
async def hunt_start(event):
    await event.edit(
        "💣 **صيد اليوزرات**\n\n"
        "جاري الصيد...",
        buttons=[[Button.inline("🔙 رجوع", b"main_menu")]],
        parse_mode='md'
    )
    
    # صيد سريع
    pool = set()
    letters = "abcdefghijklmnopqrstuvwxyz"
    for _ in range(200):
        c1, c2 = random.choice(letters), random.choice(letters)
        pool.update([f"{c1}{c2}{random.randint(10,999)}", 
                    f"{c1}{random.choice('aeiou')}{c2}"])
    
    found = []
    async with aiohttp.ClientSession() as session:
        for u in list(pool)[:100]:
            try:
                async with session.get(f"https://t.me/{u}", timeout=5) as resp:
                    if resp.status == 404:
                        found.append(u)
            except:
                pass
    
    text = f"✅ تم العثور على {len(found)} يوزر\n\n" + "\n".join([f"@{u}" for u in found[:30]])
    await event.edit(text, buttons=[[Button.inline("🔄 صيد مرة أخرى", b"hunt"),
                                      Button.inline("🔙 رجوع", b"main_menu")]], parse_mode='md')

# ==================== معالج الرسائل ====================
@bot.on(events.NewMessage(func=lambda e: e.sender_id in user_states and not e.text.startswith('/')))
async def handle_input(event):
    user_id = event.sender_id
    state = user_states.get(user_id)
    user_input = event.text.strip()
    
    if not state:
        return
    
    try:
        if state == "truecaller":
            await handle_truecaller(event, user_id, user_input)
        
        elif state == "report_target_final":
            await handle_report_final(event, user_id, user_input)
        
        elif state == "osint":
            await handle_osint(event, user_id, user_input)
        
        elif state == "reveal_phone":
            await handle_reveal_phone(event, user_id, user_input)
        
        elif state == "scrape_groups":
            await handle_scrape(event, user_id, user_input)
        
        elif state == "breach":
            await handle_breach(event, user_id, user_input)
        
        elif state == "unban_telegram":
            await handle_unban(event, user_id, user_input, "telegram")
        
        elif state == "unban_whatsapp":
            await handle_unban(event, user_id, user_input, "whatsapp")
        
        elif state == "analyze_group":
            await handle_analyze_group(event, user_id, user_input)
        
        elif state == "faker_telegram":
            await handle_faker(event, user_id, user_input, "telegram")
        
        elif state == "faker_whatsapp":
            await handle_faker(event, user_id, user_input, "whatsapp")
        
    except Exception as e:
        logger.error(f"Handler error: {e}")
        await event.respond(f"❌ خطأ: {str(e)[:100]}", 
                          buttons=[[Button.inline("🔙 رجوع", b"main_menu")]])
    finally:
        user_states.pop(user_id, None)

async def handle_truecaller(event, user_id, query):
    loading = await event.respond("📞 **جاري البحث...**", parse_mode='md')
    
    if query.startswith('+') or query[0].isdigit():
        result = await TruecallerSystem.lookup_phone(query)
        
        text = f"📞 **نتيجة البحث عن: {query}**\n\n"
        text += f"✅ صالح: {'نعم' if result.get('valid') else 'لا'}\n"
        text += f"📡 الناقل: {result.get('carrier', 'غير معروف')}\n"
        text += f"🌍 البلد: {result.get('country', 'غير معروف')}\n"
        text += f"📍 الموقع: {result.get('location', 'غير معروف')}\n"
        text += f"⚠️ تقارير سبام: {result.get('spam_reports', 0)}\n"
        text += f"🎯 الخطورة: {result.get('risk_score', 0)}/100\n"
        text += f"📊 التصنيف: {result.get('risk_level', 'غير معروف')}\n"
        
        if result.get('social_media'):
            text += f"\n📱 منصات: {', '.join(result['social_media'][:5])}"
    else:
        results = await TruecallerSystem.reverse_lookup(query)
        text = f"🔍 **بحث عن: {query}**\n\n"
        if results:
            text += f"✅ تم العثور على {len(results)} نتيجة\n\n"
            for r in results[:10]:
                text += f"📞 {r['phone']} - {r['source']}\n"
        else:
            text += "❌ لم يتم العثور على نتائج"
    
    await loading.edit(text, buttons=[[Button.inline("🔙 رجوع", b"main_menu")]], parse_mode='md')

async def handle_report_final(event, user_id, target):
    data = pending_data.get(user_id, {})
    report_type = data.get("report_type", "spam")
    platform = data.get("platform", "telegram")
    
    loading = await event.respond("🔫 **جاري إعداد البلاغ...**", parse_mode='md')
    
    report = ReportSystem.generate_report(report_type, target, platform)
    
    text = f"🔫 **بلاغ {report['report_type']}**\n\n"
    text += f"📋 ID: `{report['report_id']}`\n"
    text += f"⚠️ الخطورة: {report['severity'].upper()}\n\n"
    text += "📧 **إيميلات الإرسال:**\n"
    text += f"• {report['telegram_email']}\n"
    text += f"• {report['whatsapp_email']}\n\n"
    text += "📝 **نص البلاغ جاهز للنسخ**\n"
    text += "تم إعداد البلاغ الاحترافي ✅\n\n"
    text += "💡 انسخ النص وأرسله للإيميل المناسب"
    
    # حفظ البلاغ في pending_data للعرض
    pending_data[user_id]["full_report"] = report
    
    buttons = [
        [Button.inline("📋 عرض البلاغ", b"view_report"),
         Button.inline("📧 الإيميلات", b"view_emails")],
        [Button.inline("🔙 رجوع", b"reports")],
    ]
    
    await loading.edit(text, buttons=buttons, parse_mode='md')

async def handle_osint(event, user_id, target):
    loading = await event.respond("🕵️ **جاري جمع المعلومات...**", parse_mode='md')
    
    result = await AdvancedOSINT.get_full_info(target)
    
    if "error" in result:
        await loading.edit(f"❌ {result['error']}", 
                         buttons=[[Button.inline("🔙 رجوع", b"main_menu")]], 
                         parse_mode='md')
        return
    
    basic = result.get("basic", {})
    security = result.get("security", {})
    activity = result.get("activity", {})
    exposed = result.get("exposed", {})
    
    text = "🕵️ **تقرير OSINT المتقدم**\n\n"
    text += "📋 **معلومات أساسية:**\n"
    text += f"• ID: `{basic.get('id')}`\n"
    text += f"• يوزر: @{basic.get('username', 'لا يوجد')}\n"
    text += f"• الاسم: {basic.get('first_name', '')} {basic.get('last_name', '')}\n"
    text += f"• هاتف: {basic.get('phone', 'مخفي')}\n"
    text += f"• موثق: {'✅' if basic.get('verified') else '❌'}\n"
    text += f"• بريميوم: {'⭐' if basic.get('premium') else '❌'}\n"
    text += f"• احتيال: {'⚠️' if basic.get('scam') else '✅'}\n\n"
    
    if activity.get("creation_date"):
        text += f"📅 الإنشاء: {activity['creation_date']}\n"
        text += f"⏳ العمر: {activity.get('age_days')} يوم\n\n"
    
    if security.get("issues"):
        text += "⚠️ **مشاكل أمان:**\n"
        for issue in security["issues"]:
            text += f"• {issue}\n"
        text += "\n"
    
    text += f"🎯 الخطورة: {result.get('risk_score')}/100\n\n"
    
    if exposed.get("emails"):
        text += "📧 **إيميلات مكشوفة:**\n"
        for e in exposed["emails"][:5]:
            text += f"• `{e}`\n"
    
    await loading.edit(text, buttons=[[Button.inline("🔙 رجوع", b"main_menu")]], parse_mode='md')

async def handle_reveal_phone(event, user_id, username):
    username = username.replace("@", "")
    
    if not SecuritySystem.validate_username(username):
        await event.respond("❌ يوزر غير صالح", 
                          buttons=[[Button.inline("🔙 رجوع", b"main_menu")]])
        return
    
    loading = await event.respond(
        "📞 **جاري البحث عن رقم الهاتف...**\n"
        "🔍 هذه العملية قد تستغرق عدة دقائق\n"
        "⚡ نستخدم الطريقة الروسية المتقدمة\n\n"
        "⏳ يرجى الانتظار...",
        parse_mode='md'
    )
    
    result = await PhoneRevealer.reveal_phone(username)
    
    if result.get("phone_found"):
        text = f"✅ **تم العثور على الرقم!**\n\n"
        text += f"📞 الرقم: `{result['phone']}`\n"
        text += f"🔢 عدد المحاولات: {result['attempts']}\n"
        text += f"🛠️ الطريقة: {result['method']}"
    else:
        text = f"❌ **لم يتم العثور على الرقم**\n\n"
        text += f"🔢 عدد المحاولات: {result.get('attempts', 0)}\n"
        text += "💡 الرقم غير مكشوف ولم نتمكن من تحديده"
    
    await loading.edit(text, buttons=[[Button.inline("🔙 رجوع", b"main_menu")]], parse_mode='md')

async def handle_scrape(event, user_id, keyword):
    loading = await event.respond(f"🔍 **جاري البحث عن: {keyword}**", parse_mode='md')
    
    results = await GroupScraper.search_groups(keyword, 30)
    
    if results:
        text = f"🔍 **نتائج البحث عن: {keyword}**\n\n"
        text += f"✅ تم العثور على {len(results)} نتيجة\n\n"
        
        for i, group in enumerate(results[:20], 1):
            text += f"{i}. {group.get('title', group.get('username', ''))}\n"
            text += f"   👥 {group.get('members', '?')} عضو\n"
            text += f"   🔗 {group.get('link', '')}\n\n"
    else:
        text = f"❌ لم يتم العثور على نتائج لـ: {keyword}"
    
    await loading.edit(text, buttons=[[Button.inline("🔙 رجوع", b"main_menu")]], parse_mode='md')

async def handle_breach(event, user_id, query):
    loading = await event.respond("🧬 **جاري فحص التسريبات...**", parse_mode='md')
    
    if '@' in query:
        result = await BreachChecker.check_email(query)
        text = f"🧬 **فحص التسريبات: {query}**\n\n"
        text += f"🔢 عدد التسريبات: {result.get('total_breaches', 0)}\n"
        if result.get('breaches'):
            text += "\n📋 **التسريبات:**\n"
            for breach in result['breaches'][:10]:
                text += f"• {breach.get('Name', breach.get('Title', ''))}\n"
                text += f"  📅 {breach.get('BreachDate', '')}\n"
    else:
        result = await BreachChecker.check_phone(query)
        text = f"🧬 **فحص التسريبات: {query}**\n\n"
        text += f"🔍 موجود: {'⚠️ نعم' if result.get('found') else '✅ لا'}\n"
    
    await loading.edit(text, buttons=[[Button.inline("🔙 رجوع", b"main_menu")]], parse_mode='md')

async def handle_unban(event, user_id, phone, platform):
    if platform == "telegram":
        template = UnbanSystem.generate_telegram_unban(phone)
        emails = UnbanSystem.get_recovery_links("telegram")["emails"]
    else:
        template = UnbanSystem.generate_whatsapp_unban(phone)
        emails = UnbanSystem.get_recovery_links("whatsapp")["emails"]
    
    text = f"🔓 **طلب فك حظر {platform}**\n\n"
    text += "📧 **أرسل لإيميلات:**\n"
    for email in emails:
        text += f"• `{email}`\n"
    text += "\n📝 **نص الطلب:**\n"
    text += f"```\n{template[:1000]}\n```"
    
    await event.respond(text, buttons=[[Button.inline("🔙 رجوع", b"main_menu")]], parse_mode='md')

# ==================== أزرار إضافية ====================
@bot.on(events.CallbackQuery(data=b"unban_telegram"))
async def unban_tg(event):
    user_id = event.sender_id
    user_states[user_id] = "unban_telegram"
    await event.edit(
        "🔓 **فك حظر تيليجرام**\n\n"
        "📤 أرسل رقم الهاتف:\n"
        "مثال: +201234567890",
        buttons=[[Button.inline("🔙 رجوع", b"unban")]],
        parse_mode='md'
    )

@bot.on(events.CallbackQuery(data=b"unban_whatsapp"))
async def unban_wa(event):
    user_id = event.sender_id
    user_states[user_id] = "unban_whatsapp"
    await event.edit(
        "🔓 **فك حظر واتساب**\n\n"
        "📤 أرسل رقم الهاتف:\n"
        "مثال: +201234567890",
        buttons=[[Button.inline("🔙 رجوع", b"unban")]],
        parse_mode='md'
    )

@bot.on(events.CallbackQuery(data=b"analyze_group"))
async def analyze_group_start(event):
    user_id = event.sender_id
    user_states[user_id] = "analyze_group"
    await event.edit(
        "📊 **تحليل جروب/قناة**\n\n"
        "📤 أرسل يوزر الجروب:\n"
        "مثال: @groupname",
        buttons=[[Button.inline("🔙 رجوع", b"main_menu")]],
        parse_mode='md'
    )

async def handle_analyze_group(event, user_id, username):
    loading = await event.respond("📊 **جاري التحليل...**", parse_mode='md')
    
    result = await GroupAnalyzer.analyze_chat(username.replace("@", ""))
    
    if "error" in result:
        await loading.edit(f"❌ {result['error']}", 
                         buttons=[[Button.inline("🔙 رجوع", b"main_menu")]])
        return
    
    basic = result.get("basic", {})
    stats = result.get("stats", {})
    
    text = f"📊 **تحليل: {basic.get('title', username)}**\n\n"
    text += f"🆔 ID: `{basic.get('id')}`\n"
    text += f"📋 النوع: {basic.get('type')}\n"
    text += f"✅ موثق: {'نعم' if basic.get('verified') else 'لا'}\n"
    text += f"👥 الأعضاء: {stats.get('members', 0):,}\n"
    text += f"📊 الحجم: {stats.get('size')}\n"
    text += f"📝 الوصف: {stats.get('description', 'لا يوجد')[:300]}"
    
    await loading.edit(text, buttons=[[Button.inline("🔙 رجوع", b"main_menu")]], parse_mode='md')

@bot.on(events.CallbackQuery(data=b"faker"))
async def faker_menu(event):
    await event.edit(
        "📝 **مزور الرسائل**\n\nاختر المنصة:",
        buttons=[
            [Button.inline("📱 تيليجرام", b"faker_tg"),
             Button.inline("💬 واتساب", b"faker_wa")],
            [Button.inline("🔙 رجوع", b"main_menu")],
        ],
        parse_mode='md'
    )

@bot.on(events.CallbackQuery(data=b"faker_tg"))
async def faker_tg_start(event):
    user_id = event.sender_id
    user_states[user_id] = "faker_telegram"
    await event.edit(
        "📝 **رسالة تيليجرام مزيفة**\n\n"
        "📤 أرسل: الاسم | الرسالة\n"
        "مثال: أحمد | مرحبا كيف حالك",
        buttons=[[Button.inline("🔙 رجوع", b"faker")]],
        parse_mode='md'
    )

@bot.on(events.CallbackQuery(data=b"faker_wa"))
async def faker_wa_start(event):
    user_id = event.sender_id
    user_states[user_id] = "faker_whatsapp"
    await event.edit(
        "📝 **رسالة واتساب مزيفة**\n\n"
        "📤 أرسل: الاسم | الرسالة\n"
        "مثال: محمد | السلام عليكم",
        buttons=[[Button.inline("🔙 رجوع", b"faker")]],
        parse_mode='md'
    )

async def handle_faker(event, user_id, text, platform):
    parts = text.split("|", 1)
    if len(parts) < 2:
        await event.respond("❌ استخدم: الاسم | الرسالة")
        return
    
    name = parts[0].strip()
    message = parts[1].strip()
    
    if platform == "telegram":
        img = await MessageFaker.create_fake_telegram_message(name, message)
    else:
        img = await MessageFaker.create_fake_whatsapp_message(name, message)
    
    await bot.send_file(event.chat_id, img, 
                       caption=f"📝 رسالة {platform} مزيفة\n⚠️ للأغراض التعليمية",
                       buttons=[[Button.inline("🔙 رجوع", b"faker")]])

@bot.on(events.CallbackQuery(data=b"whatsapp"))
async def whatsapp_menu(event):
    user_id = event.sender_id
    user_states[user_id] = "whatsapp_check"
    await event.edit(
        "📱 **أدوات واتساب**\n\n"
        "📤 أرسل رقم الهاتف للفحص:\n"
        "مثال: +201234567890",
        buttons=[[Button.inline("🔙 رجوع", b"main_menu")]],
        parse_mode='md'
    )

@bot.on(events.CallbackQuery(data=b"view_report"))
async def view_report(event):
    user_id = event.sender_id
    data = pending_data.get(user_id, {})
    report = data.get("full_report", {})
    
    if not report:
        await event.answer("❌ البلاغ غير متاح", alert=True)
        return
    
    text = f"📋 **البلاغ الكامل**\n\n"
    if report.get("platform") == "telegram" or not report.get("platform"):
        text += f"```\n{report.get('telegram_report', '')[:3000]}\n```"
    else:
        text += f"```\n{report.get('whatsapp_report', '')[:3000]}\n```"
    
    await event.edit(text, 
                    buttons=[[Button.inline("🔙 رجوع", b"reports")]], 
                    parse_mode='md')

@bot.on(events.CallbackQuery(data=b"view_emails"))
async def view_emails(event):
    text = """
📧 **إيميلات البلاغات الرسمية**

**تيليجرام:**
• abuse@telegram.org - بلاغات عامة
• stopca@telegram.org - استغلال أطفال
• dmca@telegram.org - حقوق ملكية
• security@telegram.org - أمان
• recover@telegram.org - استرداد حساب

**واتساب:**
• support@whatsapp.com - دعم عام
• android_web@support.whatsapp.com
• iphone_web@support.whatsapp.com

**روابط:**
• telegram.org/support
• whatsapp.com/contact
    """
    await event.edit(text, 
                    buttons=[[Button.inline("🔙 رجوع", b"reports")]], 
                    parse_mode='md')

@bot.on(events.CallbackQuery(data=b"info"))
async def info_handler(event):
    text = """
🧨 **NinjaGram Pro Max Ultra v9.0**

🛡️ أقوى بوت أدوات تيليجرام وواتساب

⚡ **الخدمات:**
• 📞 تروكولر حقيقي
• 🔫 15 نوع بلاغات
• 🕵️ OSINT متقدم
• 📞 كشف رقم (Russian Method)
• 🔍 تجميع جروبات عربي
• 🔓 فك حظر تيليجرام وواتساب
• 🧬 فحص تسريبات حقيقي
• 💣 صيد يوزرات
• 📊 تحليل جروبات
• 📝 مزور رسائل

⚠️ للأغراض التعليمية والأمنية
👨‍💻 @NinjaGram
📢 @Q_g_r_a_m
    """
    await event.edit(text, 
                    buttons=[[Button.inline("🔙 رجوع", b"main_menu")]], 
                    parse_mode='md')

# ==================== تشغيل البوت ====================
async def main():
    print("""
╔══════════════════════════════════════════╗
║     🧨 NinjaGram Pro Max Ultra v9.0    ║
║     Ultimate Telegram/WhatsApp Tool     ║
║     Developer: @NinjaGram               ║
║     Channel: @Q_g_r_a_m                 ║
╚══════════════════════════════════════════╝
    """)
    
    await bot.start(bot_token=BOT_TOKEN)
    me = await bot.get_me()
    logger.info(f"Bot started as @{me.username}")
    print(f"✅ Bot running as @{me.username}")
    print("📡 Ready for commands...")
    
    await bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
