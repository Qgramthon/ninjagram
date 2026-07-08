#!/usr/bin/env python3
"""
SHADOW OSINT - موقع ويب للاستخبارات المفتوحة
مضمون التشغيل على Railway
"""

import os, re, json, time, socket, ssl, base64, secrets, sqlite3
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify

# ==================== إعدادات ====================
web_app = Flask(__name__)
web_app.secret_key = secrets.token_hex(32)
PORT = int(os.environ.get("PORT", 8080))
DB_PATH = "shadow.db"

# ==================== قاعدة بيانات ====================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target TEXT, scan_type TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    conn.close()

def save_scan(target, scan_type):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO scans (target, scan_type) VALUES (?, ?)", (target, scan_type))
    conn.commit()
    conn.close()

def get_scans(limit=10):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT target, scan_type, created_at FROM scans ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return rows

# ==================== فحص الهاتف ====================
def check_whatsapp(phone):
    clean = phone.replace("+", "").replace(" ", "").replace("-", "")
    try:
        import httpx
        r = httpx.get(f"https://wa.me/{clean}", follow_redirects=True, timeout=10)
        return "Continue to Chat" in r.text
    except:
        return None

def check_carrier(phone):
    try:
        import phonenumbers
        from phonenumbers import carrier, geocoder
        p = phonenumbers.parse(phone)
        return {
            "valid": phonenumbers.is_valid_number(p),
            "country": geocoder.description_for_number(p, "en"),
            "carrier": carrier.name_for_number(p, "en"),
            "national": phonenumbers.format_number(p, phonenumbers.PhoneNumberFormat.NATIONAL)
        }
    except:
        return {"error": "Invalid phone"}

def scan_phone(phone):
    return {
        "phone": phone,
        "whatsapp": check_whatsapp(phone),
        "carrier": check_carrier(phone),
        "time": datetime.now().isoformat()
    }

# ==================== فحص IP ====================
def scan_ip(ip):
    result = {"ip": ip}
    
    # IP info
    try:
        import httpx
        r = httpx.get(f"http://ip-api.com/json/{ip}", timeout=10)
        if r.status_code == 200:
            result["geo"] = r.json()
    except:
        pass
    
    # Ports
    ports = [21, 22, 80, 443, 8080, 8443]
    open_ports = []
    for port in ports:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            if s.connect_ex((ip, port)) == 0:
                open_ports.append(port)
            s.close()
        except:
            pass
    result["open_ports"] = open_ports
    
    return result

# ==================== HTML ====================
HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SHADOW OSINT</title>
    <style>
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:Arial,sans-serif;background:#0a0a0a;color:#e0e0e0;min-height:100vh}
        .header{background:#1a1a2e;padding:20px;text-align:center;border-bottom:2px solid #e94560}
        .header h1{color:#e94560;font-size:2em}
        .nav{display:flex;justify-content:center;gap:8px;padding:10px;flex-wrap:wrap;background:#111}
        .nav a{padding:8px 18px;background:#1a1a2e;color:#e0e0e0;text-decoration:none;border-radius:5px;border:1px solid #333;font-size:14px}
        .nav a:hover,.nav a.active{background:#e94560;color:white}
        .container{max-width:800px;margin:0 auto;padding:15px}
        .card{background:#1a1a2e;border:1px solid #333;border-radius:8px;padding:20px;margin:15px 0}
        .card h2{color:#e94560;margin-bottom:15px}
        .input-group{display:flex;gap:8px;margin-bottom:10px}
        input{flex:1;padding:10px;background:#0a0a0a;border:1px solid #333;border-radius:5px;color:#fff;font-size:15px}
        input:focus{outline:none;border-color:#e94560}
        .btn{padding:10px 25px;background:#e94560;color:white;border:none;border-radius:5px;cursor:pointer;font-size:15px}
        .btn:hover{background:#c73e54}
        .result{background:#0a0a0a;border:1px solid #333;border-radius:5px;padding:15px;margin-top:15px;display:none;white-space:pre-wrap;font-family:monospace;font-size:13px}
        .result.show{display:block}
        .badge{display:inline-block;padding:4px 8px;border-radius:3px;font-size:12px;font-weight:bold;margin:2px}
        .green{background:#4caf50;color:white}
        .red{background:#e94560;color:white}
        .yellow{background:#ff9800;color:black}
        table{width:100%;border-collapse:collapse;margin:10px 0}
        th,td{padding:8px;border:1px solid #333;text-align:right;font-size:13px}
        th{background:#1a1a2e;color:#e94560}
        .loading{text-align:center;padding:15px;display:none}
        .loading.show{display:block}
        .spinner{border:3px solid #333;border-top:3px solid #e94560;border-radius:50%;width:30px;height:30px;animation:spin 1s linear infinite;margin:0 auto}
        @keyframes spin{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}
    </style>
</head>
<body>
    <div class="header"><h1>🔥 SHADOW OSINT</h1></div>
    <div class="nav">
        <a href="/" class="{{active_phone}}">📱 فحص رقم</a>
        <a href="/ip" class="{{active_ip}}">🌐 فحص IP</a>
        <a href="/api" class="{{active_api}}">⚡ API</a>
    </div>
    <div class="container">{{content|safe}}</div>
    <script>
        async function scanPhone(){
            var p=document.getElementById('phone').value;
            if(!p)return alert('ادخل رقم');
            showL('load');hideR('res');
            try{
                var r=await fetch('/api/scan/phone',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({phone:p})});
                var d=await r.json();
                var h='<h3 style="color:#e94560">📱 '+d.phone+'</h3><br>';
                h+='<b>واتساب:</b> '+(d.whatsapp===true?'<span class="badge green">✅ موجود</span>':d.whatsapp===false?'<span class="badge red">❌ غير مسجل</span>':'<span class="badge yellow">⚠️ غير معروف</span>')+'<br><br>';
                var c=d.carrier||{};
                if(!c.error){h+='<b>الشبكة:</b> '+(c.carrier||'?')+'<br><b>الدولة:</b> '+(c.country||'?')+'<br><b>صالح:</b> '+(c.valid?'✅':'❌')}
                showR('res',h);
            }catch(e){showR('res','❌ خطأ: '+e.message)}
            hideL('load');
        }
        async function scanIP(){
            var ip=document.getElementById('ip').value;
            if(!ip)return alert('ادخل IP');
            showL('load');hideR('res');
            try{
                var r=await fetch('/api/scan/ip',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ip:ip})});
                var d=await r.json();
                showR('res',JSON.stringify(d,null,2));
            }catch(e){showR('res','❌ خطأ: '+e.message)}
            hideL('load');
        }
        function showL(id){document.getElementById(id).classList.add('show')}
        function hideL(id){document.getElementById(id).classList.remove('show')}
        function hideR(id){var e=document.getElementById(id);e.classList.remove('show');e.innerHTML=''}
        function showR(id,c){var e=document.getElementById(id);e.innerHTML=c;e.classList.add('show')}
    </script>
</body>
</html>"""

PHONE_PAGE = """
<div class="card">
    <h2>📱 فحص رقم الهاتف</h2>
    <div class="input-group">
        <input id="phone" placeholder="+201234567890" value="+20">
        <button class="btn" onclick="scanPhone()">🔍 فحص</button>
    </div>
    <div class="loading" id="load"><div class="spinner"></div><p>جاري الفحص...</p></div>
    <div class="result" id="res"></div>
</div>
<div class="card">
    <h2>📊 آخر الفحوصات</h2>
    <table>
        <tr><th>الهدف</th><th>النوع</th><th>التاريخ</th></tr>
        {{table}}
    </table>
</div>
"""

IP_PAGE = """
<div class="card">
    <h2>🌐 فحص IP</h2>
    <div class="input-group">
        <input id="ip" placeholder="8.8.8.8">
        <button class="btn" onclick="scanIP()">🔍 فحص</button>
    </div>
    <div class="loading" id="load"><div class="spinner"></div><p>جاري الفحص...</p></div>
    <div class="result" id="res"></div>
</div>
"""

API_PAGE = """
<div class="card">
    <h2>⚡ API</h2>
    <p>POST /api/scan/phone - {"phone": "+2012..."}</p>
    <p>POST /api/scan/ip - {"ip": "8.8.8.8"}</p>
    <p>GET /api/stats</p>
</div>
"""

# ==================== Routes ====================
@web_app.route('/')
def home():
    scans = get_scans(10)
    rows = ""
    for s in scans:
        rows += f"<tr><td>{s[0]}</td><td>{s[1]}</td><td>{s[2]}</td></tr>"
    content = PHONE_PAGE.replace("{{table}}", rows)
    html = HTML.replace("{{active_phone}}", "active").replace("{{active_ip}}", "").replace("{{active_api}}", "").replace("{{content|safe}}", content)
    return html

@web_app.route('/ip')
def ip_page():
    html = HTML.replace("{{active_phone}}", "").replace("{{active_ip}}", "active").replace("{{active_api}}", "").replace("{{content|safe}}", IP_PAGE)
    return html

@web_app.route('/api')
def api_page():
    html = HTML.replace("{{active_phone}}", "").replace("{{active_ip}}", "").replace("{{active_api}}", "active").replace("{{content|safe}}", API_PAGE)
    return html

@web_app.route('/api/scan/phone', methods=['POST'])
def api_phone():
    try:
        data = request.get_json() or {}
        phone = data.get('phone', '')
        if not phone:
            return jsonify({"error": "ادخل رقم"}), 400
        result = scan_phone(phone)
        save_scan(phone, 'phone')
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@web_app.route('/api/scan/ip', methods=['POST'])
def api_ip():
    try:
        data = request.get_json() or {}
        ip = data.get('ip', '')
        if not ip:
            return jsonify({"error": "ادخل IP"}), 400
        result = scan_ip(ip)
        save_scan(ip, 'ip')
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@web_app.route('/api/stats')
def api_stats():
    scans = get_scans(100)
    return jsonify({"total": len(scans), "recent": [{"target": s[0], "type": s[1], "date": s[2]} for s in scans[:10]]})

@web_app.route('/health')
def health():
    return jsonify({"status": "ok"})

@web_app.errorhandler(500)
def error500(e):
    return jsonify({"error": "خطأ داخلي"}), 500

@web_app.errorhandler(404)
def error404(e):
    return jsonify({"error": "غير موجود"}), 404

# ==================== تشغيل ====================
if __name__ == "__main__":
    init_db()
    print(f"🚀 Shadow OSINT running on port {PORT}")
    web_app.run(host='0.0.0.0', port=PORT, debug=False)
