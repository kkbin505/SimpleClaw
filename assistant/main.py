import asyncio
import logging
from assistant import PersonalAssistant
from config import POLL_INTERVAL_SECONDS, DISCORD_TOKEN
from discord_client import AssistantBot

logger = logging.getLogger(__name__)

async def gmail_polling_task(assistant):
    """异步执行 Gmail 轮询任务"""
    logger.info(f"Gmail Assistant started. Polling every {POLL_INTERVAL_SECONDS}s...")
    while True:
        try:
            # run_once 内部是阻塞的，但在单独的任务中运行
            assistant.run_once()
        except Exception as e:
            logger.error(f"Gmail Polling Error: {e}")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)

async def main_async():
    assistant = PersonalAssistant()
    
    # 定义任务列表
    tasks = [
        asyncio.create_task(gmail_polling_task(assistant))
    ]

    # 如果配置了 Discord Token，则启动 Discord Bot
    if DISCORD_TOKEN:
        bot = AssistantBot()
        logger.info("Starting Discord Bot...")
        # bot.start 是异步的
        tasks.append(asyncio.create_task(bot.start(DISCORD_TOKEN)))
    else:
        logger.warning("DISCORD_TOKEN not found in .env, running Gmail assistant only.")

    # 并行等待所有任务（理论上由于 while True 它们永远不会结束）
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
