import asyncio
import discord
import logging
from discord.ext import commands
from ai_parser import parse_email_for_events
from calendar_client import CalendarClient
from config import TIMEZONE, ALLOWED_USER_IDS
from datetime import datetime
from zoneinfo import ZoneInfo
import os

logger = logging.getLogger(__name__)

class AssistantBot(commands.Bot):
    def __init__(self, chatbot=None):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        # 允许传入外部的chatbot实例，否则创建新的
        if chatbot:
            self.chatbot = chatbot
        else:
            from chatbot import Chatbot
            self.chatbot = Chatbot()
        self.ready_event = asyncio.Event()

    async def on_ready(self):
        logger.info(f"Discord Bot logged in as {self.user} (ID: {self.user.id})")
        self.ready_event.set()

    async def send_dm_to_user(self, discord_id, content):
        """发送私聊消息给指定用户"""
        try:
            user = await self.fetch_user(int(discord_id))
            if user:
                await user.send(content)
                logger.info(f"Successfully sent DM to {user.name} (ID: {discord_id})")
            else:
                logger.error(f"Could not find user with ID: {discord_id}")
        except Exception as e:
            logger.error(f"Failed to send DM to {discord_id}: {e}")

    async def on_message(self, message):
        # 不要理会机器人自己的消息
        if message.author == self.user:
            return
            
        # 权限校验
        if message.author.id not in ALLOWED_USER_IDS:
            logger.info(f"忽略未授权用户: {message.author} (ID: {message.author.id})")
            return

        logger.info(f"收到授权消息 - 来自 {message.author}: {message.content}")

        # 如果是私聊，或者被 @ 提到了，我们就处理
        is_dm = isinstance(message.channel, discord.DMChannel)
        is_mention = self.user.mentioned_in(message)
        
        if is_dm or is_mention:
            await self.process_assistant_task(message)
        
        await self.process_commands(message)

    async def process_assistant_task(self, message):
        async with message.channel.typing():
            try:
                # 使用 Chatbot 处理对话（包含日程查询、创建、日常闲聊等）
                reply = self.chatbot.chat(str(message.author.id), message.content)
                await message.reply(reply)
            except Exception as e:
                logger.error(f"Discord 任务处理出错: {e}", exc_info=True)
                await message.reply("抱歉，我现在处理这个请求时遇到了一些困难，请稍后再试。")

def run_discord_bot(token):
    bot = AssistantBot()
    bot.run(token)
