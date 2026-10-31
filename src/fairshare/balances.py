"""Compute per-member balances for a group and the minimal set of payments to settle up.

Balances are net amounts in integer cents: a positive balance means the group owes that
member money (they paid more than their share); a negative balance means they owe the group.
Across a group the balances always sum to zero.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

__all__ = ["ExpenseEntry", "SettlementEntry", "Transfer", "compute_balances", "simplify_debts"]


@dataclass(frozen=True)
class ExpenseEntry:
    """One expense: who paid, and how much each participant's share is (in cents)."""

    paid_by: int
    shares: Mapping[int, int] = field(default_factory=dict)

    @property
    def amount_cents(self) -> int:
        return sum(self.shares.values())


@dataclass(frozen=True)
class SettlementEntry:
    """A direct payment from one member to another that settles debt."""

    from_user: int
    to_user: int
    amount_cents: int


@dataclass(frozen=True)
class Transfer:
    """A suggested payment: ``from_user`` should pay ``to_user`` ``amount_cents``."""

    from_user: int
    to_user: int
    amount_cents: int


def compute_balances(
    user_ids: Sequence[int],
    expenses: Sequence[ExpenseEntry],
    settlements: Sequence[SettlementEntry] = (),
) -> dict[int, int]:
    """Net balance per member. Positive = owed money, negative = owes money."""
    net = dict.fromkeys(user_ids, 0)

    for expense in expenses:
        net[expense.paid_by] = net.get(expense.paid_by, 0) + expense.amount_cents
        for uid, share in expense.shares.items():
            net[uid] = net.get(uid, 0) - share

    for s in settlements:
        # The payer reduces what they owe; the receiver reduces what they're owed.
        net[s.from_user] = net.get(s.from_user, 0) + s.amount_cents
        net[s.to_user] = net.get(s.to_user, 0) - s.amount_cents

    return net


def simplify_debts(balances: Mapping[int, int]) -> list[Transfer]:
    """Collapse balances into a minimal-ish set of payments.

    Greedily matches the biggest debtor with the biggest creditor and settles the smaller
    of the two, repeating until everyone is square. This yields at most ``n - 1`` transfers
    and, in practice, the fewest payments people actually have to make.
    """
    creditors = sorted(
        ([uid, amt] for uid, amt in balances.items() if amt > 0),
        key=lambda x: (-x[1], x[0]),
    )
    debtors = sorted(
        ([uid, -amt] for uid, amt in balances.items() if amt < 0),
        key=lambda x: (-x[1], x[0]),
    )

    transfers: list[Transfer] = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        debtor, creditor = debtors[i], creditors[j]
        pay = min(debtor[1], creditor[1])
        if pay > 0:
            transfers.append(Transfer(from_user=debtor[0], to_user=creditor[0], amount_cents=pay))
        debtor[1] -= pay
        creditor[1] -= pay
        if debtor[1] == 0:
            i += 1
        if creditor[1] == 0:
            j += 1

    return transfers
