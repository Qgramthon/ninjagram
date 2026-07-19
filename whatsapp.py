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
import re

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
phone_data = {}

# ====== دوال مساعدة ======
def generate_qr_for_phone(phone_number):
    """إنشاء QR Code لربط رقم الهاتف"""
    # تنظيف رقم الهاتف
    clean_phone = re.sub(r'[^0-9+]', '', phone_number)
    
    # إنشاء QR يحتوي على رابط واتساب + الرقم
    qr = qrcode.QRCode(box_size=10, border=4)
    # رابط واتساب الصحيح للربط
    qr_data_str = f"https://wa.me/{clean_phone}?text=ربط%20واتساب%20بوت"
    qr.add_data(qr_data_str)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return f"data:image/png;base64,{img_str}"

# ====== Routes ======

@app.route('/start', methods=['POST'])
def start_session():
    try:
        data = request.get_json()
        user_id = data.get('userId', f"user_{int(time.time())}")
        phone_number = data.get('phone', '')
        
        # إنشاء QR مع الرقم لو موجود
        if phone_number:
            qr_image = generate_qr_for_phone(phone_number)
            qr_data[user_id] = qr_image
            phone_data[user_id] = phone_number
            status_data[user_id] = "qr_ready"
            
            # حفظ في ملف
            with open(QR_FILE, "w") as f:
                json.dump({"qr": qr_image, "userId": user_id, "phone": phone_number}, f)
            
            return jsonify({
                "success": True,
                "userId": user_id,
                "phone": phone_number,
                "status": "qr_ready",
                "message": f"QR Code for {phone_number} ready"
            })
        else:
            # QR عادي لو مفيش رقم
            qr = qrcode.QRCode(box_size=10, border=4)
            qr.add_data(f"whatsapp://connect?user={user_id}")
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            qr_data[user_id] = f"data:image/png;base64,{img_str}"
            status_data[user_id] = "qr_ready"
            
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
                "status": "qr_ready",
                "phone": phone_data.get(user_id, "")
            })
        
        # جلب QR من الملف
        if os.path.exists(QR_FILE):
            with open(QR_FILE, "r") as f:
                data = json.load(f)
                if data.get("qr") and data.get("userId") == user_id:
                    qr_data[user_id] = data["qr"]
                    phone_data[user_id] = data.get("phone", "")
                    return jsonify({
                        "qr": data["qr"],
                        "status": "qr_ready",
                        "phone": data.get("phone", "")
                    })
        
        # QR جديد مع رابط واتساب
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(f"https://wa.me/?text=ربط%20واتساب")
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
        if user_id in status_data:
            return jsonify({"status": status_data[user_id]})
        
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r") as f:
                users = json.load(f)
                if user_id in users:
                    return jsonify({
                        "status": "connected",
                        "user": users[user_id]
                    })
        
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
