import asyncio
import json
import os
import time
import threading
from flask import Flask, jsonify, request
from pybaileys import WhatsApp, QRCodeHandler
import qrcode
from io import BytesIO
import base64

app = Flask(__name__)

# ====== إعدادات ======
SESSIONS_DIR = "./wa_sessions"
USERS_FILE = "./wa_users.json"

os.makedirs(SESSIONS_DIR, exist_ok=True)
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w") as f:
        json.dump({}, f)

# ====== تخزين الجلسات ======
clients = {}
qr_codes = {}
status_map = {}

# ====== دوال مساعدة ======
def save_user(user_id, data):
    with open(USERS_FILE, "r") as f:
        users = json.load(f)
    users[user_id] = data
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def get_user(user_id):
    with open(USERS_FILE, "r") as f:
        users = json.load(f)
    return users.get(user_id)

# ====== تشغيل واتساب ======
async def start_whatsapp(user_id):
    session_path = os.path.join(SESSIONS_DIR, f"{user_id}.json")
    
    # إنشاء عميل واتساب
    client = WhatsApp(
        session_path=session_path,
        auto_reconnect=True,
        print_qr=False
    )
    
    clients[user_id] = client
    status_map[user_id] = "connecting"
    
    # حدث عند استلام QR
    @client.on("qr")
    async def on_qr(qr_data):
        # تحويل QR إلى صورة
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        # تحويل الصورة إلى base64
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        qr_codes[user_id] = f"data:image/png;base64,{img_str}"
        status_map[user_id] = "qr_ready"
        print(f"[WhatsApp] QR ready for {user_id}")
    
    # حدث عند الاتصال
    @client.on("connected")
    async def on_connected():
        status_map[user_id] = "connected"
        qr_codes.pop(user_id, None)
        
        # حفظ معلومات المستخدم
        user_info = {
            "id": user_id,
            "name": client.name or "Unknown",
            "number": client.phone_number or "Unknown",
            "connected_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        save_user(user_id, user_info)
        print(f"[WhatsApp] {user_id} connected")
    
    # حدث عند قطع الاتصال
    @client.on("disconnected")
    async def on_disconnected():
        status_map[user_id] = "disconnected"
        print(f"[WhatsApp] {user_id} disconnected")
    
    # معالجة الرسائل الواردة
    @client.on("message")
    async def on_message(message):
        try:
            text = message.get("text", "")
            if not text or not text.startswith("."):
                return
            
            cmd = text[1:].split(" ")[0].lower()
            args = " ".join(text[1:].split(" ")[1:])
            
            # أوامر بسيطة
            if cmd == "بنغ":
                await client.send_message(message["from"], "[PyWhats] Ping!")
            elif cmd == "وقتي":
                now = time.strftime("%H:%M")
                await client.send_message(message["from"], f"⏰ {now}")
            elif cmd == "اوامر":
                cmds = """╭━━[ PyWhats ]━━╮
│ .بنغ - Ping
│ .وقتي - Time
│ .عريض - Bold
│ .مائل - Italic
╰━━━━━━━━━━━━━━╯"""
                await client.send_message(message["from"], cmds)
        except Exception as e:
            print(f"[WhatsApp] Message error: {e}")
    
    try:
        await client.start()
    except Exception as e:
        status_map[user_id] = "error"
        print(f"[WhatsApp] Error: {e}")

# ====== تشغيل الخادم ======
@app.route('/start', methods=['POST'])
def start_session():
    data = request.json
    user_id = data.get("userId")
    if not user_id:
        return jsonify({"error": "Missing userId"}), 400
    
    if user_id in clients:
        return jsonify({"success": True, "message": "Already running"})
    
    try:
        asyncio.create_task(start_whatsapp(user_id))
        return jsonify({"success": True, "userId": user_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/qr/<user_id>')
def get_qr(user_id):
    if user_id in qr_codes:
        return jsonify({
            "qr": qr_codes[user_id],
            "status": "qr_ready"
        })
    elif status_map.get(user_id) == "connected":
        return jsonify({"status": "connected"})
    else:
        return jsonify({"status": "waiting"})

@app.route('/status/<user_id>')
def get_status(user_id):
    status = status_map.get(user_id, "unknown")
    user = get_user(user_id)
    return jsonify({"status": status, "user": user})

@app.route('/health')
def health():
    return jsonify({"status": "ok", "clients": len(clients)})

# ====== التشغيل ======
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"[System] Starting server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
