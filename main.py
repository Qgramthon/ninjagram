#!/usr/bin/env python3
import asyncio, uuid, os, re, random, time, io, textwrap, logging
from datetime import datetime, timedelta
from urllib.parse import quote
from typing import Dict, List, Optional
from collections import deque, defaultdict
from io import BytesIO
import aiohttp
from PIL import Image, ImageDraw
import phonenumbers
from phonenumbers import geocoder, carrier
from fake_useragent import UserAgent
from telethon import TelegramClient, events, Button, functions, types
from telethon.errors import *
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.messages import SearchRequest
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact

# ============================================================
DATA_DIR = './data'
os.makedirs(DATA_DIR, exist_ok=True)
BOT_TOKEN = '7998616214:AAFGroKKmwnrOtyAeJIHmrs_bKW5jXl0B20'
BOT_API_ID = 2040
BOT_API_HASH = 'b18441a1ff607e10a989891a5462e627'
user_states = {}
pending_data = {}
rate_limiter = defaultdict(lambda: deque(maxlen=10))
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('NinjaGram')
bot = TelegramClient(f'{DATA_DIR}/bot', BOT_API_ID, BOT_API_HASH)
ua = UserAgent()
# ============================================================

class Security:
    @staticmethod
    def rate(uid, action, mx=10):
        now = time.time(); k = f"{uid}:{action}"
        if k not in rate_limiter: rate_limiter[k] = deque(maxlen=mx)
        r = rate_limiter[k]
        while r and r[0] < now - 60: r.popleft()
        if len(r) >= mx: return False
        r.append(now); return True

    @staticmethod
    def valid_un(u): return bool(re.match(r'^[a-zA-Z][a-zA-Z0-9_]{3,31}$', u))

    @staticmethod
    def valid_ph(p):
        try: return phonenumbers.is_valid_number(phonenumbers.parse(p))
        except: return bool(re.match(r'^\+?[1-9]\d{7,14}$', p.replace(" ", "")))

# ============================================================
class Truecaller:
    @classmethod
    async def lookup(cls, phone):
        r = {"phone": phone, "valid": False, "carrier": "?", "country": "?", "location": "?", "social": [], "spam": 0, "risk": 0}
        try:
            p = phonenumbers.parse(phone); r["valid"] = phonenumbers.is_valid_number(p)
            r["carrier"] = carrier.name_for_number(p, "en") or "?"
            r["country"] = geocoder.description_for_number(p, "en") or "?"
            r["location"] = geocoder.description_for_number(p, "ar") or "?"
        except: pass
        clean = re.sub(r'[^\d]', '', phone)
        async with aiohttp.ClientSession() as s:
            for u in [f"https://www.google.com/search?q={clean}", f"https://duckduckgo.com/?q={clean}"]:
                try:
                    async with s.get(u, headers={'User-Agent': ua.random}, timeout=10) as resp:
                        t = await resp.text()
                        for kw in ['spam', 'scam', 'fraud', 'احتيال', 'مزعج']:
                            if kw in t.lower(): r["spam"] += 1
                        for plat in ['facebook.com', 'instagram.com', 'twitter.com', 'telegram.me', 'wa.me']:
                            if plat in t.lower() and plat not in r["social"]: r["social"].append(plat)
                except: pass
        risk = min(r["spam"] * 15, 60) + (20 if not r["valid"] else 0)
        r["risk"] = min(risk, 100)
        r["level"] = "🟢" if risk < 30 else "🟡" if risk < 60 else "🔴"
        return r

    @classmethod
    async def reverse(cls, name):
        res = []
        async with aiohttp.ClientSession() as s:
            try:
                async with s.get(f"https://www.google.com/search?q={quote(name + ' phone')}", headers={'User-Agent': ua.random}, timeout=10) as resp:
                    for ph in re.findall(r'\+?[\d]{8,15}', await resp.text()):
                        if Security.valid_ph(ph): res.append({"phone": ph})
            except: pass
        return res[:15]

# ============================================================
class Reporter:
    TYPES = {
        "spam": ("سبام", "abuse@telegram.org", "high"),
        "impersonation": ("انتحال", "abuse@telegram.org", "critical"),
        "threats": ("تهديد", "abuse@telegram.org", "critical"),
        "terrorism": ("إرهاب", "stopca@telegram.org", "critical"),
        "child_abuse": ("أطفال", "stopca@telegram.org", "critical"),
        "fraud": ("احتيال", "abuse@telegram.org", "critical"),
        "drugs": ("مخدرات", "abuse@telegram.org", "critical"),
        "weapons": ("أسلحة", "abuse@telegram.org", "critical"),
        "violence": ("عنف", "abuse@telegram.org", "high"),
        "harassment": ("مضايقة", "abuse@telegram.org", "high"),
        "copyright": ("حقوق", "dmca@telegram.org", "high"),
        "account_theft": ("سرقة", "recover@telegram.org", "critical"),
        "malware": ("هاك", "security@telegram.org", "critical"),
        "phishing": ("تصيد", "security@telegram.org", "critical"),
        "pornography": ("إباحي", "abuse@telegram.org", "high"),
    }

    @classmethod
    def generate(cls, rtype, target, platform="telegram"):
        name, email, sev = cls.TYPES.get(rtype, cls.TYPES["spam"])
        rid = uuid.uuid4().hex[:12].upper()
        tdisp = f"@{target}" if not target.isdigit() else f"ID:{target}"
        plink = f"https://t.me/{target}" if platform == "telegram" else f"https://wa.me/{target.replace('+', '')}"
        body = f"""
╔══════════════════════════════════╗
║  REPORT ID: #{rid}
║  DATE: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
║  TARGET: {tdisp}
║  LINK: {plink}
║  VIOLATION: {name}
║  SEVERITY: {sev.upper()}
║  SEND TO: {email}
╚══════════════════════════════════╝

This account has been observed violating platform policies.
The specific violation involves {name}.
Evidence is available upon request.
Please take appropriate action.

Generated by NinjaGram Pro Max Ultra
        """.strip()
        return {"id": rid, "body": body, "email": email, "severity": sev, "type": name}

# ============================================================
class Osint:
    @classmethod
    async def deep(cls, target):
        r = {"basic": {}, "security": [], "activity": {}, "exposed": {}, "risk": 0}
        try:
            entity = await bot.get_entity(int(target) if target.lstrip('-').isdigit() else target.replace("@", ""))
            r["basic"] = {
                "id": entity.id,
                "username": getattr(entity, 'username', "لا يوجد"),
                "first": getattr(entity, 'first_name', ''),
                "last": getattr(entity, 'last_name', ''),
                "full": f"{getattr(entity, 'first_name', '')} {getattr(entity, 'last_name', '')}".strip(),
                "phone_vis": getattr(entity, 'phone', None) is not None,
                "phone": getattr(entity, 'phone', 'مخفي'),
                "verified": "✅" if getattr(entity, 'verified', False) else "❌",
                "premium": "⭐" if getattr(entity, 'premium', False) else "❌",
                "bot": "🤖" if getattr(entity, 'bot', False) else "👤",
                "scam": "⚠️" if getattr(entity, 'scam', False) else "✅",
                "fake": "⚠️" if getattr(entity, 'fake', False) else "✅",
            }
            cd = cls._est(entity.id)
            if cd:
                days = (datetime.now() - cd).days
                r["activity"]["created"] = cd.strftime("%Y-%m-%d")
                r["activity"]["age"] = f"{days} يوم ({round(days/365,1)} سنة)"
            risk = 0; issues = []
            if not r["basic"]["username"] or r["basic"]["username"] == "لا يوجد": issues.append("لا يوزر"); risk += 15
            if r["basic"]["phone_vis"]: issues.append("رقم مكشوف"); risk += 45
            if getattr(entity, 'scam', False): issues.append("احتيال"); risk += 85
            if getattr(entity, 'fake', False): issues.append("مزيف"); risk += 65
            if cd and days < 30: issues.append("حساب جديد"); risk += 30
            r["security"] = issues; r["risk"] = min(risk, 100)
            r["risk_level"] = "🟢" if risk < 25 else "🟡" if risk < 50 else "🟠" if risk < 75 else "🔴"
            try:
                fu = await bot(GetFullUserRequest(entity))
                r["activity"]["bio"] = getattr(fu.full_user, 'about', '')[:500] or "لا"
            except: pass
            if r["basic"]["username"] and r["basic"]["username"] != "لا يوجد":
                async with aiohttp.ClientSession() as s:
                    try:
                        async with s.get(f"https://t.me/{r['basic']['username']}", headers={'User-Agent': ua.random}, timeout=10) as resp:
                            t = await resp.text()
                            ems = list(set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', t)))
                            if ems: r["exposed"]["emails"] = ems[:10]
                            phs = list(set(re.findall(r'\+?[\d]{8,15}', t)))
                            if phs: r["exposed"]["phones"] = phs[:10]
                    except: pass
        except Exception as e: r["error"] = str(e)[:200]
        return r

    @staticmethod
    def _est(uid):
        if uid < 1000000: return datetime(2013, 8, 14)
        elif uid < 1000000000: return datetime(2016, 3, 15)
        elif uid < 3000000000: return datetime(2018, 6, 20)
        elif uid < 5000000000: return datetime(2020, 1, 10)
        elif uid < 6000000000: return datetime(2021, 6, 15)
        elif uid < 7000000000: return datetime(2022, 8, 20)
        elif uid < 8000000000: return datetime(2023, 6, 1)
        else: return datetime(2024, 3, 1)

# ============================================================
class PhoneRevealer:
    COUNTRIES = {
        "20": ("مصر", ["10", "11", "12", "15"]),
        "966": ("السعودية", ["50", "53", "54", "55", "56", "57", "58", "59"]),
        "971": ("الإمارات", ["50", "52", "54", "55", "56", "58"]),
        "965": ("الكويت", ["50", "55", "60", "65", "66", "67", "69"]),
    }

    @classmethod
    async def reveal(cls, username, cc="20"):
        r = {"username": username, "found": False, "phone": None, "tries": 0, "time": 0}
        info = cls.COUNTRIES.get(cc, ("?", ["10"])); prefixes = info[1]; start = time.time()
        try:
            entity = await bot.get_entity(username.replace("@", "")); tid = entity.id
            nums = []
            for pfx in prefixes[:3]:
                for i in range(0, 3000, 150): nums.append(f"+{cc}{pfx}{i:05d}")
            for i in range(0, len(nums), 40):
                batch = nums[i:i+40]
                try:
                    contacts = [InputPhoneContact(client_id=random.randint(100000, 999999), phone=n, first_name=f"S{random.randint(1,9999)}", last_name="") for n in batch]
                    imp = await bot(ImportContactsRequest(contacts))
                    if imp and imp.users:
                        for u in imp.users:
                            if u.id == tid:
                                for c, n in zip(contacts, batch):
                                    if hasattr(u, 'phone') and u.phone:
                                        r["found"] = True; r["phone"] = n; r["tries"] = i + len(batch)
                                        r["time"] = round(time.time() - start, 1)
                                        try: await bot(DeleteContactsRequest([u]))
                                        except: pass
                                        return r
                    if imp and imp.users:
                        try: await bot(DeleteContactsRequest(imp.users))
                        except: pass
                    r["tries"] = i + len(batch); await asyncio.sleep(2)
                except FloodWaitError as e: await asyncio.sleep(e.seconds)
                except: continue
        except Exception as e: r["error"] = str(e)[:200]
        r["time"] = round(time.time() - start, 1); return r

    @classmethod
    async def check(cls, phone):
        r = {"phone": phone, "registered": False, "user": None}
        try:
            c = InputPhoneContact(client_id=random.randint(100000, 999999), phone=phone, first_name="Chk", last_name="")
            imp = await bot(ImportContactsRequest([c]))
            if imp and imp.users:
                u = imp.users[0]; r["registered"] = True
                r["user"] = {"id": u.id, "username": getattr(u, 'username', None), "name": f"{getattr(u, 'first_name', '')} {getattr(u, 'last_name', '')}".strip()}
                try: await bot(DeleteContactsRequest([u]))
                except: pass
        except: pass
        return r

# ============================================================
class GroupScraper:
    @classmethod
    async def search(cls, kw, limit=25):
        res = []
        try:
            sr = await bot(SearchRequest(q=kw, filter=types.InputMessagesFilterEmpty(), min_date=None, max_date=None, offset_id=0, add_offset=0, limit=limit, max_id=0, min_id=0, hash=0))
            if hasattr(sr, 'chats'):
                for c in sr.chats:
                    if hasattr(c, 'username') and c.username:
                        res.append({"id": c.id, "username": c.username, "title": getattr(c, 'title', ''), "members": getattr(c, 'participants_count', 0), "type": "قناة" if getattr(c, 'broadcast', False) else "جروب", "link": f"https://t.me/{c.username}"})
        except: pass
        async with aiohttp.ClientSession() as s:
            for url in [f"https://tgstat.com/search?q={quote(kw)}", f"https://combot.org/telegram/top/chats?q={quote(kw)}"]:
                try:
                    async with s.get(url, headers={'User-Agent': ua.random}, timeout=15) as resp:
                        for un in set(re.findall(r'@([a-zA-Z][a-zA-Z0-9_]{3,31})', await resp.text())):
                            if not any(x.get('username') == un for x in res): res.append({"username": un, "link": f"https://t.me/{un}", "source": "web"})
                except: pass
        return res[:limit]

# ============================================================
class Unban:
    @classmethod
    def telegram(cls, phone, username=""):
        return f"""Subject: Account Recovery - {phone}
To: recover@telegram.org, login@telegram.org

Dear Telegram Support,
I request restoration of my account:
Phone: {phone} | Username: @{username or 'N/A'}
I believe the restriction was an error. Please review. Thank you."""

    @classmethod
    def whatsapp(cls, phone):
        return f"""Subject: WhatsApp Ban Appeal - {phone}
To: support@whatsapp.com

Dear WhatsApp Support,
I appeal the ban on my account {phone}. Please review. Thank you."""

# ============================================================
class Breach:
    @classmethod
    async def check(cls, email):
        r = {"email": email, "count": 0, "breaches": []}
        try:
            async with aiohttp.ClientSession() as s:
                try:
                    async with s.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}", headers={'User-Agent': 'NinjaGram'}, timeout=15) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            r["breaches"] = [{"name": b.get('Name', ''), "date": b.get('BreachDate', '')} for b in data]
                            r["count"] = len(data)
                except: pass
        except: pass
        return r

# ============================================================
class Faker:
    @classmethod
    async def telegram(cls, name, msg):
        img = Image.new('RGB', (650, 180), color='#17212B'); d = ImageDraw.Draw(img)
        d.text((15, 15), name, fill='#2B9FD9'); d.text((520, 15), datetime.now().strftime("%I:%M %p"), fill='#6C7883')
        d.line([(15, 40), (635, 40)], fill='#1F2C38', width=1); y = 50
        for ln in textwrap.wrap(msg, width=50): d.text((15, y), ln, fill='#FFFFFF'); y += 22
        d.text((15, 155), "⚠️ تعليمي", fill='#FF4444')
        o = BytesIO(); img.save(o, format='PNG'); o.seek(0); o.name = "fake_tg.png"; return o

    @classmethod
    async def whatsapp(cls, name, msg):
        img = Image.new('RGB', (600, 150), color='#075E54'); d = ImageDraw.Draw(img)
        d.rectangle([(0, 0), (600, 40)], fill='#075E54'); d.text((15, 10), name, fill='#FFFFFF')
        d.rectangle([(10, 45), (590, 125)], fill='#DCF8C6'); y = 52
        for ln in textwrap.wrap(msg, width=45): d.text((18, y), ln, fill='#000000'); y += 22
        d.text((15, 130), "⚠️ تعليمي", fill='#FF4444')
        o = BytesIO(); img.save(o, format='PNG'); o.seek(0); o.name = "fake_wa.png"; return o

# ============================================================
class UI:
    @staticmethod
    def main():
        return [
            [Button.inline("📞 تروكولر", b"tc"), Button.inline("🔫 بلاغات", b"rpt")],
            [Button.inline("🕵️ OSINT", b"osint"), Button.inline("📞 كشف رقم", b"reveal")],
            [Button.inline("🔍 جروبات", b"scrape"), Button.inline("🔓 فك حظر", b"unban")],
            [Button.inline("🧬 تسريبات", b"breach"), Button.inline("💣 صيد", b"hunt")],
            [Button.inline("📊 تحليل", b"analyze"), Button.inline("📝 مزور", b"faker")],
            [Button.inline("📱 واتساب", b"wa"), Button.inline("📞 فحص رقم", b"checkreg")],
            [Button.inline("🔄 تحويل", b"convert"), Button.inline("ℹ️ معلومات", b"info")],
        ]

    @staticmethod
    def reports():
        btns = []; row = []
        for k, v in Reporter.TYPES.items():
            row.append(Button.inline(v[0], f"rpt_{k}".encode()))
            if len(row) == 2: btns.append(row); row = []
        if row: btns.append(row)
        btns.append([Button.inline("🔙 رجوع", b"main")]); return btns

# ============================================================
@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.respond("""🧨 **NinjaGram Pro Max Ultra v10**

🔞 أقوى بوت أدوات تيليجرام وواتساب

📞 تروكولر | 🔫 15 بلاغ | 🕵️ OSINT
📞 كشف رقم | 🔍 جروبات | 🔓 فك حظر
🧬 تسريبات | 💣 صيد | 📝 مزور
📊 تحليل | 📱 واتساب | 🔄 تحويل

⚠️ تعليمي وأمني فقط
👨‍💻 @NinjaGram | 📢 @Q_g_r_a_m""", buttons=UI.main(), parse_mode='md')

@bot.on(events.CallbackQuery(data=b"main"))
async def back(event): await event.edit("🧨 **القائمة**", buttons=UI.main(), parse_mode='md')

@bot.on(events.CallbackQuery(data=b"tc"))
async def tc(event): user_states[event.sender_id] = "tc"; await event.edit("📞 **تروكولر**\nأرسل رقم أو اسم:", buttons=[[Button.inline("🔙", b"main")]], parse_mode='md')

@bot.on(events.CallbackQuery(data=b"rpt"))
async def rpt(event): await event.edit("🔫 **بلاغات**\nاختر:", buttons=UI.reports(), parse_mode='md')

@bot.on(events.CallbackQuery(data=re.compile(rb"rpt_(.+)")))
async def rpt_type(event):
    rt = event.data.decode().replace("rpt_", ""); pending_data[event.sender_id] = {"rt": rt}; user_states[event.sender_id] = "rpt_plat"
    await event.edit(f"🔫 **{Reporter.TYPES.get(rt,['?'])[0]}**\nاختر:", buttons=[[Button.inline("📱 تيليجرام", f"rp_tg_{rt}".encode()), Button.inline("💬 واتساب", f"rp_wa_{rt}".encode())], [Button.inline("🔙", b"rpt")]], parse_mode='md')

@bot.on(events.CallbackQuery(data=re.compile(rb"rp_(.+)_(.+)")))
async def rpt_plat(event):
    p, rt = event.data.decode().split("_")[1], "_".join(event.data.decode().split("_")[2:])
    pending_data[event.sender_id].update({"rt": rt, "p": p}); user_states[event.sender_id] = "rpt_tgt"
    await event.edit(f"🔫 **{'تيليجرام' if p=='tg' else 'واتساب'}**\nأرسل {'@' if p=='tg' else '+'} الهدف:", buttons=[[Button.inline("🔙", b"rpt")]], parse_mode='md')

@bot.on(events.CallbackQuery(data=b"osint"))
async def osint(event): user_states[event.sender_id] = "osint"; await event.edit("🕵️ **OSINT**\nأرسل يوزر أو ID:", buttons=[[Button.inline("🔙", b"main")]], parse_mode='md')

@bot.on(events.CallbackQuery(data=b"reveal"))
async def reveal(event):
    await event.edit("📞 **كشف رقم**\nاختر الدولة:", buttons=[[Button.inline("🇪🇬 مصر", b"rv_20"), Button.inline("🇸🇦 السعودية", b"rv_966")], [Button.inline("🇦🇪 الإمارات", b"rv_971"), Button.inline("🇰🇼 الكويت", b"rv_965")], [Button.inline("🔙", b"main")]], parse_mode='md')

@bot.on(events.CallbackQuery(data=re.compile(rb"rv_(.+)")))
async def rv_cc(event): pending_data[event.sender_id] = {"cc": event.data.decode().replace("rv_", "")}; user_states[event.sender_id] = "rv_tgt"; await event.edit("📞 **كشف الرقم**\nأرسل يوزر:", buttons=[[Button.inline("🔙", b"reveal")]], parse_mode='md')

@bot.on(events.CallbackQuery(data=b"scrape"))
async def scrape(event): user_states[event.sender_id] = "scrape"; await event.edit("🔍 **جروبات**\nأرسل كلمة:", buttons=[[Button.inline("🔙", b"main")]], parse_mode='md')

@bot.on(events.CallbackQuery(data=b"unban"))
async def unban(event): await event.edit("🔓 **فك حظر**\nاختر:", buttons=[[Button.inline("📱 تيليجرام", b"ub_tg"), Button.inline("💬 واتساب", b"ub_wa")], [Button.inline("🔙", b"main")]], parse_mode='md')

@bot.on(events.CallbackQuery(data=b"ub_tg"))
async def ub_tg(event): user_states[event.sender_id] = "ub_tg"; await event.edit("🔓 **تيليجرام**\nأرسل الرقم:", buttons=[[Button.inline("🔙", b"unban")]], parse_mode='md')

@bot.on(events.CallbackQuery(data=b"ub_wa"))
async def ub_wa(event): user_states[event.sender_id] = "ub_wa"; await event.edit("🔓 **واتساب**\nأرسل الرقم:", buttons=[[Button.inline("🔙", b"unban")]], parse_mode='md')

@bot.on(events.CallbackQuery(data=b"breach"))
async def breach(event): user_states[event.sender_id] = "breach"; await event.edit("🧬 **تسريبات**\nأرسل إيميل:", buttons=[[Button.inline("🔙", b"main")]], parse_mode='md')

@bot.on(events.CallbackQuery(data=b"hunt"))
async def hunt(event):
    if not Security.rate(event.sender_id, "hunt", 3): await event.answer("⏳ انتظر", alert=True); return
    await event.edit("💣 **صيد...**", parse_mode='md')
    pool = set(); c = "abcdefghijklmnopqrstuvwxyz"; l = ["111","222","333","444","555","666","777","888","999"]
    for _ in range(200): a, b = random.choice(c), random.choice(c); pool.update([f"{a}{b}{random.choice(l)}", f"{a}{random.choice('aeiou')}{b}"])
    pool = {u for u in pool if 3 <= len(u) <= 12}; found = []
    async with aiohttp.ClientSession() as s:
        sem = asyncio.Semaphore(30)
        async def chk(u):
            async with sem:
                try:
                    async with s.get(f"https://t.me/{u}", headers={'User-Agent': ua.random}, timeout=5) as r:
                        if r.status == 404: found.append(u)
                except: pass
        await asyncio.gather(*[chk(u) for u in list(pool)[:80]])
    txt = f"💣 **{len(found)} يوزر**\n\n" + "\n".join([f"• @{u}" for u in found[:20]]) if found else "❌ لا نتائج"
    await event.edit(txt, buttons=[[Button.inline("🔄 صيد", b"hunt"), Button.inline("🔙", b"main")]], parse_mode='md')

@bot.on(events.CallbackQuery(data=b"analyze"))
async def analyze(event): user_states[event.sender_id] = "analyze"; await event.edit("📊 **تحليل**\nأرسل @:", buttons=[[Button.inline("🔙", b"main")]], parse_mode='md')

@bot.on(events.CallbackQuery(data=b"faker"))
async def faker(event): await event.edit("📝 **مزور**\nاختر:", buttons=[[Button.inline("📱 تيليجرام", b"fk_tg"), Button.inline("💬 واتساب", b"fk_wa")], [Button.inline("🔙", b"main")]], parse_mode='md')

@bot.on(events.CallbackQuery(data=b"fk_tg"))
async def fk_tg(event): user_states[event.sender_id] = "fk_tg"; await event.edit("📝 **تيليجرام**\nأرسل: الاسم|الرسالة", buttons=[[Button.inline("🔙", b"faker")]], parse_mode='md')

@bot.on(events.CallbackQuery(data=b"fk_wa"))
async def fk_wa(event): user_states[event.sender_id] = "fk_wa"; await event.edit("📝 **واتساب**\nأرسل: الاسم|الرسالة", buttons=[[Button.inline("🔙", b"faker")]], parse_mode='md')

@bot.on(events.CallbackQuery(data=b"wa"))
async def wa(event): user_states[event.sender_id] = "wa"; await event.edit("📱 **واتساب**\nأرسل الرقم:", buttons=[[Button.inline("🔙", b"main")]], parse_mode='md')

@bot.on(events.CallbackQuery(data=b"checkreg"))
async def checkreg(event): user_states[event.sender_id] = "checkreg"; await event.edit("📞 **فحص رقم**\nأرسل الرقم:", buttons=[[Button.inline("🔙", b"main")]], parse_mode='md')

@bot.on(events.CallbackQuery(data=b"convert"))
async def convert(event): user_states[event.sender_id] = "convert"; await event.edit("🔄 **تحويل**\nأرسل @ أو ID:", buttons=[[Button.inline("🔙", b"main")]], parse_mode='md')

@bot.on(events.CallbackQuery(data=b"info"))
async def info(event): await event.edit("""🧨 **NinjaGram Pro Max Ultra v10**
20+ خدمة | 15 بلاغ | OSINT | كشف أرقام
تسريبات | صيد | مزور | تحليل
👨‍💻 @NinjaGram | 📢 @Q_g_r_a_m""", buttons=[[Button.inline("🔙", b"main")]], parse_mode='md')

# ============================================================
@bot.on(events.NewMessage(func=lambda e: e.sender_id in user_states and not e.text.startswith('/')))
async def handle(event):
    uid = event.sender_id; st = user_states.pop(uid, None); txt = event.text.strip()
    if not st: return
    try:
        if st == "tc":
            ld = await event.respond("📞 **بحث...**")
            if txt.startswith('+') or any(c.isdigit() for c in txt[:3]):
                r = await Truecaller.lookup(txt)
                out = f"📞 **{r['phone']}**\n✅ {'نعم' if r['valid'] else 'لا'} | 📡 {r['carrier']}\n🌍 {r['country']} | 📍 {r['location']}\n⚠️ سبام: {r['spam']} | 🎯 {r['risk']}/100 {r['level']}"
                if r['social']: out += f"\n📱 {', '.join(r['social'][:6])}"
            else:
                res = await Truecaller.reverse(txt); out = f"🔍 **{txt}**\n\n" + ("\n".join([f"📞 {x['phone']}" for x in res[:12]]) if res else "❌ لا نتائج")
            await ld.edit(out, buttons=[[Button.inline("🔙", b"main")]], parse_mode='md')
        elif st == "rpt_tgt":
            d = pending_data.pop(uid, {}); rt = d.get("rt", "spam"); p = "telegram" if d.get("p") == "tg" else "whatsapp"
            ld = await event.respond("🔫 **بلاغ...**"); r = Reporter.generate(rt, txt, p)
            await ld.edit(f"🔫 **{r['type']}**\n📋 `{r['id']}`\n⚠️ {r['severity'].upper()}\n📧 `{r['email']}`\n```{r['body'][:1500]}```", buttons=[[Button.inline("🔙", b"rpt")]], parse_mode='md')
        elif st == "osint":
            ld = await event.respond("🕵️ **فحص...**"); r = await Osint.deep(txt)
            if "error" in r: await ld.edit(f"❌ {r['error']}", buttons=[[Button.inline("🔙", b"main")]]); return
            out = f"🕵️ **OSINT**\n\n📋 ID: `{r['basic'].get('id')}`\n🔖 @{r['basic'].get('username')}\n👤 {r['basic'].get('full')}\n📞 {r['basic'].get('phone')}\n✅ {r['basic'].get('verified')} | ⭐ {r['basic'].get('premium')}\n⚠️ احتيال: {r['basic'].get('scam')}"
            if r['activity'].get('created'): out += f"\n📅 {r['activity'].get('created')} | ⏳ {r['activity'].get('age')}"
            if r['security']: out += f"\n\n⚠️ **الأمان:**\n" + "\n".join([f"• {i}" for i in r['security'][:8]])
            out += f"\n\n🎯 **الخطورة:** {r['risk']}/100 {r.get('risk_level','?')}"
            if r.get('exposed', {}).get('emails'): out += f"\n📧 {', '.join(r['exposed']['emails'][:4])}"
            await ld.edit(out, buttons=[[Button.inline("🔙", b"main")]], parse_mode='md')
        elif st == "rv_tgt":
            d = pending_data.pop(uid, {}); cc = d.get("cc", "20"); ld = await event.respond("📞 **كشف...**\n⏳ يستغرق وقتاً")
            r = await PhoneRevealer.reveal(txt, cc)
            out = f"✅ **تم!**\n📞 `{r['phone']}`\n🔢 {r['tries']} | ⏱️ {r['time']}s" if r["found"] else f"❌ **فشل**\n🔢 {r['tries']} | ⏱️ {r['time']}s"
            await ld.edit(out, buttons=[[Button.inline("🔙", b"reveal")]], parse_mode='md')
        elif st == "scrape":
            ld = await event.respond(f"🔍 **{txt}**"); res = await GroupScraper.search(txt)
            out = f"🔍 **{txt}**\n\n" + "\n".join([f"{i+1}. [{g.get('title',g.get('username'))}]({g.get('link')}) | {g.get('members',0)}" for i,g in enumerate(res[:15])]) if res else "❌ لا نتائج"
            await ld.edit(out, buttons=[[Button.inline("🔙", b"main")]], parse_mode='md')
        elif st == "ub_tg": await event.respond(Unban.telegram(txt), buttons=[[Button.inline("🔙", b"unban")]], parse_mode='md')
        elif st == "ub_wa": await event.respond(Unban.whatsapp(txt), buttons=[[Button.inline("🔙", b"unban")]], parse_mode='md')
        elif st == "breach":
            ld = await event.respond("🧬 **فحص...**"); r = await Breach.check(txt)
            out = f"🧬 **{txt}**\n🔢 تسريبات: {r['count']}\n" + "\n".join([f"• {b['name']} ({b['date']})" for b in r.get('breaches',[])[:10]])
            await ld.edit(out, buttons=[[Button.inline("🔙", b"main")]], parse_mode='md')
        elif st == "analyze":
            ld = await event.respond("📊 **تحليل...**")
            try:
                e = await bot.get_entity(txt.replace("@", "")); fc = await bot(GetFullChannelRequest(e))
                out = f"📊 **{getattr(e,'title',txt)}**\n🆔 `{e.id}`\n👥 {getattr(fc.full_chat,'participants_count',0):,}\n📝 {getattr(fc.full_chat,'about','')[:300]}"
                await ld.edit(out, buttons=[[Button.inline("🔙", b"main")]], parse_mode='md')
            except: await ld.edit("❌ غير موجود", buttons=[[Button.inline("🔙", b"main")]])
        elif st == "fk_tg":
            if '|' in txt:
                n, m = txt.split('|', 1); img = await Faker.telegram(n.strip(), m.strip())
                await bot.send_file(event.chat_id, img, caption="📝 تعليمي", buttons=[[Button.inline("🔙", b"faker")]])
            else: await event.respond("❌ الاسم|الرسالة", buttons=[[Button.inline("🔙", b"faker")]])
        elif st == "fk_wa":
            if '|' in txt:
                n, m = txt.split('|', 1); img = await Faker.whatsapp(n.strip(), m.strip())
                await bot.send_file(event.chat_id, img, caption="📝 تعليمي", buttons=[[Button.inline("🔙", b"faker")]])
            else: await event.respond("❌ الاسم|الرسالة", buttons=[[Button.inline("🔙", b"faker")]])
        elif st == "wa": await event.respond(f"📱 https://wa.me/{txt.replace('+','')}", buttons=[[Button.inline("🔙", b"main")]])
        elif st == "checkreg":
            ld = await event.respond("📞 **فحص...**"); r = await PhoneRevealer.check(txt)
            out = f"✅ **مسجل**\n🆔 `{r['user']['id']}`\n👤 {r['user']['name']}\n🔖 @{r['user'].get('username','لا')}" if r["registered"] else "❌ غير مسجل"
            await ld.edit(out, buttons=[[Button.inline("🔙", b"main")]], parse_mode='md')
        elif st == "convert":
            try:
                e = await bot.get_entity(int(txt) if txt.lstrip('-').isdigit() else txt.replace("@", "")); un = getattr(e, 'username', None)
                await event.respond(f"🔄\n🆔 `{e.id}`\n🔖 @{un or 'لا'}\n👤 {getattr(e,'first_name','')} {getattr(e,'last_name','')}", buttons=[[Button.inline("🔙", b"main")]], parse_mode='md')
            except: await event.respond("❌ غير موجود", buttons=[[Button.inline("🔙", b"main")]])
    except Exception as e: logger.error(f"Error: {e}"); await event.respond(f"❌ خطأ", buttons=[[Button.inline("🔙", b"main")]])

# ============================================================
if __name__ == '__main__':
    print("🧨 NinjaGram Pro Max Ultra v10")
    async def main():
        await bot.start(bot_token=BOT_TOKEN)
        me = await bot.get_me()
        print(f"✅ @{me.username}")
        await bot.run_until_disconnected()
    asyncio.run(main())
