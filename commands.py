from telethon import events
from shared import logger, client_me, active_clients, is_dev, DEV_USER_ID

async def setup_handlers(client, phone):
    """إعداد معالجات الأوامر لكل عميل"""
    try:
        @client.on(events.NewMessage(pattern=r'^\.اوامر$'))
        async def cmd_help(event):
            await event.reply("""
**📋 قائمة الأوامر:**

**📱 الأوامر الأساسية:**
• `.اوامر` - عرض هذه القائمة
• `.بايو` - عرض معلومات حسابك
• `.جروبات` - عرض قائمة الجروبات
• `.قنوات` - عرض قائمة القنوات
• `.اعادة` - إعادة تشغيل البوت

**🔧 أوامر متقدمة:**
• `.انضم [رابط]` - الانضمام إلى قناة/جروب
• `.مغادرة [رابط]` - مغادرة قناة/جروب
• `.ايدي` - عرض معرفك

**👑 أوامر المطور:**
• `.مطور` - التحقق كمطور
• `.جلسات` - عرض الجلسات النشطة
• `.حذف جلسة [رقم]` - حذف جلسة

**📢 القناة:** @Q_g_r_a_m
**👨‍💻 المطور:** @NinjaGram
            """.strip())

        @client.on(events.NewMessage(pattern=r'^\.بايو$'))
        async def cmd_me(event):
            me = await client.get_me()
            text = f"""
**👤 معلومات حسابك:**

• **الاسم:** {me.first_name or 'غير معروف'}
• **الكنية:** {me.last_name or 'غير معروف'}
• **اليوزر:** @{me.username if me.username else 'لا يوجد'}
• **الرقم:** {me.phone or 'مخفي'}
• **معرف:** `{me.id}`
• **مميز:** {'✅' if me.premium else '❌'}
• **موثق:** {'✅' if me.verified else '❌'}
            """.strip()
            await event.reply(text)

        @client.on(events.NewMessage(pattern=r'^\.جروبات$'))
        async def cmd_groups(event):
            try:
                from telethon.tl.functions.messages import GetDialogsRequest
                from telethon.tl.types import InputPeerUser
                dialogs = await client(GetDialogsRequest(
                    offset_date=None, offset_id=0, offset_peer=InputPeerUser(0, 0),
                    limit=100, hash=0))
                groups = []
                for dialog in dialogs.chats:
                    if hasattr(dialog, 'megagroup') and dialog.megagroup:
                        groups.append(f"• {dialog.title} (ID: {dialog.id})")
                if groups:
                    text = "**📋 قائمة الجروبات:**\n\n" + "\n".join(groups[:20])
                else:
                    text = "❌ لا توجد جروبات"
                await event.reply(text)
            except Exception as e:
                await event.reply(f"❌ خطأ: {str(e)}")

        @client.on(events.NewMessage(pattern=r'^\.قنوات$'))
        async def cmd_channels(event):
            try:
                from telethon.tl.functions.messages import GetDialogsRequest
                from telethon.tl.types import InputPeerUser
                dialogs = await client(GetDialogsRequest(
                    offset_date=None, offset_id=0, offset_peer=InputPeerUser(0, 0),
                    limit=100, hash=0))
                channels = []
                for dialog in dialogs.chats:
                    if hasattr(dialog, 'broadcast') and dialog.broadcast:
                        channels.append(f"• {dialog.title} (ID: {dialog.id})")
                if channels:
                    text = "**📋 قائمة القنوات:**\n\n" + "\n".join(channels[:20])
                else:
                    text = "❌ لا توجد قنوات"
                await event.reply(text)
            except Exception as e:
                await event.reply(f"❌ خطأ: {str(e)}")

        @client.on(events.NewMessage(pattern=r'^\.اعادة$'))
        async def cmd_restart(event):
            await event.reply("🔄 جاري إعادة التشغيل...")
            raise KeyboardInterrupt

        @client.on(events.NewMessage(pattern=r'^\.انضم (.+)$'))
        async def cmd_join(event):
            try:
                link = event.pattern_match.group(1)
                from telethon.tl.functions.channels import JoinChannelRequest
                entity = await client.get_entity(link)
                await client(JoinChannelRequest(entity))
                await event.reply(f"✅ تم الانضمام إلى: {entity.title}")
            except Exception as e:
                await event.reply(f"❌ فشل الانضمام: {str(e)}")

        @client.on(events.NewMessage(pattern=r'^\.ايدي$'))
        async def cmd_id(event):
            user_id = event.sender_id
            chat_id = event.chat_id
            await event.reply(f"""
**📋 المعرفات:**

• **معرفك:** `{user_id}`
• **معرف المحادثة:** `{chat_id}`
• **الرقم:** {phone}
            """.strip())

        @client.on(events.NewMessage(pattern=r'^\.مطور$'))
        async def cmd_dev(event):
            user_id = event.sender_id
            if user_id == DEV_USER_ID or is_dev(user_id):
                await event.reply("✅ **تم التحقق كمطور**")
            else:
                await event.reply("❌ **غير مصرح**")

        @client.on(events.NewMessage(pattern=r'^\.جلسات$'))
        async def cmd_sessions(event):
            if event.sender_id != DEV_USER_ID:
                await event.reply("❌ أمر خاص بالمطور فقط")
                return
            sessions = list(active_clients.keys())
            text = "**📋 الجلسات النشطة:**\n\n"
            for i, sess in enumerate(sessions, 1):
                text += f"{i}. {sess}\n"
            await event.reply(text)

        logger.info(f"✅ تم إعداد معالجات الأوامر لـ {phone}")
    except Exception as e:
        logger.error(f"خطأ في إعداد المعالجات لـ {phone}: {e}")
