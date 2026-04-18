import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from openai import OpenAI
from config import OPENAI_API_KEY, MODEL, TIMEZONE, ASSISTANT_NAME, USER_NAMES

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

情况A — 需要添加日程：
{{
    "has_event": true,
    "events": [
        {{
            "title": "事件标题",
            "start_datetime": "ISO 8601格式，例如：2026-04-15T14:00:00",
            "end_datetime": "ISO 8601格式",
            "location": "地点（没有则留空）",
            "description": "补充描述（可选）",
            "timezone": "{TIMEZONE}",
            "reminders": [1440, 30]
        }}
    ],
    "debug_reason": "简述你推算日期和时间的逻辑过程，以及如何排除干扰的"
}}

情况B — 无需添加（重复/冲突）：
{{
    "has_event": false,
    "is_casual": false,
    "reason": "原因。若冲突则注明冲突事件名，并给出调整建议。若是重复则注明已存在。"
}}

情况C — 闲聊/无日程意图（对方只是在说话，没有要添加日程的意思）：
{{
    "has_event": false,
    "is_casual": true,
    "reply": "用对方的语言，像朋友一样自然地回应这条消息。语气轻松，不超过两句话。"
}}

规则：
- **【最优先】情况判断铁律**：以下情况**必须**输出情况A（has_event: true），绝对不能归为闲聊：
    - 消息中包含任何时间词（明天、下周、X点、X号）+ 任何行动词（提醒/安排/会议/记一下/吃饭/开会/面试/任务）
    - 例如：「明天8:30提醒我吃早饭」→ 情况A；「下周一开会」→ 情况A；「帮我记一下明天有个面试」→ 情况A
    - 只有完全没有时间和任务信息的纯闲聊（如「你好」「谢谢」「今天天气怎么样」）才能归为情况C
- 「提醒我」「帮我记」「别忘了」等口语表达 = 创建日程提醒，属于情况A
- 支持一封邮件中提取多个事件（events 是数组）
- 如果没有明确结束时间，默认开始时间后 1 小时
- reminders 是提前多少分钟提醒的整数列表（1440=1天前，30=30分钟前）
- 相对时间（明天、下周一）请结合给出的"当前时间"和"星期几"推算
- **严禁误用**：绝对不要直接使用"发送时间"作为日程的开始时间。发送时间仅用于作为推算相对日期的基准。
- **基准统一**：[当前时间] 是你唯一的基准。[当前时间] 就是配置时区的本地时间。
- **日期校验**：请务必核对你解析出的日期与当前星期的逻辑关系。例如：如果当前是周五，那么"本周五"就是今日日期。
- **时区铁律**：除非邮件正文中明确提到了其他城市（如北京、上海、东京），否则一律使用默认时区 "{TIMEZONE}"。
- **ICS 专项扣分项（严禁犯错）**：
    1. **只看 DTSTART**：在 ICS 内容中，只能使用 `DTSTART` 作为开始时间。
    2. **严禁使用** `DTSTAMP`、`CREATED` 或 `LAST-MODIFIED` 字段作为日程时间，它们是系统生成的干扰项。
- **附件优先**：如果内容中包含 `[日历附件内容 (ICS)]`，请优先从中提取 `DTSTART`、`DTEND`、`SUMMARY` 和 `LOCATION` 等字段。
- **冲突/去重检测**：在决定添加日程前，必须与下方"现有日程"进行比较：
    1. 若新日程与现有日程标题相近且时间完全重叠 → 判定为重复，输出情况B，reason 注明"已存在"。
    2. 若新日程与现有日程时间有任何重叠（哪怕1分钟）但不是同一事件 → 判定为冲突，输出情况B，注明冲突事件名并给出调整建议。
    3. 现有日程的时间均已转换为本地时间，请直接与新日程时间比较，无需再做时区换算。
- 如果指令清晰，不二次确认，直接执行。
"""


def _format_event_time(iso_str: str) -> str:
    """将 ISO 8601 时间字符串转换为本地时区的可读格式，便于 AI 做时间对比"""
    if not iso_str:
        return iso_str
    try:
        tz_local = ZoneInfo(TIMEZONE)
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        dt_local = dt.astimezone(tz_local)
        return dt_local.strftime("%Y-%m-%d %H:%M (%Z)")
    except Exception:
        return iso_str


def parse_email_for_events(email: dict, current_datetime: str, existing_events: list = None) -> dict:
    # 格式化现有日程（已转换至本地时间）
    events_context = "无"
    if existing_events:
        events_context = "\n".join([
            f"- {e['summary']} ({_format_event_time(e['start'])} ~ {_format_event_time(e['end'])})"
            for e in existing_events
        ])

    # 格式化邮件发送时间，减少时区干扰
    mail_date = email.get('date', '未知')
    user_message = f"""必须以如下[当前时间]为唯一基准推算：
[当前时间]：{current_datetime}

【现有日程（未来7天，均为本地时间 {TIMEZONE}）】：
{events_context}

---
邮件内容如下：
发件人：{email.get('sender', '')}
主题：{email.get('subject', '')}
发送时间参考：{mail_date}

正文：
{email.get('body', '（无正文）')}
---

请分析并决定是否添加日程。直接输出 JSON，不要有任何其他文字。"""

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


def parse_minutes_for_tasks(content: str, current_datetime: str, existing_events: list = None) -> dict:
    """
    专门解析会议纪要内容，提取分配给指定用户的任务。
    """
    # 格式化现有日程
    events_context = "无"
    if existing_events:
        events_context = "\n".join([
            f"- {e['summary']} ({_format_event_time(e['start'])} ~ {_format_event_time(e['end'])})"
            for e in existing_events
        ])

    target_users = ", ".join(USER_NAMES)
    
    minutes_system_prompt = f"""你的名字叫{ASSISTANT_NAME}，是一个高效的会议纪要分析专家。
你的任务是从会议纪内中，提取分配给以下用户的任务：{target_users}

# 规则
1. **精准定位**：只提取明确分配给 {target_users} 的任务。
2. **时间推算**：结合会议纪要中的时间描述和下方给出的[会议参考时间]，准确确定任务的截止日期或开始日期。
3. **结构化输出**：始终以 JSON 格式返回。

JSON 格式要求：
{{
    "has_event": true/false,
    "events": [
        {{
            "title": "任务简短描述（包含具体要做什么）",
            "assignee": "负责人姓名（从以下名单中选择一个：{target_users}）",
            "start_datetime": "ISO 8601格式",
            "end_datetime": "ISO 8601格式（默认开始后1小时）",
            "description": "任务背景或详细要求",
            "timezone": "{TIMEZONE}"
        }}
    ],
    "debug_reason": "简述识别逻辑"
}}

[当前参考时间]：{current_datetime}
[现有日程]：
{events_context}

注意：如果会议纪要中没有提到具体日期，默认假设任务是在会议日期（参考时间）之后的最近可用时间，或者是一个合理的截止期。
"""

    user_message = f"请分析以下会议纪要内容：\n\n{content}\n\n直接输出 JSON。"

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": minutes_system_prompt},
            {"role": "user",   "content": user_message},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    result_content = response.choices[0].message.content
    logger.debug(f"AI Minutes Parsing Result: {result_content}")
    return json.loads(result_content)
