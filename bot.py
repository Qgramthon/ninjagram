#!/usr/bin/env python3
"""
▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
🔥 بوت تيليجرام OSINT متكامل لفحص الأرقام
▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀

📦 المتطلبات:
pip install telethon pyrogram tgcrypto httpx beautifulsoup4 lxml \
    python-telegram-bot aiofiles aiosqlite fake-useragent dnspython \
    phonenumbers cryptography

🔑 API Keys مجانية (لازم تعملها الأول):
1. NumVerify: https://numverify.com (100 فحص/شهر مجاناً)
2. AbstractAPI: https://abstractapi.com (100 فحص/شهر مجاناً)
3. Hunter.io: https://hunter.io (25 فحص/شهر مجاناً)

⚠️ إخلاء مسؤولية:
هذا الكود للأغراض التعليمية فقط. استخدامه لانتهاك خصوصية الآخرين
قد يكون غير قانوني في بلدك. أنت المسؤول الوحيد عن استخدامك.

▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
"""

import os
import sys
import asyncio
import logging
import re
import json
import base64
import hashlib
import time
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import quote, urlencode
import aiofiles
import aiosqlite
import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import phonenumbers
from phonenumbers import carrier, geocoder, timezone as ph_timezone

# Telegram
from telethon import TelegramClient, events, functions, types
from telethon.errors import (
    SessionPasswordNeededError, PhoneNumberInvalidError,
    PhoneCodeInvalidError, FloodWaitError, PhoneNumberBannedError
)
from telethon.sessions import StringSession
from telethon.tl.functions.contacts import AddContactRequest, DeleteContactsRequest
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.types import InputPhoneContact

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode

# ==================== الإعدادات الأساسية ====================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("OSINT_BOT")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8879863328:AAH_PB_1i50hIyU-UI58TcD-dflHl4dBFqo")

# API Keys (مجانية)
NUMVERIFY_KEY = os.environ.get("NUMVERIFY_KEY", "")      # https://numverify.com
ABSTRACT_API_KEY = os.environ.get("ABSTRACT_API_KEY", "") # https://abstractapi.com
HUNTER_API_KEY = os.environ.get("HUNTER_API_KEY", "")     # https://hunter.io

# ==================== قاعدة بيانات محلية ====================

DB_PATH = "osint_bot.db"

async def init_db():
    """تهيئة قاعدة البيانات"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                session_data TEXT,
                phone TEXT,
                api_id TEXT,
                api_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lookup_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                target_phone TEXT,
                results TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                user_id INTEGER,
                service TEXT,
                api_key TEXT,
                PRIMARY KEY (user_id, service)
            )
        """)
        await db.commit()

async def save_user(user_id: int, session_data: str, phone: str, api_id: str, api_hash: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO users (user_id, session_data, phone, api_id, api_hash) 
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, session_data, phone, api_id, api_hash)
        )
        await db.commit()

async def get_user(user_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "user_id": row[0],
                    "session_data": row[1],
                    "phone": row[2],
                    "api_id": row[3],
                    "api_hash": row[4]
                }
    return None

async def delete_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await db.commit()

async def save_lookup(user_id: int, phone: str, results: Dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO lookup_history (user_id, target_phone, results) VALUES (?, ?, ?)",
            (user_id, phone, json.dumps(results))
        )
        await db.commit()

async def save_api_key(user_id: int, service: str, key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO api_keys (user_id, service, api_key) VALUES (?, ?, ?)",
            (user_id, service, key)
        )
        await db.commit()

async def get_api_key(user_id: int, service: str) -> Optional[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT api_key FROM api_keys WHERE user_id = ? AND service = ?",
            (user_id, service)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

# ==================== متغيرات الجلسة ====================

login_states: Dict[int, Dict] = {}
active_clients: Dict[int, TelegramClient] = {}
ua = UserAgent()

# ==================== فئة فحص الأرقام المتكاملة ====================

class PhoneIntel:
    """
    محرك الاستخبارات - يجمع كل مصادر المعلومات
    """
    
    def __init__(self, phone: str):
        self.phone = phone
        self.parsed = self._parse_phone()
        self.results = {
            "phone": phone,
            "timestamp": datetime.now().isoformat(),
            "sources": {}
        }
    
    def _parse_phone(self):
        """تحليل الرقم دولياً"""
        try:
            parsed = phonenumbers.parse(self.phone)
            return {
                "valid": phonenumbers.is_valid_number(parsed),
                "country": geocoder.description_for_number(parsed, "ar") or geocoder.description_for_number(parsed, "en"),
                "carrier": carrier.name_for_number(parsed, "ar") or carrier.name_for_number(parsed, "en"),
                "timezone": ph_timezone.time_zones_for_number(parsed),
                "national": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL),
                "international": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
                "e164": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164),
                "country_code": parsed.country_code,
                "national_number": parsed.national_number
            }
        except:
            return {"valid": False, "error": "رقم غير صالح"}

    # ──────────────────────────────────────
    # المصدر 1: NumVerify API (مجاني)
    # ──────────────────────────────────────
    async def check_numverify(self, api_key: str = None):
        """فحص بواسطة NumVerify"""
        api_key = api_key or NUMVERIFY_KEY
        if not api_key:
            self.results["sources"]["numverify"] = {"status": "no_api_key"}
            return
        
        try:
            params = {
                "access_key": api_key,
                "number": self.phone,
                "format": 1
            }
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get("http://apilayer.net/api/validate", params=params)
                data = resp.json()
                
                self.results["sources"]["numverify"] = {
                    "status": "success",
                    "valid": data.get("valid", False),
                    "number": data.get("international_format", ""),
                    "local_format": data.get("local_format", ""),
                    "country": data.get("country_name", ""),
                    "location": data.get("location", ""),
                    "carrier": data.get("carrier", "غير معروف"),
                    "line_type": data.get("line_type", ""),
                    "raw": data
                }
        except Exception as e:
            self.results["sources"]["numverify"] = {"status": "error", "error": str(e)}

    # ──────────────────────────────────────
    # المصدر 2: AbstractAPI Phone Validation (مجاني)
    # ──────────────────────────────────────
    async def check_abstractapi(self, api_key: str = None):
        """فحص بواسطة AbstractAPI"""
        api_key = api_key or ABSTRACT_API_KEY
        if not api_key:
            self.results["sources"]["abstractapi"] = {"status": "no_api_key"}
            return
        
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"https://phonevalidation.abstractapi.com/v1/",
                    params={"api_key": api_key, "phone": self.phone}
                )
                data = resp.json()
                
                self.results["sources"]["abstractapi"] = {
                    "status": "success",
                    "valid": data.get("valid", False),
                    "country": data.get("country", {}).get("name", ""),
                    "carrier": data.get("carrier", "غير معروف"),
                    "type": data.get("type", ""),
                    "risky": data.get("risky", False),
                    "raw": data
                }
        except Exception as e:
            self.results["sources"]["abstractapi"] = {"status": "error", "error": str(e)}

    # ──────────────────────────────────────
    # المصدر 3: فحص تيليجرام (Telethon)
    # ──────────────────────────────────────
    async def check_telegram(self, client: TelegramClient):
        """فحص إذا كان الرقم مسجل على تيليجرام + معلومات إضافية"""
        try:
            # إضافة الرقم كجهة اتصال
            contact = InputPhoneContact(
                client_id=0,
                phone=self.phone,
                first_name="OSINT_CHECK",
                last_name=""
            )
            
            result = await client(functions.contacts.ImportContactsRequest([contact]))
            
            if result.users:
                user = result.users[0]
                user_info = {
                    "status": "success",
                    "exists": True,
                    "user_id": user.id,
                    "username": user.username or "لا يوجد",
                    "first_name": user.first_name or "",
                    "last_name": user.last_name or "",
                    "full_name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
                    "is_bot": user.bot,
                    "is_verified": user.verified,
                    "is_premium": getattr(user, 'premium', False),
                    "mutual_contact": getattr(user, 'mutual_contact', False),
                }
                
                # لو المستخدم يسمح برؤية رقمه
                if hasattr(user, 'phone') and user.phone:
                    user_info['visible_phone'] = user.phone
                
                # حذف جهة الاتصال بعد الفحص
                await client(functions.contacts.DeleteContactsRequest(id=[user.id]))
                
                self.results["sources"]["telegram"] = user_info
            else:
                self.results["sources"]["telegram"] = {
                    "status": "success",
                    "exists": False
                }
                
        except FloodWaitError as e:
            self.results["sources"]["telegram"] = {
                "status": "error",
                "error": f"انتظر {e.seconds} ثانية"
            }
        except Exception as e:
            self.results["sources"]["telegram"] = {
                "status": "error",
                "error": str(e)
            }
    
    # ──────────────────────────────────────
    # المصدر 4: فحص واتساب (متعدد الطرق)
    # ──────────────────────────────────────
    async def check_whatsapp(self):
        """فحص واتساب باستخدام طرق متعددة"""
        clean = self.phone.replace("+", "").replace(" ", "").replace("-", "")
        
        methods = {}
        
        # طريقة 1: wa.me الرسمي
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                headers = {"User-Agent": ua.random}
                resp = await client.get(f"https://wa.me/{clean}", headers=headers)
                
                # لو موجود، الصفحة هتحتوي على زر "متابعة للمحادثة"
                if "Continue to Chat" in resp.text or "متابعة إلى الدردشة" in resp.text:
                    methods["wa_me"] = True
                else:
                    methods["wa_me"] = False
        except:
            methods["wa_me"] = None
        
        # طريقة 2: WhatsApp Business API endpoint
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                headers = {
                    "User-Agent": "WhatsApp/2.23.25.83 Android",
                    "Accept": "application/json"
                }
                resp = await client.get(
                    f"https://wa.me/{clean}",
                    headers=headers,
                    follow_redirects=True
                )
                methods["wa_api"] = "exist" in resp.text.lower() if resp.status_code == 200 else None
        except:
            methods["wa_api"] = None
        
        # تجميع النتائج
        exists = methods.get("wa_me") or methods.get("wa_api")
        
        self.results["sources"]["whatsapp"] = {
            "status": "success",
            "exists": exists if exists is not None else "غير معروف",
            "methods": methods
        }
    
    # ──────────────────────────────────────
    # المصدر 5: Truecaller (بحث غير رسمي)
    # ──────────────────────────────────────
    async def check_truecaller(self):
        """فحص Truecaller عن طريق صفحة البحث العامة"""
        clean = self.phone.replace("+", "")
        
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                headers = {
                    "User-Agent": ua.random,
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "ar,en;q=0.9"
                }
                
                # صفحة البحث العلنية
                resp = await client.get(
                    f"https://www.truecaller.com/search/eg/{clean}",
                    headers=headers
                )
                
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'lxml')
                    
                    # البحث عن الاسم
                    name_element = soup.find("div", {"class": "profile-name"}) or \
                                  soup.find("h1", {"class": "profile-name"})
                    
                    if name_element:
                        self.results["sources"]["truecaller"] = {
                            "status": "success",
                            "found": True,
                            "name": name_element.text.strip()
                        }
                    else:
                        # محاولة البحث في الجافاسكريبت المضمن
                        scripts = soup.find_all("script")
                        for script in scripts:
                            if script.string and "name" in script.string.lower():
                                try:
                                    # البحث عن أنماط JSON
                                    json_pattern = r'\"name\":\s*\"([^\"]+)\"'
                                    match = re.search(json_pattern, script.string)
                                    if match:
                                        self.results["sources"]["truecaller"] = {
                                            "status": "success",
                                            "found": True,
                                            "name": match.group(1)
                                        }
                                        return
                                except:
                                    pass
                        
                        self.results["sources"]["truecaller"] = {
                            "status": "success",
                            "found": False
                        }
        except Exception as e:
            self.results["sources"]["truecaller"] = {
                "status": "error",
                "error": str(e)
            }
    
    # ──────────────────────────────────────
    # المصدر 6: Hunter.io (بريد مرتبط)
    # ──────────────────────────────────────
    async def check_hunter(self, api_key: str = None):
        """
        فحص إذا كان هناك بريد إلكتروني مرتبط بالرقم
        يستخدم Hunter.io Email Finder
        """
        api_key = api_key or HUNTER_API_KEY
        if not api_key:
            self.results["sources"]["hunter"] = {"status": "no_api_key"}
            return
        
        try:
            # نحتاج domain للبحث، نستخدم شركات الاتصالات المصرية كمثال
            # في الواقع، هذا الفحص يعمل بشكل أفضل لو عندك نطاق معين
            domains = ["gmail.com", "yahoo.com", "hotmail.com"]
            found_emails = []
            
            async with httpx.AsyncClient(timeout=15) as client:
                for domain in domains[:1]:  # نفحص نطاق واحد لتوفير quota
                    resp = await client.get(
                        "https://api.hunter.io/v2/email-finder",
                        params={
                            "api_key": api_key,
                            "domain": domain,
                            "phone": self.phone
                        }
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("data", {}).get("email"):
                            found_emails.append({
                                "email": data["data"]["email"],
                                "confidence": data["data"].get("confidence", 0),
                                "domain": domain
                            })
            
            self.results["sources"]["hunter"] = {
                "status": "success",
                "emails_found": len(found_emails),
                "emails": found_emails
            }
        except Exception as e:
            self.results["sources"]["hunter"] = {
                "status": "error",
                "error": str(e)
            }
    
    # ──────────────────────────────────────
    # المصدر 7: فحص فيسبوك (تجريبي)
    # ──────────────────────────────────────
    async def check_facebook(self):
        """
        فحص إذا كان الرقم مرتبط بحساب فيسبوك
        يستخدم صفحة استعادة كلمة المرور
        """
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                headers = {
                    "User-Agent": ua.random,
                    "Accept": "text/html,application/xhtml+xml",
                }
                
                # صفحة البحث عن الحساب برقم الهاتف
                resp = await client.get(
                    "https://www.facebook.com/login/identify",
                    params={"ctx": "recover", "ars": "facebook_login"},
                    headers=headers
                )
                
                if resp.status_code == 200:
                    # البحث عن أي إشارة أن الرقم مرتبط بحساب
                    soup = BeautifulSoup(resp.text, 'lxml')
                    
                    # هذه الطريقة ليست دقيقة 100% لكنها مؤشر
                    fb_indicators = [
                        "password reset",
                        "إعادة تعيين",
                        "account",
                        "حساب"
                    ]
                    
                    text = resp.text.lower()
                    found = any(ind in text for ind in fb_indicators)
                    
                    self.results["sources"]["facebook"] = {
                        "status": "success",
                        "possibly_linked": found,
                        "note": "مؤشر فقط - ليس تأكيداً"
                    }
        except Exception as e:
            self.results["sources"]["facebook"] = {
                "status": "error",
                "error": str(e)
            }
    
    # ──────────────────────────────────────
    # تجميع كل المصادر
    # ──────────────────────────────────────
    async def full_intel(self, client: TelegramClient = None, 
                         numverify_key: str = None,
                         abstract_key: str = None,
                         hunter_key: str = None):
        """تشغيل كل الفحوصات المتاحة"""
        
        tasks = []
        
        # المهام الأساسية (لا تحتاج API keys)
        tasks.append(self.check_whatsapp())
        tasks.append(self.check_truecaller())
        
        # فحص تيليجرام (يحتاج client)
        if client:
            tasks.append(self.check_telegram(client))
        
        # فحوصات API
        if numverify_key or NUMVERIFY_KEY:
            tasks.append(self.check_numverify(numverify_key))
        
        if abstract_key or ABSTRACT_API_KEY:
            tasks.append(self.check_abstractapi(abstract_key))
        
        if hunter_key or HUNTER_API_KEY:
            tasks.append(self.check_hunter(hunter_key))
        
        # تشغيل الكل بالتوازي
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return self.results

    # ──────────────────────────────────────
    # تنسيق التقرير النهائي
    # ──────────────────────────────────────
    def format_report(self) -> str:
        """تنسيق النتائج في تقرير جميل"""
        
        r = self.results
        p = self.parsed
        
        report = []
        report.append("▀" * 30)
        report.append("📱 تقرير استخباراتي متكامل")
        report.append("▄" * 30)
        report.append("")
        
        # معلومات الرقم الأساسية
        report.append(f"📞 الرقم: `{self.phone}`")
        report.append(f"🌍 الدولة: {p.get('country', 'غير معروف')}")
        report.append(f"📶 الشبكة: {p.get('carrier', 'غير معروف')}")
        report.append(f"✅ الصلاحية: {'صحيح' if p.get('valid') else 'غير صحيح'}")
        report.append(f"🕐 التوقيت: {', '.join(p.get('timezone', ['غير معروف']))}")
        report.append("")
        
        # المصادر
        sources = r.get("sources", {})
        
        # NumVerify
        nv = sources.get("numverify", {})
        if nv.get("status") == "success":
            report.append("─" * 25)
            report.append("🔍 NumVerify:")
            report.append(f"  ├ صالح: {'✅' if nv.get('valid') else '❌'}")
            report.append(f"  ├ النوع: {nv.get('line_type', 'غير معروف')}")
            report.append(f"  └ الموقع: {nv.get('location', 'غير معروف')}")
            report.append("")
        
        # AbstractAPI
        ab = sources.get("abstractapi", {})
        if ab.get("status") == "success":
            report.append("─" * 25)
            report.append("🔍 AbstractAPI:")
            report.append(f"  ├ صالح: {'✅' if ab.get('valid') else '❌'}")
            report.append(f"  ├ النوع: {ab.get('type', 'غير معروف')}")
            report.append(f"  └ خطير: {'⚠️ نعم' if ab.get('risky') else '✅ لا'}")
            report.append("")
        
        # تيليجرام
        tg = sources.get("telegram", {})
        if tg.get("exists"):
            report.append("─" * 25)
            report.append("📡 تيليجرام: ✅ موجود")
            report.append(f"  ├ الاسم: {tg.get('full_name', 'غير معروف')}")
            report.append(f"  ├ يوزر: @{tg.get('username', 'لا يوجد')}")
            report.append(f"  ├ ID: `{tg.get('user_id', 'غير معروف')}`")
            report.append(f"  ├ مميز: {'⭐ نعم' if tg.get('is_premium') else '❌ لا'}")
            report.append(f"  └ موثق: {'✅ نعم' if tg.get('is_verified') else '❌ لا'}")
            report.append("")
        elif tg.get("status") == "success" and not tg.get("exists"):
            report.append("📡 تيليجرام: ❌ غير مسجل")
            report.append("")
        
        # واتساب
        wa = sources.get("whatsapp", {})
        if wa.get("status") == "success":
            exists = wa.get("exists")
            if exists is True:
                report.append("💬 واتساب: ✅ موجود")
            elif exists is False:
                report.append("💬 واتساب: ❌ غير مسجل")
            else:
                report.append(f"💬 واتساب: ⚠️ {exists}")
            report.append("")
        
        # Truecaller
        tc = sources.get("truecaller", {})
        if tc.get("found"):
            report.append("─" * 25)
            report.append("👤 Truecaller: ✅")
            report.append(f"  └ الاسم: {tc.get('name', 'غير معروف')}")
            report.append("")
        
        # Hunter.io
        hu = sources.get("hunter", {})
        if hu.get("emails_found", 0) > 0:
            report.append("─" * 25)
            report.append("📧 البريد المرتبط:")
            for email in hu.get("emails", []):
                report.append(f"  └ {email['email']} (ثقة: {email['confidence']}%)")
            report.append("")
        
        # فيسبوك
        fb = sources.get("facebook", {})
        if fb.get("possibly_linked"):
            report.append("📘 فيسبوك: ⚠️ يحتمل وجود حساب مرتبط")
            report.append("")
        
        report.append("▀" * 30)
        report.append(f"🕐 وقت الفحص: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("🔒 جميع البيانات سرية ولا تتم مشاركتها")
        report.append("▄" * 30)
        
        return "\n".join(report)

# ==================== أوامر البوت ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب"""
    keyboard = [
        [InlineKeyboardButton("🔍 فحص رقم", callback_data="lookup"),
         InlineKeyboardButton("ℹ️ المساعدة", callback_data="help")],
        [InlineKeyboardButton("🔑 إعداد API", callback_data="setup_api"),
         InlineKeyboardButton("📊 حالتي", callback_data="status")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔥 **بوت OSINT المتكامل**\n\n"
        "أداة استخباراتية لجمع المعلومات من المصادر المفتوحة.\n\n"
        "⚠️ للأغراض التعليمية والبحثية فقط.\n"
        "أنت المسؤول عن استخدامك للأداة.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض المساعدة"""
    await update.message.reply_text(
        "📚 **دليل الاستخدام:**\n\n"
        "1️⃣ سجل دخولك: /login\n"
        "2️⃣ افحص رقم: /lookup +201234567890\n"
        "3️⃣ فحص سريع: /quick +201234567890\n\n"
        "🔑 **مفاتيح API (اختياري):**\n"
        "/setapi numverify <key>\n"
        "/setapi abstract <key>\n"
        "/setapi hunter <key>\n\n"
        "⚙️ **أوامر أخرى:**\n"
        "/status - حالة حسابك\n"
        "/history - سجل الفحوصات\n"
        "/logout - تسجيل الخروج\n\n"
        "🆓 المفاتيح المجانية:\n"
        "• numverify.com (100/شهر)\n"
        "• abstractapi.com (100/شهر)\n"
        "• hunter.io (25/شهر)",
        parse_mode=ParseMode.MARKDOWN
    )

async def login_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء تسجيل الدخول"""
    uid = update.effective_user.id
    
    user = await get_user(uid)
    if user:
        await update.message.reply_text("✅ لديك حساب مسجل بالفعل!")
        return
    
    login_states[uid] = {"step": "api_id"}
    await update.message.reply_text(
        "📱 **تسجيل الدخول - الخطوة 1/4**\n\n"
        "أرسل API_ID الخاص بك.\n"
        "للحصول عليه:\n"
        "1. افتح https://my.telegram.org\n"
        "2. سجل دخول برقمك\n"
        "3. اذهب إلى API Development Tools\n"
        "4. انسخ api_id",
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الرسائل لتسجيل الدخول"""
    uid = update.effective_user.id
    text = update.message.text.strip()
    
    if uid not in login_states:
        return
    
    state = login_states[uid]
    step = state["step"]
    
    try:
        if step == "api_id":
            api_id = int(text)
            state["api_id"] = api_id
            state["step"] = "api_hash"
            await update.message.reply_text("✅ **الخطوة 2/4:** أرسل API_HASH:")
        
        elif step == "api_hash":
            state["api_hash"] = text
            state["step"] = "phone"
            await update.message.reply_text(
                "✅ **الخطوة 3/4:** أرسل رقم الهاتف:\n"
                "مثال: +201234567890"
            )
        
        elif step == "phone":
            if not text.startswith("+"):
                await update.message.reply_text("❌ يجب أن يبدأ الرقم بـ +")
                return
            
            state["phone"] = text
            
            # إنشاء عميل
            client = TelegramClient(
                StringSession(),
                state["api_id"],
                state["api_hash"]
            )
            await client.connect()
            
            try:
                sent = await client.send_code_request(text)
                state["client"] = client
                state["phone_code_hash"] = sent.phone_code_hash
                state["step"] = "code"
                
                await update.message.reply_text(
                    "✅ **الخطوة 4/4:** تم إرسال رمز التحقق.\n"
                    "أرسل الرمز هنا (مثال: 12345)"
                )
            except Exception as e:
                await client.disconnect()
                del login_states[uid]
                await update.message.reply_text(f"❌ خطأ: {e}")
        
        elif step == "code":
            client = state["client"]
            
            try:
                await client.sign_in(
                    phone=state["phone"],
                    code=text,
                    phone_code_hash=state["phone_code_hash"]
                )
                await finish_login(update, state)
            except SessionPasswordNeededError:
                state["step"] = "password"
                await update.message.reply_text("🔒 حسابك محمي بكلمة مرور. أرسلها:")
            except Exception as e:
                await client.disconnect()
                del login_states[uid]
                await update.message.reply_text(f"❌ خطأ: {e}")
        
        elif step == "password":
            client = state["client"]
            
            try:
                await client.sign_in(password=text)
                await finish_login(update, state)
            except Exception as e:
                await client.disconnect()
                del login_states[uid]
                await update.message.reply_text(f"❌ كلمة مرور خطأ: {e}")
    
    except ValueError:
        await update.message.reply_text("❌ قيمة غير صالحة، حاول مرة أخرى:")

async def finish_login(update: Update, state: Dict):
    """إكمال تسجيل الدخول وحفظ الجلسة"""
    uid = update.effective_user.id
    client = state["client"]
    
    try:
        me = await client.get_me()
        session_string = client.session.save()
        
        await save_user(
            uid,
            session_string,
            state["phone"],
            str(state["api_id"]),
            state["api_hash"]
        )
        
        await update.message.reply_text(
            f"✅ **تم تسجيل الدخول بنجاح!**\n\n"
            f"👤 الاسم: {me.first_name}\n"
            f"📱 الرقم: {me.phone}\n"
            f"🆔 ID: {me.id}\n\n"
            f"يمكنك الآن استخدام:\n"
            f"/lookup <رقم> للفحص الكامل\n"
            f"/quick <رقم> للفحص السريع",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ في الحفظ: {e}")
    finally:
        await client.disconnect()
        del login_states[uid]

async def lookup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فحص رقم هاتف كامل"""
    uid = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text(
            "📱 **استخدام:** /lookup <رقم>\n"
            "مثال: /lookup +201234567890"
        )
        return
    
    phone = context.args[0]
    if not phone.startswith("+"):
        await update.message.reply_text("❌ يجب أن يبدأ الرقم بـ +")
        return
    
    # الحصول على جلسة المستخدم
    user = await get_user(uid)
    client = None
    
    if user:
        try:
            client = TelegramClient(
                StringSession(user["session_data"]),
                int(user["api_id"]),
                user["api_hash"]
            )
            await client.connect()
        except:
            pass
    
    # رسالة انتظار
    msg = await update.message.reply_text(f"🔍 جاري فحص `{phone}`...\nقد يستغرق 30-60 ثانية")
    
    # جلب مفاتيح API
    numverify_key = await get_api_key(uid, "numverify") or NUMVERIFY_KEY
    abstract_key = await get_api_key(uid, "abstract") or ABSTRACT_API_KEY
    hunter_key = await get_api_key(uid, "hunter") or HUNTER_API_KEY
    
    # تشغيل الفحص
    intel = PhoneIntel(phone)
    
    try:
        results = await intel.full_intel(
            client=client,
            numverify_key=numverify_key,
            abstract_key=abstract_key,
            hunter_key=hunter_key
        )
        
        report = intel.format_report()
        
        # حفظ في السجل
        await save_lookup(uid, phone, results)
        
        # إرسال التقرير
        await msg.edit_text(report, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        await msg.edit_text(f"❌ خطأ في الفحص: {e}")
    finally:
        if client:
            await client.disconnect()

async def quick_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فحص سريع - تيليجرام وواتساب فقط"""
    uid = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text("📱 **استخدام:** /quick <رقم>")
        return
    
    phone = context.args[0]
    
    user = await get_user(uid)
    if not user:
        await update.message.reply_text("❌ سجل دخول أولاً: /login")
        return
    
    msg = await update.message.reply_text("⚡ فحص سريع...")
    
    try:
        client = TelegramClient(
            StringSession(user["session_data"]),
            int(user["api_id"]),
            user["api_hash"]
        )
        await client.connect()
        
        intel = PhoneIntel(phone)
        await asyncio.gather(
            intel.check_telegram(client),
            intel.check_whatsapp()
        )
        
        # تقرير مختصر
        tg = intel.results["sources"].get("telegram", {})
        wa = intel.results["sources"].get("whatsapp", {})
        
        quick_report = f"""
📱 فحص سريع: `{phone}`

📡 تيليجرام: {'✅ موجود - ' + tg.get('full_name', '') if tg.get('exists') else '❌ غير مسجل'}
💬 واتساب: {'✅ موجود' if wa.get('exists') else '❌ غير مسجل'}

للفحص الكامل: /lookup {phone}
"""
        await msg.edit_text(quick_report, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        await msg.edit_text(f"❌ خطأ: {e}")
    finally:
        await client.disconnect()

async def setapi_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تعيين مفاتيح API"""
    uid = update.effective_user.id
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "🔑 **استخدام:**\n"
            "/setapi numverify <key>\n"
            "/setapi abstract <key>\n"
            "/setapi hunter <key>\n\n"
            "🔗 **روابط التسجيل:**\n"
            "• https://numverify.com\n"
            "• https://abstractapi.com\n"
            "• https://hunter.io"
        )
        return
    
    service = context.args[0].lower()
    key = context.args[1]
    
    valid_services = ["numverify", "abstract", "hunter"]
    if service not in valid_services:
        await update.message.reply_text(f"❌ خدمة غير معروفة. المتاح: {', '.join(valid_services)}")
        return
    
    await save_api_key(uid, service, key)
    await update.message.reply_text(f"✅ تم حفظ مفتاح {service} بنجاح")

async def apistatus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حالة المفاتيح"""
    uid = update.effective_user.id
    
    services = {
        "numverify": "NumVerify",
        "abstract": "AbstractAPI",
        "hunter": "Hunter.io"
    }
    
    report = "🔑 **حالة المفاتيح:**\n\n"
    
    for srv, name in services.items():
        user_key = await get_api_key(uid, srv)
        global_key = {
            "numverify": NUMVERIFY_KEY,
            "abstract": ABSTRACT_API_KEY,
            "hunter": HUNTER_API_KEY
        }.get(srv, "")
        
        if user_key:
            report += f"✅ {name}: مفتاحك الخاص\n"
        elif global_key:
            report += f"✅ {name}: المفتاح العام\n"
        else:
            report += f"❌ {name}: غير متوفر\n"
    
    await update.message.reply_text(report, parse_mode=ParseMode.MARKDOWN)

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حالة المستخدم"""
    uid = update.effective_user.id
    user = await get_user(uid)
    
    if user:
        await update.message.reply_text(
            "🟢 **حالتك:**\n"
            f"📱 الرقم: {user['phone']}\n"
            f"🔑 API: متاح\n\n"
            f"استخدم /lookup للفحص"
        )
    else:
        await update.message.reply_text(
            "🔴 غير مسجل\n"
            "استخدم /login لتسجيل الدخول"
        )

async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """سجل الفحوصات"""
    uid = update.effective_user.id
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT target_phone, created_at FROM lookup_history WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
            (uid,)
        ) as cursor:
            rows = await cursor.fetchall()
    
    if not rows:
        await update.message.reply_text("📭 لا يوجد سجل فحوصات")
        return
    
    history = "📊 **آخر 10 فحوصات:**\n\n"
    for phone, date in rows:
        history += f"📱 {phone} - {date}\n"
    
    await update.message.reply_text(history, parse_mode=ParseMode.MARKDOWN)

async def logout_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تسجيل الخروج"""
    uid = update.effective_user.id
    await delete_user(uid)
    
    if uid in active_clients:
        try:
            await active_clients[uid].disconnect()
        except:
            pass
        del active_clients[uid]
    
    await update.message.reply_text("✅ تم تسجيل الخروج وحذف بياناتك")

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء العملية الحالية"""
    uid = update.effective_user.id
    if uid in login_states:
        if "client" in login_states[uid]:
            try:
                await login_states[uid]["client"].disconnect()
            except:
                pass
        del login_states[uid]
        await update.message.reply_text("✅ تم الإلغاء")
    else:
        await update.message.reply_text("لا توجد عملية جارية")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الأزرار"""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    
    if action == "lookup":
        await query.edit_message_text(
            "استخدم: /lookup <رقم>\nمثال: /lookup +201234567890"
        )
    elif action == "help":
        await help_cmd(update, context)
    elif action == "setup_api":
        await query.edit_message_text(
            "🔑 **لإضافة مفتاح:**\n"
            "/setapi numverify <key>\n"
            "/setapi abstract <key>\n"
            "/setapi hunter <key>"
        )
    elif action == "status":
        await status_cmd(update, context)

# ==================== الدالة الرئيسية ====================

async def main():
    """تشغيل البوت"""
    
    # تهيئة قاعدة البيانات
    await init_db()
    
    # إنشاء التطبيق
    app = Application.builder().token(BOT_TOKEN).build()
    
    # الأوامر
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("login", login_start))
    app.add_handler(CommandHandler("lookup", lookup_cmd))
    app.add_handler(CommandHandler("quick", quick_cmd))
    app.add_handler(CommandHandler("setapi", setapi_cmd))
    app.add_handler(CommandHandler("apistatus", apistatus_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("history", history_cmd))
    app.add_handler(CommandHandler("logout", logout_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    
    # معالج الرسائل
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # معالج الأزرار
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    # معلومات التشغيل
    print("=" * 50)
    print("🔥 بوت OSINT المتكامل")
    print("=" * 50)
    print(f"📱 NumVerify: {'✅' if NUMVERIFY_KEY else '❌'} (مجاني)")
    print(f"📱 Abstract: {'✅' if ABSTRACT_API_KEY else '❌'} (مجاني)")
    print(f"📱 Hunter.io: {'✅' if HUNTER_API_KEY else '❌'} (مجاني)")
    print("=" * 50)
    print("⚡ البوت شغال...")
    
    # تشغيل
    await app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 تم إيقاف البوت")
    except Exception as e:
        print(f"❌ خطأ: {e}")
