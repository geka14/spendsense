"""Central configuration. All settings come from environment variables / .env."""
import os
from dotenv import load_dotenv

load_dotenv()

# --- Telegram (required) ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- Gmail ---
GMAIL_CREDENTIALS_FILE = os.getenv("GMAIL_CREDENTIALS_FILE", "credentials.json")
GMAIL_TOKEN_FILE = os.getenv("GMAIL_TOKEN_FILE", "token.json")
# On cloud hosts, pass the JSON content of each file as an env var instead of mounting files.
GMAIL_CREDENTIALS_JSON = os.getenv("GMAIL_CREDENTIALS_JSON", "")
GMAIL_TOKEN_JSON = os.getenv("GMAIL_TOKEN_JSON", "")
GMAIL_QUERY = os.getenv(
    "GMAIL_QUERY",
    'from:KartuKreditBCA@klikbca.com subject:"Credit Card Transaction Notification"',
)

# --- App behaviour ---
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
DATABASE_PATH = os.getenv("DATABASE_PATH", "spendsense.db")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Jakarta")

# --- Weekly summary schedule ---
WEEKLY_SUMMARY_DAY = os.getenv("WEEKLY_SUMMARY_DAY", "mon")  # mon..sun
WEEKLY_SUMMARY_HOUR = int(os.getenv("WEEKLY_SUMMARY_HOUR", "8"))
WEEKLY_SUMMARY_MINUTE = int(os.getenv("WEEKLY_SUMMARY_MINUTE", "0"))

# --- Optional LLM categorization ---
USE_LLM_CATEGORIZATION = os.getenv("USE_LLM_CATEGORIZATION", "false").lower() == "true"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")


def validate() -> None:
    """Raise if required settings are missing. Call once at startup."""
    missing = [
        name
        for name, value in (
            ("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN),
            ("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID),
        )
        if not value
    ]
    if missing:
        raise RuntimeError("Missing required env vars: " + ", ".join(missing))
