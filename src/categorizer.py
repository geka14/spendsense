"""Assign a spending category to a merchant.

Order: learned DB mapping -> seed substring rules -> optional Claude fallback -> 'Other'.
"""
from . import config, db

CATEGORIES = [
    "Groceries", "Dining", "Transport", "Shopping", "Bills & Utilities",
    "Entertainment", "Health", "Travel", "Cash/ATM", "Other",
]

# Starter rules: UPPERCASE substring -> category. Extend freely as you learn your merchants.
SEED_RULES: dict[str, str] = {
    "INDOMARET": "Groceries", "ALFAMART": "Groceries", "SUPERINDO": "Groceries",
    "HYPERMART": "Groceries", "TRANSMART": "Groceries", "RANCH MARKET": "Groceries",
    "GRAB": "Transport", "GOJEK": "Transport", "GO-JEK": "Transport",
    "BLUEBIRD": "Transport", "PERTAMINA": "Transport", "SHELL": "Transport",
    "MCDONALD": "Dining", "KFC": "Dining", "STARBUCKS": "Dining",
    "GOFOOD": "Dining", "GRABFOOD": "Dining", "BURGER KING": "Dining",
    "SHOPEE": "Shopping", "TOKOPEDIA": "Shopping", "LAZADA": "Shopping",
    "UNIQLO": "Shopping", "BLIBLI": "Shopping",
    "PLN": "Bills & Utilities", "TELKOMSEL": "Bills & Utilities",
    "INDIHOME": "Bills & Utilities", "PDAM": "Bills & Utilities",
    "BPJS": "Health", "KIMIA FARMA": "Health", "GUARDIAN": "Health", "APOTEK": "Health",
    "NETFLIX": "Entertainment", "SPOTIFY": "Entertainment",
    "CGV": "Entertainment", "CINEMA XXI": "Entertainment",
    "TARIKAN TUNAI": "Cash/ATM", "TUNAI": "Cash/ATM",
}


def _normalize(merchant: str | None) -> str:
    return merchant.upper().strip() if merchant else ""


def categorize(merchant: str | None) -> tuple[str, str]:
    """Return (category, source). source in {db, rule, llm, default}."""
    norm = _normalize(merchant)
    if not norm:
        return "Other", "default"

    learned = db.get_category_for_merchant(norm)
    if learned:
        return learned, "db"

    # Check the most specific (longest) patterns first so e.g. "GRABFOOD" (Dining)
    # is matched before "GRAB" (Transport).
    for pattern in sorted(SEED_RULES, key=len, reverse=True):
        if pattern in norm:
            return SEED_RULES[pattern], "rule"

    if config.USE_LLM_CATEGORIZATION:
        guess = llm_categorize(merchant)
        if guess:
            db.upsert_merchant_category(norm, guess, source="llm")
            return guess, "llm"

    return "Other", "default"


def llm_categorize(merchant: str | None) -> str | None:
    """Optional: ask Claude to pick one category. Returns None if disabled/unavailable."""
    if not merchant or not config.ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        prompt = (
            "Classify this Indonesian merchant into exactly one of these categories: "
            + ", ".join(CATEGORIES)
            + f'.\nMerchant: "{merchant}".\nReply with only the category name.'
        )
        msg = client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=16,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            b.text for b in msg.content if getattr(b, "type", "") == "text"
        ).strip()
        return text if text in CATEGORIES else None
    except Exception:
        return None
