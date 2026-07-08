#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║              🔥 SHADOW OSINT - موقع ويب متكامل 🔥               ║
║           المستخدم يتحمل المسؤولية القانونية كاملة                ║
╚══════════════════════════════════════════════════════════════════╝

📦 التثبيت:
pip install flask>=3.0.0 httpx~=0.25.2 beautifulsoup4>=4.12.0 lxml>=5.1.0 aiosqlite>=0.20.0 fake-useragent>=1.5.0 phonenumbers>=8.13.0 gunicorn>=21.2.0

🚀 التشغيل:
python bot.py
"""

import os
import re
import json
import time
import socket
import ssl
import hashlib
import secrets
import asyncio
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, quote
from functools import wraps

import httpx
import aiosqlite
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import phonenumbers
from phonenumbers import carrier, geocoder, timezone as ph_timezone
from flask import (
    Flask, render_template_string, request, jsonify,
    session, redirect, url_for, make_response
)

# ==================== التهيئة ====================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SHADOW_OSINT")

web_app = Flask(__name__)
web_app.secret_key = secrets.token_hex(32)

PORT = int(os.environ.get("PORT", 8080))
NUMVERIFY_KEY = os.environ.get("NUMVERIFY_KEY", "")
ABSTRACT_API_KEY = os.environ.get("ABSTRACT_API_KEY", "")
VIRUSTOTAL_KEY = os.environ.get("VIRUSTOTAL_KEY", "")
SHODAN_KEY = os.environ.get("SHODAN_KEY", "")
IPINFO_TOKEN = os.environ.get("IPINFO_TOKEN", "")
DB_PATH = "shadow_osint.db"

ua = UserAgent()

# ==================== قاعدة البيانات ====================
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target TEXT,
                scan_type TEXT,
                result TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS api_keys (
                service TEXT PRIMARY KEY,
                api_key TEXT
            );
        """)
        await db.commit()

def run_async(coro):
    """تشغيل async في sync"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

# ==================== محرك الفحص ====================
class OSINTScanner:
    def __init__(self):
        self.ua = UserAgent()
    
    async def scan_phone(self, phone: str) -> Dict:
        """فحص رقم الهاتف من جميع المصادر"""
        results = {
            "phone": phone,
            "timestamp": datetime.now().isoformat(),
            "telegram": {},
            "whatsapp": {},
            "viber": {},
            "signal": {},
            "truecaller": {},
            "carrier": {},
            "facebook": {},
            "google": {},
            "numverify": {}
        }
        
        # تشغيل كل الفحوصات بالتوازي
        tasks = [
            self._check_whatsapp(phone),
            self._check_viber(phone),
            self._check_signal(phone),
            self._check_truecaller(phone),
            self._check_carrier(phone),
            self._check_facebook(phone),
            self._check_numverify(phone),
        ]
        
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        for r in results_list:
            if isinstance(r, dict):
                results.update(r)
        
        return results
    
    async def _check_whatsapp(self, phone: str) -> Dict:
        clean = phone.replace("+", "").replace(" ", "").replace("-", "")
        methods = {}
        
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                headers = {"User-Agent": self.ua.random}
                resp = await client.get(f"https://wa.me/{clean}", headers=headers)
                methods["wa_me"] = "Continue to Chat" in resp.text
        except:
            methods["wa_me"] = None
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                headers = {"User-Agent": "WhatsApp/2.24.2.17 Android"}
                resp = await client.post(
                    "https://v.whatsapp.com/v2/exist",
                    json={"cc": phone[:3] if phone.startswith("+") else "", 
                          "in": phone[3:] if phone.startswith("+") else phone,
                          "to": phone},
                    headers=headers
                )
                methods["api"] = resp.status_code == 200
        except:
            methods["api"] = None
        
        exists = methods.get("wa_me") or methods.get("api")
        return {"whatsapp": {"exists": exists, "methods": methods}}
    
    async def _check_viber(self, phone: str) -> Dict:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "https://api.viber.com/api/v2/check",
                    json={"phone": phone},
                    headers={"User-Agent": self.ua.random}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {"viber": {"exists": data.get("exists", False)}}
        except:
            pass
        return {"viber": {"exists": None}}
    
    async def _check_signal(self, phone: str) -> Dict:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                headers = {"User-Agent": "Signal-Android/6.0"}
                resp = await client.get(
                    f"https://api.signal.org/v1/accounts/{phone}",
                    headers=headers
                )
                return {"signal": {"exists": resp.status_code == 200}}
        except:
            return {"signal": {"exists": None}}
    
    async def _check_truecaller(self, phone: str) -> Dict:
        clean = phone.replace("+", "")
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                headers = {
                    "User-Agent": self.ua.random,
                    "Accept-Language": "ar,en;q=0.9"
                }
                resp = await client.get(
                    f"https://www.truecaller.com/search/eg/{clean}",
                    headers=headers
                )
                
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'lxml')
                    scripts = soup.find_all("script", type="application/ld+json")
                    
                    for script in scripts:
                        if script.string:
                            try:
                                data = json.loads(script.string)
                                name = data.get("name", "")
                                if name:
                                    return {"truecaller": {"found": True, "name": name}}
                            except:
                                pass
                    
                    return {"truecaller": {"found": False}}
        except:
            return {"truecaller": {"error": "تعذر الفحص"}}
    
    async def _check_carrier(self, phone: str) -> Dict:
        try:
            parsed = phonenumbers.parse(phone)
            return {"carrier": {
                "valid": phonenumbers.is_valid_number(parsed),
                "country": geocoder.description_for_number(parsed, "en"),
                "carrier": carrier.name_for_number(parsed, "en"),
                "timezone": list(ph_timezone.time_zones_for_number(parsed)),
                "national": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL),
                "international": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
            }}
        except Exception as e:
            return {"carrier": {"error": str(e)}}
    
    async def _check_facebook(self, phone: str) -> Dict:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                headers = {"User-Agent": self.ua.random}
                resp = await client.get(
                    "https://www.facebook.com/login/identify",
                    params={"ctx": "recover"},
                    headers=headers
                )
                return {"facebook": {"possibly_linked": resp.status_code == 200}}
        except:
            return {"facebook": {"possibly_linked": None}}
    
    async def _check_numverify(self, phone: str) -> Dict:
        if not NUMVERIFY_KEY:
            return {"numverify": {"error": "No API key"}}
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "http://apilayer.net/api/validate",
                    params={"access_key": NUMVERIFY_KEY, "number": phone, "format": 1}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {"numverify": {
                        "valid": data.get("valid"),
                        "country": data.get("country_name"),
                        "carrier": data.get("carrier"),
                        "line_type": data.get("line_type"),
                        "location": data.get("location")
                    }}
        except:
            pass
        return {"numverify": {"error": "فشل"}}
    
    async def scan_ip(self, ip: str) -> Dict:
        """فحص IP"""
        results = {"ip": ip, "timestamp": datetime.now().isoformat()}
        
        tasks = [
            self._ipinfo(ip),
            self._geoip(ip),
            self._abuseipdb(ip),
            self._shodan(ip),
            self._port_scan(ip),
            self._reverse_dns(ip)
        ]
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        for r in responses:
            if isinstance(r, dict):
                results.update(r)
        
        return results
    
    async def _ipinfo(self, ip: str) -> Dict:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                url = f"https://ipinfo.io/{ip}/json"
                if IPINFO_TOKEN:
                    url += f"?token={IPINFO_TOKEN}"
                resp = await client.get(url)
                if resp.status_code == 200:
                    return {"ipinfo": resp.json()}
        except:
            pass
        return {}
    
    async def _geoip(self, ip: str) -> Dict:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"http://ip-api.com/json/{ip}")
                if resp.status_code == 200:
                    return {"geoip": resp.json()}
        except:
            pass
        return {}
    
    async def _abuseipdb(self, ip: str) -> Dict:
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
    
    async def _shodan(self, ip: str) -> Dict:
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
    
    async def _port_scan(self, ip: str) -> Dict:
        ports = [21, 22, 23, 25, 53, 80, 110, 143, 443, 993, 995, 8080, 8443]
        open_ports = []
        
        for port in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((ip, port))
                if result == 0:
                    open_ports.append(port)
                sock.close()
            except:
                pass
        
        return {"ports": {"open": open_ports, "scanned": ports}}
    
    async def _reverse_dns(self, ip: str) -> Dict:
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            return {"reverse_dns": hostname}
        except:
            return {"reverse_dns": None}
    
    async def scan_url(self, url: str) -> Dict:
        """فحص رابط"""
        results = {"url": url, "timestamp": datetime.now().isoformat()}
        
        tasks = [
            self._ssl_check(url),
            self._headers_check(url),
            self._virustotal(url),
            self._redirect_check(url)
        ]
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        for r in responses:
            if isinstance(r, dict):
                results.update(r)
        
        return results
    
    async def _ssl_check(self, url: str) -> Dict:
        try:
            hostname = urlparse(url).hostname or url
            ctx = ssl.create_default_context()
            with socket.create_connection((hostname, 443), timeout=5) as sock:
                with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    return {"ssl": {
                        "issuer": dict(x[0] for x in cert.get("issuer", [])),
                        "valid_from": cert.get("notBefore"),
                        "valid_to": cert.get("notAfter"),
                        "subject": dict(x[0] for x in cert.get("subject", []))
                    }}
        except Exception as e:
            return {"ssl": {"error": str(e)}}
    
    async def _headers_check(self, url: str) -> Dict:
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(url)
                
                security = {
                    "Strict-Transport-Security": resp.headers.get("Strict-Transport-Security"),
                    "Content-Security-Policy": resp.headers.get("Content-Security-Policy"),
                    "X-Frame-Options": resp.headers.get("X-Frame-Options"),
                    "X-Content-Type-Options": resp.headers.get("X-Content-Type-Options"),
                    "X-XSS-Protection": resp.headers.get("X-XSS-Protection")
                }
                
                missing = [k for k, v in security.items() if not v]
                
                return {"headers": {
                    "security": security,
                    "missing": missing,
                    "server": resp.headers.get("Server", "Unknown"),
                    "status": resp.status_code
                }}
        except:
            return {}
    
    async def _virustotal(self, url: str) -> Dict:
        if not VIRUSTOTAL_KEY:
            return {}
        try:
            url_id = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
            async with httpx.AsyncClient(timeout=15) as client:
                headers = {"x-apikey": VIRUSTOTAL_KEY}
                resp = await client.get(
                    f"https://www.virustotal.com/api/v3/urls/{url_id}",
                    headers=headers
                )
                if resp.status_code == 200:
                    stats = resp.json().get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                    return {"virustotal": stats}
        except:
            pass
        return {}
    
    async def _redirect_check(self, url: str) -> Dict:
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
                response = await client.get(url)
                if response.status_code in (301, 302, 307, 308):
                    return {"redirect": {
                        "status": response.status_code,
                        "location": response.headers.get("Location", "")
                    }}
                return {"redirect": None}
        except:
            return {}

scanner = OSINTScanner()

# ==================== HTML Templates ====================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SHADOW OSINT - أداة الاستخبارات المفتوحة</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, sans-serif;
            background: #0a0a0a;
            color: #e0e0e0;
            min-height: 100vh;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        
        /* Header */
        .header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            padding: 20px;
            text-align: center;
            border-bottom: 2px solid #e94560;
        }
        .header h1 {
            font-size: 2.5em;
            color: #e94560;
            text-shadow: 0 0 10px rgba(233,69,96,0.5);
        }
        .header p { color: #888; margin-top: 10px; }
        
        /* Navigation */
        .nav {
            display: flex;
            justify-content: center;
            gap: 10px;
            padding: 15px;
            flex-wrap: wrap;
        }
        .nav a {
            padding: 10px 25px;
            background: #1a1a2e;
            color: #e0e0e0;
            text-decoration: none;
            border-radius: 5px;
            border: 1px solid #333;
            transition: all 0.3s;
        }
        .nav a:hover, .nav a.active {
            background: #e94560;
            border-color: #e94560;
            color: white;
        }
        
        /* Cards */
        .card {
            background: #1a1a2e;
            border: 1px solid #333;
            border-radius: 10px;
            padding: 25px;
            margin: 20px 0;
        }
        .card h2 {
            color: #e94560;
            margin-bottom: 20px;
            font-size: 1.5em;
        }
        
        /* Inputs */
        .input-group {
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
        }
        input, textarea, select {
            flex: 1;
            padding: 12px 15px;
            background: #0a0a0a;
            border: 1px solid #333;
            border-radius: 5px;
            color: #e0e0e0;
            font-size: 16px;
        }
        input:focus, textarea:focus, select:focus {
            outline: none;
            border-color: #e94560;
            box-shadow: 0 0 5px rgba(233,69,96,0.3);
        }
        
        /* Buttons */
        .btn {
            padding: 12px 30px;
            background: #e94560;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            transition: all 0.3s;
        }
        .btn:hover { background: #c73e54; transform: translateY(-2px); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-sm { padding: 8px 15px; font-size: 14px; }
        
        /* Results */
        .result-box {
            background: #0a0a0a;
            border: 1px solid #333;
            border-radius: 5px;
            padding: 20px;
            margin-top: 20px;
            white-space: pre-wrap;
            font-family: monospace;
            font-size: 14px;
            max-height: 500px;
            overflow-y: auto;
            display: none;
        }
        .result-box.show { display: block; }
        .result-box.success { border-color: #4caf50; }
        .result-box.error { border-color: #e94560; }
        
        /* Loading */
        .loading {
            text-align: center;
            padding: 20px;
            display: none;
        }
        .loading.show { display: block; }
        .spinner {
            border: 3px solid #333;
            border-top: 3px solid #e94560;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        /* Table */
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
        }
        th, td {
            padding: 10px;
            border: 1px solid #333;
            text-align: right;
        }
        th {
            background: #1a1a2e;
            color: #e94560;
        }
        td { background: #0a0a0a; }
        
        /* Status */
        .status-badge {
            display: inline-block;
            padding: 5px 10px;
            border-radius: 3px;
            font-weight: bold;
        }
        .status-true { background: #4caf50; color: white; }
        .status-false { background: #e94560; color: white; }
        .status-unknown { background: #ff9800; color: white; }
        
        /* Footer */
        .footer {
            text-align: center;
            padding: 20px;
            color: #666;
            border-top: 1px solid #333;
            margin-top: 40px;
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .header h1 { font-size: 1.8em; }
            .input-group { flex-direction: column; }
            .nav { flex-direction: column; align-items: center; }
            .nav a { width: 100%; text-align: center; }
        }
        
        /* Tabs */
        .tabs {
            display: flex;
            gap: 5px;
            margin-bottom: 20px;
        }
        .tab {
            padding: 10px 20px;
            background: #0a0a0a;
            border: 1px solid #333;
            cursor: pointer;
            border-radius: 5px 5px 0 0;
        }
        .tab.active {
            background: #e94560;
            border-color: #e94560;
            color: white;
        }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        /* Stats */
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        .stat-card {
            background: #1a1a2e;
            border: 1px solid #333;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
        }
        .stat-card h3 { color: #888; font-size: 0.9em; }
        .stat-card .value { color: #e94560; font-size: 2em; font-weight: bold; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔥 SHADOW OSINT</h1>
        <p>أداة الاستخبارات المفتوحة - فحص أرقام، IP، روابط، والمزيد</p>
    </div>
    
    <div class="container">
        <div class="nav">
            <a href="/" class="{{ 'active' if active_page == 'phone' else '' }}">📱 فحص رقم</a>
            <a href="/ip" class="{{ 'active' if active_page == 'ip' else '' }}">🌐 فحص IP</a>
            <a href="/url" class="{{ 'active' if active_page == 'url' else '' }}">🔗 فحص رابط</a>
            <a href="/api" class="{{ 'active' if active_page == 'api' else '' }}">⚡ API</a>
        </div>
        
        {% block content %}{% endblock %}
    </div>
    
    <div class="footer">
        <p>⚠️ للأغراض التعليمية والبحثية فقط. المستخدم يتحمل المسؤولية الكاملة عن استخدامه.</p>
        <p>SHADOW OSINT v4.0 | © 2024</p>
    </div>
    
    <script>
        async function scanPhone() {
            const phone = document.getElementById('phone').value;
            if (!phone) return alert('الرجاء إدخال رقم الهاتف');
            
            showLoading('phoneLoading', true);
            hideResult('phoneResult');
            
            try {
                const resp = await fetch('/api/scan/phone', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({phone: phone})
                });
                
                const data = await resp.json();
                showResult('phoneResult', formatPhoneResult(data), resp.ok);
            } catch(e) {
                showResult('phoneResult', 'خطأ: ' + e.message, false);
            } finally {
                showLoading('phoneLoading', false);
            }
        }
        
        async function scanIP() {
            const ip = document.getElementById('ip').value;
            if (!ip) return alert('الرجاء إدخال عنوان IP');
            
            showLoading('ipLoading', true);
            hideResult('ipResult');
            
            try {
                const resp = await fetch('/api/scan/ip', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ip: ip})
                });
                
                const data = await resp.json();
                showResult('ipResult', JSON.stringify(data, null, 2), resp.ok);
            } catch(e) {
                showResult('ipResult', 'خطأ: ' + e.message, false);
            } finally {
                showLoading('ipLoading', false);
            }
        }
        
        async function scanURL() {
            const url = document.getElementById('url').value;
            if (!url) return alert('الرجاء إدخال رابط');
            
            showLoading('urlLoading', true);
            hideResult('urlResult');
            
            try {
                const resp = await fetch('/api/scan/url', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url: url})
                });
                
                const data = await resp.json();
                showResult('urlResult', JSON.stringify(data, null, 2), resp.ok);
            } catch(e) {
                showResult('urlResult', 'خطأ: ' + e.message, false);
            } finally {
                showLoading('urlLoading', false);
            }
        }
        
        function formatPhoneResult(data) {
            let html = '<h3 style="color:#e94560">📱 نتيجة فحص: ' + data.phone + '</h3><br>';
            
            // واتساب
            const wa = data.whatsapp || {};
            html += '<strong>💬 واتساب:</strong> ';
            if (wa.exists === true) html += '<span class="status-badge status-true">✅ موجود</span>';
            else if (wa.exists === false) html += '<span class="status-badge status-false">❌ غير مسجل</span>';
            else html += '<span class="status-badge status-unknown">⚠️ غير معروف</span>';
            html += '<br><br>';
            
            // Viber
            const vb = data.viber || {};
            html += '<strong>📞 Viber:</strong> ';
            if (vb.exists === true) html += '<span class="status-badge status-true">✅ موجود</span>';
            else if (vb.exists === false) html += '<span class="status-badge status-false">❌ غير مسجل</span>';
            else html += '<span class="status-badge status-unknown">⚠️ غير معروف</span>';
            html += '<br><br>';
            
            // Signal
            const sg = data.signal || {};
            html += '<strong>🔒 Signal:</strong> ';
            if (sg.exists === true) html += '<span class="status-badge status-true">✅ موجود</span>';
            else if (sg.exists === false) html += '<span class="status-badge status-false">❌ غير مسجل</span>';
            else html += '<span class="status-badge status-unknown">⚠️ غير معروف</span>';
            html += '<br><br>';
            
            // Truecaller
            const tc = data.truecaller || {};
            html += '<strong>👤 Truecaller:</strong> ';
            if (tc.found) html += tc.name;
            else html += 'غير موجود';
            html += '<br><br>';
            
            // Carrier
            const cr = data.carrier || {};
            if (!cr.error) {
                html += '<strong>📶 الشبكة:</strong> ' + (cr.carrier || 'غير معروف') + '<br>';
                html += '<strong>🌍 الدولة:</strong> ' + (cr.country || 'غير معروف') + '<br>';
                html += '<strong>✅ صالح:</strong> ' + (cr.valid ? 'نعم' : 'لا') + '<br><br>';
            }
            
            // NumVerify
            const nv = data.numverify || {};
            if (!nv.error && nv.valid !== undefined) {
                html += '<strong>🔍 NumVerify:</strong><br>';
                html += '├ الدولة: ' + (nv.country || '-') + '<br>';
                html += '├ المزود: ' + (nv.carrier || '-') + '<br>';
                html += '├ النوع: ' + (nv.line_type || '-') + '<br>';
                html += '└ الموقع: ' + (nv.location || '-') + '<br>';
            }
            
            return html;
        }
        
        function showLoading(id, show) {
            document.getElementById(id).classList.toggle('show', show);
        }
        
        function hideResult(id) {
            document.getElementById(id).classList.remove('show', 'success', 'error');
            document.getElementById(id).innerHTML = '';
        }
        
        function showResult(id, content, success) {
            const el = document.getElementById(id);
            el.innerHTML = content;
            el.classList.add('show');
            el.classList.add(success ? 'success' : 'error');
        }
    </script>
</body>
</html>
"""

# ==================== صفحات الموقع ====================
PHONE_PAGE = """
{% extends "base" %}
{% block content %}
<div class="card">
    <h2>📱 فحص رقم الهاتف</h2>
    <div class="input-group">
        <input type="tel" id="phone" placeholder="+201234567890" value="+20">
        <button class="btn" onclick="scanPhone()">🔍 فحص</button>
    </div>
    <div class="loading" id="phoneLoading"><div class="spinner"></div><p>جاري الفحص...</p></div>
    <div class="result-box" id="phoneResult"></div>
</div>

<div class="card">
    <h2>📊 آخر الفحوصات</h2>
    <table>
        <tr><th>الهدف</th><th>النوع</th><th>التاريخ</th></tr>
        {% for scan in recent_scans %}
        <tr>
            <td>{{ scan.target }}</td>
            <td>{{ scan.scan_type }}</td>
            <td>{{ scan.created_at }}</td>
        </tr>
        {% endfor %}
    </table>
</div>
{% endblock %}
"""

IP_PAGE = """
{% extends "base" %}
{% block content %}
<div class="card">
    <h2>🌐 فحص عنوان IP</h2>
    <div class="input-group">
        <input type="text" id="ip" placeholder="8.8.8.8">
        <button class="btn" onclick="scanIP()">🔍 فحص</button>
    </div>
    <div class="loading" id="ipLoading"><div class="spinner"></div><p>جاري الفحص...</p></div>
    <div class="result-box" id="ipResult"></div>
</div>
{% endblock %}
"""

URL_PAGE = """
{% extends "base" %}
{% block content %}
<div class="card">
    <h2>🔗 فحص رابط</h2>
    <div class="input-group">
        <input type="url" id="url" placeholder="https://example.com">
        <button class="btn" onclick="scanURL()">🔍 فحص</button>
    </div>
    <div class="loading" id="urlLoading"><div class="spinner"></div><p>جاري الفحص...</p></div>
    <div class="result-box" id="urlResult"></div>
</div>
{% endblock %}
"""

API_PAGE = """
{% extends "base" %}
{% block content %}
<div class="card">
    <h2>⚡ API Documentation</h2>
    
    <h3>فحص رقم</h3>
    <div class="result-box show" style="background:#0a0a0a; padding:15px;">
        <strong>POST</strong> /api/scan/phone<br>
        <strong>Body:</strong> {"phone": "+201234567890"}
    </div>
    <br>
    
    <h3>فحص IP</h3>
    <div class="result-box show" style="background:#0a0a0a; padding:15px;">
        <strong>POST</strong> /api/scan/ip<br>
        <strong>Body:</strong> {"ip": "8.8.8.8"}
    </div>
    <br>
    
    <h3>فحص رابط</h3>
    <div class="result-box show" style="background:#0a0a0a; padding:15px;">
        <strong>POST</strong> /api/scan/url<br>
        <strong>Body:</strong> {"url": "https://example.com"}
    </div>
</div>
{% endblock %}
"""

# ==================== Routes ====================
@web_app.route('/')
def home():
    recent = run_async(get_recent_scans(10))
    return render_template_string(
        HTML_TEMPLATE.replace('{% extends "base" %}', '') + 
        PHONE_PAGE.replace('{% extends "base" %}', ''),
        active_page='phone',
        recent_scans=recent
    )

@web_app.route('/ip')
def ip_page():
    return render_template_string(
        HTML_TEMPLATE.replace('{% extends "base" %}', '') + 
        IP_PAGE.replace('{% extends "base" %}', ''),
        active_page='ip'
    )

@web_app.route('/url')
def url_page():
    return render_template_string(
        HTML_TEMPLATE.replace('{% extends "base" %}', '') + 
        URL_PAGE.replace('{% extends "base" %}', ''),
        active_page='url'
    )

@web_app.route('/api')
def api_page():
    return render_template_string(
        HTML_TEMPLATE.replace('{% extends "base" %}', '') + 
        API_PAGE.replace('{% extends "base" %}', ''),
        active_page='api'
    )

# ==================== API Routes ====================
@web_app.route('/api/scan/phone', methods=['POST'])
def api_scan_phone():
    data = request.get_json()
    phone = data.get('phone', '')
    
    if not phone:
        return jsonify({"error": "الرجاء إدخال رقم الهاتف"}), 400
    
    try:
        results = run_async(scanner.scan_phone(phone))
        
        # حفظ الفحص
        run_async(save_scan(phone, 'phone', json.dumps(results)))
        
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@web_app.route('/api/scan/ip', methods=['POST'])
def api_scan_ip():
    data = request.get_json()
    ip = data.get('ip', '')
    
    if not ip:
        return jsonify({"error": "الرجاء إدخال IP"}), 400
    
    try:
        results = run_async(scanner.scan_ip(ip))
        run_async(save_scan(ip, 'ip', json.dumps(results)))
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@web_app.route('/api/scan/url', methods=['POST'])
def api_scan_url():
    data = request.get_json()
    url = data.get('url', '')
    
    if not url:
        return jsonify({"error": "الرجاء إدخال رابط"}), 400
    
    try:
        results = run_async(scanner.scan_url(url))
        run_async(save_scan(url, 'url', json.dumps(results)))
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@web_app.route('/api/stats')
def api_stats():
    count = run_async(get_scan_count())
    return jsonify({
        "total_scans": count,
        "uptime": "running",
        "version": "4.0.0"
    })

# ==================== دوال مساعدة ====================
async def save_scan(target: str, scan_type: str, result: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO scans (target, scan_type, result, ip_address) VALUES (?, ?, ?, ?)",
            (target, scan_type, result, request.remote_addr if hasattr(request, 'remote_addr') else '')
        )
        await db.commit()

async def get_recent_scans(limit: int = 10) -> List:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT target, scan_type, created_at FROM scans ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {"target": r[0], "scan_type": r[1], "created_at": r[2]}
                for r in rows
            ]

async def get_scan_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM scans") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

# ==================== التشغيل ====================
def main():
    run_async(init_db())
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║           🔥 SHADOW OSINT - موقع ويب متكامل 🔥              ║
║         المستخدم يتحمل المسؤولية القانونية كاملة              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    print(f"🌐 الرابط: http://0.0.0.0:{PORT}")
    print(f"📱 NumVerify: {'✅ متصل' if NUMVERIFY_KEY else '❌ غير متصل'}")
    print(f"🛡️ VirusTotal: {'✅ متصل' if VIRUSTOTAL_KEY else '❌ غير متصل'}")
    print(f"🔍 Shodan: {'✅ متصل' if SHODAN_KEY else '❌ غير متصل'}")
    print("═" * 60)
    print("⚡ الموقع شغال...")
    
    web_app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)

if __name__ == "__main__":
    main()
