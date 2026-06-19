import asyncio
import threading
import logging
import time
import json
import os
import sys
import uuid
from flask import Flask, request, jsonify

from telethon import TelegramClient, events, Button
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.sessions import StringSession

# ======================== الإعدادات ========================
BOT_TOKEN = '8887748662:AAFgLMUO2eXpYzityDj35-IDTLywtdO8S8Q'
BOT_API_ID = 2040
BOT_API_HASH = 'b18441a1ff607e10a989891a5462e627'

DATA_DIR = '/data' if os.path.exists('/data') else '.'
os.makedirs(DATA_DIR, exist_ok=True)
SESSION_FILE = os.path.join(DATA_DIR, 'active_sessions.json')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

app = Flask(__name__)

# المتغيرات
active_clients = {}
pending_web = {}  # {token: {'api_id', 'api_hash', 'phone', 'client', 'hash'}}

# ======================== صفحة الويب ========================
HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rolex Setup</title>
    <style>
        body { font-family: sans-serif; background: #0A0A19; color: #fff; padding: 20px; }
        .card { background: rgba(255,255,255,0.05); border-radius: 16px; padding: 20px; max-width: 400px; margin: auto; }
        input { width: 100%; padding: 12px; margin: 8px 0; border-radius: 8px; border: 1px solid rgba(255,255,255,0.2); background: rgba(255,255,255,0.05); color: #fff; font-size: 16px; box-sizing: border-box; }
        button { width: 100%; padding: 14px; margin: 12px 0; border-radius: 8px; border: none; background: #4F6EF7; color: #fff; font-size: 16px; cursor: pointer; }
        .status { padding: 10px; margin: 10px 0; border-radius: 8px; text-align: center; display: none; }
        .error { background: rgba(255,0,0,0.2); }
        .success { background: rgba(0,255,0,0.2); }
    </style>
</head>
<body>
    <div class="card">
        <h2 style="text-align:center;">Rolex Telethon Setup</h2>
        <div id="step1">
            <input type="number" id="api_id" placeholder="API ID">
            <input type="text" id="api_hash" placeholder="API Hash">
            <input type="text" id="phone" placeholder="Phone: +201234567890">
            <button onclick="sendCode()">Send Code</button>
        </div>
        <div id="step2" style="display:none;">
            <input type="text" id="code" placeholder="Verification Code">
            <input type="password" id="password" placeholder="2FA Password (optional)">
            <button onclick="verifyCode()">Verify</button>
        </div>
        <div id="status" class="status"></div>
    </div>
    <script>
        let token = null;
        function show(msg, cls) {
            const s = document.getElementById('status');
            s.textContent = msg; s.className = 'status ' + cls; s.style.display = 'block';
        }
        async function sendCode() {
            const api_id = document.getElementById('api_id').value;
            const api_hash = document.getElementById('api_hash').value;
            const phone = document.getElementById('phone').value;
            show('Sending...', '');
            const res = await fetch('/send_code', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({api_id: parseInt(api_id), api_hash, phone})
            });
            const data = await res.json();
            if (data.status === 'ok') {
                token = data.token;
                document.getElementById('step1').style.display = 'none';
                document.getElementById('step2').style.display = 'block';
                show('Code sent! Check your Telegram.', 'success');
            } else {
                show(data.message || 'Error', 'error');
            }
        }
        async function verifyCode() {
            const code = document.getElementById('code').value;
            const password = document.getElementById('password').value;
            show('Verifying...', '');
            const res = await fetch('/verify_code', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({token, code, password})
            });
            const data = await res.json();
            if (data.status === 'ok') {
                show('Setup Complete! Return to bot and send /done', 'success');
                document.getElementById('step2').style.display = 'none';
            } else if (data.status === '2fa') {
                show('Enter 2FA password', 'error');
            } else {
                show(data.message || 'Error', 'error');
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return HTML

@app.route('/send_code', methods=['POST'])
def send_code():
    try:
        data = request.json
        api_id = data['api_id']
        api_hash = data['api_hash']
        phone = data['phone']
        
        async def _send():
            client = TelegramClient(StringSession(), api_id, api_hash)
            await client.connect()
            result = await client.send_code_request(phone)
            return client, result.phone_code_hash
        
        loop = asyncio.new_event_loop()
        client, phone_code_hash = loop.run_until_complete(_send())
        
        token = uuid.uuid4().hex
        pending_web[token] = {
            'api_id': api_id,
            'api_hash': api_hash,
            'phone': phone,
            'client': client,
            'hash': phone_code_hash
        }
        
        return jsonify({'status': 'ok', 'token': token})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/verify_code', methods=['POST'])
def verify_code():
    try:
        data = request.json
        token = data['token']
        code = data['code']
        password = data.get('password', '')
        
        if token not in pending_web:
            return jsonify({'status': 'error', 'message': 'Session expired'})
        
        info = pending_web[token]
        
        async def _verify():
            client = info['client']
            if not client.is_connected():
                await client.connect()
            try:
                await client.sign_in(phone=info['phone'], code=code, phone_code_hash=info['hash'])
            except SessionPasswordNeededError:
                if password:
                    await client.sign_in(password=password)
                else:
                    raise
            return client
        
        loop = asyncio.new_event_loop()
        client = loop.run_until_complete(_verify())
        
        session_str = client.session.save()
        phone = info['phone']
        api_id = info['api_id']
        api_hash = info['api_hash']
        
        # حفظ الجلسة
        sessions = {}
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, 'r') as f:
                sessions = json.load(f)
        sessions[phone] = {'session': session_str, 'api_id': api_id, 'api_hash': api_hash}
        with open(SESSION_FILE, 'w') as f:
            json.dump(sessions, f)
        
        del pending_web[token]
        return jsonify({'status': 'ok'})
    except SessionPasswordNeededError:
        return jsonify({'status': '2fa', 'message': 'Enter 2FA password'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# ======================== البوت ========================
bot = TelegramClient(f'bot_session_{uuid.uuid4().hex[:6]}', BOT_API_ID, BOT_API_HASH)

def get_webapp_url():
    domain = os.environ.get('RAILWAY_PUBLIC_DOMAIN', 'http://localhost:5000')
    return domain

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    url = get_webapp_url()
    buttons = [
        [Button.url("OPEN SETUP PAGE", url)]
    ]
    await event.respond(
        "**Rolex Telethon Setup**\n\n"
        "Press the button to open the setup page.\n"
        "After completing setup, come back here and send `/done` to check.",
        buttons=buttons,
        parse_mode='md'
    )

@bot.on(events.NewMessage(pattern='/done'))
async def done(event):
    await event.respond("Setup complete! Your account is now active.")

async def main():
    flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False), daemon=True)
    flask_thread.start()
    logger.info("Flask started")
    
    await bot.start(bot_token=BOT_TOKEN)
    logger.info("Bot started")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
