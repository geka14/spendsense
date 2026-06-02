"""Parser for BCA credit card transaction notification emails.

The email uses a fixed "Label : value" layout. We extract the value on the line that
contains each label. Pure functions — safe to unit test (see tests/test_parser.py).
"""
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from . import config

TZ = ZoneInfo(config.TIMEZONE)

# Label regexes (the value is whatever follows the colon on the same line).
LABEL_NOMOR_KARTU = r"Nomor Kartu"
LABEL_MERCHANT = r"Merchant\s*/\s*ATM"
LABEL_TXN_TYPE = r"Jenis Transaksi"
LABEL_DATE = r"Pada Tanggal"
LABEL_AMOUNT = r"Sejumlah"


@dataclass
class ParsedTransaction:
    merchant: str | None
    amount: float | None
    currency: str
    transaction_type: str | None
    card_last4: str | None
    occurred_at: str | None  # ISO-8601 with Asia/Jakarta offset
    needs_review: bool
    raw_snippet: str | None
    is_reversal: bool = False


def html_to_text(html: str) -> str:
    return BeautifulSoup(html, "html.parser").get_text("\n")


def _value_after_label(text: str, label_regex: str) -> str | None:
    m = re.search(label_regex + r"\s*:\s*(.+)", text)
    return m.group(1).strip() if m else None


def _parse_amount(raw: str | None) -> float | None:
    # "Rp354.200,00" -> 354200.00  (Indonesian: '.' thousands, ',' decimals)
    if not raw:
        return None
    digits = re.sub(r"[^0-9.,]", "", raw)
    normalized = digits.replace(".", "").replace(",", ".")
    try:
        return float(Decimal(normalized))
    except (InvalidOperation, ValueError):
        return None


def _parse_date(raw: str | None) -> str | None:
    # "31-05-2026 11:44:07 WIB" -> ISO-8601 in Asia/Jakarta
    if not raw:
        return None
    m = re.search(r"(\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}:\d{2})", raw)
    if not m:
        return None
    try:
        dt = datetime.strptime(m.group(1), "%d-%m-%Y %H:%M:%S").replace(tzinfo=TZ)
        return dt.isoformat()
    except ValueError:
        return None


def _redact(text: str) -> str:
    # Never keep the customer number, even in the needs_review snippet.
    return re.sub(r"(Nomor Customer\s*:\s*)\S+", r"\1[REDACTED]", text)


def parse_bca_email(html_or_text: str) -> ParsedTransaction:
    text = html_to_text(html_or_text) if "<" in html_or_text else html_or_text

    is_reversal = "reversal/void" in text.lower()

    merchant = _value_after_label(text, LABEL_MERCHANT)
    amount = _parse_amount(_value_after_label(text, LABEL_AMOUNT))
    occurred_at = _parse_date(_value_after_label(text, LABEL_DATE))
    txn_type = _value_after_label(text, LABEL_TXN_TYPE)

    nomor_kartu = _value_after_label(text, LABEL_NOMOR_KARTU)
    digits = re.sub(r"[^0-9X]", "", nomor_kartu) if nomor_kartu else ""
    card_last4 = digits[-4:] if digits else None

    # Required fields for a clean record.
    needs_review = not (merchant and amount is not None and occurred_at)
    snippet = _redact(text)[:1000] if needs_review else None

    return ParsedTransaction(
        merchant=merchant,
        amount=amount,
        currency="IDR",
        transaction_type=txn_type,
        card_last4=card_last4,
        occurred_at=occurred_at,
        needs_review=needs_review,
        raw_snippet=snippet,
        is_reversal=is_reversal,
    )
