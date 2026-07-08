#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║              بوت تيليجرام متكامل - OSINT                ║
║         المستخدم يتحمل المسؤولية القانونية كاملة         ║
╚══════════════════════════════════════════════════════════╝
"""

import os
import sys
import asyncio
import logging
import json
import random
import re
import time
import base64
import hashlib
import socket
import ssl
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urlencode, quote

# مكتبات الطرف الثالث
import httpx
import aiosqlite
import aiofiles
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from flask import Flask, request, jsonify
import phonenumbers
from phonenumbers import carrier, geocoder, timezone as ph_timezone
from cryptography.fernet import Fernet

# تيليجرام
from telethon import TelegramClient, events
from telethon.errors import (
    SessionPasswordNeededError, FloodWaitError, 
    PhoneNumberInvalidError, PhoneCodeInvalidError
)
from telethon.sessions import StringSession
from telethon.tl.functions.contacts import (
    ImportContactsRequest, DeleteContactsRequest, 
    GetContactsRequest
)
from telethon.tl.types import InputPhoneContact
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.users import GetFullUserRequest

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode

# ==================== التهيئة ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MEGA_BOT")

# Flask للتشغيل الدائم
web_app = Flask(__name__)
PORT = int(os.environ.get("PORT", 8080))
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8879863328:AAH_PB_1i50hIyU-UI58TcD-dflHl4dBFqo")

# مفاتيح API اختيارية
NUMVERIFY_KEY = os.environ.get("NUMVERIFY_KEY", "")
ABSTRACT_API_KEY = os.environ.get("ABSTRACT_API_KEY", "")
VIRUSTOTAL_KEY = os.environ.get("VIRUSTOTAL_KEY", "")
SHODAN_KEY = os.environ.get("SHODAN_KEY", "")
IPINFO_TOKEN = os.environ.get("IPINFO_TOKEN", "")

ua = UserAgent()

# ==================== قاعدة البيانات ====================
DB_PATH = "mega_bot.db"

async def init_database():
    """إنشاء جداول قاعدة البيانات"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                session_string TEXT,
                phone TEXT,
                api_id TEXT,
                api_hash TEXT,
                is_admin INTEGER DEFAULT 0,
                credits INTEGER DEFAULT 100,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS scan_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                target TEXT,
                scan_type TEXT,
                result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS api_keys (
                user_id INTEGER,
                service TEXT,
                api_key TEXT,
                PRIMARY KEY (user_id, service)
            );
            
            CREATE TABLE IF NOT EXISTS sms_services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                url TEXT,
                method TEXT DEFAULT 'POST',
                phone_param TEXT,
                headers TEXT,
                body_template TEXT,
                success_indicator TEXT,
                is_active INTEGER DEFAULT 1,
                country TEXT DEFAULT 'GLOBAL',
                category TEXT DEFAULT 'general'
            );
            
            CREATE TABLE IF NOT EXISTS target_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                list_name TEXT,
                targets TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await db.commit()

# ==================== التشفير ====================
fernet_key = Fernet.generate_key()
cipher = Fernet(fernet_key)

def encrypt(data: str) -> str:
    return cipher.encrypt(data.encode()).decode()

def decrypt(data: str) -> str:
    return cipher.decrypt(data.encode()).decode()

# ==================== إدارة الجلسات ====================
class SessionManager:
    def __init__(self):
        self.active_sessions = {}
        self.login_states = {}
        self.user_clients = {}
    
    async def save_session(self, user_id: int, session: str, phone: str, 
                          api_id: str, api_hash: str):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT OR REPLACE INTO users 
                   (user_id, session_string, phone, api_id, api_hash) 
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, encrypt(session), encrypt(phone), 
                 encrypt(api_id), encrypt(api_hash))
            )
            await db.commit()
    
    async def get_session(self, user_id: int) -> Optional[Dict]:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "user_id": row[0],
                        "session_string": decrypt(row[2]) if row[2] else None,
                        "phone": decrypt(row[3]) if row[3] else None,
                        "api_id": decrypt(row[4]) if row[4] else None,
                        "api_hash": decrypt(row[5]) if row[5] else None,
                        "credits": row[7]
                    }
        return None
    
    async def delete_session(self, user_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            await db.commit()
    
    async def get_client(self, user_id: int) -> Optional[TelegramClient]:
        if user_id in self.user_clients:
            client = self.user_clients[user_id]
            if client.is_connected():
                return client
        
        session_data = await self.get_session(user_id)
        if not session_data:
            return None
        
        try:
            client = TelegramClient(
                StringSession(session_data["session_string"]),
                int(session_data["api_id"]),
                session_data["api_hash"]
            )
            await client.connect()
            
            if await client.is_user_authorized():
                self.user_clients[user_id] = client
                return client
        except:
            pass
        
        return None

session_manager = SessionManager()

# ==================== محرك الفحص الاستخباراتي ====================
class OSINTEngine:
    def __init__(self):
        self.results = {}
        self.sources = {}
    
    async def full_scan(self, target: str, scan_type: str = "phone") -> Dict:
        """تشغيل جميع الفحوصات المتاحة"""
        self.results = {"target": target, "type": scan_type, "timestamp": datetime.now().isoformat()}
        
        if scan_type == "phone":
            await self.phone_scan(target)
        elif scan_type == "email":
            await self.email_scan(target)
        elif scan_type == "username":
            await self.username_scan(target)
        elif scan_type == "ip":
            await self.ip_scan(target)
        elif scan_type == "url":
            await self.url_scan(target)
        
        return self.results
    
    async def phone_scan(self, phone: str):
        """فحص رقم الهاتف من جميع المصادر"""
        tasks = [
            self.check_telegram(phone),
            self.check_whatsapp(phone),
            self.check_viber(phone),
            self.check_signal(phone),
            self.check_truecaller(phone),
            self.check_getcontact(phone),
            self.check_numverify(phone),
            self.check_carrier_info(phone),
            self.check_facebook_reset(phone),
            self.check_google_account(phone),
            self.check_breaches(phone),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, dict):
                self.results.update(result)
    
    async def check_telegram(self, phone: str, client: TelegramClient = None):
        """فحص تيليجرام"""
        try:
            if not client:
                self.results["telegram"] = {"error": "No client available"}
                return
            
            contact = InputPhoneContact(
                client_id=0, phone=phone, 
                first_name="OSINT_BOT", last_name=""
            )
            
            result = await client(ImportContactsRequest([contact]))
            
            if result.users:
                user = result.users[0]
                full_user = await client(GetFullUserRequest(user))
                
                user_data = {
                    "exists": True,
                    "user_id": user.id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "phone_visible": bool(user.phone) if hasattr(user, 'phone') else False,
                    "is_premium": getattr(user, 'premium', False),
                    "is_verified": getattr(user, 'verified', False),
                    "is_bot": getattr(user, 'bot', False),
                    "language": getattr(user, 'lang_code', None),
                    "bio": full_user.full_user.about if hasattr(full_user.full_user, 'about') else None,
                    "common_chats": getattr(full_user, 'common_chats_count', 0),
                    "profile_photos_count": full_user.full_user.profile_photo.id if full_user.full_user.profile_photo else 0
                }
                
                self.results["telegram"] = user_data
                
                # حذف جهة الاتصال بعد الفحص
                await client(DeleteContactsRequest(id=[user.id]))
            else:
                self.results["telegram"] = {"exists": False}
                
        except Exception as e:
            self.results["telegram"] = {"error": str(e), "exists": False}
    
    async def check_whatsapp(self, phone: str):
        """فحص واتساب"""
        clean = phone.replace("+", "").replace(" ", "").replace("-", "")
        methods = {}
        
        try:
            # طريقة 1: wa.me
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                headers = {"User-Agent": ua.random}
                resp = await client.get(f"https://wa.me/{clean}", headers=headers)
                methods["wa_me"] = "Continue to Chat" in resp.text
        except:
            methods["wa_me"] = None
        
        try:
            # طريقة 2: WhatsApp Business API
            async with httpx.AsyncClient(timeout=10) as client:
                headers = {
                    "User-Agent": "WhatsApp/2.24.2.17 Android",
                    "Content-Type": "application/json"
                }
                resp = await client.post(
                    "https://v.whatsapp.com/v2/exist",
                    json={"cc": phone[:3], "in": phone[3:], "to": phone},
                    headers=headers
                )
                methods["api_check"] = resp.status_code == 200
        except:
            methods["api_check"] = None
        
        exists = methods.get("wa_me") or methods.get("api_check")
        self.results["whatsapp"] = {
            "exists": exists,
            "methods": methods
        }
    
    async def check_viber(self, phone: str):
        """فحص Viber"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                headers = {"User-Agent": ua.random}
                resp = await client.post(
                    "https://api.viber.com/api/v2/check",
                    json={"phone": phone},
                    headers=headers
                )
                if resp.status_code == 200:
                    data = resp.json()
                    self.results["viber"] = {
                        "exists": data.get("exists", False),
                        "name": data.get("name", "")
                    }
        except:
            self.results["viber"] = {"exists": None}
    
    async def check_signal(self, phone: str):
        """فحص Signal"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                headers = {"User-Agent": "Signal-Android/6.0"}
                resp = await client.get(
                    f"https://api.signal.org/v1/accounts/{phone}",
                    headers=headers
                )
                self.results["signal"] = {
                    "exists": resp.status_code == 200
                }
        except:
            self.results["signal"] = {"exists": None}
    
    async def check_truecaller(self, phone: str):
        """فحص Truecaller"""
        clean = phone.replace("+", "")
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                headers = {
                    "User-Agent": ua.random,
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "ar,en;q=0.9"
                }
                
                resp = await client.get(
                    f"https://www.truecaller.com/search/eg/{clean}",
                    headers=headers
                )
                
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'lxml')
                    
                    # البحث عن الاسم في JSON المضمن
                    scripts = soup.find_all("script", type="application/ld+json")
                    for script in scripts:
                        if script.string:
                            try:
                                data = json.loads(script.string)
                                name = data.get("name", "")
                                if name:
                                    self.results["truecaller"] = {
                                        "found": True,
                                        "name": name,
                                        "spam_score": data.get("spamScore", 0)
                                    }
                                    return
                            except:
                                pass
                    
                    self.results["truecaller"] = {"found": False}
        except Exception as e:
            self.results["truecaller"] = {"error": str(e)}
    
    async def check_getcontact(self, phone: str):
        """فحص Getcontact"""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                headers = {
                    "User-Agent": "GetContact/5.0 Android",
                    "Content-Type": "application/json"
                }
                resp = await client.get(
                    f"https://api.getcontact.com/v2/search/{phone}",
                    headers=headers
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    tags = data.get("result", {}).get("tags", [])
                    self.results["getcontact"] = {
                        "found": True,
                        "name": data.get("result", {}).get("name", ""),
                        "tags": [t["tag"] for t in tags[:10]],
                        "tag_count": len(tags)
                    }
                else:
                    self.results["getcontact"] = {"found": False}
        except:
            self.results["getcontact"] = {"error": "API not accessible"}
    
    async def check_numverify(self, phone: str):
        """فحص NumVerify"""
        key = NUMVERIFY_KEY
        if not key:
            self.results["numverify"] = {"error": "No API key"}
            return
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "http://apilayer.net/api/validate",
                    params={
                        "access_key": key,
                        "number": phone,
                        "format": 1
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    self.results["carrier_info"] = {
                        "valid": data.get("valid"),
                        "country": data.get("country_name"),
                        "location": data.get("location"),
                        "carrier": data.get("carrier"),
                        "line_type": data.get("line_type")
                    }
        except Exception as e:
            self.results["numverify"] = {"error": str(e)}
    
    async def check_carrier_info(self, phone: str):
        """معلومات الشبكة باستخدام phonenumbers"""
        try:
            parsed = phonenumbers.parse(phone)
            self.results["phone_info"] = {
                "valid": phonenumbers.is_valid_number(parsed),
                "possible": phonenumbers.is_possible_number(parsed),
                "country": geocoder.description_for_number(parsed, "en"),
                "carrier": carrier.name_for_number(parsed, "en"),
                "timezone": list(ph_timezone.time_zones_for_number(parsed)),
                "national_format": phonenumbers.format_number(
                    parsed, phonenumbers.PhoneNumberFormat.NATIONAL
                ),
                "international_format": phonenumbers.format_number(
                    parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL
                ),
                "country_code": parsed.country_code,
                "national_number": parsed.national_number
            }
        except Exception as e:
            self.results["phone_info"] = {"error": str(e)}
    
    async def check_facebook_reset(self, phone: str):
        """فحص ارتباط فيسبوك"""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                headers = {"User-Agent": ua.random}
                resp = await client.get(
                    "https://www.facebook.com/login/identify",
                    params={"ctx": "recover"},
                    headers=headers
                )
                
                # الحصول على csrf token
                soup = BeautifulSoup(resp.text, 'lxml')
                
                # إرسال طلب استعادة برقم الهاتف
                form_data = {"phone": phone, "method": "phone"}
                resp2 = await client.post(
                    "https://www.facebook.com/ajax/login/help/identify.php",
                    data=form_data,
                    headers=headers
                )
                
                self.results["facebook"] = {
                    "possibly_linked": "account_found" in resp2.text.lower()
                }
        except:
            self.results["facebook"] = {"error": "Check failed"}
    
    async def check_google_account(self, phone: str):
        """فحص حساب جوجل"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                headers = {"User-Agent": ua.random}
                resp = await client.get(
                    "https://accounts.google.com/signin/v2/recoveryidentifier",
                    params={"flowName": "GlifWebSignIn", "flowEntry": "AccountRecovery"},
                    headers=headers
                )
                self.results["google"] = {
                    "checked": True,
                    "note": "Requires further interaction"
                }
        except:
            self.results["google"] = {"checked": False}
    
    async def check_breaches(self, phone: str):
        """فحص التسريبات (محاكاة)"""
        # يمكن ربطه بقاعدة بيانات تسريبات حقيقية
        self.results["breaches"] = {
            "checked": True,
            "note": "Connect to breach database for real results"
        }

osint_engine = OSINTEngine()

# ==================== وحدة فحص IP ====================
class IPAnalyzer:
    async def analyze(self, ip: str) -> Dict:
        results = {}
        
        tasks = [
            self.ipinfo_lookup(ip),
            self.shodan_lookup(ip),
            self.geoip_lookup(ip),
            self.abuseipdb_check(ip),
            self.port_scan(ip),
            self.reverse_dns(ip)
        ]
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        for resp in responses:
            if isinstance(resp, dict):
                results.update(resp)
        
        return results
    
    async def ipinfo_lookup(self, ip: str):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                token = IPINFO_TOKEN or ""
                url = f"https://ipinfo.io/{ip}/json"
                if token:
                    url += f"?token={token}"
                
                resp = await client.get(url)
                if resp.status_code == 200:
                    return {"ipinfo": resp.json()}
        except:
            pass
        return {}
    
    async def geoip_lookup(self, ip: str):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"http://ip-api.com/json/{ip}")
                if resp.status_code == 200:
                    return {"geoip": resp.json()}
        except:
            pass
        return {}
    
    async def shodan_lookup(self, ip: str):
        if not SHODAN_KEY:
            return {}
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"https://api.shodan.io/shodan/host/{ip}",
                    params={"key": SHODAN_KEY}
                )
                if resp.status_code == 200:
                    return {"shodan": resp.json()}
        except:
            pass
        return {}
    
    async def abuseipdb_check(self, ip: str):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                headers = {
                    "Key": os.environ.get("ABUSEIPDB_KEY", ""),
                    "Accept": "application/json"
                }
                resp = await client.get(
                    "https://api.abuseipdb.com/api/v2/check",
                    params={"ipAddress": ip, "maxAgeInDays": 90},
                    headers=headers
                )
                if resp.status_code == 200:
                    return {"abuseipdb": resp.json()}
        except:
            pass
        return {}
    
    async def port_scan(self, ip: str, ports: List[int] = None):
        if not ports:
            ports = [21, 22, 23, 25, 53, 80, 443, 8080, 8443]
        
        open_ports = []
        for port in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex((ip, port))
                if result == 0:
                    open_ports.append(port)
                sock.close()
            except:
                pass
        
        return {"port_scan": {"open_ports": open_ports, "scanned": ports}}
    
    async def reverse_dns(self, ip: str):
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            return {"reverse_dns": hostname}
        except:
            return {"reverse_dns": None}

ip_analyzer = IPAnalyzer()

# ==================== وحدة فحص URL ====================
class URLScanner:
    async def scan(self, url: str) -> Dict:
        results = {}
        
        tasks = [
            self.virustotal_scan(url),
            self.ssl_check(url),
            self.headers_check(url),
            self.whois_lookup(url),
            self.redirect_check(url)
        ]
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        for resp in responses:
            if isinstance(resp, dict):
                results.update(resp)
        
        return results
    
    async def virustotal_scan(self, url: str):
        if not VIRUSTOTAL_KEY:
            return {}
        
        try:
            # ترميز URL
            url_id = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
            
            async with httpx.AsyncClient(timeout=15) as client:
                headers = {"x-apikey": VIRUSTOTAL_KEY}
                resp = await client.get(
                    f"https://www.virustotal.com/api/v3/urls/{url_id}",
                    headers=headers
                )
                if resp.status_code == 200:
                    data = resp.json()
                    stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                    return {
                        "virustotal": {
                            "malicious": stats.get("malicious", 0),
                            "suspicious": stats.get("suspicious", 0),
                            "harmless": stats.get("harmless", 0),
                            "undetected": stats.get("undetected", 0)
                        }
                    }
        except:
            pass
        return {}
    
    async def ssl_check(self, url: str):
        try:
            hostname = url.split("://")[-1].split("/")[0]
            
            ctx = ssl.create_default_context()
            with socket.create_connection((hostname, 443), timeout=5) as sock:
                with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    
                    return {
                        "ssl": {
                            "issuer": dict(x[0] for x in cert.get("issuer", [])),
                            "subject": dict(x[0] for x in cert.get("subject", [])),
                            "valid_from": cert.get("notBefore"),
                            "valid_to": cert.get("notAfter"),
                            "san": cert.get("subjectAltName", [])
                        }
                    }
        except Exception as e:
            return {"ssl": {"error": str(e)}}
    
    async def headers_check(self, url: str):
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(url)
                
                security_headers = {
                    "Strict-Transport-Security": resp.headers.get("Strict-Transport-Security"),
                    "Content-Security-Policy": resp.headers.get("Content-Security-Policy"),
                    "X-Frame-Options": resp.headers.get("X-Frame-Options"),
                    "X-Content-Type-Options": resp.headers.get("X-Content-Type-Options"),
                    "X-XSS-Protection": resp.headers.get("X-XSS-Protection"),
                }
                
                missing = [h for h, v in security_headers.items() if v is None]
                
                return {
                    "headers": {
                        "security_headers": security_headers,
                        "missing_headers": missing,
                        "server": resp.headers.get("Server", "Unknown"),
                        "status_code": resp.status_code
                    }
                }
        except:
            return {}
    
    async def whois_lookup(self, url: str):
        try:
            hostname = url.split("://")[-1].split("/")[0]
            # محاكاة WHOIS (يحتاج مكتبة python-whois أو API خارجي)
            return {"whois": {"domain": hostname, "note": "Requires whois library"}}
        except:
            return {}
    
    async def redirect_check(self, url: str):
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
                response = await client.get(url)
                
                if response.status_code in (301, 302, 307, 308):
                    return {
                        "redirect": {
                            "status": response.status_code,
                            "location": response.headers.get("Location", ""),
                            "chain": [str(response.url)]
                        }
                    }
                return {"redirect": None}
        except:
            return {}

url_scanner = URLScanner()

# ==================== بوت تيليجرام ====================
class MegaBot:
    def __init__(self):
        self.app = None
    
    async def setup(self):
        """إعداد البوت"""
        self.app = Application.builder().token(BOT_TOKEN).build()
        
        # الأوامر الأساسية
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("login", self.cmd_login))
        self.app.add_handler(CommandHandler("logout", self.cmd_logout))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("cancel", self.cmd_cancel))
        
        # أوامر الفحص
        self.app.add_handler(CommandHandler("scan", self.cmd_scan))
        self.app.add_handler(CommandHandler("lookup", self.cmd_lookup))
        self.app.add_handler(CommandHandler("ip", self.cmd_ip))
        self.app.add_handler(CommandHandler("url", self.cmd_url))
        self.app.add_handler(CommandHandler("email", self.cmd_email))
        
        # أوامر متقدمة
        self.app.add_handler(CommandHandler("setapi", self.cmd_setapi))
        self.app.add_handler(CommandHandler("credits", self.cmd_credits))
        self.app.add_handler(CommandHandler("history", self.cmd_history))
        
        # معالجات
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        
        logger.info("Bot handlers registered")
    
    # ==================== أوامر البوت ====================
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("🔍 فحص رقم", callback_data="menu_scan"),
             InlineKeyboardButton("🌐 فحص IP", callback_data="menu_ip")],
            [InlineKeyboardButton("🔗 فحص رابط", callback_data="menu_url"),
             InlineKeyboardButton("📧 فحص إيميل", callback_data="menu_email")],
            [InlineKeyboardButton("📊 حسابي", callback_data="menu_status"),
             InlineKeyboardButton("ℹ️ مساعدة", callback_data="menu_help")]
        ]
        
        await update.message.reply_text(
            "╔══════════════════════╗\n"
            "║   🔥 بوت OSINT المتكامل   ║\n"
            "╚══════════════════════╝\n\n"
            "أداة استخباراتية متكاملة لجمع المعلومات من المصادر المفتوحة.\n\n"
            "📋 **الأوامر الأساسية:**\n"
            "/login - تسجيل الدخول\n"
            "/scan - فحص شامل\n"
            "/lookup - فحص رقم\n"
            "/ip - فحص IP\n"
            "/url - فحص رابط\n"
            "/email - فحص بريد\n\n"
            "⚠️ للأغراض التعليمية والبحثية فقط.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """
📚 **دليل الاستخدام الكامل**

**1. تسجيل الدخول:**
/login - بدء تسجيل الدخول
تحتاج API_ID و API_HASH من my.telegram.org

**2. فحص الأرقام:**
/lookup +201234567890
/scan phone +201234567890

**3. فحص IP:**
/ip 8.8.8.8
/scan ip 8.8.8.8

**4. فحص الروابط:**
/url https://example.com
/scan url https://example.com

**5. فحص البريد:**
/email user@example.com

**6. المفاتيح API:**
/setapi numverify KEY
/setapi virustotal KEY
/setapi shodan KEY

**7. أخرى:**
/status - حالة حسابك
/credits - رصيدك
/history - سجل الفحوصات
/logout - تسجيل خروج
/cancel - إلغاء العملية
"""
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def cmd_login(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        
        existing = await session_manager.get_session(uid)
        if existing:
            await update.message.reply_text("✅ لديك حساب مسجل بالفعل!")
            return
        
        session_manager.login_states[uid] = {"step": "api_id"}
        
        await update.message.reply_text(
            "📱 **تسجيل الدخول - الخطوة 1/4**\n\n"
            "أرسل API_ID الخاص بك.\n"
            "للحصول عليه: https://my.telegram.org\n"
            "اذهب إلى: API Development Tools"
        )
    
    async def cmd_logout(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        
        if uid in session_manager.user_clients:
            try:
                await session_manager.user_clients[uid].disconnect()
            except:
                pass
            del session_manager.user_clients[uid]
        
        await session_manager.delete_session(uid)
        await update.message.reply_text("✅ تم تسجيل الخروج بنجاح")
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        
        session = await session_manager.get_session(uid)
        
        if not session:
            await update.message.reply_text("🔴 غير مسجل\nاستخدم /login")
            return
        
        client = await session_manager.get_client(uid)
        
        status_text = "🟢 **حالة الحساب**\n\n"
        status_text += f"📱 الرقم: {session.get('phone', 'غير معروف')}\n"
        status_text += f"💰 الرصيد: {session.get('credits', 0)} فحص\n"
        
        if client:
            me = await client.get_me()
            status_text += f"👤 الاسم: {me.first_name}\n"
            status_text += f"🆔 ID: {me.id}\n"
            status_text += f"⚡ الجلسة: نشطة\n"
        else:
            status_text += "⚡ الجلسة: غير نشطة\n"
        
        await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)
    
    async def cmd_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        
        if uid in session_manager.login_states:
            del session_manager.login_states[uid]
            await update.message.reply_text("✅ تم إلغاء العملية")
        else:
            await update.message.reply_text("لا توجد عملية جارية")
    
    async def cmd_scan(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        
        if not context.args:
            await update.message.reply_text(
                "📋 **استخدام:**\n"
                "/scan phone <رقم>\n"
                "/scan ip <عنوان>\n"
                "/scan url <رابط>\n"
                "/scan email <بريد>"
            )
            return
        
        scan_type = context.args[0].lower()
        target = context.args[1] if len(context.args) > 1 else None
        
        if not target:
            await update.message.reply_text("❌ حدد الهدف")
            return
        
        msg = await update.message.reply_text(f"🔍 جاري الفحص الشامل...")
        
        try:
            results = await osint_engine.full_scan(target, scan_type)
            report = self.format_scan_report(results)
            await msg.edit_text(report, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await msg.edit_text(f"❌ خطأ: {e}")
    
    async def cmd_lookup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        
        if not context.args:
            await update.message.reply_text("📱 **استخدام:** /lookup +201234567890")
            return
        
        phone = context.args[0]
        
        if not phone.startswith("+"):
            await update.message.reply_text("❌ يجب أن يبدأ الرقم بـ +")
            return
        
        msg = await update.message.reply_text(f"🔍 جاري فحص {phone}...")
        
        try:
            client = await session_manager.get_client(uid)
            results = await osint_engine.phone_scan(phone)
            
            if client:
                await osint_engine.check_telegram(phone, client)
            
            report = self.format_phone_report(osint_engine.results)
            await msg.edit_text(report, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            await msg.edit_text(f"❌ خطأ: {e}")
    
    async def cmd_ip(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("🌐 **استخدام:** /ip 8.8.8.8")
            return
        
        ip = context.args[0]
        msg = await update.message.reply_text(f"🔍 فحص {ip}...")
        
        try:
            results = await ip_analyzer.analyze(ip)
            report = self.format_ip_report(results)
            await msg.edit_text(report, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await msg.edit_text(f"❌ خطأ: {e}")
    
    async def cmd_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("🔗 **استخدام:** /url https://example.com")
            return
        
        url = context.args[0]
        msg = await update.message.reply_text(f"🔍 فحص {url}...")
        
        try:
            results = await url_scanner.scan(url)
            report = self.format_url_report(results)
            await msg.edit_text(report, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await msg.edit_text(f"❌ خطأ: {e}")
    
    async def cmd_email(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("📧 **استخدام:** /email user@example.com")
            return
        
        email = context.args[0]
        msg = await update.message.reply_text(f"🔍 فحص {email}...")
        
        # فحص أساسي للبريد
        report = f"""
📧 **تقرير البريد:** `{email}`

📋 **تحليل أساسي:**
├ الخدمة: {email.split('@')[1]}
├ الاسم: {email.split('@')[0]}
├ الطول: {len(email)} حرف

🔒 **فحص الأمان:**
├ Have I Been Pwned: يتطلب API
└ مؤقت: {'⚠️ نعم' if email.split('@')[1] in ['tempmail.com', '10minutemail.com'] else '✅ لا'}
"""
        await msg.edit_text(report, parse_mode=ParseMode.MARKDOWN)
    
    async def cmd_setapi(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "🔑 **استخدام:**\n"
                "/setapi numverify KEY\n"
                "/setapi virustotal KEY\n"
                "/setapi shodan KEY\n"
                "/setapi abuseipdb KEY"
            )
            return
        
        service = context.args[0].lower()
        key = context.args[1]
        
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO api_keys VALUES (?, ?, ?)",
                (uid, service, key)
            )
            await db.commit()
        
        await update.message.reply_text(f"✅ تم حفظ مفتاح {service}")
    
    async def cmd_credits(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        session = await session_manager.get_session(uid)
        
        if session:
            await update.message.reply_text(f"💰 رصيدك: {session.get('credits', 0)} فحص")
        else:
            await update.message.reply_text("🔴 غير مسجل")
    
    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT target, scan_type, created_at FROM scan_history WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
                (uid,)
            ) as cursor:
                rows = await cursor.fetchall()
        
        if not rows:
            await update.message.reply_text("📭 لا يوجد سجل")
            return
        
        history = "📊 **آخر 10 فحوصات:**\n\n"
        for target, scan_type, date in rows:
            history += f"🎯 {target} ({scan_type}) - {date}\n"
        
        await update.message.reply_text(history, parse_mode=ParseMode.MARKDOWN)
    
    # ==================== معالجات ====================
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        text = update.message.text.strip()
        
        if uid in session_manager.login_states:
            await self.process_login_step(update, text)
    
    async def process_login_step(self, update: Update, text: str):
        uid = update.effective_user.id
        state = session_manager.login_states[uid]
        step = state["step"]
        
        try:
            if step == "api_id":
                api_id = int(text)
                state["api_id"] = api_id
                state["step"] = "api_hash"
                await update.message.reply_text("✅ الخطوة 2/4: أرسل API_HASH")
            
            elif step == "api_hash":
                state["api_hash"] = text
                state["step"] = "phone"
                await update.message.reply_text("✅ الخطوة 3/4: أرسل رقم الهاتف (+2012...)")
            
            elif step == "phone":
                if not text.startswith("+"):
                    await update.message.reply_text("❌ يجب أن يبدأ بـ +")
                    return
                
                state["phone"] = text
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
                    await update.message.reply_text("✅ الخطوة 4/4: أرسل رمز التحقق")
                except Exception as e:
                    await client.disconnect()
                    del session_manager.login_states[uid]
                    await update.message.reply_text(f"❌ خطأ في إرسال الكود: {e}")
            
            elif step == "code":
                client = state["client"]
                try:
                    await client.sign_in(
                        phone=state["phone"],
                        code=text,
                        phone_code_hash=state["phone_code_hash"]
                    )
                    await self.complete_login(update, state)
                except SessionPasswordNeededError:
                    state["step"] = "password"
                    await update.message.reply_text("🔒 حسابك محمي. أرسل كلمة المرور:")
                except Exception as e:
                    await client.disconnect()
                    del session_manager.login_states[uid]
                    await update.message.reply_text(f"❌ خطأ: {e}")
            
            elif step == "password":
                client = state["client"]
                try:
                    await client.sign_in(password=text)
                    await self.complete_login(update, state)
                except Exception as e:
                    await client.disconnect()
                    del session_manager.login_states[uid]
                    await update.message.reply_text(f"❌ كلمة مرور خطأ: {e}")
        
        except ValueError:
            await update.message.reply_text("❌ قيمة غير صالحة")
    
    async def complete_login(self, update: Update, state: Dict):
        uid = update.effective_user.id
        client = state["client"]
        
        try:
            me = await client.get_me()
            session_string = client.session.save()
            
            await session_manager.save_session(
                uid, session_string,
                state["phone"],
                str(state["api_id"]),
                state["api_hash"]
            )
            
            await update.message.reply_text(
                f"✅ **تم تسجيل الدخول!**\n\n"
                f"👤 {me.first_name}\n"
                f"📱 {me.phone}\n"
                f"🆔 {me.id}\n\n"
                f"يمكنك الآن استخدام أوامر الفحص."
            )
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ: {e}")
        finally:
            await client.disconnect()
            del session_manager.login_states[uid]
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "menu_scan":
            await query.edit_message_text(
                "🔍 **فحص رقم:**\n/lookup +201234567890\n\n"
                "🌐 **فحص IP:**\n/ip 8.8.8.8\n\n"
                "🔗 **فحص رابط:**\n/url https://example.com"
            )
        elif data == "menu_ip":
            await query.edit_message_text("استخدم: /ip <عنوان>\nمثال: /ip 8.8.8.8")
        elif data == "menu_url":
            await query.edit_message_text("استخدم: /url <رابط>\nمثال: /url https://google.com")
        elif data == "menu_email":
            await query.edit_message_text("استخدم: /email <بريد>\nمثال: /email user@gmail.com")
        elif data == "menu_status":
            await self.cmd_status(update, context)
        elif data == "menu_help":
            await self.cmd_help(update, context)
    
    # ==================== تنسيق التقارير ====================
    def format_scan_report(self, results: Dict) -> str:
        report = "📊 **تقرير الفحص الشامل**\n"
        report += "═" * 25 + "\n\n"
        report += f"🎯 الهدف: {results.get('target', '')}\n"
        report += f"📋 النوع: {results.get('type', '')}\n"
        report += f"🕐 الوقت: {results.get('timestamp', '')}\n\n"
        report += json.dumps(results, indent=2, ensure_ascii=False)[:3500]
        return report
    
    def format_phone_report(self, results: Dict) -> str:
        report = "📱 **تقرير فحص الرقم**\n"
        report += "═" * 25 + "\n\n"
        
        # تيليجرام
        tg = results.get("telegram", {})
        if tg.get("exists"):
            report += "📡 **تيليجرام:** ✅ موجود\n"
            report += f"├ الاسم: {tg.get('first_name', '')} {tg.get('last_name', '')}\n"
            report += f"├ يوزر: @{tg.get('username', 'لا يوجد')}\n"
            report += f"├ ID: {tg.get('user_id', '')}\n"
            report += f"└ مميز: {'⭐ نعم' if tg.get('is_premium') else 'لا'}\n\n"
        else:
            report += "📡 **تيليجرام:** ❌ غير مسجل\n\n"
        
        # واتساب
        wa = results.get("whatsapp", {})
        wa_exists = wa.get("exists") if isinstance(wa.get("exists"), bool) else None
        if wa_exists is True:
            report += "💬 **واتساب:** ✅ موجود\n\n"
        elif wa_exists is False:
            report += "💬 **واتساب:** ❌ غير مسجل\n\n"
        
        # Truecaller
        tc = results.get("truecaller", {})
        if tc.get("found"):
            report += f"👤 **Truecaller:** {tc.get('name', '')}\n\n"
        
        # الشبكة
        carrier = results.get("carrier_info", {})
        if carrier:
            report += f"📶 **الشبكة:** {carrier.get('carrier', 'غير معروف')}\n"
            report += f"🌍 **الدولة:** {carrier.get('country', '')}\n"
            report += f"📋 **النوع:** {carrier.get('line_type', '')}\n\n"
        
        report += "═" * 25
        return report
    
    def format_ip_report(self, results: Dict) -> str:
        report = "🌐 **تقرير فحص IP**\n"
        report += "═" * 25 + "\n\n"
        
        # IPInfo
        ipinfo = results.get("ipinfo", {})
        if ipinfo:
            report += f"📍 **الموقع:** {ipinfo.get('city', '')}, {ipinfo.get('region', '')}, {ipinfo.get('country', '')}\n"
            report += f"🏢 **المزود:** {ipinfo.get('org', 'غير معروف')}\n"
            report += f"📮 **الرمز البريدي:** {ipinfo.get('postal', '')}\n\n"
        
        # AbuseIPDB
        abuse = results.get("abuseipdb", {}).get("data", {})
        if abuse:
            report += f"⚠️ **السمعة:** {abuse.get('abuseConfidenceScore', 0)}% ضار\n"
            report += f"📊 **عدد البلاغات:** {abuse.get('totalReports', 0)}\n\n"
        
        # Ports
        ports = results.get("port_scan", {})
        if ports.get("open_ports"):
            report += f"🔓 **المنافذ المفتوحة:** {', '.join(map(str, ports['open_ports']))}\n\n"
        
        # DNS
        dns = results.get("reverse_dns", "")
        if dns:
            report += f"🔍 **Reverse DNS:** {dns}\n\n"
        
        report += "═" * 25
        return report
    
    def format_url_report(self, results: Dict) -> str:
        report = "🔗 **تقرير فحص الرابط**\n"
        report += "═" * 25 + "\n\n"
        
        # VirusTotal
        vt = results.get("virustotal", {})
        if vt:
            report += "🛡️ **VirusTotal:**\n"
            report += f"├ ضار: {vt.get('malicious', 0)}\n"
            report += f"├ مشبوه: {vt.get('suspicious', 0)}\n"
            report += f"└ آمن: {vt.get('harmless', 0)}\n\n"
        
        # SSL
        ssl_info = results.get("ssl", {})
        if ssl_info.get("valid_to"):
            report += "🔒 **SSL:**\n"
            report += f"├ صالح حتى: {ssl_info['valid_to']}\n"
            report += f"└ المصدر: {ssl_info.get('issuer', {}).get('commonName', '')}\n\n"
        
        # Headers
        headers = results.get("headers", {})
        if headers:
            missing = headers.get("missing_headers", [])
            if missing:
                report += f"⚠️ **رؤوس أمان مفقودة:** {', '.join(missing)}\n\n"
            else:
                report += "✅ جميع رؤوس الأمان موجودة\n\n"
        
        report += "═" * 25
        return report

# ==================== Flask للتشغيل الدائم ====================
@web_app.route('/')
def home():
    return "MEGA OSINT Bot is Running!"

@web_app.route('/health')
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

@web_app.route('/api/stats')
def stats():
    return jsonify({
        "users": len(session_manager.active_sessions),
        "uptime": "running",
        "version": "3.0.0"
    })

def run_flask():
    web_app.run(host='0.0.0.0', port=PORT, debug=False)

# ==================== الدالة الرئيسية ====================
async def main():
    # تهيئة قاعدة البيانات
    await init_database()
    
    # إعداد البوت
    bot = MegaBot()
    await bot.setup()
    
    # تشغيل Flask في خيط منفصل
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("""
╔══════════════════════════════════════════════════════════╗
║              🔥 MEGA OSINT BOT v3.0 🔥                  ║
║         المستخدم يتحمل المسؤولية القانونية كاملة          ║
╚══════════════════════════════════════════════════════════╝
    """)
    print(f"🌐 Web Server: 0.0.0.0:{PORT}")
    print(f"🤖 Bot Token: {BOT_TOKEN[:10]}...")
    print(f"📱 NumVerify API: {'✅' if NUMVERIFY_KEY else '❌'}")
    print(f"🛡️ VirusTotal API: {'✅' if VIRUSTOTAL_KEY else '❌'}")
    print(f"🔍 Shodan API: {'✅' if SHODAN_KEY else '❌'}")
    print("═" * 50)
    print("⚡ البوت شغال...")
    
    await bot.app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    asyncio.run(main())
