#!/usr/bin/env python3
"""
NinjaGram Pro Max Ultra v10 - Main Entry Point
===============================================
تشغيل: NinjaGram Bot + UserBot System + Web Server
"""

import asyncio
import threading
import logging
import sys
import signal
import time
from datetime import datetime

from shared import *
from server import app

# ============ Configuration ============
HOST = os.environ.get('HOST', '0.0.0.0')
PORT = int(os.environ.get('PORT', 5000))
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# ============ Global State ============
shutdown_event = threading.Event()
bot_task = None

# ============================================================
# SESSION MANAGER
# ============================================================
def start_main_loop():
    """تشغيل Event Loop الرئيسي في Thread منفصل"""
    try:
        asyncio.set_event_loop(main_loop)
        
        # تحميل الجلسات المحفوظة
        logger.info("🔄 جاري تحميل الجلسات...")
        main_loop.run_until_complete(load_all_sessions())
        logger.info(f"✅ تم تحميل {len(active_clients)} جلسة")
        
        # جدولة الحفظ التلقائي
        asyncio.ensure_future(auto_save_sessions_loop(), loop=main_loop)
        asyncio.ensure_future(health_check_loop(), loop=main_loop)
        
        # تشغيل الـ Loop
        logger.info("🔄 Event Loop الرئيسي قيد التشغيل...")
        main_loop.run_forever()
        
    except Exception as e:
        logger.error(f"❌ فشل تشغيل Main Loop: {e}")
        shutdown_event.set()

# ============================================================
# AUTO SAVE LOOP
# ============================================================
async def auto_save_sessions_loop():
    """حفظ تلقائي للجلسات كل 5 دقائق"""
    logger.info("💾 نظام الحفظ التلقائي نشط (كل 5 دقائق)")
    while not shutdown_event.is_set():
        try:
            await asyncio.sleep(300)  # 5 دقائق
            if active_clients:
                await save_all_sessions()
                logger.debug(f"💾 تم حفظ {len(active_clients)} جلسة")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"❌ خطأ في الحفظ التلقائي: {e}")

# ============================================================
# HEALTH CHECK LOOP
# ============================================================
async def health_check_loop():
    """فحص صحة الجلسات كل 10 دقائق"""
    logger.info("🏥 نظام فحص الصحة نشط (كل 10 دقائق)")
    while not shutdown_event.is_set():
        try:
            await asyncio.sleep(600)  # 10 دقائق
            disconnected = []
            for phone, client in list(active_clients.items()):
                try:
                    if not client.is_connected():
                        disconnected.append(phone)
                except:
                    disconnected.append(phone)
            
            if disconnected:
                logger.warning(f"⚠️ جلسات منفصلة: {disconnected}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"❌ خطأ في فحص الصحة: {e}")

# ============================================================
# BOT MANAGER
# ============================================================
async def start_bot():
    """تشغيل بوت NinjaGram"""
    retry_count = 0
    max_retries = 5
    
    while retry_count < max_retries and not shutdown_event.is_set():
        try:
            logger.info(f"🤖 محاولة تشغيل البوت... (محاولة {retry_count + 1}/{max_retries})")
            
            # استيراد البوت
            import bot as ninjagram_bot
            
            await ninjagram_bot.bot.start(bot_token=BOT_TOKEN)
            me = await ninjagram_bot.bot.get_me()
            
            logger.info(f"""
╔══════════════════════════════════════╗
║   🤖 NinjaGram Pro Max Ultra v10    ║
║   ✅ البوت شغال: @{me.username}     ║
║   🆔 ID: {me.id}                    ║
║   👤 {me.first_name}                ║
╚══════════════════════════════════════╝
            """)
            
            # إشعار المطور
            await notify_dev(f"""
✅ **NinjaGram Bot Started**
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🤖 @{me.username}
📊 Active Sessions: {len(active_clients)}
🌐 Server: http://{HOST}:{PORT}
            """)
            
            # إعادة تعيين عداد المحاولات
            retry_count = 0
            
            # تشغيل البوت
            await ninjagram_bot.bot.run_until_disconnected()
            
        except Exception as e:
            retry_count += 1
            logger.error(f"❌ فشل تشغيل البوت (محاولة {retry_count}): {e}")
            
            if retry_count < max_retries:
                wait_time = min(retry_count * 10, 60)  # تصاعدي: 10, 20, 30, 40, 50
                logger.info(f"⏳ انتظار {wait_time} ثانية قبل إعادة المحاولة...")
                await asyncio.sleep(wait_time)
            else:
                logger.critical("💀 فشل تشغيل البوت بعد 5 محاولات")
                shutdown_event.set()
                break

# ============================================================
# GRACEFUL SHUTDOWN
# ============================================================
async def shutdown():
    """إيقاف آمن للنظام"""
    logger.info("🛑 جاري إيقاف النظام...")
    shutdown_event.set()
    
    # حفظ الجلسات
    try:
        await save_all_sessions()
        logger.info("💾 تم حفظ جميع الجلسات")
    except Exception as e:
        logger.error(f"❌ فشل حفظ الجلسات: {e}")
    
    # إيقاف البوت
    try:
        import bot as ninjagram_bot
        if ninjagram_bot.bot.is_connected():
            await ninjagram_bot.bot.disconnect()
            logger.info("🤖 تم إيقاف البوت")
    except:
        pass
    
    # إيقاف Loop
    try:
        main_loop.stop()
        logger.info("🔄 تم إيقاف Event Loop")
    except:
        pass
    
    logger.info("👋 وداعاً!")

def signal_handler(signum, frame):
    """معالج إشارات النظام"""
    logger.info(f"📡 استقبلت إشارة: {signum}")
    shutdown_event.set()
    
    # تشغيل shutdown في الـ main loop
    if main_loop.is_running():
        asyncio.run_coroutine_threadsafe(shutdown(), main_loop)

# ============================================================
# MAIN ENTRY POINT
# ============================================================
if __name__ == '__main__':
    logger.info("""
╔══════════════════════════════════════════╗
║   🧨 NinjaGram Pro Max Ultra v10        ║
║   🚀 Starting System...                 ║
╚══════════════════════════════════════════╝
    """)
    
    # تسجيل معالج الإشارات
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # تشغيل Main Loop في Thread منفصل
    loop_thread = threading.Thread(
        target=start_main_loop,
        name="MainEventLoop",
        daemon=True
    )
    loop_thread.start()
    logger.info("🔄 Main Event Loop Thread Started")
    
    # انتظار تهيئة الـ Loop
    time.sleep(1)
    
    # جدولة تشغيل البوت في الـ Main Loop
    if main_loop.is_running():
        bot_task = asyncio.run_coroutine_threadsafe(start_bot(), main_loop)
        logger.info("🤖 Bot Task Scheduled")
    else:
        logger.critical("❌ Main Loop غير جاهز!")
        sys.exit(1)
    
    # ============ تشغيل Web Server ============
    try:
        logger.info(f"""
╔══════════════════════════════════════╗
║   🌐 Web Server Starting            ║
║   📍 http://{HOST}:{PORT}           ║
║   🔧 Debug: {DEBUG}                 ║
╚══════════════════════════════════════╝
        """)
        
        # تشغيل Flask في الـ Main Thread
        app.run(
            host=HOST,
            port=PORT,
            debug=DEBUG,
            use_reloader=False,
            threaded=True
        )
        
    except KeyboardInterrupt:
        logger.info("⌨️ Keyboard Interrupt")
    except Exception as e:
        logger.error(f"❌ Server Error: {e}")
    finally:
        # تنظيف عند الخروج
        if not shutdown_event.is_set():
            shutdown_event.set()
            if main_loop.is_running():
                try:
                    future = asyncio.run_coroutine_threadsafe(shutdown(), main_loop)
                    future.result(timeout=10)
                except:
                    pass
        
        logger.info("👋 System Shutdown Complete")
        sys.exit(0)
