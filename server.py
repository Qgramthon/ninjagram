import asyncio
import os
import threading
from functools import wraps
from typing import Dict, Tuple

from flask import Flask, jsonify, request, render_template_string
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession

app = Flask(__name__)

# تخزين العملاء
active_clients: Dict[str, TelegramClient] = {}
pending_logins: Dict[str, Tuple[TelegramClient, str, int, str]] = {}  # (client, phone_code_hash, api_id, api_hash)

def async_route(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

def run_client_background(client: TelegramClient, identifier: str):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def runner():
        try:
            await client.start()
            print(f"✅ UserBot Started: {identifier}")
            await client.run_until_disconnected()
        except Exception as e:
            print(f"❌ Error {identifier}: {e}")
        finally:
            await client.disconnect()

    loop.run_until_complete(runner())

async def setup_handlers(client: TelegramClient):
    @client.on(events.NewMessage(pattern='/ping'))
    async def ping(event):
        await event.reply("Pong! البوت شغال يا صاحبي ⚡")

    # أضف handlers الخاصة بك هنا


@app.route('/')
def home():
    html = """
    <h1>Telegram UserBot - qgram-bot</h1>
    <form action="/api/send_code" method="post">
        <label>API ID:</label><br>
        <input type="text" name="api_id" placeholder="12345678" required><br><br>
        
        <label>API HASH:</label><br>
        <input type="text" name="api_hash" placeholder="0123456789abcdef..." required><br><br>
        
        <label>رقم الهاتف:</label><br>
        <input type="text" name="phone" placeholder="+201234567890" required><br><br>
        
        <button type="submit">إرسال كود التحقق</button>
    </form>
    <hr>
    <a href="/api/status">حالة البوتات النشطة</a>
    """
    return html


@app.route('/api/send_code', methods=['POST'])
@async_route
async def send_code():
    api_id = request.form.get('api_id')
    api_hash = request.form.get('api_hash')
    phone = request.form.get('phone', '').strip()

    if not api_id or not api_hash or not phone:
        return jsonify({"error": "يجب إدخال API_ID و API_HASH و رقم الهاتف"}), 400

    try:
        api_id = int(api_id)
        client = TelegramClient(StringSession(), api_id, api_hash)

        await client.connect()

        if await client.is_user_authorized():
            await setup_handlers(client)
            active_clients[phone] = client
            threading.Thread(target=run_client_background, args=(client, phone), daemon=True).start()
            return jsonify({"status": "already_active"})

        sent = await client.send_code_request(phone)
        pending_logins[phone] = (client, sent.phone_code_hash, api_id, api_hash)

        return jsonify({"status": "code_sent", "message": "تم إرسال كود التحقق"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/verify', methods=['POST'])
@async_route
async def verify():
    phone = request.form.get('phone', '').strip()
    code = request.form.get('code', '').strip()
    password = request.form.get('password')

    if not phone or not code or phone not in pending_logins:
        return jsonify({"error": "بيانات غير صحيحة"}), 400

    client, phone_code_hash, _, _ = pending_logins[phone]

    try:
        await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
    except SessionPasswordNeededError:
        if not password:
            return jsonify({"error": "كلمة مرور التحقق بخطوتين مطلوبة", "needs_2fa": True}), 401
        await client.sign_in(password=password)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    await setup_handlers(client)
    active_clients[phone] = client
    del pending_logins[phone]

    threading.Thread(target=run_client_background, args=(client, phone), daemon=True).start()

    return jsonify({"status": "success", "message": "تم تفعيل اليوزربوت بنجاح"})


@app.route('/api/status')
def status():
    return jsonify({
        "active": list(active_clients.keys()),
        "pending": list(pending_logins.keys())
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
