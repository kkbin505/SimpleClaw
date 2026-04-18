import asyncio
import logging
from assistant import PersonalAssistant
from config import POLL_INTERVAL_SECONDS, DISCORD_TOKEN
from discord_client import AssistantBot
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

async def schedule_reminder_task(assistant):
    """异步执行日程提醒调度任务"""
    if assistant.discord_bot:
        logger.info("Waiting for Discord Bot to be ready for Scheduler...")
        await assistant.discord_bot.ready_event.wait()

    reminder = ScheduleReminder(
        calendar_client=assistant.calendar,
        discord_bot=assistant.discord_bot,
    )
    await reminder.run()

async def main_async():
    # 先初始化 Bot（如果需要的话，也可以先初始化 Assistant）
    bot = None
    if DISCORD_TOKEN:
        bot = AssistantBot()
    
    assistant = PersonalAssistant(discord_bot=bot)
    
    # 定义任务列表
    tasks = [
        asyncio.create_task(gmail_polling_task(assistant)),
    ]

    # 如果配置了 Discord Bot，启动提醒调度器和 Bot
    if bot:
        logger.info("Starting Discord Bot...")
        tasks.append(asyncio.create_task(bot.start(DISCORD_TOKEN)))
        tasks.append(asyncio.create_task(schedule_reminder_task(assistant)))
    else:
        logger.warning("DISCORD_TOKEN not found in .env, running Gmail assistant only.")

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
