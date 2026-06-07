"""SQLite access layer. All reads/writes go through here."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from . import config

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


@contextmanager
def get_conn():
    Path(config.DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA_PATH.read_text())
        try:
            conn.execute("ALTER TABLE transactions ADD COLUMN telegram_message_id INTEGER")
        except sqlite3.OperationalError:
            pass  # column already exists after the first migration
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_transactions_tg_msg "
            "ON transactions(telegram_message_id)"
        )
        for col in ("is_reversal", "is_reversed", "is_excluded"):
            try:
                conn.execute(
                    f"ALTER TABLE transactions ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0"
                )
            except sqlite3.OperationalError:
                pass
        try:
            conn.execute("ALTER TABLE transactions ADD COLUMN pending_reversal_candidates TEXT")
        except sqlite3.OperationalError:
            pass


def transaction_exists(message_id: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT 1 FROM transactions WHERE gmail_message_id = ?", (message_id,)
        )
        return cur.fetchone() is not None


def insert_transaction(txn: dict) -> bool:
    """Insert a transaction. Returns True if actually inserted, False if already existed."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO transactions
                (gmail_message_id, merchant, amount, currency, transaction_type,
                 card_last4, occurred_at, category, needs_review, raw_snippet,
                 is_reversal, is_reversed)
            VALUES
                (:gmail_message_id, :merchant, :amount, :currency, :transaction_type,
                 :card_last4, :occurred_at, :category, :needs_review, :raw_snippet,
                 :is_reversal, :is_reversed)
            """,
            txn,
        )
        return cur.rowcount > 0


def get_category_for_merchant(merchant_norm: str):
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT category FROM merchant_categories WHERE merchant_pattern = ?",
            (merchant_norm,),
        )
        row = cur.fetchone()
        return row["category"] if row else None


def upsert_merchant_category(pattern: str, category: str, source: str = "rule") -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO merchant_categories (merchant_pattern, category, source)
            VALUES (?, ?, ?)
            ON CONFLICT(merchant_pattern)
            DO UPDATE SET category = excluded.category, source = excluded.source
            """,
            (pattern, category, source),
        )


def set_telegram_message_id(gmail_message_id: str, telegram_message_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE transactions SET telegram_message_id = ? WHERE gmail_message_id = ?",
            (telegram_message_id, gmail_message_id),
        )


def get_transaction_by_telegram_message_id(telegram_message_id: int) -> dict | None:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM transactions WHERE telegram_message_id = ?",
            (telegram_message_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def update_transaction_category(gmail_message_id: str, category: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE transactions SET category = ?, needs_review = 0 WHERE gmail_message_id = ?",
            (category, gmail_message_id),
        )


def update_category_for_merchant(merchant: str, category: str) -> None:
    """Update category for ALL existing transactions from this merchant (case-insensitive)."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE transactions SET category = ? WHERE LOWER(merchant) = LOWER(?)",
            (category, merchant),
        )


def exclude_transaction(gmail_message_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE transactions SET is_excluded = 1 WHERE gmail_message_id = ?",
            (gmail_message_id,),
        )


def find_reversal_candidates(merchant: str, amount: float, before_iso: str) -> list[dict]:
    """Return all eligible transactions that could be the original for a reversal, oldest-first."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT id, merchant, amount, occurred_at, gmail_message_id
            FROM transactions
            WHERE LOWER(merchant) = LOWER(?)
              AND amount = ?
              AND is_reversal = 0
              AND is_reversed = 0
              AND is_excluded = 0
              AND occurred_at < ?
            ORDER BY occurred_at ASC
            """,
            (merchant, amount, before_iso),
        )
        return [dict(r) for r in cur.fetchall()]


def mark_transaction_reversed(transaction_id: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE transactions SET is_reversed = 1 WHERE id = ?", (transaction_id,))


def undo_reversal(transaction_id: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE transactions SET is_reversed = 0 WHERE id = ?", (transaction_id,))


def set_pending_reversal_candidates(gmail_message_id: str, candidate_ids: list[int]) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE transactions SET pending_reversal_candidates = ? WHERE gmail_message_id = ?",
            (json.dumps(candidate_ids), gmail_message_id),
        )


def clear_pending_reversal_candidates(gmail_message_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE transactions SET pending_reversal_candidates = NULL WHERE gmail_message_id = ?",
            (gmail_message_id,),
        )


def get_transactions_from(from_iso: str) -> list[dict]:
    """Return non-needs_review transactions for resending.

    Normal transactions: occurred_at >= from_iso.
    Reversal transactions: all of them (date may be NULL or pre-cutoff).
    Results ordered oldest-first; NULL occurred_at sorts last.
    """
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT * FROM transactions
            WHERE needs_review = 0
              AND (
                (is_reversal = 0 AND occurred_at >= ?)
                OR is_reversal = 1
              )
            ORDER BY COALESCE(occurred_at, '9999-12-31') ASC
            """,
            (from_iso,),
        )
        return [dict(r) for r in cur.fetchall()]


def count_transactions() -> int:
    with get_conn() as conn:
        cur = conn.execute("SELECT COUNT(*) FROM transactions")
        return cur.fetchone()[0]


def clear_all_transactions() -> int:
    """Delete every row in transactions. Returns the number of rows deleted."""
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM transactions")
        return cur.rowcount


def get_summary_between(start_iso: str, end_iso: str) -> list[dict]:
    """Totals per category for [start, end), excluding needs_review, reversal, reversed, and excluded rows."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT category, COUNT(*) AS n, SUM(amount) AS total
            FROM transactions
            WHERE occurred_at >= ? AND occurred_at < ?
              AND needs_review = 0
              AND is_reversal = 0
              AND is_reversed = 0
              AND is_excluded = 0
            GROUP BY category
            ORDER BY total DESC
            """,
            (start_iso, end_iso),
        )
        return [dict(r) for r in cur.fetchall()]
