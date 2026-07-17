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

# ------------------- الواجهة (The Boys Edition) -------------------
@app.route('/')
def home():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>ACCESS PORTAL · THE BOYS</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700;800&family=Inter:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@500;600&display=swap');

  :root {
    --bg:#0A0D12; --surface:#0D1118; --card:#111621;
    --border:rgba(198,163,90,0.14); --border-hi:rgba(198,163,90,0.35);
    --red:#9E2A2B; --red-dark:#5C1518; --gold:#C6A35A;
    --text:#EDEFF2; --text2:rgba(237,239,242,0.62); --text3:rgba(237,239,242,0.36);
    --success:#3FA65B; --danger:#C1443B;
    --r:12px; --r2:20px;
  }
  *, *::before, *::after { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family:'Inter',-apple-system,BlinkMacSystemFont,system-ui,sans-serif;
    background:var(--bg); color:var(--text); min-height:100vh;
    display:flex; align-items:center; justify-content:center;
    padding:20px 16px 40px; -webkit-font-smoothing:antialiased; overflow-x:hidden;
  }
  /* subtle vignette + hairline grid, no neon glow */
  body::before {
    content:''; position:fixed; inset:0; pointer-events:none; z-index:0;
    background:
      radial-gradient(ellipse 70% 40% at 50% -5%, rgba(158,42,43,0.10) 0%, transparent 55%),
      radial-gradient(ellipse 60% 50% at 50% 110%, rgba(198,163,90,0.05) 0%, transparent 60%);
  }
  body::after {
    content:''; position:fixed; inset:0; pointer-events:none; z-index:0; opacity:.4;
    background-image: linear-gradient(rgba(255,255,255,0.015) 1px, transparent 1px);
    background-size: 100% 3px;
  }
  .wrap { position:relative; z-index:1; width:100%; max-width:420px; display:flex; flex-direction:column; gap:18px; }

  .hd { text-align:center; padding:6px 0 2px; }
  .seal {
    width:64px; height:64px; margin:0 auto 18px; position:relative;
    border-radius:50%; border:1.5px solid var(--gold);
    display:flex; align-items:center; justify-content:center;
    background:radial-gradient(circle at 50% 35%, #171B22 0%, #0D1118 100%);
    animation:sealIn .6s cubic-bezier(.2,.8,.3,1) both;
  }
  .seal::before {
    content:''; position:absolute; inset:-6px; border-radius:50%;
    border:1px solid rgba(198,163,90,0.25);
  }
  .seal svg { width:28px; height:28px; }
  .eyebrow {
    font-family:'IBM Plex Mono',monospace; font-size:10.5px; font-weight:600;
    letter-spacing:3px; color:var(--gold); text-transform:uppercase;
    animation:fadeUp .5s .05s ease both; margin-bottom:10px;
  }
  .hd h1 {
    font-family:'Barlow Condensed',sans-serif; font-size:42px; font-weight:800;
    letter-spacing:2px; text-transform:uppercase; color:var(--text);
    animation:fadeUp .5s .12s ease both; line-height:1;
  }
  .hd h1 span { color:var(--red); }
  .hd .rule {
    width:46px; height:2px; background:var(--gold); margin:14px auto 12px;
    animation:widthIn .6s .3s cubic-bezier(.2,.8,.3,1) both;
  }
  .hd p {
    font-size:12.5px; color:var(--text3); letter-spacing:.4px;
    animation:fadeUp .5s .2s ease both;
  }

  .card {
    background:var(--card); border:1px solid var(--border); border-radius:var(--r2);
    padding:26px 22px; box-shadow:0 24px 60px rgba(0,0,0,0.55);
    animation:fadeUp .5s .18s ease both; transition:border-color .3s;
    position:relative;
  }
  .card:hover { border-color:var(--border-hi); }

  .step-label { display:flex; align-items:center; gap:10px; margin-bottom:20px; }
  .step-dot {
    width:24px; height:24px; border-radius:6px; background:var(--red);
    display:flex; align-items:center; justify-content:center;
    font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:600; color:#fff;
    flex-shrink:0;
  }
  .step-text {
    font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:600;
    color:var(--text2); text-transform:uppercase; letter-spacing:1.5px;
  }

  .back-btn {
    display:inline-flex; align-items:center; gap:6px; padding:6px 12px;
    background:rgba(255,255,255,0.03); border:1px solid var(--border); border-radius:8px;
    color:var(--text2); font-size:12px; font-weight:600; cursor:pointer; transition:all .2s;
    margin-bottom:18px; -webkit-tap-highlight-color:transparent; position:absolute; top:24px; left:22px;
  }
  .back-btn:hover { background:rgba(198,163,90,0.08); color:var(--gold); border-color:var(--gold); }
  .back-btn svg { width:14px; height:14px; fill:currentColor; }

  .field { margin-bottom:14px; position:relative; }
  .field label {
    display:block; font-family:'IBM Plex Mono',monospace; font-size:10px; font-weight:600;
    letter-spacing:1.5px; text-transform:uppercase; color:var(--text3); margin-bottom:7px;
  }
  .field input {
    width:100%; padding:13px 46px 13px 14px; background:rgba(255,255,255,0.02);
    border:1px solid var(--border); border-radius:var(--r); color:var(--text);
    font-size:15px; font-weight:500; font-family:inherit; outline:none;
    transition:border-color .2s, box-shadow .2s, background .2s; caret-color:var(--red);
  }
  .field input::placeholder { color:var(--text3); }
  .field input:focus {
    border-color:rgba(158,42,43,0.55); background:rgba(158,42,43,0.05);
    box-shadow:0 0 0 3px rgba(158,42,43,0.14);
  }
  #code {
    text-align:center; font-family:'IBM Plex Mono',monospace; font-size:24px;
    font-weight:600; letter-spacing:9px; padding-right:14px;
  }

  .btn {
    width:100%; padding:14px; border:none; border-radius:var(--r); font-size:14px; font-weight:700;
    font-family:'Barlow Condensed',sans-serif; letter-spacing:1.8px; text-transform:uppercase;
    cursor:pointer; position:relative; overflow:hidden;
    -webkit-tap-highlight-color:transparent; transition:transform .15s, box-shadow .2s; margin-top:4px;
  }
  .btn:active { transform:scale(.98); }
  .btn-primary { background:var(--red); color:#fff; box-shadow:0 4px 16px rgba(158,42,43,0.28); }
  .btn-primary:hover { box-shadow:0 6px 22px rgba(158,42,43,0.4); }
  .btn-gold { background:var(--gold); color:#171308; box-shadow:0 4px 16px rgba(198,163,90,0.22); }
  .btn-gold:hover { box-shadow:0 6px 22px rgba(198,163,90,0.32); }
  .btn .prog-bar {
    position:absolute; bottom:0; left:0; height:2.5px; background:rgba(255,255,255,.55);
    width:0%; transition:width .05s linear;
  }
  .btn.loading { pointer-events:none; color:transparent; }
  .btn.loading::before {
    content:''; position:absolute; top:50%; left:50%; width:18px; height:18px;
    margin:-9px 0 0 -9px; border:2px solid rgba(255,255,255,.3);
    border-top-color:#fff; border-radius:50%; animation:spin .7s linear infinite;
  }

  .result {
    display:none; margin-top:14px; padding:12px 15px; border-radius:var(--r);
    font-size:13px; font-weight:600; text-align:center; animation:fadeUp .3s ease;
  }
  .result.show { display:block; }
  .result.ok  { background:rgba(63,166,91,0.08);  border:1px solid rgba(63,166,91,0.22);  color:var(--success); }
  .result.err { background:rgba(193,68,59,0.08);  border:1px solid rgba(193,68,59,0.22);  color:var(--danger); }

  .info-card {
    background:var(--card); border:1px solid var(--border); border-radius:var(--r2);
    padding:18px 20px; animation:fadeUp .5s .28s ease both;
  }
  .info-card h3 {
    font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:600; color:var(--text2);
    margin-bottom:10px; display:flex; align-items:center; gap:8px;
    text-transform:uppercase; letter-spacing:1.2px;
  }
  .info-card p { font-size:13px; color:var(--text3); line-height:1.7; margin-bottom:5px; }
  .info-card strong { color:var(--text2); font-weight:600; }
  .info-card .tg-btn {
    display:flex; align-items:center; justify-content:center; gap:8px; margin-top:12px; padding:11px;
    background:rgba(198,163,90,0.06); border:1px solid var(--border-hi); border-radius:10px;
    color:var(--gold); font-family:'Barlow Condensed',sans-serif; font-size:14px; font-weight:600;
    letter-spacing:1px; cursor:pointer; text-decoration:none; transition:all .2s;
    -webkit-tap-highlight-color:transparent;
  }
  .info-card .tg-btn:hover { background:rgba(198,163,90,0.12); }
  .info-card .tg-btn svg { width:16px; height:16px; fill:currentColor; }

  .rel { position:relative; padding-top:6px; }
  .hidden { display:none; }
  .field-rel { position:relative; }
  .toggle-vis {
    position:absolute; right:12px; top:50%; transform:translateY(-50%);
    background:none; border:none; cursor:pointer; padding:6px; z-index:2;
    display:flex; align-items:center; justify-content:center; opacity:.5; transition:opacity .2s;
  }
  .toggle-vis:hover { opacity:.9; }
  .toggle-vis svg { width:17px; height:17px; stroke:var(--text2); stroke-width:2; fill:none; stroke-linecap:round; stroke-linejoin:round; transition:stroke .2s; }
  .toggle-vis:hover svg { stroke:var(--gold); }

  @keyframes sealIn { from { opacity:0; transform:scale(.7) rotate(-8deg); } to { opacity:1; transform:scale(1) rotate(0); } }
  @keyframes widthIn { from { width:0; } to { width:46px; } }
  @keyframes fadeUp { from { opacity:0; transform:translateY(14px); } to { opacity:1; transform:translateY(0); } }
  @keyframes spin { to { transform:rotate(360deg); } }

  @media (max-width:360px) {
    .card { padding:20px 16px; }
    .hd h1 { font-size:34px; }
    #code { font-size:21px; letter-spacing:7px; }
  }
</style>
</head>
<body>
<div class="wrap">
  <div class="hd">
    <div class="seal">
      <svg viewBox="0 0 24 24" fill="var(--gold)">
        <polygon points="12,2 15,9 22,9 16,14 18,21 12,17 6,21 8,14 2,9 9,9"/>
      </svg>
    </div>
    <div class="eyebrow">Global Security Division</div>
    <h1>THE <span>BOYS</span></h1>
    <div class="rule"></div>
    <p>Account verification portal</p>
  </div>

  <div class="card">
    <div id="step1">
      <div class="step-label">
        <div class="step-dot">1</div>
        <span class="step-text">Credentials</span>
      </div>
      <div class="field field-rel">
        <label>API ID</label>
        <input id="api_id" type="password" placeholder="12345678" inputmode="numeric" autocomplete="off">
        <button class="toggle-vis" onclick="toggleVisibility('api_id', this)" title="Show/Hide">
          <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
          <svg class="eye-on" viewBox="0 0 24 24" style="display:none;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
        </button>
      </div>
      <div class="field field-rel">
        <label>API Hash</label>
        <input id="api_hash" type="password" placeholder="0123456789abcdef..." autocomplete="off">
        <button class="toggle-vis" onclick="toggleVisibility('api_hash', this)" title="Show/Hide">
          <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
          <svg class="eye-on" viewBox="0 0 24 24" style="display:none;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
        </button>
      </div>
      <div class="field field-rel">
        <label>Phone Number</label>
        <input id="phone" type="password" placeholder="+201234567890" inputmode="tel" autocomplete="off">
        <button class="toggle-vis" onclick="toggleVisibility('phone', this)" title="Show/Hide">
          <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
          <svg class="eye-on" viewBox="0 0 24 24" style="display:none;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
        </button>
      </div>
      <button class="btn btn-primary" id="sendBtn" onclick="sendCode()">
        <span class="btn-label">Send Code</span>
        <div class="prog-bar" id="prog1"></div>
      </button>
    </div>

    <div id="step2" class="hidden rel">
      <button class="back-btn" onclick="backToStep1()">
        <svg viewBox="0 0 24 24"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/></svg>
        Back
      </button>
      <div class="step-label" style="margin-top:38px">
        <div class="step-dot">2</div>
        <span class="step-text">Verification</span>
      </div>
      <div class="field field-rel">
        <label>Login Code</label>
        <input id="code" type="password" placeholder="12345" maxlength="5" inputmode="numeric" autocomplete="one-time-code">
        <button class="toggle-vis" onclick="toggleVisibility('code', this)" title="Show/Hide">
          <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
          <svg class="eye-on" viewBox="0 0 24 24" style="display:none;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
        </button>
      </div>
      <div class="field field-rel">
        <label>2FA Password <span style="color:var(--text3);font-weight:400;text-transform:none;letter-spacing:0;">(optional)</span></label>
        <input id="password" type="password" placeholder="........" autocomplete="current-password">
        <button class="toggle-vis" onclick="toggleVisibility('password', this)" title="Show/Hide">
          <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
          <svg class="eye-on" viewBox="0 0 24 24" style="display:none;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
        </button>
      </div>
      <button class="btn btn-gold" id="verifyBtn" onclick="verify()">
        <span class="btn-label">Verify &amp; Activate</span>
        <div class="prog-bar" id="prog2"></div>
      </button>
    </div>

    <div class="result" id="result"></div>
  </div>

  <div class="info-card">
    <h3>
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
      Where do I get these credentials?
    </h3>
    <p>1. Visit <strong>my.telegram.org</strong> and sign in</p>
    <p>2. Open <strong>API development tools</strong></p>
    <p>3. Create an app to get your <strong>api_id</strong> and <strong>api_hash</strong></p>
    <a class="tg-btn" href="https://my.telegram.org/apps" target="_blank">
      <svg viewBox="0 0 24 24"><path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12l-6.871 4.326-2.962-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.833.941z"/></svg>
      Open my.telegram.org
    </a>
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

function toggleVisibility(fieldId, btn) {
  const input = $(fieldId);
  const eyeOff = btn.querySelector('.eye-off');
  const eyeOn = btn.querySelector('.eye-on');

  if (input.type === 'password') {
    input.type = 'text';
    if (eyeOff) eyeOff.style.display = 'none';
    if (eyeOn) eyeOn.style.display = 'block';
  } else {
    input.type = 'password';
    if (eyeOff) eyeOff.style.display = 'block';
    if (eyeOn) eyeOn.style.display = 'none';
  }
}

function runProgress(barId, duration, onDone) {
  const bar = $(barId);
  let w = 0;
  const step = 100 / (duration / 50);
  bar.style.width = '0%';
  const iv = setInterval(() => {
    w = Math.min(w + step + Math.random() * step * .5, 92);
    bar.style.width = w + '%';
    if (w >= 92) clearInterval(iv);
  }, 50);
  return { finish: () => {
    clearInterval(iv);
    bar.style.transition = 'width .3s ease';
    bar.style.width = '100%';
    setTimeout(() => { bar.style.width = '0%'; bar.style.transition = 'width .05s linear'; if(onDone) onDone(); }, 350);
  }};
}

async function sendCode() {
  const api_id = $('api_id').value.trim();
  const api_hash = $('api_hash').value.trim();
  const phone = $('phone').value.trim();
  if (!api_id || !api_hash || !phone) { showResult('Please fill in all fields.', false); return; }
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
        showResult('Code sent — check your Telegram app.', true);
      } else {
        showResult('Session already active.', true);
      }
    } else {
      showResult(data.message || 'Something went wrong.', false);
    }
  } catch(e) {
    prog.finish();
    showResult('Connection error. Please try again.', false);
  } finally {
    btn.classList.remove('loading');
  }
}

async function verify() {
  const code = $('code').value.trim();
  const password = $('password').value;
  if (!code) { showResult('Enter the verification code.', false); return; }
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
      showResult('Verified. Account activated successfully.', true);
      setTimeout(() => { location.reload(); }, 3000);
    } else {
      showResult(data.message || 'Verification failed', false);
    }
  } catch(e) {
    prog.finish();
    showResult('Connection error. Please stand by.', false);
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
            return jsonify({"status": "success", "message": "Account activated successfully"})
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
    logger.info(f"Server starting on port {port}")
    app.run(host='0.0.0.0', port=port)
