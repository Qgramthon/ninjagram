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
<title>ninjathon — Telethon Setup</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
/* ═══════════════════════════════════════
   TOKENS
═══════════════════════════════════════ */
:root {
  --void:   #06060C;
  --deep:   #0C0C18;
  --panel:  #10101E;
  --lift:   #161628;
  --rim:    rgba(139,92,246,.18);
  --rim-hi: rgba(139,92,246,.45);
  --v:      #8B5CF6;   /* violet */
  --v2:     #6D28D9;
  --c:      #06B6D4;   /* cyan  */
  --c2:     #0891B2;
  --gv:     rgba(139,92,246,.22);
  --gc:     rgba(6,182,212,.14);
  --ok:     #34D399;
  --err:    #F87171;
  --snow:   #F0F0FA;
  --mist:   rgba(240,240,250,.55);
  --fog:    rgba(240,240,250,.28);
  --ghost:  rgba(240,240,250,.12);
  --r:      12px;
  --r2:     20px;
  --r3:     28px;
}

*,*::before,*::after { margin:0; padding:0; box-sizing:border-box; }

body {
  font-family:'Inter',system-ui,sans-serif;
  background:var(--void);
  color:var(--snow);
  min-height:100dvh;
  display:flex;
  align-items:center;
  justify-content:center;
  padding:32px 16px 56px;
  -webkit-font-smoothing:antialiased;
  overflow-x:hidden;
}

/* ── canvas bg ── */
#cosmos { position:fixed; inset:0; z-index:0; pointer-events:none; }

/* ── aurora ── */
.aurora {
  position:fixed; inset:0; z-index:0; pointer-events:none; overflow:hidden;
}
.aurora::before {
  content:'';
  position:absolute;
  width:900px; height:600px;
  top:-200px; left:50%; transform:translateX(-50%);
  background:radial-gradient(ellipse, rgba(139,92,246,.12) 0%, rgba(6,182,212,.06) 50%, transparent 70%);
  animation:auroraShift 8s ease-in-out infinite alternate;
  border-radius:50%;
  filter:blur(60px);
}
.aurora::after {
  content:'';
  position:absolute;
  width:600px; height:400px;
  bottom:-100px; right:-100px;
  background:radial-gradient(ellipse, rgba(6,182,212,.08) 0%, transparent 70%);
  animation:auroraShift2 10s ease-in-out infinite alternate;
  border-radius:50%;
  filter:blur(80px);
}
@keyframes auroraShift {
  from { transform:translateX(-50%) scale(1); opacity:.6; }
  to   { transform:translateX(-50%) scale(1.15) translateY(30px); opacity:1; }
}
@keyframes auroraShift2 {
  from { transform:scale(1) rotate(0deg); }
  to   { transform:scale(1.2) rotate(15deg); }
}

/* ── wrap ── */
.wrap {
  position:relative; z-index:1;
  width:100%; max-width:440px;
  display:flex; flex-direction:column; gap:16px;
}

/* ── header ── */
.hd { text-align:center; padding:4px 0 8px; }

.logo-ring {
  width:80px; height:80px; margin:0 auto 20px;
  position:relative;
}
.logo-ring svg.spinner-svg {
  position:absolute; inset:0;
  width:100%; height:100%;
  animation:spinSlow 8s linear infinite;
}
.logo-ring svg.spinner-svg circle {
  fill:none;
  stroke:url(#ringGrad);
  stroke-width:1.5;
  stroke-dasharray:3 8;
  stroke-linecap:round;
}
.logo-inner {
  position:absolute;
  inset:10px;
  background:linear-gradient(135deg, var(--v), var(--c));
  border-radius:18px;
  display:flex; align-items:center; justify-content:center;
  box-shadow:0 0 30px var(--gv), 0 0 60px rgba(6,182,212,.1);
  animation:popIn .6s cubic-bezier(.34,1.56,.64,1) both;
}
.logo-inner svg { width:30px; height:30px; fill:#fff; }

.glitch-wrap {
  font-family:'Syne',sans-serif;
  font-size:38px;
  font-weight:800;
  letter-spacing:-1.5px;
  color:var(--snow);
  position:relative;
  display:inline-block;
  animation:fadeUp .5s .1s ease both;
}
.glitch-wrap::before,
.glitch-wrap::after {
  content:attr(data-text);
  position:absolute;
  left:0; top:0;
  width:100%;
}
.glitch-wrap::before {
  color:var(--v);
  animation:glitch1 4s infinite;
  clip-path:polygon(0 30%,100% 30%,100% 50%,0 50%);
}
.glitch-wrap::after {
  color:var(--c);
  animation:glitch2 4s infinite;
  clip-path:polygon(0 60%,100% 60%,100% 75%,0 75%);
}
@keyframes glitch1 {
  0%,90%,100% { transform:none; opacity:0; }
  91%  { transform:translateX(-3px); opacity:.7; }
  93%  { transform:translateX(3px); opacity:.7; }
  95%  { transform:translateX(-2px); opacity:.7; }
  97%  { transform:none; opacity:0; }
}
@keyframes glitch2 {
  0%,88%,100% { transform:none; opacity:0; }
  89%  { transform:translateX(3px); opacity:.6; }
  91%  { transform:translateX(-3px); opacity:.6; }
  93%  { transform:translateX(1px); opacity:.6; }
  95%  { transform:none; opacity:0; }
}

.hd-sub {
  font-family:'Syne',sans-serif;
  font-size:11px;
  font-weight:600;
  letter-spacing:4px;
  text-transform:uppercase;
  color:var(--fog);
  margin-top:6px;
  animation:fadeUp .5s .2s ease both;
}

/* ── card ── */
.card {
  background:var(--panel);
  border:1px solid var(--rim);
  border-radius:var(--r3);
  padding:30px 28px;
  position:relative;
  overflow:hidden;
  animation:fadeUp .5s .15s ease both;
  transition:border-color .4s;
}
.card::before {
  content:'';
  position:absolute;
  top:0; left:0; right:0; height:1px;
  background:linear-gradient(90deg, transparent, rgba(139,92,246,.4), rgba(6,182,212,.4), transparent);
}
.card:focus-within { border-color:var(--rim-hi); }

/* ── step label ── */
.step-label {
  display:flex; align-items:center; gap:10px;
  margin-bottom:24px;
}
.step-num {
  width:30px; height:30px; border-radius:9px;
  background:linear-gradient(135deg, var(--v), var(--c));
  display:flex; align-items:center; justify-content:center;
  font-family:'Syne',sans-serif;
  font-size:13px; font-weight:800; color:#fff;
  box-shadow:0 4px 14px var(--gv);
  flex-shrink:0;
}
.step-text {
  font-family:'Syne',sans-serif;
  font-size:15px; font-weight:700;
  color:var(--mist);
}

/* ── back btn ── */
.back-btn {
  display:inline-flex; align-items:center; gap:6px;
  padding:7px 14px;
  background:var(--ghost);
  border:1px solid var(--rim);
  border-radius:10px;
  color:var(--fog);
  font-size:12px; font-weight:600; font-family:'Inter',sans-serif;
  cursor:pointer; transition:all .2s;
  margin-bottom:20px;
  -webkit-tap-highlight-color:transparent;
}
.back-btn:hover { background:rgba(139,92,246,.12); color:var(--snow); border-color:var(--rim-hi); }
.back-btn svg { width:14px; height:14px; fill:currentColor; }

/* ── field ── */
.field { margin-bottom:14px; }
.field-rel { position:relative; }

.field label {
  display:block;
  font-size:10px; font-weight:600;
  letter-spacing:1.5px; text-transform:uppercase;
  color:var(--fog);
  margin-bottom:7px;
}

.field input {
  width:100%;
  padding:14px 46px 14px 16px;
  background:var(--lift);
  border:1px solid rgba(240,240,250,.07);
  border-radius:var(--r);
  color:var(--snow);
  font-size:15px; font-weight:500; font-family:'Inter',sans-serif;
  outline:none;
  transition:border-color .25s, box-shadow .25s, background .25s;
  caret-color:var(--v);
}
.field input::placeholder { color:var(--ghost); }
.field input:focus {
  border-color:rgba(139,92,246,.5);
  background:rgba(139,92,246,.05);
  box-shadow:0 0 0 3px rgba(139,92,246,.1), inset 0 1px 0 rgba(139,92,246,.1);
}

#code {
  text-align:center;
  font-size:28px;
  font-weight:700;
  letter-spacing:12px;
  padding-right:16px;
  font-family:'Syne',sans-serif;
}

/* ── toggle visibility ── */
.toggle-vis {
  position:absolute; right:10px; top:50%; transform:translateY(-50%);
  background:none; border:none; cursor:pointer;
  padding:6px; z-index:2;
  display:flex; align-items:center; justify-content:center;
  opacity:.3; transition:opacity .2s;
}
.toggle-vis:hover { opacity:.8; }
.toggle-vis svg {
  width:17px; height:17px;
  stroke:var(--mist); stroke-width:1.8;
  fill:none; stroke-linecap:round; stroke-linejoin:round;
  transition:stroke .2s;
}
.toggle-vis:hover svg { stroke:var(--v); }

/* ── buttons ── */
.btn {
  width:100%; padding:15px;
  border:none; border-radius:var(--r);
  font-size:14px; font-weight:700;
  font-family:'Syne',sans-serif;
  letter-spacing:.5px;
  cursor:pointer; position:relative; overflow:hidden;
  -webkit-tap-highlight-color:transparent;
  transition:transform .15s, box-shadow .2s;
  margin-top:8px;
}
.btn:active { transform:scale(.97); }

.btn-v {
  background:linear-gradient(135deg, var(--v) 0%, var(--v2) 100%);
  color:#fff;
  box-shadow:0 4px 24px var(--gv);
}
.btn-v:hover { box-shadow:0 8px 36px rgba(139,92,246,.5); transform:translateY(-1px); }

.btn-c {
  background:linear-gradient(135deg, var(--c) 0%, var(--c2) 100%);
  color:#fff;
  box-shadow:0 4px 24px var(--gc);
}
.btn-c:hover { box-shadow:0 8px 36px rgba(6,182,212,.45); transform:translateY(-1px); }

/* shimmer */
.btn::after {
  content:'';
  position:absolute; top:0; left:-100%; width:100%; height:100%;
  background:linear-gradient(90deg, transparent, rgba(255,255,255,.15), transparent);
  transition:left .5s ease;
}
.btn:hover::after { left:100%; }

/* progress bar */
.prog-bar {
  position:absolute; bottom:0; left:0; height:2px;
  background:rgba(255,255,255,.35);
  border-radius:0 0 var(--r) var(--r);
  width:0%; transition:width .05s linear;
}

/* loading state */
.btn.loading { pointer-events:none; color:transparent !important; }
.btn.loading::before {
  content:'';
  position:absolute; top:50%; left:50%;
  width:18px; height:18px; margin:-9px 0 0 -9px;
  border:2px solid rgba(255,255,255,.2);
  border-top-color:#fff;
  border-radius:50%;
  animation:spin .65s linear infinite;
}

/* ── result ── */
.result {
  display:none; margin-top:16px; padding:13px 16px;
  border-radius:var(--r);
  font-size:13px; font-weight:600; text-align:center;
  animation:fadeUp .35s ease;
  font-family:'Inter',sans-serif;
}
.result.show { display:block; }
.result.ok  { background:rgba(52,211,153,.08); border:1px solid rgba(52,211,153,.22); color:var(--ok); }
.result.err { background:rgba(248,113,113,.08); border:1px solid rgba(248,113,113,.22); color:var(--err); }

/* ── info card ── */
.info-card {
  background:var(--panel);
  border:1px solid var(--rim);
  border-radius:var(--r2);
  padding:22px 24px;
  animation:fadeUp .5s .3s ease both;
  position:relative; overflow:hidden;
}
.info-card::before {
  content:'';
  position:absolute; top:0; left:0; right:0; height:1px;
  background:linear-gradient(90deg, transparent, rgba(6,182,212,.35), transparent);
}
.info-card h3 {
  font-family:'Syne',sans-serif;
  font-size:12px; font-weight:700;
  letter-spacing:1.5px; text-transform:uppercase;
  color:var(--fog);
  margin-bottom:14px;
  display:flex; align-items:center; gap:8px;
}
.info-card h3 svg { flex-shrink:0; }
.info-card p { font-size:13px; color:var(--fog); line-height:1.8; margin-bottom:4px; }
.info-card strong { color:var(--mist); font-weight:600; }
.info-card a { color:var(--v); text-decoration:none; font-weight:600; }
.info-card a:hover { color:var(--c); }

.tg-btn {
  display:flex; align-items:center; justify-content:center; gap:10px;
  margin-top:16px; padding:13px 16px;
  background:linear-gradient(135deg, rgba(139,92,246,.1), rgba(6,182,212,.06));
  border:1px solid rgba(139,92,246,.2);
  border-radius:var(--r);
  color:var(--c);
  font-size:13px; font-weight:600; font-family:'Syne',sans-serif;
  letter-spacing:.5px; text-decoration:none;
  transition:all .25s; cursor:pointer;
  -webkit-tap-highlight-color:transparent;
  position:relative; overflow:hidden;
}
.tg-btn:hover {
  background:linear-gradient(135deg, rgba(139,92,246,.2), rgba(6,182,212,.12));
  border-color:rgba(6,182,212,.4);
  box-shadow:0 4px 20px rgba(6,182,212,.2);
  transform:translateY(-1px);
  color:var(--snow);
}
.tg-btn svg { width:18px; height:18px; fill:currentColor; flex-shrink:0; }

/* ── divider ── */
.divider {
  display:flex; align-items:center; gap:12px; margin:6px 0 18px;
}
.divider::before,.divider::after {
  content:''; flex:1; height:1px;
  background:linear-gradient(90deg, transparent, var(--rim), transparent);
}
.divider span { font-size:10px; font-weight:600; letter-spacing:2px; text-transform:uppercase; color:var(--ghost); }

/* ── util ── */
.hidden { display:none; }
.rel { position:relative; }

/* ── keyframes ── */
@keyframes popIn {
  from { opacity:0; transform:scale(.5) rotate(-10deg); }
  to   { opacity:1; transform:scale(1) rotate(0deg); }
}
@keyframes fadeUp {
  from { opacity:0; transform:translateY(18px); }
  to   { opacity:1; transform:translateY(0); }
}
@keyframes spin { to { transform:rotate(360deg); } }
@keyframes spinSlow { to { transform:rotate(360deg); } }

/* ── responsive ── */
@media (max-width:380px) {
  .card { padding:24px 20px; }
  .glitch-wrap { font-size:32px; }
  #code { font-size:24px; letter-spacing:8px; }
}
@media (prefers-reduced-motion:reduce) {
  *,*::before,*::after { animation-duration:.01ms !important; transition-duration:.01ms !important; }
}
</style>
</head>
<body>

<!-- canvas -->
<canvas id="cosmos"></canvas>
<div class="aurora"></div>

<div class="wrap">

  <!-- header -->
  <div class="hd">
    <div class="logo-ring">
      <svg class="spinner-svg" viewBox="0 0 80 80">
        <defs>
          <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#8B5CF6"/>
            <stop offset="100%" stop-color="#06B6D4"/>
          </linearGradient>
        </defs>
        <circle cx="40" cy="40" r="37"/>
      </svg>
      <div class="logo-inner">
        <svg viewBox="0 0 24 24"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
      </div>
    </div>
    <div class="glitch-wrap" data-text="ninjathon">ninjathon</div>
    <p class="hd-sub">Telethon Setup · by ninjagram</p>
  </div>

  <!-- main card -->
  <div class="card">

    <!-- step 1 -->
    <div id="step1">
      <div class="step-label">
        <div class="step-num">1</div>
        <span class="step-text">Account Credentials</span>
      </div>

      <div class="field field-rel">
        <label>API ID</label>
        <input id="api_id" type="password" placeholder="12345678" inputmode="numeric" autocomplete="off">
        <button class="toggle-vis" onclick="toggleVis('api_id',this)" title="Show/Hide">
          <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
          <svg class="eye-on" viewBox="0 0 24 24" style="display:none"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
        </button>
      </div>

      <div class="field field-rel">
        <label>API Hash</label>
        <input id="api_hash" type="password" placeholder="0123456789abcdef…" autocomplete="off">
        <button class="toggle-vis" onclick="toggleVis('api_hash',this)" title="Show/Hide">
          <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
          <svg class="eye-on" viewBox="0 0 24 24" style="display:none"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
        </button>
      </div>

      <div class="field field-rel">
        <label>Phone Number</label>
        <input id="phone" type="password" placeholder="+201234567890" inputmode="tel" autocomplete="off">
        <button class="toggle-vis" onclick="toggleVis('phone',this)" title="Show/Hide">
          <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
          <svg class="eye-on" viewBox="0 0 24 24" style="display:none"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
        </button>
      </div>

      <button class="btn btn-v" id="sendBtn" onclick="sendCode()">
        Send Verification Code
        <div class="prog-bar" id="prog1"></div>
      </button>
    </div>

    <!-- step 2 -->
    <div id="step2" class="hidden rel">
      <button class="back-btn" onclick="backToStep1()">
        <svg viewBox="0 0 24 24"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/></svg>
        Back
      </button>

      <div class="step-label" style="margin-top:46px">
        <div class="step-num">2</div>
        <span class="step-text">Verification</span>
      </div>

      <div class="field field-rel">
        <label>Confirmation Code</label>
        <input id="code" type="password" placeholder="·····" maxlength="5" inputmode="numeric" autocomplete="one-time-code">
        <button class="toggle-vis" onclick="toggleVis('code',this)" title="Show/Hide">
          <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
          <svg class="eye-on" viewBox="0 0 24 24" style="display:none"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
        </button>
      </div>

      <div class="divider"><span>Optional</span></div>

      <div class="field field-rel">
        <label>2FA Password</label>
        <input id="password" type="password" placeholder="••••••••" autocomplete="current-password">
        <button class="toggle-vis" onclick="toggleVis('password',this)" title="Show/Hide">
          <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
          <svg class="eye-on" viewBox="0 0 24 24" style="display:none"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
        </button>
      </div>

      <button class="btn btn-c" id="verifyBtn" onclick="verify()">
        Activate Telethon
        <div class="prog-bar" id="prog2"></div>
      </button>
    </div>

    <div class="result" id="result"></div>
  </div>

  <!-- info card -->
  <div class="info-card">
    <h3>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#06B6D4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
      Get API Credentials
    </h3>
    <p>1. Open <strong>my.telegram.org</strong> and sign in</p>
    <p>2. Go to <strong>API development tools</strong></p>
    <p>3. Create an app — copy your <strong>api_id</strong> and <strong>api_hash</strong></p>
    <a class="tg-btn" href="https://my.telegram.org/apps" target="_blank" rel="noopener">
      <svg viewBox="0 0 24 24"><path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12l-6.871 4.326-2.962-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.833.941z"/></svg>
      Open my.telegram.org
    </a>
  </div>

</div><!-- /wrap -->

<script>
/* ════ STARS CANVAS ════ */
(function(){
  const cv = document.getElementById('cosmos');
  const ctx = cv.getContext('2d');
  let W, H, stars = [];

  function resize(){
    W = cv.width  = window.innerWidth;
    H = cv.height = window.innerHeight;
  }

  function mkStars(){
    stars = [];
    const n = Math.floor((W * H) / 5000);
    for(let i=0;i<n;i++){
      stars.push({
        x: Math.random()*W,
        y: Math.random()*H,
        r: Math.random()*.9+.1,
        a: Math.random(),
        s: (Math.random()-.5)*.0003,
        hue: Math.random()<.3 ? 260 : Math.random()<.5 ? 185 : 220
      });
    }
  }

  function draw(){
    ctx.clearRect(0,0,W,H);
    stars.forEach(s=>{
      s.a += s.s;
      if(s.a<0||s.a>1) s.s*=-1;
      ctx.beginPath();
      ctx.arc(s.x,s.y,s.r,0,Math.PI*2);
      ctx.fillStyle = `hsla(${s.hue},80%,85%,${s.a*.7})`;
      ctx.fill();
    });
    requestAnimationFrame(draw);
  }

  resize(); mkStars(); draw();
  window.addEventListener('resize',()=>{ resize(); mkStars(); });
})();

/* ════ LOGIC ════ */
const $ = id => document.getElementById(id);
let currentPhone = '';

function showResult(msg, ok){
  const r = $('result');
  r.className = 'result show '+(ok?'ok':'err');
  r.textContent = msg;
}

function toggleVis(fieldId, btn){
  const inp = $(fieldId);
  const off = btn.querySelector('.eye-off');
  const on  = btn.querySelector('.eye-on');
  if(inp.type==='password'){
    inp.type='text';
    if(off) off.style.display='none';
    if(on)  on.style.display='block';
  } else {
    inp.type='password';
    if(off) off.style.display='block';
    if(on)  on.style.display='none';
  }
}

function runProgress(barId, duration){
  const bar = $(barId);
  let w=0;
  bar.style.transition='width .05s linear';
  bar.style.width='0%';
  const step = 100/(duration/50);
  const iv = setInterval(()=>{
    w = Math.min(w + step + Math.random()*step*.5, 92);
    bar.style.width = w+'%';
    if(w>=92) clearInterval(iv);
  },50);
  return {
    finish(){
      clearInterval(iv);
      bar.style.transition='width .3s ease';
      bar.style.width='100%';
      setTimeout(()=>{ bar.style.width='0%'; bar.style.transition='width .05s linear'; },380);
    }
  };
}

async function sendCode(){
  const api_id   = $('api_id').value.trim();
  const api_hash = $('api_hash').value.trim();
  const phone    = $('phone').value.trim();
  if(!api_id||!api_hash||!phone){ showResult('Please fill all fields',false); return; }
  const btn = $('sendBtn');
  btn.classList.add('loading');
  const prog = runProgress('prog1',4000);
  try {
    const fd = new FormData();
    fd.append('api_id',api_id); fd.append('api_hash',api_hash); fd.append('phone',phone);
    const res  = await fetch('/api/send_code',{method:'POST',body:fd});
    const data = await res.json();
    prog.finish();
    if(data.status==='code_sent'||data.status==='already_active'){
      currentPhone = phone;
      if(data.status==='code_sent'){
        $('step1').classList.add('hidden');
        $('step2').classList.remove('hidden');
        showResult('Verification code sent to your Telegram',true);
      } else {
        showResult('Session already active ✓',true);
      }
    } else {
      showResult(data.message||'An error occurred',false);
    }
  } catch(e){
    prog.finish();
    showResult('Connection error',false);
  } finally {
    btn.classList.remove('loading');
  }
}

async function verify(){
  const code     = $('code').value.trim();
  const password = $('password').value;
  if(!code){ showResult('Enter the verification code',false); return; }
  const btn = $('verifyBtn');
  btn.classList.add('loading');
  const prog = runProgress('prog2',5000);
  try {
    const fd = new FormData();
    fd.append('phone',currentPhone); fd.append('code',code); fd.append('password',password);
    const res  = await fetch('/api/verify',{method:'POST',body:fd});
    const data = await res.json();
    prog.finish();
    if(data.status==='success'){
      showResult('Telethon activated successfully! ✓',true);
      setTimeout(()=>{ location.reload(); },3000);
    } else {
      showResult(data.message||'Verification failed',false);
    }
  } catch(e){
    prog.finish();
    showResult('Connection error',false);
  } finally {
    btn.classList.remove('loading');
  }
}

function backToStep1(){
  $('step2').classList.add('hidden');
  $('step1').classList.remove('hidden');
  $('result').className='result';
}

document.addEventListener('keydown',e=>{
  if(e.key!=='Enter') return;
  if(!$('step2').classList.contains('hidden')) verify();
  else if(!$('step1').classList.contains('hidden')) sendCode();
});
</script>
</body>
</html>
"""

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
