from pathlib import Path

from src.bca_parser import parse_bca_email

SAMPLE = (Path(__file__).parent / "sample_email.txt").read_text()


def test_parses_known_fields():
    p = parse_bca_email(SAMPLE)
    assert p.merchant == "SKS MKG"
    assert p.amount == 354200.00
    assert p.currency == "IDR"
    assert p.transaction_type == "DOMESTIK"
    assert p.card_last4 == "8545"
    assert p.occurred_at.startswith("2026-05-31T11:44:07")
    assert p.needs_review is False


def test_amount_indonesian_format():
    # decimals use ',' and thousands use '.'
    from src.bca_parser import _parse_amount
    assert _parse_amount("Rp1.234.567,89") == 1234567.89
    assert _parse_amount("Rp354.200,00") == 354200.00


def test_unparseable_flags_review():
    p = parse_bca_email("Some unrelated email with no transaction fields.")
    assert p.needs_review is True
    assert p.amount is None
