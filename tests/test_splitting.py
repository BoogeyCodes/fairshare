from __future__ import annotations

import pytest

from fairshare.splitting import SplitError, split_equal, split_exact, split_percent, split_shares


def test_equal_split_sums_exactly_and_spreads_the_remainder():
    shares = split_equal(1000, [1, 2, 3])
    assert sum(shares.values()) == 1000
    assert shares == {1: 334, 2: 333, 3: 333}  # first (by id) absorbs the extra cent


def test_equal_split_is_independent_of_input_order():
    assert split_equal(1000, [3, 1, 2]) == split_equal(1000, [1, 2, 3])


def test_exact_split_requires_the_sum_to_match():
    assert split_exact(1000, {1: 600, 2: 400}) == {1: 600, 2: 400}
    with pytest.raises(SplitError):
        split_exact(1000, {1: 600, 2: 300})
    with pytest.raises(SplitError):
        split_exact(1000, {1: 1100, 2: -100})


def test_percent_split_apportions_by_largest_remainder():
    # 33.333 / 33.333 / 33.334 of 1000 -> 333 / 333 / 334 (the last keeps the cent)
    shares = split_percent(1000, {1: 33.333, 2: 33.333, 3: 33.334})
    assert sum(shares.values()) == 1000
    assert shares == {1: 333, 2: 333, 3: 334}


def test_percent_split_breaks_ties_deterministically():
    shares = split_percent(1001, {1: 50, 2: 50})
    assert sum(shares.values()) == 1001
    assert shares == {1: 501, 2: 500}


def test_percent_must_sum_to_100():
    with pytest.raises(SplitError):
        split_percent(1000, {1: 40, 2: 40})


def test_shares_split_is_proportional():
    shares = split_shares(1000, {1: 2, 2: 1, 3: 1})
    assert shares == {1: 500, 2: 250, 3: 250}


def test_shares_require_positive_integer_weights():
    with pytest.raises(SplitError):
        split_shares(1000, {1: 0, 2: 1})
    with pytest.raises(SplitError):
        split_shares(1000, {1: 1.5, 2: 1})  # type: ignore[dict-item]


@pytest.mark.parametrize("func", [split_equal, split_exact, split_percent, split_shares])
def test_amount_must_be_positive(func):
    with pytest.raises(SplitError):
        func(0, {1: 1} if func is not split_equal else [1])


def test_participants_must_be_distinct_and_present():
    with pytest.raises(SplitError):
        split_equal(100, [])
    with pytest.raises(SplitError):
        split_equal(100, [1, 1])
