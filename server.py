import threading
import asyncio
import uuid
import logging
import sys
import os
import signal
from flask import Flask, jsonify, request
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession
from shared import *

app = Flask(__name__)

# ------------------- موقع الويب (The Boys / Vought Masterpiece) -------------------
@app.route('/')
def home():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>VOUGHT TERMINAL · NinjaThon (The Boys Edition)</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@700;900&family=Rajdhani:wght@400;500;600;700&display=swap');
  
  :root {
    --bg-dark: #050505;
    --vought-blue: #0A192F;
    --laser-red: #E60000;
    --laser-glow: rgba(230, 0, 0, 0.7);
    --gold: #D4AF37;
    --glass-bg: rgba(15, 15, 18, 0.65);
    --glass-border: rgba(255, 255, 255, 0.08);
    --text-main: #FFFFFF;
    --text-dim: rgba(255, 255, 255, 0.5);
    --success: #00FF66;
  }

  *, *::before, *::after { margin:0; padding:0; box-sizing:border-box; }
  
  body {
    font-family: 'Rajdhani', sans-serif;
    background-color: var(--bg-dark);
    color: var(--text-main);
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow-x: hidden;
    position: relative;
  }

  /* Cinematic Background */
  body::before {
    content: '';
    position: fixed;
    top: 0; left: 0; width: 100vw; height: 100vh;
    background: radial-gradient(circle at 50% 0%, var(--vought-blue) 0%, var(--bg-dark) 60%);
    z-index: -2;
  }

  /* Homelander Laser Sweep Effect */
  .laser-sweep {
    position: fixed;
    top: 0; left: 0; width: 100vw; height: 2px;
    background: var(--laser-red);
    box-shadow: 0 0 20px 5px var(--laser-glow), 0 0 40px 10px var(--laser-glow);
    opacity: 0.1;
    z-index: -1;
    animation: laserScan 6s infinite ease-in-out;
  }

  .wrap {
    width: 100%;
    max-width: 480px;
    padding: 20px;
    position: relative;
    z-index: 1;
    perspective: 1000px;
  }

  /* Glassmorphism Card Masterpiece */
  .card {
    background: var(--glass-bg);
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    border: 1px solid var(--glass-border);
    border-top: 1px solid rgba(230, 0, 0, 0.3);
    border-radius: 24px;
    padding: 40px 30px;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.8), 
                inset 0 1px 0 rgba(255, 255, 255, 0.1),
                0 0 30px rgba(230, 0, 0, 0.05);
    animation: floatIn 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    transform-style: preserve-3d;
    transition: box-shadow 0.4s ease, transform 0.4s ease;
  }

  .card:hover {
    box-shadow: 0 30px 60px -10px rgba(0, 0, 0, 0.9), 
                inset 0 1px 0 rgba(255, 255, 255, 0.15),
                0 0 40px rgba(230, 0, 0, 0.15);
  }

  /* Header Branding */
  .hd {
    text-align: center;
    margin-bottom: 35px;
    position: relative;
  }

  .hd h1 {
    font-family: 'Cinzel', serif;
    font-size: 38px;
    font-weight: 900;
    letter-spacing: 4px;
    background: linear-gradient(180deg, #FFFFFF 0%, var(--laser-red) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-shadow: 0 0 30px rgba(230, 0, 0, 0.4);
    text-transform: uppercase;
    margin-bottom: 5px;
  }

  .hd p {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-dim);
    letter-spacing: 6px;
    text-transform: uppercase;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
  }

  .hd p::before, .hd p::after {
    content: '';
    height: 1px;
    width: 30px;
    background: var(--laser-red);
    opacity: 0.5;
  }

  /* Progress/Step Indicators */
  .step-label {
    display: flex;
    align-items: center;
    gap: 15px;
    margin-bottom: 25px;
  }

  .step-dot {
    width: 36px; height: 36px;
    border-radius: 50%;
    background: rgba(230, 0, 0, 0.1);
    border: 1px solid var(--laser-red);
    display: flex; align-items: center; justify-content: center;
    font-size: 16px; font-weight: 700; color: var(--laser-red);
    box-shadow: 0 0 15px rgba(230, 0, 0, 0.3);
    text-shadow: 0 0 5px var(--laser-red);
  }

  .step-text {
    font-size: 18px; font-weight: 600; color: var(--text-main);
    letter-spacing: 2px; text-transform: uppercase;
  }

  /* Form Fields */
  .field {
    position: relative;
    margin-bottom: 20px;
  }

  .field label {
    position: absolute;
    top: 50%; left: 16px;
    transform: translateY(-50%);
    font-size: 15px; font-weight: 500; color: var(--text-dim);
    transition: all 0.3s ease;
    pointer-events: none;
    letter-spacing: 1px;
  }

  .field input {
    width: 100%;
    padding: 24px 45px 10px 16px;
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    color: var(--text-main);
    font-size: 16px; font-weight: 600; font-family: inherit;
    outline: none;
    transition: all 0.3s ease;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.5);
  }

  .field input:focus, .field input:not(:placeholder-shown) {
    border-color: var(--laser-red);
    background: rgba(230, 0, 0, 0.03);
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.5), 0 0 15px rgba(230, 0, 0, 0.15);
  }

  .field input:focus + label, .field input:not(:placeholder-shown) + label {
    top: 12px;
    font-size: 11px;
    color: var(--laser-red);
    font-weight: 700;
  }

  /* Eye Toggle */
  .toggle-vis {
    position: absolute; right: 16px; top: 50%; transform: translateY(-50%);
    background: none; border: none; cursor: pointer; z-index: 2;
    color: var(--text-dim); transition: color 0.3s ease;
  }
  .toggle-vis:hover { color: var(--laser-red); }
  .toggle-vis svg { width: 20px; height: 20px; fill: currentColor; }

  #code {
    text-align: center; font-size: 32px; font-weight: 700; letter-spacing: 15px;
    padding: 20px;
  }

  /* Epic Buttons */
  .btn {
    width: 100%; padding: 18px;
    border: none; border-radius: 12px;
    font-size: 18px; font-weight: 700; font-family: 'Rajdhani', sans-serif;
    letter-spacing: 3px; text-transform: uppercase;
    cursor: pointer; position: relative; overflow: hidden;
    transition: all 0.3s ease; margin-top: 10px;
    display: flex; align-items: center; justify-content: center;
    z-index: 1;
  }

  .btn-homelander {
    background: linear-gradient(90deg, #8B0000 0%, var(--laser-red) 50%, #8B0000 100%);
    background-size: 200% auto;
    color: #fff;
    box-shadow: 0 10px 25px rgba(230, 0, 0, 0.4);
    border: 1px solid rgba(255, 100, 100, 0.3);
  }

  .btn-homelander:hover {
    background-position: right center;
    box-shadow: 0 15px 35px rgba(230, 0, 0, 0.6);
    transform: translateY(-2px);
  }

  .btn-gold {
    background: linear-gradient(90deg, #B8960F 0%, var(--gold) 50%, #B8960F 100%);
    background-size: 200% auto;
    color: #000;
    box-shadow: 0 10px 25px rgba(212, 175, 55, 0.3);
    border: 1px solid rgba(255, 255, 255, 0.4);
  }

  .btn-gold:hover {
    background-position: right center;
    box-shadow: 0 15px 35px rgba(212, 175, 55, 0.5);
    transform: translateY(-2px);
  }

  .btn:active { transform: scale(0.98); }

  /* Loading State */
  .btn .prog-bar {
    position: absolute; bottom: 0; left: 0; height: 4px;
    background: #fff; width: 0%; box-shadow: 0 0 10px #fff;
    transition: width 0.05s linear; z-index: -1;
  }

  .btn.loading { pointer-events: none; color: transparent; }
  .btn.loading::before {
    content: ''; position: absolute; width: 24px; height: 24px;
    border: 3px solid rgba(255,255,255,0.3); border-top-color: #fff;
    border-radius: 50%; animation: spin 0.8s cubic-bezier(0.5, 0, 0.5, 1) infinite;
  }

  /* Back Button */
  .back-btn {
    position: absolute; top: -50px; left: 0;
    display: inline-flex; align-items: center; gap: 8px;
    background: none; border: none; color: var(--text-dim);
    font-size: 15px; font-weight: 600; font-family: inherit;
    cursor: pointer; transition: all 0.3s ease; text-transform: uppercase; letter-spacing: 1px;
  }
  .back-btn:hover { color: var(--laser-red); transform: translateX(-5px); }
  .back-btn svg { width: 18px; height: 18px; fill: currentColor; }

  /* Result Box */
  .result {
    display: none; margin-top: 25px; padding: 16px; border-radius: 12px;
    font-size: 15px; font-weight: 600; text-align: center; letter-spacing: 1px;
    animation: fadeUp 0.4s ease forwards;
    backdrop-filter: blur(10px);
  }
  .result.show { display: block; }
  .result.ok  { background: rgba(0, 255, 102, 0.1); border: 1px solid rgba(0, 255, 102, 0.3); color: var(--success); text-shadow: 0 0 10px rgba(0,255,102,0.4); }
  .result.err { background: rgba(230, 0, 0, 0.1); border: 1px solid rgba(230, 0, 0, 0.3); color: var(--laser-red); text-shadow: 0 0 10px rgba(230,0,0,0.4); }

  /* Info Footer */
  .info-footer {
    margin-top: 20px; text-align: center; z-index: 1;
    animation: floatIn 1s 0.2s ease forwards; opacity: 0;
  }
  .info-footer a {
    color: var(--text-dim); text-decoration: none; font-size: 13px; font-weight: 500;
    letter-spacing: 1px; transition: color 0.3s ease; border-bottom: 1px solid transparent;
  }
  .info-footer a:hover { color: var(--gold); border-bottom-color: var(--gold); }

  /* Utilities */
  .hidden { display: none !important; }
  .rel { position: relative; }

  /* Animations */
  @keyframes floatIn {
    0% { opacity: 0; transform: translateY(40px) scale(0.95); }
    100% { opacity: 1; transform: translateY(0) scale(1); }
  }
  @keyframes fadeUp {
    0% { opacity: 0; transform: translateY(15px); }
    100% { opacity: 1; transform: translateY(0); }
  }
  @keyframes spin { 100% { transform: rotate(360deg); } }
  @keyframes laserScan {
    0% { top: -10%; opacity: 0; }
    10% { opacity: 0.5; }
    50% { top: 110%; opacity: 0.1; }
    100% { top: 110%; opacity: 0; }
  }

  @media (max-width: 480px) {
    .card { padding: 30px 20px; }
    .hd h1 { font-size: 30px; }
    #code { font-size: 26px; letter-spacing: 10px; }
  }
</style>
</head>
<body>
<div class="laser-sweep"></div>

<div class="wrap">
  <div class="card">
    <div class="hd">
      <h1>NINJATHON</h1>
      <p>Vought Terminal</p>
    </div>

    <!-- STEP 1 -->
    <div id="step1">
      <div class="step-label">
        <div class="step-dot">I</div>
        <span class="step-text">Clearance Data</span>
      </div>

      <div class="field">
        <input id="api_id" type="password" placeholder=" " inputmode="numeric" autocomplete="off">
        <label>API ID</label>
        <button class="toggle-vis" onclick="toggleVisibility('api_id')" tabindex="-1">
          <svg viewBox="0 0 24 24"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg>
        </button>
      </div>

      <div class="field">
        <input id="api_hash" type="password" placeholder=" " autocomplete="off">
        <label>API HASH</label>
        <button class="toggle-vis" onclick="toggleVisibility('api_hash')" tabindex="-1">
          <svg viewBox="0 0 24 24"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg>
        </button>
      </div>

      <div class="field">
        <input id="phone" type="password" placeholder=" " inputmode="tel" autocomplete="off">
        <label>PHONE NUMBER (EX: +20...)</label>
        <button class="toggle-vis" onclick="toggleVisibility('phone')" tabindex="-1">
          <svg viewBox="0 0 24 24"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg>
        </button>
      </div>

      <button class="btn btn-homelander" id="sendBtn" onclick="sendCode()">
        Initiate Link
        <div class="prog-bar" id="prog1"></div>
      </button>
    </div>

    <!-- STEP 2 -->
    <div id="step2" class="hidden rel">
      <button class="back-btn" onclick="backToStep1()">
        <svg viewBox="0 0 24 24"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/></svg>
        Abort
      </button>

      <div class="step-label">
        <div class="step-dot">II</div>
        <span class="step-text">Override Code</span>
      </div>

      <div class="field">
        <input id="code" type="password" placeholder=" " maxlength="5" inputmode="numeric" autocomplete="one-time-code">
        <label style="left:50%; transform:translate(-50%, -50%); text-align:center; width:100%;">TELEGRAM CODE</label>
        <button class="toggle-vis" onclick="toggleVisibility('code')" tabindex="-1">
          <svg viewBox="0 0 24 24"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg>
        </button>
      </div>

      <div class="field">
        <input id="password" type="password" placeholder=" " autocomplete="current-password">
        <label>2FA PASSWORD (IF ANY)</label>
        <button class="toggle-vis" onclick="toggleVisibility('password')" tabindex="-1">
          <svg viewBox="0 0 24 24"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg>
        </button>
      </div>

      <button class="btn btn-gold" id="verifyBtn" onclick="verify()">
        Deploy Compound V
        <div class="prog-bar" id="prog2"></div>
      </button>
    </div>

    <!-- Result Notification -->
    <div class="result" id="result"></div>
  </div>

  <div class="info-footer">
    <a href="https://my.telegram.org/apps" target="_blank">OBTAIN VOUGHT CREDENTIALS (MY.TELEGRAM.ORG)</a>
  </div>
</div>

<script>
const $ = id => document.getElementById(id);
let currentPhone = '';

function showResult(msg, ok) {
  const r = $('result');
  r.className = 'result show ' + (ok ? 'ok' : 'err');
  r.textContent = msg;
}

function toggleVisibility(fieldId) {
  const input = $(fieldId);
  input.type = input.type === 'password' ? 'text' : 'password';
}

function runProgress(barId, duration, onDone) {
  const bar = $(barId);
  let w = 0;
  const step = 100 / (duration / 50);
  bar.style.width = '0%';
  const iv = setInterval(() => {
    w = Math.min(w + step + Math.random() * step * 0.5, 95);
    bar.style.width = w + '%';
    if (w >= 95) clearInterval(iv);
  }, 50);
  return { finish: () => {
    clearInterval(iv);
    bar.style.transition = 'width .4s cubic-bezier(0.16, 1, 0.3, 1)';
    bar.style.width = '100%';
    setTimeout(() => { bar.style.width = '0%'; bar.style.transition = 'none'; if(onDone) onDone(); }, 400);
  }};
}

async function sendCode() {
  const api_id = $('api_id').value.trim();
  const api_hash = $('api_hash').value.trim();
  const phone = $('phone').value.trim();
  if (!api_id || !api_hash || !phone) { showResult('ACCESS DENIED: Missing Credentials.', false); return; }
  
  const btn = $('sendBtn');
  btn.classList.add('loading');
  const prog = runProgress('prog1', 4000);
  
  try {
    const fd = new FormData();
    fd.append('api_id', api_id);
    fd.append('api_hash', api_hash);
    fd.append('phone', phone);
    const res = await fetch('/api/send_code', { method:'POST', body:fd });
    const data = await res.json();
    prog.finish();
    
    if (data.status === 'code_sent' || data.status === 'already_active') {
      currentPhone = phone;
      if (data.status === 'code_sent') {
        $('step1').classList.add('hidden');
        $('step2').classList.remove('hidden');
        $('code').focus();
        showResult('LINK ESTABLISHED. Awaiting Override Code.', true);
      } else {
        showResult('SESSION ACTIVE. You have full control.', true);
      }
    } else {
      showResult(data.message || 'SYSTEM ERROR', false);
    }
  } catch(e) {
    prog.finish();
    showResult('NETWORK FAILURE. Retrying...', false);
  } finally {
    btn.classList.remove('loading');
  }
}

async function verify() {
  const code = $('code').value.trim();
  const password = $('password').value;
  if (!code) { showResult('CODE REQUIRED FOR OVERRIDE.', false); return; }
  
  const btn = $('verifyBtn');
  btn.classList.add('loading');
  const prog = runProgress('prog2', 5000);
  
  try {
    const fd = new FormData();
    fd.append('phone', currentPhone);
    fd.append('code', code);
    fd.append('password', password);
    const res = await fetch('/api/verify', { method:'POST', body:fd });
    const data = await res.json();
    prog.finish();
    
    if (data.status === 'success') {
      showResult('COMPOUND V DEPLOYED. Welcome to The Seven.', true);
      setTimeout(() => { location.reload(); }, 3000);
    } else {
      showResult(data.message || 'AUTHORIZATION FAILED', false);
    }
  } catch(e) {
    prog.finish();
    showResult('CONNECTION LOST. Stand by.', false);
  } finally {
    btn.classList.remove('loading');
  }
}

function backToStep1() {
  $('step2').classList.add('hidden');
  $('step1').classList.remove('hidden');
  $('result').className = 'result';
}

document.addEventListener('keydown', e => {
  if (e.key !== 'Enter') return;
  if (!$('step2').classList.contains('hidden')) verify();
  else if (!$('step1').classList.contains('hidden')) sendCode();
});
</script>
</body>
</html>"""

# ------------------- Health Check -------------------
@app.route('/health')
def health():
    return jsonify({"status": "ok", "clients": len(active_clients)}), 200

# ------------------- API: Send Code -------------------
@app.route('/api/send_code', methods=['POST'])
def api_send_code():
    try:
        api_id = int(request.form.get('api_id'))
        api_hash = request.form.get('api_hash')
        phone = request.form.get('phone', '').strip()
        if not api_id or not api_hash or not phone:
            return jsonify({"status": "error", "message": "All fields required"}), 400

        async def _send():
            api_configs_storage[phone] = {'api_id': api_id, 'api_hash': api_hash}
            save_config(phone, api_id, api_hash)
            client = TelegramClient(StringSession(), api_id, api_hash)
            await client.connect()
            if await client.is_user_authorized():
                active_clients[phone] = client
                client_me[phone] = await client.get_me()
                start_client_in_background(client, phone)
                await save_all_sessions()
                return jsonify({"status": "already_active", "message": "Session already active"})
            sent = await client.send_code_request(phone)
            pending_logins[phone] = (client, sent.phone_code_hash, api_id, api_hash)
            return jsonify({"status": "code_sent", "message": "Verification code sent"})
        return run_in_main(_send())
    except Exception as e:
        logger.error(f"Error sending code: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ------------------- API: Verify Code -------------------
@app.route('/api/verify', methods=['POST'])
def api_verify():
    phone = request.form.get('phone', '').strip()
    code = request.form.get('code', '').strip()
    password = request.form.get('password')
    if not phone or not code or phone not in pending_logins:
        return jsonify({"status": "error", "message": "Invalid session"}), 400

    async def _verify():
        client, phone_code_hash, api_id, api_hash = pending_logins[phone]
        try:
            try:
                await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                if not password:
                    return jsonify({"status": "error", "message": "2FA password required"}), 401
                await client.sign_in(password=password)
            active_clients[phone] = client
            client_me[phone] = await client.get_me()
            del pending_logins[phone]
            await save_all_sessions()
            start_client_in_background(client, phone)
            await notify_dev(f"New user activated: {phone}")
            return jsonify({"status": "success", "message": "NinjaThon installed successfully"})
        except Exception as e:
            logger.error(f"Verification error: {e}")
            return jsonify({"status": "error", "message": str(e)}), 400
    return run_in_main(_verify())

# ------------------- Helper -------------------
def run_in_main(coro):
    from shared import main_loop
    future = asyncio.run_coroutine_threadsafe(coro, main_loop)
    return future.result(timeout=60)

# ------------------- Startup -------------------
def start_background_loop():
    """Start the asyncio event loop in a background thread"""
    asyncio.set_event_loop(main_loop)
    main_loop.create_task(periodic_save())
    main_loop.create_task(cleanup_expired())
    main_loop.run_forever()

if __name__ == '__main__':
    threading.Thread(target=start_background_loop, daemon=True).start()
    
    future = asyncio.run_coroutine_threadsafe(load_and_start_all_sessions(), main_loop)
    try:
        future.result(timeout=30)
    except Exception as e:
        logger.error(f"Failed to load sessions: {e}")
    
    def handle_shutdown(signum, frame):
        logger.info("Received shutdown signal")
        asyncio.run_coroutine_threadsafe(shutdown(), main_loop).result(timeout=10)
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)
    
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"NinjaThon server starting on port {port}")
    app.run(host='0.0.0.0', port=port)
