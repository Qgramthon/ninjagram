import asyncio
import os
import threading
import time
from functools import wraps
from typing import Dict, Optional

from flask import Flask, jsonify, request
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession

app = Flask(__name__)

# Global storage: phone or unique user_id -> client
active_clients: Dict[str, TelegramClient] = {}
# For pending login flows: phone -> (client, phone_code_hash)
pending_logins: Dict[str, tuple[TelegramClient, str]] = {}

# Environment variables or hardcoded (better from env in production)
API_ID = int(os.getenv('API_ID', 0))  # Set these in Railway dashboard
API_HASH = os.getenv('API_HASH', '')

if not API_ID or not API_HASH:
    raise ValueError("Set API_ID and API_HASH environment variables")

# Helper to run async functions from sync Flask routes
def async_route(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

# Background event loop thread for running clients
def run_client_background(client: TelegramClient):
    """Run a client's event loop in a background thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def run():
        try:
            await client.start()  # This connects and ensures authorized
            print(f"Client {client.session.save()} started and listening")
            await client.run_until_disconnected()
        except Exception as e:
            print(f"Client error: {e}")
        finally:
            await client.disconnect()
    
    loop.run_until_complete(run())

# Example command handler - customize as needed
async def setup_handlers(client: TelegramClient):
    @client.on(events.NewMessage(pattern='/ping'))
    async def ping_handler(event):
        await event.reply("Pong! UserBot is alive.")
    
    # Add more handlers here...
    # @client.on(events.NewMessage())
    # async def all_messages(event):
    #     ...

# ====================== ROUTES ======================

@app.route('/')
def home():
    return """
    <h1>Telegram UserBot Control Panel</h1>
    <form action="/api/send_code" method="post">
        <input type="text" name="phone" placeholder="+1234567890" required><br>
        <button type="submit">Send Code</button>
    </form>
    """

@app.route('/api/send_code', methods=['POST'])
@async_route
async def send_code():
    phone = request.form.get('phone') or request.json.get('phone')
    if not phone:
        return jsonify({"error": "Phone required"}), 400
    
    # Clean phone
    phone = ''.join(filter(str.isdigit, phone.replace('+', '')))
    if phone.startswith('0'):
        phone = '1' + phone[1:]  # or handle country code properly
    phone = '+' + phone if not phone.startswith('+') else phone  # rough

    try:
        # Create new client with StringSession for persistence
        session_name = f"user_{phone.replace('+', '')}"
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        
        await client.connect()
        
        if await client.is_user_authorized():
            # Already logged in - setup and start listening
            await setup_handlers(client)
            active_clients[phone] = client
            threading.Thread(target=run_client_background, args=(client,), daemon=True).start()
            return jsonify({"status": "already_authorized", "message": "Bot already active"})
        
        sent = await client.send_code_request(phone)
        pending_logins[phone] = (client, sent.phone_code_hash)
        
        return jsonify({
            "status": "code_sent",
            "message": "Verification code sent to Telegram app"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/verify', methods=['POST'])
@async_route
async def verify():
    phone = request.form.get('phone') or request.json.get('phone')
    code = request.form.get('code') or request.json.get('code')
    password = request.form.get('password') or request.json.get('password')  # 2FA if needed
    
    if not phone or not code:
        return jsonify({"error": "Phone and code required"}), 400
    
    if phone not in pending_logins:
        return jsonify({"error": "No pending login for this phone"}), 400
    
    client, phone_code_hash = pending_logins[phone]
    
    try:
        await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
    except SessionPasswordNeededError:
        if not password:
            return jsonify({"error": "2FA password required", "needs_password": True}), 401
        await client.sign_in(password=password)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
    # Login successful
    await setup_handlers(client)
    active_clients[phone] = client
    del pending_logins[phone]
    
    # Start background listener
    threading.Thread(target=run_client_background, args=(client,), daemon=True).start()
    
    # Optional: save string session for persistence across restarts
    session_str = client.session.save()
    print(f"Session saved for {phone}: {session_str[:50]}...")
    
    return jsonify({
        "status": "success",
        "message": "UserBot activated and listening for commands"
    })

@app.route('/api/status')
def status():
    return jsonify({
        "active_bots": list(active_clients.keys()),
        "pending_logins": list(pending_logins.keys())
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
else:
    # For Gunicorn
    # Start any pre-loaded clients if you persist sessions (advanced)
    pass
