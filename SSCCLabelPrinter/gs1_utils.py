"""
gs1_utils.py
GS1 Application Identifier (AI) helpers: check-digit calculation, field
formatting, bracketed-AI element string construction, and GS1 Digital Link
URI construction.
"""

from urllib.parse import quote


class GS1FormatError(Exception):
    """Raised when GS1 data cannot be formatted/validated."""
    pass


def calculate_gs1_check_digit(digits):
    """
    Standard GS1 Modulo-10 check digit algorithm.
    `digits` is a string of digits WITHOUT the check digit.
    Returns the single check-digit character.
    """
    if not digits or not digits.isdigit():
        raise GS1FormatError(f"Cannot calculate check digit for non-numeric value: {digits!r}")

    total = 0
    # Weighting starts from the rightmost digit: 3,1,3,1,... from the right.
    reversed_digits = digits[::-1]
    for i, ch in enumerate(reversed_digits):
        weight = 3 if i % 2 == 0 else 1
        total += int(ch) * weight

    check_digit = (10 - (total % 10)) % 10
    return str(check_digit)


def format_gtin(raw):
    """
    Accepts an 8/12/13/14-digit GTIN.
    - If 13 or fewer digits are given without an obvious check digit
      convention, we assume the value is already complete (as typically
      supplied on a spreadsheet) and simply zero-pad to 14 digits (AI 01
      always carries a 14-digit GTIN).
    - Does NOT recalculate the check digit for GTIN (spreadsheets nearly
      always contain validated, already-correct GTINs); if you need
      validation, verify upstream.
    """
    raw = str(raw).strip()
    if not raw.isdigit():
        raise GS1FormatError(f"GTIN must be numeric: {raw!r}")
    if len(raw) > 14:
        raise GS1FormatError(f"GTIN too long ({len(raw)} digits): {raw!r}")
    return raw.zfill(14)


def format_sscc(raw):
    """
    Accepts either:
      - 17 digits: extension digit + GS1 Company Prefix + Serial Reference
        (no check digit yet) -> we calculate and append the check digit.
      - 18 digits: already includes a check digit -> we validate it.
    Returns the complete 18-digit SSCC.
    """
    raw = str(raw).strip()
    if not raw.isdigit():
        raise GS1FormatError(f"SSCC must be numeric: {raw!r}")

    if len(raw) == 17:
        check = calculate_gs1_check_digit(raw)
        return raw + check
    elif len(raw) == 18:
        body, supplied_check = raw[:-1], raw[-1]
        expected_check = calculate_gs1_check_digit(body)
        if supplied_check != expected_check:
            raise GS1FormatError(
                f"SSCC check digit mismatch for {raw!r}: "
                f"expected {expected_check}, got {supplied_check}"
            )
        return raw
    else:
        raise GS1FormatError(f"SSCC must be 17 or 18 digits, got {len(raw)}: {raw!r}")


def format_expiry(raw):
    """
    Accepts a date and returns YYMMDD (AI 17 format).
    Accepts: YYMMDD (passthrough if already 6 digits), YYYY-MM-DD,
    DD/MM/YYYY, MM/DD/YYYY (best-effort), or a datetime/date object.
    """
    import datetime as _dt

    if isinstance(raw, (_dt.date, _dt.datetime)):
        return raw.strftime("%y%m%d")

    s = str(raw).strip()
    if s.isdigit() and len(s) == 6:
        return s

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            dt = _dt.datetime.strptime(s, fmt)
            return dt.strftime("%y%m%d")
        except ValueError:
            continue

    raise GS1FormatError(f"Could not parse expiry date: {raw!r}")


def format_alnum(raw, max_len=None):
    """Generic alphanumeric field formatter (batch/lot, serial, etc.)."""
    s = str(raw).strip()
    if max_len and len(s) > max_len:
        raise GS1FormatError(f"Value too long (max {max_len}): {s!r}")
    return s


def format_quantity(raw, length=2):
    """Formats a numeric quantity field, zero-padded to `length` digits."""
    s = str(raw).strip()
    if not s.isdigit():
        raise GS1FormatError(f"Quantity must be numeric: {raw!r}")
    if len(s) > length:
        raise GS1FormatError(f"Quantity too long (max {length} digits): {s!r}")
    return s.zfill(length)


# ---------------------------------------------------------------------------
# AI maps
# ---------------------------------------------------------------------------

# GTIN-based product labels
SUPPORTED_AIS = {
    "GTIN":     {"ai": "01", "formatter": format_gtin},
    "BATCH":    {"ai": "10", "formatter": format_alnum},
    "EXPIRY":   {"ai": "17", "formatter": format_expiry},
    "SERIAL":   {"ai": "21", "formatter": format_alnum},
    "QUANTITY": {"ai": "30", "formatter": format_quantity},
}

# SSCC-based logistics/pallet labels
SUPPORTED_AIS_SSCC = {
    "SSCC":         {"ai": "00", "formatter": format_sscc},
    "CONTENT_GTIN": {"ai": "02", "formatter": format_gtin},
    "BATCH":        {"ai": "10", "formatter": format_alnum},
    "EXPIRY":       {"ai": "17", "formatter": format_expiry},
    "COUNT":        {"ai": "37", "formatter": format_quantity},
}


def build_gs1_string(field_values, raw_extra="", ai_map=None):
    """
    Builds a bracketed-AI GS1 element string, e.g.:
        (01)00012345678905(10)LOT123(17)251231

    `field_values` is a dict of logical field name -> raw value
    (e.g. {"GTIN": "...", "BATCH": "...", ...}). Missing/blank fields
    are skipped.

    `raw_extra` is an optional string of ADDITIONAL bracketed AI data the
    user typed directly (must already be in "(AI)value(AI)value..." form).

    `ai_map` selects which AI dictionary to use (defaults to SUPPORTED_AIS,
    the GTIN map); pass SUPPORTED_AIS_SSCC for SSCC labels.
    """
    if ai_map is None:
        ai_map = SUPPORTED_AIS

    parts = []
    for field_name, spec in ai_map.items():
        value = field_values.get(field_name)
        if value is None or str(value).strip() == "":
            continue
        formatted = spec["formatter"](value)
        parts.append(f"({spec['ai']}){formatted}")

    if raw_extra and raw_extra.strip():
        extra = raw_extra.strip()
        if not extra.startswith("("):
            raise GS1FormatError(
                f"Extra AI data must start with '(' e.g. (91)TEXT -- got: {extra!r}"
            )
        parts.append(extra)

    if not parts:
        raise GS1FormatError("No GS1 data supplied for this row")

    return "".join(parts)


def build_digital_link_uri(field_values, raw_extra="", ai_map=None,
                            domain="https://id.gs1.org"):
    """
    Builds a GS1 Digital Link URI, e.g.:
        https://id.gs1.org/01/00012345678905/10/LOT123?17=251231

    Primary identifier AIs (01/00 for GTIN/SSCC) go in the URI path;
    qualifier/attribute AIs are appended as query parameters, per the
    GS1 Digital Link standard's simple default ordering.
    """
    if ai_map is None:
        ai_map = SUPPORTED_AIS

    if not domain or not domain.strip():
        raise GS1FormatError("Digital Link domain cannot be empty")
    domain = domain.strip().rstrip("/")

    # Primary identifiers that anchor the URI path (checked in priority order)
    primary_ai_order = ["01", "00"]  # GTIN, SSCC

    path_ai = None
    path_value = None
    query_parts = []

    # First pass: find the primary identifier
    collected = []
    for field_name, spec in ai_map.items():
        value = field_values.get(field_name)
        if value is None or str(value).strip() == "":
            continue
        formatted = spec["formatter"](value)
        collected.append((spec["ai"], formatted))

    for ai_code in primary_ai_order:
        for ai, val in collected:
            if ai == ai_code:
                path_ai, path_value = ai, val
                break
        if path_ai:
            break

    if path_ai is None:
        # Fall back to whichever AI came first if no recognised primary
        if collected:
            path_ai, path_value = collected[0]
            collected = collected[1:]
        else:
            path_ai = None

    for ai, val in collected:
        if ai == path_ai and val == path_value:
            continue
        query_parts.append(f"{ai}={quote(val, safe='')}")

    if path_ai is None and not query_parts:
        raise GS1FormatError("No GS1 data supplied for this row")

    if path_ai is not None:
        uri = f"{domain}/{path_ai}/{quote(path_value, safe='')}"
    else:
        uri = domain

    if raw_extra and raw_extra.strip():
        extra = raw_extra.strip()
        query_parts.append(extra.lstrip("?&"))

    if query_parts:
        uri += "?" + "&".join(query_parts)

    return uri
