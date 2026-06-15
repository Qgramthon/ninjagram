#!/usr/bin/env python3
"""
Qgram Cloud - Developer Dashboard
Developer: @H_Tahoun | Channel: @Q_g_r_a_m
"""

import os, sys, json, asyncio, time, random, threading, logging
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

# ==================== Configuration ====================
BOT_TOKEN = "8871068990:AAH9OLFclsTzxgzOXOt36V2VY5iinCDzYoo"
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 5000))
SESSIONS_DIR = Path("sessions")
DOWNLOADS_DIR = Path("downloads")
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
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
    with open("stats.json", "r") as f:
        stats = json.load(f)
except: pass

def save_stats():
    try:
        stats["active_now"] = len(active_clients)
        with open("stats.json", "w") as f:
            json.dump(stats, f, indent=2)
    except: pass

app = Flask(__name__)

# ==================== مكتبة المحتوى ====================
TRUTHS = [
    "اكتر حاجة بتخاف منها في حياتك؟",
    "مين الشخص اللي مش بتطيقه ومع ذلك بتعامله؟",
    "السر اللي محدش يعرفه عنك؟",
    "اكبر كذبة قلتها في حياتك؟",
    "مين اكتر شخص بتغير منه؟",
    "الحاجة اللي بتخبيها عن اهلك؟",
    "اكبر ندم في حياتك؟",
    "لو عندك فرصة تعمل حاجة غلط ومحدش هيعرف، هتعملها؟",
    "مين الشخص اللي بتحبه سرا؟",
    "اسوا حاجة عملتها في حياتك؟",
    "اخر مرة بكيت فيها وليه؟",
    "مين الشخص اللي بتحس انه بيحسدك؟",
    "الحاجة اللي بتتمنى تغيرها في شكلك؟",
    "اكتر حاجة بتضايقك في صاحبك المفضل؟",
    "لو خيروك بين فلوس كتير وصديق عمرك، هتختار ايه؟",
    "الحاجة اللي بتعملها ومش مقتنع بيها؟",
    "مين الشخص اللي حبيته ومخدتش باله منك؟",
    "اسوا عادة عندك؟",
    "اكتر موقف محرج حصلك قدام الناس؟",
    "مين اكتر شخص بتكرهه في عيلتك؟",
]

KET = [
    "رايك في الدراما المصرية السنة دي؟",
    "مين افضل ممثل مصري بالنسبة لك؟",
    "اكتر فيلم مصري حبيته؟",
    "رايك في الاغاني الشعبية المصرية؟",
    "مين افضل مطرب عندك؟",
    "اكتر اكلة مصرية بتحبها؟",
    "رايك في التعليم في مصر؟",
    "مين افضل لاعب كرة قدم مصري؟",
    "رايك في النادي الاهلي؟",
    "رايك في نادي الزمالك؟",
    "اكتر مكان بتحبه في مصر؟",
    "رايك في الشعب المصري؟",
    "اكتر عادة مصرية بتحبها؟",
    "رايك في الجواز المبكر؟",
    "رايك في السفر للخارج؟",
    "اكتر حاجة بتميز مصر؟",
    "رايك في اللهجة المصرية؟",
    "مين اشهر شخصية مصرية بتحبها؟",
    "رايك في المطبخ المصري؟",
    "اكتر موقف مضحك حصلك في مصر؟",
]

WISDOMS = [
    "اللي يتلسع من الشوربة ينفخ في الزبادي",
    "الصبر مفتاح الفرج",
    "العلم في الصغر كالنقش على الحجر",
    "من جد وجد ومن زرع حصد",
    "خير الكلام ما قل ودل",
    "في التاني السلامة وفي العجلة الندامة",
    "الوقت كالسيف ان لم تقطعه قطعك",
    "الصديق وقت الضيق",
    "القناعة كنز لا يفنى",
    "عامل الناس بما تحب ان يعاملوك به",
]

QUOTES = [
    "كن انت التغيير الذي تريد ان تراه في العالم - غاندي",
    "الحياة اما مغامرة جريئة او لا شيء - هيلين كيلر",
    "النجاح هو الانتقال من فشل الى فشل دون فقدان الحماس - تشرشل",
    "ليس المهم ان تعيش، بل المهم ان تعيش جيدا - سقراط",
    "لا تنتظر الفرصة، بل اصنعها",
    "ما لا يقتلني يجعلني اقوى - نيتشه",
    "السعادة ليست في امتلاك الكثير",
    "لا تحكم على الكتاب من غلافه",
    "من يحبك بصدق لا يخذلك ابدا",
    "لا تتوقف عندما تتعب، توقف عندما تنتهي",
]

POETRY = [
    "الخيل والليل والبيداء تعرفني\nوالسيف والرمح والقرطاس والقلم",
    "اذا غامرت في شرف مروم\nفلا تقنع بما دون النجوم",
    "ولم ار في عيوب الناس عيبا\nكنقص القادرين على التمام",
    "وما نيل المطالب بالتمني\nولكن تؤخذ الدنيا غلابا",
    "دع الايام تفعل ما تشاء\nوطب نفسا اذا حكم القضاء",
]

ADVICES = [
    "استثمر في نفسك وفي تعليمك، ده احسن استثمار ممكن تعمله",
    "متبصش على اللي عند غيرك، ركز على رحلتك انت",
    "النجاح مش بيجي بين يوم وليلة، لازم صبر وتعب",
    "خلي دايما عندك هدف عايز توصله، عشان متعيش وخلاص",
    "الناس هتنسى اللي قولته وهتعمله، بس مش هتنسى اللي حسسته بيه",
]

# ==================== HTML Dashboard ====================
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
                    <div class="cmd-item"><b>.صراحة</b>Truth</div><div class="cmd-item"><b>.كت</b>Question</div>
                    <div class="cmd-item"><b>.حب</b>Love</div><div class="cmd-item"><b>.حكمة</b>Wisdom</div>
                    <div class="cmd-item"><b>.اقتباس</b>Quote</div><div class="cmd-item"><b>.شعر</b>Poetry</div>
                    <div class="cmd-item"><b>.انصحني</b>Advice</div><div class="cmd-item"><b>.كتم</b>Mute</div>
                    <div class="cmd-item"><b>.خط عريض</b>Bold</div><div class="cmd-item"><b>.انتحال</b>Clone</div>
                    <div class="cmd-item"><b>.تقليد</b>Mimic</div><div class="cmd-item"><b>.حفظ</b>Save</div>
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

# ==================== Helper Functions ====================
def create_user_bot(api_id, api_hash, phone):
    client = TelegramClient(str(SESSIONS_DIR / phone), api_id, api_hash, connection_retries=10, retry_delay=3, auto_reconnect=True)
    muted_users, bold_mode, fake_mode = {}, {}, {}
    
    async def gt(event):
        if event.is_private: return event.chat_id
        r = await event.get_reply_message()
        return r.sender_id if r else None
    
    async def se(event, text):
        try: await event.edit(text, parse_mode='html')
        except: pass
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.'))
    async def h(event):
        try:
            t = event.text.strip()
            if not t.startswith('.'): return
            c = t[1:].strip().lower()
            
            if c not in ['اوامر', 'مساعدة', 'بنق', 'بنغ']:
                stats["commands_used"][c] = stats["commands_used"].get(c, 0) + 1
                save_stats()
            
            if c in ['صراحه', 'صراحة']: await se(event, random.choice(TRUTHS))
            elif c == 'كت': await se(event, random.choice(KET))
            elif c == 'حكمة': await se(event, random.choice(WISDOMS))
            elif c == 'اقتباس': await se(event, random.choice(QUOTES))
            elif c == 'شعر': await se(event, random.choice(POETRY))
            elif c == 'انصحني': await se(event, random.choice(ADVICES))
            elif c == 'حب':
                tg = await gt(event)
                if tg: await se(event, f"نسبة الحب بينكما {random.randint(1,100)}%")
                else: await se(event, "رد على رسالة الشخص")
            elif c == 'سورس': await se(event, "QGRAM TELETHON SOURCE\n@Q_g_r_a_m\n@H_Tahoun")
            elif c == 'ايدي':
                r = await event.get_reply_message()
                try:
                    u = await client.get_entity(r.sender_id if r else event.sender_id)
                    n = u.first_name or "?"
                    un = f"@{u.username}" if u.username else "None"
                    await se(event, f"Name: {n}\nUser: {un}\nID: {u.id}")
                except: await se(event, f"ID: {event.sender_id}")
            elif c == 'معلومات':
                ch = await client.get_entity(event.chat_id)
                await se(event, f"Name: {ch.title}\nID: {ch.id}")
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
                if event.chat_id in bold_mode: del bold_mode[event.chat_id]
                await se(event, "خط عادي دلوقت")
            elif c == 'تقليد':
                r = await event.get_reply_message()
                if r: fake_mode[event.chat_id] = {'target_id': r.sender_id}; await se(event, "يتم التقليد حاليا")
            elif c == 'الغاء تقليد':
                if event.chat_id in fake_mode: del fake_mode[event.chat_id]; await se(event, "سايبك بمزاجي ها")
            elif c in ['بنق', 'بنغ']:
                s = time.time(); await se(event, f"سرعة النت: {round((time.time()-s)*1000)}ms")
            elif c == 'تاريخ':
                n = datetime.now()
                da = {'Saturday':'السبت','Sunday':'الاحد','Monday':'الاثنين','Tuesday':'الثلاثاء','Wednesday':'الاربعاء','Thursday':'الخميس','Friday':'الجمعة'}
                await se(event, f"Data: {n.strftime('%Y/%m/%d')}\nTime: {n.strftime('%I:%M %p')}\nDay: {da.get(n.strftime('%A'))}")
            elif c in ['اوامر', 'مساعدة']:
                await se(event, "الاوامر: .صراحة .كت .حب .حكمة .اقتباس .شعر .انصحني .كتم .خط عريض .تقليد .انتحال .حفظ .بنق .تاريخ .ايدي .معلومات .سورس")
        except: pass
    
    @client.on(events.NewMessage(incoming=True))
    async def ml(event):
        try:
            if event.chat_id in fake_mode and event.sender_id == fake_mode[event.chat_id]['target_id']:
                await asyncio.sleep(0.5)
                if event.text: await event.reply(event.text)
        except: pass
    
    @client.on(events.NewMessage(incoming=True))
    async def mul(event):
        try:
            if event.sender_id in muted_users and event.chat_id in muted_users[event.sender_id]:
                await event.delete()
        except: pass
    
    @client.on(events.NewMessage(outgoing=True))
    async def bp(event):
        try:
            if event.chat_id in bold_mode and event.text and not event.text.startswith('.'):
                await asyncio.sleep(0.1); await event.edit(f"<b>{event.text}</b>", parse_mode='html')
        except: pass
    
    return client

# ==================== API Routes ====================
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

@app.route('/api/send_code', methods=['POST'])
def api_send_code():
    try:
        d = request.json
        api_id, api_hash, phone = int(d['api_id']), d['api_hash'], d['phone']
        client = TelegramClient(str(SESSIONS_DIR / f"t_{phone}"), api_id, api_hash)
        
        async def s():
            await client.start(phone=phone)
            r = await client.send_code_request(phone)
            
            data = {'phone_code_hash': r.phone_code_hash, 'api_id': api_id, 'api_hash': api_hash}
            with open(SESSIONS_DIR / f"pending_{phone}.json", "w") as f:
                json.dump(data, f)
            
            pending_logins[phone] = {'client': client, 'hash': r.phone_code_hash, 'api_id': api_id, 'api_hash': api_hash}
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(s())
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)[:150]})

@app.route('/api/verify', methods=['POST'])
def api_verify():
    try:
        d = request.json
        phone, code, pw = d['phone'], d['code'], d.get('password', '')
        
        if phone not in pending_logins:
            file_path = SESSIONS_DIR / f"pending_{phone}.json"
            if file_path.exists():
                with open(file_path, "r") as f:
                    saved = json.load(f)
                
                client = TelegramClient(str(SESSIONS_DIR / f"t_{phone}"), saved['api_id'], saved['api_hash'])
                
                async def connect_client():
                    await client.start(phone=phone)
                    pending_logins[phone] = {'client': client, 'hash': saved['phone_code_hash'], 'api_id': saved['api_id'], 'api_hash': saved['api_hash']}
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(connect_client())
            else:
                return jsonify({'success': False, 'message': 'Session expired'})
        
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
            
            await client.disconnect()
            
            file_path = SESSIONS_DIR / f"pending_{phone}.json"
            if file_path.exists(): file_path.unlink()
            
            bot = create_user_bot(p['api_id'], p['api_hash'], phone)
            await bot.start(phone=phone)
            active_clients[phone] = bot
            
            stats["total_users"] = len(active_clients)
            stats["total_logins"] = stats.get("total_logins", 0) + 1
            save_stats()
            
            del pending_logins[phone]
            return True, "ok"
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        ok, msg = loop.run_until_complete(v())
        return jsonify({'success': ok, 'message': msg if not ok else 'ok'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)[:150]})

# ==================== Telegram Bot ====================
async def start_telegram_bot():
    try:
        bot = TelegramClient(str(SESSIONS_DIR / "bot"), 30589536, "b5f5ae07b739eb28e37d2aa92125bcea")
        await bot.start(bot_token=BOT_TOKEN)
        
        @bot.on(events.NewMessage(pattern='/start'))
        async def sc(event):
            await event.reply(
                "QGRAM CLOUD\n\nActivate your UserBot now:",
                buttons=[Button.web("Open Dashboard", "https://web-production-e73e7.up.railway.app")]
            )
        
        @bot.on(events.NewMessage(pattern='/stats'))
        async def st(event):
            save_stats()
            total_cmds = sum(stats.get("commands_used", {}).values())
            top = sorted(stats.get("commands_used", {}).items(), key=lambda x: x[1], reverse=True)[:5]
            top_text = "\n".join([f".{cmd}: {count}" for cmd, count in top])
            await event.reply(
                f"STATISTICS\n\n"
                f"Total Users: {stats.get('total_users', 0)}\n"
                f"Active Now: {len(active_clients)}\n"
                f"Total Commands: {total_cmds}\n\n"
                f"TOP COMMANDS:\n{top_text if top_text else 'No data yet'}"
            )
        
        logging.info("Bot running")
        await bot.run_until_disconnected()
    except Exception as e:
        logging.error(f"Bot error: {e}")

# ==================== Main ====================
def main():
    print("\n" + "=" * 50)
    print("   QGRAM CLOUD - DEVELOPER DASHBOARD")
    print("   @H_Tahoun | @Q_g_r_a_m")
    print("=" * 50 + "\n")
    
    threading.Thread(target=lambda: asyncio.run(start_telegram_bot()), daemon=True).start()
    app.run(host=HOST, port=PORT)

if __name__ == "__main__":
    main()
