"""
Unit tests for db.set_wallet_balance — the "correct a wallet to an exact amount"
adjustment. get_wallet_balance + the write functions are mocked, so no Supabase
call happens; we assert the delta math and WHERE the correction is recorded.

The critical property: a correction goes to `wallet_adjustments`, never to
income/expenses. Those two tables feed the monthly summary, the category charts
and the AI advisor, so a wallet correction landing there would show up as real
earning or spending and distort the savings rate.
"""
from unittest.mock import patch

import db


def test_adjust_up_records_a_positive_adjustment():
    with patch("db.get_wallet_balance", return_value=100.0), \
         patch("db.create_wallet_adjustment") as m_adj:
        delta = db.set_wallet_balance(1, 250)

    assert delta == 150.0
    m_adj.assert_called_once()
    assert m_adj.call_args.args[:2] == (1, 150.0)


def test_adjust_down_records_a_negative_adjustment():
    with patch("db.get_wallet_balance", return_value=500.0), \
         patch("db.create_wallet_adjustment") as m_adj:
        delta = db.set_wallet_balance(2, 200)

    assert delta == -300.0
    m_adj.assert_called_once()
    # The sign carries the direction — there is no separate "expense" path.
    assert m_adj.call_args.args[:2] == (2, -300.0)


def test_no_op_when_already_at_target():
    with patch("db.get_wallet_balance", return_value=250.0), \
         patch("db.create_wallet_adjustment") as m_adj:
        delta = db.set_wallet_balance(1, 250)

    assert delta == 0.0
    m_adj.assert_not_called()


def test_correction_never_touches_income_or_expenses():
    """The whole point: corrections must stay out of the reporting tables."""
    with patch("db.get_wallet_balance", return_value=0.0), \
         patch("db.create_wallet_adjustment"), \
         patch("db.save_income") as m_inc, patch("db.save_expense") as m_exp:
        db.set_wallet_balance(1, 999)
        db.set_wallet_balance(1, -999)

    m_inc.assert_not_called()
    m_exp.assert_not_called()
