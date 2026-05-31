"""Telegram message formatting and command handlers (locked to the owner)."""
from datetime import datetime
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

from . import config, summary


def _format_dt(iso: str | None) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d %b %Y, %H:%M")
    except (TypeError, ValueError):
        return iso or "unknown time"


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
        "/help — show this message"
    )


@restricted
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


@restricted
async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(summary.build_weekly_summary(previous=False))
