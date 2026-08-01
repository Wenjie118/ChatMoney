"""
The wallets correctness GATE (Layer 1).

Asserts the system invariant against hand-built data, with NO network access:

    Σ(active wallet balances) + unassigned == current_balance

get_balance() now DEFINES current_balance as that sum, so what these tests actually
gate is that the two halves still partition every movement exactly once: no money
counted twice, none dropped. We check that by comparing against the independent
ground truth — Σ income − Σ expenses over the same rows — which is what the user's
money adds up to regardless of how it's labelled. Transfers must cancel out.

We exercise the pure helpers db._compute_wallet_balances / db._compute_unassigned
directly (they take already-filtered rows), so no Supabase call happens.
"""
import db


def _moves(income=(), expenses=(), transfers=(), adjustments=()):
    return db.Movements(list(income), list(expenses), list(transfers), list(adjustments))


def _ground_truth(moves):
    """All the money in the horizon, ignoring wallets entirely: Σ income − Σ
    expenses + Σ adjustments (already signed). Transfers never appear — a transfer
    moves money between wallets, so the system total is unchanged."""
    return (
        sum(i["amount"] for i in moves.income)
        - sum(e["amount"] for e in moves.expenses)
        + sum(a["amount"] for a in moves.adjustments)
    )


def _assert_invariant(active_ids, moves):
    balances = db._compute_wallet_balances(active_ids, moves)
    unassigned = db._compute_unassigned(active_ids, moves)
    current = sum(balances.values()) + unassigned          # == get_balance()
    assert round(current, 6) == round(_ground_truth(moves), 6)
    return balances, unassigned


def test_invariant_no_wallets():
    # With no wallets at all, every movement sits in Unassigned — and there is no
    # standalone baseline padding it any more.
    income = [{"amount": 5000, "wallet_id": None}]
    expenses = [{"amount": 1200, "wallet_id": None}]
    balances, unassigned = _assert_invariant([], _moves(income, expenses))
    assert balances == {}
    assert round(unassigned, 2) == 5000 - 1200


def test_invariant_tagged_income_and_expense():
    active = [1, 2]
    income = [{"amount": 3000, "wallet_id": 1}, {"amount": 500, "wallet_id": None}]
    expenses = [{"amount": 200, "wallet_id": 1}, {"amount": 100, "wallet_id": 2}]
    balances, _ = _assert_invariant(active, _moves(income, expenses))
    assert balances[1] == 3000 - 200   # tagged income minus tagged expense
    assert balances[2] == -100


def test_invariant_with_full_transfer():
    # A transfer between two real wallets nets to zero across the system.
    active = [1, 2]
    income = [{"amount": 1000, "wallet_id": 1}]
    transfers = [{"amount": 400, "from_wallet": 1, "to_wallet": 2}]
    balances, unassigned = _assert_invariant(active, _moves(income, transfers=transfers))
    assert balances[1] == 600
    assert balances[2] == 400
    assert unassigned == 0


def test_invariant_half_resolved_transfer_to_null():
    # Transfer INTO an unknown (NULL) wallet: leaves wallet 1, lands in Unassigned.
    active = [1]
    income = [{"amount": 1000, "wallet_id": 1}]
    transfers = [{"amount": 250, "from_wallet": 1, "to_wallet": None}]
    balances, unassigned = _assert_invariant(active, _moves(income, transfers=transfers))
    assert balances[1] == 750
    assert unassigned == 250


def test_invariant_half_resolved_transfer_from_null():
    # Transfer FROM unknown into wallet 1: Unassigned goes negative by the amount,
    # so the system total stays 0 (no income or expense actually happened).
    active = [1]
    transfers = [{"amount": 300, "from_wallet": None, "to_wallet": 1}]
    balances, unassigned = _assert_invariant(active, _moves(transfers=transfers))
    assert balances[1] == 300
    assert unassigned == -300


def test_invariant_money_in_soft_deleted_wallet_folds_into_unassigned():
    # Wallet 2 was soft-deleted (not in active_ids) but still has tagged income.
    # That money must count toward Unassigned, or the invariant would break.
    active = [1]  # wallet 2 is inactive
    income = [{"amount": 800, "wallet_id": 1}, {"amount": 500, "wallet_id": 2}]
    expenses = [{"amount": 300, "wallet_id": 2}]
    balances, unassigned = _assert_invariant(active, _moves(income, expenses))
    assert balances == {1: 800}
    assert unassigned == 500 - 300  # wallet 2's net, now unassigned


def test_balance_equals_wallet_total_when_nothing_is_unassigned():
    # The headline promise: with every row tagged to a wallet, the balance IS the
    # sum of the wallets — nothing extra underneath it.
    active = [1, 2]
    income = [{"amount": 7000, "wallet_id": 1}, {"amount": 1500, "wallet_id": 2}]
    expenses = [{"amount": 250, "wallet_id": 1}]
    balances, unassigned = _assert_invariant(active, _moves(income, expenses))
    assert unassigned == 0
    assert sum(balances.values()) == 7000 + 1500 - 250


def test_editing_a_wallet_moves_the_total_by_exactly_the_delta():
    # Regression for the old behaviour: a wallet correction used to land on TOP of
    # a separate manual baseline, so the headline balance never matched the wallets.
    # set_wallet_balance records the delta as a tagged adjustment, so the balance
    # must move by that delta and nothing more.
    active = [1, 2]
    income = [{"amount": 400, "wallet_id": 1}, {"amount": 600, "wallet_id": 2}]
    balances, unassigned = _assert_invariant(active, _moves(income))
    before = sum(balances.values()) + unassigned
    assert before == 1000

    # Correct wallet 1 from 400 -> 550: set_wallet_balance writes a +150 adjustment.
    moves = _moves(income, adjustments=[{"amount": 150, "wallet_id": 1}])
    balances, unassigned = _assert_invariant(active, moves)
    after = sum(balances.values()) + unassigned
    assert balances[1] == 550          # wallet shows exactly what was typed
    assert after == before + 150       # total moved by the delta, not stacked
    assert after == sum(balances.values())  # still exactly the wallet total


def test_negative_adjustment_lowers_the_wallet_and_the_total():
    # Adjustments carry their own sign — there is no separate "expense" direction.
    active = [1]
    income = [{"amount": 1000, "wallet_id": 1}]
    moves = _moves(income, adjustments=[{"amount": -250, "wallet_id": 1}])
    balances, unassigned = _assert_invariant(active, moves)
    assert balances[1] == 750
    assert unassigned == 0


def test_adjustment_on_a_soft_deleted_wallet_folds_into_unassigned():
    # Same rule as every other movement: money on an inactive wallet is Unassigned,
    # so the invariant survives a delete.
    active = [1]  # wallet 2 is inactive
    moves = _moves(adjustments=[{"amount": 500, "wallet_id": 2}, {"amount": 100, "wallet_id": 1}])
    balances, unassigned = _assert_invariant(active, moves)
    assert balances == {1: 100}
    assert unassigned == 500


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
    adjustments = [
        {"amount": 320.50, "wallet_id": 2},
        {"amount": -45.25, "wallet_id": 3},
        {"amount": 60, "wallet_id": None},     # adjustment with no wallet
    ]
    _assert_invariant(active, _moves(income, expenses, transfers, adjustments))
