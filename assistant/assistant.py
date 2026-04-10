import logging
from datetime import datetime
from gmail_client import GmailClient
from calendar_client import CalendarClient
from ai_parser import parse_email_for_events
from config import TIMEZONE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class PersonalAssistant:
    def __init__(self):
        self.gmail = GmailClient()
        self.calendar = CalendarClient()
        logger.info("Personal Assistant initialized.")

    def run_once(self):
        """处理一轮未读邮件"""
        logger.info("Checking for new emails...")
        messages = self.gmail.get_unread_messages()

        if not messages:
            logger.info("No new messages.")
            return

        logger.info(f"Found {len(messages)} new message(s).")
        for msg in messages:
            try:
                self._process(msg)
            except Exception as e:
                logger.error(f"Error processing [{msg['subject']}]: {e}", exc_info=True)

    def _process(self, msg: dict):
        logger.info(f"Processing: \"{msg['subject']}\" from {msg['sender']}")

        current_dt = datetime.now().strftime(f"%Y-%m-%d %H:%M (%Z, {TIMEZONE})")
        result = parse_email_for_events(msg, current_dt)

        if result.get("has_event"):
            events = result.get("events", [])
            for event_data in events:
                link = self.calendar.create_event(event_data)
                logger.info(f"  ✅ Created: [{event_data['title']}] @ {event_data['start_datetime']} → {link}")
        else:
            logger.info(f"  ⏭️  No event: {result.get('reason', '')}")

        # 标记已处理
        self.gmail.mark_as_read(msg["id"])
        self.gmail.add_label(msg["id"], "AI_PROCESSED")
