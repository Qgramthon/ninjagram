import asyncio
import os
import threading
from functools import wraps
from typing import Dict, Optional

from flask import Flask, jsonify, request, render_template_string
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession

app = Flask(__name__)

# Load from environment variables (Railway)
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')

if not API_ID or not API_HASH:
    raise ValueError("API_ID and API_HASH must be set as environment variables in Railway")

API_ID = int(API_ID)

# Storage
active_clients: Dict[str, TelegramClient] = {}
pending_logins: Dict[str, tuple[TelegramClient, str]] = {}

# Helper to run async code from Flask
def async_route(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

def run_client_background(client: TelegramClient, phone: str):
    """Run Telethon client in background thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def runner():
        try:
            await client.start()
            print(f"✅ UserBot started for {phone}")
            await client.run_until_disconnected()
        except Exception as e:
            print(f"❌ Client error for {phone}: {e}")
        finally:
            try:
                await client.disconnect()
            except:
                pass

    loop.run_until_complete(runner())

async def setup_handlers(client: TelegramClient):
    """Define your command handlers here"""
    @client.on(events.NewMessage(pattern='/ping'))
    async def ping(event):
        await event.reply("Pong! UserBot is running.")

    # Add more handlers as needed
    # @client.on(events.NewMessage())
    # async def handler(event):
    #     ...

# ====================== WEB ROUTES ======================

@app.route('/')
def home():
    html = """
    <h1>Telegram UserBot</h1>
    <form action="/api/send_code" method="post">
        <label>Phone number:</label><br>
        <input type="text" name="phone" placeholder="+1234567890" required><br><br>
        <button type="submit">Send Verification Code</button>
    </form>
    <hr>
    <a href="/api/status">Check Status</a>
    """
    return html

@app.route('/api/send_code', methods=['POST'])
@async_route
async def send_code():
    phone = (request.form.get('phone') or request.json.get('phone') or '').strip()
    if not phone:
        return jsonify({"error": "Phone number is required"}), 400

    try:
        session = StringSession()  # In-memory for now
        client = TelegramClient(session, API_ID, API_HASH)

        await client.connect()

        if await client.is_user_authorized():
            await setup_handlers(client)
            active_clients[phone] = client
            threading.Thread(target=run_client_background, args=(client, phone), daemon=True).start()
            return jsonify({"status": "already_active", "message": "Bot already logged in"})

        sent = await client.send_code_request(phone)
        pending_logins[phone] = (client, sent.phone_code_hash)

        return jsonify({
            "status": "code_sent",
            "message": "Verification code sent to your Telegram app"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/verify', methods=['POST'])
@async_route
async def verify():
    phone = (request.form.get('phone') or request.json.get('phone') or '').strip()
    code = (request.form.get('code') or request.json.get('code') or '').strip()
    password = request.form.get('password') or request.json.get('password')

    if not phone or not code:
        return jsonify({"error": "Phone and code are required"}), 400
    if phone not in pending_logins:
        return jsonify({"error": "No pending login found for this phone"}), 400

    client, phone_code_hash = pending_logins[phone]

    try:
        await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
    except SessionPasswordNeededError:
        if not password:
            return jsonify({"error": "Two-factor authentication password required", "needs_2fa": True}), 401
        await client.sign_in(password=password)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    # Success
    await setup_handlers(client)
    active_clients[phone] = client
    del pending_logins[phone]

    threading.Thread(target=run_client_background, args=(client, phone), daemon=True).start()

    session_str = client.session.save()
    print(f"Session string for {phone}:\n{session_str}")

    return jsonify({
        "status": "success",
        "message": "UserBot successfully activated and listening"
    })


@app.route('/api/status')
def status():
    return jsonify({
        "active_bots": list(active_clients.keys()),
        "pending_logins": list(pending_logins.keys())
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
