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
import base64
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
from flask import Flask, render_template_string, request, jsonify, session

# ==================== التهيئة ====================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SHADOW_OSINT")

web_app = Flask(__name__)
web_app.secret_key = secrets.token_hex(32)

PORT = int(os.environ.get("PORT", 8080))
NUMVERIFY_KEY = os.environ.get("NUMVERIFY_KEY", "")
VIRUSTOTAL_KEY = os.environ.get("VIRUSTOTAL_KEY", "")
SHODAN_KEY = os.environ.get("SHODAN_KEY", "")
IPINFO_TOKEN = os.environ.get("IPINFO_TOKEN", "")
DB_PATH = "shadow_osint.db"

ua = UserAgent()

# ==================== قاعدة البيانات ====================
def init_db():
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT,
            scan_type TEXT,
            result TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_scan(target, scan_type, result, ip=""):
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO scans (target, scan_type, result, ip_address) VALUES (?, ?, ?, ?)",
        (target, scan_type, json.dumps(result, ensure_ascii=False), ip)
    )
    conn.commit()
    conn.close()

def get_recent_scans(limit=10):
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT target, scan_type, created_at FROM scans ORDER BY created_at DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"target": r[0], "scan_type": r[1], "created_at": r[2]} for r in rows]

# ==================== محرك الفحص ====================
class Scanner:
    def __init__(self):
        self.ua = UserAgent()
    
    def scan_phone(self, phone):
        """فحص رقم الهاتف"""
        results = {
            "phone": phone,
            "timestamp": datetime.now().isoformat(),
            "whatsapp": {},
            "viber": {},
            "signal": {},
            "truecaller": {},
            "carrier": {},
            "numverify": {}
        }
        
        # واتساب
        clean = phone.replace("+", "").replace(" ", "").replace("-", "")
        try:
            resp = httpx.get(f"https://wa.me/{clean}", headers={"User-Agent": self.ua.random}, follow_redirects=True, timeout=10)
            results["whatsapp"] = {"exists": "Continue to Chat" in resp.text}
        except:
            results["whatsapp"] = {"exists": None}
        
        # Viber
        try:
            resp = httpx.post("https://api.viber.com/api/v2/check", json={"phone": phone}, headers={"User-Agent": self.ua.random}, timeout=10)
            if resp.status_code == 200:
                results["viber"] = {"exists": resp.json().get("exists", False)}
        except:
            results["viber"] = {"exists": None}
        
        # Signal
        try:
            resp = httpx.get(f"https://api.signal.org/v1/accounts/{phone}", headers={"User-Agent": "Signal-Android/6.0"}, timeout=10)
            results["signal"] = {"exists": resp.status_code == 200}
        except:
            results["signal"] = {"exists": None}
        
        # Truecaller
        try:
            resp = httpx.get(f"https://www.truecaller.com/search/eg/{clean}", headers={"User-Agent": self.ua.random, "Accept-Language": "ar,en;q=0.9"}, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'lxml')
                scripts = soup.find_all("script", type="application/ld+json")
                found = False
                for script in scripts:
                    if script.string:
                        try:
                            data = json.loads(script.string)
                            name = data.get("name", "")
                            if name:
                                results["truecaller"] = {"found": True, "name": name}
                                found = True
                                break
                        except:
                            pass
                if not found:
                    results["truecaller"] = {"found": False}
        except:
            results["truecaller"] = {"error": "تعذر الفحص"}
        
        # Carrier
        try:
            parsed = phonenumbers.parse(phone)
            results["carrier"] = {
                "valid": phonenumbers.is_valid_number(parsed),
                "country": geocoder.description_for_number(parsed, "en"),
                "carrier": carrier.name_for_number(parsed, "en"),
                "timezone": list(ph_timezone.time_zones_for_number(parsed)),
                "national": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL),
                "international": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
            }
        except Exception as e:
            results["carrier"] = {"error": str(e)}
        
        # NumVerify
        if NUMVERIFY_KEY:
            try:
                resp = httpx.get("http://apilayer.net/api/validate", params={
                    "access_key": NUMVERIFY_KEY, "number": phone, "format": 1
                }, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    results["numverify"] = {
                        "valid": data.get("valid"),
                        "country": data.get("country_name"),
                        "carrier": data.get("carrier"),
                        "line_type": data.get("line_type"),
                        "location": data.get("location")
                    }
            except:
                pass
        
        return results
    
    def scan_ip(self, ip):
        """فحص IP"""
        results = {"ip": ip, "timestamp": datetime.now().isoformat()}
        
        # IPInfo
        try:
            url = f"https://ipinfo.io/{ip}/json"
            if IPINFO_TOKEN:
                url += f"?token={IPINFO_TOKEN}"
            resp = httpx.get(url, timeout=10)
            if resp.status_code == 200:
                results["ipinfo"] = resp.json()
        except:
            pass
        
        # GeoIP
        try:
            resp = httpx.get(f"http://ip-api.com/json/{ip}", timeout=10)
            if resp.status_code == 200:
                results["geoip"] = resp.json()
        except:
            pass
        
        # Shodan
        if SHODAN_KEY:
            try:
                resp = httpx.get(f"https://api.shodan.io/shodan/host/{ip}", params={"key": SHODAN_KEY}, timeout=10)
                if resp.status_code == 200:
                    results["shodan"] = resp.json()
            except:
                pass
        
        # Port Scan
        ports = [21, 22, 23, 25, 53, 80, 110, 143, 443, 993, 995, 8080, 8443]
        open_ports = []
        for port in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                if sock.connect_ex((ip, port)) == 0:
                    open_ports.append(port)
                sock.close()
            except:
                pass
        results["ports"] = {"open": open_ports, "scanned": ports}
        
        # Reverse DNS
        try:
            results["reverse_dns"] = socket.gethostbyaddr(ip)[0]
        except:
            results["reverse_dns"] = None
        
        return results
    
    def scan_url(self, url):
        """فحص رابط"""
        results = {"url": url, "timestamp": datetime.now().isoformat()}
        
        # SSL
        try:
            hostname = urlparse(url).hostname or url
            ctx = ssl.create_default_context()
            with socket.create_connection((hostname, 443), timeout=5) as sock:
                with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    results["ssl"] = {
                        "issuer": dict(x[0] for x in cert.get("issuer", [])),
                        "valid_from": cert.get("notBefore"),
                        "valid_to": cert.get("notAfter")
                    }
        except Exception as e:
            results["ssl"] = {"error": str(e)}
        
        # Headers
        try:
            resp = httpx.get(url, timeout=10, follow_redirects=True)
            security = {
                "Strict-Transport-Security": resp.headers.get("Strict-Transport-Security"),
                "Content-Security-Policy": resp.headers.get("Content-Security-Policy"),
                "X-Frame-Options": resp.headers.get("X-Frame-Options"),
                "X-Content-Type-Options": resp.headers.get("X-Content-Type-Options"),
            }
            results["headers"] = {
                "security": security,
                "missing": [k for k, v in security.items() if not v],
                "server": resp.headers.get("Server", "Unknown"),
                "status": resp.status_code
            }
        except:
            pass
        
        # VirusTotal
        if VIRUSTOTAL_KEY:
            try:
                url_id = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
                resp = httpx.get(
                    f"https://www.virustotal.com/api/v3/urls/{url_id}",
                    headers={"x-apikey": VIRUSTOTAL_KEY},
                    timeout=15
                )
                if resp.status_code == 200:
                    stats = resp.json().get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                    results["virustotal"] = stats
            except:
                pass
        
        return results

scanner = Scanner()

# ==================== HTML ====================
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SHADOW OSINT - أداة الاستخبارات</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, sans-serif; background: #0a0a0a; color: #e0e0e0; min-height: 100vh; }
        .container { max-width: 1000px; margin: 0 auto; padding: 15px; }
        .header { background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px; text-align: center; border-bottom: 2px solid #e94560; }
        .header h1 { font-size: 2em; color: #e94560; }
        .header p { color: #888; margin-top: 8px; font-size: 14px; }
        .nav { display: flex; justify-content: center; gap: 8px; padding: 12px; flex-wrap: wrap; }
        .nav a { padding: 8px 18px; background: #1a1a2e; color: #e0e0e0; text-decoration: none; border-radius: 5px; border: 1px solid #333; font-size: 14px; }
        .nav a:hover, .nav a.active { background: #e94560; border-color: #e94560; color: white; }
        .card { background: #1a1a2e; border: 1px solid #333; border-radius: 8px; padding: 20px; margin: 15px 0; }
        .card h2 { color: #e94560; margin-bottom: 15px; font-size: 1.3em; }
        .input-group { display: flex; gap: 8px; margin-bottom: 12px; }
        input { flex: 1; padding: 10px 12px; background: #0a0a0a; border: 1px solid #333; border-radius: 5px; color: #e0e0e0; font-size: 15px; }
        input:focus { outline: none; border-color: #e94560; }
        .btn { padding: 10px 25px; background: #e94560; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 15px; }
        .btn:hover { background: #c73e54; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .result-box { background: #0a0a0a; border: 1px solid #333; border-radius: 5px; padding: 15px; margin-top: 15px; font-family: monospace; font-size: 13px; white-space: pre-wrap; max-height: 400px; overflow-y: auto; display: none; }
        .result-box.show { display: block; }
        .result-box.success { border-color: #4caf50; }
        .result-box.error { border-color: #e94560; }
        .loading { text-align: center; padding: 15px; display: none; }
        .loading.show { display: block; }
        .spinner { border: 3px solid #333; border-top: 3px solid #e94560; border-radius: 50%; width: 35px; height: 35px; animation: spin 1s linear infinite; margin: 0 auto; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .status-badge { display: inline-block; padding: 4px 8px; border-radius: 3px; font-weight: bold; font-size: 12px; }
        .status-true { background: #4caf50; color: white; }
        .status-false { background: #e94560; color: white; }
        .status-unknown { background: #ff9800; color: white; }
        table { width: 100%; border-collapse: collapse; margin: 8px 0; }
        th, td { padding: 8px; border: 1px solid #333; text-align: right; font-size: 13px; }
        th { background: #1a1a2e; color: #e94560; }
        td { background: #0a0a0a; }
        .footer { text-align: center; padding: 15px; color: #666; border-top: 1px solid #333; margin-top: 30px; font-size: 12px; }
        @media (max-width: 600px) {
            .input-group { flex-direction: column; }
            .nav { flex-direction: column; }
            .nav a { width: 100%; text-align: center; }
            .header h1 { font-size: 1.5em; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔥 SHADOW OSINT</h1>
        <p>أداة الاستخبارات المفتوحة - فحص أرقام | IP | روابط</p>
    </div>
    <div class="container">
        <div class="nav">
            <a href="/" class="{{ active_phone }}">📱 فحص رقم</a>
            <a href="/ip" class="{{ active_ip }}">🌐 فحص IP</a>
            <a href="/url" class="{{ active_url }}">🔗 فحص رابط</a>
            <a href="/api" class="{{ active_api }}">⚡ API</a>
        </div>
        {{ content|safe }}
    </div>
    <div class="footer">
        <p>⚠️ للأغراض التعليمية والبحثية فقط. المستخدم يتحمل المسؤولية الكاملة.</p>
        <p>SHADOW OSINT v4.0</p>
    </div>
    <script>
        async function scanPhone() {
            var phone = document.getElementById('phone').value;
            if (!phone) return alert('الرجاء إدخال رقم الهاتف');
            showLoading('phoneLoading', true);
            hideResult('phoneResult');
            try {
                var resp = await fetch('/api/scan/phone', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({phone:phone})});
                var data = await resp.json();
                showResult('phoneResult', formatPhone(data), resp.ok);
            } catch(e) {
                showResult('phoneResult', 'خطأ: ' + e.message, false);
            }
            showLoading('phoneLoading', false);
        }
        async function scanIP() {
            var ip = document.getElementById('ip').value;
            if (!ip) return alert('الرجاء إدخال IP');
            showLoading('ipLoading', true);
            hideResult('ipResult');
            try {
                var resp = await fetch('/api/scan/ip', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ip:ip})});
                var data = await resp.json();
                showResult('ipResult', JSON.stringify(data, null, 2), resp.ok);
            } catch(e) {
                showResult('ipResult', 'خطأ: ' + e.message, false);
            }
            showLoading('ipLoading', false);
        }
        async function scanURL() {
            var url = document.getElementById('url').value;
            if (!url) return alert('الرجاء إدخال رابط');
            showLoading('urlLoading', true);
            hideResult('urlResult');
            try {
                var resp = await fetch('/api/scan/url', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({url:url})});
                var data = await resp.json();
                showResult('urlResult', JSON.stringify(data, null, 2), resp.ok);
            } catch(e) {
                showResult('urlResult', 'خطأ: ' + e.message, false);
            }
            showLoading('urlLoading', false);
        }
        function formatPhone(d) {
            var h = '<h3 style="color:#e94560;margin-bottom:10px;">📱 نتيجة فحص: ' + d.phone + '</h3>';
            var wa = d.whatsapp || {};
            h += '<strong>💬 واتساب:</strong> ';
            if (wa.exists===true) h += '<span class="status-badge status-true">✅ موجود</span>';
            else if (wa.exists===false) h += '<span class="status-badge status-false">❌ غير مسجل</span>';
            else h += '<span class="status-badge status-unknown">⚠️ غير معروف</span>';
            h += '<br><br>';
            var vb = d.viber || {};
            h += '<strong>📞 Viber:</strong> ';
            if (vb.exists===true) h += '<span class="status-badge status-true">✅ موجود</span>';
            else if (vb.exists===false) h += '<span class="status-badge status-false">❌ غير مسجل</span>';
            else h += '<span class="status-badge status-unknown">⚠️ غير معروف</span>';
            h += '<br><br>';
            var sg = d.signal || {};
            h += '<strong>🔒 Signal:</strong> ';
            if (sg.exists===true) h += '<span class="status-badge status-true">✅ موجود</span>';
            else if (sg.exists===false) h += '<span class="status-badge status-false">❌ غير مسجل</span>';
            else h += '<span class="status-badge status-unknown">⚠️ غير معروف</span>';
            h += '<br><br>';
            var tc = d.truecaller || {};
            h += '<strong>👤 Truecaller:</strong> ';
            h += tc.found ? tc.name : 'غير موجود';
            h += '<br><br>';
            var cr = d.carrier || {};
            if (!cr.error) {
                h += '<strong>📶 الشبكة:</strong> ' + (cr.carrier||'غير معروف') + '<br>';
                h += '<strong>🌍 الدولة:</strong> ' + (cr.country||'غير معروف') + '<br>';
                h += '<strong>✅ صالح:</strong> ' + (cr.valid?'نعم':'لا') + '<br>';
            }
            return h;
        }
        function showLoading(id, s) { document.getElementById(id).classList.toggle('show', s); }
        function hideResult(id) { var e = document.getElementById(id); e.classList.remove('show','success','error'); e.innerHTML = ''; }
        function showResult(id, content, ok) { var e = document.getElementById(id); e.innerHTML = content; e.classList.add('show'); e.classList.add(ok?'success':'error'); }
    </script>
</body>
</html>"""

PHONE_PAGE = """
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
        {% for scan in recent %}
        <tr><td>{{ scan.target }}</td><td>{{ scan.scan_type }}</td><td>{{ scan.created_at }}</td></tr>
        {% endfor %}
    </table>
</div>
"""

IP_PAGE = """
<div class="card">
    <h2>🌐 فحص عنوان IP</h2>
    <div class="input-group">
        <input type="text" id="ip" placeholder="8.8.8.8">
        <button class="btn" onclick="scanIP()">🔍 فحص</button>
    </div>
    <div class="loading" id="ipLoading"><div class="spinner"></div><p>جاري الفحص...</p></div>
    <div class="result-box" id="ipResult"></div>
</div>
"""

URL_PAGE = """
<div class="card">
    <h2>🔗 فحص رابط</h2>
    <div class="input-group">
        <input type="url" id="url" placeholder="https://example.com">
        <button class="btn" onclick="scanURL()">🔍 فحص</button>
    </div>
    <div class="loading" id="urlLoading"><div class="spinner"></div><p>جاري الفحص...</p></div>
    <div class="result-box" id="urlResult"></div>
</div>
"""

API_PAGE = """
<div class="card">
    <h2>⚡ API Documentation</h2>
    <h3>فحص رقم</h3>
    <div class="result-box show" style="padding:12px;">
        <strong>POST</strong> /api/scan/phone<br>
        <strong>Body:</strong> {"phone": "+201234567890"}
    </div>
    <br>
    <h3>فحص IP</h3>
    <div class="result-box show" style="padding:12px;">
        <strong>POST</strong> /api/scan/ip<br>
        <strong>Body:</strong> {"ip": "8.8.8.8"}
    </div>
    <br>
    <h3>فحص رابط</h3>
    <div class="result-box show" style="padding:12px;">
        <strong>POST</strong> /api/scan/url<br>
        <strong>Body:</strong> {"url": "https://example.com"}
    </div>
</div>
"""

# ==================== Routes ====================
@web_app.route('/')
def home():
    recent = get_recent_scans(10)
    content = PHONE_PAGE.replace('{% for scan in recent %}', '{% for scan in recent %}').replace('{% endfor %}', '{% endfor %}')
    html = HTML_TEMPLATE.replace('{{ active_phone }}', 'active').replace('{{ active_ip }}', '').replace('{{ active_url }}', '').replace('{{ active_api }}', '')
    # تعويض الجدول يدوياً
    table_rows = ""
    for scan in recent:
        table_rows += f"<tr><td>{scan['target']}</td><td>{scan['scan_type']}</td><td>{scan['created_at']}</td></tr>"
    content = content.replace("{% for scan in recent %}<tr><td>{{ scan.target }}</td><td>{{ scan.scan_type }}</td><td>{{ scan.created_at }}</td></tr>{% endfor %}", table_rows)
    html = html.replace('{{ content|safe }}', content)
    return html

@web_app.route('/ip')
def ip_page():
    html = HTML_TEMPLATE.replace('{{ active_phone }}', '').replace('{{ active_ip }}', 'active').replace('{{ active_url }}', '').replace('{{ active_api }}', '')
    html = html.replace('{{ content|safe }}', IP_PAGE)
    return html

@web_app.route('/url')
def url_page():
    html = HTML_TEMPLATE.replace('{{ active_phone }}', '').replace('{{ active_ip }}', '').replace('{{ active_url }}', 'active').replace('{{ active_api }}', '')
    html = html.replace('{{ content|safe }}', URL_PAGE)
    return html

@web_app.route('/api')
def api_page():
    html = HTML_TEMPLATE.replace('{{ active_phone }}', '').replace('{{ active_ip }}', '').replace('{{ active_url }}', '').replace('{{ active_api }}', 'active')
    html = html.replace('{{ content|safe }}', API_PAGE)
    return html

# API
@web_app.route('/api/scan/phone', methods=['POST'])
def api_scan_phone():
    data = request.get_json()
    phone = data.get('phone', '') if data else ''
    if not phone:
        return jsonify({"error": "الرجاء إدخال رقم الهاتف"}), 400
    try:
        results = scanner.scan_phone(phone)
        save_scan(phone, 'phone', results, request.remote_addr or '')
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@web_app.route('/api/scan/ip', methods=['POST'])
def api_scan_ip():
    data = request.get_json()
    ip = data.get('ip', '') if data else ''
    if not ip:
        return jsonify({"error": "الرجاء إدخال IP"}), 400
    try:
        results = scanner.scan_ip(ip)
        save_scan(ip, 'ip', results, request.remote_addr or '')
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@web_app.route('/api/scan/url', methods=['POST'])
def api_scan_url():
    data = request.get_json()
    url = data.get('url', '') if data else ''
    if not url:
        return jsonify({"error": "الرجاء إدخال رابط"}), 400
    try:
        results = scanner.scan_url(url)
        save_scan(url, 'url', results, request.remote_addr or '')
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== التشغيل ====================
def main():
    init_db()
    
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
