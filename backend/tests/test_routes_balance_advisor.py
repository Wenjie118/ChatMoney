"""
Route tests for the balance and advisor routers (Issue #13).

These exercise the global exception handlers from main.py end-to-end and the
advisor's deliberate override (a busy-LLM ValueError maps to 503, not 422).
llm + db are mocked; no secrets or network needed.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app
from db import DatabaseConnectionError

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# balance
# ---------------------------------------------------------------------------
def test_get_balance_happy_path():
    snapshot = {
        "current_balance": 1234.5,
        "wallet_total": 1200.0,
        "unassigned": 34.5,
        "last_updated": "2026-07-01",
    }
    with patch("routes.balance.get_balance", return_value=snapshot):
        res = client.get("/balance")
    assert res.status_code == 200
    assert res.json() == snapshot


def test_get_balance_db_down_returns_503():
    with patch("routes.balance.get_balance", side_effect=DatabaseConnectionError("supabase down")):
        res = client.get("/balance")
    assert res.status_code == 503
    assert "supabase down" in res.json()["detail"]


def test_balance_is_read_only_no_put_endpoint():
    # The balance is derived from wallets; writing one would drop a new anchor row
    # dated now and reset every wallet to zero. Change a wallet instead.
    res = client.put("/balance", json={"amount": 500})
    assert res.status_code == 405


# ---------------------------------------------------------------------------
# advisor
# ---------------------------------------------------------------------------
def test_advice_happy_path():
    with patch("routes.advisor.get_advice", return_value="You saved RM2000 in July."):
        res = client.post("/advisor/advice", json={"month": 7, "year": 2026})
    assert res.status_code == 200
    assert res.json() == {"advice": "You saved RM2000 in July."}


def test_advice_busy_llm_valueerror_maps_to_503_not_422():
    # The advisor treats a busy-LLM ValueError as a dependency outage (503),
    # overriding the global ValueError->422 mapping via its own local catch.
    with patch("routes.advisor.get_advice", side_effect=ValueError("The AI service is busy right now.")):
        res = client.post("/advisor/advice", json={"month": 7, "year": 2026})
    assert res.status_code == 503
    assert "busy" in res.json()["detail"]


def test_advice_db_down_returns_503():
    with patch("routes.advisor.get_advice", side_effect=DatabaseConnectionError("supabase down")):
        res = client.post("/advisor/advice", json={})
    assert res.status_code == 503


def test_periods_reshapes_tuples_into_objects():
    with patch("routes.advisor.get_logged_periods", return_value=[(2026, 7), (2026, 6)]):
        res = client.get("/advisor/periods")
    assert res.status_code == 200
    assert res.json() == [{"year": 2026, "month": 7}, {"year": 2026, "month": 6}]
