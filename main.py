#!/usr/bin/env python3
# 🧨 NinjaGram Pro Max Ultra v10 - Railway Test
import asyncio, os, threading
from aiohttp import web
from telethon import TelegramClient, events, Button

# ==================== CONFIG ====================
BOT_TOKEN = '7998616214:AAHJmfPpL8rzRgso3hxIO-CKHE2rlycyNwo'
API_ID = 2040
API_HASH = 'b18441a1ff607e10a989891a5462e627'
PORT = int(os.environ.get('PORT', 8080))

# ==================== BOT ====================
bot = TelegramClient('session', API_ID, API_HASH)

# ==================== WEB APP ====================
async def handle(request):
    return web.Response(text="✅ Bot Running")

app = web.Application()
app.router.add_get('/', handle)

def start_web():
    web.run_app(app, host='0.0.0.0', port=PORT, print=lambda _: None)

# ==================== HANDLERS ====================
@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await event.respond("✅ **البوت شغال!**\n\nاختار الخدمة:", buttons=[
        [Button.inline("📞 تروكولر", b"tc")],
        [Button.inline("🕵️ OSINT", b"osint")],
        [Button.inline("📊 إحصائيات", b"info")],
    ], parse_mode='md')

@bot.on(events.CallbackQuery(data=b"main"))
async def back_main(event):
    await event.edit("✅ **القائمة الرئيسية**", buttons=[
        [Button.inline("📞 تروكولر", b"tc")],
        [Button.inline("🕵️ OSINT", b"osint")],
        [Button.inline("📊 إحصائيات", b"info")],
    ], parse_mode='md')

@bot.on(events.CallbackQuery(data=b"info"))
async def info_handler(event):
    await event.edit("📊 **NinjaGram Pro Max Ultra v10**\n\n✅ البوت شغال على Railway!", buttons=[[Button.inline("🔙", b"main")]])

@bot.on(events.CallbackQuery(data=b"tc"))
async def tc_start(event):
    await event.respond("📞 أرسل رقم الهاتف للبحث")

@bot.on(events.CallbackQuery(data=b"osint"))
async def osint_start(event):
    await event.respond("🕵️ أرسل يوزر أو ID للفحص")

# ==================== RUN ====================
if __name__ == '__main__':
    print("🧨 NinjaGram Starting...")
    
    # Start web server in thread
    threading.Thread(target=start_web, daemon=True).start()
    print(f"🌐 Web Server on port {PORT}")
    
    # Start bot
    async def main():
        await bot.start(bot_token=BOT_TOKEN)
        me = await bot.get_me()
        print(f"✅ Bot Online: @{me.username}")
        print("🚀 Ready!")
        await bot.run_until_disconnected()
    
    asyncio.run(main())
