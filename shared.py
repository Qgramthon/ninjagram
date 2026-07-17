"""
Vought International - Shared Module
The Boys Edition - Telethon Setup
"""

import os
import asyncio
import logging
import json
import random
import io
from datetime import datetime
from telethon import TelegramClient, events, functions, types
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.messages import GetFullChatRequest
from telethon.tl.functions.channels import GetFullChannelRequest, EditAdminRequest
from telethon.tl.functions.contacts import BlockRequest, UnblockRequest
from telethon.tl.functions.messages import DeleteHistoryRequest
from telethon.tl.types import ChatAdminRights, ChatBannedRights
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    FloodWaitError,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Vought")

main_loop = asyncio.new_event_loop()

SESSIONS_DIR = "sessions"
CONFIG_DIR = "configs"
os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)

active_clients: dict = {}
pending_logins: dict = {}
client_me: dict = {}
api_configs_storage: dict = {}
disabled_commands: dict = {}

def save_config(phone: str, api_id: int, api_hash: str):
    safe_phone = phone.replace('+', '')
    config_path = os.path.join(CONFIG_DIR, f"{safe_phone}.json")
    with open(config_path, "w") as f:
        json.dump({"api_id": api_id, "api_hash": api_hash, "phone": phone}, f)

def load_config(phone: str) -> dict | None:
    safe_phone = phone.replace('+', '')
    config_path = os.path.join(CONFIG_DIR, f"{safe_phone}.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return json.load(f)
    return None

async def save_session(phone: str, client: TelegramClient):
    try:
        session_string = client.session.save()
        safe_phone = phone.replace('+', '')
        session_file = os.path.join(SESSIONS_DIR, f"{safe_phone}.txt")
        lock_file = os.path.join(SESSIONS_DIR, f"{safe_phone}.lock")
        with open(lock_file, "w") as f:
            f.write(str(os.getpid()))
        temp_file = session_file + ".tmp"
        with open(temp_file, "w") as f:
            f.write(session_string)
        os.replace(temp_file, session_file)
    except Exception as e:
        logger.error(f"Failed to save session {phone}: {e}")

async def save_all_sessions():
    for phone, client in list(active_clients.items()):
        await save_session(phone, client)

async def load_and_start_all_sessions():
    if not os.path.exists(SESSIONS_DIR):
        return
    loaded = 0
    for filename in os.listdir(SESSIONS_DIR):
        if not filename.endswith('.txt'):
            continue
        safe_phone = filename.replace('.txt', '')
        phone = f"+{safe_phone}"
        if phone in active_clients:
            continue
        lock_file = os.path.join(SESSIONS_DIR, f"{safe_phone}.lock")
        if os.path.exists(lock_file):
            try:
                with open(lock_file, "r") as f:
                    pid = int(f.read().strip())
                try:
                    os.kill(pid, 0)
                    continue
                except OSError:
                    os.remove(lock_file)
            except:
                os.remove(lock_file)
        config = load_config(phone)
        if not config:
            continue
        try:
            session_file = os.path.join(SESSIONS_DIR, filename)
            with open(session_file, "r") as f:
                session_string = f.read().strip()
            if not session_string:
                continue
            client = TelegramClient(StringSession(session_string), config["api_id"], config["api_hash"])
            await client.connect()
            if await client.is_user_authorized():
                with open(lock_file, "w") as f:
                    f.write(str(os.getpid()))
                active_clients[phone] = client
                client_me[phone] = await client.get_me()
                api_configs_storage[phone] = {"api_id": config["api_id"], "api_hash": config["api_hash"]}
                start_client_in_background(client, phone)
                loaded += 1
            else:
                await client.disconnect()
                cleanup_session_files(phone)
        except Exception as e:
            logger.error(f"Failed to load {phone}: {e}")
            cleanup_session_files(phone)

def cleanup_session_files(phone: str):
    safe_phone = phone.replace('+', '')
    for file_path in [
        os.path.join(SESSIONS_DIR, f"{safe_phone}.txt"),
        os.path.join(SESSIONS_DIR, f"{safe_phone}.lock"),
        os.path.join(CONFIG_DIR, f"{safe_phone}.json")
    ]:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass

async def notify_dev(message: str):
    logger.info(message)

async def periodic_save():
    while True:
        await asyncio.sleep(300)
        await save_all_sessions()

async def cleanup_expired():
    while True:
        await asyncio.sleep(600)
        for phone, client in list(active_clients.items()):
            try:
                if not await client.is_user_authorized():
                    await client.disconnect()
                    del active_clients[phone]
                    client_me.pop(phone, None)
                    api_configs_storage.pop(phone, None)
                    cleanup_session_files(phone)
            except:
                pass

async def translate_text(text: str, target: str = None) -> str:
    try:
        import urllib.parse
        import urllib.request
        has_arabic = any('\u0600' <= c <= '\u06ff' for c in text)
        if target:
            sl, tl = 'auto', target
        else:
            sl, tl = ('ar', 'en') if has_arabic else ('en', 'ar')
        url = "https://translate.googleapis.com/translate_a/single"
        params = {'client': 'gtx', 'sl': sl, 'tl': tl, 'dt': 't', 'q': text}
        full_url = url + '?' + urllib.parse.urlencode(params)
        req = urllib.request.Request(full_url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            return ''.join([part[0] for part in data[0] if part[0] is not None])
    except Exception as e:
        return f"Error: {e}"

SYMBOLS = ["★", "☆", "✦", "✧", "♛", "♔", "☠", "☢", "⚡", "☄", "❖", "✪", "✯", "✰", "꧁", "꧂", "『", "』", "【", "】", "〘", "〙"]

def start_client_in_background(client: TelegramClient, phone: str):
    
    async def is_disabled(cmd, event):
        return phone in disabled_commands and cmd in disabled_commands[phone]

    async def get_target_name(event, fallback="المستخدم"):
        """Returns the first name of the replied user, or the fallback string."""
        if event.is_reply:
            reply = await event.get_reply_message()
            if reply and reply.sender_id:
                try:
                    user = await client.get_entity(reply.sender_id)
                    return user.first_name or fallback
                except:
                    return fallback
        return fallback

    # ========== ACCOUNT COMMANDS ==========
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.نيم (.+)$'))
    async def set_name(event):
        if await is_disabled('نيم', event): return
        try:
            await client(UpdateProfileRequest(first_name=event.pattern_match.group(1)))
            await event.edit("تم تغيير الاسم")
        except Exception as e:
            await event.edit(f"خطأ: {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بايو (.+)$'))
    async def set_bio(event):
        if await is_disabled('بايو', event): return
        try:
            await client(UpdateProfileRequest(about=event.pattern_match.group(1)))
            await event.edit("تم تغيير البايو")
        except Exception as e:
            await event.edit(f"خطأ: {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بروف$'))
    async def set_pfp(event):
        if await is_disabled('بروف', event): return
        if not event.is_reply:
            await event.edit("رد على صورة")
            return
        reply = await event.get_reply_message()
        if not reply.photo:
            await event.edit("الرسالة لا تحتوي على صورة")
            return
        try:
            photo = await reply.download_media()
            await client(functions.photos.UploadProfilePhotoRequest(await client.upload_file(photo)))
            await event.edit("تم تغيير الصورة")
            os.remove(photo)
        except Exception as e:
            await event.edit(f"خطأ: {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.وقتي$'))
    async def time_name(event):
        if await is_disabled('وقتي', event): return
        try:
            now = datetime.now().strftime("%I:%M %p")
            me = await client.get_me()
            name = me.first_name or ""
            if "|" in name:
                name = name.split("|")[0].strip()
            await client(UpdateProfileRequest(first_name=f"{name} | {now}"))
            await event.edit(f"تم: {name} | {now}")
        except Exception as e:
            await event.edit(f"خطأ: {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.حالة$'))
    async def status(event):
        if await is_disabled('حالة', event): return
        try:
            me = await client.get_me()
            full = await client(GetFullUserRequest(me.id))
            text = f"الاسم: {me.first_name}\n"
            text += f"اليوزر: @{me.username if me.username else 'لا يوجد'}\n"
            text += f"الايدي: `{me.id}`\n"
            text += f"البايو: {full.full_user.about if full.full_user.about else 'لا يوجد'}\n"
            text += f"رقم: {me.phone if me.phone else 'مخفي'}"
            await event.edit(text)
        except Exception as e:
            await event.edit(f"خطأ: {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.رومات$'))
    async def groups(event):
        if await is_disabled('رومات', event): return
        try:
            dialogs = await client.get_dialogs()
            groups = [d for d in dialogs if d.is_group]
            text = "الرومات:\n\n"
            for i, g in enumerate(groups[:20], 1):
                text += f"`{i}.` {g.name}\n"
            await event.edit(text or "لا يوجد رومات")
        except Exception as e:
            await event.edit(f"خطأ: {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.قنوات$'))
    async def channels(event):
        if await is_disabled('قنوات', event): return
        try:
            dialogs = await client.get_dialogs()
            chs = [d for d in dialogs if d.is_channel]
            text = "القنوات:\n\n"
            for i, c in enumerate(chs[:20], 1):
                text += f"`{i}.` {c.name}\n"
            await event.edit(text or "لا يوجد قنوات")
        except Exception as e:
            await event.edit(f"خطأ: {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بلوكات$'))
    async def blocked(event):
        if await is_disabled('بلوكات', event): return
        try:
            blocked_list = await client(functions.contacts.GetBlockedRequest(offset=0, limit=50))
            text = "المتبلكين:\n\n"
            for i, b in enumerate(blocked_list.users, 1):
                text += f"`{i}.` {b.first_name} - @{b.username if b.username else 'لا يوجد'}\n"
            await event.edit(text if blocked_list.users else "لا يوجد بلوكات")
        except Exception as e:
            await event.edit(f"خطأ: {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بنغ$'))
    async def ping(event):
        if await is_disabled('بنغ', event): return
        start = datetime.now()
        msg = await event.edit("جاري الحساب...")
        end = datetime.now()
        speed = (end - start).microseconds / 1000
        await msg.edit(f"السرعة: `{speed:.2f}ms`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.مخفي$'))
    async def hide_name(event):
        if await is_disabled('مخفي', event): return
        try:
            await client(UpdateProfileRequest(first_name=""))
            await event.edit("تم إخفاء الاسم")
        except Exception as e:
            await event.edit(f"خطأ: {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.رمز$'))
    async def symbol(event):
        if await is_disabled('رمز', event): return
        sym = random.choice(SYMBOLS)
        me = await client.get_me()
        name = (me.first_name or "") + " " + sym
        try:
            await client(UpdateProfileRequest(first_name=name))
            await event.edit(f"تم إضافة: {sym}")
        except Exception as e:
            await event.edit(f"خطأ: {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.زخرفة (.+)$'))
    async def decorate(event):
        if await is_disabled('زخرفة', event): return
        text = event.pattern_match.group(1)
        d = {'a':'α','b':'в','c':'¢','d':'∂','e':'є','f':'ƒ','g':'g','h':'н','i':'ι','j':'נ','k':'к','l':'ℓ','m':'м','n':'η','o':'σ','p':'ρ','q':'q','r':'я','s':'ѕ','t':'т','u':'υ','v':'ν','w':'ω','x':'χ','y':'у','z':'z'}
        await event.edit(''.join(d.get(c.lower(),c) for c in text))

    # ========== FORMAT COMMANDS ==========
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.عريض$'))
    async def bold(event):
        if await is_disabled('عريض', event): return
        if not event.is_reply:
            await event.edit("رد على رسالة")
            return
        reply = await event.get_reply_message()
        if reply.text:
            await event.edit(f"**{reply.text}**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.مائل$'))
    async def italic(event):
        if await is_disabled('مائل', event): return
        if not event.is_reply:
            await event.edit("رد على رسالة")
            return
        reply = await event.get_reply_message()
        if reply.text:
            await event.edit(f"__{reply.text}__")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.مشطوب$'))
    async def strike(event):
        if await is_disabled('مشطوب', event): return
        if not event.is_reply:
            await event.edit("رد على رسالة")
            return
        reply = await event.get_reply_message()
        if reply.text:
            await event.edit(f"~~{reply.text}~~")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.خط$'))
    async def normal(event):
        if await is_disabled('خط', event): return
        if not event.is_reply:
            await event.edit("رد على رسالة")
            return
        reply = await event.get_reply_message()
        if reply.text:
            await event.edit(reply.text)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بيك$'))
    async def sticker_to_photo(event):
        if await is_disabled('بيك', event): return
        if not event.is_reply:
            await event.edit("رد على ملصق")
            return
        reply = await event.get_reply_message()
        if not reply.sticker:
            await event.edit("الرسالة ليست ملصق")
            return
        try:
            photo = await reply.download_media()
            await client.send_file(event.chat_id, photo)
            await event.delete()
            os.remove(photo)
        except Exception as e:
            await event.edit(f"خطأ: {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ستيك$'))
    async def photo_to_sticker(event):
        if await is_disabled('ستيك', event): return
        if not event.is_reply:
            await event.edit("رد على صورة")
            return
        reply = await event.get_reply_message()
        if not reply.photo:
            await event.edit("الرسالة ليست صورة")
            return
        try:
            photo = await reply.download_media()
            await client.send_file(event.chat_id, photo, force_document=False, attributes=[types.DocumentAttributeSticker(alt="sticker", stickerset=types.InputStickerSetEmpty())])
            await event.delete()
            os.remove(photo)
        except Exception as e:
            await event.edit(f"خطأ: {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.نص$'))
    async def voice_text(event):
        if await is_disabled('نص', event): return
        if not event.is_reply:
            await event.edit("رد على ريك")
            return
        reply = await event.get_reply_message()
        if not reply.voice:
            await event.edit("الرسالة ليست ريك")
            return
        await event.edit("الريك فقط - لا يمكن استخراج النص")

    # ========== TRANSLATION ==========
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ترجم (.+)$'))
    async def translate_cmd(event):
        if await is_disabled('ترجم', event): return
        text = event.pattern_match.group(1)
        msg = await event.edit("جاري الترجمة...")
        result = await translate_text(text)
        await msg.edit(f"**الترجمة:**\n{result}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ترجم$'))
    async def translate_reply(event):
        if await is_disabled('ترجم', event): return
        if not event.is_reply:
            await event.edit("رد على رسالة أو اكتب .ترجم + النص")
            return
        reply = await event.get_reply_message()
        if not reply or not reply.text:
            await event.edit("لا يوجد نص للترجمة")
            return
        msg = await event.edit("جاري الترجمة...")
        result = await translate_text(reply.text)
        await msg.edit(f"**الترجمة:**\n{result}")

    # ========== CHAT COMMANDS ==========
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.مسح (\d+)$'))
    async def delete_msgs(event):
        if await is_disabled('مسح', event): return
        count = int(event.pattern_match.group(1))
        chat = await event.get_input_chat()
        messages = []
        async for msg in client.iter_messages(chat, limit=count + 1):
            messages.append(msg.id)
        await client.delete_messages(chat, messages)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.مسح$'))
    async def delete_reply(event):
        if await is_disabled('مسح', event): return
        if event.is_reply:
            reply = await event.get_reply_message()
            await reply.delete()
            await event.delete()

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.رسائل$'))
    async def msg_count(event):
        if await is_disabled('رسائل', event): return
        chat = await event.get_input_chat()
        count = sum(1 async for _ in client.iter_messages(chat, from_user='me'))
        await event.edit(f"عدد رسائلك: `{count}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.توب$'))
    async def top_messages(event):
        if await is_disabled('توب', event): return
        chat = await event.get_input_chat()
        users_count = {}
        async for msg in client.iter_messages(chat, limit=100):
            if msg.sender_id:
                users_count[msg.sender_id] = users_count.get(msg.sender_id, 0) + 1
        sorted_users = sorted(users_count.items(), key=lambda x: x[1], reverse=True)[:5]
        text = "توب الأعضاء:\n\n"
        for i, (user_id, count) in enumerate(sorted_users, 1):
            try:
                user = await client.get_entity(user_id)
                name = user.first_name or "Unknown"
                text += f"`{i}.` **{name}** `{count}` رسالة\n"
            except:
                text += f"`{i}.` `{user_id}` `{count}` رسالة\n"
        await event.edit(text)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.اول$'))
    async def first_msg(event):
        if await is_disabled('اول', event): return
        chat = await event.get_input_chat()
        async for msg in client.iter_messages(chat, reverse=True, limit=1):
            await event.edit(f"اول رسالة: {msg.date}")
            return

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.انشاء$'))
    async def created(event):
        if await is_disabled('انشاء', event): return
        try:
            chat = await event.get_input_chat()
            if hasattr(chat, 'channel_id'):
                full = await client(GetFullChannelRequest(chat))
                await event.edit(f"تاريخ الانشاء: {full.full_chat.about}")
            else:
                full = await client(GetFullChatRequest(chat_id=event.chat_id))
                await event.edit(f"معلومات: {full.full_chat}")
        except:
            await event.edit("غير متاح")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تونزي$'))
    async def top_replier(event):
        if await is_disabled('تونزي', event): return
        await event.edit("قيد التطوير")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ث$'))
    async def pin(event):
        if await is_disabled('ث', event): return
        if not event.is_reply:
            await event.edit("رد على رسالة")
            return
        reply = await event.get_reply_message()
        try:
            await client.pin_message(event.chat_id, reply.id)
            await event.edit("تم التثبيت")
        except:
            await event.edit("لا توجد صلاحية")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.حفظ$'))
    async def save(event):
        if await is_disabled('حفظ', event): return
        if not event.is_reply:
            await event.edit("رد على رسالة لحفظها")
            return
        reply = await event.get_reply_message()
        if not reply:
            await event.edit("لا يوجد رد")
            return
        try:
            if reply.media:
                # يحفظ الوسائط: صور، ملصقات، فيديو، ملفات، الخ
                file_path = await reply.download_media()
                if file_path:
                    await client.send_file('me', file_path, caption=reply.text or "")
                    os.remove(file_path)
                    await event.edit("تم حفظ الوسائط")
                else:
                    await event.edit("فشل تحميل الوسائط")
            elif reply.text:
                await client.send_message('me', reply.text)
                await event.edit("تم حفظ النص")
            else:
                await event.edit("الرسالة لا تحتوي على نص أو وسائط")
        except Exception as e:
            await event.edit(f"خطأ: {e}")

    # ========== PRIVATE COMMANDS ==========
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تحفيل$'))
    async def antiflood(event):
        if await is_disabled('تحفيل', event): return
        await event.edit("خاصية التحفيل قيد التطوير")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.كول$'))
    async def block_calls(event):
        if await is_disabled('كول', event): return
        await event.edit("خاصية قفل المكالمات قيد التطوير")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.حذف$'))
    async def delete_chat(event):
        if await is_disabled('حذف', event): return
        try:
            chat = await event.get_input_chat()
            await client.delete_dialog(chat)
            await event.edit("تم حذف المحادثة")
        except Exception as e:
            await event.edit(f"خطأ: {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.سجل$'))
    async def log_edits(event):
        if await is_disabled('سجل', event): return
        await event.edit("خاصية سجل التعديلات قيد التطوير")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بلوك$'))
    async def block_user(event):
        if await is_disabled('بلوك', event): return
        if event.is_reply:
            reply = await event.get_reply_message()
            user = await client.get_entity(reply.sender_id)
            await client(BlockRequest(user))
            await event.edit(f"تم حظر {user.first_name}")
        else:
            await event.edit("رد على المستخدم")

    # ========== GROUP COMMANDS ==========
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تحليل(?: (.+))?$'))
    async def analyze_group(event):
        if await is_disabled('تحليل', event): return
        target = await get_target_name(event, "المجموعة") if not event.pattern_match.group(1) else event.pattern_match.group(1)
        await event.edit(f"تحليل {target}: `{random.randint(0,100)}%`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.كتم$'))
    async def mute(event):
        if await is_disabled('كتم', event): return
        if not event.is_reply:
            await event.edit("رد على المستخدم")
            return
        try:
            reply = await event.get_reply_message()
            user = await client.get_entity(reply.sender_id)
            rights = ChatBannedRights(until_date=None, send_messages=True)
            await client(functions.channels.EditBannedRequest(event.chat_id, user, rights))
            await event.edit(f"تم كتم {user.first_name}")
        except Exception as e:
            await event.edit(f"خطأ: {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.طرد$'))
    async def kick(event):
        if await is_disabled('طرد', event): return
        if not event.is_reply:
            await event.edit("رد على المستخدم")
            return
        try:
            reply = await event.get_reply_message()
            user = await client.get_entity(reply.sender_id)
            await client.kick_participant(event.chat_id, user)
            await event.edit(f"تم طرد {user.first_name}")
        except Exception as e:
            await event.edit(f"خطأ: {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.فتح$'))
    async def open_chat(event):
        if await is_disabled('فتح', event): return
        try:
            await client(functions.messages.EditChatDefaultBannedRightsRequest(
                peer=event.chat_id,
                banned_rights=ChatBannedRights(until_date=None, send_messages=False)
            ))
            await event.edit("تم فتح الدردشة")
        except:
            await event.edit("خطأ في الصلاحية")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.قفل$'))
    async def close_chat(event):
        if await is_disabled('قفل', event): return
        try:
            await client(functions.messages.EditChatDefaultBannedRightsRequest(
                peer=event.chat_id,
                banned_rights=ChatBannedRights(until_date=None, send_messages=True)
            ))
            await event.edit("تم قفل الدردشة")
        except:
            await event.edit("خطأ في الصلاحية")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.قفل ستيك$'))
    async def lock_stickers(event):
        if await is_disabled('قفل ستيك', event): return
        await event.edit("خاصية قفل الملصقات قيد التطوير")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غفير$'))
    async def low_admin(event):
        if await is_disabled('غفير', event): return
        await event.edit("خاصية رفع غفير قيد التطوير")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ادمن$'))
    async def admin(event):
        if await is_disabled('ادمن', event): return
        if not event.is_reply:
            await event.edit("رد على المستخدم")
            return
        try:
            reply = await event.get_reply_message()
            user = await client.get_entity(reply.sender_id)
            rights = ChatAdminRights(
                change_info=True, post_messages=True, edit_messages=True,
                delete_messages=True, ban_users=False, invite_users=True,
                pin_messages=True, add_admins=False, anonymous=False, manage_call=True
            )
            await client(EditAdminRequest(event.chat_id, user, rights, "Admin"))
            await event.edit(f"تم رفع {user.first_name} ادمن")
        except Exception as e:
            await event.edit(f"خطأ: {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.مشرف$'))
    async def full_admin(event):
        if await is_disabled('مشرف', event): return
        if not event.is_reply:
            await event.edit("رد على المستخدم")
            return
        try:
            reply = await event.get_reply_message()
            user = await client.get_entity(reply.sender_id)
            rights = ChatAdminRights(
                change_info=True, post_messages=True, edit_messages=True,
                delete_messages=True, ban_users=True, invite_users=True,
                pin_messages=True, add_admins=True, anonymous=False, manage_call=True
            )
            await client(EditAdminRequest(event.chat_id, user, rights, "Owner"))
            await event.edit(f"تم رفع {user.first_name} مشرف كامل")
        except Exception as e:
            await event.edit(f"خطأ: {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.البوتات$'))
    async def bots_list(event):
        if await is_disabled('البوتات', event): return
        try:
            participants = await client.get_participants(event.chat_id)
            bots = [p for p in participants if p.bot]
            text = "البوتات:\n\n" + "\n".join([f"@{b.username}" for b in bots if b.username])
            await event.edit(text or "لا يوجد بوتات")
        except:
            await event.edit("خطأ")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.محذوف$'))
    async def deleted_accounts(event):
        if await is_disabled('محذوف', event): return
        try:
            participants = await client.get_participants(event.chat_id)
            deleted = [p for p in participants if p.deleted]
            await event.edit(f"عدد الحسابات المحذوفة: {len(deleted)}")
        except:
            await event.edit("خطأ")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ادمنز$'))
    async def admin_list(event):
        if await is_disabled('ادمنز', event): return
        try:
            admins = await client.get_participants(event.chat_id, filter=types.ChannelParticipantsAdmins())
            text = "الادمنز:\n\n" + "\n".join([f"{a.first_name}" for a in admins])
            await event.edit(text)
        except:
            await event.edit("خطأ")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.صلاحياتي$'))
    async def my_rights(event):
        if await is_disabled('صلاحياتي', event): return
        await event.edit("خاصية عرض الصلاحيات قيد التطوير")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.صلاحياته$'))
    async def his_rights(event):
        if await is_disabled('صلاحياته', event): return
        await event.edit("خاصية عرض صلاحيات المستخدم قيد التطوير")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.خاين$'))
    async def traitor(event):
        if await is_disabled('خاين', event): return
        await event.edit("خاصية طرد الخاين قيد التطوير")

    # ========== CHANNEL COMMANDS ==========
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.توقيع$'))
    async def sign(event):
        if await is_disabled('توقيع', event): return
        await event.edit("خاصية التوقيع قيد التطوير")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.توجيه$'))
    async def forward_lock(event):
        if await is_disabled('توجيه', event): return
        await event.edit("خاصية قفل التوجيه قيد التطوير")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ريأكت$'))
    async def react_lock(event):
        if await is_disabled('ريأكت', event): return
        await event.edit("خاصية قفل الريأكت قيد التطوير")

    # ========== MEMBERS ADD ==========
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ضيف (.+)$'))
    async def add_member(event):
        if await is_disabled('ضيف', event): return
        target = event.pattern_match.group(1)
        try:
            if target.startswith('@'):
                user = await client.get_entity(target)
                await client(functions.channels.InviteToChannelRequest(event.chat_id, [user]))
                await event.edit(f"تم إضافة {user.first_name}")
            else:
                await event.edit("يوزر غير صحيح")
        except Exception as e:
            await event.edit(f"خطأ: {e}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ضيف ح$'))
    async def add_deleted(event):
        if await is_disabled('ضيف ح', event): return
        await event.edit("خاصية إضافة المحذوفين قيد التطوير")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ضيف ب$'))
    async def add_bots(event):
        if await is_disabled('ضيف ب', event): return
        await event.edit("خاصية إضافة البوتات قيد التطوير")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تسجيل$'))
    async def register(event):
        if await is_disabled('تسجيل', event): return
        await event.edit("خاصية التسجيل قيد التطوير")

    # ========== ENTERTAINMENT ==========
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.انتحال (.+)$'))
    async def ghost(event):
        if await is_disabled('انتحال', event): return
        await event.delete()
        await client.send_message(event.chat_id, event.pattern_match.group(1))

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تقليد$'))
    async def mimic(event):
        if await is_disabled('تقليد', event): return
        if not event.is_reply:
            await event.edit("رد على شخص لتقليده")
            return
        reply = await event.get_reply_message()
        if reply and reply.text:
            await event.delete()
            await client.send_message(event.chat_id, reply.text)
        else:
            await event.edit("الرسالة لا تحتوي على نص")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ضحك$'))
    async def laugh_anim(event):
        if await is_disabled('ضحك', event): return
        await event.edit("😂😂😂")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.قلب$'))
    async def hearts(event):
        if await is_disabled('قلب', event): return
        hearts_list = ["❤️", "💕", "💗", "💖", "💝", "💘"]
        msg = await event.edit("❤️")
        for _ in range(3):
            for h in hearts_list:
                await asyncio.sleep(0.3)
                await msg.edit(h)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.مطر$'))
    async def rain(event):
        if await is_disabled('مطر', event): return
        await event.edit("☔️ مطر مطر مطر")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ثلج$'))
    async def snow(event):
        if await is_disabled('ثلج', event): return
        await event.edit("❄️ ثلج ثلج ثلج")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ليل$'))
    async def night(event):
        if await is_disabled('ليل', event): return
        await event.edit("🌙 ليل ليل ليل")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.قمر$'))
    async def moon(event):
        if await is_disabled('قمر', event): return
        await event.edit("🌕 قمر قمر قمر")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ورد$'))
    async def flowers(event):
        if await is_disabled('ورد', event): return
        await event.edit("🌸 ورد ورد ورد")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.قتل(?: (.+))?$'))
    async def kill(event):
        if await is_disabled('قتل', event): return
        target = await get_target_name(event, "الضحية") if not event.pattern_match.group(1) else event.pattern_match.group(1)
        await event.edit(f"تم قتل {target} بدم بارد")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تهكير(?: (.+))?$'))
    async def hack(event):
        if await is_disabled('تهكير', event): return
        target = await get_target_name(event, "الهدف") if not event.pattern_match.group(1) else event.pattern_match.group(1)
        msg = await event.edit("جاري الاختراق...")
        steps = ["جاري الاتصال...", "تخطي الحماية...", "كسر كلمة المرور...", "الوصول للبيانات...", "تحميل الملفات...", f"تم اختراق {target}"]
        for step in steps:
            await asyncio.sleep(0.5)
            await msg.edit(step)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ذكاء(?: (.+))?$'))
    async def iq(event):
        if await is_disabled('ذكاء', event): return
        target = await get_target_name(event, "المستخدم") if not event.pattern_match.group(1) else event.pattern_match.group(1)
        await event.edit(f"نسبة ذكاء {target}: `{random.randint(1,200)}%`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.شذ(?: (.+))?$'))
    async def gay(event):
        if await is_disabled('شذ', event): return
        target = await get_target_name(event, "المستخدم") if not event.pattern_match.group(1) else event.pattern_match.group(1)
        await event.edit(f"نسبة شذوذ {target}: `{random.randint(0,100)}%`")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تصفية$'))
    async def purge(event):
        if await is_disabled('تصفية', event): return
        await event.edit("جاري تصفية الروم...")

    # ========== FUN RAISE ==========
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.حمار(?: (.+))?$'))
    async def donkey(event):
        target = await get_target_name(event, "المستخدم") if not event.pattern_match.group(1) else event.pattern_match.group(1)
        await event.edit(f"تم رفع {target} حمار رسمياً")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.سباك(?: (.+))?$'))
    async def plumber(event):
        target = await get_target_name(event, "المستخدم") if not event.pattern_match.group(1) else event.pattern_match.group(1)
        await event.edit(f"تم رفع {target} سباك")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.شحات(?: (.+))?$'))
    async def beggar(event):
        target = await get_target_name(event, "المستخدم") if not event.pattern_match.group(1) else event.pattern_match.group(1)
        await event.edit(f"تم رفع {target} شحات")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ميكانيكي(?: (.+))?$'))
    async def mechanic(event):
        target = await get_target_name(event, "المستخدم") if not event.pattern_match.group(1) else event.pattern_match.group(1)
        await event.edit(f"تم رفع {target} ميكانيكي")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بيكيا(?: (.+))?$'))
    async def scrap(event):
        target = await get_target_name(event, "المستخدم") if not event.pattern_match.group(1) else event.pattern_match.group(1)
        await event.edit(f"تم رفع {target} بتاع روبابيكيا")

    # ========== SUPPORT ==========
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غ (.+)$'))
    async def disable_cmd(event):
        cmd = event.pattern_match.group(1).strip()
        if phone not in disabled_commands:
            disabled_commands[phone] = []
        if cmd not in disabled_commands[phone]:
            disabled_commands[phone].append(cmd)
        await event.edit(f"تم تعطيل: .{cmd}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تعطيل$'))
    async def disable_all(event):
        await event.edit("تم تعطيل التيليثون مؤقتاً")
        active_clients.pop(phone, None)

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تفعيل$'))
    async def enable_all(event):
        await event.edit("تم تفعيل التيليثون")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.واتس (\d+)$'))
    async def whatsapp_report(event):
        number = event.pattern_match.group(1)
        await event.edit(f"تم إنشاء بلاغ فك واتس للرقم {number}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تيلي (\d+)$'))
    async def telegram_report(event):
        number = event.pattern_match.group(1)
        await event.edit(f"تم إنشاء بلاغ فك تيلي للرقم {number}")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.فني$'))
    async def support(event):
        await event.edit("للتواصل مع المطور: @J0E_3")

    # ========== HELP & SOURCE ==========
    
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.اوامر$'))
    async def commands_list(event):
        await event.edit("""**ᴛʜᴇ ʙᴏʏs ᴛᴇʟᴇᴛʜᴏɴ**

**أوامر الحسابات:**
`.نيم` `.بايو` `.بروف` `.وقتي` `.حالة` `.رومات` `.قنوات` `.بلوكات` `.بنغ` `.مخفي` `.رمز` `.زخرفة`

**أوامر الصيغ:**
`.عريض` `.مائل` `.مشطوب` `.خط` `.بيك` `.ستيك` `.نص` `.ترجم`

**أوامر المحادثات:**
`.مسح` `.رسائل` `.توب` `.اول` `.انشاء` `.تونزي` `.ث` `.حفظ`

**أوامر البرايفيت:**
`.تحفيل` `.كول` `.حذف` `.سجل` `.بلوك`

**أوامر الجروبات:**
`.تحليل` `.كتم` `.طرد` `.فتح` `.قفل` `.قفل ستيك` `.غفير` `.ادمن` `.مشرف` `.البوتات` `.محذوف` `.ادمنز` `.صلاحياتي` `.صلاحياته` `.خاين`

**أوامر القنوات:**
`.توقيع` `.توجيه` `.ريأكت`

**أوامر الممولين:**
`.ضيف` `.ضيف ح` `.ضيف ب` `.تسجيل`

**أوامر التسلية:**
`.انتحال` `.تقليد` `.ضحك` `.قلب` `.مطر` `.ثلج` `.ليل` `.قمر` `.ورد` `.قتل` `.تهكير` `.ذكاء` `.شذ` `.تصفية`

**أوامر الرفع:**
`.حمار` `.سباك` `.شحات` `.ميكانيكي` `.بيكيا`

**أوامر الدعم:**
`.تعطيل` `.تفعيل` `.واتس` `.تيلي` `.فني`

`.سورس` `.اوامر`""")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.سورس$'))
    async def source(event):
        await event.edit("**THE BOYS TELETHON**\nBy Vought International\n@i_v_k_i")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ايقاف$'))
    async def stop_source(event):
        await event.edit("تم الإيقاف")
        await client.disconnect()
        active_clients.pop(phone, None)
        cleanup_session_files(phone)

async def shutdown():
    await save_all_sessions()
    for filename in os.listdir(SESSIONS_DIR):
        if filename.endswith('.lock'):
            try:
                os.remove(os.path.join(SESSIONS_DIR, filename))
            except:
                pass
    for phone, client in list(active_clients.items()):
        try:
            await client.disconnect()
        except:
            pass
    active_clients.clear()
    client_me.clear()
    api_configs_storage.clear()
