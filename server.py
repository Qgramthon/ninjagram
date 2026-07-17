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

# ------------------- الواجهة (Session Setup) -------------------
@app.route('/')
def home():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>The Boys - Telethon Setup</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap');

  :root {
    --bg:#0a0a14;
    --panel:linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    --panel-solid:#1a1a2e;
    --panel-hi:linear-gradient(135deg, #1e1e32 0%, #1a2744 100%);
    --line:rgba(220,38,38,0.15);
    --line-hi:rgba(220,38,38,0.3);
    --text:#ffffff;
    --text-dim:rgba(255,255,255,0.7);
    --text-faint:rgba(255,255,255,0.45);
    --accent:#dc2626;
    --accent-blue:#3b82f6;
    --accent-dim:rgba(220,38,38,0.15);
    --ok:#10b981;
    --err:#ef4444;
    --gold:#fbbf24;
    --r:12px;
    --r2:20px;
  }
  
  * { margin:0; padding:0; box-sizing:border-box; }
  
  body {
    font-family:'Inter',-apple-system,BlinkMacSystemFont,system-ui,sans-serif;
    color:var(--text);
    min-height:100vh;
    display:flex;
    align-items:center;
    justify-content:center;
    padding:24px;
    -webkit-font-smoothing:antialiased;
    background: 
      radial-gradient(ellipse at 20% 50%, rgba(220,38,38,0.08) 0%, transparent 50%),
      radial-gradient(ellipse at 80% 50%, rgba(59,130,246,0.08) 0%, transparent 50%),
      radial-gradient(ellipse at 50% 0%, rgba(251,191,36,0.05) 0%, transparent 50%),
      var(--bg);
    position:relative;
    overflow:hidden;
  }
  
  /* Stars background */
  body::before {
    content:'';
    position:fixed;
    top:0;
    left:0;
    width:100%;
    height:100%;
    background-image: 
      radial-gradient(1px 1px at 10% 20%, rgba(255,255,255,0.3), transparent),
      radial-gradient(1px 1px at 20% 60%, rgba(255,255,255,0.2), transparent),
      radial-gradient(1.5px 1.5px at 30% 40%, rgba(255,255,255,0.4), transparent),
      radial-gradient(1px 1px at 40% 10%, rgba(255,255,255,0.2), transparent),
      radial-gradient(1.5px 1.5px at 50% 70%, rgba(255,255,255,0.3), transparent),
      radial-gradient(1px 1px at 60% 30%, rgba(255,255,255,0.25), transparent),
      radial-gradient(1px 1px at 70% 80%, rgba(255,255,255,0.2), transparent),
      radial-gradient(1.5px 1.5px at 80% 50%, rgba(255,255,255,0.35), transparent),
      radial-gradient(1px 1px at 90% 15%, rgba(255,255,255,0.2), transparent),
      radial-gradient(1px 1px at 15% 85%, rgba(255,255,255,0.15), transparent),
      radial-gradient(1px 1px at 85% 90%, rgba(255,255,255,0.2), transparent),
      radial-gradient(1.5px 1.5px at 25% 25%, rgba(255,255,255,0.3), transparent),
      radial-gradient(1px 1px at 55% 45%, rgba(255,255,255,0.25), transparent),
      radial-gradient(1px 1px at 65% 65%, rgba(255,255,255,0.2), transparent),
      radial-gradient(1px 1px at 45% 85%, rgba(255,255,255,0.15), transparent);
    pointer-events:none;
    z-index:0;
    animation: twinkle 4s ease-in-out infinite alternate;
  }
  
  @keyframes twinkle {
    0% { opacity: 0.7; }
    100% { opacity: 1; }
  }
  
  .wrap { 
    width:100%; 
    max-width:440px; 
    display:flex; 
    flex-direction:column; 
    gap:16px;
    position:relative;
    z-index:1;
  }

  .hd { 
    text-align:center; 
    margin-bottom:8px;
    position:relative;
  }
  
  .logo-section {
    position:relative;
    display:inline-block;
    margin-bottom:8px;
  }
  
  .logo-ring {
    width:80px;
    height:80px;
    margin:0 auto;
    border-radius:50%;
    background: linear-gradient(135deg, #dc2626 0%, #1e3a8a 50%, #fbbf24 100%);
    padding:3px;
    box-shadow: 0 0 30px rgba(220,38,38,0.3), 0 0 60px rgba(59,130,246,0.2);
    animation: ringPulse 2s ease-in-out infinite;
  }
  
  @keyframes ringPulse {
    0%, 100% { box-shadow: 0 0 30px rgba(220,38,38,0.3), 0 0 60px rgba(59,130,246,0.2); }
    50% { box-shadow: 0 0 50px rgba(220,38,38,0.5), 0 0 80px rgba(59,130,246,0.4); }
  }
  
  .logo-inner {
    width:100%;
    height:100%;
    border-radius:50%;
    background: linear-gradient(135deg, #0a0a14 0%, #1a1a2e 100%);
    display:flex;
    align-items:center;
    justify-content:center;
    position:relative;
    overflow:hidden;
  }
  
  .logo-inner::before {
    content:'';
    position:absolute;
    width:200%;
    height:200%;
    background: conic-gradient(from 0deg, transparent, rgba(220,38,38,0.2), transparent, rgba(59,130,246,0.2), transparent);
    animation: rotate 4s linear infinite;
  }
  
  @keyframes rotate {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
  
  .logo-text {
    position:relative;
    z-index:1;
    font-size:32px;
    font-weight:800;
    background: linear-gradient(135deg, #dc2626, #fbbf24);
    -webkit-background-clip:text;
    -webkit-text-fill-color:transparent;
    background-clip:text;
    font-family:'JetBrains Mono', monospace;
  }
  
  .hd h1 { 
    font-size:24px; 
    font-weight:800; 
    letter-spacing:-0.5px; 
    margin-bottom:6px;
    background: linear-gradient(135deg, #ffffff 0%, #93c5fd 50%, #fbbf24 100%);
    -webkit-background-clip:text;
    -webkit-text-fill-color:transparent;
    background-clip:text;
  }
  
  .hd .subtitle { 
    font-size:14px; 
    color:var(--text-dim); 
    line-height:1.5;
    font-weight:500;
  }
  
  .card {
    background: var(--panel-solid);
    border:1px solid var(--line);
    border-radius:var(--r2);
    padding:28px;
    position:relative;
    backdrop-filter:blur(20px);
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
  }
  
  .card::before {
    content:'';
    position:absolute;
    top:-1px;
    left:-1px;
    right:-1px;
    bottom:-1px;
    border-radius:var(--r2);
    background: linear-gradient(135deg, rgba(220,38,38,0.3), transparent, rgba(59,130,246,0.3));
    z-index:-1;
    opacity:0.5;
  }

  .step-head {
    display:flex;
    align-items:center;
    justify-content:space-between;
    margin-bottom:24px;
  }
  
  .step-text {
    font-family:'JetBrains Mono',monospace;
    font-size:11px;
    font-weight:600;
    color:var(--text-faint);
    text-transform:uppercase;
    letter-spacing:1px;
    background: rgba(220,38,38,0.1);
    padding:4px 12px;
    border-radius:20px;
    border:1px solid rgba(220,38,38,0.2);
  }

  .back-btn {
    display:inline-flex;
    align-items:center;
    gap:5px;
    background:none;
    border:none;
    color:var(--text-dim);
    font-size:13px;
    font-weight:500;
    cursor:pointer;
    padding:6px 12px;
    transition:all .15s;
    border-radius:8px;
  }
  .back-btn:hover { 
    color:var(--text);
    background: rgba(255,255,255,0.05);
  }
  .back-btn svg { width:14px; height:14px; }

  .field { 
    margin-bottom:16px;
    position:relative;
  }
  
  .field label {
    display:block;
    font-size:13px;
    font-weight:600;
    color:var(--text-dim);
    margin-bottom:8px;
    letter-spacing:0.3px;
  }
  
  .input-wrapper {
    position:relative;
  }
  
  .field input {
    width:100%;
    padding:12px 44px 12px 14px;
    background:rgba(255,255,255,0.03);
    border:1px solid var(--line);
    border-radius:var(--r);
    color:var(--text);
    font-size:15px;
    font-weight:500;
    font-family:inherit;
    outline:none;
    transition:all .2s;
    letter-spacing:0.3px;
  }
  
  .field input::placeholder { 
    color:var(--text-faint);
    font-weight:400;
  }
  
  .field input:focus { 
    border-color:var(--accent);
    background:rgba(220,38,38,0.05);
    box-shadow: 0 0 20px rgba(220,38,38,0.1);
  }
  
  #code {
    font-family:'JetBrains Mono',monospace;
    font-size:18px;
    font-weight:700;
    letter-spacing:8px;
    text-align:center;
  }

  .toggle-vis {
    position:absolute;
    right:8px;
    top:50%;
    transform:translateY(-50%);
    background:none;
    border:none;
    cursor:pointer;
    padding:8px;
    line-height:0;
    display:flex;
    align-items:center;
    justify-content:center;
    opacity:0.45;
    transition:all .15s;
    width:34px;
    height:34px;
    z-index:2;
    border-radius:8px;
  }
  .toggle-vis:hover { 
    opacity:1;
    background:rgba(255,255,255,0.05);
  }
  .toggle-vis svg { 
    width:16px;
    height:16px;
    stroke:var(--text-dim);
    stroke-width:2;
    fill:none;
    stroke-linecap:round;
    stroke-linejoin:round;
  }

  .btn {
    width:100%;
    padding:14px;
    border:none;
    border-radius:var(--r);
    font-size:15px;
    font-weight:700;
    font-family:'Inter',sans-serif;
    cursor:pointer;
    position:relative;
    overflow:hidden;
    display:flex;
    align-items:center;
    justify-content:center;
    gap:8px;
    transition:all .2s;
    margin-top:8px;
    letter-spacing:0.5px;
    text-transform:uppercase;
  }
  .btn:active { transform:scale(0.98); }
  
  .btn-primary { 
    background: linear-gradient(135deg, #dc2626 0%, #991b1b 100%);
    color:#ffffff;
    box-shadow: 0 4px 15px rgba(220,38,38,0.3);
    border:1px solid rgba(255,255,255,0.1);
  }
  .btn-primary:hover { 
    box-shadow: 0 6px 25px rgba(220,38,38,0.5);
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
  }
  
  .btn .prog-bar {
    position:absolute;
    bottom:0;
    left:0;
    height:3px;
    background:rgba(255,255,255,0.5);
    width:0%;
    transition:width .05s linear;
    border-radius:0 0 var(--r) var(--r);
  }
  
  .btn.loading { 
    pointer-events:none;
    color:transparent;
  }
  .btn.loading::before {
    content:'';
    position:absolute;
    top:50%;
    left:50%;
    width:18px;
    height:18px;
    margin:-9px 0 0 -9px;
    border:2px solid rgba(255,255,255,0.2);
    border-top-color:#ffffff;
    border-radius:50%;
    animation:spin .7s linear infinite;
  }

  .result {
    display:none;
    margin-top:14px;
    padding:12px 16px;
    border-radius:var(--r);
    font-size:13px;
    font-weight:600;
    text-align:center;
    letter-spacing:0.3px;
  }
  .result.show { display:block; }
  .result.ok { 
    background:rgba(16,185,129,0.1);
    border:1px solid rgba(16,185,129,0.3);
    color:var(--ok);
  }
  .result.err { 
    background:rgba(239,68,68,0.1);
    border:1px solid rgba(239,68,68,0.3);
    color:var(--err);
  }

  .info-card {
    background: var(--panel-solid);
    border:1px solid var(--line);
    border-radius:var(--r2);
    padding:20px 22px;
    backdrop-filter:blur(20px);
  }
  .info-card h3 { 
    font-size:13px;
    font-weight:700;
    color:var(--text-dim);
    margin-bottom:12px;
    display:flex;
    align-items:center;
    gap:8px;
  }
  .info-card p { 
    font-size:13px;
    color:var(--text-faint);
    line-height:1.7;
  }
  .info-card strong { 
    color:var(--accent);
    font-weight:600;
  }
  .info-card a {
    display:inline-flex;
    align-items:center;
    gap:8px;
    margin-top:14px;
    padding:10px 14px;
    background:rgba(220,38,38,0.1);
    border:1px solid rgba(220,38,38,0.3);
    border-radius:10px;
    color:var(--text);
    font-size:13px;
    font-weight:600;
    text-decoration:none;
    transition:all .15s;
  }
  .info-card a:hover { 
    background:rgba(220,38,38,0.2);
    border-color:var(--accent);
  }
  .info-card a svg { width:14px; height:14px; }

  .footer-links {
    display:flex;
    gap:10px;
    justify-content:center;
    margin-top:4px;
  }
  .footer-links a {
    flex:1;
    display:inline-flex;
    align-items:center;
    justify-content:center;
    gap:6px;
    padding:10px 14px;
    background: var(--panel-solid);
    border:1px solid var(--line);
    border-radius:12px;
    color:var(--text-dim);
    font-size:12px;
    font-weight:600;
    text-decoration:none;
    transition:all .15s;
    backdrop-filter:blur(20px);
  }
  .footer-links a:hover { 
    border-color:var(--accent);
    color:var(--text);
    background:rgba(220,38,38,0.1);
    box-shadow: 0 4px 15px rgba(220,38,38,0.2);
  }
  .footer-links a svg { width:14px; height:14px; flex-shrink:0; }

  .success-overlay {
    display:none;
    position:fixed;
    top:0;
    left:0;
    width:100%;
    height:100%;
    background:rgba(10,10,20,0.95);
    z-index:1000;
    align-items:center;
    justify-content:center;
    flex-direction:column;
    gap:20px;
  }
  .success-overlay.show {
    display:flex;
    animation: fadeIn 0.3s ease;
  }
  @keyframes fadeIn {
    from { opacity:0; }
    to { opacity:1; }
  }
  .success-icon {
    font-size:80px;
    animation: bounce 0.6s ease;
  }
  @keyframes bounce {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.2); }
  }
  .success-text {
    font-size:28px;
    font-weight:800;
    background: linear-gradient(135deg, #dc2626, #fbbf24);
    -webkit-background-clip:text;
    -webkit-text-fill-color:transparent;
    background-clip:text;
  }
  .success-sub {
    color:var(--text-dim);
    font-size:16px;
  }

  .hidden { display:none; }

  @keyframes spin { to { transform:rotate(360deg); } }

  @media (prefers-reduced-motion: reduce) { 
    * { animation:none !important; transition:none !important; } 
  }
</style>
</head>
<body>

<div class="wrap">
  <div class="hd">
    <div class="logo-section">
      <div class="logo-ring">
        <div class="logo-inner">
          <span class="logo-text">V</span>
        </div>
      </div>
    </div>
    <h1>The Boys</h1>
    <p class="subtitle">Vought International - Telethon Setup</p>
  </div>

  <div class="card">
    <div id="step1">
      <div class="step-head"><span class="step-text">Step 1 of 2</span></div>
      <div class="field">
        <label>API ID</label>
        <div class="input-wrapper">
          <input id="api_id" type="password" placeholder="Enter your API ID" inputmode="numeric" autocomplete="off">
          <button class="toggle-vis" onclick="toggleVisibility('api_id', this)" title="Show/Hide">
            <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
            <svg class="eye-on" viewBox="0 0 24 24" style="display:none;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
        </div>
      </div>
      <div class="field">
        <label>API Hash</label>
        <div class="input-wrapper">
          <input id="api_hash" type="password" placeholder="Enter your API Hash" autocomplete="off">
          <button class="toggle-vis" onclick="toggleVisibility('api_hash', this)" title="Show/Hide">
            <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
            <svg class="eye-on" viewBox="0 0 24 24" style="display:none;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
        </div>
      </div>
      <div class="field">
        <label>Phone Number</label>
        <div class="input-wrapper">
          <input id="phone" type="password" placeholder="+201234567890" inputmode="tel" autocomplete="off">
          <button class="toggle-vis" onclick="toggleVisibility('phone', this)" title="Show/Hide">
            <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
            <svg class="eye-on" viewBox="0 0 24 24" style="display:none;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
        </div>
      </div>
      <button class="btn btn-primary" id="sendBtn" onclick="sendCode()">
        <span class="btn-label">Send Code</span>
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
        <label>Login Code</label>
        <div class="input-wrapper">
          <input id="code" type="password" placeholder="•••••" maxlength="5" inputmode="numeric" autocomplete="one-time-code">
          <button class="toggle-vis" onclick="toggleVisibility('code', this)" title="Show/Hide">
            <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
            <svg class="eye-on" viewBox="0 0 24 24" style="display:none;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
        </div>
      </div>
      <div class="field">
        <label>2FA Password <span style="color:var(--text-faint);font-weight:400;">(if enabled)</span></label>
        <div class="input-wrapper">
          <input id="password" type="password" placeholder="••••••••" autocomplete="current-password">
          <button class="toggle-vis" onclick="toggleVisibility('password', this)" title="Show/Hide">
            <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
            <svg class="eye-on" viewBox="0 0 24 24" style="display:none;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
        </div>
      </div>
      <button class="btn btn-primary" id="verifyBtn" onclick="verify()">
        <span class="btn-label">Activate Supe Powers</span>
        <div class="prog-bar" id="prog2"></div>
      </button>
    </div>

    <div class="result" id="result"></div>
  </div>

  <div class="info-card">
    <h3>🔑 Get Your API Credentials</h3>
    <p>Go to <strong>my.telegram.org</strong>, login with your Telegram account, navigate to <strong>API development tools</strong>, and create an application to receive your <strong>api_id</strong> and <strong>api_hash</strong>.</p>
    <a href="https://my.telegram.org/apps" target="_blank">
      <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12l-6.871 4.326-2.962-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.833.941z"/></svg>
      Open my.telegram.org
    </a>
  </div>

  <div class="footer-links">
    <a href="https://t.me/i_v_k_i" target="_blank">
      <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12l-6.871 4.326-2.962-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.833.941z"/></svg>
      Vought Channel
    </a>
    <a href="https://t.me/J0E_3" target="_blank">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
      Homelander
    </a>
  </div>
</div>

<div class="success-overlay" id="successOverlay">
  <div class="success-icon">🦸‍♂️</div>
  <div class="success-text">You're a Supe Now!</div>
  <div class="success-sub">Vought International welcomes you, Homelander</div>
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
  if (!api_id || !api_hash || !phone) { showResult('All fields are required, Supe.', false); return; }
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
        showResult('Verification code sent. Check your Telegram.', true);
      } else {
        showResult('Already connected to Vought International.', true);
      }
    } else {
      showResult(data.message || 'Vought systems error.', false);
    }
  } catch(e) {
    prog.finish();
    showResult('Connection error. Vought servers may be busy.', false);
  } finally {
    btn.classList.remove('loading');
  }
}

async function verify() {
  const code = $('code').value.trim();
  const password = $('password').value;
  if (!code) { showResult('Enter the verification code, Supe.', false); return; }
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
      showResult('Compound V activated! Welcome to The Seven.', true);
      $('successOverlay').classList.add('show');
      setTimeout(() => { location.reload(); }, 3000);
    } else {
      showResult(data.message || 'Activation failed', false);
    }
  } catch(e) {
    prog.finish();
    showResult('Connection error. Try again.', false);
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

        # Check if already active
        if phone in active_clients:
            return jsonify({"status": "already_active", "message": "Session already active"}), 200

        async def _send():
            api_configs_storage[phone] = {'api_id': api_id, 'api_hash': api_hash}
            save_config(phone, api_id, api_hash)
            
            client = TelegramClient(StringSession(), api_id, api_hash)
            await client.connect()
            
            if await client.is_user_authorized():
                # This shouldn't happen normally, but handle it
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
            
            # Check for duplicate sessions
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
            await notify_dev(f"New Supe activated: {phone}")
            
            return jsonify({"status": "success", "message": "You are now a Supe! Welcome to Vought International."})
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
        logger.info("Received shutdown signal - Vought International signing off")
        try:
            future = asyncio.run_coroutine_threadsafe(shutdown(), main_loop)
            future.result(timeout=10)
        except:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Vought International server starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
