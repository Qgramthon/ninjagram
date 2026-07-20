import discord
from discord.ext import commands
import os
import asyncio
import logging

# ====== إعدادات ======
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DiscordBot")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix=".",
    self_bot=True,
    help_command=None,
    intents=intents
)

# ====== أوامر البوت ======

@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (Self-Bot)")
    logger.info(f"Connected to {len(bot.guilds)} guilds")

@bot.command(name="بنغ")
async def ping(ctx):
    """اختبار سرعة البوت"""
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! `{latency}ms`")

@bot.command(name="وقتي")
async def time_cmd(ctx):
    """عرض الوقت الحالي"""
    from datetime import datetime
    now = datetime.now().strftime("%H:%M:%S")
    await ctx.send(f"🕐 {now}")

@bot.command(name="حالة")
async def status_cmd(ctx):
    """عرض حالة البوت"""
    embed = discord.Embed(
        title="📊 Bot Status",
        color=0x00ff00
    )
    embed.add_field(name="User", value=str(bot.user), inline=True)
    embed.add_field(name="Servers", value=str(len(bot.guilds)), inline=True)
    embed.add_field(name="Ping", value=f"{round(bot.latency * 1000)}ms", inline=True)
    await ctx.send(embed=embed)

@bot.command(name="اوامر")
async def help_cmd(ctx):
    """عرض قائمة الأوامر"""
    cmds = """╭━━━━[ *Discord Self-Bot* ]━━━━╮
│ .بنغ - Ping
│ .وقتي - Time
│ .حالة - Status
│ .اوامر - Commands
│ .مسح <عدد> - Delete messages
│ .ايقاف - Stop
╰━━━━━━━━━━━━━━━━━━╯"""
    await ctx.send(cmds)

@bot.command(name="مسح")
async def purge(ctx, amount: int = 10):
    """حذف رسائل البوت (Self-Bot)"""
    if amount > 100:
        amount = 100
    deleted = 0
    async for msg in ctx.channel.history(limit=amount + 1):
        if msg.author == bot.user:
            await msg.delete()
            deleted += 1
            await asyncio.sleep(0.5)
    await ctx.send(f"✅ Deleted {deleted} messages", delete_after=3)

@bot.command(name="ايقاف")
async def stop(ctx):
    """إيقاف البوت"""
    await ctx.send("🛑 Bot is stopping...")
    await bot.close()

# ====== تشغيل البوت ======
if __name__ == "__main__":
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        logger.error("DISCORD_TOKEN not found in environment variables")
        exit(1)
    
    logger.info("Starting Discord Self-Bot...")
    bot.run(TOKEN)
