"""
The wallets correctness GATE (Layer 1).

Asserts the system invariant against hand-built data, with NO network access:

    Σ(active wallet balances) + unassigned == current_balance

where all three are computed over the same horizon (post balance-anchor movements)
with manual_balance as the Unassigned baseline. If this ever fails there is a bug
in the ledger math. We exercise the pure helpers db._compute_wallet_balances /
db._compute_unassigned directly (they take already-filtered rows), so no Supabase
call happens.
"""
import db


def _current_balance(manual_balance, income, expenses):
    """The main-balance formula, restricted to the post-anchor rows we pass in:
    manual_balance + Σ income − Σ expenses. Transfers never affect it (a transfer
    moves money between wallets; total is unchanged)."""
    return manual_balance + sum(i["amount"] for i in income) - sum(e["amount"] for e in expenses)


def _assert_invariant(manual_balance, active_ids, income, expenses, transfers):
    balances = db._compute_wallet_balances(active_ids, income, expenses, transfers)
    unassigned = db._compute_unassigned(manual_balance, active_ids, income, expenses, transfers)
    current = _current_balance(manual_balance, income, expenses)
    assert round(sum(balances.values()) + unassigned, 6) == round(current, 6)
    return balances, unassigned


def test_invariant_no_wallets():
    # Everything (baseline + all movements) sits in Unassigned.
    income = [{"amount": 5000, "wallet_id": None}]
    expenses = [{"amount": 1200, "wallet_id": None}]
    balances, unassigned = _assert_invariant(6498.43, [], income, expenses, [])
    assert balances == {}
    assert round(unassigned, 2) == round(6498.43 + 5000 - 1200, 2)


def test_invariant_tagged_income_and_expense():
    active = [1, 2]
    income = [{"amount": 3000, "wallet_id": 1}, {"amount": 500, "wallet_id": None}]
    expenses = [{"amount": 200, "wallet_id": 1}, {"amount": 100, "wallet_id": 2}]
    balances, _ = _assert_invariant(1000, active, income, expenses, [])
    assert balances[1] == 3000 - 200   # tagged income minus tagged expense
    assert balances[2] == -100


def test_invariant_with_full_transfer():
    # A transfer between two real wallets nets to zero across the system.
    active = [1, 2]
    income = [{"amount": 1000, "wallet_id": 1}]
    transfers = [{"amount": 400, "from_wallet": 1, "to_wallet": 2}]
    balances, unassigned = _assert_invariant(0, active, income, [], transfers)
    assert balances[1] == 600
    assert balances[2] == 400
    assert unassigned == 0


def test_invariant_half_resolved_transfer_to_null():
    # Transfer INTO an unknown (NULL) wallet: leaves wallet 1, lands in Unassigned.
    active = [1]
    income = [{"amount": 1000, "wallet_id": 1}]
    transfers = [{"amount": 250, "from_wallet": 1, "to_wallet": None}]
    balances, unassigned = _assert_invariant(0, active, income, [], transfers)
    assert balances[1] == 750
    assert unassigned == 250


def test_invariant_half_resolved_transfer_from_null():
    # Transfer FROM unknown into wallet 1: Unassigned goes negative by the amount.
    active = [1]
    transfers = [{"amount": 300, "from_wallet": None, "to_wallet": 1}]
    balances, unassigned = _assert_invariant(1000, active, [], [], transfers)
    assert balances[1] == 300
    assert unassigned == 1000 - 300


def test_invariant_money_in_soft_deleted_wallet_folds_into_unassigned():
    # Wallet 2 was soft-deleted (not in active_ids) but still has tagged income.
    # That money must count toward Unassigned, or the invariant would break.
    active = [1]  # wallet 2 is inactive
    income = [{"amount": 800, "wallet_id": 1}, {"amount": 500, "wallet_id": 2}]
    expenses = [{"amount": 300, "wallet_id": 2}]
    balances, unassigned = _assert_invariant(0, active, income, expenses, [])
    assert balances == {1: 800}
    assert unassigned == 500 - 300  # wallet 2's net, now unassigned


def test_invariant_kitchen_sink():
    active = [1, 2, 3]
    income = [
        {"amount": 4000, "wallet_id": 1},
        {"amount": 600, "wallet_id": None},
        {"amount": 900, "wallet_id": 99},   # tagged to a deleted/unknown wallet
    ]
    expenses = [
        {"amount": 250, "wallet_id": 1},
        {"amount": 120, "wallet_id": 2},
        {"amount": 80, "wallet_id": None},
    ]
    transfers = [
        {"amount": 500, "from_wallet": 1, "to_wallet": 2},
        {"amount": 150, "from_wallet": 2, "to_wallet": 3},
        {"amount": 75, "from_wallet": 3, "to_wallet": None},   # to unknown
    ]
    _assert_invariant(6498.43, active, income, expenses, transfers)
