"""Weekly summary: compute week ranges and build the Telegram summary text."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import config, db

TZ = ZoneInfo(config.TIMEZONE)


def week_bounds(reference: datetime | None = None, previous: bool = False):
    """Return (start, end) datetimes for a Mon 00:00 -> next Mon 00:00 window."""
    now = reference or datetime.now(TZ)
    monday = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    if previous:
        return monday - timedelta(days=7), monday
    return monday, monday + timedelta(days=7)


def format_rupiah(amount: float) -> str:
    # Indonesian grouping uses '.' as the thousands separator.
    return "Rp " + f"{int(round(amount)):,}".replace(",", ".")


def build_weekly_summary(previous: bool = False) -> str:
    start, end = week_bounds(previous=previous)
    rows = db.get_summary_between(start.isoformat(), end.isoformat())
    label = f"{start.strftime('%d %b')} – {(end - timedelta(days=1)).strftime('%d %b %Y')}"

    if not rows:
        return f"🗓 Weekly summary ({label})\nNo transactions recorded."

    total = sum(r["total"] for r in rows)
    lines = [f"🗓 Weekly summary ({label})", ""]
    for r in rows:
        pct = (r["total"] / total * 100) if total else 0
        lines.append(f"• {r['category']}: {format_rupiah(r['total'])} ({pct:.0f}%, {r['n']}x)")
    count = sum(r["n"] for r in rows)
    lines += ["", f"Total: {format_rupiah(total)} across {count} transactions"]
    return "\n".join(lines)
