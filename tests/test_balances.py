from __future__ import annotations

from fairshare.balances import (
    ExpenseEntry,
    SettlementEntry,
    compute_balances,
    simplify_debts,
)


def test_balances_net_to_zero():
    # Alice(1) pays 30.00 split equally three ways; Bob(2) pays 9.00 split equally.
    expenses = [
        ExpenseEntry(paid_by=1, shares={1: 1000, 2: 1000, 3: 1000}),
        ExpenseEntry(paid_by=2, shares={1: 300, 2: 300, 3: 300}),
    ]
    net = compute_balances([1, 2, 3], expenses)
    assert sum(net.values()) == 0
    # Alice(1): paid 3000, owes 1000+300=1300 -> net +1700
    # Bob(2): paid 900, owes 1000+300=1300 -> net -400
    # Carol(3): paid 0, owes 1300 -> net -1300
    assert net == {1: 1700, 2: -400, 3: -1300}


def test_settlement_moves_balance_toward_zero():
    expenses = [ExpenseEntry(paid_by=1, shares={1: 500, 2: 500})]  # Bob owes Alice 500
    net = compute_balances([1, 2], expenses, [SettlementEntry(from_user=2, to_user=1, amount_cents=500)])
    assert net == {1: 0, 2: 0}


def test_simplify_two_debtors_one_creditor():
    transfers = simplify_debts({1: 1500, 2: -1000, 3: -500})
    assert sum(t.amount_cents for t in transfers) == 1500
    assert {(t.from_user, t.to_user, t.amount_cents) for t in transfers} == {
        (2, 1, 1000),
        (3, 1, 500),
    }


def test_simplify_collapses_a_chain():
    # A owes B 10, B owes C 10  ->  net A:-10, B:0, C:+10  ->  A pays C directly.
    transfers = simplify_debts({1: -1000, 2: 0, 3: 1000})
    assert len(transfers) == 1
    assert (transfers[0].from_user, transfers[0].to_user, transfers[0].amount_cents) == (1, 3, 1000)


def test_simplify_uses_at_most_n_minus_one_transfers():
    balances = {1: 500, 2: 500, 3: -300, 4: -700}
    transfers = simplify_debts(balances)
    assert len(transfers) <= len(balances) - 1
    # every debt is cleared
    net = dict(balances)
    for t in transfers:
        net[t.from_user] += t.amount_cents
        net[t.to_user] -= t.amount_cents
    assert all(v == 0 for v in net.values())


def test_everyone_settled_gives_no_transfers():
    assert simplify_debts({1: 0, 2: 0}) == []
