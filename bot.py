#!/usr/bin/env python3
"""
SHADOW OSINT - نسخة Railway
"""

import os
import json
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string

# ==================== Flask App ====================
web_app = Flask(__name__)

# ==================== HTML ====================
HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>SHADOW OSINT</title>
    <style>
        body { font-family: Arial; background: #0a0a0a; color: #fff; padding: 20px; }
        .card { background: #1a1a2e; padding: 20px; border-radius: 10px; margin: 10px 0; max-width: 600px; margin: 10px auto; }
        input { padding: 10px; width: 70%; background: #000; color: #fff; border: 1px solid #333; border-radius: 5px; }
        button { padding: 10px 20px; background: #e94560; color: #fff; border: none; border-radius: 5px; cursor: pointer; }
        .result { background: #000; padding: 15px; border-radius: 5px; margin-top: 10px; display: none; }
    </style>
</head>
<body>
    <h1 style="text-align:center;color:#e94560">🔥 SHADOW OSINT</h1>
    
    <div class="card">
        <h2>📱 فحص رقم</h2>
        <input id="phone" placeholder="+201234567890">
        <button onclick="scan()">فحص</button>
        <div id="result" class="result"></div>
    </div>
    
    <script>
        async function scan() {
            var phone = document.getElementById('phone').value;
            var res = document.getElementById('result');
            res.style.display = 'block';
            res.innerHTML = 'جاري الفحص...';
            
            try {
                var r = await fetch('/scan', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({phone: phone})
                });
                var data = await r.json();
                
                var html = '<h3>نتيجة: ' + phone + '</h3>';
                html += '<p>واتساب: ' + (data.whatsapp ? '✅ موجود' : '❌ غير مسجل') + '</p>';
                html += '<p>صالح: ' + (data.valid ? '✅' : '❌') + '</p>';
                html += '<p>الدولة: ' + (data.country || '?') + '</p>';
                html += '<p>الشبكة: ' + (data.carrier || '?') + '</p>';
                
                res.innerHTML = html;
            } catch(e) {
                res.innerHTML = 'خطأ: ' + e.message;
            }
        }
    </script>
</body>
</html>"""

# ==================== Routes ====================
@web_app.route('/')
def home():
    return HTML

@web_app.route('/scan', methods=['POST'])
def scan():
    try:
        data = request.get_json()
        phone = data.get('phone', '')
        
        result = {
            "phone": phone,
            "whatsapp": False,
            "valid": True,
            "country": "Egypt",
            "carrier": "Unknown"
        }
        
        # فحص واتساب
        try:
            import httpx
            clean = phone.replace('+', '').replace(' ', '')
            r = httpx.get(f'https://wa.me/{clean}', follow_redirects=True, timeout=10)
            result['whatsapp'] = 'Continue to Chat' in r.text
        except:
            pass
        
        # فحص الشبكة
        try:
            import phonenumbers
            from phonenumbers import carrier, geocoder
            p = phonenumbers.parse(phone)
            result['valid'] = phonenumbers.is_valid_number(p)
            result['country'] = geocoder.description_for_number(p, 'en') or 'Unknown'
            result['carrier'] = carrier.name_for_number(p, 'en') or 'Unknown'
        except:
            pass
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@web_app.route('/health')
def health():
    return jsonify({"status": "ok"})

# ==================== Run ====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f'Running on port {port}')
    web_app.run(host='0.0.0.0', port=port, debug=False)
