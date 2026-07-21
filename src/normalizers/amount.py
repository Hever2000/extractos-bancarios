from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from src.models.errors import ParseError
from src.models.statement import Amount, Sign


def normalize_amount(raw: str | None) -> Amount:
    if raw is None or raw.strip() == "":
        return Amount.zero()

    val = raw.strip()
    val = val.replace("$", "").strip()

    if not val:
        return Amount.zero()

    sign: Sign = Sign(1)

    if val.startswith("(") and val.endswith(")"):
        sign = Sign(-1)
        val = val[1:-1]

    elif val.startswith("-"):
        sign = Sign(-1)
        val = val[1:]

    elif val.endswith("-"):
        sign = Sign(-1)
        val = val[:-1]

    if not val or val in ("0", "-0"):
        return Amount.zero()

    if "," in val:
        val = val.replace(".", "")
        val = val.replace(",", ".")
    else:
        val = val.replace(" ", "")

    val = re.sub(r"[^0-9.\-]", "", val)

    try:
        decimal_val = Decimal(val)
    except InvalidOperation:
        raise ParseError(f"Cannot parse amount: '{raw}'", detail=val)

    return Amount(value=abs(decimal_val), sign=sign)
