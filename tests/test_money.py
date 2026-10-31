from __future__ import annotations

import pytest

from fairshare.money import MoneyError, format_cents, parse_amount


@pytest.mark.parametrize(
    ("cents", "text"),
    [(0, "0.00"), (5, "0.05"), (1250, "12.50"), (100000, "1000.00"), (-500, "-5.00")],
)
def test_format_cents(cents, text):
    assert format_cents(cents) == text


@pytest.mark.parametrize(
    ("text", "cents"),
    [("12.50", 1250), ("12", 1200), ("0.05", 5), ("1,000.00", 100000), (" 7.99 ", 799)],
)
def test_parse_amount(text, cents):
    assert parse_amount(text) == cents


@pytest.mark.parametrize("text", ["", "   ", "abc", "-5", "0", "1.234", "1.2.3"])
def test_parse_amount_rejects_bad_input(text):
    with pytest.raises(MoneyError):
        parse_amount(text)


def test_round_trip():
    # parse_amount only accepts positive amounts, so round-trip the positive values.
    for cents in (1, 99, 100, 123456):
        assert parse_amount(format_cents(cents)) == cents
