import asyncio
import io
import logging
from telethon import events
from telethon.errors import (
    FloodWaitError, ChatAdminRequiredError, UserNotParticipantError,
    ChannelPrivateError
)
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon.tl.types import InputPhoto
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.channels import InviteToChannelRequest, JoinChannelRequest
from shared import (
    active_clients, muted_users, taqleed_users, ent7al_users, ent7al_original,
    client_me, track_command, logger
)

# ------------- دوال مساعدة للانتحال -------------
async def get_user_info_full(client, user_id):
    try:
        user = await client.get_entity(user_id)
        name = user.first_name or ""
        if user.last_name:
            name += f" {user.last_name}"
        bio = ""
        try:
            full = await client(GetFullUserRequest(user_id))
            if full.full_user.about:
                bio = full.full_user.about
        except:
            pass
        return {
            'name': name.strip() or "غير معروف",
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
            'bio': bio,
            'id': user.id
        }
    except:
        return None

async def change_profile_photo(client, user_id, phone):
    try:
        bio = io.BytesIO()
        await client.download_profile_photo(user_id, file=bio)
        bio.seek(0)
        uploaded = await client.upload_file(bio, file_name="photo.jpg")
        result = await client(UploadProfilePhotoRequest(file=uploaded))
        await asyncio.sleep(2)
        if hasattr(result, 'photo') and hasattr(result.photo, 'id'):
            return True, result.photo.id
        return True, None
    except FloodWaitError as e:
        logger.warning(f"Flood wait {e.seconds}s during photo change for {phone}")
        await asyncio.sleep(e.seconds)
        try:
            bio = io.BytesIO()
            await client.download_profile_photo(user_id, file=bio)
            bio.seek(0)
            uploaded = await client.upload_file(bio, file_name="photo.jpg")
            result = await client(UploadProfilePhotoRequest(file=uploaded))
            await asyncio.sleep(2)
            if hasattr(result, 'photo') and hasattr(result.photo, 'id'):
                return True, result.photo.id
            return True, None
        except:
            return False, None
    except Exception as e:
        logger.error(f"Photo change failed for {phone}: {e}")
        return False, None

# ------------- إعداد المعالجات -------------
async def setup_handlers(client, phone):
    if phone not in muted_users:
        muted_users[phone] = {}
    if phone not in taqleed_users:
        taqleed_users[phone] = {}
    if phone not in ent7al_users:
        ent7al_users[phone] = False
    if phone not in ent7al_original:
        ent7al_original[phone] = {}

    # ---- الكتم التلقائي ----
    @client.on(events.NewMessage(incoming=True))
    async def auto_mute(event):
        if event.is_private and event.sender_id in muted_users.get(phone, {}):
            try: await event.delete()
            except: pass

    # ---- التقليد التلقائي ----
    @client.on(events.NewMessage(incoming=True))
    async def auto_taqleed(event):
        sender_id = event.sender_id
        if sender_id and sender_id in taqleed_users.get(phone, {}):
            if event.text and not event.text.startswith('.'):
                await asyncio.sleep(0.3)
                try: await event.reply(event.text)
                except: pass

    # ---- أمر التقليد ----
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تقليد$'))
    async def taq(event):
        target = None
        if event.is_reply: target = (await event.get_reply_message()).sender_id
        elif event.is_private: target = event.chat_id
        if target:
            taqleed_users[phone][target] = True
            await event.edit("**• يتم التقليد**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غ تقليد$'))
    async def notaq(event):
        target = None
        if event.is_reply: target = (await event.get_reply_message()).sender_id
        elif event.is_private: target = event.chat_id
        if target and target in taqleed_users.get(phone, {}):
            del taqleed_users[phone][target]
        await event.edit("**• تم فك التقليد**")

    # ---- أمر الانتحال ----
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.انتحال$'))
    async def ent7al(event):
        track_command(phone, ".انتحال")
        await event.edit("**• جاري الانتحال...**")
        target_user = None
        if event.is_reply:
            reply = await event.get_reply_message()
            try: target_user = await client.get_entity(reply.sender_id)
            except: pass
        elif event.is_private:
            try: target_user = await client.get_entity(event.chat_id)
            except: pass
        if not target_user:
            await event.edit("**• فشل الانتحال**")
            return
        target_info = await get_user_info_full(client, target_user.id)
        if not target_info:
            await event.edit("**• فشل الانتحال**")
            return
        me = await client.get_me()
        client_me[phone] = me
        original = {
            'first_name': me.first_name or '',
            'last_name': me.last_name if me.last_name is not None else '',
            'added_photo_id': None,
            'about': ''
        }
        try:
            fu = await client(GetFullUserRequest('me'))
            if fu.full_user.about:
                original['about'] = fu.full_user.about
        except: pass
        # تغيير الاسم
        name_ok = False
        try:
            await client(UpdateProfileRequest(
                first_name=target_info['first_name'],
                last_name=target_info['last_name']
            ))
            await asyncio.sleep(1)
            name_ok = True
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            try:
                await client(UpdateProfileRequest(
                    first_name=target_info['first_name'],
                    last_name=target_info['last_name']
                ))
                name_ok = True
            except: pass
        except: pass
        # تغيير البايو
        bio_ok = False
        target_bio = target_info['bio']
        try:
            await client(UpdateProfileRequest(about=target_bio[:70] if target_bio else ''))
            await asyncio.sleep(0.5)
            bio_ok = True
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            try:
                await client(UpdateProfileRequest(about=target_bio[:70] if target_bio else ''))
                bio_ok = True
            except: pass
        except: pass
        # تغيير الصورة
        photo_ok, added_id = await change_profile_photo(client, target_user.id, phone)
        if photo_ok and added_id:
            original['added_photo_id'] = added_id
        ent7al_original[phone] = original
        ent7al_users[phone] = True
        if name_ok and bio_ok and photo_ok:
            await event.edit("**• تم الانتحال**")
        elif not name_ok and not bio_ok and not photo_ok:
            await event.edit("**• فشل الانتحال**")
        else:
            await event.edit("**• تم الانتحال جزئياً**")

    # ---- أمر إلغاء الانتحال ----
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.الغاء انتحال$'))
    async def unent7al(event):
        track_command(phone, ".الغاء انتحال")
        await event.edit("**• جاري إلغاء الانتحال...**")
        if not ent7al_users.get(phone) or not ent7al_original.get(phone):
            await event.edit("**• لا يوجد انتحال**")
            return
        original = ent7al_original[phone]
        # استعادة الاسم
        first = original.get('first_name', '')
        last = original.get('last_name', '')
        for attempt in range(3):
            try:
                await client(UpdateProfileRequest(first_name=first, last_name=last))
                await asyncio.sleep(1.5)
                me_now = await client.get_me()
                if me_now.first_name == first and (me_now.last_name or '') == last:
                    break
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"Restore name attempt {attempt+1}: {e}")
                await asyncio.sleep(1)
        # حذف الصورة المضافة
        if original.get('added_photo_id'):
            try:
                await client(DeletePhotosRequest(id=[InputPhoto(
                    id=original['added_photo_id'],
                    access_hash=0,
                    file_reference=b''
                )]))
                await asyncio.sleep(2)
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
                try:
                    await client(DeletePhotosRequest(id=[InputPhoto(
                        id=original['added_photo_id'],
                        access_hash=0,
                        file_reference=b''
                    )]))
                except: pass
            except Exception as e:
                logger.error(f"Failed to delete added photo: {e}")
        # استعادة البايو
        try:
            await client(UpdateProfileRequest(about=original.get('about', '')))
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            try:
                await client(UpdateProfileRequest(about=original.get('about', '')))
            except: pass
        except Exception as e:
            logger.error(f"Restore bio failed: {e}")
        ent7al_users[phone] = False
        ent7al_original[phone] = {}
        await event.edit("**• تم إلغاء الانتحال**")

    # ================== أمر إضافة الأعضاء الذكي ==================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.اضافة (\d+) (@?\w+)$'))
    async def add_members_from_group(event):
        if not event.is_group:
            await event.edit("**• الأمر يعمل في المجموعات فقط**")
            return

        count = int(event.pattern_match.group(1))
        target_username = event.pattern_match.group(2).strip()

        await event.edit(f"**• جاري سحب {count} عضو من {target_username} وإضافتهم هنا...**")

        # التحقق من صلاحية الدعوة في الجروب الحالي
        try:
            perms = await client.get_permissions(event.chat_id, 'me')
            if not perms.invite_users:
                await event.edit("**• لا تملك صلاحية إضافة أعضاء في هذا الجروب**")
                return
        except Exception as e:
            await event.edit(f"**• خطأ في الصلاحيات: {str(e)[:50]}**")
            return

        # جلب الجروب المصدر
        try:
            source_group = await client.get_entity(target_username)
        except:
            await event.edit(f"**• لم يتم العثور على الجروب {target_username}**")
            return

        # الانضمام إن لزم
        try:
            await client.get_permissions(source_group, 'me')
        except UserNotParticipantError:
            try:
                await client(JoinChannelRequest(source_group))
                await asyncio.sleep(3)
                await event.edit(f"**• تم الانضمام إلى {target_username}، جاري السحب...**")
            except Exception as e:
                await event.edit(f"**• فشل الانضمام إلى الجروب المصدر: {str(e)[:50]}**")
                return

        added = 0
        failed = 0
        batch = []
        batch_size = 5
        base_delay = 4  # ثواني بين الدفعات (آمن)
        current_delay = base_delay

        async def send_batch(batch_list):
            nonlocal added, failed, current_delay
            try:
                await client(InviteToChannelRequest(channel=event.chat_id, users=batch_list))
                added += len(batch_list)
                # إعادة التأخير للوضع الطبيعي إذا نجحت
                current_delay = base_delay
            except FloodWaitError as e:
                logger.info(f"Flood wait {e.seconds}s, increasing delay")
                await asyncio.sleep(e.seconds)
                # إعادة المحاولة بعد الانتظار
                try:
                    await client(InviteToChannelRequest(channel=event.chat_id, users=batch_list))
                    added += len(batch_list)
                except:
                    failed += len(batch_list)
                # زيادة التأخير مؤقتاً
                current_delay = min(current_delay + 2, 15)
            except Exception as e:
                if "PEER_FLOOD" in str(e):
                    logger.warning("Peer flood, waiting 15s")
                    await asyncio.sleep(15)
                    current_delay = 10
                else:
                    logger.warning(f"Batch failed: {e}")
                    failed += len(batch_list)

        try:
            participants_iter = client.iter_participants(source_group, limit=count)
            async for user in participants_iter:
                if user.bot or user.deleted:
                    continue
                batch.append(user.id)
                if len(batch) >= batch_size:
                    await send_batch(batch)
                    batch = []
                    await asyncio.sleep(current_delay)
                    # تحديث التقدم كل 10 أعضاء
                    if added % 10 == 0 and added > 0:
                        await event.edit(f"**• تمت إضافة {added} عضو حتى الآن...**")

            # الدفعة الأخيرة
            if batch:
                await send_batch(batch)

            result = f"**• تمت إضافة {added} عضو بنجاح**"
            if failed:
                result += f"\n• فشل في إضافة {failed} عضو"
            await event.edit(result)

        except ChatAdminRequiredError:
            await event.edit("**• لا تملك صلاحيات لسحب الأعضاء من الجروب المصدر**")
        except Exception as e:
            await event.edit(f"**• فشل: {str(e)[:50]}**")

    logger.info(f"Handlers (taqleed/ent7al + smart add) ready for {phone}")
