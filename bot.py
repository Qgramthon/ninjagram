# bot.py – لوحة تحكم المطور الكاملة (إحصائيات، إدارة، صلاحيات، وأكثر)
import asyncio, uuid, os, time
from telethon import TelegramClient, events, Button
from shared import *
from collections import Counter

bot = TelegramClient(f'bot_session_{uuid.uuid4().hex[:6]}', BOT_API_ID, BOT_API_HASH)

START_IMAGE = "start.jpg"

allowed_chats = set()
ALLOWED_KEYWORDS = ["Qthon", "تيليثون", "لوحة تحكم", "طريقة جلب", "التحقق من المطور",
                    "تم التحقق", "فشل التحقق", "التحقق معطل", "خيارات المطور",
                    "المستخدمين", "النشطاء", "أكثر الأوامر", "المجموعات", "القنوات",
                    "إذاعة", "رجوع", "قريباً", "غير مصرح", "تم تفعيل"]

def is_allowed_text(text):
    if not text: return False
    for kw in ALLOWED_KEYWORDS:
        if kw in text: return True
    return False

# --- دوال مساعدة للإحصائيات ---
async def get_user_stats():
    total = len(active_clients)
    active_now = sum(1 for c in active_clients.values() if c.is_connected())
    blacklisted = len(blacklist) if hasattr(sys.modules[__name__], 'blacklist') else 0
    disabled = sum(1 for v in disabled_users.values() if v) if 'disabled_users' in dir() else 0
    total_cmds = sum(len(c) for c in command_stats.values())
    return total, active_now, blacklisted, disabled, total_cmds

async def get_top_users(limit=10):
    user_activity = []
    for phone, cmds in command_stats.items():
        name = user_info_cache.get(phone, {}).get('first_name', phone)
        user_activity.append((name, sum(cmds.values())))
    user_activity.sort(key=lambda x: x[1], reverse=True)
    return user_activity[:limit]

async def get_groups_and_channels(client, filter_type=None):
    """filter_type: 'group' أو 'channel' أو None للكل"""
    dialogs = await client.get_dialogs(limit=500)
    result = []
    for d in dialogs:
        if filter_type == 'group' and d.is_group:
            result.append(d)
        elif filter_type == 'channel' and d.is_channel and not d.is_group:
            result.append(d)
        elif filter_type is None:
            if d.is_group or (d.is_channel and not d.is_group):
                result.append(d)
    return result

def dev_panel_markup():
    lock_text = "فتح خيارات المطور" if dev_access_locked else "قفل خيارات المطور"
    return [
        [Button.inline("📊 إحصائيات عامة", b"dev_stats"),
         Button.inline("👥 المستخدمين", b"dev_users_list")],
        [Button.inline("🟢 النشطاء حالياً", b"dev_active"),
         Button.inline("🏆 توب المستخدمين", b"dev_top_users")],
        [Button.inline("📋 المجموعات (حيّة)", b"dev_groups"),
         Button.inline("📢 القنوات (حيّة)", b"dev_channels")],
        [Button.inline("🔍 بحث عن مستخدم", b"dev_search_user"),
         Button.inline("✉️ رسالة لمستخدم", b"dev_send_msg")],
        [Button.inline("🚫 إدارة الحظر", b"dev_manage_ban"),
         Button.inline("⚙️ إدارة التعطيل", b"dev_manage_disable")],
        [Button.inline("📈 أكثر الأوامر", b"dev_topcmd"),
         Button.inline("📣 إذاعة", b"dev_broadcast")],
        [Button.inline(lock_text, b"dev_lock")],
    ]

# --- الحماية من الرسائل غير المصرحة ---
@bot.on(events.NewMessage(outgoing=True))
async def block_unauthorized(event):
    if event.chat_id not in allowed_chats:
        await event.delete()
        return
    if not is_allowed_text(event.text):
        await event.delete()

@bot.on(events.NewMessage(pattern='/start'))
async def bot_start(event):
    allowed_chats.add(event.chat_id)
    user_id = event.sender_id
    buttons = [[Button.url("بدء التنصيب", "https://t.me/Qthon_bot?profile")]]
    caption = (
        "**• لبدء تنصيب تيليثون ڪيوجࢪام 🜲**\n"
        "**- افتح تطبيق البوت كما فالصورة**\n"
        "**- تابع إجراءات التنصيب المطلوبة**"
    )
    if os.path.exists(START_IMAGE):
        await bot.send_file(event.chat_id, START_IMAGE, caption=caption, buttons=buttons, parse_mode='md')
    else:
        await bot.send_message(event.chat_id, caption, buttons=buttons, parse_mode='md')
    if is_dev(user_id):
        await bot.send_message(event.chat_id, "**لوحة تحكم Qthon**\n\nاختر خياراً.",
                               buttons=dev_panel_markup(), parse_mode='md')

# --- Callback queries ---
@bot.on(events.CallbackQuery())
async def dev_callback(event):
    allowed_chats.add(event.chat_id)
    data = event.data.decode()
    if not is_dev(event.sender_id):
        await event.answer("غير مصرح", alert=True)
        return

    # --- العودة للقائمة الرئيسية ---
    if data == "dev_back":
        await event.edit("**لوحة تحكم Qthon**\n\nاختر خياراً.",
                         buttons=dev_panel_markup(), parse_mode='md')
        await event.answer()

    # --- قفل/فتح خيارات المطور ---
    elif data == "dev_lock":
        global dev_access_locked
        dev_access_locked = not dev_access_locked
        state = "مقفلة" if dev_access_locked else "مفتوحة"
        await event.answer(f"خيارات المطور الآن {state}", alert=True)
        await event.edit("**لوحة تحكم Qthon**\n\nاختر خياراً.",
                         buttons=dev_panel_markup(), parse_mode='md')

    # --- إحصائيات عامة ---
    elif data == "dev_stats":
        total, active_now, blacklisted, disabled, total_cmds = await get_user_stats()
        msg = (
            f"**📊 إحصائيات عامة**\n\n"
            f"👥 إجمالي المستخدمين: {total}\n"
            f"🟢 نشط الآن: {active_now}\n"
            f"🚫 محظور: {blacklisted}\n"
            f"⛔ معطل: {disabled}\n"
            f"📈 إجمالي الأوامر: {total_cmds}\n"
            f"💰 حسابات بنكية: {len(bank_data) if 'bank_data' in dir() else 0}\n"
            f"🗄️ حجم البيانات: {round(os.path.getsize(SESSION_FILE) / 1024, 1) if os.path.exists(SESSION_FILE) else 0} KB"
        )
        await event.edit(msg, parse_mode='md', buttons=[[Button.inline("رجوع", b"dev_back")]])

    # --- قائمة المستخدمين ---
    elif data == "dev_users_list":
        if not user_info_cache:
            await event.edit("لا يوجد مستخدمين.", buttons=[[Button.inline("رجوع", b"dev_back")]])
            return
        msg = "**👥 المستخدمين المسجلين:**\n\n"
        for i, (phone, info) in enumerate(user_info_cache.items(), 1):
            username = f"@{info['username']}" if info.get('username') else "بدون"
            msg += f"{i}. {info['first_name']} | {username} | {phone}\n"
            if i % 20 == 0:  # تقسيم الصفحات الطويلة
                await event.edit(msg, buttons=[[Button.inline("التالي ➡️", b"dev_users_next")], [Button.inline("رجوع", b"dev_back")]])
                return
        await event.edit(msg, parse_mode='md', buttons=[[Button.inline("رجوع", b"dev_back")]])

    # --- النشطاء حالياً ---
    elif data == "dev_active":
        if not active_clients:
            msg = "لا توجد جلسات نشطة."
        else:
            msg = f"**🟢 النشطاء حالياً ({len(active_clients)}):**\n\n"
            for phone, client in active_clients.items():
                info = user_info_cache.get(phone, {})
                name = info.get('first_name', phone)
                uname = info.get('username')
                display = f"{name} - @{uname}" if uname else f"{name} - {phone}"
                msg += f"• {display}\n"
        await event.edit(msg, parse_mode='md', buttons=[[Button.inline("رجوع", b"dev_back")]])

    # --- توب المستخدمين ---
    elif data == "dev_top_users":
        top = await get_top_users(10)
        if not top:
            msg = "لا توجد إحصائيات بعد."
        else:
            msg = "**🏆 توب 10 مستخدمين:**\n\n"
            for i, (name, cnt) in enumerate(top, 1):
                msg += f"{i}. {name}: {cnt} أمر\n"
        await event.edit(msg, parse_mode='md', buttons=[[Button.inline("رجوع", b"dev_back")]])

    # --- المجموعات (حيّة) ---
    elif data == "dev_groups":
        msg = "**📋 المجموعات (أول 20):**\n\n"
        groups = await get_groups_and_channels(bot, 'group')
        if not groups:
            msg = "لا توجد مجموعات."
        else:
            for g in groups[:20]:
                members = getattr(g, 'participants_count', '?')
                msg += f"• {g.name} (ID: {g.id}, الأعضاء: {members})\n"
        await event.edit(msg, parse_mode='md', buttons=[[Button.inline("رجوع", b"dev_back")]])

    # --- القنوات (حيّة) ---
    elif data == "dev_channels":
        msg = "**📢 القنوات (أول 20):**\n\n"
        channels = await get_groups_and_channels(bot, 'channel')
        if not channels:
            msg = "لا توجد قنوات."
        else:
            for c in channels[:20]:
                members = getattr(c, 'participants_count', '?')
                msg += f"• {c.name} (ID: {c.id}, المشتركين: {members})\n"
        await event.edit(msg, parse_mode='md', buttons=[[Button.inline("رجوع", b"dev_back")]])

    # --- أكثر الأوامر ---
    elif data == "dev_topcmd":
        all_cmds = Counter()
        for cmds in command_stats.values():
            all_cmds.update(cmds)
        top = all_cmds.most_common(10)
        if not top:
            msg = "لم تُستخدم أوامر بعد."
        else:
            msg = "**📈 أكثر 10 أوامر استخداماً:**\n\n"
            for i, (cmd, cnt) in enumerate(top, 1):
                msg += f"{i}. .{cmd}: {cnt} مرة\n"
        await event.edit(msg, parse_mode='md', buttons=[[Button.inline("رجوع", b"dev_back")]])

    # --- بحث عن مستخدم ---
    elif data == "dev_search_user":
        await event.edit("**🔍 أدخل رقم الهاتف أو اليوزر للبحث عنه:**",
                         buttons=[[Button.inline("إلغاء", b"dev_back")]])
        # سنخزن حالة البحث في قاموس مؤقت
        search_state[event.chat_id] = 'search'
        await event.answer()

    # --- رسالة لمستخدم ---
    elif data == "dev_send_msg":
        await event.edit("**✉️ أدخل رقم الهاتف أو اليوزر ثم الرسالة مفصولة بعلامة |**\nمثال: +2010xxxxxxx | مرحبا",
                         buttons=[[Button.inline("إلغاء", b"dev_back")]])
        search_state[event.chat_id] = 'send_msg'
        await event.answer()

    # --- إدارة الحظر ---
    elif data == "dev_manage_ban":
        msg = "**🚫 إدارة الحظر:**\n\n"
        if not blacklist:
            msg += "لا يوجد مستخدمين محظورين."
        else:
            for i, phone in enumerate(blacklist, 1):
                name = user_info_cache.get(phone, {}).get('first_name', phone)
                msg += f"{i}. {name} ({phone})\n"
        await event.edit(msg, parse_mode='md',
                         buttons=[[Button.inline("حظر مستخدم", b"dev_ban_user"),
                                   Button.inline("سماح", b"dev_unban_user")],
                                  [Button.inline("رجوع", b"dev_back")]])

    # --- إدارة التعطيل ---
    elif data == "dev_manage_disable":
        msg = "**⚙️ إدارة التعطيل:**\n\n"
        if not disabled_users:
            msg += "لا يوجد مستخدمين معطلين."
        else:
            for phone, val in disabled_users.items():
                if val:
                    name = user_info_cache.get(phone, {}).get('first_name', phone)
                    msg += f"• {name} ({phone})\n"
        await event.edit(msg, parse_mode='md',
                         buttons=[[Button.inline("تعطيل مستخدم", b"dev_disable_user"),
                                   Button.inline("تفعيل", b"dev_enable_user")],
                                  [Button.inline("رجوع", b"dev_back")]])

    # --- إذاعة ---
    elif data == "dev_broadcast":
        await event.edit("**📣 أدخل نص الإذاعة:**",
                         buttons=[[Button.inline("إلغاء", b"dev_back")]])
        search_state[event.chat_id] = 'broadcast'
        await event.answer()

    # --- حظر مستخدم (يدخل الرقم) ---
    elif data == "dev_ban_user":
        await event.edit("**🚫 أدخل رقم هاتف المستخدم المراد حظره:**",
                         buttons=[[Button.inline("إلغاء", b"dev_back")]])
        search_state[event.chat_id] = 'ban'
        await event.answer()

    elif data == "dev_unban_user":
        await event.edit("**🔓 أدخل رقم هاتف المستخدم المراد السماح له:**",
                         buttons=[[Button.inline("إلغاء", b"dev_back")]])
        search_state[event.chat_id] = 'unban'
        await event.answer()

    elif data == "dev_disable_user":
        await event.edit("**⛔ أدخل رقم هاتف المستخدم المراد تعطيله:**",
                         buttons=[[Button.inline("إلغاء", b"dev_back")]])
        search_state[event.chat_id] = 'disable'
        await event.answer()

    elif data == "dev_enable_user":
        await event.edit("**✅ أدخل رقم هاتف المستخدم المراد تفعيله:**",
                         buttons=[[Button.inline("إلغاء", b"dev_back")]])
        search_state[event.chat_id] = 'enable'
        await event.answer()

    await event.answer()

# --- معالجة المدخلات النصية (حالات البحث، الحظر، التعطيل، الإذاعة) ---
search_state = {}

@bot.on(events.NewMessage(incoming=True, func=lambda e: e.chat_id in search_state and not e.text.startswith('/')))
async def handle_text_input(event):
    state = search_state.pop(event.chat_id, None)
    if not state: return

    text = event.text.strip()
    if state == 'search':
        # بحث عن مستخدم وعرض معلوماته
        phone = text if text.startswith('+') else None
        username = text if not text.startswith('+') else None
        found = False
        for p, info in user_info_cache.items():
            if phone and p == phone:
                found = True
                break
            if username and info.get('username', '').lower() == username.lower():
                phone = p
                found = True
                break
        if found:
            info = user_info_cache.get(phone, {})
            msg = f"**👤 معلومات المستخدم:**\nالاسم: {info['first_name']}\nاليوزر: @{info.get('username', 'لا')}\nالرقم: {phone}"
        else:
            msg = "**❌ المستخدم غير موجود في القاعدة.**"
        await event.respond(msg, buttons=[[Button.inline("رجوع للقائمة", b"dev_back")]])

    elif state == 'send_msg':
        parts = text.split('|', 1)
        if len(parts) < 2:
            await event.respond("**❌ الصيغة غير صحيحة.**", buttons=[[Button.inline("رجوع", b"dev_back")]])
            return
        target, message = parts[0].strip(), parts[1].strip()
        # محاولة إرسال الرسالة لليوزربوت المطور
        try:
            dev_client = active_clients.get(DEV_PHONE)
            if not dev_client:
                await event.respond("**❌ حساب المطور غير متصل حالياً.**")
                return
            # جلب الكيان
            entity = await dev_client.get_input_entity(target)
            await dev_client.send_message(entity, message)
            await event.respond("**✅ تم إرسال الرسالة بنجاح.**", buttons=[[Button.inline("رجوع", b"dev_back")]])
        except Exception as e:
            await event.respond(f"**❌ فشل: {str(e)[:100]}**", buttons=[[Button.inline("رجوع", b"dev_back")]])

    elif state == 'broadcast':
        # إذاعة لكل المستخدمين المسجلين
        sent = 0
        for phone, client in active_clients.items():
            try:
                await client.send_message('me', f"📣 إذاعة من المطور:\n\n{text}")
                sent += 1
                await asyncio.sleep(0.5)
            except: pass
        await event.respond(f"**✅ تم الإرسال إلى {sent} مستخدم.**", buttons=[[Button.inline("رجوع", b"dev_back")]])

    elif state in ('ban', 'unban', 'disable', 'enable'):
        phone = text if text.startswith('+') else f"+{text}"
        if phone not in user_info_cache:
            await event.respond("**❌ الرقم غير موجود في القاعدة.**", buttons=[[Button.inline("رجوع", b"dev_back")]])
            return
        if state == 'ban':
            blacklist.add(phone)
            save_blacklist()
            await event.respond(f"**🚫 تم حظر {phone}.**", buttons=[[Button.inline("رجوع", b"dev_back")]])
        elif state == 'unban':
            blacklist.discard(phone)
            save_blacklist()
            await event.respond(f"**🔓 تم السماح لـ {phone}.**", buttons=[[Button.inline("رجوع", b"dev_back")]])
        elif state == 'disable':
            disabled_users[phone] = True
            await event.respond(f"**⛔ تم تعطيل {phone}.**", buttons=[[Button.inline("رجوع", b"dev_back")]])
        elif state == 'enable':
            disabled_users[phone] = False
            await event.respond(f"**✅ تم تفعيل {phone}.**", buttons=[[Button.inline("رجوع", b"dev_back")]])

# --- المحافظة على باقي الدوال (how_to_get_data, dev_login, handle_phone_verify) إن احتاجت ---
@bot.on(events.CallbackQuery(data=b"how_to_get_data"))
async def how_to_get_data(event):
    allowed_chats.add(event.chat_id)
    await event.answer("🔹 طريقة جلب بيانات API:\n\n1. افتح my.telegram.org ...", alert=True)

@bot.on(events.CallbackQuery(data=b"dev_login"))
async def dev_login(event):
    allowed_chats.add(event.chat_id)
    if not is_dev(event.sender_id):
        await event.answer("غير مصرح", alert=True)
        return
    pending_verify[event.sender_id] = True
    buttons = [[Button.request_phone("مشاركة رقم الهاتف", resize=True)]]
    await event.edit("**التحقق من المطور**\n\nشارك رقم هاتفك للتحقق كمالك.", buttons=buttons, parse_mode='md')
    await event.answer()

@bot.on(events.NewMessage(func=lambda e: e.message.contact or e.sender_id in pending_verify))
async def handle_phone_verify(event):
    allowed_chats.add(event.chat_id)
    user_id = event.sender_id
    if user_id not in pending_verify: return
    if dev_access_locked and not is_dev(user_id):
        del pending_verify[user_id]
        await event.respond("**التحقق معطل حالياً**\nخيارات المطور مقفلة.", parse_mode='md')
        return
    phone = (f"+{event.message.contact.phone_number}" if event.message.contact else event.text.strip().replace("+", ""))
    if not phone.startswith('+'): phone = f"+{phone}"
    if phone == DEV_PHONE:
        verified_devs.add(user_id)
        del pending_verify[user_id]
        await event.respond("**تم التحقق من الهوية!**\n\nمرحباً بك في لوحة التحكم.",
                            buttons=dev_panel_markup(), parse_mode='md')
        await notify_dev(f"تم تفعيل مطور جديد: {phone}")
    else:
        await event.respond("**فشل التحقق**\nرقم الهاتف غير مطابق.", parse_mode='md')
