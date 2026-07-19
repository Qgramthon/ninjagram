import asyncio
import json
import os
import time
import threading
from flask import Flask, jsonify, request
import qrcode
from io import BytesIO
import base64
import random

app = Flask(__name__)
USER_ID = "test_user"

@app.route('/start', methods=['POST'])
def start_session():
    return jsonify({"status": "qr_ready", "userId": USER_ID})

@app.route('/qr/<user_id>')
def get_qr(user_id):
    # إنشاء QR وهمي للاختبار
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(f"whatsapp://connect?user={user_id}")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return jsonify({
        "qr": f"data:image/png;base64,{img_str}",
        "status": "qr_ready"
    })

@app.route('/status/<user_id>')
def get_status(user_id):
    return jsonify({"status": "waiting"})

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port, debug=False)
