"""Telegram message formatting and command handlers (locked to the owner)."""
import asyncio
import logging
from datetime import datetime
from functools import wraps

log = logging.getLogger("spendsense")

from telegram import Update
from telegram.ext import ContextTypes

from . import config, db, summary


_CATEGORY_ALIASES: dict[str, str] = {
    # Dining
    "food": "Dining", "makan": "Dining", "eat": "Dining", "restaurant": "Dining",
    "resto": "Dining", "cafe": "Dining", "kafe": "Dining",
    "lunch": "Dining", "dinner": "Dining", "breakfast": "Dining",
    "sarapan": "Dining", "makan siang": "Dining", "makan malam": "Dining",
    # Groceries
    "grocery": "Groceries", "groceries": "Groceries", "supermarket": "Groceries",
    "belanja": "Groceries", "sembako": "Groceries", "minimarket": "Groceries",
    # Transport
    "transport": "Transport", "transportasi": "Transport", "ojek": "Transport",
    "taxi": "Transport", "taksi": "Transport", "bensin": "Transport",
    "fuel": "Transport", "petrol": "Transport", "bus": "Transport",
    "kereta": "Transport", "train": "Transport", "mrt": "Transport",
    # Shopping
    "shopping": "Shopping", "shop": "Shopping", "online": "Shopping",
    "belanja online": "Shopping", "ecommerce": "Shopping",
    # Bills & Utilities
    "bills": "Bills & Utilities", "utilities": "Bills & Utilities",
    "tagihan": "Bills & Utilities", "listrik": "Bills & Utilities",
    "electricity": "Bills & Utilities", "internet": "Bills & Utilities",
    "pulsa": "Bills & Utilities", "utility": "Bills & Utilities",
    # Entertainment
    "entertainment": "Entertainment", "hiburan": "Entertainment",
    "movie": "Entertainment", "film": "Entertainment", "bioskop": "Entertainment",
    "nonton": "Entertainment", "game": "Entertainment", "streaming": "Entertainment",
    # Health
    "health": "Health", "kesehatan": "Health", "obat": "Health",
    "pharmacy": "Health", "apotek": "Health", "doctor": "Health",
    "dokter": "Health", "klinik": "Health", "clinic": "Health",
    "medical": "Health", "rumah sakit": "Health", "hospital": "Health",
    # Travel
    "travel": "Travel", "hotel": "Travel", "penginapan": "Travel",
    "flight": "Travel", "pesawat": "Travel", "liburan": "Travel",
    "vacation": "Travel", "wisata": "Travel",
    # Cash/ATM
    "cash": "Cash/ATM", "atm": "Cash/ATM", "tunai": "Cash/ATM",
    "tarik tunai": "Cash/ATM", "withdrawal": "Cash/ATM",
    # Other
    "other": "Other", "lain": "Other", "lainnya": "Other",
    "misc": "Other", "miscellaneous": "Other",
}

_CANONICAL = {c.lower(): c for c in (
    "Groceries", "Dining", "Transport", "Shopping", "Bills & Utilities",
    "Entertainment", "Health", "Travel", "Cash/ATM", "Other",
)}


def _normalize_category(raw: str) -> str:
    key = raw.lower().strip()
    if key in _CATEGORY_ALIASES:
        return _CATEGORY_ALIASES[key]
    if key in _CANONICAL:
        return _CANONICAL[key]
    return raw.strip().title()  # custom category, e.g. "personal care" → "Personal Care"


def _format_dt(iso: str | None) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d %b %Y, %H:%M")
    except (TypeError, ValueError):
        return iso or "unknown time"


def format_reversal_alert(txn: dict) -> str:
    amt = f"-{summary.format_rupiah(txn['amount'])}" if txn.get("amount") is not None else "Rp ???"
    return (
        "↩️ BCA Reversal/Void\n"
        f"{amt} — {txn.get('merchant') or '???'}\n"
        f"{_format_dt(txn.get('occurred_at'))} WIB\n"
        f"Card ....{txn.get('card_last4') or '????'} · {txn.get('transaction_type') or ''}"
    )



def format_alert(txn: dict) -> str:
    """Build the real-time alert text from a transaction dict."""
    if txn.get("needs_review"):
        snippet = (txn.get("raw_snippet") or "")[:500]
        return "⚠️ Couldn't fully parse a BCA transaction email. Please review:\n\n" + snippet

    return (
        "💳 BCA Credit Card\n"
        f"{summary.format_rupiah(txn['amount'])} — {txn['merchant']}\n"
        f"{_format_dt(txn['occurred_at'])} WIB\n"
        f"Card ....{txn.get('card_last4') or '????'} · {txn.get('transaction_type') or ''}\n"
        f"Category: {txn['category']}"
    )


def restricted(func):
    """Ignore any chat that isn't the configured owner."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if str(update.effective_chat.id) != str(config.TELEGRAM_CHAT_ID):
            return
        return await func(update, context)
    return wrapper


@restricted
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "SpendSense is running.\n"
        "/summary — this week's spending by category\n"
        "/monthly — this month's spending by category\n"
        "/help — show this message"
    )


@restricted
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


@restricted
async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(summary.build_weekly_summary(previous=False))


@restricted
async def cmd_monthly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(summary.build_monthly_summary(previous=False))


@restricted
async def cmd_resend(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resend transaction alerts from a date (YYYY-MM-DD). Updates telegram_message_id."""
    args = context.args
    from_date = args[0] if args else "2026-06-01"
    try:
        # Parse as start-of-day Asia/Jakarta; ISO string comparison works lexicographically
        datetime.strptime(from_date, "%Y-%m-%d")
        from_iso = f"{from_date}T00:00:00+07:00"
    except ValueError:
        await update.message.reply_text(f"Invalid date '{from_date}'. Use YYYY-MM-DD.")
        return

    txns = db.get_transactions_from(from_iso)
    if not txns:
        await update.message.reply_text(f"No transactions found from {from_date}.")
        return

    await update.message.reply_text(f"Resending {len(txns)} alerts from {from_date}…")

    sent_count = 0
    for txn in txns:
        try:
            if txn.get("is_reversal"):
                text = format_reversal_alert(txn)
            else:
                text = format_alert(txn)
            sent = await context.bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=text)
            db.set_telegram_message_id(txn["gmail_message_id"], sent.message_id)
            sent_count += 1
            await asyncio.sleep(0.35)  # stay under Telegram's 30 msg/s limit
        except Exception as e:
            log.warning("Resend failed for %s: %s", txn.get("gmail_message_id"), e)

    await update.message.reply_text(f"✅ Done — {sent_count}/{len(txns)} alerts resent.")


@restricted
async def cmd_cleardb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete all transaction rows. Requires /cleardb CONFIRM to proceed."""
    args = context.args
    if not args or args[0] != "CONFIRM":
        count = db.count_transactions()
        await update.message.reply_text(
            f"⚠️ This will permanently delete all {count} transaction rows.\n"
            "Send /cleardb CONFIRM to proceed."
        )
        return
    deleted = db.clear_all_transactions()
    await update.message.reply_text(f"🗑 Done — {deleted} transactions deleted.")


@restricted
async def handle_recategorize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reply_to = update.message.reply_to_message
    if reply_to is None:
        return

    txn = db.get_transaction_by_telegram_message_id(reply_to.message_id)
    if txn is None:
        await update.message.reply_text(
            "No transaction linked to that message.\n"
            "(Only alerts sent after the recategorize update are linked.)"
        )
        return

    text = update.message.text.strip().lower()

    # Remove from summary
    if text == "remove":
        db.exclude_transaction(txn["gmail_message_id"])
        await update.message.reply_text(
            f"🗑 {txn['merchant'] or 'Transaction'} removed from summaries."
        )
        return

    # Recategorize
    category = _normalize_category(update.message.text)
    db.update_transaction_category(txn["gmail_message_id"], category)

    if txn.get("merchant"):
        from . import categorizer
        db.upsert_merchant_category(
            categorizer._stable_merchant_key(txn["merchant"]), category, source="manual"
        )
        db.update_category_for_merchant(txn["merchant"], category)

    await update.message.reply_text(f"✅ {txn['merchant'] or 'Transaction'} → {category}")
