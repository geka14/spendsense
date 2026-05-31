"""One-shot helper: print your Telegram chat ID.

Usage:
    1. Fill TELEGRAM_BOT_TOKEN in .env (or export it in your shell).
    2. Send any message to your bot in Telegram.
    3. Run:  python get_chat_id.py
    4. Copy the chat ID printed into TELEGRAM_CHAT_ID in .env.
"""
import os
import urllib.request
import json

from dotenv import load_dotenv

load_dotenv()

token = os.getenv("TELEGRAM_BOT_TOKEN", "")
if not token:
    raise SystemExit("Set TELEGRAM_BOT_TOKEN in .env first.")

url = f"https://api.telegram.org/bot{token}/getUpdates"
with urllib.request.urlopen(url) as resp:
    data = json.loads(resp.read())

messages = data.get("result", [])
if not messages:
    raise SystemExit(
        "No updates found. Send any message to your bot in Telegram, then re-run."
    )

seen = set()
for update in messages:
    chat = (update.get("message") or update.get("channel_post") or {}).get("chat", {})
    cid = chat.get("id")
    name = chat.get("first_name") or chat.get("title") or ""
    if cid and cid not in seen:
        seen.add(cid)
        print(f"Chat ID: {cid}  ({name})")

print("\nPaste the correct ID as TELEGRAM_CHAT_ID in your .env file.")
