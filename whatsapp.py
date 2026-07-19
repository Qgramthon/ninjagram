import os
import json
import time
import random
import re
from flask import Flask, jsonify, request

app = Flask(__name__)

# ====== إعدادات ======
PORT = 3000
USERS_FILE = "./wa_users.json"
VERIFICATION_FILE = "./wa_verification.json"

os.makedirs("./wa_sessions", exist_ok=True)
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w") as f:
        json.dump({}, f)
if not os.path.exists(VERIFICATION_FILE):
    with open(VERIFICATION_FILE, "w") as f:
        json.dump({}, f)

# ====== تخزين مؤقت ======
verification_codes = {}  # {user_id: {"phone": "number", "code": "12345678", "timestamp": time}}

# ====== دوال مساعدة ======
def generate_code():
    """توليد كود ربط من 8 أرقام"""
    return ''.join([str(random.randint(0, 9)) for _ in range(8)])

def save_verification(user_id, phone, code):
    """حفظ كود الربط في الملف"""
    data = {
        "phone": phone,
        "code": code,
        "timestamp": time.time()
    }
    verification_codes[user_id] = data
    
    with open(VERIFICATION_FILE, "w") as f:
        json.dump(verification_codes, f, indent=2)
    
    return data

def get_verification(user_id):
    """جلب كود الربط من الذاكرة أو الملف"""
    if user_id in verification_codes:
        return verification_codes[user_id]
    
    if os.path.exists(VERIFICATION_FILE):
        with open(VERIFICATION_FILE, "r") as f:
            data = json.load(f)
            if user_id in data:
                verification_codes[user_id] = data[user_id]
                return data[user_id]
    
    return None

def verify_code(user_id, code):
    """التحقق من صحة كود الربط"""
    data = get_verification(user_id)
    if not data:
        return {"valid": False, "message": "No verification request found"}
    
    # التحقق من صلاحية الكود (5 دقائق)
    if time.time() - data["timestamp"] > 300:
        return {"valid": False, "message": "Code expired, request a new one"}
    
    if data["code"] == code:
        # تسجيل المستخدم
        users = {}
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r") as f:
                users = json.load(f)
        
        users[user_id] = {
            "phone": data["phone"],
            "connected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "verified": True
        }
        
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=2)
        
        return {"valid": True, "message": "Phone verified successfully"}
    
    return {"valid": False, "message": "Invalid code"}

# ====== Routes ======

@app.route('/start', methods=['POST'])
def start_session():
    try:
        data = request.get_json()
        user_id = data.get('userId', f"user_{int(time.time())}")
        phone = data.get('phone', '').strip()
        
        if not phone:
            return jsonify({"error": "Phone number is required"}), 400
        
        # تنظيف رقم الهاتف
        clean_phone = re.sub(r'[^0-9+]', '', phone)
        
        # توليد كود ربط
        code = generate_code()
        save_verification(user_id, clean_phone, code)
        
        return jsonify({
            "success": True,
            "userId": user_id,
            "phone": clean_phone,
            "code": code,  # إرجاع الكود للتطبيق (سيظهر للمستخدم)
            "status": "code_sent",
            "message": f"Pairing code generated for {clean_phone}"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/verify', methods=['POST'])
def verify():
    try:
        data = request.get_json()
        user_id = data.get('userId')
        code = data.get('code', '').strip()
        
        if not user_id or not code:
            return jsonify({"error": "User ID and code are required"}), 400
        
        result = verify_code(user_id, code)
        
        if result["valid"]:
            return jsonify({
                "success": True,
                "status": "verified",
                "message": result["message"]
            })
        else:
            return jsonify({
                "success": False,
                "status": "invalid",
                "message": result["message"]
            }), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/status/<user_id>')
def get_status(user_id):
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r") as f:
                users = json.load(f)
                if user_id in users:
                    return jsonify({
                        "status": "verified",
                        "user": users[user_id]
                    })
        
        data = get_verification(user_id)
        if data:
            return jsonify({
                "status": "code_sent",
                "phone": data["phone"]
            })
        
        return jsonify({"status": "waiting"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/resend', methods=['POST'])
def resend_code():
    try:
        data = request.get_json()
        user_id = data.get('userId')
        phone = data.get('phone', '').strip()
        
        if not user_id:
            return jsonify({"error": "User ID required"}), 400
        
        if phone:
            clean_phone = re.sub(r'[^0-9+]', '', phone)
        else:
            existing = get_verification(user_id)
            if existing:
                clean_phone = existing["phone"]
            else:
                return jsonify({"error": "Phone number required"}), 400
        
        code = generate_code()
        save_verification(user_id, clean_phone, code)
        
        return jsonify({
            "success": True,
            "userId": user_id,
            "phone": clean_phone,
            "code": code,
            "status": "code_sent",
            "message": f"New pairing code generated for {clean_phone}"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "platform": "whatsapp",
        "verifications": len(verification_codes)
    })

@app.route('/')
def home():
    return jsonify({
        "service": "WhatsApp Pairing Server",
        "status": "running",
        "port": PORT
    })

if __name__ == "__main__":
    print(f"[WhatsApp] Server starting on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
