"""SQLite access layer. All reads/writes go through here."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from . import config

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


@contextmanager
def get_conn():
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


def transaction_exists(message_id: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT 1 FROM transactions WHERE gmail_message_id = ?", (message_id,)
        )
        return cur.fetchone() is not None


def insert_transaction(txn: dict) -> None:
    """Insert a transaction. `txn` keys must match the columns below."""
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO transactions
                (gmail_message_id, merchant, amount, currency, transaction_type,
                 card_last4, occurred_at, category, needs_review, raw_snippet)
            VALUES
                (:gmail_message_id, :merchant, :amount, :currency, :transaction_type,
                 :card_last4, :occurred_at, :category, :needs_review, :raw_snippet)
            """,
            txn,
        )


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


def get_summary_between(start_iso: str, end_iso: str) -> list[dict]:
    """Totals per category for [start, end), excluding needs_review rows."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT category, COUNT(*) AS n, SUM(amount) AS total
            FROM transactions
            WHERE occurred_at >= ? AND occurred_at < ? AND needs_review = 0
            GROUP BY category
            ORDER BY total DESC
            """,
            (start_iso, end_iso),
        )
        return [dict(r) for r in cur.fetchall()]
