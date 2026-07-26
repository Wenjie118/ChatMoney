"""
Unit tests for db.set_wallet_balance — the "correct a wallet to an exact amount"
adjustment. get_wallet_balance + the save_* functions are mocked, so no Supabase
call happens; we assert the delta math and which side (income vs expense) is
recorded.
"""
from unittest.mock import patch

import db


def test_adjust_up_records_income_for_the_delta():
    with patch("db.get_wallet_balance", return_value=100.0), \
         patch("db.save_income") as m_inc, patch("db.save_expense") as m_exp:
        delta = db.set_wallet_balance(1, 250)

    assert delta == 150.0
    m_inc.assert_called_once()
    assert m_inc.call_args.kwargs["amount"] == 150.0
    assert m_inc.call_args.kwargs["wallet_id"] == 1
    m_exp.assert_not_called()


def test_adjust_down_records_expense_for_the_delta():
    with patch("db.get_wallet_balance", return_value=500.0), \
         patch("db.save_income") as m_inc, patch("db.save_expense") as m_exp:
        delta = db.set_wallet_balance(2, 200)

    assert delta == -300.0
    m_exp.assert_called_once()
    assert m_exp.call_args.kwargs["amount"] == 300.0  # positive amount, expense direction
    assert m_exp.call_args.kwargs["wallet_id"] == 2
    m_inc.assert_not_called()


def test_no_op_when_already_at_target():
    with patch("db.get_wallet_balance", return_value=250.0), \
         patch("db.save_income") as m_inc, patch("db.save_expense") as m_exp:
        delta = db.set_wallet_balance(1, 250)

    assert delta == 0.0
    m_inc.assert_not_called()
    m_exp.assert_not_called()
