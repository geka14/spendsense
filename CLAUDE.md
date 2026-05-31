# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this project is

SpendSense is a single-user personal tool. It reads BCA credit card transaction emails from
Gmail, sends real-time alerts to one Telegram chat, stores transactions in SQLite, and
produces a **weekly** per-category spending summary via Telegram. See `PRD_SpendSense.docx`
for the full product spec and later phases. **Phase 1 (this scaffold) is Telegram-only with a
weekly summary.** Do not add a web UI or native app — those are later phases.

## How to run

```bash
pip install -r requirements.txt
cp .env.example .env          # then fill in TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
python -m src.main            # run as a module from the repo root (relative imports)
```

First run opens a browser for Gmail OAuth and writes `token.json`.

## How to test

```bash
pytest                        # runs tests/test_parser.py against a real BCA sample
```

When changing the parser, run the tests. When changing anything else, do a manual end-to-end
check: trigger a transaction (or replay a saved email) and confirm a Telegram alert arrives
and a row lands in the DB.

## Project layout

```
src/
  config.py        Loads env vars (python-dotenv). Single source of settings.
  schema.sql       SQLite schema (transactions, merchant_categories).
  db.py            Connection helper + all DB reads/writes.
  bca_parser.py    parse_bca_email(html_or_text) -> ParsedTransaction. Pure & tested.
  categorizer.py   Rule-based categories + seed map + optional Claude fallback.
  gmail_client.py  OAuth + list/fetch matching messages (read-only scope).
  summary.py       Week boundaries + Rupiah formatting + weekly summary text.
  telegram_bot.py  Alert formatting + /start /help /summary handlers (locked to owner).
  main.py          Wires Application + JobQueue (60s Gmail poll, weekly summary job).
tests/
  test_parser.py   Parser assertions.
  sample_email.txt Plain-text version of a real BCA notification.
```

## Implementation status

Implemented and intended to work: config, schema, db, parser (with tests), rule-based
categorizer + optional LLM hook, Gmail OAuth/list/fetch, weekly summary builder, Telegram
alert/format/commands, and the main poll + weekly job wiring.

Verify / harden before relying on it:
- **PTB weekday indexing** in `main.py`'s `run_daily(days=...)` — confirm the convention for
  the installed `python-telegram-bot` version (in v20+ Monday is `0`) and test it fires.
- **Gmail body extraction** in `gmail_client._extract_body` against your actual emails
  (multipart shapes vary); confirm it returns the HTML/text that contains the labels.
- **Backlog on startup**: currently the 60s poll picks up the most recent N unseen messages.
  If you want a fuller backfill on first run, raise `max_results` or add a one-time backfill.
- **Refund/reversal emails**: not yet special-cased. Check how BCA phrases them and handle
  negative amounts / de-duplication if needed.

## Conventions

- Money is handled as a numeric amount + `currency` ("IDR"); parse Indonesian format
  (`.` = thousands, `,` = decimals). Format for display via `summary.format_rupiah`.
- Timestamps are stored as ISO-8601 strings in Asia/Jakarta; week ranges query on that.
- Never store or log `Nomor Customer`. Keep only the last 4 card digits.
- All settings come from `config.py` / `.env` — no hardcoded tokens, IDs, or paths.
- Keep modules small and readable; add a short comment for any non-obvious choice.

## The BCA email format (parser contract)

Only emails from `KartuKreditBCA@klikbca.com` with subject
"Credit Card Transaction Notification" are processed. Relevant `Label : value` lines:

```
Nomor Kartu      : 431657XXXX8545          -> card_last4 = "8545"
Merchant / ATM   : SKS MKG                  -> merchant
Jenis Transaksi  : DOMESTIK                 -> transaction_type
Pada Tanggal     : 31-05-2026 11:44:07 WIB  -> occurred_at (%d-%m-%Y %H:%M:%S, Asia/Jakarta)
Sejumlah         : Rp354.200,00             -> amount = 354200.00
```

If a matching email can't be fully parsed, store it with `needs_review = 1` and send a
"couldn't parse" Telegram message — never drop it silently.
