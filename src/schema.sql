-- SpendSense SQLite schema (Phase 1)

CREATE TABLE IF NOT EXISTS transactions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    gmail_message_id  TEXT    UNIQUE NOT NULL,        -- de-duplication key
    merchant          TEXT,
    amount            REAL,                            -- numeric value, e.g. 354200.00
    currency          TEXT    NOT NULL DEFAULT 'IDR',
    transaction_type  TEXT,                            -- e.g. DOMESTIK
    card_last4        TEXT,                            -- last 4 digits only
    occurred_at       TEXT,                            -- ISO-8601, Asia/Jakarta
    category          TEXT    NOT NULL DEFAULT 'Other',
    needs_review      INTEGER NOT NULL DEFAULT 0,      -- 0 = parsed ok, 1 = needs review
    raw_snippet         TEXT,                            -- only for needs_review (customer no. redacted)
    telegram_message_id INTEGER,                         -- Telegram message_id of the alert sent; NULL for pre-feature rows
    is_reversal         INTEGER NOT NULL DEFAULT 0,      -- 1 = this row is a reversal/void notification
    is_reversed         INTEGER NOT NULL DEFAULT 0,      -- 1 = this row was cancelled by a subsequent reversal
    is_excluded         INTEGER NOT NULL DEFAULT 0,      -- 1 = manually removed from summaries
    created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_transactions_occurred_at ON transactions(occurred_at);

CREATE TABLE IF NOT EXISTS merchant_categories (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_pattern TEXT    UNIQUE NOT NULL,          -- normalized (UPPER) merchant or substring
    category         TEXT    NOT NULL,
    source           TEXT    NOT NULL DEFAULT 'rule',  -- rule | llm | manual
    created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);
