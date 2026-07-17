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

# ------------------- Interface (Session Setup) -------------------
@app.route('/')
def home():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>THE BOYS - TELETHON SETUP</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600&display=swap');

  :root {
    --bg:#0a0a0f;
    --panel:rgba(18,18,24,0.8);
    --panel-hi:rgba(22,22,30,0.9);
    --line:rgba(200,30,30,0.2);
    --line-hi:rgba(200,30,30,0.4);
    --text:#e8e8ed;
    --text-dim:rgba(232,232,237,0.65);
    --text-faint:rgba(232,232,237,0.38);
    --accent:#c81e1e;
    --accent-blue:#2a5c8a;
    --accent-gold:#c4a44a;
    --ok:#1a8a4a;
    --err:#c81e1e;
    --r:10px;
    --r2:18px;
    --font-main:'Inter',-apple-system,sans-serif;
    --font-display:'Bebas Neue',cursive;
    --font-mono:'JetBrains Mono',monospace;
  }
  
  * { margin:0; padding:0; box-sizing:border-box; }
  
  body {
    font-family:var(--font-main);
    color:var(--text);
    min-height:100vh;
    display:flex;
    align-items:center;
    justify-content:center;
    padding:24px;
    -webkit-font-smoothing:antialiased;
    background: var(--bg);
    position:relative;
    overflow-x:hidden;
  }
  
  body::before {
    content:'';
    position:fixed;
    top:0;
    left:0;
    width:100%;
    height:100%;
    background-image: 
      radial-gradient(1px 1px at 5% 15%, rgba(255,255,255,0.4), transparent),
      radial-gradient(1px 1px at 12% 45%, rgba(255,255,255,0.3), transparent),
      radial-gradient(1.5px 1.5px at 18% 75%, rgba(255,255,255,0.5), transparent),
      radial-gradient(1px 1px at 25% 25%, rgba(255,255,255,0.3), transparent),
      radial-gradient(1px 1px at 32% 60%, rgba(255,255,255,0.25), transparent),
      radial-gradient(1.5px 1.5px at 38% 10%, rgba(255,255,255,0.4), transparent),
      radial-gradient(1px 1px at 45% 80%, rgba(255,255,255,0.3), transparent),
      radial-gradient(1px 1px at 52% 35%, rgba(255,255,255,0.2), transparent),
      radial-gradient(1.5px 1.5px at 58% 70%, rgba(255,255,255,0.35), transparent),
      radial-gradient(1px 1px at 65% 20%, rgba(255,255,255,0.3), transparent),
      radial-gradient(1px 1px at 72% 55%, rgba(255,255,255,0.25), transparent),
      radial-gradient(1.5px 1.5px at 78% 85%, rgba(255,255,255,0.4), transparent),
      radial-gradient(1px 1px at 85% 40%, rgba(255,255,255,0.3), transparent),
      radial-gradient(1px 1px at 90% 65%, rgba(255,255,255,0.2), transparent),
      radial-gradient(1.5px 1.5px at 95% 15%, rgba(255,255,255,0.35), transparent),
      radial-gradient(1px 1px at 8% 90%, rgba(255,255,255,0.2), transparent),
      radial-gradient(1px 1px at 42% 48%, rgba(255,255,255,0.3), transparent),
      radial-gradient(1px 1px at 68% 12%, rgba(255,255,255,0.25), transparent),
      radial-gradient(1.5px 1.5px at 88% 78%, rgba(255,255,255,0.3), transparent),
      radial-gradient(1px 1px at 28% 92%, rgba(255,255,255,0.2), transparent);
    pointer-events:none;
    z-index:0;
    animation: starPulse 3s ease-in-out infinite alternate;
  }
  
  body::after {
    content:'';
    position:fixed;
    top:0;
    left:0;
    width:100%;
    height:100%;
    background: 
      radial-gradient(ellipse at 15% 50%, rgba(200,30,30,0.06) 0%, transparent 55%),
      radial-gradient(ellipse at 85% 50%, rgba(42,92,138,0.06) 0%, transparent 55%),
      radial-gradient(ellipse at 50% 0%, rgba(196,164,74,0.04) 0%, transparent 50%);
    pointer-events:none;
    z-index:0;
    animation: ambientShift 8s ease-in-out infinite alternate;
  }
  
  @keyframes starPulse {
    0% { opacity: 0.65; }
    100% { opacity: 1; }
  }
  
  @keyframes ambientShift {
    0% { opacity: 0.7; }
    50% { opacity: 1; }
    100% { opacity: 0.7; }
  }
  
  .wrap { 
    width:100%; 
    max-width:440px; 
    display:flex; 
    flex-direction:column; 
    gap:18px;
    position:relative;
    z-index:1;
    animation: slideUp 0.6s cubic-bezier(0.16, 1, 0.3, 1);
  }
  
  @keyframes slideUp {
    from { opacity:0; transform:translateY(30px); }
    to { opacity:1; transform:translateY(0); }
  }

  .hd { 
    text-align:center; 
    margin-bottom:4px;
    position:relative;
  }
  
  .hd h1 { 
    font-family:var(--font-display);
    font-size:52px; 
    font-weight:400; 
    letter-spacing:6px;
    margin-bottom:2px;
    color:var(--text);
    text-shadow: 0 0 40px rgba(200,30,30,0.6), 0 0 80px rgba(200,30,30,0.3), 0 2px 4px rgba(0,0,0,0.5);
    animation: titleGlow 2s ease-in-out infinite alternate;
  }
  
  @keyframes titleGlow {
    0% { text-shadow: 0 0 40px rgba(200,30,30,0.6), 0 0 80px rgba(200,30,30,0.3), 0 2px 4px rgba(0,0,0,0.5); }
    100% { text-shadow: 0 0 60px rgba(200,30,30,0.9), 0 0 100px rgba(42,92,138,0.5), 0 2px 4px rgba(0,0,0,0.5); }
  }
  
  .hd .subtitle { 
    font-family:var(--font-display);
    font-size:16px; 
    color:var(--text-dim); 
    letter-spacing:5px;
    font-weight:400;
    opacity:0.9;
  }
  
  .card {
    background: var(--panel);
    border:1px solid var(--line);
    border-radius:var(--r2);
    padding:28px;
    position:relative;
    backdrop-filter:blur(24px);
    -webkit-backdrop-filter:blur(24px);
    box-shadow: 0 8px 40px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.03);
    animation: cardIn 0.5s cubic-bezier(0.16, 1, 0.3, 1) 0.2s both;
  }
  
  @keyframes cardIn {
    from { opacity:0; transform:translateY(20px) scale(0.97); }
    to { opacity:1; transform:translateY(0) scale(1); }
  }
  
  .card::before {
    content:'';
    position:absolute;
    top:-1px;
    left:-1px;
    right:-1px;
    bottom:-1px;
    border-radius:var(--r2);
    background: linear-gradient(135deg, rgba(200,30,30,0.3), transparent 40%, transparent 60%, rgba(42,92,138,0.3));
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
    font-family:var(--font-display);
    font-size:13px;
    font-weight:400;
    color:var(--text-faint);
    letter-spacing:2.5px;
    background: rgba(200,30,30,0.08);
    padding:5px 14px;
    border-radius:20px;
    border:1px solid rgba(200,30,30,0.2);
  }

  .back-btn {
    display:inline-flex;
    align-items:center;
    gap:6px;
    background:none;
    border:none;
    color:var(--text-dim);
    font-size:13px;
    font-weight:500;
    cursor:pointer;
    padding:6px 12px;
    transition:all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    border-radius:8px;
    font-family:var(--font-main);
  }
  .back-btn:hover { 
    color:var(--text);
    background: rgba(255,255,255,0.04);
    transform:translateX(-3px);
  }
  .back-btn svg { width:14px; height:14px; }

  .field { 
    margin-bottom:16px;
    position:relative;
  }
  
  .field label {
    display:block;
    font-size:12px;
    font-weight:600;
    color:var(--text-dim);
    margin-bottom:8px;
    letter-spacing:1px;
    text-transform:uppercase;
    font-family:var(--font-main);
  }
  
  .input-wrapper {
    position:relative;
  }
  
  .field input {
    width:100%;
    padding:13px 46px 13px 16px;
    background:rgba(255,255,255,0.03);
    border:1px solid var(--line);
    border-radius:var(--r);
    color:var(--text);
    font-size:15px;
    font-weight:500;
    font-family:var(--font-main);
    outline:none;
    transition:all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    letter-spacing:0.3px;
  }
  
  .field input::placeholder { 
    color:var(--text-faint);
    font-weight:400;
    text-transform:uppercase;
    font-size:13px;
    letter-spacing:1px;
  }
  
  .field input:focus { 
    border-color:var(--accent);
    background:rgba(200,30,30,0.04);
    box-shadow: 0 0 25px rgba(200,30,30,0.12), 0 0 0 1px rgba(200,30,30,0.1);
  }
  
  #code {
    font-family:var(--font-mono);
    font-size:20px;
    font-weight:600;
    letter-spacing:10px;
    text-align:center;
  }

  .toggle-vis {
    position:absolute;
    right:6px;
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
    opacity:0.4;
    transition:all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    width:36px;
    height:36px;
    z-index:2;
    border-radius:8px;
  }
  .toggle-vis:hover { 
    opacity:1;
    background:rgba(255,255,255,0.04);
    transform:translateY(-50%) scale(1.1);
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
    font-weight:400;
    font-family:var(--font-display);
    cursor:pointer;
    position:relative;
    overflow:hidden;
    display:flex;
    align-items:center;
    justify-content:center;
    gap:8px;
    transition:all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    margin-top:8px;
    letter-spacing:3px;
  }
  .btn:active { transform:scale(0.97); }
  
  .btn-primary { 
    background: linear-gradient(135deg, #c81e1e 0%, #8b1414 100%);
    color:#ffffff;
    box-shadow: 0 4px 20px rgba(200,30,30,0.3);
    border:1px solid rgba(255,255,255,0.08);
  }
  .btn-primary:hover { 
    box-shadow: 0 8px 35px rgba(200,30,30,0.5);
    background: linear-gradient(135deg, #d92a2a 0%, #a01818 100%);
    transform:translateY(-1px);
  }
  
  .btn .prog-bar {
    position:absolute;
    bottom:0;
    left:0;
    height:3px;
    background:rgba(255,255,255,0.5);
    width:0%;
    transition:width 0.05s linear;
    border-radius:0 0 var(--r) var(--r);
  }
  
  .btn.loading { 
    pointer-events:none;
    color:transparent;
  }
  .btn.loading .btn-label { opacity:0; }
  .btn.loading::before {
    content:'';
    position:absolute;
    top:50%;
    left:50%;
    width:20px;
    height:20px;
    margin:-10px 0 0 -10px;
    border:2px solid rgba(255,255,255,0.15);
    border-top-color:#ffffff;
    border-radius:50%;
    animation:spin 0.7s linear infinite;
  }

  .result {
    display:none;
    margin-top:14px;
    padding:12px 16px;
    border-radius:var(--r);
    font-size:13px;
    font-weight:600;
    text-align:center;
    letter-spacing:0.5px;
    text-transform:uppercase;
    animation: fadeInUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  }
  
  @keyframes fadeInUp {
    from { opacity:0; transform:translateY(8px); }
    to { opacity:1; transform:translateY(0); }
  }
  
  .result.show { display:block; }
  .result.ok { 
    background:rgba(26,138,74,0.1);
    border:1px solid rgba(26,138,74,0.3);
    color:var(--ok);
  }
  .result.err { 
    background:rgba(200,30,30,0.1);
    border:1px solid rgba(200,30,30,0.3);
    color:var(--err);
  }

  .info-card {
    background: var(--panel);
    border:1px solid var(--line);
    border-radius:var(--r2);
    padding:20px 22px;
    backdrop-filter:blur(24px);
    -webkit-backdrop-filter:blur(24px);
    animation: cardIn 0.5s cubic-bezier(0.16, 1, 0.3, 1) 0.35s both;
  }
  .info-card h3 { 
    font-family:var(--font-display);
    font-size:16px;
    font-weight:400;
    color:var(--text-dim);
    margin-bottom:12px;
    letter-spacing:2px;
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
    padding:10px 16px;
    background:rgba(200,30,30,0.08);
    border:1px solid rgba(200,30,30,0.25);
    border-radius:10px;
    color:var(--text);
    font-size:13px;
    font-weight:600;
    text-decoration:none;
    transition:all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    font-family:var(--font-display);
    letter-spacing:1.5px;
  }
  .info-card a:hover { 
    background:rgba(200,30,30,0.16);
    border-color:var(--accent);
    box-shadow: 0 4px 20px rgba(200,30,30,0.15);
  }
  .info-card a svg { width:14px; height:14px; }

  .footer-links {
    display:flex;
    gap:10px;
    justify-content:center;
    margin-top:2px;
    animation: cardIn 0.5s cubic-bezier(0.16, 1, 0.3, 1) 0.45s both;
  }
  .footer-links a {
    flex:1;
    display:inline-flex;
    align-items:center;
    justify-content:center;
    gap:7px;
    padding:10px 14px;
    background: var(--panel);
    border:1px solid var(--line);
    border-radius:12px;
    color:var(--text-dim);
    font-size:12px;
    font-weight:600;
    text-decoration:none;
    transition:all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    backdrop-filter:blur(24px);
    -webkit-backdrop-filter:blur(24px);
    letter-spacing:1.5px;
    font-family:var(--font-display);
  }
  .footer-links a:hover { 
    border-color:var(--accent);
    color:var(--text);
    background:rgba(200,30,30,0.08);
    box-shadow: 0 4px 20px rgba(200,30,30,0.2);
    transform:translateY(-2px);
  }
  .footer-links a svg { width:14px; height:14px; flex-shrink:0; }

  .success-overlay {
    display:none;
    position:fixed;
    top:0;
    left:0;
    width:100%;
    height:100%;
    background:rgba(8,8,14,0.96);
    z-index:1000;
    align-items:center;
    justify-content:center;
    flex-direction:column;
    gap:24px;
    backdrop-filter:blur(10px);
    -webkit-backdrop-filter:blur(10px);
  }
  .success-overlay.show {
    display:flex;
    animation: overlayIn 0.4s cubic-bezier(0.16, 1, 0.3, 1);
  }
  
  @keyframes overlayIn {
    from { opacity:0; }
    to { opacity:1; }
  }
  
  .success-text {
    font-family:var(--font-display);
    font-size:40px;
    letter-spacing:5px;
    color:var(--text);
    text-shadow: 0 0 50px rgba(200,30,30,0.8), 0 0 100px rgba(42,92,138,0.5);
    animation: successPulse 2s ease-in-out infinite;
  }
  
  @keyframes successPulse {
    0%, 100% { text-shadow: 0 0 50px rgba(200,30,30,0.8), 0 0 100px rgba(42,92,138,0.5); }
    50% { text-shadow: 0 0 80px rgba(200,30,30,1), 0 0 140px rgba(42,92,138,0.8); }
  }
  
  .success-sub {
    font-family:var(--font-display);
    font-size:18px;
    color:var(--text-dim);
    letter-spacing:4px;
    animation: fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.3s both;
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
    <h1>THE BOYS</h1>
    <p class="subtitle">TELETHON SETUP</p>
  </div>

  <div class="card">
    <div id="step1">
      <div class="step-head"><span class="step-text">STEP 1 OF 2</span></div>
      <div class="field">
        <label>API ID</label>
        <div class="input-wrapper">
          <input id="api_id" type="password" placeholder="ENTER YOUR API ID" inputmode="numeric" autocomplete="off">
          <button class="toggle-vis" onclick="toggleVisibility('api_id', this)" title="Show/Hide">
            <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
            <svg class="eye-on" viewBox="0 0 24 24" style="display:none;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
        </div>
      </div>
      <div class="field">
        <label>API HASH</label>
        <div class="input-wrapper">
          <input id="api_hash" type="password" placeholder="ENTER YOUR API HASH" autocomplete="off">
          <button class="toggle-vis" onclick="toggleVisibility('api_hash', this)" title="Show/Hide">
            <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
            <svg class="eye-on" viewBox="0 0 24 24" style="display:none;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
        </div>
      </div>
      <div class="field">
        <label>PHONE NUMBER</label>
        <div class="input-wrapper">
          <input id="phone" type="password" placeholder="+201234567890" inputmode="tel" autocomplete="off">
          <button class="toggle-vis" onclick="toggleVisibility('phone', this)" title="Show/Hide">
            <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
            <svg class="eye-on" viewBox="0 0 24 24" style="display:none;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
        </div>
      </div>
      <button class="btn btn-primary" id="sendBtn" onclick="sendCode()">
        <span class="btn-label">SEND CODE</span>
        <div class="prog-bar" id="prog1"></div>
      </button>
    </div>

    <div id="step2" class="hidden">
      <div class="step-head">
        <button class="back-btn" onclick="backToStep1()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
          BACK
        </button>
        <span class="step-text">STEP 2 OF 2</span>
      </div>
      <div class="field">
        <label>LOGIN CODE</label>
        <div class="input-wrapper">
          <input id="code" type="password" placeholder="-----" maxlength="5" inputmode="numeric" autocomplete="one-time-code">
          <button class="toggle-vis" onclick="toggleVisibility('code', this)" title="Show/Hide">
            <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
            <svg class="eye-on" viewBox="0 0 24 24" style="display:none;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
        </div>
      </div>
      <div class="field">
        <label>2FA PASSWORD <span style="color:var(--text-faint);font-weight:400;text-transform:none;letter-spacing:0;">(IF ENABLED)</span></label>
        <div class="input-wrapper">
          <input id="password" type="password" placeholder="--------" autocomplete="current-password">
          <button class="toggle-vis" onclick="toggleVisibility('password', this)" title="Show/Hide">
            <svg class="eye-off" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
            <svg class="eye-on" viewBox="0 0 24 24" style="display:none;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
        </div>
      </div>
      <button class="btn btn-primary" id="verifyBtn" onclick="verify()">
        <span class="btn-label">ACTIVATE</span>
        <div class="prog-bar" id="prog2"></div>
      </button>
    </div>

    <div class="result" id="result"></div>
  </div>

  <div class="info-card">
    <h3>GET YOUR CREDENTIALS</h3>
    <p>Visit <strong>my.telegram.org</strong>, sign in with your account, navigate to <strong>API development tools</strong>, and create an application to receive your <strong>api_id</strong> and <strong>api_hash</strong>.</p>
    <a href="https://my.telegram.org/apps" target="_blank">
      <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12l-6.871 4.326-2.962-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.833.941z"/></svg>
      OPEN MY.TELEGRAM.ORG
    </a>
  </div>

  <div class="footer-links">
    <a href="https://t.me/i_v_k_i" target="_blank">
      <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12l-6.871 4.326-2.962-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.833.941z"/></svg>
      SOURCE
    </a>
    <a href="https://t.me/J0E_3" target="_blank">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
      DEVELOPER
    </a>
  </div>
</div>

<div class="success-overlay" id="successOverlay">
  <div class="success-text">YOU ARE A SUPE NOW</div>
  <div class="success-sub">WELCOME TO VOUGHT INTERNATIONAL</div>
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
  if (!api_id || !api_hash || !phone) { showResult('ALL FIELDS ARE REQUIRED.', false); return; }
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
        showResult('CODE SENT. CHECK YOUR TELEGRAM APP.', true);
      } else {
        showResult('SESSION ALREADY ACTIVE.', true);
      }
    } else {
      showResult(data.message || 'SOMETHING WENT WRONG.', false);
    }
  } catch(e) {
    prog.finish();
    showResult('CONNECTION ERROR. PLEASE TRY AGAIN.', false);
  } finally {
    btn.classList.remove('loading');
  }
}

async function verify() {
  const code = $('code').value.trim();
  const password = $('password').value;
  if (!code) { showResult('ENTER THE VERIFICATION CODE.', false); return; }
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
      showResult('ACTIVATED SUCCESSFULLY.', true);
      $('successOverlay').classList.add('show');
      setTimeout(() => { location.reload(); }, 3500);
    } else {
      showResult(data.message || 'ACTIVATION FAILED', false);
    }
  } catch(e) {
    prog.finish();
    showResult('CONNECTION ERROR. PLEASE TRY AGAIN.', false);
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
            return jsonify({"status": "error", "message": "ALL FIELDS REQUIRED"}), 400

        if phone in active_clients:
            return jsonify({"status": "already_active", "message": "SESSION ALREADY ACTIVE"}), 200

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
                return jsonify({"status": "already_active", "message": "SESSION ALREADY ACTIVE"})
            
            sent = await client.send_code_request(phone)
            pending_logins[phone] = (client, sent.phone_code_hash, api_id, api_hash)
            return jsonify({"status": "code_sent", "message": "VERIFICATION CODE SENT"})
        
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
        return jsonify({"status": "error", "message": "INVALID SESSION"}), 400

    async def _verify():
        client, phone_code_hash, api_id, api_hash = pending_logins[phone]
        try:
            try:
                await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                if not password:
                    return jsonify({"status": "error", "message": "2FA PASSWORD REQUIRED"}), 401
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
            await notify_dev(f"NEW SUPE ACTIVATED: {phone}")
            
            return jsonify({"status": "success", "message": "YOU ARE NOW A SUPE. WELCOME TO VOUGHT INTERNATIONAL."})
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
