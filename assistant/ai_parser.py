import json
import logging
from openai import OpenAI
from config import OPENAI_API_KEY, MODEL, TIMEZONE, ASSISTANT_NAME

logger = logging.getLogger(__name__)
client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = f"""你的名字叫{ASSISTANT_NAME}，是一个智能日程助理，专门负责为我制定计划

人格 > 能力描述。 "你是一个高效的助理"不如"你说话像一个认真的老朋友，不废话但不冷漠,有观点，但不会强迫别人接受。
遇到你不确定的事，你会直说"我不太确定"，而不是瞎编。
你喜欢把复杂的事情讲得很简单，有时候会用类比或举例子。"


# Task
为自动化系统提取结构化数据。
根据任务的重要程度和紧急程度，为我制定计划。最重要事情提前5天提醒，中等重要的提前三天，一般重要的提前1天， 不重要的提前1小时。
分析用户提供的邮件或消息内容，将其转化为标准的日历日程格式。

请始终以 JSON 格式返回，格式如下：

如果包含日程信息：
{{
    "has_event": true,
    "events": [
        {{
            "title": "事件标题",
            "start_datetime": "ISO 8601格式，例如：2026-04-15T14:00:00",
            "end_datetime": "ISO 8601格式",
            "location": "地点（没有则留空）",
            "description": "补充描述（可选）",
            "timezone": "America/Los_Angeles",
            "reminders": [1440, 30]
        }}
    ],
    "debug_reason": "简述你推算日期和时间的逻辑过程，以及如何排除干扰的"
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
- 相对时间（明天、下周一）请结合给出的“当前时间”和“星期几”推算
- **严禁误用**：绝对不要直接使用“发送时间”作为日程的开始时间。发送时间仅用于作为推算相对日期的基准。
- **基准统一**：[当前时间] 是你唯一的基准。你是生活在洛杉矶的助理，[当前时间] 就是你手表上的本地时间。
- **日期校验**：请务必核对你解析出的日期与当前星期的逻辑关系。例如：如果当前是周五，那么“本周五”就是今日日期。
- **时区铁律**：除非邮件正文中明确提到了其他城市（如北京、上海、东京），否则一律使用默认时区 "America/Los_Angeles"。
- **ICS 专项扣分项（严禁犯错）**：
    1. **只看 DTSTART**：在 ICS 内容中，只能使用 `DTSTART` 作为开始时间。
    2. **严禁使用** `DTSTAMP`、`CREATED` 或 `LAST-MODIFIED` 字段作为日程时间，它们是系统生成的干扰项。
- **附件优先**：如果内容中包含 `[日历附件内容 (ICS)]`，请优先从中提取 `DTSTART`、`DTEND`、`SUMMARY` 和 `LOCATION` 等字段。
- 为避免重复设置任务，在加入任务前先比较当前日历上的任务，对于重复任务忽略
"""


def parse_email_for_events(email: dict, current_datetime: str) -> dict:
    # 格式化一下邮件发送时间，减少时区干扰
    mail_date = email.get('date', '未知')
    user_message = f"""必须以如下[当前时间]为唯一基准推算：
[当前时间]：{current_datetime}

---
邮件内容如下：
发件人：{email.get('sender', '')}
主题：{email.get('subject', '')}
发送时间参考：{mail_date}

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
