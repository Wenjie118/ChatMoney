"""
API route tests for the transactions router (Issue #13, non-planner part).

Uses FastAPI's TestClient with llm + db mocked, so there are no real Supabase
or Gemini calls and no secrets are needed. Asserts the success shapes and the
error mapping wired up by the global handlers in main.py:
    - unparseable / busy LLM (ValueError)   -> 422
    - Supabase unreachable (DBConnError)     -> 503

(The /plans GET/PUT/actuals tests from #13 are deferred with the Planner
feature, #2, which those routes don't exist for yet.)
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app
from db import DatabaseConnectionError

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# POST /transactions/parse
# ---------------------------------------------------------------------------
def test_parse_happy_path_saves_and_returns_flattened_rows():
    parsed = [
        {"type": "expense", "amount": 50, "category": "Food", "description": "coffee", "date": "2026-07-01"},
        {"type": "income", "amount": 3000, "source": "Salary", "description": "pay", "date": "2026-07-25"},
    ]
    with patch("routes.transactions.parse_transaction", return_value=parsed) as m_parse, \
         patch("routes.transactions.save_expense") as m_exp, \
         patch("routes.transactions.save_income") as m_inc:
        res = client.post("/transactions/parse", json={"text": "coffee 50 and salary 3000"})

    assert res.status_code == 200
    body = res.json()
    assert body[0] == {
        "type": "expense", "amount": 50.0, "category_or_source": "Food",
        "description": "coffee", "date": "2026-07-01", "count": None,
    }
    assert body[1]["type"] == "income"
    assert body[1]["category_or_source"] == "Salary"
    m_parse.assert_called_once()
    m_exp.assert_called_once()
    m_inc.assert_called_once()


def test_parse_unparseable_returns_422():
    with patch("routes.transactions.parse_transaction", side_effect=ValueError("Could not parse your message.")):
        res = client.post("/transactions/parse", json={"text": "???"})
    assert res.status_code == 422
    assert res.json()["detail"] == "Could not parse your message."


def test_parse_db_down_returns_503():
    parsed = [{"type": "expense", "amount": 10, "category": "Food", "description": "x", "date": "2026-07-01"}]
    with patch("routes.transactions.parse_transaction", return_value=parsed), \
         patch("routes.transactions.save_expense", side_effect=DatabaseConnectionError("supabase down")):
        res = client.post("/transactions/parse", json={"text": "food 10"})
    assert res.status_code == 503
    assert "supabase down" in res.json()["detail"]


# ---------------------------------------------------------------------------
# POST /transactions/parse-pdf
# ---------------------------------------------------------------------------
def _pdf_upload(content: bytes = b"%PDF-1.4 fake statement"):
    return {"file": ("stmt.pdf", content, "application/pdf")}


def test_parse_pdf_happy_path_consolidates_rows():
    parsed = [
        {"type": "expense", "amount": 10, "category": "Food", "description": "Lunch", "date": "2026-07-01"},
        {"type": "expense", "amount": 12, "category": "Food", "description": "Lunch", "date": "2026-07-03"},
    ]
    with patch("routes.transactions.parse_pdf_transactions", return_value=parsed):
        res = client.post("/transactions/parse-pdf", files=_pdf_upload())

    assert res.status_code == 200
    body = res.json()
    # consolidate_transactions (real) merges the two identical Lunch rows.
    assert len(body) == 1
    assert body[0]["amount"] == 22
    assert body[0]["count"] == 2
    assert body[0]["category_or_source"] == "Food"


def test_parse_pdf_non_pdf_upload_returns_422_without_llm_call():
    with patch("routes.transactions.parse_pdf_transactions") as m_llm:
        res = client.post("/transactions/parse-pdf", files=_pdf_upload(b"not a pdf"))
    assert res.status_code == 422
    m_llm.assert_not_called()  # rejected by _validate_pdf before the LLM


def test_parse_pdf_unreadable_returns_422():
    with patch("routes.transactions.parse_pdf_transactions", side_effect=ValueError("Could not read transactions")):
        res = client.post("/transactions/parse-pdf", files=_pdf_upload())
    assert res.status_code == 422
    assert "Could not read" in res.json()["detail"]


# ---------------------------------------------------------------------------
# POST /transactions/save-multiple
# ---------------------------------------------------------------------------
def _rows():
    return [
        {"type": "expense", "amount": 10, "category_or_source": "Food", "description": "x", "date": "2026-07-01"},
        {"type": "income", "amount": 500, "category_or_source": "Salary", "description": "y", "date": "2026-07-02"},
    ]


def test_save_multiple_happy_path_returns_counts():
    with patch("routes.transactions.save_multiple_transactions",
               return_value={"total": 2, "saved": 2, "failed": 0}) as m_save:
        res = client.post("/transactions/save-multiple", json=_rows())
    assert res.status_code == 200
    assert res.json() == {"total": 2, "saved": 2, "failed": 0}
    m_save.assert_called_once()


def test_save_multiple_rejects_non_positive_amount_with_422():
    bad = [{"type": "expense", "amount": 0, "category_or_source": "Food", "description": "x", "date": "2026-07-01"}]
    # TransactionRequest.amount is Field(gt=0) -> pydantic validation 422, no db call.
    with patch("routes.transactions.save_multiple_transactions") as m_save:
        res = client.post("/transactions/save-multiple", json=bad)
    assert res.status_code == 422
    m_save.assert_not_called()


def test_save_multiple_db_down_returns_503():
    with patch("routes.transactions.save_multiple_transactions",
               side_effect=DatabaseConnectionError("supabase down")):
        res = client.post("/transactions/save-multiple", json=_rows())
    assert res.status_code == 503


# ---------------------------------------------------------------------------
# GET /transactions/summary
# ---------------------------------------------------------------------------
def test_summary_happy_path_computes_figures():
    income = [{"amount": 3000.0}, {"amount": 500.0}]
    expenses = [{"amount": 1200.0}, {"amount": 300.0}]
    with patch("routes.transactions.get_income", return_value=income), \
         patch("routes.transactions.get_expenses", return_value=expenses):
        res = client.get("/transactions/summary", params={"month": 7, "year": 2026})

    assert res.status_code == 200
    body = res.json()
    assert body["total_income"] == 3500.0
    assert body["total_expenses"] == 1500.0
    assert body["net_savings"] == 2000.0
    assert body["savings_rate"] == pytest.approx(2000.0 / 3500.0 * 100)


def test_summary_no_income_guards_savings_rate():
    with patch("routes.transactions.get_income", return_value=[]), \
         patch("routes.transactions.get_expenses", return_value=[{"amount": 100.0}]):
        res = client.get("/transactions/summary", params={"month": 7, "year": 2026})
    assert res.status_code == 200
    assert res.json()["savings_rate"] == 0.0


def test_summary_db_down_returns_503():
    with patch("routes.transactions.get_expenses", side_effect=DatabaseConnectionError("supabase down")), \
         patch("routes.transactions.get_income", return_value=[]):
        res = client.get("/transactions/summary", params={"month": 7, "year": 2026})
    assert res.status_code == 503


# ---------------------------------------------------------------------------
# GET /transactions/recent
# ---------------------------------------------------------------------------
def test_recent_happy_path_merges_and_sorts_newest_first():
    expenses = [{"amount": 10, "category": "Food", "description": "x", "date": "2026-07-05"}]
    income = [{"amount": 3000, "source": "Salary", "description": "pay", "date": "2026-07-25"}]
    with patch("routes.transactions.get_expenses", return_value=expenses), \
         patch("routes.transactions.get_income", return_value=income):
        res = client.get("/transactions/recent", params={"month": 7, "year": 2026})

    assert res.status_code == 200
    body = res.json()
    assert [r["date"] for r in body] == ["2026-07-25", "2026-07-05"]  # newest first
    assert body[0]["type"] == "income"
    assert body[0]["category_or_source"] == "Salary"


def test_recent_db_down_returns_503():
    with patch("routes.transactions.get_expenses", side_effect=DatabaseConnectionError("supabase down")), \
         patch("routes.transactions.get_income", return_value=[]):
        res = client.get("/transactions/recent", params={"month": 7, "year": 2026})
    assert res.status_code == 503
