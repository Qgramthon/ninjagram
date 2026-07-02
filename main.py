#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 🧨 NinjaGram X - خدمي وإحترافي (Railway Ready)
import asyncio, os, re, logging, requests, json, uuid, io
from datetime import datetime
from urllib.parse import quote
from io import BytesIO
import qrcode
from PIL import Image, ImageDraw, ImageFont
from telethon import TelegramClient, events, Button
from telethon.tl.functions.users import GetFullUserRequest
import aiohttp
from aiohttp import web

# ==================== التكوين (Configuration) ====================
DATA_DIR = './data'
os.makedirs(DATA_DIR, exist_ok=True)

# !! مهم: استبدل هذه القيم بقيمك الخاصة !!
BOT_TOKEN = '7998616214:AAHJmfPpL8rzRgso3hxIO-CKHE2rlycyNwo'
API_ID = 2040  # هذا API_ID تجريبي وقديم، استخدم الخاص بك
API_HASH = 'b18441a1ff607e10a989891a5462e627' # هذا API_HASH تجريبي وقديم، استخدم الخاص بك
DEV_ID = 6443238809
PORT = int(os.environ.get('PORT', 8080))

# تخزين حالات المستخدمين
user_states = {}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger('NinjaGramX')

# إنشاء العميل
bot = TelegramClient(f'{DATA_DIR}/session', API_ID, API_HASH)

# ==================== تطبيق ويب لـ Railway ====================
async def handle_health(request):
    return web.Response(text="✅ NinjaGram X Bot is Running!")

app = web.Application()
app.router.add_get('/', handle_health)

# ==================== مكتبة الخدمات الحقيقية (Service Library) ====================
class RealServices:
    """مكتبة خدمات حقيقية ومفيدة تعتمد على APIs مجانية"""

    @staticmethod
    async def check_whatsapp(phone: str) -> dict:
        """التحقق من وجود رقم على الواتساب ومعلوماته الأساسية"""
        result = {"phone": phone, "has_whatsapp": False, "profile": {}}
        # API مجانية للتحقق من الواتساب (قد تحتاج لمفتاح لكنها تعمل بشكل أساسي)
        url = f"https://walog.darksmurf205.repl.co/check?phone={phone}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("status") == "success":
                            result["has_whatsapp"] = True
                            result["profile"] = {
                                "name": data.get("name", "غير معروف"),
                                "about": data.get("about", ""),
                                "photo_url": data.get("photo", "")
                            }
        except Exception as e:
            logger.error(f"WhatsApp check error: {e}")
        return result

    @staticmethod
    async def ip_info(ip: str) -> dict:
        """الحصول على معلومات شاملة عن أي عنوان IP"""
        url = f"http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,query"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    return await resp.json()
        except Exception as e:
            return {"status": "fail", "message": str(e)}

    @staticmethod
    def generate_qr(data: str, box_size: int = 10) -> BytesIO:
        """إنشاء رمز QR من أي نص أو رابط"""
        qr = qrcode.QRCode(version=1, box_size=box_size, border=4)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        output = BytesIO()
        img.save(output, format='PNG')
        output.seek(0)
        output.name = "qr_code.png"
        return output

    @staticmethod
    async def get_crypto_price(coin_id: str = "bitcoin") -> dict:
        """جلب سعر العملات الرقمية (Bitcoin, Ethereum, etc.)"""
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    return await resp.json()
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    async def check_phone_info(phone: str) -> dict:
        """الحصول على معلومات أساسية عن رقم الهاتف (الدولة والشركة)"""
        url = f"https://api.apilayer.com/number_verification/validate?number={phone}"
        headers = {"apikey": "YOUR_API_KEY_FROM_APILAYER"} # يمكنك التسجيل للحصول على مفتاح مجاني
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=15) as resp:
                    return await resp.json()
        except Exception as e:
            # في حالة عدم وجود مفتاح API، نعطي نتيجة وهمية للديمو
            logger.warning(f"Phone info API key missing, using demo data. Error: {e}")
            # استخراج بسيط لمفتاح الدولة (افتراضي)
            country_code = phone[:3] if phone.startswith('+') else phone[:2]
            return {
                "valid": True,
                "number": phone,
                "local_format": phone,
                "international_format": phone,
                "country_prefix": country_code,
                "country_name": "Demo Country (Add API Key)",
                "location": "World",
                "carrier": "Demo Carrier (Add API Key)",
                "line_type": "mobile"
            }

    @staticmethod
    async def generate_text_to_image(text: str) -> BytesIO:
        """تحويل النص العربي إلى صورة بتنسيق جميل (مفيد للتصاميم السريعة)"""
        img = Image.new('RGB', (800, 400), color='#2C3E50')
        d = ImageDraw.Draw(img)
        # يمكنك تحميل خط عربي جميل ووضعه في مجلد fonts
        font_path = "fonts/arabic_font.ttf"
        try:
            font = ImageFont.truetype(font_path, 24)
        except:
            font = ImageFont.load_default()

        d.text((20,20), text, fill='#ECF0F1', font=font)
        output = BytesIO()
        img.save(output, format='PNG')
        output.seek(0)
        output.name = "text_image.png"
        return output

# ==================== واجهة المستخدم (UI) ====================
class UI:
    @staticmethod
    def main_menu():
        return [
            [Button.inline("📱 فحص واتساب", b"wa_check")],
            [Button.inline("🌍 معلومات IP", b"ip_info")],
            [Button.inline("📊 أسعار العملات", b"crypto")],
            [Button.inline("📞 معلومات رقم", b"phone_info")],
            [Button.inline("🔲 إنشاء QR كود", b"make_qr")],
            [Button.inline("🕵️ تحليل حساب (OSINT)", b"account_osint")],
            [Button.inline("🖼️ نص إلى صورة", b"text2img")],
            [Button.inline("ℹ️ حول البوت", b"about")],
        ]

# ==================== أوامر البوت ====================
@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await event.respond(
        "🧨 **NinjaGram X - البوت الخدمي الشامل**\n\n"
        "اختر إحدى الخدمات الحقيقية من القائمة أدناه:",
        buttons=UI.main_menu(),
        parse_mode='md'
    )

@bot.on(events.CallbackQuery(data=b"main"))
async def back_to_main(event):
    await event.edit(
        "🧨 **القائمة الرئيسية**",
        buttons=UI.main_menu(),
        parse_mode='md'
    )

@bot.on(events.CallbackQuery(data=b"about"))
async def about_handler(event):
    await event.edit(
        "🧨 **NinjaGram X**\n\n"
        "بوت خدمات متعددة ومفيدة، مبني بعناية ليقدم خدمات حقيقية وموثوقة.\n\n"
        "👨‍💻 المطور: @Q_g_r_a_m",
        buttons=[[Button.inline("🔙 رجوع", b"main")]],
        parse_mode='md'
    )

# ==================== معالجة الخدمات ====================
@bot.on(events.CallbackQuery(data=b"wa_check"))
async def wa_check_prompt(event):
    user_states[event.sender_id] = "wa_check"
    await event.edit("📱 **فحص واتساب**\n\nأرسل رقم الهاتف بصيغة دولية (مثال: +201000000000):",
                     buttons=[[Button.inline("🔙 رجوع", b"main")]], parse_mode='md')

@bot.on(events.CallbackQuery(data=b"ip_info"))
async def ip_info_prompt(event):
    user_states[event.sender_id] = "ip_info"
    await event.edit("🌍 **معلومات IP**\n\nأرسل عنوان IP للفحص:",
                     buttons=[[Button.inline("🔙 رجوع", b"main")]], parse_mode='md')

@bot.on(events.CallbackQuery(data=b"crypto"))
async def crypto_prompt(event):
    await event.edit("📊 **أسعار العملات**\n\nاختر العملة:",
                     buttons=[
                         [Button.inline("₿ بيتكوين", b"crypto_bitcoin")],
                         [Button.inline("⟠ إيثريوم", b"crypto_ethereum")],
                         [Button.inline("🔙 رجوع", b"main")]
                     ], parse_mode='md')

@bot.on(events.CallbackQuery(data=re.compile(rb"crypto_(.+)")))
async def crypto_handler(event):
    coin = event.data.decode().split("_")[1]
    await event.answer(f"جاري جلب سعر {coin}...")
    data = await RealServices.get_crypto_price(coin)
    if "error" in data:
        await event.edit("❌ فشل جلب البيانات. تأكد من الاتصال بالإنترنت.",
                         buttons=[[Button.inline("🔙 رجوع", b"crypto")]], parse_mode='md')
        return

    price = data.get(coin, {}).get("usd", "غير متاح")
    change = data.get(coin, {}).get("usd_24h_change", "غير متاح")
    change_emoji = "🔺" if change and change > 0 else "🔻"

    await event.edit(
        f"📊 **سعر {coin.capitalize()}**\n\n"
        f"💰 السعر الحالي: ${price}\n"
        f"📈 التغير (24 ساعة): {change_emoji} {change:.2f}%",
        buttons=[[Button.inline("🔙 رجوع", b"crypto")]], parse_mode='md'
    )

@bot.on(events.CallbackQuery(data=b"phone_info"))
async def phone_info_prompt(event):
    user_states[event.sender_id] = "phone_info"
    await event.edit("📞 **معلومات رقم الهاتف**\n\nأرسل رقم الهاتف بصيغة دولية:",
                     buttons=[[Button.inline("🔙 رجوع", b"main")]], parse_mode='md')

@bot.on(events.CallbackQuery(data=b"make_qr"))
async def make_qr_prompt(event):
    user_states[event.sender_id] = "make_qr"
    await event.edit("🔲 **إنشاء QR كود**\n\nأرسل النص أو الرابط المراد تحويله إلى QR:",
                     buttons=[[Button.inline("🔙 رجوع", b"main")]], parse_mode='md')

@bot.on(events.CallbackQuery(data=b"account_osint"))
async def account_osint_prompt(event):
    user_states[event.sender_id] = "account_osint"
    await event.edit("🕵️ **تحليل حساب تيليجرام**\n\nأرسل يوزر الحساب (@username) أو ID الرقمي:",
                     buttons=[[Button.inline("🔙 رجوع", b"main")]], parse_mode='md')

@bot.on(events.CallbackQuery(data=b"text2img"))
async def text2img_prompt(event):
    user_states[event.sender_id] = "text2img"
    await event.edit("🖼️ **نص إلى صورة**\n\nأرسل النص العربي المراد تحويله لصورة:",
                     buttons=[[Button.inline("🔙 رجوع", b"main")]], parse_mode='md')

# ==================== معالج الرسائل الرئيسي ====================
@bot.on(events.NewMessage(func=lambda e: e.sender_id in user_states and not e.text.startswith('/')))
async def message_handler(event):
    uid = event.sender_id
    state = user_states.pop(uid, None) # إزالة الحالة بعد الاستلام
    text = event.text.strip()

    if not state:
        return

    # إعلام المستخدم بأن العملية جارية
    processing_msg = await event.respond("⏳ جاري المعالجة...")

    try:
        if state == "wa_check":
            result = await RealServices.check_whatsapp(text)
            if result["has_whatsapp"]:
                profile = result["profile"]
                response = (
                    f"✅ **رقم الواتساب: {text}**\n\n"
                    f"👤 الاسم: {profile.get('name', 'غير معروف')}\n"
                    f"📝 الحالة: {profile.get('about', 'غير معروف')}\n"
                )
            else:
                response = f"❌ **الرقم {text} ليس لديه واتساب أو أن الخدمة غير متاحة حاليًا.**"
            await processing_msg.edit(response, buttons=[[Button.inline("🔙 رجوع", b"main")]], parse_mode='md')

        elif state == "ip_info":
            result = await RealServices.ip_info(text)
            if result.get("status") == "fail":
                await processing_msg.edit(f"❌ فشل في جلب معلومات IP: {result.get('message', 'غير معروف')}",
                                        buttons=[[Button.inline("🔙 رجوع", b"main")]], parse_mode='md')
            else:
                response = (
                    f"🌍 **معلومات IP: {text}**\n\n"
                    f"📍 الدولة: {result.get('country', '?')} ({result.get('countryCode', '?')})\n"
                    f"🏙️ المدينة: {result.get('city', '?')}، {result.get('regionName', '?')}\n"
                    f"📮 الرمز البريدي: {result.get('zip', '?')}\n"
                    f"🕒 التوقيت: {result.get('timezone', '?')}\n"
                    f"🔌 مزود الخدمة: {result.get('isp', '?')}\n"
                    f"🏢 المنظمة: {result.get('org', '?')}\n"
                )
                await processing_msg.edit(response, buttons=[[Button.inline("🔙 رجوع", b"main")]], parse_mode='md')

        elif state == "phone_info":
            result = await RealServices.check_phone_info(text)
            response = (
                f"📞 **معلومات الرقم: {text}**\n\n"
                f"✅ صالح: {'نعم' if result.get('valid') else 'لا'}\n"
                f"🌍 الدولة: {result.get('country_name', '?')}\n"
                f"📍 الموقع: {result.get('location', '?')}\n"
                f"📡 الناقل: {result.get('carrier', '?')}\n"
                f"📱 نوع الخط: {result.get('line_type', '?')}\n"
            )
            await processing_msg.edit(response, buttons=[[Button.inline("🔙 رجوع", b"main")]], parse_mode='md')

        elif state == "make_qr":
            qr_image = RealServices.generate_qr(text)
            await bot.send_file(
                event.chat_id,
                qr_image,
                caption=f"🔲 **QR Code for:** `{text[:50]}...`",
                buttons=[[Button.inline("🔙 رجوع", b"main")]]
            )
            await processing_msg.delete() # حذف رسالة "جاري المعالجة"

        elif state == "account_osint":
            try:
                # تنظيف المدخلات
                if text.isdigit() or (text.startswith('-') and text[1:].isdigit()):
                    entity = await bot.get_entity(int(text))
                else:
                    entity = await bot.get_entity(text.replace("@", ""))

                full = await bot(GetFullUserRequest(entity))
                user = entity

                response = (
                    f"🕵️ **تحليل حساب: {text}**\n\n"
                    f"🆔 ID: `{user.id}`\n"
                    f"👤 الاسم: {getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}\n"
                    f"📛 اليوزر: @{getattr(user, 'username', 'لا يوجد')}\n"
                    f"📞 رقم الهاتف: {'مكشوف' if getattr(user, 'phone', None) else 'مخفي'}\n"
                    f"✅ موثق: {'نعم' if getattr(user, 'verified', False) else 'لا'}\n"
                    f"⭐ بريميوم: {'نعم' if getattr(user, 'premium', False) else 'لا'}\n"
                    f"🤖 بوت: {'نعم' if getattr(user, 'bot', False) else 'لا'}\n"
                    f"⚠️ احتيال: {'نعم' if getattr(user, 'scam', False) else 'لا'}\n"
                    f"📝 البايو: {getattr(full.full_user, 'about', 'لا يوجد')[:300]}\n"
                )
                await processing_msg.edit(response, buttons=[[Button.inline("🔙 رجوع", b"main")]], parse_mode='md')
            except Exception as e:
                await processing_msg.edit(f"❌ الحساب غير موجود أو حدث خطأ: {e}",
                                        buttons=[[Button.inline("🔙 رجوع", b"main")]], parse_mode='md')

        elif state == "text2img":
            image = await RealServices.generate_text_to_image(text)
            await bot.send_file(
                event.chat_id,
                image,
                caption=f"🖼️ تم تحويل النص إلى صورة!",
                buttons=[[Button.inline("🔙 رجوع", b"main")]]
            )
            await processing_msg.delete()

    except Exception as e:
        logger.error(f"Error in state '{state}': {e}")
        await processing_msg.edit(f"❌ حدث خطأ غير متوقع: {e}",
                                buttons=[[Button.inline("🔙 رجوع", b"main")]], parse_mode='md')

# ==================== تشغيل البوت ====================
if __name__ == '__main__':
    print("🧨 NinjaGram X starting...")

    # تشغيل السيرفر الوهمي لـ Railway في الخلفية
    from threading import Thread
    Thread(target=lambda: web.run_app(app, host='0.0.0.0', port=PORT, print=lambda _: None), daemon=True).start()
    print(f"🌐 Web server running on port {PORT}")

    async def main():
        await bot.start(bot_token=BOT_TOKEN)
        me = await bot.get_me()
        print(f"✅ Bot @{me.username} is ready!")
        await bot.run_until_disconnected()

    # استخدام asyncio.run بدلاً من loop اليدوي (أفضل ممارسة)
    asyncio.run(main())
