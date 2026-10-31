"""Split an expense amount among participants, in integer cents.

Everything is done in whole cents so the shares always sum back to the exact total:
no floating-point drift, no missing or extra penny. Each strategy distributes any
leftover cents deterministically (largest-remainder method) so the result is stable
and as fair as integer money allows.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

__all__ = ["SplitError", "split_equal", "split_exact", "split_percent", "split_shares"]


class SplitError(ValueError):
    """Raised when a split request is invalid (bad total, weights or sums)."""


def _check_amount(amount_cents: int) -> None:
    if not isinstance(amount_cents, int):
        raise SplitError("amount must be an integer number of cents")
    if amount_cents <= 0:
        raise SplitError("amount must be greater than zero")


def _check_participants(user_ids: Sequence[int]) -> list[int]:
    ids = list(user_ids)
    if not ids:
        raise SplitError("an expense needs at least one participant")
    if len(set(ids)) != len(ids):
        raise SplitError("participants must be distinct")
    return ids


def split_equal(amount_cents: int, user_ids: Sequence[int]) -> dict[int, int]:
    """Split as evenly as possible; the first few participants absorb the leftover cents."""
    _check_amount(amount_cents)
    ids = _check_participants(user_ids)

    base, remainder = divmod(amount_cents, len(ids))
    order = sorted(ids)
    return {uid: base + (1 if i < remainder else 0) for i, uid in enumerate(order)}


def split_exact(amount_cents: int, shares: Mapping[int, int]) -> dict[int, int]:
    """Use caller-supplied exact cents per participant; they must sum to the total."""
    _check_amount(amount_cents)
    ids = _check_participants(list(shares))

    result = {uid: shares[uid] for uid in ids}
    if any(v < 0 for v in result.values()):
        raise SplitError("exact shares cannot be negative")
    total = sum(result.values())
    if total != amount_cents:
        raise SplitError(f"exact shares sum to {total}, expected {amount_cents}")
    return result


def split_percent(amount_cents: int, percents: Mapping[int, float]) -> dict[int, int]:
    """Split by percentage; percentages must sum to 100. Leftover cents go by largest remainder."""
    _check_amount(amount_cents)
    ids = _check_participants(list(percents))

    if any(percents[uid] < 0 for uid in ids):
        raise SplitError("percentages cannot be negative")
    total_pct = sum(percents[uid] for uid in ids)
    if abs(total_pct - 100) > 1e-6:
        raise SplitError(f"percentages sum to {total_pct}, expected 100")

    weights = {uid: percents[uid] for uid in ids}
    return _largest_remainder(amount_cents, weights, sum(weights.values()))


def split_shares(amount_cents: int, weights: Mapping[int, int]) -> dict[int, int]:
    """Split by integer shares/weights (e.g. 2:1:1). Leftover cents go by largest remainder."""
    _check_amount(amount_cents)
    ids = _check_participants(list(weights))

    if any(not isinstance(weights[uid], int) or weights[uid] <= 0 for uid in ids):
        raise SplitError("every weight must be a positive integer")
    w = {uid: weights[uid] for uid in ids}
    return _largest_remainder(amount_cents, w, sum(w.values()))


def _largest_remainder(amount_cents: int, weights: Mapping[int, float], total_weight: float) -> dict[int, int]:
    """Apportion ``amount_cents`` across ``weights`` and hand out the remainder one cent
    at a time to the entries whose exact share was most truncated (ties broken by user id)."""
    if total_weight <= 0:
        raise SplitError("total weight must be positive")

    exact = {uid: amount_cents * weight / total_weight for uid, weight in weights.items()}
    floored = {uid: int(value) for uid, value in exact.items()}
    leftover = amount_cents - sum(floored.values())

    # Give the remaining cents to the largest fractional parts first.
    ranked = sorted(
        weights,
        key=lambda uid: (exact[uid] - floored[uid], weights[uid], -uid),
        reverse=True,
    )
    for i in range(leftover):
        floored[ranked[i]] += 1
    return floored
