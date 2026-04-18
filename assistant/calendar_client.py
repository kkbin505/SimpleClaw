import logging
from googleapiclient.discovery import build
from google_auth import get_credentials
from config import CALENDAR_ID, TIMEZONE
from datetime import datetime, timedelta, timezone as dt_timezone

logger = logging.getLogger(__name__)


class CalendarClient:
    def __init__(self):
        self.service = build("calendar", "v3", credentials=get_credentials())

    def list_events(self, days: int = 7, max_results: int = 15) -> list:
        from zoneinfo import ZoneInfo
        from datetime import datetime, timedelta

        tz = ZoneInfo(TIMEZONE)
        now = datetime.now(tz)
        time_max = now + timedelta(days=days)

        results = self.service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=now.isoformat(),
            timeMax=time_max.isoformat(),
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = results.get("items", [])
        formatted = []

        for e in events:
            all_day = "dateTime" not in e["start"]
            start_str = e["start"].get("dateTime") or e["start"].get("date")
            end_str   = e["end"].get("dateTime")   or e["end"].get("date")

            # 计算距现在多少小时（帮助 GPT 判断紧迫性）
            hours_until = None
            if not all_day and start_str:
                try:
                    start_dt = datetime.fromisoformat(start_str).astimezone(tz)
                    hours_until = round((start_dt - now).total_seconds() / 3600, 1)
                except Exception:
                    pass

            formatted.append({
                "id":          e["id"],
                "title":       e.get("summary", "（无标题）"),
                "start":       start_str,
                "end":         end_str,
                "location":    e.get("location", ""),
                "description": e.get("description", ""),
                "all_day":     all_day,
                "hours_until": hours_until,   # GPT 用这个判断紧迫性
            })

        return formatted

    def delete_event(self, event_id: str):
        """删除日程"""
        self.service.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
        logger.info(f"Event {event_id} deleted.")

    def is_duplicate(self, title: str, start_dt: str) -> bool:
        """检查指定时间点是否已存在同名任务"""
        # start_dt 格式通常是 2024-04-15T14:00:00
        # 我们查询该时间点前后 1 分钟内的事件
        # 确保 timeMin 是合法的 RFC 3339 格式
        # 如果已经有时区信息（Z 或 +/-），则不重复添加
        time_min = start_dt
        if "Z" not in start_dt and "+" not in start_dt and ("-" not in start_dt[10:]):
            time_min += "Z"

        events_result = self.service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=time_min,
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        for event in events:
            if event.get('summary') == title:
                # 如果标题一样，且开始时间也几乎一样，判定为重复
                # 注意：Google 返回的时间格式可能带时区，这里做简单匹配，也可进一步解析
                exist_start = event['start'].get('dateTime', event['start'].get('date'))
                if exist_start.startswith(start_dt[:16]): # 匹配到分钟即可
                    return True
        return False

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

        # 强制清理逻辑：如果使用的是默认加州时区，且 AI 返回的时间字符串里带有偏移量（如 +08:00），
        # 则强制移除偏移量，确保 Google Calendar 以 timeZone 参数为准。
        if timezone == TIMEZONE:
            for key in ["start", "end"]:
                dt_str = event_body[key]["dateTime"]
                if "+" in dt_str:
                    event_body[key]["dateTime"] = dt_str.split("+")[0]
                elif dt_str.endswith("Z"):
                    event_body[key]["dateTime"] = dt_str[:-1]

        result = self.service.events().insert(
            calendarId=CALENDAR_ID, body=event_body
        ).execute()

        link = result.get("htmlLink", "")
        logger.info(f"Calendar event created: {link}")
        return link

    def get_upcoming_events(self, days=7) -> list:
        """获取未来几天的日程，用于 AI 去重和冲突检测"""
        from datetime import datetime, timedelta, timezone as dt_timezone
        
        # 使用 UTC 时间
        now = datetime.now(dt_timezone.utc).isoformat()
        time_max = (datetime.now(dt_timezone.utc) + timedelta(days=days)).isoformat()

        logger.info(f"Fetching upcoming events from {now} to {time_max}...")
        
        events_result = self.service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=now,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime"
        ).execute()
        
        events = events_result.get("items", [])
        
        # 简化数据结构以节省 Token
        simplified_events = []
        for event in events:
            simplified_events.append({
                "summary": event.get("summary", "无标题"),
                "start": event.get("start", {}).get("dateTime") or event.get("start", {}).get("date"),
                "end": event.get("end", {}).get("dateTime") or event.get("end", {}).get("date"),
            })
            
        return simplified_events
