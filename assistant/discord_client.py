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

ALLOWED_USERS = os.environ.get("ALLOWED_USER_IDS", "").split(",")

class AssistantBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.calendar = CalendarClient()
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
        if str(message.author.id) not in ALLOWED_USERS:
            logger.info(f"忽略未授权用户: {message.author} (ID: {message.author.id})")
            return

        logger.info(f"收到授权消息 - 来自 {message.author}: {message.content}")

        # 如果是私聊，或者被 @ 提到了，我们就处理
        is_dm = isinstance(message.channel, discord.DMChannel)
        is_mention = self.user.mentioned_in(message)
        
        if is_dm or is_mention:
            logger.info("满足触发条件，正在分析...")
            await self.process_assistant_task(message)
        
        await self.process_commands(message)

    async def process_assistant_task(self, message):
        async with message.channel.typing():
            now = datetime.now(ZoneInfo(TIMEZONE))
            current_dt = now.strftime("%Y-%m-%d (%A) %H:%M %Z")
            
            mock_email = {
                "sender": message.author.name,
                "subject": "Discord Message",
                "body": message.content,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            try:
                existing_events = self.calendar.get_upcoming_events(days=7)
                result = parse_email_for_events(mock_email, current_dt, existing_events=existing_events)
                
                # 记录详细解析结果到本地日志
                logger.info(f"AI 解析结果 (用户 ID: {message.author.id}): {result}")

                if result.get("has_event"):
                    for event_data in result["events"]:
                        if self.calendar.is_duplicate(event_data['title'], event_data['start_datetime']):
                            await message.reply(f"📅 发现了重复任务：**{event_data['title']}**，已跳过。")
                            continue
                        
                        link = self.calendar.create_event(event_data)
                        await message.reply(f"✅ 已为你安排日程：\n**{event_data['title']}**\n⏰ {event_data['start_datetime']}\n🔗 [查看日历]({link})")
                else:
                    if result.get('is_casual'):
                        # 闲聊 → 用 AI 生成的自然回复
                        reply_text = result.get('reply', '嗯，收到了。')
                        logger.info(f"闲聊回复: {reply_text}")
                        await message.reply(reply_text)
                    else:
                        reason = result.get('reason', '')
                        logger.info(f"好的。原因: {reason}")
                        if reason:
                            # 冲突或重复 → 告知用户
                            await message.reply(f"⚠️ 无法创建日程：{reason}")
            except Exception as e:
                logger.error(f"Discord 任务处理出错: {e}", exc_info=True)
                await message.reply("抱歉，处理该任务时发生错误，详情请查看本地日志。")

def run_discord_bot(token):
    bot = AssistantBot()
    bot.run(token)
