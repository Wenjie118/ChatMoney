"""
Unit tests for utils.transactions.consolidate_transactions — the PDF-row merge
logic (Issue #16, non-planner part).

Pure function, no Supabase/Gemini, so nothing is mocked here.

(The plan-math parts of #16 — save_plan's balancing rule and
get_allocation_actuals — are deferred with the Planner feature, #2.)
"""

from utils.transactions import consolidate_transactions


def test_merges_duplicate_rows_sums_amount_and_counts():
    rows = [
        {"type": "expense", "amount": 10.0, "category": "Food", "description": "Lunch", "date": "2026-07-01"},
        {"type": "expense", "amount": 15.5, "category": "Food", "description": "Lunch", "date": "2026-07-03"},
    ]
    out = consolidate_transactions(rows)

    assert len(out) == 1
    row = out[0]
    assert row["type"] == "expense"
    assert row["amount"] == 25.5           # 10.0 + 15.5
    assert row["count"] == 2               # two lines merged
    assert row["category_or_source"] == "Food"
    assert row["description"] == "Lunch"


def test_keeps_latest_date_among_merged_rows():
    rows = [
        {"type": "expense", "amount": 5, "category": "Transport", "description": "Grab", "date": "2026-07-10"},
        {"type": "expense", "amount": 6, "category": "Transport", "description": "Grab", "date": "2026-07-02"},
        {"type": "expense", "amount": 7, "category": "Transport", "description": "Grab", "date": "2026-07-25"},
    ]
    out = consolidate_transactions(rows)

    assert len(out) == 1
    assert out[0]["count"] == 3
    assert out[0]["amount"] == 18
    assert out[0]["date"] == "2026-07-25"  # newest ISO date wins


def test_distinct_rows_are_not_merged():
    rows = [
        {"type": "expense", "amount": 10, "category": "Food", "description": "Lunch", "date": "2026-07-01"},
        {"type": "expense", "amount": 20, "category": "Shopping", "description": "Shirt", "date": "2026-07-01"},
        # same category but different description -> a distinct group
        {"type": "expense", "amount": 30, "category": "Food", "description": "Dinner", "date": "2026-07-01"},
    ]
    out = consolidate_transactions(rows)

    assert len(out) == 3
    assert all(r["count"] == 1 for r in out)


def test_flattens_income_source_and_expense_category_into_category_or_source():
    rows = [
        {"type": "income", "amount": 3000, "source": "Salary", "description": "July pay", "date": "2026-07-25"},
        {"type": "expense", "amount": 50, "category": "Bills", "description": "Electric", "date": "2026-07-05"},
    ]
    out = consolidate_transactions(rows)

    by_type = {r["type"]: r for r in out}
    assert by_type["income"]["category_or_source"] == "Salary"
    assert by_type["expense"]["category_or_source"] == "Bills"
    # The raw `source` / `category` keys are collapsed away.
    assert "source" not in by_type["income"]
    assert "category" not in by_type["expense"]


def test_income_and_expense_with_same_description_stay_separate():
    # `type` is part of the grouping key, so an income and expense that otherwise
    # look alike must not merge (this is how a paired Transfer keeps two legs).
    rows = [
        {"type": "expense", "amount": 50, "category": "Transfer", "description": "move", "date": "2026-07-01"},
        {"type": "income", "amount": 50, "source": "Transfer", "description": "move", "date": "2026-07-01"},
    ]
    out = consolidate_transactions(rows)

    assert len(out) == 2
    assert {r["type"] for r in out} == {"expense", "income"}


def test_empty_input_returns_empty_list():
    assert consolidate_transactions([]) == []
