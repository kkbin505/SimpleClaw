import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from openai import OpenAI
from config import OPENAI_API_KEY, MODEL, TIMEZONE
from ai_parser import SYSTEM_PROMPT, WEEKDAY_ZH
from calendar_client import CalendarClient

logger = logging.getLogger(__name__)
client = OpenAI(api_key=OPENAI_API_KEY)

# 定义工具供 GPT 调用
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_upcoming_events",
            "description": (
                "查询 Google Calendar 中即将到来的事件。"
                "当用户询问近期安排、这周有什么事、最近有啥、今明两天的日程等时调用。"
                "返回结果包含事件标题、时间、地点、备注及距现在的小时数，"
                "请据此判断优先级并以秘书风格整理汇报。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "向后查询多少天，默认 7，用户说'今明两天'传 2，'这周'传到本周末的天数"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "最多返回多少条，默认 15"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_event",
            "description": "创建一个新的日历日程",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "日程标题"},
                    "start_datetime": {"type": "string", "description": "开始时间 (ISO 8601 格式)"},
                    "end_datetime": {"type": "string", "description": "结束时间 (ISO 8601 格式)"},
                    "location": {"type": "string", "description": "地点"},
                    "description": {"type": "string", "description": "描述"},
                    "reminders": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "提前多少分钟提醒"
                    }
                },
                "required": ["title", "start_datetime", "end_datetime"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_event",
            "description": "删除指定的日历日程",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "日程的 ID"}
                },
                "required": ["event_id"]
            }
        }
    }
]

class ConversationManager:
    def __init__(self, max_history=20):
        self.max_history = max_history
        self.histories = {} # user_id -> list of messages

    def add_message(self, user_id, role, content):
        if user_id not in self.histories:
            self.histories[user_id] = []
        self.histories[user_id].append({"role": role, "content": content})
        # 保持记录在限额内
        if len(self.histories[user_id]) > self.max_history:
            self.histories[user_id] = self.histories[user_id][-self.max_history:]

    def get_history(self, user_id):
        return self.histories.get(user_id, [])

class ToolExecutor:
    def __init__(self):
        self.calendar = CalendarClient()

    def execute(self, name, args):
        if name == "list_upcoming_events":
            days = args.get("days", 7)
            max_results = args.get("max_results", 15)
            return self.calendar.list_events(days, max_results)
        elif name == "create_event":
            return self.calendar.create_event(args)
        elif name == "delete_event":
            return self.calendar.delete_event(args.get("event_id"))
        else:
            return {"error": f"Tool {name} not found"}

class Chatbot:
    def __init__(self):
        self.conversation = ConversationManager(max_history=10)
        self.executor = ToolExecutor()

    def _build_time_context(self) -> str:
        """生成带中文星期的当前时间，帮助 GPT 处理相对时间"""
        now = datetime.now(ZoneInfo(TIMEZONE))
        weekday = WEEKDAY_ZH[now.weekday()]
        time_of_day = (
            "早上" if 5 <= now.hour < 12
            else "下午" if 12 <= now.hour < 18
            else "晚上" if 18 <= now.hour < 23
            else "深夜"
        )
        return (
            f"当前时间：{now.strftime('%Y年%m月%d日')} {weekday} "
            f"{now.strftime('%H:%M')}（{time_of_day}）"
        )

    def chat(self, user_id: str, user_message: str) -> str:
        time_context = self._build_time_context()
        self.conversation.add_message(user_id, "user", user_message)

        messages = [
            {
                "role": "system",
                "content": f"{SYSTEM_PROMPT}\n\n{time_context}"
            },
            *self.conversation.get_history(user_id),
        ]

        for _ in range(5):
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.75,
            )

            msg = response.choices[0].message
            finish_reason = response.choices[0].finish_reason

            if finish_reason == "stop" or not msg.tool_calls:
                reply = msg.content or "（工作已完成）"
                self.conversation.add_message(user_id, "assistant", reply)
                return reply

            # 处理工具调用
            messages.append(msg) # 直接把消息对象添加进去供后续轮次参考

            for tool_call in msg.tool_calls:
                tool_name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                logger.info(f"Tool: {tool_name} | Args: {args}")
                result = self.executor.execute(tool_name, args)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

        return "抱歉，处理时出了点问题，请稍后重试。"
