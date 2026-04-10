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
]

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
