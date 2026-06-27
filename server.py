# server.py
import threading, asyncio, uuid, logging, sys
from flask import Flask, jsonify, request
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession
from shared import *            # يستورد كل المتغيرات والدوال، بما فيها main_loop

app = Flask(__name__)

# ------------------- موقع الويب -------------------
@app.route('/')
def home():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>ꪀɪꪀȷᥲƚһ᥆ꪀ — Telethon Setup</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
  :root {
    --bg:#0A0A19; --surface:#0F0F22; --card:#12122A;
    --border:rgba(200,200,215,0.12); --border-hi:rgba(200,200,215,0.3);
    --accent:#7C83FF; --accent2:#5A60CC; --glow:rgba(124,131,255,0.2);
    --success:#6DD98A; --danger:#FF6B6B; --text:#E8E8F0;
    --text2:rgba(232,232,240,0.6); --text3:rgba(232,232,240,0.35);
    --r:14px; --r2:22px;
  }
  *, *::before, *::after { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family:'Inter',-apple-system,BlinkMacSystemFont,system-ui,sans-serif;
    background:var(--bg); color:var(--text); min-height:100vh;
    display:flex; align-items:center; justify-content:center;
    padding:20px 16px 40px; -webkit-font-smoothing:antialiased; overflow-x:hidden;
  }
  body::before {
    content:''; position:fixed; inset:0;
    background: radial-gradient(ellipse 80% 50% at 50% -10%, rgba(124,131,255,.08) 0%, transparent 70%),
                radial-gradient(ellipse 50% 40% at 80% 90%, rgba(90,96,204,.05) 0%, transparent 60%);
    pointer-events:none; z-index:0;
  }
  .wrap { position:relative; z-index:1; width:100%; max-width:420px; display:flex; flex-direction:column; gap:20px; }
  .hd { text-align:center; padding:8px 0 4px; }
  .hd-icon {
    width:72px; height:72px; background:linear-gradient(135deg, var(--accent), var(--accent2));
    border-radius:22px; margin:0 auto 16px; display:flex; align-items:center; justify-content:center;
    box-shadow:0 0 0 1px rgba(200,200,215,.15), 0 12px 40px var(--glow);
    animation:popIn .5s cubic-bezier(.34,1.56,.64,1) both;
  }
  .hd-icon svg { width:36px; height:36px; fill:#fff; }
  .hd h1 {
    font-size:32px; font-weight:800; letter-spacing:-1.2px;
    background:linear-gradient(135deg, #E8E8F0 0%, #C8C8D8 50%, #E8E8F0 100%);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;
    animation:fadeUp .5s .1s ease both;
  }
  .hd p { font-size:13px; font-weight:500; color:var(--text3); letter-spacing:.5px; margin-top:4px; animation:fadeUp .5s .2s ease both; }
  .card {
    background:var(--card); border:1px solid var(--border); border-radius:var(--r2); padding:28px 24px;
    box-shadow:0 2px 0 rgba(200,200,215,.03) inset, 0 32px 80px rgba(0,0,0,.6);
    animation:fadeUp .5s .15s ease both; transition:border-color .3s;
  }
  .card:hover { border-color:var(--border-hi); }
  .step-label { display:flex; align-items:center; gap:10px; margin-bottom:22px; }
  .step-dot {
    width:28px; height:28px; border-radius:50%; background:linear-gradient(135deg, var(--accent), var(--accent2));
    display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:700; color:#fff;
    box-shadow:0 4px 12px var(--glow); flex-shrink:0;
  }
  .step-text { font-size:14px; font-weight:600; color:var(--text2); }
  .back-btn {
    display:inline-flex; align-items:center; gap:6px; padding:6px 14px;
    background:rgba(200,200,215,.05); border:1px solid var(--border); border-radius:10px;
    color:var(--text2); font-size:12px; font-weight:600; cursor:pointer; transition:all .2s;
    margin-bottom:18px; -webkit-tap-highlight-color:transparent; position:absolute; top:24px; left:24px;
  }
  .back-btn:hover { background:rgba(200,200,215,.1); color:var(--text); }
  .back-btn svg { width:14px; height:14px; fill:currentColor; }
  .field { margin-bottom:14px; }
  .field label {
    display:block; font-size:11px; font-weight:700; letter-spacing:1px; text-transform:uppercase;
    color:var(--text3); margin-bottom:7px;
  }
  .field input {
    width:100%; padding:14px 44px 14px 16px; background:rgba(200,200,215,.03); border:1px solid var(--border);
    border-radius:var(--r); color:var(--text); font-size:15px; font-weight:500; font-family:inherit;
    outline:none; transition:border-color .2s, box-shadow .2s, background .2s; caret-color:var(--accent);
  }
  .field input::placeholder { color:var(--text3); }
  .field input:focus {
    border-color:rgba(124,131,255,.5); background:rgba(124,131,255,.05);
    box-shadow:0 0 0 3px rgba(124,131,255,.12);
  }
  #code { text-align:center; font-size:28px; font-weight:700; letter-spacing:10px; padding-right:16px; }
  .btn {
    width:100%; padding:15px; border:none; border-radius:var(--r); font-size:15px; font-weight:700;
    font-family:inherit; cursor:pointer; position:relative; overflow:hidden;
    -webkit-tap-highlight-color:transparent; transition:transform .15s, box-shadow .2s, background .2s; margin-top:6px;
  }
  .btn:active { transform:scale(.97); }
  .btn-blue {
    background:linear-gradient(135deg, var(--accent) 0%, var(--accent2) 100%);
    color:#fff; box-shadow:0 4px 20px var(--glow);
  }
  .btn-blue:hover { box-shadow:0 8px 32px rgba(124,131,255,.4); transform:translateY(-1px); }
  .btn-green {
    background:linear-gradient(135deg, #6DD98A 0%, #4CAF6E 100%);
    color:#fff; box-shadow:0 4px 20px rgba(109,217,138,.2);
  }
  .btn-green:hover { box-shadow:0 8px 32px rgba(109,217,138,.35); transform:translateY(-1px); }
  .btn::after {
    content:''; position:absolute; inset:0;
    background:linear-gradient(90deg, transparent 0%, rgba(255,255,255,.15) 50%, transparent 100%);
    transform:translateX(-100%); transition:transform .4s ease;
  }
  .btn:active::after { transform:translateX(100%); }
  .btn .prog-bar {
    position:absolute; bottom:0; left:0; height:3px; background:rgba(255,255,255,.4);
    border-radius:0 0 var(--r) var(--r); width:0%; transition:width .05s linear;
  }
  .btn.loading { pointer-events:none; color:transparent; }
  .btn.loading::before {
    content:''; position:absolute; top:50%; left:50%; width:20px; height:20px;
    margin:-10px 0 0 -10px; border:2.5px solid rgba(255,255,255,.25);
    border-top-color:#fff; border-radius:50%; animation:spin .7s linear infinite;
  }
  .result {
    display:none; margin-top:16px; padding:13px 16px; border-radius:var(--r);
    font-size:13px; font-weight:600; text-align:center; animation:fadeUp .35s ease;
  }
  .result.show { display:block; }
  .result.ok  { background:rgba(109,217,138,.1);  border:1px solid rgba(109,217,138,.25);  color:var(--success); }
  .result.err { background:rgba(255,107,107,.1);   border:1px solid rgba(255,107,107,.25);  color:var(--danger);  }
  .info-card {
    background:var(--card); border:1px solid var(--border); border-radius:var(--r2);
    padding:20px 22px; animation:fadeUp .5s .3s ease both;
  }
  .info-card h3 { font-size:13px; font-weight:700; color:var(--text2); margin-bottom:12px; display:flex; align-items:center; gap:8px; }
  .info-card p { font-size:13px; color:var(--text3); line-height:1.75; margin-bottom:6px; }
  .info-card a { color:var(--accent); text-decoration:none; font-weight:600; border-bottom:1px solid transparent; transition:border-color .2s; }
  .info-card a:hover { border-bottom-color:var(--accent); }
  .info-card .tg-btn {
    display:flex; align-items:center; justify-content:center; gap:8px; margin-top:14px; padding:12px;
    background:linear-gradient(135deg, rgba(124,131,255,.12), rgba(90,96,204,.08));
    border:1px solid rgba(124,131,255,.25); border-radius:14px; color:var(--accent);
    font-size:13px; font-weight:700; cursor:pointer; text-decoration:none; transition:all .2s;
    -webkit-tap-highlight-color:transparent;
  }
  .info-card .tg-btn:hover { background:linear-gradient(135deg, rgba(124,131,255,.2), rgba(90,96,204,.15)); box-shadow:0 4px 20px rgba(124,131,255,.2); transform:translateY(-1px); }
  .info-card .tg-btn svg { width:18px; height:18px; fill:currentColor; }
  .rel { position:relative; padding-top:8px; }
  .hidden { display:none; }
  .field-rel { position:relative; }
  .toggle-vis {
    position:absolute; right:10px; top:50%; transform:translateY(-50%);
    background:none; border:none; cursor:pointer;
    padding:6px; z-index:2; transition:opacity .2s;
    display:flex; align-items:center; justify-content:center;
    opacity:0.45;
  }
  .toggle-vis:hover { opacity:0.85; }
  .toggle-vis svg { width:18px; height:18px; stroke:var(--text2); stroke-width:2; fill:none; stroke-linecap:round; stroke-linejoin:round; transition:stroke .2s; }
  .toggle-vis:hover svg { stroke:var(--accent); }
  @keyframes popIn { from { opacity:0; transform:scale(.6); } to { opacity:1; transform:scale(1); } }
  @keyframes fadeUp { from { opacity:0; transform:translateY(16px); } to { opacity:1; transform:translateY(0); } }
  @keyframes spin { to { transform:rotate(360deg); } }
  @media (max-width:360px) {
    .card { padding:22px 18px; }
    .hd h1 { font-size:28px; }
    #code { font-size:24px; letter-spacing:8px; }
  }
</style>
</head>
<body>
<div class="wrap">
  <div class="hd">
    <div class="hd-icon">
      <svg viewBox="0 0 24 24"><path d="M12 2L2 22h20L12 2zm0 3.5L18.5 20H5.5L12 5.5z"/></svg>
    </div>
    <h1>ꪀɪꪀȷᥲƚһ᥆ꪀ</h1>
    <p>ᑲᥡ ꪀɪꪀȷᥲgɾᥲꪔ</p>
  </div>
  <div class="card">
    <div id="step1">
      <div class="step-label">
        <div class="step-dot">1</div>
        <span class="step-text">Account Information</span>
      </div>
      <div class="field field-rel">
        <label>API ID</label>
        <input id="api_id" type="password" placeholder="12345678" inputmode="numeric" autocomplete="off">
        <button class="toggle-vis" onclick="toggleVisibility('api_id', this)" title="Show/Hide">
          <svg id="api_id_eye_off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
          <svg id="api_id_eye_on" viewBox="0 0 24 24" style="display:none;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
        </button>
      </div>
      <div class="field field-rel">
        <label>API Hash</label>
        <input id="api_hash" type="password" placeholder="0123456789abcdef…" autocomplete="off">
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
      <button class="btn btn-blue" id="sendBtn" onclick="sendCode()">
        <span class="btn-label">Send Verification Code</span>
        <div class="prog-bar" id="prog1"></div>
      </button>
    </div>
    <div id="step2" class="hidden rel">
      <button class="back-btn" onclick="backToStep1()">
        <svg viewBox="0 0 24 24"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/></svg>
        Back
      </button>
      <div class="step-label" style="margin-top:40px">
        <div class="step-dot">2</div>
        <span class="step-text">Verification Code</span>
      </div>
      <div class="field field-rel">
        <label>Code</label>
        <input id="code" type="password" placeholder="12345" maxlength="5" inputmode="numeric" autocomplete="one-time-code">
        <button class="toggle-vis" onclick="toggleVisibility('code', this)" title="Show/Hide">
          <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
          <svg class="eye-on" viewBox="0 0 24 24" style="display:none;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
        </button>
      </div>
      <div class="field field-rel">
        <label>2FA Password <span style="color:var(--text3);font-weight:400">(optional)</span></label>
        <input id="password" type="password" placeholder="••••••••" autocomplete="current-password">
        <button class="toggle-vis" onclick="toggleVisibility('password', this)" title="Show/Hide">
          <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
          <svg class="eye-on" viewBox="0 0 24 24" style="display:none;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
        </button>
      </div>
      <button class="btn btn-green" id="verifyBtn" onclick="verify()">
        <span class="btn-label">Activate Telethon</span>
        <div class="prog-bar" id="prog2"></div>
      </button>
    </div>
    <div class="result" id="result"></div>
  </div>
  <div class="info-card">
    <h3>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
      How to get API credentials?
    </h3>
    <p>1. Open Telegram website from the button below</p>
    <p>2. Log in with your phone number</p>
    <p>3. Go to <strong>API development tools</strong></p>
    <p>4. Create an app and copy your <strong>api_id</strong> and <strong>api_hash</strong></p>
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
  if (!api_id || !api_hash || !phone) { showResult('Please fill all fields', false); return; }
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
        showResult('Verification code sent', true);
      } else {
        showResult('Session already active', true);
      }
    } else {
      showResult(data.message || 'Error occurred', false);
    }
  } catch(e) {
    prog.finish();
    showResult('Connection error', false);
  } finally {
    btn.classList.remove('loading');
  }
}

async function verify() {
  const code = $('code').value.trim();
  const password = $('password').value;
  if (!code) { showResult('Enter verification code', false); return; }
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
      showResult('Telethon installed successfully!', true);
      setTimeout(() => { location.reload(); }, 3000);
    } else {
      showResult(data.message || 'Verification failed', false);
    }
  } catch(e) {
    prog.finish();
    showResult('Connection error', false);
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

@app.route('/health')
def health():
    return "OK", 200

# ------------------- API -------------------
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
        logger.error(f"خطأ في إرسال الكود: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

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
            await notify_dev(f"تم تفعيل مستخدم جديد: {phone}")
            return jsonify({"status": "success", "message": "Telethon installed successfully"})
        except Exception as e:
            logger.error(f"خطأ في التحقق: {e}")
            return jsonify({"status": "error", "message": str(e)}), 400
    return run_in_main(_verify())

def run_in_main(coro):
    from shared import main_loop
    future = asyncio.run_coroutine_threadsafe(coro, main_loop)
    return future.result(timeout=60)
