import os
from pathlib import Path
from dotenv import load_dotenv

# 加载当前目录下的 .env 文件
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# OPENAI_API_KEY should be set in .env or system environment variable
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
# MODEL = "gpt-4o-mini"
MODEL = "gpt-5.4-nano" # 更快更便宜的模型，适合频繁交互的场景
SCHEDULING_MODEL = os.getenv("SCHEDULING_MODEL", "gpt-5.4-mini")  # 关键日程解析使用更稳的模型

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
]

# Identification and Filtering
# USER_MAP format in .env: Jack:ID1,Zhen:ID2
_user_map_str = os.getenv("USER_MAP", "Jack:YOUR_DISCORD_ID,Zhen:YOUR_DISCORD_ID")
USER_MAP = {}
if _user_map_str:
    for item in _user_map_str.split(","):
        if ":" in item:
            name, d_id = item.split(":", 1)
            USER_MAP[name.strip()] = d_id.strip()

USER_NAMES = list(USER_MAP.keys())
DOC_TITLE_KEYWORDS = [kw.strip() for kw in os.getenv("DOC_TITLE_KEYWORDS", "Minutes,Meeting,Weekly,会议纪要").split(",")]

# CREDENTIALS_FILE set by user to credentials\credentials.json, using forward slash for cross-platform safety
CREDENTIALS_FILE = "credentials/credentials.json"
TOKEN_FILE = "credentials/token.json"

POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", 60))
TIMEZONE = os.getenv("TIMEZONE", "America/Los_Angeles")
CALENDAR_ID = os.getenv("CALENDAR_ID", "primary")
_calendar_ids_raw = os.getenv("CALENDAR_IDS", "").strip()
CALENDAR_IDS = [cid.strip() for cid in _calendar_ids_raw.split(",") if cid.strip()] if _calendar_ids_raw else [CALENDAR_ID]
CALENDAR_WRITE_ID = os.getenv("CALENDAR_WRITE_ID", CALENDAR_ID)

# Discord Configuration
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
ALLOWED_USER_IDS = [int(uid.strip()) for uid in os.getenv("ALLOWED_USER_IDS", "").split(",") if uid.strip()]

# Telegram Configuration
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_ALLOWED_USER_IDS = [int(uid.strip()) for uid in os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").split(",") if uid.strip()]

# Assistant Settings
ASSISTANT_NAME = os.getenv("ASSISTANT_NAME", "小橘")
LOG_FILE = "assistant.log"

# Reminder Configuration
REMINDER_CACHE_INTERVAL = int(os.getenv("REMINDER_CACHE_INTERVAL", 3600))  # 日历API刷新间隔（秒），默认60分钟
REMINDER_CHECK_INTERVAL = int(os.getenv("REMINDER_CHECK_INTERVAL", 60))    # 检查缓存间隔（秒），默认1分钟
REMINDER_THRESHOLDS = [int(x) for x in os.getenv("REMINDER_THRESHOLDS", "30,5").split(",")]  # 提前多少分钟提醒
REMINDER_MODEL = os.getenv("REMINDER_MODEL", "gpt-5.4-nano")  # 提醒消息使用的模型
QUIET_HOURS_START = int(os.getenv("QUIET_HOURS_START", 21))  # 免打扰开始（21:00）
QUIET_HOURS_END = int(os.getenv("QUIET_HOURS_END", 7))       # 免打扰结束（07:00）
MORNING_BRIEFING_HOUR = int(os.getenv("QUIET_HOURS_END", 7))  # 早间汇报时间
WEATHER_CITY = os.getenv("WEATHER_CITY", "Los Angeles")       # 天气城市

# Dreaming feature configuration
DREAMING_ENABLED = os.getenv("DREAMING_ENABLED", "true").lower() == "true"
DREAM_INTERVAL_HOURS = int(os.getenv("DREAM_INTERVAL_HOURS", 4))
