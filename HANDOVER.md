# SpendSense — Handover

_Last updated: 2026-06-02 (session 2)_

---

## State of Play

### Completed

| Feature | Notes |
|---|---|
| Gmail polling → Telegram alerts | Polls every 60s, alerts on new BCA transactions |
| Weekly spending summary | Sends every Sunday 18:00 WIB via `/summary` or scheduled job |
| Reply-to-recategorize | Reply to any alert in Telegram to update category + teach merchant map |
| Auto-categorization | Rule-based seed map + learned `merchant_categories` table + optional Claude fallback |
| Reversal/void handling | Detects reversal emails, stores with `is_reversal=1`, marks original as `is_reversed=1`, excludes both from summary |
| Railway deployment | Live on Railway (service: `marvelous-enjoyment`, project: `667344aa`), persistent `/data` volume for SQLite |
| Notion product docs | "Product Documentation" page in Notion has SpendSense → Weekly Summary + Reply-to-Recategorize sub-pages |
| Plain-text summary trigger | Sending "summary" (any case) as a plain message returns the current week summary, same as `/summary` |
| Stable merchant category keys | `_stable_merchant_key()` in `src/categorizer.py` strips trailing order-ID tokens before storing/looking up learned mappings — Tokopedia/GoPay orders with different suffixes now share one category entry |

### In-Progress / Partially Done

| Item | Status |
|---|---|
| **Merchant category map** | Only 2 manual entries (`TTS BY TKPD`, `MIDTRANS-IFIID`). Most merchants still fall through to "Other". The reply-to-recategorize feature is the intended fix — but it requires the bot to be running when the original alert was sent so `telegram_message_id` is stored. Stable key fix now deployed, so new learned entries will persist across orders. |
| **Railway ↔ GitHub auto-deploy** | Not connected. Every deploy requires `railway up --detach --service marvelous-enjoyment` from the local machine. Consider connecting the GitHub repo in the Railway dashboard. |

### Unresolved / Known Issues

| Issue | Detail |
|---|---|
| Pre-Railway `telegram_message_id` = NULL | All 52 transactions in the DB were alerted before the `telegram_message_id` feature landed or before Railway was running. Replying to those old alerts will return "No transaction linked to that message." Only new alerts sent by the Railway bot will be linkable. |
| `set_railway_vars.sh` not committed | The helper script to set Railway env vars is untracked (`git status` shows it). Safe to commit or delete. |
| `merchant_categories` learning is per-merchant-instance | ~~Was per full string — now fixed.~~ `_stable_merchant_key()` strips trailing order-ID tokens before storing/looking up, so `TTS BY TKPD 1041025679` and `TTS BY TKPD 9999999999` both resolve to `TTS BY TKPD`. Existing 2 DB entries are unaffected (no digits). |
| Reversal match is first-past-the-post | `find_and_mark_reversed()` marks the most recent non-reversed transaction with the same merchant+amount. If two identical transactions exist and only one is reversed, it always picks the most recent — which may be wrong. No workaround yet. |

---

## File State

```
On branch main — up to date with origin/main

Untracked (not committed):
  set_railway_vars.sh     ← helper for Railway env vars, safe to commit or ignore
```

**DB state (local `spendsense.db`):**
- 52 transactions, 0 reversals processed, 2 manual merchant category entries
- All `telegram_message_id` = NULL (pre-Railway era)
- Railway `/data/spendsense.db` is the live database; local copy is stale

---

## Key Learnings

### Railway
- `mcpServers` does not belong in `~/.claude/settings.json` — MCP servers are configured via `claude mcp add` CLI, which writes to `~/.claude.json`.
- Railway internal integrations can't create top-level Notion pages — the integration must be explicitly shared on an existing page first.
- Railway service name auto-generated as `marvelous-enjoyment` (not `spendsense`). Always use `--service marvelous-enjoyment` flag.
- Railway volumes must be configured in `railway.toml` (`[[volumes]] mountPath = "/data"`) AND `DATABASE_PATH` env var must point inside `/data/`. The directory is created on first deploy — `db.py` must call `Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)` before connecting.
- Deploying via `railway up` uploads source directly — it is **not** connected to GitHub. Changes must be pushed to GitHub AND `railway up` run separately.
- The `Conflict: terminated by other getUpdates request` error on redeploy is normal — it clears once the old container stops.

### Notion MCP
- The Notion MCP server tools (`mcp__notion__*`) only appear after restarting the Claude Code session following `claude mcp add`. They are deferred tools and won't show on the same session they're configured.
- Using the REST API directly (curl / Python `urllib`) is a reliable fallback — same result without needing the MCP session restart.
- Notion internal integrations cannot create workspace-level pages. Must create the parent page manually in Notion, share it with the integration via "Connections", then pass its page ID to the API.
- Shell heredoc `<<'EOF'` breaks if the JSON body contains single quotes (e.g. `it's`). Use a Python script with `json.dumps()` instead.

### Parser / DB
- `ALTER TABLE ... ADD COLUMN` in SQLite does not support `IF NOT EXISTS` — always wrap in `try/except sqlite3.OperationalError`.
- `schema.sql` runs via `executescript()` on every startup — new columns added there only apply to fresh DBs. Existing DBs need the `ALTER TABLE` migration path in `init_db()`.
- The Gmail query uses OR syntax: `(subject:"A" OR subject:"B")` — without parentheses the `from:` filter doesn't apply to both subjects.

### Telegram bot
- `MessageHandler` with `filters.TEXT & filters.REPLY & ~filters.COMMAND` must be registered **after** all `CommandHandler`s in `main()` — PTB processes handlers in registration order within the same group.
- `send_message()` returns a `Message` object — capture it to get `message_id` for reply-linking.
- The `@restricted` decorator silently ignores messages from any chat that isn't `TELEGRAM_CHAT_ID`. Useful for security but makes debugging confusing if the wrong chat ID is set.

---

## Next Concrete Step

No critical issues outstanding. Suggested next tasks in priority order:

1. **Build up the merchant category map** — use the bot for a week and reply-to-recategorize new transactions as they come in. Stable keys are now in place so each learned entry will be reused across orders.
2. **Connect Railway ↔ GitHub** — auto-deploy on push so `railway up` isn't needed after every commit.
3. **Raise `max_results` for backfill** — currently capped at 50 in `gmail_client.list_recent_message_ids`. Increase if a fuller transaction history is wanted on fresh deploys.
