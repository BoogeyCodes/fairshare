"""Convert between integer cents (how money is stored) and human strings."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

__all__ = ["MoneyError", "format_cents", "parse_amount"]


class MoneyError(ValueError):
    """Raised when a money string can't be parsed."""


def format_cents(cents: int) -> str:
    """``1250`` -> ``"12.50"``; negatives keep their sign (``-500`` -> ``"-5.00"``)."""
    sign = "-" if cents < 0 else ""
    whole, frac = divmod(abs(cents), 100)
    return f"{sign}{whole}.{frac:02d}"


def parse_amount(text: str) -> int:
    """Parse a positive money string like ``"12.50"`` or ``"12"`` into cents.

    Rejects blanks, non-numbers, negatives and zero, and more than two decimal places.
    """
    if text is None:
        raise MoneyError("amount is required")
    cleaned = str(text).strip().replace(",", "")
    if not cleaned:
        raise MoneyError("amount is required")
    try:
        value = Decimal(cleaned)
    except InvalidOperation as exc:
        raise MoneyError(f"'{text}' is not a valid amount") from exc

    if value <= 0:
        raise MoneyError("amount must be greater than zero")
    if -value.as_tuple().exponent > 2:
        raise MoneyError("amount can have at most two decimal places")

    cents = int((value * 100).to_integral_value(rounding=ROUND_HALF_UP))
    return cents
