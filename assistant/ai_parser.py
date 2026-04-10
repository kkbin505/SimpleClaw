import json
import logging
from openai import OpenAI
from config import OPENAI_API_KEY, MODEL, TIMEZONE

logger = logging.getLogger(__name__)
client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = f"""你是一个智能日程助理。用户会转发邮件或消息，你需要分析内容并提取日程信息。

请始终以 JSON 格式返回，格式如下：

如果包含日程信息：
{{
    "has_event": true,
    "events": [
        {{
            "title": "事件标题",
            "start_datetime": "ISO 8601格式，例如：2024-04-15T14:00:00",
            "end_datetime": "ISO 8601格式",
            "location": "地点（没有则留空）",
            "description": "补充描述（可选）",
            "timezone": "时区，默认 {TIMEZONE}",
            "reminders": [1440, 30]
        }}
    ]
}}

如果不包含日程信息：
{{
    "has_event": false,
    "reason": "原因说明"
}}

规则：
- 支持一封邮件中提取多个事件（events 是数组）
- 如果没有明确结束时间，默认开始时间后 1 小时
- reminders 是提前多少分钟提醒的整数列表（1440=1天前，30=30分钟前）
- 相对时间（明天、下周一）请结合当前时间推算
- 时区优先根据邮件内容判断，其次使用默认时区
"""


def parse_email_for_events(email: dict, current_datetime: str) -> dict:
    user_message = f"""当前时间：{current_datetime}

---
发件人：{email.get('sender', '')}
主题：{email.get('subject', '')}
发送时间：{email.get('date', '')}

正文：
{email.get('body', '（无正文）')}
---

请分析以上内容，提取所有日程信息。"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    content = response.choices[0].message.content
    logger.debug(f"AI response: {content}")
    return json.loads(content)
