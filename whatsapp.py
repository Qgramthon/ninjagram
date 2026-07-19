import os
import json
import time
import threading
import subprocess
from flask import Flask, jsonify, request
import qrcode
from io import BytesIO
import base64
import random

app = Flask(__name__)

# ====== إعدادات ======
PORT = 3000
SESSIONS_DIR = "./wa_sessions"
USERS_FILE = "./wa_users.json"
QR_FILE = "./wa_qr.json"

os.makedirs(SESSIONS_DIR, exist_ok=True)
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w") as f:
        json.dump({}, f)

# ====== تخزين مؤقت ======
qr_data = {}
status_data = {}

# ====== Routes ======

@app.route('/start', methods=['POST'])
def start_session():
    try:
        data = request.get_json()
        user_id = data.get('userId', f"user_{int(time.time())}")
        
        # إنشاء QR وهمي للاختبار
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(f"whatsapp://connect?user={user_id}")
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        qr_data[user_id] = f"data:image/png;base64,{img_str}"
        status_data[user_id] = "qr_ready"
        
        # حفظ في ملف
        with open(QR_FILE, "w") as f:
            json.dump({"qr": qr_data[user_id], "userId": user_id}, f)
        
        return jsonify({
            "success": True,
            "userId": user_id,
            "status": "qr_ready"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/qr/<user_id>')
def get_qr(user_id):
    try:
        # جلب QR من الذاكرة
        if user_id in qr_data:
            return jsonify({
                "qr": qr_data[user_id],
                "status": "qr_ready"
            })
        
        # جلب QR من الملف
        if os.path.exists(QR_FILE):
            with open(QR_FILE, "r") as f:
                data = json.load(f)
                if data.get("qr"):
                    qr_data[user_id] = data["qr"]
                    return jsonify({
                        "qr": data["qr"],
                        "status": "qr_ready"
                    })
        
        # محاكاة QR جديد
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(f"whatsapp://connect?user={user_id}")
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        qr_data[user_id] = f"data:image/png;base64,{img_str}"
        
        return jsonify({
            "qr": qr_data[user_id],
            "status": "qr_ready"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/status/<user_id>')
def get_status(user_id):
    try:
        # جلب الحالة من الذاكرة
        if user_id in status_data:
            return jsonify({"status": status_data[user_id]})
        
        # جلب الحالة من الملف
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r") as f:
                users = json.load(f)
                if user_id in users:
                    return jsonify({
                        "status": "connected",
                        "user": users[user_id]
                    })
        
        # حالة افتراضية
        return jsonify({"status": "waiting"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "platform": "whatsapp",
        "clients": len(qr_data)
    })

@app.route('/')
def home():
    return jsonify({
        "service": "WhatsApp Server",
        "status": "running",
        "port": PORT
    })

# ====== تشغيل السيرفر ======
if __name__ == "__main__":
    print(f"[WhatsApp] Server starting on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
