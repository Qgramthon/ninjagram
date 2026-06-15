#!/usr/bin/env python3
"""
Qgram Cloud - Developer Dashboard
Developer: @H_Tahoun | Channel: @Q_g_r_a_m
"""

import os, sys, json, asyncio, time, random, threading, logging, glob as glob_mod
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, render_template_string
from telethon import TelegramClient, events, functions, Button
from telethon.errors import (
    FloodWaitError, SessionPasswordNeededError,
    PhoneCodeInvalidError, PhoneCodeExpiredError
)
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest

BOT_TOKEN = "8871068990:AAH9OLFclsTzxgzOXOt36V2VY5iinCDzYoo"
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 5000))
SESSIONS_DIR = Path("sessions")
DOWNLOADS_DIR = Path("downloads")
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

for f in glob_mod.glob("*.json"):
    try: os.remove(f)
    except: pass
for f in glob_mod.glob("sessions/pending_*.json"):
    try: os.remove(f)
    except: pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

pending_logins = {}
active_clients = {}
stats = {
    "total_users": 0,
    "total_logins": 0,
    "active_now": 0,
    "commands_used": {},
    "start_time": datetime.now().isoformat()
}

try:
    if os.path.exists("stats.json"):
        with open("stats.json", "r", encoding="utf-8") as f:
            loaded = json.load(f)
            stats.update(loaded)
except:
    pass

def save_stats():
    try:
        stats["active_now"] = len(active_clients)
        tmp = "stats_tmp.json"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)
        os.replace(tmp, "stats.json")
    except:
        pass

app = Flask(__name__)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Qgram Dashboard</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root {
            --bg-primary: #0A0A19;
            --bg-secondary: #121226;
            --bg-card: #1A1A2E;
            --border: #2A2A4A;
            --accent: #6C63FF;
            --accent-hover: #8B83FF;
            --text-primary: #E8E8F0;
            --text-secondary: #9090B0;
            --success: #4ADE80;
            --danger: #F87171;
            --radius: 12px;
            --radius-sm: 8px;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            line-height: 1.6;
        }
        .app-container { max-width: 680px; margin: 0 auto; padding: 16px; }
        .header { text-align: center; padding: 24px 0; }
        .header-logo {
            font-size: 32px; font-weight: 800; letter-spacing: 2px;
            background: linear-gradient(135deg, var(--accent), var(--accent-hover));
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        .header-sub { color: var(--text-secondary); font-size: 13px; margin-top: 4px; }
        .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 16px; }
        .stat-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px 12px; text-align: center; }
        .stat-number { font-size: 28px; font-weight: 700; color: var(--accent); }
        .stat-label { font-size: 11px; color: var(--text-secondary); margin-top: 4px; text-transform: uppercase; letter-spacing: 1px; }
        .card { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px; margin-bottom: 14px; }
        .card-header { font-size: 15px; font-weight: 600; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
        .card-header::before { content: ''; width: 4px; height: 20px; background: var(--accent); border-radius: 2px; }
        .step { display: none; } .step.active { display: block; }
        label { color: var(--text-secondary); font-size: 12px; display: block; margin: 14px 0 6px; font-weight: 500; }
        input { width: 100%; padding: 13px 16px; background: var(--bg-primary); border: 1.5px solid var(--border); border-radius: var(--radius-sm); color: var(--text-primary); font-size: 14px; font-family: inherit; }
        input:focus { outline: none; border-color: var(--accent); }
        input::placeholder { color: #4A4A6A; }
        button { width: 100%; padding: 14px; background: var(--accent); color: #fff; border: none; border-radius: var(--radius-sm); font-size: 15px; font-weight: 600; cursor: pointer; margin-top: 16px; font-family: inherit; }
        button:hover { background: var(--accent-hover); }
        button:disabled { opacity: 0.5; cursor: not-allowed; }
        .msg { padding: 12px; border-radius: var(--radius-sm); margin-top: 12px; text-align: center; display: none; font-size: 13px; }
        .msg.success { background: rgba(74,222,128,0.1); color: var(--success); display: block; border: 1px solid rgba(74,222,128,0.2); }
        .msg.error { background: rgba(248,113,113,0.1); color: var(--danger); display: block; border: 1px solid rgba(248,113,113,0.2); }
        .info-box { background: rgba(108,99,255,0.06); border: 1px solid rgba(108,99,255,0.2); border-radius: var(--radius-sm); padding: 12px; margin: 12px 0; font-size: 12px; color: var(--text-secondary); }
        .info-box b { color: var(--accent); }
        .top-commands { margin-top: 14px; }
        .command-item { display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; background: var(--bg-primary); border-radius: var(--radius-sm); margin: 6px 0; font-size: 13px; }
        .command-name { font-weight: 600; color: var(--accent); }
        .command-count { color: var(--text-secondary); font-size: 12px; background: var(--bg-card); padding: 4px 10px; border-radius: 20px; border: 1px solid var(--border); }
        .success-icon { text-align: center; font-size: 48px; margin: 16px 0; }
        .commands-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; margin-top: 12px; }
        .cmd-item { background: var(--bg-primary); border: 1px solid var(--border); padding: 10px; border-radius: var(--radius-sm); text-align: center; font-size: 11px; color: var(--text-secondary); }
        .cmd-item b { color: var(--accent); display: block; margin-bottom: 3px; font-size: 13px; }
        .divider { height: 1px; background: var(--border); margin: 20px 0; }
    </style>
</head>
<body>
    <div class="app-container">
        <div class="header">
            <div class="header-logo">QGRAM</div>
            <div class="header-sub">Telethon UserBot Cloud</div>
        </div>

        <div class="stats-grid">
            <div class="stat-card"><div class="stat-number" id="totalUsers">0</div><div class="stat-label">Total Users</div></div>
            <div class="stat-card"><div class="stat-number" id="activeNow">0</div><div class="stat-label">Active Now</div></div>
            <div class="stat-card"><div class="stat-number" id="totalCommands">0</div><div class="stat-label">Commands</div></div>
        </div>

        <div class="card">
            <div class="card-header">Top Commands</div>
            <div class="top-commands" id="topCommandsList"><div class="command-item"><span class="command-name">--</span><span class="command-count">0</span></div></div>
        </div>

        <div class="divider"></div>

        <div class="step active" id="s1">
            <div class="card">
                <div class="card-header">Connect Account</div>
                <div class="info-box">Get <b>API_ID</b> and <b>API_HASH</b> from <b>my.telegram.org</b></div>
                <label>API ID</label><input type="number" id="api_id" placeholder="12345678">
                <label>API HASH</label><input type="text" id="api_hash" placeholder="a1b2c3d4e5f6a1b2c3d4e5f6">
                <label>Phone Number</label><input type="text" id="phone" placeholder="+201234567890">
                <button onclick="sendCode()">Send Verification Code</button>
                <div id="msg1" class="msg"></div>
            </div>
        </div>

        <div class="step" id="s2">
            <div class="card">
                <div class="card-header">Verify Code</div>
                <label>Verification Code</label><input type="text" id="code" placeholder="12345" maxlength="5">
                <label>2FA Password (if enabled)</label><input type="password" id="password" placeholder="Leave empty if none">
                <button onclick="verifyCode()">Activate Bot</button>
                <div id="msg2" class="msg"></div>
            </div>
        </div>

        <div class="step" id="s3">
            <div class="card">
                <div class="card-header">Activated</div>
                <div class="success-icon">OK</div>
                <div class="msg success">Bot is running on your account 24/7</div>
                <div class="commands-grid">
                    <div class="cmd-item"><b>.كتم</b>Mute User</div>
                    <div class="cmd-item"><b>.خط عريض</b>Bold Text</div>
                    <div class="cmd-item"><b>.تقليد</b>Mimic User</div>
                    <div class="cmd-item"><b>.انتحال</b>Clone Account</div>
                    <div class="cmd-item"><b>.حفظ</b>Save Media</div>
                    <div class="cmd-item"><b>.بنق</b>Ping</div>
                    <div class="cmd-item"><b>.تاريخ</b>Date & Time</div>
                    <div class="cmd-item"><b>.ايدي</b>User ID</div>
                    <div class="cmd-item"><b>.معلومات</b>Group Info</div>
                    <div class="cmd-item"><b>.سورس</b>Source</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const tg = window.Telegram.WebApp; tg.ready(); tg.expand();
        let phoneNumber = '';
        function sm(n,t,c){let m=document.getElementById('msg'+n);m.textContent=t;m.className='msg '+c}
        function ss(n){document.querySelectorAll('.step').forEach(s=>s.classList.remove('active'));document.getElementById('s'+n).classList.add('active')}
        
        function updateStats(){
            fetch('/api/stats').then(r=>r.json()).then(d=>{
                document.getElementById('totalUsers').textContent=d.total_users||0;
                document.getElementById('activeNow').textContent=d.active_now||0;
                document.getElementById('totalCommands').textContent=d.total_commands||0;
                let topHtml='';
                const top=d.top_commands||{};
                const sorted=Object.entries(top).sort((a,b)=>b[1]-a[1]).slice(0,5);
                sorted.forEach(([cmd,count])=>{topHtml+=`<div class="command-item"><span class="command-name">.${cmd}</span><span class="command-count">${count}</span></div>`});
                if(topHtml) document.getElementById('topCommandsList').innerHTML=topHtml;
            });
        }
        updateStats(); setInterval(updateStats,5000);
        
        async function sendCode(){
            let b=event.target; b.disabled=true; b.textContent='Sending...';
            let ai=document.getElementById('api_id').value;
            let ah=document.getElementById('api_hash').value;
            let p=document.getElementById('phone').value; phoneNumber=p;
            if(!ai||!ah||!p){sm(1,'All fields required','error');b.disabled=false;b.textContent='Send Code';return}
            try{
                let r=await fetch('/api/send_code',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({api_id:ai,api_hash:ah,phone:p})});
                let d=await r.json();
                if(d.success){sm(1,'Code sent','success');setTimeout(()=>ss(2),500)}
                else{sm(1,d.message,'error')}
            }catch(e){sm(1,'Connection failed','error')}
            b.disabled=false;b.textContent='Send Code';
        }
        
        async function verifyCode(){
            let b=event.target; b.disabled=true; b.textContent='Activating...';
            let c=document.getElementById('code').value;
            let pw=document.getElementById('password').value;
            if(!c){sm(2,'Enter code','error');b.disabled=false;b.textContent='Activate';return}
            try{
                let r=await fetch('/api/verify',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({phone:phoneNumber,code:c,password:pw})});
                let d=await r.json();
                if(d.success){ss(3);tg.sendData(JSON.stringify({done:true}));updateStats()}
                else{sm(2,d.message,'error')}
            }catch(e){sm(2,'Connection failed','error')}
            b.disabled=false;b.textContent='Activate';
        }
    </script>
</body>
</html>
"""

def create_user_bot(api_id, api_hash, phone):
    client = TelegramClient(str(SESSIONS_DIR / phone), api_id, api_hash, connection_retries=10, retry_delay=3, auto_reconnect=True)
    muted_users, bold_mode, fake_mode, impersonate_data, auto_save_mode = {}, {}, {}, {}, {}
    
    async def gt(event):
        if event.is_private: return event.chat_id
        r = await event.get_reply_message()
        return r.sender_id if r else None
    
    async def se(event, text):
        try: await event.edit(text, parse_mode='html')
        except: pass
    
    async def get_user_info(user_id):
        try:
            user = await client.get_entity(user_id)
            name = user.first_name or "غير معروف"
            if user.last_name: name += f" {user.last_name}"
            username = f"@{user.username}" if user.username else "لا يوجد"
            bio = "لا يوجد"
            try:
                full = await client(GetFullUserRequest(user_id))
                if full.full_user.about: bio = full.full_user.about
            except: pass
            return {'name': name, 'first_name': user.first_name, 'last_name': user.last_name or '', 'username': username, 'bio': bio, 'id': user.id}
        except: return None
    
    async def download_media(message):
        try:
            if not message or not message.media: return None
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"media_{ts}"
            if hasattr(message.media, 'photo'): filename = f"photo_{ts}.jpg"
            elif hasattr(message.media, 'document'):
                for attr in message.media.document.attributes:
                    if hasattr(attr, 'file_name'): filename = attr.file_name; break
            filepath = DOWNLOADS_DIR / filename
            if filepath.exists():
                base, ext, c = filepath.stem, filepath.suffix, 1
                while filepath.exists():
                    filepath = DOWNLOADS_DIR / f"{base}_{c}{ext}"; c += 1
            await message.download_media(file=filepath)
            return filepath
        except: return None
    
    async def change_profile_photo(user_id):
        try:
            photo_data = await client.download_profile_photo(user_id)
            if not photo_data: return False
            uploaded_file = await client.upload_file(photo_data)
            current = await client.get_profile_photos('me', limit=10)
            if current:
                await client(DeletePhotosRequest(id=[p.id for p in current]))
                await asyncio.sleep(2)
            await client(UploadProfilePhotoRequest(file=uploaded_file))
            await asyncio.sleep(1)
            return True
        except: return False
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.'))
    async def h(event):
        try:
            t = event.text.strip()
            if not t.startswith('.'): return
            c = t[1:].strip().lower()
            
            if c not in ['اوامر', 'مساعدة', 'بنق', 'بنغ']:
                stats["commands_used"][c] = stats["commands_used"].get(c, 0) + 1
                save_stats()
            
            if c == 'حب':
                tg = await gt(event)
                if tg: await se(event, f"نسبة الحب بينكما {random.randint(1,100)}%")
                else: await se(event, "رد على رسالة الشخص")
            elif c == 'سورس': await se(event, "QGRAM TELETHON SOURCE\n@Q_g_r_a_m\n@H_Tahoun")
            elif c == 'ايدي':
                r = await event.get_reply_message()
                info = await get_user_info(r.sender_id if r else event.sender_id)
                if info: await se(event, f"Name: {info['name']}\nUser: {info['username']}\nBio: {info['bio']}\nID: {info['id']}")
                else: await se(event, f"ID: {event.sender_id}")
            elif c == 'معلومات':
                ch = await client.get_entity(event.chat_id)
                title = ch.title if hasattr(ch, 'title') else "خاص"
                await se(event, f"Name: {title}\nID: {ch.id}")
            elif c == 'كتم':
                tg = await gt(event)
                if tg:
                    if tg not in muted_users: muted_users[tg] = set()
                    muted_users[tg].add(event.chat_id)
                    await se(event, "خف كلام شوية")
            elif c == 'الغاء كتم':
                tg = await gt(event)
                if tg and tg in muted_users: del muted_users[tg]; await se(event, "خلاص صعبت عليا")
            elif c == 'خط عريض': bold_mode[event.chat_id] = True; await se(event, "خطك عريض دلوقت")
            elif c == 'الغاء خط عريض':
                if event.chat_id in bold_mode: del bold_mode[event.chat_id]; await se(event, "خط عادي دلوقت")
            elif c == 'تقليد':
                r = await event.get_reply_message()
                if r: fake_mode[event.chat_id] = {'target_id': r.sender_id}; await se(event, "يتم التقليد حاليا")
            elif c == 'الغاء تقليد':
                if event.chat_id in fake_mode: del fake_mode[event.chat_id]; await se(event, "سايبك بمزاجي ها")
            elif c == 'انتحال':
                r = await event.get_reply_message()
                if not r: await se(event, "رد على رسالة الشخص"); return
                await se(event, "جاري الانتحال...")
                try:
                    target_info = await get_user_info(r.sender_id)
                    if not target_info: await se(event, "فشل"); return
                    me = await client.get_me()
                    my_info = await get_user_info(me.id)
                    try:
                        my_photos = await client.get_profile_photos('me', limit=1)
                        orig_photo = my_photos[0] if my_photos else None
                    except: orig_photo = None
                    impersonate_data[event.chat_id] = {'first_name': me.first_name, 'last_name': me.last_name or '', 'photo': orig_photo, 'bio': my_info['bio'] if my_info else 'لا يوجد'}
                    await change_profile_photo(r.sender_id)
                    await client(functions.account.UpdateProfileRequest(first_name=target_info['first_name'], last_name=target_info['last_name']))
                    if target_info['bio'] != 'لا يوجد': await client(functions.account.UpdateProfileRequest(about=target_info['bio'][:70]))
                    await se(event, f"تم الانتحال: {target_info['name']}")
                except Exception as e: await se(event, f"خطأ: {str(e)[:100]}")
            elif c == 'الغاء انتحال':
                if event.chat_id not in impersonate_data: await se(event, "لا يوجد انتحال"); return
                try:
                    orig = impersonate_data[event.chat_id]
                    try:
                        current = await client.get_profile_photos('me', limit=10)
                        if current: await client(DeletePhotosRequest(id=[p.id for p in current])); await asyncio.sleep(2)
                        if orig.get('photo'): await client(UploadProfilePhotoRequest(file=orig['photo']))
                    except: pass
                    await client(functions.account.UpdateProfileRequest(first_name=orig['first_name'], last_name=orig['last_name']))
                    if orig.get('bio') and orig['bio'] != 'لا يوجد': await client(functions.account.UpdateProfileRequest(about=orig['bio'][:70]))
                    await se(event, "تم استعادة الحساب")
                    del impersonate_data[event.chat_id]
                except Exception as e: await se(event, f"خطأ: {str(e)[:100]}")
            elif c == 'حفظ':
                r = await event.get_reply_message()
                if not r or not r.media: await se(event, "رد على وسائط"); return
                await se(event, "جاري الحفظ...")
                fp = await download_media(r)
                if fp: await se(event, f"تم: {fp.name}")
                else: await se(event, "فشل")
            elif c == 'حفظ تلقائي':
                if event.chat_id in auto_save_mode: del auto_save_mode[event.chat_id]; await se(event, "حفظ تلقائي: متوقف")
                else: auto_save_mode[event.chat_id] = True; await se(event, "حفظ تلقائي: مفعل")
            elif c in ['بنق', 'بنغ']:
                s = time.time(); await se(event, f"سرعة النت: {round((time.time()-s)*1000)}ms")
            elif c == 'تاريخ':
                n = datetime.now()
                da = {'Saturday':'السبت','Sunday':'الاحد','Monday':'الاثنين','Tuesday':'الثلاثاء','Wednesday':'الاربعاء','Thursday':'الخميس','Friday':'الجمعة'}
                await se(event, f"Data: {n.strftime('%Y/%m/%d')}\nTime: {n.strftime('%I:%M %p')}\nDay: {da.get(n.strftime('%A'))}")
            elif c in ['اوامر', 'مساعدة']:
                await se(event, "الاوامر: .كتم .خط عريض .تقليد .انتحال .حفظ .حب .بنق .تاريخ .ايدي .معلومات .سورس")
        except: pass
    
    @client.on(events.NewMessage(incoming=True))
    async def ml(event):
        try:
            if event.chat_id in fake_mode and event.sender_id == fake_mode[event.chat_id]['target_id']:
                await asyncio.sleep(0.5)
                if event.text: await event.reply(event.text)
                elif event.media: await client.send_file(event.chat_id, event.media, reply_to=event.id)
        except: pass
    
    @client.on(events.NewMessage(incoming=True))
    async def mul(event):
        try:
            if event.sender_id in muted_users and event.chat_id in muted_users[event.sender_id]:
                await event.delete()
        except: pass
    
    @client.on(events.NewMessage(incoming=True))
    async def asl(event):
        try:
            if event.chat_id in auto_save_mode and event.media:
                await download_media(event)
        except: pass
    
    @client.on(events.NewMessage(outgoing=True))
    async def bp(event):
        try:
            if event.chat_id in bold_mode and event.text and not event.text.startswith('.'):
                await asyncio.sleep(0.1); await event.edit(f"<b>{event.text}</b>", parse_mode='html')
        except: pass
    
    return client

@app.route('/')
def index():
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/stats')
def api_stats():
    save_stats()
    total_commands = sum(stats.get("commands_used", {}).values())
    return jsonify({
        "total_users": stats.get("total_users", 0),
        "active_now": len(active_clients),
        "total_commands": total_commands,
        "top_commands": stats.get("commands_used", {}),
        "uptime": stats.get("start_time", "")
    })

def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

@app.route('/api/send_code', methods=['POST'])
def api_send_code():
    try:
        d = request.json
        api_id, api_hash, phone = int(d['api_id']), d['api_hash'], d['phone']
        
        async def s():
            client = TelegramClient(str(SESSIONS_DIR / f"t_{phone}"), api_id, api_hash)
            await client.start(phone=phone)
            r = await client.send_code_request(phone)
            pending_logins[phone] = {'client': client, 'hash': r.phone_code_hash, 'api_id': api_id, 'api_hash': api_hash}
        
        run_async(s())
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)[:150]})

@app.route('/api/verify', methods=['POST'])
def api_verify():
    try:
        d = request.json
        phone, code, pw = d['phone'], d['code'], d.get('password', '')
        
        if phone not in pending_logins:
            return jsonify({'success': False, 'message': 'Session expired - please restart'})
        
        p = pending_logins[phone]
        client = p['client']
        
        async def v():
            try:
                await client.sign_in(phone=phone, code=code, phone_code_hash=p['hash'])
            except SessionPasswordNeededError:
                if pw: await client.sign_in(password=pw)
                else: return False, "2FA password required"
            except PhoneCodeInvalidError: return False, "Invalid code"
            except PhoneCodeExpiredError: return False, "Code expired"
            
            bot = create_user_bot(p['api_id'], p['api_hash'], phone)
            await bot.start(phone=phone)
            active_clients[phone] = bot
            
            stats["total_users"] = len(active_clients)
            stats["total_logins"] = stats.get("total_logins", 0) + 1
            save_stats()
            
            del pending_logins[phone]
            return True, "ok"
        
        ok, msg = run_async(v())
        return jsonify({'success': ok, 'message': msg if not ok else 'ok'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)[:150]})

async def start_telegram_bot():
    try:
        bot = TelegramClient(str(SESSIONS_DIR / "bot"), 30589536, "b5f5ae07b739eb28e37d2aa92125bcea")
        await bot.start(bot_token=BOT_TOKEN)
        
        @bot.on(events.NewMessage(pattern='/start'))
        async def sc(event):
            await event.reply("QGRAM CLOUD\n\nActivate your UserBot now:", buttons=[Button.web("Open Dashboard", "https://web-production-e73e7.up.railway.app")])
        
        @bot.on(events.NewMessage(pattern='/stats'))
        async def st(event):
            save_stats()
            total_cmds = sum(stats.get("commands_used", {}).values())
            top = sorted(stats.get("commands_used", {}).items(), key=lambda x: x[1], reverse=True)[:5]
            top_text = "\n".join([f".{cmd}: {count}" for cmd, count in top])
            await event.reply(f"STATISTICS\n\nTotal Users: {stats.get('total_users', 0)}\nActive Now: {len(active_clients)}\nTotal Commands: {total_cmds}\n\nTOP COMMANDS:\n{top_text if top_text else 'No data yet'}")
        
        logging.info("Bot running")
        await bot.run_until_disconnected()
    except Exception as e:
        logging.error(f"Bot error: {e}")

def main():
    print("\n" + "=" * 50)
    print("   QGRAM CLOUD - DEVELOPER DASHBOARD")
    print("   @H_Tahoun | @Q_g_r_a_m")
    print("=" * 50 + "\n")
    
    threading.Thread(target=lambda: asyncio.run(start_telegram_bot()), daemon=True).start()
    app.run(host=HOST, port=PORT)

if __name__ == "__main__":
    main()
