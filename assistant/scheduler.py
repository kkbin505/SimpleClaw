"""
日程提醒调度器 (Schedule Reminder Scheduler)

功能：
1. 每 60 分钟从 Google Calendar API 刷新事件缓存
2. 每 60 秒检查缓存，在事件开始前 60 分钟和 15 分钟发送 Discord DM 提醒
3. 每天早上 7:00 推送当天全部日程摘要
4. 免打扰时段：21:00 ~ 07:00（早间汇报除外）
5. 使用 GPT-4o-mini 生成个性化提醒消息
"""

import asyncio
import logging
import httpx
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from openai import OpenAI

from calendar_client import CalendarClient
from config import (
    OPENAI_API_KEY, TIMEZONE, ALLOWED_USER_IDS, TELEGRAM_ALLOWED_USER_IDS, ASSISTANT_NAME,
    REMINDER_CACHE_INTERVAL, REMINDER_CHECK_INTERVAL, REMINDER_THRESHOLDS,
    REMINDER_MODEL, QUIET_HOURS_START, QUIET_HOURS_END, MORNING_BRIEFING_HOUR,
    WEATHER_CITY, DREAMING_ENABLED,
)
from dreaming import DreamGenerator

logger = logging.getLogger(__name__)
ai_client = OpenAI(api_key=OPENAI_API_KEY)


class ScheduleReminder:
    def __init__(self, calendar_client: CalendarClient, discord_bot=None, telegram_bot=None):
        self.calendar = calendar_client
        self.discord_bot = discord_bot
        self.telegram_bot = telegram_bot
        self.thresholds = sorted(REMINDER_THRESHOLDS, reverse=True)  # [60, 15]
        self.tz = ZoneInfo(TIMEZONE)

        # 缓存
        self._cached_events: list = []
        self._last_cache_time: datetime | None = None

        # 防重复：{f"{event_id}_{threshold_minutes}": True}
        self.sent_reminders: dict[str, bool] = {}

        # 早间汇报：记录上次推送日期，避免同一天重复推送
        self._last_briefing_date: str | None = None
        
        # 梦幻思考器
        self.dream_generator = DreamGenerator() if DREAMING_ENABLED else None

    # ------------------------------------------------------------------
    # 主循环入口
    # ------------------------------------------------------------------
    async def run(self):
        """持续运行：每分钟检查一次"""
        logger.info(
            f"ScheduleReminder started | thresholds={self.thresholds}min "
            f"| cache_interval={REMINDER_CACHE_INTERVAL}s "
            f"| quiet={QUIET_HOURS_START}:00~{QUIET_HOURS_END}:00"
        )
        while True:
            try:
                await self._tick()
            except Exception as e:
                logger.error(f"ScheduleReminder tick error: {e}", exc_info=True)
            await asyncio.sleep(REMINDER_CHECK_INTERVAL)

    async def _tick(self):
        """单次 tick：刷新缓存 → 检查早间汇报 → 检查梦 → 检查事件提醒"""
        now = datetime.now(self.tz)

        # 1. 按需刷新缓存
        await self._refresh_cache_if_needed(now)

        # 2. 早间汇报（7:00 AM，不受免打扰限制）
        await self._check_morning_briefing(now)

        # 3. 检查梦（梦不受免打扰限制，但间隔由配置决定）
        if DREAMING_ENABLED:
            await self._check_dreams()

        # 4. 免打扰时段内不发事件提醒
        if self._is_quiet_hour(now):
            return

        # 5. 检查事件提醒
        await self._check_event_reminders(now)

    # ------------------------------------------------------------------
    # 缓存管理
    # ------------------------------------------------------------------
    async def _refresh_cache_if_needed(self, now: datetime):
        """每 REMINDER_CACHE_INTERVAL 秒刷新一次日历缓存"""
        if (
            self._last_cache_time is None
            or (now - self._last_cache_time).total_seconds() >= REMINDER_CACHE_INTERVAL
        ):
            try:
                # list_events 返回带 hours_until 的事件列表
                self._cached_events = self.calendar.list_events(days=1, max_results=30)
                self._last_cache_time = now
                logger.info(f"Calendar cache refreshed: {len(self._cached_events)} events in next 24h")
            except Exception as e:
                logger.error(f"Failed to refresh calendar cache: {e}", exc_info=True)

    # ------------------------------------------------------------------
    # 免打扰
    # ------------------------------------------------------------------
    def _is_quiet_hour(self, now: datetime) -> bool:
        """判断当前是否在免打扰时段（21:00 ~ 07:00）"""
        hour = now.hour
        if QUIET_HOURS_START > QUIET_HOURS_END:
            # 跨午夜：21:00~07:00 → hour >= 21 or hour < 7
            return hour >= QUIET_HOURS_START or hour < QUIET_HOURS_END
        else:
            return QUIET_HOURS_START <= hour < QUIET_HOURS_END

    # ------------------------------------------------------------------
    # 事件提醒
    # ------------------------------------------------------------------
    async def _check_event_reminders(self, now: datetime):
        """检查缓存中的事件，在匹配阈值时发送提醒"""
        for event in self._cached_events:
            if event.get("hours_until") is None or event.get("all_day"):
                continue

            minutes_until = event["hours_until"] * 60

            # 跳过已过去的事件
            if minutes_until < 0:
                continue

            # 找出所有“可触发”且“尚未发送”的阈值
            active_unsent = [
                t for t in self.thresholds 
                if minutes_until <= t + 2 and f"{event['id']}_{t}" not in self.sent_reminders
            ]
            
            if not active_unsent:
                continue
                
            # 如果有多个符合条件的，选择最小的那个（即最接近现在的）
            # 比如当前剩余 12 分钟，符合 60 和 15 两个阈值，则只触发 15 分钟级的提醒
            target_threshold = min(active_unsent)
            
            await self._send_event_reminder(event, target_threshold)
            
            # 标记该阈值已发送，并同时屏蔽所有比它大的阈值
            # 这样如果系统启动时任务只剩 10 分钟，只会发 15 分钟提醒，而不会补发 60 分钟的
            for t in self.thresholds:
                if t >= target_threshold:
                    self.sent_reminders[f"{event['id']}_{t}"] = True

    async def _send_event_reminder(self, event: dict, minutes_before: int):
        """生成 AI 提醒并通过 Discord DM 发送"""
        try:
            msg = self._generate_ai_reminder(event, minutes_before)
        except Exception as e:
            logger.error(f"AI reminder generation failed, using fallback: {e}")
            msg = self._format_fallback_reminder(event, minutes_before)

        await self._broadcast_dm(msg)
        logger.info(f"Reminder sent: [{event['title']}] ({minutes_before}min before)")

    def _generate_ai_reminder(self, event: dict, minutes_before: int) -> str:
        """调用 GPT-4o-mini 生成个性化提醒"""
        time_label = self._humanize_minutes(minutes_before)
        prompt = f"""你是{ASSISTANT_NAME}，用户的私人助理。现在需要提醒用户一个即将开始的日程。

日程信息：
- 标题：{event['title']}
- 开始：{event['start']}
- 结束：{event['end']}
- 地点：{event.get('location') or '未指定'}
- 备注：{event.get('description') or '无'}
- 距开始：{time_label}

请用简短、温馨的语气提醒用户。根据事件类型给出 1-2 条实用小贴士。
要求：
- 开头用 ⏰ emoji
- 包含事件名称和时间
- 不超过 3 句话
- 语气像朋友提醒，不要太正式"""

        response = ai_client.chat.completions.create(
            model=REMINDER_MODEL,
            messages=[
                {"role": "system", "content": f"你是{ASSISTANT_NAME}，一个贴心的私人助理。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=200,
        )
        return response.choices[0].message.content

    def _format_fallback_reminder(self, event: dict, minutes_before: int) -> str:
        """AI 失败时的兜底模板"""
        time_label = self._humanize_minutes(minutes_before)
        lines = [
            f"⏰ **日程提醒** — {time_label}后开始",
            f"📌 **{event['title']}**",
            f"🕐 {event['start']} ~ {event['end']}",
        ]
        if event.get("location"):
            lines.append(f"📍 {event['location']}")
        if event.get("description"):
            lines.append(f"📝 {event['description']}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 早间汇报
    # ------------------------------------------------------------------
    async def _check_morning_briefing(self, now: datetime):
        """每天 7:00 AM 推送当天日程摘要"""
        today_str = now.strftime("%Y-%m-%d")

        # 已经推送过今天的
        if self._last_briefing_date == today_str:
            return

        # 还没到 7 点
        if now.hour < MORNING_BRIEFING_HOUR:
            return

        # 过了 7 点但在 8 点之前，触发推送（8 点后就不补发了）
        if now.hour >= MORNING_BRIEFING_HOUR + 1:
            # 超过 1 小时窗口，跳过今天（可能是刚启动）
            self._last_briefing_date = today_str
            return

        # 先刷新缓存确保数据最新
        try:
            self._cached_events = self.calendar.list_events(days=1, max_results=30)
            self._last_cache_time = now
        except Exception as e:
            logger.error(f"Failed to refresh cache for morning briefing: {e}")

        # 过滤今天的事件
        today_events = [
            e for e in self._cached_events
            if e.get("start") and e["start"].startswith(today_str)
        ]

        weather_info = await self._get_weather()
        msg = self._generate_morning_briefing(today_events, now, weather_info)
        await self._broadcast_dm(msg)
        self._last_briefing_date = today_str
        logger.info(f"Morning briefing sent for {today_str}: {len(today_events)} events")

    def _generate_morning_briefing(self, events: list, now: datetime, weather_info: str) -> str:
        """用 AI 生成早间日程汇报"""
        weekday_zh = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        date_str = f"{now.strftime('%Y年%m月%d日')} {weekday_zh[now.weekday()]}"

        if not events:
            events_text = "今天没有任何日程安排。"
        else:
            events_text = "\n".join([
                f"- {e['title']} | {e['start']} ~ {e['end']}"
                + (f" | 📍{e['location']}" if e.get("location") else "")
                for e in events
            ])

        prompt = f"""你是{ASSISTANT_NAME}，用户的私人助理。现在是早上 6 点，请为用户做一个今日日程汇报以及天气提醒。

日期：{date_str}

天气实况：
{weather_info}

今日日程：
{events_text}

要求：
- 开头用 🌅 emoji + 早安问候
- **【新增】**：先简要播报天气，并根据天气（温差、阴雨、体感）给主人一个穿衣或出行的小建议。
- 列出所有日程，按时间排序。
- 如果日程很多，简要提醒注意时间管理。
- 如果没有日程，轻松地告诉用户今天比较自由。
- 结尾简短鼓励。
- 整体不超过 10 句话，语气温暖、体贴。"""

        try:
            response = ai_client.chat.completions.create(
                model=REMINDER_MODEL,
                messages=[
                    {"role": "system", "content": f"你是{ASSISTANT_NAME}，一个温暖专业的私人助理，正在做早间汇报。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=400,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"AI morning briefing failed, using fallback: {e}")
            # 兜底
            if not events:
                return f"🌅 早安！今天是 {date_str}，没有日程安排，好好享受自由的一天吧！"
            lines = [f"🌅 早安！今天是 {date_str}，以下是今日日程：\n"]
            for e in events:
                lines.append(f"📌 **{e['title']}** — {e['start']} ~ {e['end']}")
            lines.append("\n祝你今天一切顺利！💪")
            return "\n".join(lines)

    # ------------------------------------------------------------------
    # 天气预报
    # ------------------------------------------------------------------
    async def _get_weather(self) -> str:
        """从 wttr.in 获取天气信息"""
        city = WEATHER_CITY
        logger.info(f"Fetching weather for {city}...")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # 使用 j1 格式获取 JSON 数据，并指定语言为中文
                resp = await client.get(f"https://wttr.in/{city}?format=j1&lang=zh")
                if resp.status_code == 200:
                    data = resp.json()
                    current = data['current_condition'][0]
                    today = data['weather'][0]
                    
                    # 提取描述（优先使用中文）
                    desc = current.get('lang_zh', [{'value': current['weatherDesc'][0]['value']}])[0]['value']
                    
                    weather_info = (
                        f"城市：{city}\n"
                        f"当前心情：{desc}，体感 {current['FeelsLikeC']}°C\n"
                        f"今日温差：{today['mintempC']}°C ~ {today['maxtempC']}°C\n"
                    )
                    return weather_info
        except Exception as e:
            logger.error(f"Weather fetch failed: {e}")
        return "天气信息获取失败"

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------
    async def _broadcast_dm(self, content: str):
        """给所有授权用户发送 DM（Discord 和 Telegram）"""
        # 发送 Discord DM
        if self.discord_bot:
            for discord_id in ALLOWED_USER_IDS:
                try:
                    await self.discord_bot.send_dm_to_user(discord_id, content)
                except Exception as e:
                    logger.error(f"Failed to DM Discord user {discord_id}: {e}")
        else:
            logger.debug("Discord bot not available, skipping Discord DM")
        
        # 发送 Telegram 消息
        if self.telegram_bot:
            for telegram_id in TELEGRAM_ALLOWED_USER_IDS:
                try:
                    await self.telegram_bot.send_message_to_user(telegram_id, content)
                except Exception as e:
                    logger.error(f"Failed to send Telegram message to user {telegram_id}: {e}")
        else:
            logger.debug("Telegram bot not available, skipping Telegram message")

    # ------------------------------------------------------------------
    # 梦幻思考
    # ------------------------------------------------------------------
    async def _check_dreams(self):
        """检查并生成梦（对所有授权用户）"""
        if not self.dream_generator:
            return
        
        # 检查所有授权用户
        all_user_ids = set(ALLOWED_USER_IDS + TELEGRAM_ALLOWED_USER_IDS)
        
        for user_id in all_user_ids:
            user_id_str = str(user_id)
            
            if self.dream_generator.should_generate_dream(user_id_str):
                try:
                    dream_content = await self.dream_generator.generate_dream(user_id_str)
                    if dream_content:
                        # 格式化梦的消息
                        msg = self._format_dream_message(dream_content)
                        await self._broadcast_dm_to_user(user_id_str, msg)
                        logger.info(f"Dream sent to user {user_id_str}")
                except Exception as e:
                    logger.error(f"Failed to generate dream for user {user_id_str}: {e}", exc_info=True)

    def _format_dream_message(self, dream_content: str) -> str:
        """格式化梦的消息"""
        return f"""💭 **{ASSISTANT_NAME}的梦幻思考**

{dream_content}

---
*这是基于你最近的交互模式的深思分析。希望能帮助你更好地组织工作和生活。*"""

    async def _broadcast_dm_to_user(self, user_id: str, content: str):
        """发送DM给特定用户（支持Discord和Telegram）"""
        try:
            # 尝试发送给Discord用户
            if self.discord_bot and int(user_id) in ALLOWED_USER_IDS:
                await self.discord_bot.send_dm_to_user(user_id, content)
                return
        except Exception as e:
            logger.debug(f"Failed to send Discord DM to {user_id}: {e}")
        
        try:
            # 尝试发送给Telegram用户
            if self.telegram_bot and int(user_id) in TELEGRAM_ALLOWED_USER_IDS:
                await self.telegram_bot.send_message_to_user(int(user_id), content)
                return
        except Exception as e:
            logger.debug(f"Failed to send Telegram message to {user_id}: {e}")

    @staticmethod
    def _humanize_minutes(minutes: int) -> str:
        """将分钟数转换为易读文本"""
        if minutes >= 60:
            hours = minutes // 60
            remaining = minutes % 60
            if remaining:
                return f"{hours}小时{remaining}分钟"
            return f"{hours}小时"
        return f"{minutes}分钟"
