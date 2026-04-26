import asyncio
import logging
from assistant import PersonalAssistant
from config import POLL_INTERVAL_SECONDS, DISCORD_TOKEN, TELEGRAM_TOKEN
from discord_client import AssistantBot
from telegram_client import AssistantTelegramBot
from scheduler import ScheduleReminder

logger = logging.getLogger(__name__)

async def gmail_polling_task(assistant):
    """异步执行 Gmail 轮询任务"""
    if assistant.discord_bot:
        logger.info("Waiting for Discord Bot to be ready...")
        await assistant.discord_bot.ready_event.wait()
    
    logger.info(f"Gmail Assistant started. Polling every {POLL_INTERVAL_SECONDS}s...")
    while True:
        try:
            await assistant.run_once()
        except Exception as e:
            logger.error(f"Gmail Polling Error: {e}")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)

async def schedule_reminder_task(assistant, discord_bot=None, telegram_bot=None):
    """异步执行日程提醒调度任务"""
    if discord_bot:
        logger.info("Waiting for Discord Bot to be ready for Scheduler...")
        await discord_bot.ready_event.wait()
    
    if telegram_bot:
        logger.info("Waiting for Telegram Bot to be ready for Scheduler...")
        await telegram_bot.ready_event.wait()

    reminder = ScheduleReminder(
        calendar_client=assistant.calendar,
        discord_bot=discord_bot,
        telegram_bot=telegram_bot,
    )
    await reminder.run()

async def main_async():
    # 先初始化 Bot（如果需要的话，也可以先初始化 Assistant）
    discord_bot = None
    if DISCORD_TOKEN:
        discord_bot = AssistantBot()
    
    telegram_bot = None
    if TELEGRAM_TOKEN:
        telegram_bot = AssistantTelegramBot()
        await telegram_bot.initialize(TELEGRAM_TOKEN)
    
    assistant = PersonalAssistant(discord_bot=discord_bot, telegram_bot=telegram_bot)
    
    # 定义任务列表
    tasks = [
        asyncio.create_task(gmail_polling_task(assistant)),
    ]

    # 如果配置了 Discord Bot，启动提醒调度器和 Bot
    if discord_bot:
        logger.info("Starting Discord Bot...")
        tasks.append(asyncio.create_task(discord_bot.start(DISCORD_TOKEN)))
        tasks.append(asyncio.create_task(schedule_reminder_task(assistant, discord_bot, telegram_bot)))
    elif telegram_bot:
        # 如果只有 Telegram Bot，也需要启动提醒调度器
        logger.info("Discord Bot not configured, starting Telegram-only scheduler...")
        tasks.append(asyncio.create_task(schedule_reminder_task(assistant, None, telegram_bot)))
    else:
        logger.warning("Neither DISCORD_TOKEN nor TELEGRAM_TOKEN found in .env, running Gmail assistant only.")

    # 如果配置了 Telegram Bot，启动它
    if telegram_bot:
        logger.info("Starting Telegram Bot...")
        tasks.append(asyncio.create_task(telegram_bot.start()))

    # 并行等待所有任务
    await asyncio.gather(*tasks)

def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user.")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)

if __name__ == "__main__":
    main()
