"""
API route tests for the wallets + transfers routers.

db is mocked (no Supabase), so these assert the route wiring, response shapes, and
validation — including the manual-transfer rule that BOTH wallets are required.
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app
from db import DatabaseConnectionError

client = TestClient(app, raise_server_exceptions=False)


# ---- GET /wallets ----------------------------------------------------------
def test_list_wallets_returns_balances():
    with patch("routes.wallets.get_all_wallet_balances",
               return_value=[{"id": 1, "name": "Daily", "balance": 250.0}]):
        res = client.get("/wallets")
    assert res.status_code == 200
    assert res.json() == [{"id": 1, "name": "Daily", "balance": 250.0}]


def test_list_wallets_db_down_returns_503():
    with patch("routes.wallets.get_all_wallet_balances",
               side_effect=DatabaseConnectionError("supabase down")):
        res = client.get("/wallets")
    assert res.status_code == 503


# ---- POST /wallets ---------------------------------------------------------
def test_create_wallet():
    with patch("routes.wallets.create_wallet", return_value={"id": 5, "name": "Savings"}):
        res = client.post("/wallets", json={"name": "Savings"})
    assert res.status_code == 200
    assert res.json() == {"id": 5, "name": "Savings", "balance": 0.0}


def test_create_wallet_rejects_blank_name_422():
    with patch("routes.wallets.create_wallet") as m:
        res = client.post("/wallets", json={"name": ""})
    assert res.status_code == 422
    m.assert_not_called()


# ---- GET /wallets/unassigned ----------------------------------------------
def test_unassigned_returns_total_and_rows():
    rows = [{"id": 9, "type": "expense", "amount": 30.0,
             "category_or_source": "Food", "description": "x", "date": "2026-07-10"}]
    with patch("routes.wallets.get_unassigned_total", return_value=1234.5), \
         patch("routes.wallets.get_unassigned_rows", return_value=rows):
        res = client.get("/wallets/unassigned")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1234.5
    assert body["rows"][0]["id"] == 9


# ---- PATCH / DELETE /wallets/{id} -----------------------------------------
def test_rename_wallet():
    with patch("routes.wallets.rename_wallet"), \
         patch("routes.wallets.get_wallet_balance", return_value=100.0):
        res = client.patch("/wallets/3", json={"name": "Renamed"})
    assert res.status_code == 200
    assert res.json() == {"id": 3, "name": "Renamed", "balance": 100.0}


def test_delete_wallet_soft():
    with patch("routes.wallets.deactivate_wallet") as m:
        res = client.delete("/wallets/3")
    assert res.status_code == 200
    assert res.json()["status"] == "deactivated"
    m.assert_called_once_with(3)


# ---- GET /wallets/{id}/ledger ---------------------------------------------
def test_wallet_ledger():
    entries = [{"date": "2026-07-01", "kind": "income", "description": "pay",
                "amount": 500.0, "signed_amount": 500.0}]
    with patch("routes.wallets.get_wallet_ledger", return_value=entries):
        res = client.get("/wallets/1/ledger")
    assert res.status_code == 200
    assert res.json()[0]["kind"] == "income"


# ---- POST /transfers (both wallets REQUIRED) ------------------------------
def test_create_transfer_happy_path():
    row = {"id": 1, "from_wallet": 1, "to_wallet": 2, "amount": 100.0,
           "description": None, "date": "2026-07-20"}
    with patch("routes.transfers.create_transfer", return_value=row) as m:
        res = client.post("/transfers", json={"from_wallet": 1, "to_wallet": 2, "amount": 100})
    assert res.status_code == 200
    assert res.json()["amount"] == 100.0
    m.assert_called_once()


def test_create_transfer_missing_wallet_returns_422():
    # Pydantic rejects a missing required wallet id BEFORE the db is touched.
    with patch("routes.transfers.create_transfer") as m:
        res = client.post("/transfers", json={"to_wallet": 2, "amount": 100})
    assert res.status_code == 422
    m.assert_not_called()


def test_create_transfer_equal_wallets_returns_422():
    with patch("routes.transfers.create_transfer",
               side_effect=ValueError("A transfer must be between two different wallets.")):
        res = client.post("/transfers", json={"from_wallet": 1, "to_wallet": 1, "amount": 100})
    assert res.status_code == 422
    assert "different wallets" in res.json()["detail"]


def test_create_transfer_non_positive_amount_returns_422():
    with patch("routes.transfers.create_transfer") as m:
        res = client.post("/transfers", json={"from_wallet": 1, "to_wallet": 2, "amount": 0})
    assert res.status_code == 422  # Field(gt=0)
    m.assert_not_called()


# ---- PATCH /transactions/{id}/wallet (resolve Unassigned) -----------------
def test_resolve_expense_wallet():
    with patch("routes.transactions.update_expense_wallet") as m:
        res = client.patch("/transactions/7/wallet?type=expense", json={"wallet_id": 2})
    assert res.status_code == 200
    m.assert_called_once_with(7, 2)


def test_resolve_bad_type_returns_422():
    res = client.patch("/transactions/7/wallet?type=bogus", json={"wallet_id": 2})
    assert res.status_code == 422
