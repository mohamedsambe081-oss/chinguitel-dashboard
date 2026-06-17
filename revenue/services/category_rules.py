from __future__ import annotations

import re

CATEGORY_ORDER = ["DATA", "VOICE", "MIX", "SMS", "others"]

CATEGORY_KEYWORDS = {
    "DATA": ["maurinet", "1 year data", "internet", "net", "unlimited"],
    "VOICE": ["allo", "mauri allo", "internat", "mauriallo", "voice"],
    "MIX": ["mauri attay", "mauri mix", "maurimix", "mix"],
    "SMS": ["chat", "mauri chat", "maurichat"],
}

# Exact / special names supplied by the business user.
# Keys are normalized with _norm(), so spaces, '_' and '-' differences are ignored.
SPECIAL_PACKAGE_NAMES = {
    # Mauri Mix long bundle names
    "mauri mix bonus 144 voice mauri mix offer 20h 334 internet mauri mix offer 20gb 344 sms mauri mix offer 500 sms 352": "Mix 1000",
    "mauri mix bonus 140 voice mauri mix offer 1h 30min 330 internet mauri mix offer 2 gb 340 sms mauri mix offer 100 sms 348": "Mix 100",
    "mauri mix bonus 141 voice mauri mix offer 3h 331 internet mauri mix offer 4gb 341 sms mauri mix offer 200 sms 349": "Mix 200",
    "mauri mix bonus 142 voice mauri mix offer 5h 332 internet mauri mix offer 6gb sms mauri mix offer 300 sms 350": "Mix 300",
    "mauri mix bonus 143 voice mauri mix offer 10h 333 internet mauri mix offer 10gb 343 sms mauri mix offer 500 sms 351": "Mix 500",
    "voice mauri mix 50 vc sms mauri mix 50 vc internet mauri mix 50 vc": "Mix 50",
    "mauri mix offer 10h 10gb 500sms 500mru": "Mix 500",
    "mauri mix offer 1h 30min 2gb 100sms 100mru": "Mix 100",
    "mauri mix offer 3h 4gb 200sms 200mru": "Mix 200",
    "mauri mix offer 40 min 512 mb 40 sms": "Mix 40",
    "maurimix 70 data voice mauri mix 70 maurimix 70 sms maurimix bonus 70": "Mix 70",

    # Mauri Attay bundle names
    "mauri attay offer 1500 sec 300 mb 25 sms": "Attay 25",
    "mauri attay offer 450 sec 100 mb 5 sms": "Attay 5",
    "mauri attay offer 900 sec 200 mb 15 sms": "Attay 15",
    "voice mauri attay 10 vc sms mauri attay 10 vc internet mauri attay 10 vc": "Attay 10",
    "voice mauri attay 20 vc sms mauri attay 20 vc internet mauri attay 20 vc": "Attay 20",
    "voice mauri attay 30 vc sms mauri attay 30 vc internet mauri attay 30 vc": "Attay 30",

    # Previous special cases requested by the user
    "mauri allo promo vc": "Allo 50",
    "mauri allo promo": "Allo 50",
    "maurinet 1gb": "Net 40",
    "maurinet promo": "Net 20",
    "mari mix 150": "Mix 150",
}


def _norm(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[;:/,()\[\]_\-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _compact(value: str) -> str:
    return _norm(value).replace(" ", "")


def _extract_price(text: str, compact: str) -> str | None:
    """Extract the commercial price from a package name."""
    # Most long names contain the real price as 100MRU / 500MRU.
    m = re.search(r"(\d+)\s*mru\b", text)
    if m:
        return m.group(1)

    # Common explicit package names: Mix 100, Mauri Mix 70, Net 20, Allo 50, Chat 10...
    patterns = [
        r"\bmauri\s*mix\s*(\d+)\b",
        r"\bmaurimix\s*(\d+)\b",
        r"\bmix\s*(\d+)\b",
        r"\bmauri\s*attay\s*(\d+)\b",
        r"\bmauriattay\s*(\d+)\b",
        r"\battay\s*(\d+)\b",
        r"\bmauri\s*allo\s*(\d+)\b",
        r"\bmauriallo\s*(\d+)\b",
        r"\ballo\s*(\d+)\b",
        r"\bmauri\s*chat\s*(\d+)\b",
        r"\bmaurichat\s*(\d+)\b",
        r"\bchat\s*(\d+)\b",
        r"\bmaurinet\s*(\d+)\b",
        r"\bnet\s*(\d+)\b",
        r"\binternet\s*(\d+)\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(1)

    # Old bundle component codes often end with the commercial code/price.
    # Example: maurimix_bonus_70 -> 70.
    if "maurimix" in compact or "mauriallo" in compact or "maurichat" in compact or "maurinet" in compact:
        nums = re.findall(r"\d+", text)
        if nums:
            return nums[-1]

    return None


def standardize_package_name(package: str) -> str:
    """Convert long technical package names into business names used in charts/tables.

    Examples:
    - long Mauri Mix bundle -> Mix 100 / Mix 200 / Mix 500
    - Maurinet / Internet / Net offers -> Net <price>
    - MauriAllo / Voice / Allo offers -> Allo <price>
    - MauriChat / Chat offers -> Chat <price>
    - Mauri Attay offers -> Mix <price>
    """
    original = str(package or "").strip()
    text = _norm(original)
    compact = text.replace(" ", "")

    if text in SPECIAL_PACKAGE_NAMES:
        return SPECIAL_PACKAGE_NAMES[text]

    if text == "mauri allo":
        return "Allo 70"

    # Promo Allo names do not always contain the price, but business rule = Allo 50.
    if "allo" in text and "promo" in text:
        return "Allo 50"

    # Promo Maurinet / 1GB names do not always contain the commercial price.
    if "maurinet" in compact and "promo" in text:
        return "Net 20"
    if "maurinet" in compact and re.search(r"\b1\s*gb\b", text):
        return "Net 40"

    # Mauri Attay is a mixed bundle, so it must be converted to Mix <price> before
    # the generic Voice/Internet detection, because these long labels contain both words.
    if "mauriattay" in compact or "mauri attay" in text:
        if "450 sec" in text or "5 sms" in text:
            return "Attay 5"
        if "900 sec" in text or "15 sms" in text:
            return "Attay 15"
        if "1500 sec" in text or "25 sms" in text:
            return "Attay 25"
        price = _extract_price(text, compact)
        return f"Attay {price}" if price else original

    # MIX first because long Mix names contain Voice/Internet/SMS words too.
    if "maurimix" in compact or "mauri mix" in text or "mari mix" in text or re.search(r"\bmix\s*\d+\b", text):
        price = _extract_price(text, compact)
        return f"Mix {price}" if price else original

    # DATA / Internet / MauriNet -> Net <price>
    if "maurinet" in compact or "internet" in text or re.search(r"(^|\s)net(\s|\d|$)", text):
        price = _extract_price(text, compact)
        return f"Net {price}" if price else original

    # VOICE / MauriAllo -> Allo <price>
    if "mauriallo" in compact or "mauri allo" in text or "allo" in text or "voice" in text:
        price = _extract_price(text, compact)
        return f"Allo {price}" if price else original

    # SMS / MauriChat -> Chat <price>
    if "maurichat" in compact or "mauri chat" in text or "chat" in text:
        price = _extract_price(text, compact)
        return f"Chat {price}" if price else original

    return original


def infer_category(package: str) -> str:
    text = _norm(package)
    compact = text.replace(" ", "")

    if re.search(r"\bmix\b", text) or "maurimix" in compact or "mauri mix" in text or "mari mix" in text or "mauriattay" in compact or "mauri attay" in text:
        return "MIX"

    if (
        "maurinet" in compact
        or "1 year data" in text
        or "internet" in text
        or "unlimited" in text
        or re.search(r"(^|\s)net(\s|\d|$)", text)
    ):
        return "DATA"

    if (
        "mauriallo" in compact
        or "mauri allo" in text
        or "allo" in text
        or "internat" in text
        or "voice" in text
    ):
        return "VOICE"

    if "maurichat" in compact or "mauri chat" in text or "chat" in text:
        return "SMS"

    return "others"


def sync_existing_record_categories(batch_size: int = 1000) -> int:
    """Update already imported records to the current business categories and short names."""
    from revenue.models import RevenueRecord

    changed = []
    total = 0
    for record in RevenueRecord.objects.only("id", "package", "category").iterator(chunk_size=batch_size):
        new_package = standardize_package_name(record.package)
        new_category = infer_category(new_package)
        if record.package != new_package or record.category != new_category:
            record.package = new_package
            record.category = new_category
            changed.append(record)
            total += 1
            if len(changed) >= batch_size:
                RevenueRecord.objects.bulk_update(changed, ["package", "category"], batch_size=batch_size)
                changed.clear()
    if changed:
        RevenueRecord.objects.bulk_update(changed, ["package", "category"], batch_size=batch_size)
    return total
