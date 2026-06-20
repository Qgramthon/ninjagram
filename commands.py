import asyncio
import io
import os
import logging
from concurrent.futures import ThreadPoolExecutor
from telethon import events
from telethon.errors import FloodWaitError, ChatAdminRequiredError
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon.tl.types import InputPhoto, DocumentAttributeAudio, DocumentAttributeVideo
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.messages import AddChatUserRequest
from shared import (
    active_clients, muted_users, taqleed_users, ent7al_users, ent7al_original,
    client_me, track_command, logger, TEMP_DIR
)

# ───────────────────────────────────────────────
# ThreadPoolExecutor مشترك لجميع عمليات التحميل
# ───────────────────────────────────────────────
_DOWNLOAD_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="yt_dl")

def format_duration(seconds):
    if not seconds:
        return "0:00"
    mins, secs = divmod(int(seconds), 60)
    return f"{mins}:{secs:02d}"

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

# ───────────────────────────────────────────────
# دوال تحميل في Thread منفصل (لا تبلوك event loop)
# ───────────────────────────────────────────────

def _check_aria2c() -> bool:
    """تحقق إذا aria2c مثبت في النظام"""
    import shutil
    return shutil.which("aria2c") is not None

def _build_base_opts(out_dir: str, use_aria2c: bool) -> dict:
    """خيارات yt_dlp المشتركة بين الأوامر"""
    opts = {
        'outtmpl': f'{out_dir}/%(title).80s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'noplaylist': True,
        'concurrent_fragment_downloads': 8,   # تحميل مجزأ متوازي
        'http_chunk_size': 10 * 1024 * 1024,  # قطع 10MB
        'socket_timeout': 30,
        'retries': 5,
        'fragment_retries': 5,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],  # fallback تلقائي
                'skip': ['dash', 'hls'],               # تجنب التجزئة البطيئة
            }
        },
    }
    if use_aria2c:
        opts.update({
            'external_downloader': 'aria2c',
            'external_downloader_args': {
                'aria2c': [
                    '--max-connection-per-server=16',
                    '--split=16',
                    '--min-split-size=1M',
                    '--max-concurrent-downloads=8',
                    '--continue=true',
                    '--summary-interval=0',
                    '--console-log-level=error',
                ]
            },
        })
    return opts

def _run_ytdlp_audio(query: str, out_dir: str) -> tuple[dict, str]:
    """تشغيل yt_dlp للصوت — يعمل في thread خارجي"""
    import yt_dlp

    use_aria2c = _check_aria2c()
    final_path = {}

    def hook(d):
        if d['status'] == 'finished':
            fp = d.get('info_dict', {}).get('filepath') or d.get('postprocessor_result', {}).get('filepath')
            if fp:
                final_path['v'] = fp

    opts = _build_base_opts(out_dir, use_aria2c)
    opts.update({
        'format': 'bestaudio[abr>=128]/bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'postprocessor_hooks': [hook],
    })

    search = f"ytsearch1:{query}" if not query.startswith("http") else query

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(search, download=True)
        if isinstance(info, dict) and 'entries' in info:
            info = info['entries'][0]

    # اكتشاف الملف إذا لم يُرجع hook المسار
    filepath = final_path.get('v')
    if not filepath or not os.path.exists(filepath):
        base = ydl.prepare_filename(info)
        base_no_ext = os.path.splitext(base)[0]
        for ext in ('.mp3', '.m4a', '.opus', '.ogg', '.webm'):
            c = base_no_ext + ext
            if os.path.exists(c):
                filepath = c
                break
        else:
            raise FileNotFoundError("لم يُعثر على ملف الصوت بعد التحميل")

    return info, filepath


def _run_ytdlp_video(query: str, out_dir: str) -> tuple[dict, str]:
    """تشغيل yt_dlp للفيديو — يعمل في thread خارجي"""
    import yt_dlp

    use_aria2c = _check_aria2c()
    final_path = {}

    def hook(d):
        if d['status'] == 'finished':
            fp = d.get('info_dict', {}).get('filepath') or d.get('postprocessor_result', {}).get('filepath')
            if fp:
                final_path['v'] = fp

    opts = _build_base_opts(out_dir, use_aria2c)
    opts.update({
        # أفضل جودة ≤720p مع صوت، ويفضّل mp4 مباشرة لتفادي الـ merge
        'format': (
            'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]'
            '/bestvideo[height<=720]+bestaudio'
            '/best[height<=720]/best'
        ),
        'merge_output_format': 'mp4',
        'postprocessor_hooks': [hook],
    })

    search = f"ytsearch1:{query}" if not query.startswith("http") else query

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(search, download=True)
        if isinstance(info, dict) and 'entries' in info:
            info = info['entries'][0]

    filepath = final_path.get('v')
    if not filepath or not os.path.exists(filepath):
        base = ydl.prepare_filename(info)
        base_no_ext = os.path.splitext(base)[0]
        for ext in ('.mp4', '.webm', '.mkv'):
            c = base_no_ext + ext
            if os.path.exists(c):
                filepath = c
                break
        else:
            raise FileNotFoundError("لم يُعثر على ملف الفيديو بعد التحميل")

    return info, filepath


def _run_ytdlp_general(url: str, out_dir: str) -> tuple[dict, str]:
    """تحميل عام (Pinterest وغيره) — يعمل في thread خارجي"""
    import yt_dlp

    use_aria2c = _check_aria2c()
    final_path = {}

    def hook(d):
        if d['status'] == 'finished':
            fp = d.get('info_dict', {}).get('filepath') or d.get('postprocessor_result', {}).get('filepath')
            if fp:
                final_path['v'] = fp

    opts = _build_base_opts(out_dir, use_aria2c)
    opts.update({
        'format': 'best',
        'merge_output_format': 'mp4',
        'postprocessor_hooks': [hook],
    })

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if isinstance(info, dict) and 'entries' in info:
            info = info['entries'][0]

    filepath = final_path.get('v')
    if not filepath or not os.path.exists(filepath):
        base = ydl.prepare_filename(info)
        base_no_ext = os.path.splitext(base)[0]
        for ext in ('.mp4', '.webm', '.mkv', '.jpg', '.jpeg', '.png', '.gif'):
            c = base_no_ext + ext
            if os.path.exists(c):
                filepath = c
                break
        else:
            raise FileNotFoundError("لم يُعثر على الملف بعد التحميل")

    return info, filepath


# ───────────────────────────────────────────────
# الـ Handlers الرئيسية
# ───────────────────────────────────────────────

async def setup_handlers(client, phone):
    if phone not in muted_users:
        muted_users[phone] = {}
    if phone not in taqleed_users:
        taqleed_users[phone] = {}
    if phone not in ent7al_users:
        ent7al_users[phone] = False
    if phone not in ent7al_original:
        ent7al_original[phone] = {}

    # ─────────────── التقليد ───────────────
    @client.on(events.NewMessage(incoming=True))
    async def auto_taqleed(event):
        sender_id = event.sender_id
        if sender_id and sender_id in taqleed_users.get(phone, {}):
            if event.text and not event.text.startswith('.'):
                await asyncio.sleep(0.3)
                try:
                    await event.reply(event.text)
                except:
                    pass

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.تقليد$'))
    async def taq(event):
        target = None
        if event.is_reply:
            target = (await event.get_reply_message()).sender_id
        elif event.is_private:
            target = event.chat_id
        if target:
            taqleed_users[phone][target] = True
            await event.edit("**• يتم التقليد**")

    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.غ تقليد$'))
    async def notaq(event):
        target = None
        if event.is_reply:
            target = (await event.get_reply_message()).sender_id
        elif event.is_private:
            target = event.chat_id
        if target and target in taqleed_users.get(phone, {}):
            del taqleed_users[phone][target]
        await event.edit("**• تم فك التقليد**")

    # ─────────────── الانتحال ───────────────
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.انتحال$'))
    async def ent7al(event):
        track_command(phone, ".انتحال")
        await event.edit("**• جاري الانتحال...**")

        target_user = None
        if event.is_reply:
            reply = await event.get_reply_message()
            try:
                target_user = await client.get_entity(reply.sender_id)
            except:
                pass
        elif event.is_private:
            try:
                target_user = await client.get_entity(event.chat_id)
            except:
                pass

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
        except:
            pass

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
            except:
                pass
        except:
            pass

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
            except:
                pass
        except:
            pass

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
                await client(UpdateProfileRequest(first_name=first, last_name=last))
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
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
                try:
                    await client(DeletePhotosRequest(id=[InputPhoto(
                        id=original['added_photo_id'],
                        access_hash=0,
                        file_reference=b''
                    )]))
                except:
                    pass
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
            except Exception as e:
                logger.error(f"Fallback photo deletion failed: {e}")

        try:
            await client(UpdateProfileRequest(about=original.get('about', '')))
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            try:
                await client(UpdateProfileRequest(about=original.get('about', '')))
            except:
                pass
        except Exception as e:
            logger.error(f"Restore bio failed: {e}")

        ent7al_users[phone] = False
        ent7al_original[phone] = {}
        await event.edit("**• تم إلغاء الانتحال**")

    # ─────────────── إضافة أعضاء ───────────────
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
        except Exception:
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
            async for user in client.iter_participants(source_group, limit=count):
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
                    await event.edit("**• الصلاحيات غير كافية - يجب أن تكون مشرفًا**")
                    return
                except Exception as e:
                    failed += 1
                    if "PEER_FLOOD" in str(e) or "USER_PRIVACY_RESTRICTED" in str(e):
                        break

            result_msg = f"**• تمت إضافة {added} عضو بنجاح**"
            if failed:
                result_msg += f"\n• فشل في إضافة {failed} عضو (الخصوصية أو الحظر)"
            await event.edit(result_msg)

        except ChatAdminRequiredError:
            await event.edit("**• لا تملك صلاحيات لسحب الأعضاء من الجروب المصدر**")
        except Exception as e:
            await event.edit(f"**• فشل في جلب الأعضاء: {str(e)[:50]}**")

    # ─────────────── تحميل الصوت (.يوت) ───────────────
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.يوت (.+)'))
    async def youtube_audio(event):
        query = event.pattern_match.group(1).strip()
        await event.edit("**• 🎵 جاري البحث والتحميل...**")

        loop = asyncio.get_event_loop()
        try:
            info, filepath = await loop.run_in_executor(
                _DOWNLOAD_EXECUTOR,
                _run_ytdlp_audio, query, TEMP_DIR
            )
        except FileNotFoundError as e:
            await event.edit(f"**• {e}**")
            return
        except Exception as e:
            await event.edit(f"**• فشل التحميل:**\n{str(e)[:200]}")
            return

        try:
            duration_str = format_duration(info.get('duration', 0))
            caption = f"᥉᥆ᥙɾᥴꫀ Ϙƚһ᥆ꪀ\n• {duration_str} | ᥲᥙძᎥ᥆"
            await client.send_file(
                event.chat_id,
                filepath,
                caption=caption,
                attributes=[DocumentAttributeAudio(
                    duration=info.get('duration', 0),
                    title=info.get('title', ''),
                    performer=info.get('uploader', '')
                )]
            )
            await event.delete()
        except Exception as e:
            await event.edit(f"**• فشل الإرسال:**\n{str(e)[:200]}")
        finally:
            try:
                os.remove(filepath)
            except:
                pass

    # ─────────────── تحميل الفيديو (.فيد) ───────────────
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.فيد (.+)'))
    async def video_download(event):
        query = event.pattern_match.group(1).strip()
        await event.edit("**• 🎬 جاري تحميل الفيديو...**")

        loop = asyncio.get_event_loop()
        try:
            info, filepath = await loop.run_in_executor(
                _DOWNLOAD_EXECUTOR,
                _run_ytdlp_video, query, TEMP_DIR
            )
        except FileNotFoundError as e:
            await event.edit(f"**• {e}**")
            return
        except Exception as e:
            await event.edit(f"**• فشل تحميل الفيديو:**\n{str(e)[:200]}")
            return

        try:
            duration_str = format_duration(info.get('duration', 0))
            caption = f"᥉᥆ᥙɾᥴꫀ Ϙƚһ᥆ꪀ\n• {duration_str} | ᥎Ꭵძꫀ᥆"
            await client.send_file(
                event.chat_id,
                filepath,
                caption=caption,
                attributes=[DocumentAttributeVideo(
                    duration=info.get('duration', 0),
                    w=info.get('width', 0),
                    h=info.get('height', 0),
                    supports_streaming=True
                )]
            )
            await event.delete()
        except Exception as e:
            await event.edit(f"**• فشل الإرسال:**\n{str(e)[:200]}")
        finally:
            try:
                os.remove(filepath)
            except:
                pass

    # ─────────────── تحميل بنترست (.بين) ───────────────
    @client.on(events.NewMessage(outgoing=True, pattern=r'^\.بين (.+)'))
    async def pinterest_download(event):
        url = event.pattern_match.group(1).strip()
        if "pinterest.com" not in url and "pin.it" not in url:
            await event.edit("**• الرجاء إدخال رابط بنترست صالح**")
            return
        await event.edit("**• 📌 جاري التحميل من بنترست...**")

        loop = asyncio.get_event_loop()
        try:
            info, filepath = await loop.run_in_executor(
                _DOWNLOAD_EXECUTOR,
                _run_ytdlp_general, url, TEMP_DIR
            )
        except FileNotFoundError as e:
            await event.edit(f"**• {e}**")
            return
        except Exception as e:
            await event.edit(f"**• فشل تحميل بنترست:**\n{str(e)[:200]}")
            return

        try:
            if filepath.lower().endswith(('.mp4', '.webm')):
                duration_str = format_duration(info.get('duration', 0))
                caption = f"᥉᥆ᥙɾᥴꫀ Ϙƚһ᥆ꪀ\n• {duration_str} | ρᎥꪀƚɾꫀ᥉ꫀƚ"
                await client.send_file(
                    event.chat_id, filepath, caption=caption,
                    attributes=[DocumentAttributeVideo(
                        duration=info.get('duration', 0),
                        w=info.get('width', 0),
                        h=info.get('height', 0),
                        supports_streaming=True
                    )]
                )
            else:
                caption = f"᥉᥆ᥙɾᥴꫀ Ϙƚһ᥆ꪀ\n• Pin | ρᎥꪀƚɾꫀ᥉ꫀƚ"
                await client.send_file(event.chat_id, filepath, caption=caption)

            await event.delete()
        except Exception as e:
            await event.edit(f"**• فشل الإرسال:**\n{str(e)[:200]}")
        finally:
            try:
                os.remove(filepath)
            except:
                pass

    logger.info(f"All handlers ready for {phone}")
