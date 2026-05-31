# SpendSense

Personal tool that watches Gmail for BCA credit card transaction emails, sends a real-time
alert to Telegram (amount + merchant), stores every transaction with a spending category,
and provides a **weekly** per-category spending summary through the same Telegram bot.

Telegram is the only interface — there is no web or mobile app to build.

This repo is a **starter scaffold**. Most of Phase 1 is implemented; see `CLAUDE.md` for
what's done and what still needs wiring/testing.

## Architecture (Phase 1 / MVP)

```
Bank email → Gmail inbox → [poll] → parse → categorize → SQLite
                                              └→ Telegram alert → your iPhone
/summary command ─────────────────────────────→ weekly category breakdown
```

Ingestion is **polling** (check Gmail every 60s) and Telegram uses **long polling**, so no
public webhook or open ports are needed — it runs as one always-on process.

## Prerequisites

- Python 3.11+
- A Telegram account, a Google account that receives the BCA emails
- (Optional) An Anthropic API key for LLM-assisted categorization

## Setup

1. **Install dependencies**
   ```bash
   python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Create the Telegram bot**
   - In Telegram, message `@BotFather`, send `/newbot`, follow the prompts, copy the token.

3. **Find your Telegram chat ID**
   - Send any message to your new bot first.
   - Then message `@userinfobot` to get your numeric ID, OR ask Claude Code to write a
     one-off script that calls `getUpdates` and prints the chat ID.

4. **Enable the Gmail API**
   - Go to Google Cloud Console → create a project → enable the **Gmail API**.
   - Configure an OAuth consent screen (External, add yourself as a test user).
   - Create an **OAuth client ID** of type *Desktop app*, download the JSON, and save it as
     `credentials.json` in this folder.

5. **Configure environment**
   ```bash
   cp .env.example .env
   ```
   Fill in `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. Leave the rest at defaults to start.

6. **Run it**
   ```bash
   python -m src.main
   ```
   The first run opens a browser to authorize Gmail (read-only). After that, a `token.json`
   is saved and reused. Make a test card transaction (or wait for one) and you should get a
   Telegram alert within ~1 minute. Send `/summary` to your bot for this week's breakdown.

## Tests

```bash
pytest
```

`tests/test_parser.py` validates the BCA email parser against a real sample.

## Deploying 24/7

A sleeping laptop misses transactions. Run it on an always-on host:
- **Managed:** push to GitHub, add a Dockerfile, deploy on Railway/Render.
- **Self-hosted:** Raspberry Pi or small VPS under `systemd` (auto-restart). Authorize Gmail
  once locally, then copy `token.json` to the host.

## Security

- The bot only responds to your `TELEGRAM_CHAT_ID`.
- The `Nomor Customer` value is never stored or logged.
- Only the last 4 card digits are kept.
- `.env`, `credentials.json`, `token.json`, and the database are git-ignored.
