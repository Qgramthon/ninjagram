# bot.py
import asyncio, uuid, os, re, random, string, aiohttp
from datetime import datetime
from urllib.parse import quote
from telethon import TelegramClient, events, Button
from telethon.errors import FloodWaitError
from telethon.tl.functions.channels import InviteToChannelRequest
from shared import *
from collections import Counter

bot = TelegramClient(f'bot_session_{uuid.uuid4().hex[:6]}', BOT_API_ID, BOT_API_HASH)
START_IMAGE = "start.jpg"
allowed_chats = set()

# ============================================
# الكلمات المسموحة للبوت
# ============================================
ALLOWED_KEYWORDS = [
    "Qthon", "تيليثون", "لوحة تحكم", "طريقة جلب", "التحقق من المطور",
    "تم التحقق", "فشل التحقق", "التحقق معطل", "خيارات المطور",
    "المستخدمين", "النشطاء", "أكثر الأوامر", "المجموعات", "القنوات",
    "إذاعة", "رجوع", "قريباً", "غير مصرح", "تم تفعيل",
    "جاري إضافة", "تم بدء الإضافة", "فشل الإضافة", "تم إيقاف",
    "توقف", "لا توجد جلسات", "تم الإضافة", "إيقاف مستخدم",
    "أرسل رقم", "تنصيب", "راسل المطور", "تم إرجاع", "إرجاع مستخدم",
    "تم إيقاف التنصيب", "المستخدمين الموقوفين", "موقوف",
    "بدء التنصيب", "اختر خياراً",
    # كلمات الأوامر الجديدة
    "صيد", "يوزرات", "تحميل", "فيديو", "معلومات", "آيدي", "فحص", "متاح"
]

# ============================================
# تخزين حالات المستخدمين
# ============================================
user_states = {}

# ============================================
# دوال مساعدة
# ============================================
def is_allowed_text(text):
    if not text: return False
    for keyword in ALLOWED_KEYWORDS:
        if keyword in text: return True
    return False

def dev_panel_markup():
    lock_text = "فتح خيارات المطور" if dev_access_locked else "قفل خيارات المطور"
    return [
        [Button.inline("👥 عدد المستخدمين", b"dev_users"), Button.inline("🟢 النشطاء حالياً", b"dev_active")],
        [Button.inline("📊 أكثر الأوامر", b"dev_topcmd"), Button.inline("📋 قائمة المجموعات", b"dev_groups")],
        [Button.inline("📢 قائمة القنوات", b"dev_channels"), Button.inline("📣 إذاعة", b"dev_broadcast")],
        [Button.inline("➕ إضافة أعضاء لجروب", b"dev_addto"), Button.inline("⛔ إيقاف مستخدم", b"dev_stopuser")],
        [Button.inline("🔄 إرجاع مستخدم", b"dev_unblockuser")],
        [Button.inline(lock_text, b"dev_lock")],
    ]

def main_menu_markup():
    return [
        [Button.inline("🎯 صيد يوزرات", b"hunt_menu")],
        [Button.inline("🎬 تحميل فيديو", b"video_menu")],
        [Button.inline("🔍 معلومات حساب", b"info_start")],
        [Button.inline("🔗 فتح بالآيدي", b"open_start")],
        [Button.inline("🔄 تحويل يوزر/آيدي", b"resolve_start")],
        [Button.inline("✅ فحص يوزر", b"check_start")],
    ]

def hunt_menu_markup():
    return [
        [Button.inline("📱 تيليجرام", b"hunt_tg"), Button.inline("📷 انستجرام", b"hunt_ig")],
        [Button.inline("🎵 تيكتوك", b"hunt_tk"), Button.inline("🌐 الثلاثة معاً", b"hunt_all")],
        [Button.inline("🔙 رجوع", b"back_main")],
    ]

def video_menu_markup():
    return [
        [Button.inline("🎵 تيكتوك", b"dl_tiktok"), Button.inline("📷 انستجرام", b"dl_instagram")],
        [Button.inline("▶️ يوتيوب", b"dl_youtube"), Button.inline("📘 فيسبوك", b"dl_facebook")],
        [Button.inline("🔙 رجوع", b"back_main")],
    ]

def back_markup():
    return [[Button.inline("🔙 رجوع للقائمة", b"back_main")]]

# ============================================
# مولد اليوزرات
# ============================================
def generate_usernames(platform="tg"):
    usernames = []
    chars = string.ascii_uppercase
    vowels = "AEIOU"
    consonants = "BCDFGHJKLMNPQRSTVWXYZ"
    nums = "0123456789"
    
    for _ in range(50):
        l1 = random.choice(consonants)
        l2 = random.choice(vowels)
        d = random.choice("1379")
        usernames.extend([f"{l1}{l2}{d}", f"{d}{l1}{l2}", f"{l1}{d}{l2}"])
    
    for _ in range(30):
        l = random.choice(chars)
        d = random.choice(nums)
        usernames.extend([f"{l}{d}{l}", f"{d}{l}{d}"])
    
    for l in random.sample(chars, 10):
        usernames.append(f"{l}{l}{l}")
    
    lucky = ["777", "888", "999", "111", "333", "555"]
    for num in lucky:
        for l in random.sample(chars, 5):
            usernames.extend([f"{num}{l}", f"{l}{num}"])
    
    vip = ["VIP", "KING", "BOSS", "GOD", "LEO", "ACE", "PRO", "X", "OG"]
    for word in vip:
        for d in "1379":
            usernames.extend([f"{word}{d}", f"{d}{word}"])
    
    for _ in range(30):
        l1, l2 = random.sample(chars, 2)
        d1, d2 = random.sample(nums, 2)
        usernames.extend([f"{l1}{l2}{d1}{d2}", f"{d1}{d2}{l1}{l2}"])
    
    return list(set(usernames))

# ============================================
# دوال الفحص
# ============================================
async def check_tg_username(username):
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://fragment.com/username/{username.lower()}"
            headers = {'User-Agent': 'Mozilla/5.0'}
            async with session.get(url, headers=headers, timeout=8) as resp:
                text = await resp.text()
                if "Not Found" in text or resp.status == 404:
                    return f"✅ @{username}"
    except: pass
    return None

async def check_ig_username(username):
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://www.instagram.com/{username}/"
            headers = {'User-Agent': 'Mozilla/5.0'}
            async with session.get(url, headers=headers, timeout=8) as resp:
                if resp.status == 404:
                    return f"✅ @{username}"
    except: pass
    return None

async def check_tk_username(username):
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://www.tiktok.com/@{username}"
            headers = {'User-Agent': 'Mozilla/5.0'}
            async with session.get(url, headers=headers, timeout=8) as resp:
                if resp.status == 404:
                    return f"✅ @{username}"
    except: pass
    return None

async def get_telegram_info(username):
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://t.me/{username}"
            headers = {'User-Agent': 'Mozilla/5.0'}
            async with session.get(url, headers=headers, timeout=8) as resp:
                text = await resp.text()
                info = {"username": username, "url": url, "exists": resp.status == 200}
                name_match = re.search(r'<meta property="og:title" content="([^"]+)"', text)
                if name_match: info["display_name"] = name_match.group(1)
                image_match = re.search(r'<meta property="og:image" content="([^"]+)"', text)
                if image_match: info["profile_image"] = image_match.group(1)
                desc_match = re.search(r'<meta property="og:description" content="([^"]+)"', text)
                if desc_match: info["bio"] = desc_match.group(1)
                return info
    except: return {"exists": False, "error": "فشل الاتصال"}

async def download_video(url, platform):
    try:
        if platform == "tiktok":
            api_url = f"https://tikwm.com/api/?url={quote(url)}"
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, timeout=15) as resp:
                    data = await resp.json()
                    if data.get("code") == 0:
                        return {"success": True, "video_url": data.get("data", {}).get("play"), "platform": "تيكتوك"}
        elif platform == "instagram":
            return {"success": False, "error": "استخدم @instasave_bot لتحميل فيديوهات انستجرام"}
        elif platform == "youtube":
            return {"success": False, "error": "استخدم @vid_downloader_bot لتحميل فيديوهات يوتيوب"}
        elif platform == "facebook":
            return {"success": False, "error": "استخدم @fbdownloader_bot لتحميل فيديوهات فيسبوك"}
        return {"success": False, "error": "فشل التحميل"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ============================================
# حدث: منع الرسائل غير المصرحة
# ============================================
@bot.on(events.NewMessage(outgoing=True))
async def block_unauthorized(event):
    if event.chat_id not in allowed_chats:
        await event.delete()
        return
    if not is_allowed_text(event.text):
        await event.delete()
        return

# ============================================
# أمر: /start
# ============================================
@bot.on(events.NewMessage(pattern='/start'))
async def bot_start(event):
    allowed_chats.add(event.chat_id)
    user_id = event.sender_id

    if is_dev(user_id):
        await bot.send_message(
            event.chat_id,
            "**🜲 لوحة تحكم Ninjagram**\n\nاختر خياراً من القائمة:",
            buttons=dev_panel_markup(),
            parse_mode='md'
        )
        return

    caption = (
        "🐙 **Ninjathon UserBot**\n\n"
        "🎯 **الخدمات:**\n"
        "1️⃣ صيد يوزرات (تيليجرام | انستا | تيكتوك)\n"
        "2️⃣ تحميل فيديوهات\n"
        "3️⃣ معلومات حساب تيليجرام\n"
        "4️⃣ فتح بالآيدي\n"
        "5️⃣ تحويل يوزر/آيدي\n"
        "6️⃣ فحص توفر يوزر\n\n"
        "• Channel: @Q_g_r_a_m"
    )
    buttons = main_menu_markup()
    
    if os.path.exists(START_IMAGE):
        await bot.send_file(event.chat_id, file=START_IMAGE, caption=caption, buttons=buttons, parse_mode='md')
    else:
        await bot.send_message(event.chat_id, caption, buttons=buttons, parse_mode='md')

# ============================================
# أوامر سريعة
# ============================================
@bot.on(events.NewMessage(pattern='/hunt'))
async def cmd_hunt(event):
    allowed_chats.add(event.chat_id)
    await event.respond("🎯 **اختر منصة الصيد:**", buttons=hunt_menu_markup(), parse_mode='md')

@bot.on(events.NewMessage(pattern='/video'))
async def cmd_video(event):
    allowed_chats.add(event.chat_id)
    await event.respond("🎬 **اختر منصة التحميل:**", buttons=video_menu_markup(), parse_mode='md')

@bot.on(events.NewMessage(pattern='/info'))
async def cmd_info(event):
    allowed_chats.add(event.chat_id)
    user_states[event.sender_id] = "waiting_info"
    await event.respond("🔍 **أرسل يوزر تيليجرام:**\nمثال: @username", buttons=back_markup(), parse_mode='md')

@bot.on(events.NewMessage(pattern='/open'))
async def cmd_open(event):
    allowed_chats.add(event.chat_id)
    user_states[event.sender_id] = "waiting_open"
    await event.respond("🔗 **أرسل الآيدي الرقمي:**\nمثال: 123456789", buttons=back_markup(), parse_mode='md')

@bot.on(events.NewMessage(pattern='/resolve'))
async def cmd_resolve(event):
    allowed_chats.add(event.chat_id)
    user_states[event.sender_id] = "waiting_resolve"
    await event.respond("🔄 **أرسل اليوزر أو الآيدي:**\nمثال: @username أو 123456789", buttons=back_markup(), parse_mode='md')

@bot.on(events.NewMessage(pattern='/check'))
async def cmd_check(event):
    allowed_chats.add(event.chat_id)
    user_states[event.sender_id] = "waiting_check"
    await event.respond("✅ **أرسل اليوزر للفحص:**\nمثال: @username", buttons=back_markup(), parse_mode='md')

# ============================================
# حدث: أزرار الكول باك
# ============================================
@bot.on(events.CallbackQuery())
async def callback_handler(event):
    allowed_chats.add(event.chat_id)
    data = event.data.decode()
    user_id = event.sender_id

    # === المطور فقط ===
    if data.startswith("dev_") and not is_dev(user_id):
        await event.answer("غير مصرح", alert=True)
        return

    # === الرجوع للقائمة الرئيسية ===
    if data == "back_main":
        caption = "🐙 **Ninjathon UserBot**\n\nاختر الخدمة:"
        await event.edit(caption, buttons=main_menu_markup(), parse_mode='md')
        await event.answer()
        return

    # === قائمة الصيد ===
    if data == "hunt_menu":
        await event.edit("🎯 **اختر منصة الصيد:**", buttons=hunt_menu_markup(), parse_mode='md')
        await event.answer()
        return

    # === صيد تيليجرام ===
    if data == "hunt_tg":
        await event.edit("📱 **جاري صيد يوزرات تيليجرام...**\n⏳ استنى شوية...", parse_mode='md')
        usernames = generate_usernames("tg")[:300]
        found = []
        async with aiohttp.ClientSession() as session:
            sem = asyncio.Semaphore(30)
            async def check(u):
                async with sem: return await check_tg_username(u)
            results = await asyncio.gather(*[check(u) for u in usernames])
            found = [r for r in results if r]
        
        if found:
            text = f"✅ **تم العثور على {len(found)} يوزر تيليجرام:**\n\n"
            text += "\n".join(found[:30])
            if len(found) > 30: text += f"\n\n... و {len(found)-30} آخرين"
        else:
            text = "❌ **لم يتم العثور على يوزرات متاحة**"
        await event.edit(text, buttons=back_markup(), parse_mode='md')
        await event.answer()
        return

    # === صيد انستجرام ===
    if data == "hunt_ig":
        await event.edit("📷 **جاري صيد يوزرات انستجرام...**\n⏳ استنى شوية...", parse_mode='md')
        usernames = generate_usernames("ig")[:300]
        found = []
        async with aiohttp.ClientSession() as session:
            sem = asyncio.Semaphore(30)
            async def check(u):
                async with sem: return await check_ig_username(u.lower())
            results = await asyncio.gather(*[check(u) for u in usernames])
            found = [r for r in results if r]
        
        if found:
            text = f"✅ **تم العثور على {len(found)} يوزر انستجرام:**\n\n"
            text += "\n".join(found[:30])
        else:
            text = "❌ **لم يتم العثور على يوزرات متاحة**"
        await event.edit(text, buttons=back_markup(), parse_mode='md')
        await event.answer()
        return

    # === صيد تيكتوك ===
    if data == "hunt_tk":
        await event.edit("🎵 **جاري صيد يوزرات تيكتوك...**\n⏳ استنى شوية...", parse_mode='md')
        usernames = generate_usernames("tk")[:300]
        found = []
        async with aiohttp.ClientSession() as session:
            sem = asyncio.Semaphore(30)
            async def check(u):
                async with sem: return await check_tk_username(u.lower())
            results = await asyncio.gather(*[check(u) for u in usernames])
            found = [r for r in results if r]
        
        if found:
            text = f"✅ **تم العثور على {len(found)} يوزر تيكتوك:**\n\n"
            text += "\n".join(found[:30])
        else:
            text = "❌ **لم يتم العثور على يوزرات متاحة**"
        await event.edit(text, buttons=back_markup(), parse_mode='md')
        await event.answer()
        return

    # === صيد الكل ===
    if data == "hunt_all":
        await event.edit("🌐 **جاري صيد يوزرات من الثلاث منصات...**\n⏳ استنى شوية...", parse_mode='md')
        usernames = generate_usernames()[:200]
        all_found = {"tg": [], "ig": [], "tk": []}
        async with aiohttp.ClientSession() as session:
            sem = asyncio.Semaphore(20)
            async def check_all(u):
                async with sem:
                    tg = await check_tg_username(u)
                    ig = await check_ig_username(u.lower())
                    tk = await check_tk_username(u.lower())
                    return {"tg": tg, "ig": ig, "tk": tk}
            results = await asyncio.gather(*[check_all(u) for u in usernames])
            for r in results:
                if r["tg"]: all_found["tg"].append(r["tg"])
                if r["ig"]: all_found["ig"].append(r["ig"])
                if r["tk"]: all_found["tk"].append(r["tk"])
        
        text = f"✅ **نتائج الصيد الشامل:**\n\n"
        text += f"📱 تيليجرام: {len(all_found['tg'])} يوزر\n"
        text += f"📷 انستجرام: {len(all_found['ig'])} يوزر\n"
        text += f"🎵 تيكتوك: {len(all_found['tk'])} يوزر\n"
        if all_found["tg"]:
            text += f"\n**أفضل يوزرات تيليجرام:**\n" + "\n".join(all_found["tg"][:10])
        await event.edit(text, buttons=back_markup(), parse_mode='md')
        await event.answer()
        return

    # === قائمة التحميل ===
    if data == "video_menu":
        await event.edit("🎬 **اختر منصة التحميل:**", buttons=video_menu_markup(), parse_mode='md')
        await event.answer()
        return

    # === تحميل فيديو ===
    if data.startswith("dl_"):
        platform = data.replace("dl_", "")
        platforms_ar = {"tiktok": "تيكتوك", "instagram": "انستجرام", "youtube": "يوتيوب", "facebook": "فيسبوك"}
        user_states[user_id] = f"waiting_video_{platform}"
        await event.edit(f"🎬 **تحميل من {platforms_ar.get(platform, platform)}**\n\nأرسل رابط الفيديو:", buttons=back_markup(), parse_mode='md')
        await event.answer()
        return

    # === معلومات حساب ===
    if data == "info_start":
        user_states[user_id] = "waiting_info"
        await event.edit("🔍 **أرسل يوزر تيليجرام:**\nمثال: @username", buttons=back_markup(), parse_mode='md')
        await event.answer()
        return

    # === فتح بالآيدي ===
    if data == "open_start":
        user_states[user_id] = "waiting_open"
        await event.edit("🔗 **أرسل الآيدي الرقمي:**\nمثال: 123456789", buttons=back_markup(), parse_mode='md')
        await event.answer()
        return

    # === تحويل ===
    if data == "resolve_start":
        user_states[user_id] = "waiting_resolve"
        await event.edit("🔄 **أرسل اليوزر أو الآيدي:**", buttons=back_markup(), parse_mode='md')
        await event.answer()
        return

    # === فحص يوزر ===
    if data == "check_start":
        user_states[user_id] = "waiting_check"
        await event.edit("✅ **أرسل اليوزر للفحص:**\nمثال: @username", buttons=back_markup(), parse_mode='md')
        await event.answer()
        return

    # === أزرار المطور ===
    await handle_dev_callback(event)

# ============================================
# دوال أزرار المطور
# ============================================
async def handle_dev_callback(event):
    data = event.data.decode()
    
    if data == "dev_back":
        await event.edit("**🜲 لوحة تحكم Qthon**\n\nاختر خياراً.", buttons=dev_panel_markup(), parse_mode='md')
        return

    if data == "dev_lock":
        global dev_access_locked
        dev_access_locked = not dev_access_locked
        state = "مقفلة" if dev_access_locked else "مفتوحة"
        await event.answer(f"خيارات المطور الآن {state}", alert=True)
        await event.edit("**🜲 لوحة تحكم Qthon**\n\nاختر خياراً.", buttons=dev_panel_markup(), parse_mode='md')
        return

    if data == "dev_users":
        total = len(active_clients)
        msg = f"**👥 إجمالي المستخدمين:** {total}\n\n"
        for phone, info in user_info_cache.items():
            username = f"@{info.get('username')}" if info.get('username') else "بدون معرف"
            blocked = " ⛔موقوف" if phone in blocked_users else ""
            msg += f"• {info.get('first_name', 'غير معروف')} | {username} | {phone}{blocked}\n"
        await event.edit(msg, parse_mode='md', buttons=[[Button.inline("رجوع", b"dev_back")]])
        return

    if data == "dev_active":
        msg = f"**🟢 النشطاء حالياً:** {len(active_clients)}\n\n"
        for phone, client in active_clients.items():
            info = user_info_cache.get(phone, {})
            name = info.get('first_name', phone)
            uname = f" @{info.get('username')}" if info.get('username') else ""
            msg += f"• {name}{uname}\n"
        await event.edit(msg, parse_mode='md', buttons=[[Button.inline("رجوع", b"dev_back")]])
        return

    if data == "dev_topcmd":
        all_cmds = Counter()
        for cmds in command_stats.values(): all_cmds.update(cmds)
        top = all_cmds.most_common(10)
        msg = "**📊 أكثر الأوامر:**\n\n" + "\n".join([f"{i}. .{c}: {n}" for i, (c, n) in enumerate(top, 1)]) if top else "لا توجد"
        await event.edit(msg, parse_mode='md', buttons=[[Button.inline("رجوع", b"dev_back")]])
        return

    if data == "dev_groups":
        msg = "**📋 المجموعات:**\n\n"
        found = False
        for phone, client in active_clients.items():
            try:
                dialogs = await client.get_dialogs(limit=200)
                groups = [d for d in dialogs if d.is_group and not d.is_channel]
                if groups:
                    found = True
                    info = user_info_cache.get(phone, {})
                    msg += f"**{info.get('first_name', phone)}:**\n"
                    for g in groups[:10]: msg += f"  • {g.name} (ID: {g.id})\n"
            except: pass
        if not found: msg += "لا توجد مجموعات."
        await event.edit(msg, parse_mode='md', buttons=[[Button.inline("رجوع", b"dev_back")]])
        return

    if data == "dev_channels":
        msg = "**📢 القنوات:**\n\n"
        found = False
        for phone, client in active_clients.items():
            try:
                dialogs = await client.get_dialogs(limit=200)
                channels = [d for d in dialogs if d.is_channel and not d.is_group]
                if channels:
                    found = True
                    info = user_info_cache.get(phone, {})
                    msg += f"**{info.get('first_name', phone)}:**\n"
                    for c in channels[:10]: msg += f"  • {c.name} (ID: {c.id})\n"
            except: pass
        if not found: msg += "لا توجد قنوات."
        await event.edit(msg, parse_mode='md', buttons=[[Button.inline("رجوع", b"dev_back")]])
        return

    if data == "dev_addto":
        pending_input[event.sender_id] = "addto"
        await event.edit("**➕ أرسل يوزر الجروب:**", buttons=[[Button.inline("رجوع", b"dev_back")]], parse_mode='md')
        return

    if data == "dev_stopuser":
        pending_input[event.sender_id] = "stopuser"
        msg = "**⛔ أرسل رقم المستخدم:**\n\n" + "\n".join([f"• {p}: {i.get('first_name', p)}" for p, i in user_info_cache.items()])
        await event.edit(msg, buttons=[[Button.inline("رجوع", b"dev_back")]], parse_mode='md')
        return

    if data == "dev_unblockuser":
        if not blocked_users: await event.answer("لا يوجد", alert=True); return
        pending_input[event.sender_id] = "unblockuser"
        msg = "**🔄 أرسل رقم المستخدم:**\n\n" + "\n".join([f"• {p}" for p in blocked_users])
        await event.edit(msg, buttons=[[Button.inline("رجوع", b"dev_back")]], parse_mode='md')
        return

    if data == "dev_broadcast":
        await event.answer("قريباً", alert=True)
        return

# ============================================
# حدث: معالجة المدخلات
# ============================================
@bot.on(events.NewMessage(func=lambda e: e.sender_id in pending_input or e.sender_id in user_states))
async def handle_input(event):
    allowed_chats.add(event.chat_id)
    user_id = event.sender_id
    
    # === مدخلات المطور ===
    if user_id in pending_input:
        await handle_dev_input(event)
        return
    
    # === مدخلات المستخدمين ===
    if user_id in user_states:
        await handle_user_input(event)
        return

async def handle_dev_input(event):
    user_id = event.sender_id
    action = pending_input.pop(user_id, None)
    
    if action == "addto":
        group = event.text.strip().replace('@', '')
        total = 0
        for phone, client in active_clients.items():
            try:
                target = await client.get_entity(group)
                async for dialog in client.iter_dialogs():
                    if dialog.is_group:
                        async for user in client.iter_participants(dialog.id, limit=5):
                            try:
                                await client(InviteToChannelRequest(target, [user.id]))
                                total += 1; await asyncio.sleep(2)
                            except FloodWaitError as e: await asyncio.sleep(e.seconds)
                            except: pass
            except: pass
        await event.respond(f"**✅ تمت الإضافة: {total} عضو**", parse_mode='md')

    elif action == "stopuser":
        phone = event.text.strip()
        if not phone.startswith('+'): phone = f"+{phone}"
        blocked_users.add(phone)
        if phone in active_clients:
            try: await active_clients[phone].disconnect()
            except: pass
            del active_clients[phone]
        await event.respond(f"**⛔ تم إيقاف {phone}**", parse_mode='md')

    elif action == "unblockuser":
        phone = event.text.strip()
        if not phone.startswith('+'): phone = f"+{phone}"
        blocked_users.discard(phone)
        await event.respond(f"**✅ تم إرجاع {phone}**", parse_mode='md')

async def handle_user_input(event):
    user_id = event.sender_id
    text = event.text.strip()
    state = user_states.pop(user_id, "")

    # === تحميل فيديو ===
    if state.startswith("waiting_video_"):
        platform = state.replace("waiting_video_", "")
        await event.respond("⏳ **جاري التحميل...**", parse_mode='md')
        result = await download_video(text, platform)
        if result.get("success"):
            await event.respond(f"✅ **تم التحميل!**\n\n🔗 [اضغط للتحميل]({result['video_url']})", buttons=back_markup(), parse_mode='md')
        else:
            await event.respond(f"❌ **فشل:** {result.get('error')}", buttons=back_markup(), parse_mode='md')
        return

    # === معلومات حساب ===
    if state == "waiting_info":
        username = text.replace("@", "").strip()
        await event.respond("🔍 **جاري جلب المعلومات...**", parse_mode='md')
        info = await get_telegram_info(username)
        if info.get("exists"):
            res = f"🔍 **معلومات @{username}:**\n\n"
            if info.get("display_name"): res += f"📛 الاسم: {info['display_name']}\n"
            if info.get("bio"): res += f"📝 البايو: {info['bio'][:200]}\n"
            res += f"\n🔗 [فتح الحساب]({info['url']})\n🔗 [فتح في التطبيق](tg://user?id={username})"
        else:
            res = f"❌ **الحساب @{username} غير موجود**"
        await event.respond(res, buttons=back_markup(), parse_mode='md')
        return

    # === فتح بالآيدي ===
    if state == "waiting_open":
        entity_id = text.strip()
        buttons = [
            [Button.url("🔗 فتح في تيليجرام", f"tg://user?id={entity_id}")],
            [Button.url("🌐 فتح في المتصفح", f"https://t.me/@id{entity_id}")],
            [Button.inline("🔙 رجوع", b"back_main")],
        ]
        await event.respond(f"🔗 **فتح بالآيدي: {entity_id}**", buttons=buttons, parse_mode='md')
        return

    # === تحويل ===
    if state == "waiting_resolve":
        entity = text.replace("@", "").strip()
        if entity.isdigit():
            res = f"🔄 **تحويل الآيدي:**\n\n🆔 الآيدي: {entity}\n🔗 tg://user?id={entity}\n🌐 https://t.me/@id{entity}"
        else:
            res = f"🔄 **تحويل اليوزر:**\n\n📛 @{entity}\n🔗 https://t.me/{entity}\n📱 tg://resolve?domain={entity}"
        await event.respond(res, buttons=back_markup(), parse_mode='md')
        return

    # === فحص يوزر ===
    if state == "waiting_check":
        username = text.replace("@", "").strip()
        await event.respond("✅ **جاري الفحص...**", parse_mode='md')
        tg = await check_tg_username(username)
        ig = await check_ig_username(username.lower())
        tk = await check_tk_username(username.lower())
        res = f"✅ **نتائج @{username}:**\n\n📱 تيليجرام: {tg if tg else '❌ مستخدم'}\n📷 انستجرام: {ig if ig else '❌ مستخدم'}\n🎵 تيكتوك: {tk if tk else '❌ مستخدم'}"
        await event.respond(res, buttons=back_markup(), parse_mode='md')
        return

# ============================================
# أحداث إضافية للمطور
# ============================================
@bot.on(events.CallbackQuery(data=b"how_to_get_data"))
async def how_to_get_data(event):
    allowed_chats.add(event.chat_id)
    await event.answer(
        "🔹 **طريقة جلب API:**\n\n1. افتح my.telegram.org\n2. أدخل رقم هاتفك\n3. استلم رمز التحقق\n4. اختر API development tools\n5. املأ النموذج\n6. انسخ api_id و api_hash",
        alert=True)

@bot.on(events.CallbackQuery(data=b"dev_login"))
async def dev_login(event):
    allowed_chats.add(event.chat_id)
    if not is_dev(event.sender_id): await event.answer("غير مصرح", alert=True); return
    pending_verify[event.sender_id] = True
    await event.edit("**التحقق من المطور**\n\nشارك رقم هاتفك.", buttons=[[Button.request_phone("مشاركة رقم الهاتف", resize=True)]], parse_mode='md')

@bot.on(events.NewMessage(func=lambda e: e.message.contact or e.sender_id in pending_verify))
async def handle_phone_verify(event):
    allowed_chats.add(event.chat_id)
    user_id = event.sender_id
    if user_id not in pending_verify: return
    phone = f"+{event.message.contact.phone_number}" if event.message.contact else event.text.strip().replace("+", "")
    if not phone.startswith('+'): phone = f"+{phone}"
    if phone == DEV_PHONE:
        verified_devs.add(user_id)
        del pending_verify[user_id]
        await event.respond("**تم التحقق!**\nمرحباً بك.", buttons=dev_panel_markup(), parse_mode='md')
    else:
        await event.respond("**فشل التحقق**", parse_mode='md')
