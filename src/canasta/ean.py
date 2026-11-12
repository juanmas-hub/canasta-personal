"""GS1 check-digit validation for EAN/UPC/GTIN codes."""

from __future__ import annotations


def gs1_check_digit(payload: str) -> int:
    """Return the GS1 check digit for a numeric payload without the check digit."""
    total = 0
    for index, char in enumerate(reversed(payload)):
        weight = 3 if index % 2 == 0 else 1
        total += int(char) * weight
    return (10 - total % 10) % 10


def _valid(code: str) -> bool:
    return code.isdigit() and len(code) > 1 and gs1_check_digit(code[:-1]) == int(code[-1])


def is_valid_ean(code: str) -> bool:
    """Validate EAN-8/13, UPC-A and GTIN-14, including zero-padded short codes.

    ``id_producto`` is always 13 digits in SEPA. A real EAN-8 or UPC-A can arrive
    zero-padded to 13 digits; if the 13-digit check fails, the suffix is tried.
    """
    code = code.strip()
    if not code.isdigit() or set(code) == {"0"}:
        return False
    if len(code) in (8, 12, 13, 14) and _valid(code):
        return True
    if len(code) == 13:
        if code.startswith("00000") and _valid(code[-8:]):
            return True
        if code.startswith("0") and _valid(code[-12:]):
            return True
    return False
