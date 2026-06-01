"""Entry point: wire the Telegram bot, the Gmail poll job, and the weekly summary job.

Run from the repo root:  python -m src.main
"""
import logging
from datetime import time
from zoneinfo import ZoneInfo

from telegram.ext import Application, CommandHandler, ContextTypes

from . import bca_parser, categorizer, config, db, gmail_client, summary, telegram_bot

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("spendsense")

# python-telegram-bot run_daily weekday indexing (v20+: Monday = 0).
# NOTE: verify against your installed PTB version and test that the job fires.
_DAY_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


async def poll_gmail(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check Gmail for new BCA transaction emails; store + alert for each new one."""
    service = context.application.bot_data["gmail"]
    try:
        ids = gmail_client.list_recent_message_ids(service, max_results=50)
    except Exception as e:  # network/auth hiccup — try again next tick
        log.warning("Gmail list failed: %s", e)
        return

    for mid in reversed(ids):  # process oldest first
        if db.transaction_exists(mid):
            continue
        try:
            body = gmail_client.get_message_body(service, mid)
            parsed = bca_parser.parse_bca_email(body)

            category = "Other"
            if not parsed.needs_review:
                category, _ = categorizer.categorize(parsed.merchant)

            txn = {
                "gmail_message_id": mid,
                "merchant": parsed.merchant,
                "amount": parsed.amount,
                "currency": parsed.currency,
                "transaction_type": parsed.transaction_type,
                "card_last4": parsed.card_last4,
                "occurred_at": parsed.occurred_at,
                "category": category,
                "needs_review": 1 if parsed.needs_review else 0,
                "raw_snippet": parsed.raw_snippet,
            }
            db.insert_transaction(txn)
            await context.bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=telegram_bot.format_alert(txn),
            )
            log.info("Alerted transaction %s (%s)", mid, parsed.merchant)
        except Exception as e:
            log.exception("Failed to process message %s: %s", mid, e)


async def weekly_summary_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_message(
        chat_id=config.TELEGRAM_CHAT_ID,
        text=summary.build_weekly_summary(previous=False),
    )


def main() -> None:
    config.validate()
    db.init_db()

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.bot_data["gmail"] = gmail_client.get_service()

    app.add_handler(CommandHandler("start", telegram_bot.cmd_start))
    app.add_handler(CommandHandler("help", telegram_bot.cmd_help))
    app.add_handler(CommandHandler("summary", telegram_bot.cmd_summary))

    jq = app.job_queue
    jq.run_repeating(poll_gmail, interval=config.POLL_INTERVAL_SECONDS, first=5)

    weekday = _DAY_MAP.get(config.WEEKLY_SUMMARY_DAY.lower(), 0)
    jq.run_daily(
        weekly_summary_job,
        time=time(
            hour=config.WEEKLY_SUMMARY_HOUR,
            minute=config.WEEKLY_SUMMARY_MINUTE,
            tzinfo=ZoneInfo(config.TIMEZONE),
        ),
        days=(weekday,),
    )

    log.info("SpendSense started. Polling Gmail every %ss.", config.POLL_INTERVAL_SECONDS)
    app.run_polling()


if __name__ == "__main__":
    main()
