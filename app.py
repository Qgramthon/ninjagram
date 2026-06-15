import os
import secrets
import logging
from pathlib import Path
from functools import wraps

from quart import Quart, request, jsonify, render_template_string
from quart_limiter import RateLimiter, limiter
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError

# ====================== CONFIG ======================
PORT = int(os.environ.get("PORT", 5000))
SESSIONS_DIR = Path("/app/sessions")  # مخصص لـ Railway Volume
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    raise ValueError("❌ يجب تعيين ADMIN_PASSWORD في متغيرات Railway")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = Quart(__name__)
rate_limiter = RateLimiter(app, default_limits=["10 per minute"])

active_clients = {}
app.pending_logins = {}   # للـ login المؤقت

# ====================== AUTH ======================
def require_auth():
    def decorator(f):
        @wraps(f)
        async def decorated(*args, **kwargs):
            auth = request.authorization
            if not auth or auth.password != ADMIN_PASSWORD:
                return jsonify({"success": False, "message": "غير مصرح"}), 401
            return await f(*args, **kwargs)
        return decorated
    return decorator

# ====================== HTML ======================
HTML = """<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>QGRAM</title><script src="https://telegram.org/js/telegram-web-app.js"></script><style>:root{--bg:#0A0A19;--card:#1A1A2E;--border:#2A2A4A;--accent:#6C63FF;--text:#E8E8F0;--sub:#9090B0;--success:#4ADE80;--danger:#F87171}*{margin:0;padding:0;box-sizing:border-box}body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;padding:16px}.container{max-width:520px;margin:0 auto}.header{text-align:center;padding:30px 0}.logo{font-size:36px;font-weight:900;background:linear-gradient(135deg,var(--accent),#a5a0ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent}.card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:24px;margin-bottom:16px}label{color:var(--sub);font-size:13px;display:block;margin:16px 0 8px}input{width:100%;padding:14px;background:var(--bg);border:1.5px solid var(--border);border-radius:10px;color:var(--text);font-size:15px}input:focus{outline:none;border-color:var(--accent)}button{width:100%;padding:15px;background:var(--accent);color:#fff;border:none;border-radius:10px;font-size:16px;font-weight:600;cursor:pointer;margin-top:12px}button:disabled{opacity:0.6}.msg{padding:14px;border-radius:10px;margin:12px 0;text-align:center;display:none}.msg.success{background:rgba(74,222,128,0.15);color:var(--success)}.msg.error{background:rgba(248,113,113,0.15);color:var(--danger)}</style></head><body><div class="container"><div class="header"><div class="logo">QGRAM</div></div><div class="step active" id="s1"><div class="card"><h3>ربط حساب جديد</h3><label>API ID</label><input type="number" id="api_id"><label>API HASH</label><input type="text" id="api_hash"><label>رقم الهاتف</label><input type="tel" id="phone"><button onclick="sendCode()">إرسال الكود</button><div id="msg1" class="msg"></div></div></div><div class="step" id="s2"><div class="card"><h3>تفعيل الحساب</h3><label>الكود</label><input type="text" id="code"><label>كلمة مرور 2FA (اختياري)</label><input type="password" id="password"><button onclick="verifyCode()">تفعيل</button><div id="msg2" class="msg"></div></div></div><div class="step" id="s3"><div class="card"><div class="msg success">✅ الحساب مفعل ويعمل 24/7</div></div></div></div><script>const tg=window.Telegram.WebApp;tg.ready();tg.expand();let ph='';function sm(n,t,c){const e=document.getElementById('msg'+n);e.textContent=t;e.className=`msg ${c}`;e.style.display='block'}function ss(n){document.querySelectorAll('.step').forEach(s=>s.classList.remove('active'));document.getElementById('s'+n).classList.add('active')}async function sendCode(){const b=event.target;b.disabled=true;b.textContent='جاري...';const d={api_id:parseInt(document.getElementById('api_id').value),api_hash:document.getElementById('api_hash').value.trim(),phone:document.getElementById('phone').value.trim()};if(!d.api_id||!d.api_hash||!d.phone){sm(1,'جميع الحقول مطلوبة','error');b.disabled=false;b.textContent='إرسال الكود';return}try{const r=await fetch('/api/send_code',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});const res=await r.json();res.success?(ph=d.phone,sm(1,'تم إرسال الكود','success'),setTimeout(()=>ss(2),700)):sm(1,res.message,'error')}catch{sm(1,'فشل الاتصال','error')}b.disabled=false;b.textContent='إرسال الكود'}async function verifyCode(){const b=event.target;b.disabled=true;b.textContent='جاري التفعيل...';try{const r=await fetch('/api/verify',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({phone:ph,code:document.getElementById('code').value.trim(),password:document.getElementById('password').value.trim()})});const res=await r.json();res.success?(ss(3),tg.sendData(JSON.stringify({done:true}))):sm(2,res.message,'error')}catch{sm(2,'فشل الاتصال','error')}b.disabled=false;b.textContent='تفعيل'}</script></body></html>"""

# ====================== CLIENT FACTORY ======================
async def create_and_start_client(phone: str, api_id: int, api_hash: str, session_str: str = None):
    if phone in active_clients:
        return active_clients[phone]

    session = StringSession(session_str) if session_str else str(SESSIONS_DIR / f"{phone}.session")
    client = TelegramClient(session, api_id, api_hash, auto_reconnect=True, connection_retries=10)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.'))
    async def command_handler(event):
        try:
            cmd = event.text[1:].strip().lower()
            if cmd == "ايدي":
                r = await event.get_reply_message()
                uid = r.sender_id if r else event.sender_id
                await event.edit(f"**ID:** `{uid}`")
            elif cmd == "حب":
                r = await event.get_reply_message()
                if r:
                    await event.edit(f"نسبة الحب ❤️: {secrets.randbelow(99)+1}%")
                else:
                    await event.edit("رد على رسالة")
            # أضف باقي أوامرك هنا...
            else:
                await event.edit("أمر غير معروف")
        except Exception as e:
            logger.error(f"Command error {phone}: {e}")

    await client.start(phone=phone)
    active_clients[phone] = client
    logger.info(f"✅ Client started successfully: {phone}")
    return client

# ====================== ROUTES ======================
@app.route('/')
async def index():
    return await render_template_string(HTML)

@app.route('/api/send_code', methods=['POST'])
@require_auth()
@limiter.limit("5 per minute")
async def api_send_code():
    try:
        data = await request.get_json()
        api_id = int(data['api_id'])
        api_hash = data['api_hash'].strip()
        phone = data['phone'].strip()

        client = TelegramClient(f"t_{phone}", api_id, api_hash)
        await client.connect()
        sent = await client.send_code_request(phone)

        app.pending_logins[phone] = {
            "client": client,
            "hash": sent.phone_code_hash,
            "api_id": api_id,
            "api_hash": api_hash
        }
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Send code error: {e}")
        return jsonify({"success": False, "message": str(e)[:150]}), 400

@app.route('/api/verify', methods=['POST'])
@require_auth()
@limiter.limit("5 per minute")
async def api_verify():
    try:
        data = await request.get_json()
        phone = data['phone']
        code = data['code']
        password = data.get('password', '')

        if phone not in app.pending_logins:
            return jsonify({"success": False, "message": "انتهت الجلسة، ابدأ من جديد"})

        p = app.pending_logins[phone]
        client = p["client"]

        await client.sign_in(phone, code, phone_code_hash=p["hash"])
        if password:
            await client.sign_in(password=password)

        session_str = client.session.save()
        await client.disconnect()

        # تشغيل البوت الدائم
        await create_and_start_client(phone, p["api_id"], p["api_hash"], session_str)

        del app.pending_logins[phone]
        return jsonify({"success": True, "message": "تم التفعيل بنجاح"})
    except (PhoneCodeInvalidError, PhoneCodeExpiredError):
        return jsonify({"success": False, "message": "كود خاطئ أو منتهي الصلاحية"})
    except SessionPasswordNeededError:
        return jsonify({"success": False, "message": "مطلوب كلمة مرور 2FA"})
    except Exception as e:
        logger.error(f"Verify error: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)[:150]}), 400

# ====================== STARTUP ======================
@app.before_serving
async def startup():
    logger.info("🚀 Starting QGRAM on Railway...")
    # يمكن إضافة تحميل تلقائي للجلسات هنا لاحقاً

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
