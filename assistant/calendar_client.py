import logging
from googleapiclient.discovery import build
from google_auth import get_credentials
from config import CALENDAR_ID, TIMEZONE

logger = logging.getLogger(__name__)


class CalendarClient:
    def __init__(self):
        self.service = build("calendar", "v3", credentials=get_credentials())

    def create_event(self, event_data: dict) -> str:
        """根据 AI 解析结果创建日历事件，返回事件链接"""
        timezone = event_data.get("timezone") or TIMEZONE

        # 构建提醒列表
        reminder_overrides = [
            {"method": "email", "minutes": 24 * 60},   # 提前 1 天邮件提醒
            {"method": "popup", "minutes": 30},          # 提前 30 分钟弹窗
        ]
        if event_data.get("reminders"):
            reminder_overrides = [
                {"method": "popup", "minutes": m}
                for m in event_data["reminders"]
            ]

        event_body = {
            "summary": event_data["title"],
            "location": event_data.get("location", ""),
            "description": event_data.get("description", ""),
            "start": {"dateTime": event_data["start_datetime"], "timeZone": timezone},
            "end":   {"dateTime": event_data["end_datetime"],   "timeZone": timezone},
            "reminders": {
                "useDefault": False,
                "overrides": reminder_overrides,
            },
        }

        result = self.service.events().insert(
            calendarId=CALENDAR_ID, body=event_body
        ).execute()

        link = result.get("htmlLink", "")
        logger.info(f"Calendar event created: {link}")
        return link
