"""
Unit tests for db.save_multiple_transactions — the per-row bulk insert behind
POST /transactions/save-multiple.

save_income / save_expense are patched so no real Supabase call happens; we
assert the {total, saved, failed} accounting, including that rows with no
category/source are skipped (the manual-entry uncategorized-row bug) rather than
written as uncategorized transactions.
"""
from unittest.mock import patch

import db


def test_saves_valid_rows_and_reports_counts():
    rows = [
        {"type": "expense", "amount": 10, "category": "Food", "source": "Food", "date": "2026-07-01", "description": "x"},
        {"type": "income", "amount": 500, "category": "Salary", "source": "Salary", "date": "2026-07-02", "description": "y"},
    ]
    with patch("db.save_expense") as m_exp, patch("db.save_income") as m_inc:
        result = db.save_multiple_transactions(rows)

    assert result == {"total": 2, "saved": 2, "failed": 0}
    m_exp.assert_called_once()
    m_inc.assert_called_once()


def test_skips_rows_with_empty_category_and_counts_them_failed():
    rows = [
        {"type": "expense", "amount": 10, "category": "", "source": "", "date": "2026-07-01", "description": "x"},
        {"type": "expense", "amount": 20, "category": "Food", "source": "Food", "date": "2026-07-03", "description": "z"},
    ]
    with patch("db.save_expense") as m_exp, patch("db.save_income") as m_inc:
        result = db.save_multiple_transactions(rows)

    # Only the categorized row is written; the empty one is failed, not saved.
    assert result == {"total": 2, "saved": 1, "failed": 1}
    m_exp.assert_called_once()
    m_inc.assert_not_called()


def test_skips_whitespace_only_and_none_category():
    rows = [
        {"type": "expense", "amount": 10, "category": "   ", "source": None, "date": "2026-07-01", "description": "x"},
        {"type": "income", "amount": 30, "category": None, "source": None, "date": "2026-07-04", "description": "w"},
    ]
    with patch("db.save_expense") as m_exp, patch("db.save_income") as m_inc:
        result = db.save_multiple_transactions(rows)

    assert result == {"total": 2, "saved": 0, "failed": 2}
    m_exp.assert_not_called()
    m_inc.assert_not_called()
