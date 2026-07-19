import os
import json
import time
import base64
import asyncio
import qrcode
from io import BytesIO
from flask import Flask, jsonify, request
from pybaileys import WhatsApp, QRCodeHandler

app = Flask(__name__)
PORT = 3000

# ====== تخزين ======
qr_data = {}
status_data = {}
clients = {}

# ====== تشغيل واتساب ======
def start_whatsapp_client(user_id):
    """تشغيل عميل واتساب حقيقي"""
    try:
        # مجلد الجلسة
        session_dir = f"./wa_sessions/{user_id}"
        os.makedirs(session_dir, exist_ok=True)
        
        # إنشاء عميل واتساب
        client = WhatsApp(
            session_path=session_dir,
            auto_reconnect=True,
            print_qr=False
        )
        
        clients[user_id] = client
        status_data[user_id] = "connecting"
        
        # ====== حدث عند ظهور QR ======
        @client.on("qr")
        async def on_qr(qr_string):
            """استقبال QR حقيقي من واتساب"""
            print(f"[WhatsApp] QR received for {user_id}")
            
            # تحويل QR إلى صورة
            qr = qrcode.QRCode(box_size=10, border=4)
            qr.add_data(qr_string)  # البيانات الحقيقية من واتساب
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            qr_data[user_id] = f"data:image/png;base64,{img_str}"
            status_data[user_id] = "qr_ready"
            
            # حفظ في ملف
            with open(f"./wa_qr_{user_id}.json", "w") as f:
                json.dump({"qr": qr_data[user_id], "status": "qr_ready"}, f)
        
        # ====== حدث عند الاتصال ======
        @client.on("connected")
        async def on_connected():
            print(f"[WhatsApp] {user_id} connected successfully!")
            status_data[user_id] = "connected"
            qr_data.pop(user_id, None)
        
        # ====== حدث عند قطع الاتصال ======
        @client.on("disconnected")
        async def on_disconnected():
            print(f"[WhatsApp] {user_id} disconnected")
            status_data[user_id] = "disconnected"
        
        # تشغيل العميل
        asyncio.create_task(client.start())
        
        return True
    except Exception as e:
        print(f"[WhatsApp] Error: {e}")
        status_data[user_id] = "error"
        return False

# ====== Routes ======

@app.route('/start', methods=['POST'])
def start_session():
    try:
        data = request.get_json()
        user_id = data.get('userId', f"user_{int(time.time())}")
        
        if user_id in clients:
            return jsonify({"success": True, "userId": user_id, "status": status_data.get(user_id, "running")})
        
        # تشغيل العميل
        start_whatsapp_client(user_id)
        
        return jsonify({
            "success": True,
            "userId": user_id,
            "status": "connecting",
            "message": "WhatsApp client starting..."
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
        
        # جلب من الملف
        qr_file = f"./wa_qr_{user_id}.json"
        if os.path.exists(qr_file):
            with open(qr_file, "r") as f:
                data = json.load(f)
                if data.get("qr"):
                    qr_data[user_id] = data["qr"]
                    return jsonify({
                        "qr": data["qr"],
                        "status": "qr_ready"
                    })
        
        return jsonify({"status": "waiting"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/status/<user_id>')
def get_status(user_id):
    try:
        status = status_data.get(user_id, "waiting")
        return jsonify({"status": status})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "clients": len(clients),
        "platform": "pybaileys"
    })

if __name__ == "__main__":
    print(f"[WhatsApp] Server starting on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
