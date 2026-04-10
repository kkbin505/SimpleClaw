import os
from dotenv import load_dotenv

load_dotenv()

# OPENAI_API_KEY should be set as a system environment variable.
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
MODEL = "gpt-4o-mini"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
]

CREDENTIALS_FILE = "credentials/google_credentials.json"
TOKEN_FILE = "credentials/token.json"

POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", 60))
TIMEZONE = os.getenv("TIMEZONE", "Asia/Shanghai")
CALENDAR_ID = "primary"
