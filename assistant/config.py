import os
from pathlib import Path
from dotenv import load_dotenv

# 加载当前目录下的 .env 文件
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# OPENAI_API_KEY should be set in .env or system environment variable
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
MODEL = "gpt-4o-mini"

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
CALENDAR_ID = "primary"

# Discord Configuration
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
ALLOWED_USER_IDS = [int(uid.strip()) for uid in os.getenv("ALLOWED_USER_IDS", "").split(",") if uid.strip()]

# Assistant Settings
ASSISTANT_NAME = os.getenv("ASSISTANT_NAME", "小橘")
LOG_FILE = "assistant.log"
