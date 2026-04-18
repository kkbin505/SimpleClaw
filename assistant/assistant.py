import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from gmail_client import GmailClient
from calendar_client import CalendarClient
from ai_parser import parse_email_for_events, parse_minutes_for_tasks
from docs_client import GoogleDocsClient
from config import TIMEZONE, LOG_FILE, DOC_TITLE_KEYWORDS, USER_MAP
import json
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PersonalAssistant:
    def __init__(self, discord_bot=None):
        self.gmail = GmailClient()
        self.calendar = CalendarClient()
        self.docs = GoogleDocsClient()
        self.discord_bot = discord_bot
        self.processed_docs_file = "credentials/processed_docs.json"
        logger.info("Personal Assistant initialized.")

    async def run_once(self):
        """处理一轮未读邮件和共享文档"""
        await self.process_emails()
        await self.process_shared_docs()

    async def process_emails(self):
        """处理一轮未读邮件"""
        logger.info("Checking for new emails...")
        # 注意：GmailClient 的方法目前是同步的，但在异步任务中运行。
        # 如果需要完全非阻塞，可以考虑将其也异步化。
        messages = self.gmail.get_unread_messages()

        if not messages:
            logger.info("No new messages.")
            return

        logger.info(f"Found {len(messages)} new message(s).")
        for msg in messages:
            try:
                await self._process(msg)
            except Exception as e:
                logger.error(f"Error processing [{msg['subject']}]: {e}", exc_info=True)

    async def process_shared_docs(self):
        """处理共享的会议纪要文档"""
        logger.info("Checking for shared Google Docs...")
        
        # 加载已处理的文档列表
        processed_ids = []
        if os.path.exists(self.processed_docs_file):
            try:
                with open(self.processed_docs_file, "r") as f:
                    processed_ids = json.load(f)
            except Exception:
                processed_ids = []

        shared_docs = self.docs.list_shared_docs(keywords=DOC_TITLE_KEYWORDS)
        
        new_docs = [d for d in shared_docs if d["id"] not in processed_ids]
        
        if not new_docs:
            logger.info("No new shared documents to process.")
            return

        logger.info(f"Found {len(new_docs)} new shared document(s).")
        
        # 获取当前参考时间
        now = datetime.now(ZoneInfo(TIMEZONE))
        current_dt = now.strftime("%Y-%m-%d (%A) %H:%M %Z")

        for doc in new_docs:
            try:
                logger.info(f"Processing document: \"{doc['name']}\" (ID: {doc['id']})")
                content = self.docs.get_doc_text(doc["id"])
                
                if not content.strip():
                    logger.warning(f"  ⚠️ Document \"{doc['name']}\" is empty.")
                    processed_ids.append(doc["id"])
                    continue

                existing_events = self.calendar.get_upcoming_events(days=7)
                result = parse_minutes_for_tasks(content, current_dt, existing_events=existing_events)
                
                if result.get("has_event"):
                    events = result.get("events", [])
                    for event_data in events:
                        if self.calendar.is_duplicate(event_data['title'], event_data['start_datetime']):
                            logger.info(f"  ⏭️  Duplicate ignored: [{event_data['title']}]")
                            continue
                        
                        link = self.calendar.create_event(event_data)
                        logger.info(f"  ✅ Created from Doc: [{event_data['title']}] → {link}")

                        # Discord 推送
                        if self.discord_bot:
                            assignee = event_data.get("assignee")
                            discord_id = USER_MAP.get(assignee)
                            if discord_id:
                                msg = f"🔔 **温馨提醒**：明天的纪要里有一个你的任务：\n**{event_data['title']}**\n⏰ {event_data['start_datetime']}\n🔗 [查看日历]({link})"
                                await self.discord_bot.send_dm_to_user(discord_id, msg)
                else:
                    logger.info(f"  ⏭️  No tasks found: {result.get('debug_reason', '')}")
                
                # 标记为已处理
                processed_ids.append(doc["id"])
                
            except Exception as e:
                logger.error(f"Error processing document [{doc['name']}]: {e}")
                # 注意：这里不向 processed_ids 添加 ID，下轮轮询会重试

        # 保存更新后的已处理列表
        os.makedirs(os.path.dirname(self.processed_docs_file), exist_ok=True)
        with open(self.processed_docs_file, "w") as f:
            json.dump(processed_ids, f)

    async def _process(self, msg: dict):
        logger.info(f"Processing: \"{msg['subject']}\" from {msg['sender']}")

        # 使用 zoneinfo 获取配置时区的当前时间，确保 AI 推算相对日期（如"明天"）时准确
        now = datetime.now(ZoneInfo(TIMEZONE))
        current_dt = now.strftime("%Y-%m-%d (%A) %H:%M %Z")

        # 获取现有日程上下文（未来 7 天），用于 AI 去重和冲突检测
        existing_events = self.calendar.get_upcoming_events(days=7)

        result = parse_email_for_events(msg, current_dt, existing_events=existing_events)
        logger.debug(f"AI Parsing Result for \"{msg['subject']}\": {result}")

        if result.get("has_event"):
            events = result.get("events", [])
            for event_data in events:
                if self.calendar.is_duplicate(event_data['title'], event_data['start_datetime']):
                    logger.info(f"  ⏭️  Duplicate ignored: [{event_data['title']}] at {event_data['start_datetime']}")
                    continue

                link = self.calendar.create_event(event_data)
                logger.info(f"  ✅ Created: [{event_data['title']}] @ {event_data['start_datetime']} → {link}")
        else:
            logger.info(f"  ⏭️  No event: {result.get('reason', '')}")

        # 标记已处理
        self.gmail.mark_as_read(msg["id"])
        self.gmail.add_label(msg["id"], "AI_PROCESSED")
