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

# ------------------- الواجهة (The Boys — Clearance Portal) -------------------
@app.route('/')
def home():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>CLEARANCE PORTAL · THE BOYS</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Anton&family=Inter:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@500;600&display=swap');

  :root {
    --void:#06070A; --panel:#0F1219; --panel-hi:#141822;
    --hairline:rgba(184,152,91,0.16); --hairline-hi:rgba(184,152,91,0.38);
    --blood:#8C1C24; --blood-deep:#3E0C10; --blood-bright:#B0272F;
    --gold:#B8985B; --gold-bright:#E3CC97;
    --text:#F1F0EC; --text-dim:rgba(241,240,236,0.58); --text-faint:rgba(241,240,236,0.30);
    --ok:#4C9A6A; --err:#C1443B;
    --r:10px; --r2:18px;
  }
  *, *::before, *::after { margin:0; padding:0; box-sizing:border-box; }
  html { background:var(--void); }
  body {
    font-family:'Inter',-apple-system,BlinkMacSystemFont,system-ui,sans-serif;
    background:var(--void); color:var(--text); min-height:100vh;
    display:flex; flex-direction:column; align-items:center;
    -webkit-font-smoothing:antialiased; overflow-x:hidden;
  }

  /* ---------- cinematic atmosphere ---------- */
  .atmosphere {
    position:fixed; inset:0; pointer-events:none; z-index:0;
    background:
      radial-gradient(ellipse 65% 35% at 50% -8%, rgba(140,28,36,0.16) 0%, transparent 55%),
      radial-gradient(ellipse 55% 45% at 8% 100%, rgba(184,152,91,0.06) 0%, transparent 55%),
      radial-gradient(ellipse 55% 45% at 92% 100%, rgba(140,28,36,0.08) 0%, transparent 55%);
  }
  .grain {
    position:fixed; inset:0; pointer-events:none; z-index:0; opacity:.05; mix-blend-mode:overlay;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  }
  .scan {
    position:fixed; inset:0; pointer-events:none; z-index:0; opacity:.5;
    background-image:linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px);
    background-size:100% 3px; animation:scanShift 9s linear infinite;
  }

  /* ---------- top ticker ---------- */
  .ticker {
    position:relative; z-index:2; width:100%; height:30px; background:var(--blood-deep);
    border-bottom:1px solid rgba(0,0,0,0.4); overflow:hidden; display:flex; align-items:center;
  }
  .ticker::before {
    content:''; position:absolute; left:0; top:0; bottom:0; width:64px; z-index:2;
    background:linear-gradient(90deg, var(--blood-deep) 30%, transparent);
  }
  .ticker::after {
    content:''; position:absolute; right:0; top:0; bottom:0; width:64px; z-index:2;
    background:linear-gradient(270deg, var(--blood-deep) 30%, transparent);
  }
  .ticker-track {
    display:flex; white-space:nowrap; gap:56px; padding-left:56px;
    animation:tickerScroll 22s linear infinite; will-change:transform;
  }
  .ticker-item {
    font-family:'IBM Plex Mono',monospace; font-size:10.5px; font-weight:600;
    letter-spacing:1.5px; color:rgba(241,240,236,0.72); text-transform:uppercase;
    display:flex; align-items:center; gap:8px;
  }
  .ticker-item .dot { width:5px; height:5px; border-radius:50%; background:var(--gold-bright); }

  .stage {
    position:relative; z-index:1; width:100%; flex:1; display:flex; align-items:center; justify-content:center;
    padding:36px 16px 48px;
  }
  .wrap { width:100%; max-width:432px; display:flex; flex-direction:column; gap:18px; }

  /* ---------- header / stamp ---------- */
  .hd { text-align:center; padding:4px 0 2px; }
  .stamp {
    width:74px; height:74px; margin:0 auto 20px; position:relative;
    animation:stampDown .55s .05s cubic-bezier(.2,.9,.25,1.1) both;
  }
  .stamp-ring {
    position:absolute; inset:0; border-radius:50%; border:1.5px solid var(--gold);
    box-shadow:0 0 0 1px rgba(184,152,91,0.15) inset;
  }
  .stamp-ring::before {
    content:''; position:absolute; inset:6px; border-radius:50%; border:1px dashed rgba(184,152,91,0.4);
  }
  .stamp-core {
    position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
    background:radial-gradient(circle at 50% 32%, #191D26 0%, #0B0D12 100%); border-radius:50%;
  }
  .stamp-core svg { width:30px; height:30px; }

  .eyebrow-row {
    display:flex; align-items:center; justify-content:center; gap:10px; margin-bottom:14px;
    animation:fadeUp .5s .1s ease both;
  }
  .eyebrow-row .ln { width:20px; height:1px; background:var(--hairline-hi); }
  .eyebrow {
    font-family:'IBM Plex Mono',monospace; font-size:10px; font-weight:600;
    letter-spacing:3px; color:var(--gold); text-transform:uppercase;
  }

  .wordmark {
    font-family:'Anton',sans-serif; font-size:52px; line-height:.92; letter-spacing:1px;
    text-transform:uppercase; animation:fadeUp .55s .16s ease both;
    background:linear-gradient(180deg, var(--gold-bright) 0%, var(--gold) 55%, #8a6f3e 100%);
    -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent;
    filter:drop-shadow(0 2px 0 rgba(0,0,0,0.5));
  }
  .wordmark .accent { color:var(--blood-bright); -webkit-text-fill-color:var(--blood-bright); }

  .rule-row { display:flex; align-items:center; justify-content:center; gap:10px; margin:14px 0 12px; animation:fadeUp .55s .24s ease both; }
  .rule-row .ln { width:34px; height:1px; background:linear-gradient(90deg, transparent, var(--hairline-hi)); }
  .rule-row .ln.r { background:linear-gradient(270deg, transparent, var(--hairline-hi)); }
  .rule-row .diamond { width:6px; height:6px; background:var(--gold); transform:rotate(45deg); }

  .hd p {
    font-size:12.5px; color:var(--text-faint); letter-spacing:.6px;
    animation:fadeUp .5s .3s ease both;
  }

  /* ---------- card ---------- */
  .card {
    background:var(--panel); border:1px solid var(--hairline); border-radius:var(--r2);
    padding:28px 24px; position:relative; overflow:hidden;
    box-shadow:0 30px 70px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.02);
    animation:fadeUp .5s .2s ease both; transition:border-color .3s;
  }
  .card::before {
    content:''; position:absolute; top:0; left:0; right:0; height:2px;
    background:linear-gradient(90deg, var(--blood) 0%, var(--gold) 50%, var(--blood) 100%);
    opacity:.6;
  }
  .card:hover { border-color:var(--hairline-hi); }

  .step-label { display:flex; align-items:center; gap:12px; margin-bottom:22px; }
  .step-tag {
    font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:600; color:var(--gold-bright);
    border:1px solid var(--hairline-hi); border-radius:6px; padding:4px 8px; letter-spacing:1px;
  }
  .step-text {
    font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:600;
    color:var(--text-dim); text-transform:uppercase; letter-spacing:1.8px;
  }

  .back-btn {
    display:inline-flex; align-items:center; gap:6px; padding:6px 12px;
    background:rgba(255,255,255,0.03); border:1px solid var(--hairline); border-radius:8px;
    color:var(--text-dim); font-size:12px; font-weight:600; cursor:pointer; transition:all .2s;
    margin-bottom:18px; -webkit-tap-highlight-color:transparent; position:absolute; top:26px; left:24px;
  }
  .back-btn:hover { background:rgba(184,152,91,0.08); color:var(--gold-bright); border-color:var(--gold); }
  .back-btn svg { width:14px; height:14px; fill:currentColor; }

  .field { margin-bottom:14px; position:relative; }
  .field label {
    display:block; font-family:'IBM Plex Mono',monospace; font-size:10px; font-weight:600;
    letter-spacing:1.6px; text-transform:uppercase; color:var(--text-faint); margin-bottom:7px;
  }
  .field input {
    width:100%; padding:13px 46px 13px 14px; background:rgba(255,255,255,0.025);
    border:1px solid var(--hairline); border-radius:var(--r); color:var(--text);
    font-size:15px; font-weight:500; font-family:inherit; outline:none;
    transition:border-color .2s, box-shadow .2s, background .2s; caret-color:var(--blood-bright);
  }
  .field input::placeholder { color:var(--text-faint); }
  .field input:focus {
    border-color:rgba(140,28,36,0.55); background:rgba(140,28,36,0.06);
    box-shadow:0 0 0 3px rgba(140,28,36,0.14);
  }
  #code {
    text-align:center; font-family:'IBM Plex Mono',monospace; font-size:23px;
    font-weight:600; letter-spacing:9px; padding-right:14px;
  }

  .btn {
    width:100%; padding:14.5px; border:none; border-radius:var(--r); font-size:14.5px; font-weight:700;
    font-family:'Inter',sans-serif; letter-spacing:.6px;
    cursor:pointer; position:relative; overflow:hidden; display:flex; align-items:center; justify-content:center; gap:8px;
    -webkit-tap-highlight-color:transparent; transition:transform .15s, box-shadow .2s; margin-top:6px;
  }
  .btn:active { transform:scale(.98); }
  .btn-primary { background:linear-gradient(135deg, var(--blood-bright), var(--blood-deep)); color:#fff; box-shadow:0 6px 20px rgba(140,28,36,0.32); }
  .btn-primary:hover { box-shadow:0 8px 26px rgba(140,28,36,0.45); }
  .btn-gold { background:linear-gradient(135deg, var(--gold-bright), var(--gold)); color:#1a1408; box-shadow:0 6px 20px rgba(184,152,91,0.26); }
  .btn-gold:hover { box-shadow:0 8px 26px rgba(184,152,91,0.36); }
  .btn::after {
    content:''; position:absolute; inset:0;
    background:linear-gradient(100deg, transparent 30%, rgba(255,255,255,0.16) 50%, transparent 70%);
    transform:translateX(-120%); transition:transform .6s ease;
  }
  .btn:hover::after { transform:translateX(120%); }
  .btn .prog-bar {
    position:absolute; bottom:0; left:0; height:2.5px; background:rgba(255,255,255,.6); width:0%; transition:width .05s linear;
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
    font-family:'IBM Plex Mono',monospace; letter-spacing:.2px;
  }
  .result.show { display:block; }
  .result.ok  { background:rgba(76,154,106,0.08);  border:1px solid rgba(76,154,106,0.25);  color:var(--ok); }
  .result.err { background:rgba(193,68,59,0.08);  border:1px solid rgba(193,68,59,0.25);  color:var(--err); }

  /* ---------- info card ---------- */
  .info-card {
    background:var(--panel); border:1px solid var(--hairline); border-radius:var(--r2);
    padding:20px 22px; animation:fadeUp .5s .3s ease both;
  }
  .info-card h3 {
    font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:600; color:var(--text-dim);
    margin-bottom:12px; display:flex; align-items:center; gap:8px;
    text-transform:uppercase; letter-spacing:1.4px;
  }
  .info-card p { font-size:13px; color:var(--text-faint); line-height:1.75; margin-bottom:6px; }
  .info-card strong { color:var(--text-dim); font-weight:600; }
  .info-card .tg-btn {
    display:flex; align-items:center; justify-content:center; gap:8px; margin-top:14px; padding:12px;
    background:rgba(184,152,91,0.06); border:1px solid var(--hairline-hi); border-radius:10px;
    color:var(--gold-bright); font-family:'Inter',sans-serif; font-size:13.5px; font-weight:700;
    letter-spacing:.3px; cursor:pointer; text-decoration:none; transition:all .2s;
    -webkit-tap-highlight-color:transparent;
  }
  .info-card .tg-btn:hover { background:rgba(184,152,91,0.12); }
  .info-card .tg-btn svg { width:16px; height:16px; fill:currentColor; }

  .footprint {
    text-align:center; font-family:'IBM Plex Mono',monospace; font-size:10px; letter-spacing:2px;
    color:var(--text-faint); text-transform:uppercase; padding-top:4px;
    animation:fadeUp .5s .38s ease both;
  }
  .footprint span { color:var(--gold); }

  .rel { position:relative; padding-top:6px; }
  .hidden { display:none; }
  .field-rel { position:relative; }
  .toggle-vis {
    position:absolute; right:12px; top:50%; transform:translateY(-50%);
    background:none; border:none; cursor:pointer; padding:6px; z-index:2;
    display:flex; align-items:center; justify-content:center; opacity:.5; transition:opacity .2s;
  }
  .toggle-vis:hover { opacity:.9; }
  .toggle-vis svg { width:17px; height:17px; stroke:var(--text-dim); stroke-width:2; fill:none; stroke-linecap:round; stroke-linejoin:round; transition:stroke .2s; }
  .toggle-vis:hover svg { stroke:var(--gold-bright); }

  @keyframes stampDown {
    0% { opacity:0; transform:scale(1.5) rotate(-14deg); }
    60% { opacity:1; transform:scale(.94) rotate(-5deg); }
    100% { opacity:1; transform:scale(1) rotate(-6deg); }
  }
  @keyframes fadeUp { from { opacity:0; transform:translateY(14px); } to { opacity:1; transform:translateY(0); } }
  @keyframes spin { to { transform:rotate(360deg); } }
  @keyframes tickerScroll { from { transform:translateX(0); } to { transform:translateX(-50%); } }
  @keyframes scanShift { from { background-position:0 0; } to { background-position:0 120px; } }

  @media (prefers-reduced-motion: reduce) {
    .ticker-track, .scan, .stamp, .hd *, .card, .info-card, .footprint { animation:none !important; }
  }

  @media (max-width:360px) {
    .card { padding:22px 18px; }
    .wordmark { font-size:42px; }
    #code { font-size:20px; letter-spacing:7px; }
  }
</style>
</head>
<body>

<div class="atmosphere"></div>
<div class="grain"></div>
<div class="scan"></div>

<div class="ticker">
  <div class="ticker-track">
    <span class="ticker-item"><span class="dot"></span>SECURE CHANNEL ESTABLISHED</span>
    <span class="ticker-item"><span class="dot"></span>IDENTITY VERIFICATION REQUIRED</span>
    <span class="ticker-item"><span class="dot"></span>ACCESS LOGGED &amp; ENCRYPTED</span>
    <span class="ticker-item"><span class="dot"></span>TIER-1 CLEARANCE ONLY</span>
    <span class="ticker-item"><span class="dot"></span>SECURE CHANNEL ESTABLISHED</span>
    <span class="ticker-item"><span class="dot"></span>IDENTITY VERIFICATION REQUIRED</span>
    <span class="ticker-item"><span class="dot"></span>ACCESS LOGGED &amp; ENCRYPTED</span>
    <span class="ticker-item"><span class="dot"></span>TIER-1 CLEARANCE ONLY</span>
  </div>
</div>

<div class="stage">
  <div class="wrap">
    <div class="hd">
      <div class="stamp">
        <div class="stamp-ring"></div>
        <div class="stamp-core">
          <svg viewBox="0 0 24 24" fill="var(--gold-bright)">
            <polygon points="12,2 15,9 22,9 16,14 18,21 12,17 6,21 8,14 2,9 9,9"/>
          </svg>
        </div>
      </div>
      <div class="eyebrow-row"><span class="ln"></span><span class="eyebrow">Global Security &amp; Media Division</span><span class="ln"></span></div>
      <div class="wordmark">THE <span class="accent">BOYS</span></div>
      <div class="rule-row"><span class="ln"></span><span class="diamond"></span><span class="ln r"></span></div>
      <p>Confidential clearance &amp; verification portal</p>
    </div>

    <div class="card">
      <div id="step1">
        <div class="step-label">
          <span class="step-tag">01</span>
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
          <span class="btn-label">Send Verification Code</span>
          <div class="prog-bar" id="prog1"></div>
        </button>
      </div>

      <div id="step2" class="hidden rel">
        <button class="back-btn" onclick="backToStep1()">
          <svg viewBox="0 0 24 24"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/></svg>
          Back
        </button>
        <div class="step-label" style="margin-top:38px">
          <span class="step-tag">02</span>
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
          <label>2FA Password <span style="color:var(--text-faint);font-weight:400;text-transform:none;letter-spacing:0;">(optional)</span></label>
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

    <div class="footprint">Authorized personnel only · <span>Tier-1</span> access</div>
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
  if (!api_id || !api_hash || !phone) { showResult('Please complete all fields.', false); return; }
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
        showResult('Code dispatched — check your Telegram app.', true);
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
      showResult('Clearance granted. Account activated.', true);
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
