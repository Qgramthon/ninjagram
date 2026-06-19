import asyncio
import io
import os
import logging
from telethon import events
from telethon.errors import FloodWaitError, ChatAdminRequiredError
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon.tl.types import InputPhoto, DocumentAttributeAudio
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.types import InputPhoneContact
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.messages import AddChatUserRequest
from shared import (
    active_clients, muted_users, taqleed_users, ent7al_users, ent7al_original,
    client_me, track_command, logger, TEMP_DIR
)

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

async def setup_handlers(client, phone):
    if phone not in muted_users:
        muted_users[phone] = {}
    if phone not in taqleed_users:
        taqleed_users[phone] = {}
    if phone not in ent7al_users:
        ent7al_users[phone] = False
    if phone not in ent7al_original:
        ent7al_original[phone] = {}

    @client.on(events.NewMessage(incoming=True))
    async def auto_mute(event):
        if event.is_private and event.sender_id in muted_users.get(phone, {}):
            try: await event.delete()
            except: pass

    @client.on(events.NewMessage(incoming=True))
    async def auto_taqleed(event):
        sender_id = event.sender_id
        if sender_id and sender_id in taqleed_users.get(phone, {}):
            if event.text and not event.text.startswith('.'):
                await asyncio.sleep(0.3)
                try: await event.reply(event.text)
                except: pass

    # ======================== الأوامر الأساسية ========================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.سورس$'))
    async def src(event):
        await event.edit("**تيليثون ڪيوجـࢪام 𔓕**\n\n• لتنصيب السورس [إضغط هنا](https://t.me/Q_g_r_a_m)\n• لمتابعة التحديثات [إضغط هنا](https://t.me/Q_g_r_a_m)", parse_mode='md')

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.اوامر$'))
    async def cmds(event):
        track_command(phone, ".اوامر")
        await event.edit("""**اوامر السورس 𔓕**

ايدي ا
تقليد غ تقليد
خط غ خط
اسم + الاسم
بايو + البايو
ث غ ث
اضافة + عدد + @يوزر
حذف + عدد
رن
قفل فتح
كتم غ كتم
حظر غ حظر
تقيد غ تقييد
تهكير
انتحال الغاء انتحال
ذكاء + سؤال
بوت + سؤال
صراحة
كت
ضحك غيوم قلوب ورود
غباء
تحويل + رقم
رفع شحات رفع حمار رفع غبي رفع سباك رفع مالك رفع ادمن
يوت + اسم/رابط
اوامر سورس""", parse_mode='md')

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.(ايدي|ا)$'))
    async def id_cmd(event):
        track_command(phone, ".ايدي")
        await event.delete()
        user = None
        if event.is_reply: user = await client.get_entity((await event.get_reply_message()).sender_id)
        elif event.is_group: user = await client.get_entity(event.sender_id)
        else: user = await client.get_entity(event.chat_id)
        if not user: return
        lines = [f"ꪀᥲꪔꫀ {user.first_name or ''} {user.last_name or ''}".strip()]
        if user.username: lines.append(f"ᥙ᥉ꫀɾ @{user.username}")
        try:
            full = await client.get_entity(user.id)
            if hasattr(full, 'about') and full.about: lines.append(f"ᑲᎥ᥆ {full.about[:50]}")
        except: pass
        lines.append(f"Ꭵძ {user.id}")
        await client.send_message(event.chat_id, "\n".join(lines))

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

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.خط$'))
    async def bold(event):
        bold_mode[phone] = True
        await event.edit("**• تم تفعيل الخط العريض**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غ خط$'))
    async def nobold(event):
        bold_mode[phone] = False
        await event.edit("**• تم الغاء الخط العريض**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.اسم (.+)'))
    async def name(event):
        try:
            await client(UpdateProfileRequest(first_name=event.pattern_match.group(1).strip(), last_name=''))
            await event.edit("**• تم تغيير الاسم**")
        except: await event.edit("**• فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بايو (.+)'))
    async def bio(event):
        try:
            await client(UpdateProfileRequest(about=event.pattern_match.group(1).strip()))
            await event.edit("**• تم تغيير البايو**")
        except: await event.edit("**• فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.ث$'))
    async def pin_msg(event):
        try:
            if event.is_reply: await (await event.get_reply_message()).pin(); await event.edit("**• تم التثبيت**")
            else: await client(ToggleDialogPinRequest(peer=event.input_chat, pinned=True)); await event.edit("**• تم تثبيت المحادثة**")
        except: await event.edit("**• فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غ ث$'))
    async def unpin_msg(event):
        try:
            if event.is_reply: await (await event.get_reply_message()).unpin(); await event.edit("**• تم الغاء التثبيت**")
            else: await client(ToggleDialogPinRequest(peer=event.input_chat, pinned=False)); await event.edit("**• تم الغاء تثبيت المحادثة**")
        except: await event.edit("**• فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.حذف (\d+)$'))
    async def delete_count(event):
        count = int(event.pattern_match.group(1))
        await event.edit(f"**• جاري حذف {count} رسالة**")
        try:
            messages = await client.get_messages(event.chat_id, limit=count)
            await client.delete_messages(event.chat_id, [m.id for m in messages])
            await event.edit(f"**• تم حذف {len(messages)} رسالة**")
        except: await event.edit("**• فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.حذف$'))
    async def delete_reply(event):
        if event.is_reply:
            try: await (await event.get_reply_message()).delete(); await event.delete()
            except: await event.edit("**• فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.رن$'))
    async def call(event):
        await event.edit("**• جاري الاتصال**")
        try:
            target = None
            if event.is_private: target = event.chat_id
            elif event.is_reply: target = (await event.get_reply_message()).sender_id
            if target: await client(RequestCallRequest(user_id=target, g_a_hash=b'', protocol=PhoneCallProtocol())); await event.edit("**• تم الاتصال**")
            else: await event.edit("**• فشل**")
        except: await event.edit("**• فشل الاتصال**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.قفل$'))
    async def lock(event):
        if event.is_group:
            try:
                rights = ChatBannedRights(until_date=None, send_messages=True, send_media=True, send_stickers=True, send_gifs=True, send_games=True, send_inline=True, send_polls=True, change_info=True, invite_users=True, pin_messages=True)
                await client(EditChatDefaultBannedRightsRequest(peer=event.input_chat, banned_rights=rights))
                await event.edit("**• تم قفل الجروب**")
            except: await event.edit("**• فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.فتح$'))
    async def unlock(event):
        if event.is_group:
            try:
                rights = ChatBannedRights(until_date=None, send_messages=False, send_media=False, send_stickers=False, send_gifs=False, send_games=False, send_inline=False, send_polls=False, change_info=False, invite_users=False, pin_messages=False)
                await client(EditChatDefaultBannedRightsRequest(peer=event.input_chat, banned_rights=rights))
                await event.edit("**• تم فتح الجروب**")
            except: await event.edit("**• فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.كتم$'))
    async def mute(event):
        target = None
        if event.is_reply: target = (await event.get_reply_message()).sender_id
        elif event.is_private: target = event.chat_id
        if target: muted_users[phone][target] = True
        await event.edit("**• تم الكتم**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غ كتم$'))
    async def unmute(event):
        target = None
        if event.is_reply: target = (await event.get_reply_message()).sender_id
        elif event.is_private: target = event.chat_id
        if target and target in muted_users.get(phone, {}): del muted_users[phone][target]
        await event.edit("**• تم فك الكتم**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.حظر$'))
    async def ban(event):
        target = None
        if event.is_reply: target = (await event.get_reply_message()).sender_id
        elif event.is_private: target = event.chat_id
        if target:
            try: await client(BlockRequest(target)); banned_users[phone][target] = True; await event.edit("**• تم الحظر**")
            except: await event.edit("**• فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غ حظر$'))
    async def unban(event):
        target = None
        if event.is_reply: target = (await event.get_reply_message()).sender_id
        elif event.is_private: target = event.chat_id
        if target:
            try: await client(UnblockRequest(target)); banned_users[phone].pop(target, None); await event.edit("**• تم فك الحظر**")
            except: await event.edit("**• فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تقيد$'))
    async def restrict(event):
        if event.is_group and event.is_reply:
            try: await client.edit_permissions(event.chat_id, (await event.get_reply_message()).sender_id, send_messages=False); await event.edit("**• تم التقييد**")
            except: await event.edit("**• فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غ تقييد$'))
    async def unrestrict(event):
        if event.is_group and event.is_reply:
            try: await client.edit_permissions(event.chat_id, (await event.get_reply_message()).sender_id, send_messages=True); await event.edit("**• تم فك التقييد**")
            except: await event.edit("**• فشل**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تهكير$'))
    async def hack(event):
        n = "الضحية"
        if event.is_reply:
            try: n = (await client.get_entity((await event.get_reply_message()).sender_id)).first_name
            except: pass
        await event.edit("**جاري التهكير**"); await asyncio.sleep(1)
        await event.edit("**تم اختراق 50%**"); await asyncio.sleep(1)
        await event.edit(f"**تم تهكير {n} بنجاح**")

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
            'photo_bytes': None,
            'added_photo_id': None,
            'about': ''
        }

        try:
            fu = await client(GetFullUserRequest('me'))
            if fu.full_user.about:
                original['about'] = fu.full_user.about
        except: pass

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

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.الغاء انتحال$'))
    async def unent7al(event):
        track_command(phone, ".الغاء انتحال")
        await event.edit("**• جاري إلغاء الانتحال...**")

        if not ent7al_users.get(phone) or not ent7al_original.get(phone):
            await event.edit("**• لا يوجد انتحال**")
            return

        original = ent7al_original[phone]

        restored_name = False
        first = original.get('first_name', '')
        last = original.get('last_name', '')
        for attempt in range(3):
            try:
                await client(UpdateProfileRequest(
                    first_name=first,
                    last_name=last
                ))
                await asyncio.sleep(1.5)
                me_now = await client.get_me()
                if me_now.first_name == first and (me_now.last_name or '') == last:
                    restored_name = True
                    break
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"Restore name attempt {attempt+1}: {e}")
                await asyncio.sleep(1)

        if not restored_name:
            logger.error(f"Could not fully restore name for {phone}")

        if original.get('added_photo_id'):
            try:
                await client(DeletePhotosRequest(id=[InputPhoto(
                    id=original['added_photo_id'],
                    access_hash=0,
                    file_reference=b''
                )]))
                await asyncio.sleep(2)
                logger.info(f"Deleted impersonated photo ID {original['added_photo_id']}")
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
        else:
            try:
                current_photos = await client.get_profile_photos('me', limit=1)
                if current_photos:
                    p = current_photos[0]
                    await client(DeletePhotosRequest(id=[InputPhoto(
                        id=p.id,
                        access_hash=p.access_hash,
                        file_reference=p.file_reference
                    )]))
                    await asyncio.sleep(2)
                    logger.info("Deleted most recent photo as fallback")
            except Exception as e:
                logger.error(f"Fallback photo deletion failed: {e}")

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

    # ================== أمر إضافة جهات من جروب خارجي ==================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.اضافة (\d+) (@?\w+)$'))
    async def add_members_from_group(event):
        if not event.is_group:
            await event.edit("**• الأمر يعمل في المجموعات فقط**")
            return

        count = int(event.pattern_match.group(1))
        target_username = event.pattern_match.group(2).strip()
        await event.edit(f"**• جاري سحب {count} عضو من {target_username} وإضافتهم هنا...**")

        try:
            source_group = await client.get_entity(target_username)
        except Exception as e:
            await event.edit(f"**• لم يتم العثور على الجروب {target_username}**")
            return

        try:
            await client.join_channel(source_group)
            await asyncio.sleep(3)
        except:
            pass

        added = 0
        failed = 0
        try:
            participants_iter = client.iter_participants(source_group, limit=count)
            async for user in participants_iter:
                if user.bot or user.deleted:
                    continue
                try:
                    if hasattr(event.chat, 'megagroup') and event.chat.megagroup:
                        await client(InviteToChannelRequest(channel=event.chat_id, users=[user.id]))
                    else:
                        await client(AddChatUserRequest(chat_id=event.chat_id, user_id=user.id, fwd_limit=10))
                    added += 1
                    await asyncio.sleep(1.5)
                except FloodWaitError as e:
                    logger.info(f"Flood wait {e.seconds}s")
                    await asyncio.sleep(e.seconds)
                    try:
                        if hasattr(event.chat, 'megagroup') and event.chat.megagroup:
                            await client(InviteToChannelRequest(channel=event.chat_id, users=[user.id]))
                        else:
                            await client(AddChatUserRequest(chat_id=event.chat_id, user_id=user.id, fwd_limit=10))
                        added += 1
                    except:
                        failed += 1
                except ChatAdminRequiredError:
                    await event.edit("**• الصلاحيات غير كافية - يجب أن تكون مشرفًا في هذا الجروب**")
                    return
                except Exception as e:
                    logger.warning(f"Failed to add {user.id}: {e}")
                    failed += 1
                    if "PEER_FLOOD" in str(e) or "USER_PRIVACY_RESTRICTED" in str(e):
                        break

            result_msg = f"**• تمت إضافة {added} عضو بنجاح**"
            if failed > 0:
                result_msg += f"\n• فشل في إضافة {failed} عضو (بسبب الخصوصية أو الحظر)"
            await event.edit(result_msg)

        except ChatAdminRequiredError:
            await event.edit("**• لا تملك صلاحيات لسحب الأعضاء من الجروب المصدر**")
        except Exception as e:
            await event.edit(f"**• فشل في جلب الأعضاء: {str(e)[:50]}**")

    # ================== أمر يوت – تحميل الصوت ==================
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.يوت (.+)'))
    async def youtube_audio(event):
        query = event.pattern_match.group(1).strip()
        await event.edit("**• جاري البحث عن الفيديو...**")

        try:
            import yt_dlp
        except ImportError:
            await event.edit("**• مكتبة yt-dlp غير مثبتة**")
            return

        if query.startswith("http"):
            search_query = query
        else:
            search_query = f"ytsearch1:{query}"

        ydl_opts = {
            'outtmpl': f'{TEMP_DIR}/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search_query, download=True)
                filepath = ydl.prepare_filename(info)
                if not os.path.exists(filepath):
                    base, _ = os.path.splitext(filepath)
                    for ext in ['.mp3', '.m4a', '.webm', '.opus']:
                        test_path = base + ext
                        if os.path.exists(test_path):
                            filepath = test_path
                            break
                if not os.path.exists(filepath):
                    await event.edit("**• فشل في العثور على الملف بعد التحميل**")
                    return

                await client.send_file(
                    event.chat_id,
                    filepath,
                    caption=f"**🎵 {info.get('title', 'بدون عنوان')}**",
                    attributes=[DocumentAttributeAudio(
                        duration=info.get('duration', 0),
                        title=info.get('title', ''),
                        performer=info.get('uploader', '')
                    )]
                )
                await event.delete()
                os.remove(filepath)

        except Exception as e:
            await event.edit(f"**• فشل التحميل:**\n{str(e)[:200]}")

    logger.info(f"All handlers ready for {phone}")
