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


def month_bounds(reference: datetime | None = None, previous: bool = False):
    """Return (start, end) datetimes for a first-of-month -> first-of-next-month window."""
    now = reference or datetime.now(TZ)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # Advance one month (wrap December → January)
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1)
    else:
        next_month = start.replace(month=start.month + 1)
    if previous:
        # shift both boundaries back one month
        return month_bounds(start - timedelta(days=1), previous=False)
    return start, next_month


def format_rupiah(amount: float) -> str:
    # Indonesian grouping uses '.' as the thousands separator.
    return "Rp " + f"{int(round(amount)):,}".replace(",", ".")


def build_weekly_summary(previous: bool = False) -> str:
    start, end = week_bounds(previous=previous)
    rows = db.get_summary_between(start.isoformat(), end.isoformat())
    label = f"{start.strftime('%d %b')} – {(end - timedelta(days=1)).strftime('%d %b %Y')}"

    if not rows:
        return f"📊 Weekly Summary\n🗓 {label}\n\nNo transactions recorded this week."

    total = sum(r["total"] for r in rows)
    count = sum(r["n"] for r in rows)

    lines = [
        "📊 Weekly Summary",
        f"🗓 {label}",
        "",
        f"💳 Total spent: {format_rupiah(total)} ({count} transactions)",
        "",
        "By category:",
    ]

    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(rows):
        pct = (r["total"] / total * 100) if total else 0
        prefix = medals[i] if i < 3 else "   •"
        lines.append(f"{prefix} {r['category']}: {format_rupiah(r['total'])} ({pct:.0f}%, {r['n']}x)")

    return "\n".join(lines)


def build_monthly_summary(previous: bool = False) -> str:
    start, end = month_bounds(previous=previous)
    rows = db.get_summary_between(start.isoformat(), end.isoformat())
    label = start.strftime("%B %Y")

    if not rows:
        return f"📅 Monthly Summary\n🗓 {label}\n\nNo transactions recorded this month."

    total = sum(r["total"] for r in rows)
    count = sum(r["n"] for r in rows)

    lines = [
        "📅 Monthly Summary",
        f"🗓 {label}",
        "",
        f"💳 Total spent: {format_rupiah(total)} ({count} transactions)",
        "",
        "By category:",
    ]

    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(rows):
        pct = (r["total"] / total * 100) if total else 0
        prefix = medals[i] if i < 3 else "   •"
        lines.append(f"{prefix} {r['category']}: {format_rupiah(r['total'])} ({pct:.0f}%, {r['n']}x)")

    return "\n".join(lines)
