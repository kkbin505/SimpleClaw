import asyncio
import logging
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters
from config import TIMEZONE, TELEGRAM_ALLOWED_USER_IDS
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


class AssistantTelegramBot:
    def __init__(self, chatbot=None):
        # 允许传入外部的chatbot实例，否则创建新的
        if chatbot:
            self.chatbot = chatbot
        else:
            from chatbot import Chatbot
            self.chatbot = Chatbot()
        self.ready_event = asyncio.Event()
        self.application = None

    async def initialize(self, token: str):
        """初始化 Telegram Bot Application"""
        self.application = Application.builder().token(token).build()
        
        # 注册消息处理器
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.on_message)
        )
        
        # 注册启动和关闭处理
        self.application.post_init = self._post_init
        
        logger.info("Telegram Bot initialized")

    async def _post_init(self, application):
        """Bot 启动后的初始化"""
        bot = application.bot
        bot_user = await bot.get_me()
        logger.info(f"Telegram Bot logged in as @{bot_user.username} (ID: {bot_user.id})")
        self.ready_event.set()

    async def start(self):
        """启动 Telegram Bot (轮询模式)"""
        if not self.application:
            raise RuntimeError("Bot not initialized. Call initialize() first.")
        
        logger.info("Starting Telegram Bot polling...")
        try:
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
        except Exception as e:
            logger.error(f"Failed to start Telegram Bot: {e}", exc_info=True)
            raise

    async def stop(self):
        """停止 Telegram Bot"""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("Telegram Bot stopped")

    async def on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理来自用户的消息"""
        message = update.message
        if not message or not message.text:
            return

        # 权限校验
        user_id = message.from_user.id
        if user_id not in TELEGRAM_ALLOWED_USER_IDS:
            logger.info(f"忽略未授权用户: {message.from_user.username or user_id} (ID: {user_id})")
            return

        logger.info(
            f"收到授权消息 - 来自 {message.from_user.username or user_id} "
            f"(ID: {user_id}): {message.text}"
        )

        # 显示"正在输入"状态
        try:
            await context.bot.send_chat_action(chat_id=message.chat_id, action="typing")
        except Exception as e:
            logger.warning(f"Failed to send typing action: {e}")

        try:
            # 使用 Chatbot 处理对话（包含日程查询、创建、日常闲聊等）
            reply = self.chatbot.chat(str(user_id), message.text)
            
            # 处理消息长度限制（Telegram 单条消息最大 4096 字符）
            await self._send_message(message.chat_id, reply, context)
        except Exception as e:
            logger.error(f"Telegram 任务处理出错: {e}", exc_info=True)
            await message.reply_text("抱歉，我现在处理这个请求时遇到了一些困难，请稍后再试。")

    async def _send_message(self, chat_id: int, text: str, context: ContextTypes.DEFAULT_TYPE):
        """发送消息，自动分段处理长消息"""
        max_length = 4096
        if len(text) <= max_length:
            await context.bot.send_message(chat_id=chat_id, text=text)
        else:
            # 分段发送
            for i in range(0, len(text), max_length):
                chunk = text[i : i + max_length]
                await context.bot.send_message(chat_id=chat_id, text=chunk)
                await asyncio.sleep(0.1)  # 避免限流

    async def send_message_to_user(self, telegram_id: int, content: str):
        """发送私聊消息给指定用户（用于定时提醒等）"""
        if not self.application:
            logger.error("Telegram Bot not initialized")
            return False

        try:
            bot = self.application.bot
            # 分段处理长消息
            max_length = 4096
            if len(content) <= max_length:
                await bot.send_message(chat_id=telegram_id, text=content)
            else:
                # 分段发送
                for i in range(0, len(content), max_length):
                    chunk = content[i : i + max_length]
                    await bot.send_message(chat_id=telegram_id, text=chunk)
                    await asyncio.sleep(0.1)
            
            logger.info(f"Successfully sent message to Telegram user (ID: {telegram_id})")
            return True
        except Exception as e:
            logger.error(f"Failed to send message to Telegram user {telegram_id}: {e}")
            return False
