import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from openai import OpenAI
from config import OPENAI_API_KEY, MODEL, TIMEZONE, DREAMING_ENABLED
from ai_parser import SYSTEM_PROMPT, WEEKDAY_ZH
from calendar_client import CalendarClient
from dreaming import DreamGenerator

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
    def __init__(self, dream_generator: DreamGenerator | None = None):
        self.conversation = ConversationManager(max_history=10)
        self.executor = ToolExecutor()
        self.dream_generator = dream_generator or (DreamGenerator() if DREAMING_ENABLED else None)

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

    def _extract_day_offset(self, user_message: str) -> int | None:
        """从用户原话中提取相对日期偏移。"""
        text = user_message or ""
        if "今天" in text or "今日" in text:
            return 0
        if "明天" in text or "明日" in text:
            return 1
        if "后天" in text:
            return 2
        return None

    def _shift_iso_to_date(self, iso_str: str, target_date) -> str:
        """保留原有时间部分，仅替换日期。"""
        dt = datetime.fromisoformat(iso_str)
        shifted = dt.replace(year=target_date.year, month=target_date.month, day=target_date.day)
        return shifted.isoformat()

    def _normalize_create_event_args(self, user_message: str, args: dict) -> dict:
        """根据用户显式日期词，校正 create_event 的日期，避免今天被漂移到明天。"""
        if not isinstance(args, dict):
            return args

        start_dt = args.get("start_datetime")
        end_dt = args.get("end_datetime")
        if not start_dt or not end_dt:
            return args

        day_offset = self._extract_day_offset(user_message)
        if day_offset is None:
            return args

        try:
            now_local = datetime.now(ZoneInfo(TIMEZONE))
            target_date = now_local.date().fromordinal(now_local.date().toordinal() + day_offset)
            fixed_args = dict(args)
            fixed_args["start_datetime"] = self._shift_iso_to_date(start_dt, target_date)
            fixed_args["end_datetime"] = self._shift_iso_to_date(end_dt, target_date)

            if (
                fixed_args["start_datetime"] != start_dt
                or fixed_args["end_datetime"] != end_dt
            ):
                logger.info(
                    "Adjusted create_event date by user intent: %s -> %s, %s -> %s",
                    start_dt,
                    fixed_args["start_datetime"],
                    end_dt,
                    fixed_args["end_datetime"],
                )

            return fixed_args
        except Exception as e:
            logger.warning(f"Failed to normalize create_event args: {e}")
            return args

    def chat(self, user_id: str, user_message: str) -> str:
        # 检查特殊命令
        if user_message.strip().lower() in ["/dream", "/梦", "梦"]:
            return self._handle_dream_command(user_id, "latest")
        elif user_message.strip().lower() in ["/dreams", "/梦历史", "梦历史"]:
            return self._handle_dream_command(user_id, "history")
        
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
                raw_reply = msg.content or "（工作已完成）"
                
                # 尝试解析 JSON 格式以提取对话内容
                final_reply = raw_reply
                try:
                    # 去掉可能存在的 markdown 代码块包裹
                    clean_content = raw_reply.strip()
                    if clean_content.startswith("```json"):
                        clean_content = clean_content.replace("```json", "", 1).rsplit("```", 1)[0].strip()
                    elif clean_content.startswith("```"):
                        clean_content = clean_content.replace("```", "", 1).rsplit("```", 1)[0].strip()
                    
                    data = json.loads(clean_content)
                    if isinstance(data, dict):
                        # 如果是闲聊，提取 reply；如果是无效日程，提取 reason
                        if "reply" in data:
                            final_reply = data["reply"]
                        elif "reason" in data:
                            final_reply = data["reason"]
                except (json.JSONDecodeError, Exception):
                    # 如果不是 JSON 或者解析失败，直接使用原始文本
                    final_reply = raw_reply

                self.conversation.add_message(user_id, "assistant", final_reply)
                
                # 追踪交互
                if self.dream_generator:
                    self.dream_generator.add_interaction(
                        user_id,
                        "chat",
                        f"User: {user_message[:100]}... | Assistant: {final_reply[:100]}..."
                    )
                
                return final_reply

            # 处理工具调用
            messages.append(msg) # 直接把消息对象添加进去供后续轮次参考

            for tool_call in msg.tool_calls:
                tool_name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                if tool_name == "create_event":
                    args = self._normalize_create_event_args(user_message, args)

                logger.info(f"Tool: {tool_name} | Args: {args}")
                result = self.executor.execute(tool_name, args)

                # 追踪工具调用交互
                if self.dream_generator and tool_name in ["list_upcoming_events", "create_event", "delete_event"]:
                    self.dream_generator.add_interaction(
                        user_id,
                        f"calendar_{tool_name}",
                        json.dumps(args, ensure_ascii=False)[:100]
                    )

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

        return "抱歉，处理时出了点问题，请稍后重试。"

    def _handle_dream_command(self, user_id: str, command_type: str) -> str:
        """处理梦相关命令"""
        if not self.dream_generator:
            return "抱歉，梦幻思考功能未启用。"
        
        if command_type == "latest":
            dream = self.dream_generator.get_latest_dream(user_id)
            if not dream:
                return "你还没有梦。多和我交互，我就会开始思考你的模式并生成梦。"
            return f"💭 **你最近的梦**\n\n{dream}"
        
        elif command_type == "history":
            history = self.dream_generator.get_dream_history(user_id, limit=5)
            if not history:
                return "你还没有梦的历史。多和我交互，我就会开始思考你的模式并生成梦。"
            
            result = "📚 **你的梦幻历史**\n\n"
            for i, dream_record in enumerate(history, 1):
                ts = dream_record["timestamp"]
                result += f"**梦 #{i}** ({ts})\n{dream_record['content']}\n\n"
            return result
        
        return "未知的梦命令。"
