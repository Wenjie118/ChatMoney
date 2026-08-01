"""
Balance endpoint.

    GET  /balance   -> current balance snapshot              (COMPLETE — example)

The balance is READ-ONLY: it is derived as Σ(wallet balances) + unassigned, so it
is changed by editing a WALLET (PATCH /wallets/{id}/balance), never by writing a
balance. There is deliberately no PUT /balance — setting a manual balance would
write a new anchor row dated now, which would push every existing movement out of
the horizon and reset all wallet balances to zero.

This module is the REFERENCE PATTERN for the whole backend. Read GET /balance
closely; every other endpoint follows the same shape:

    1. Define an APIRouter.
    2. Declare the endpoint with a path + HTTP method decorator.
    3. Annotate the return type with a Pydantic model from schemas/models.py
       (FastAPI uses it to serialize the response AND document it in /docs).
    4. Call into the existing db.py / llm.py functions.
    5. Translate domain errors (DatabaseConnectionError) into HTTP errors.
"""

from fastapi import APIRouter

# db.py lives at the project root; it's importable thanks to the sys.path line
# in main.py.
from db import get_balance
from schemas.models import BalanceResponse

router = APIRouter()


# ===========================================================================
# COMPLETE EXAMPLE — study this, then mirror it for the other endpoints.
# ===========================================================================
@router.get("", response_model=BalanceResponse)
def read_balance() -> BalanceResponse:
    """Return the current balance snapshot.

    Calls `db.get_balance()`, which derives the balance from wallets and returns:
        {"current_balance": float,   # == wallet_total + unassigned
         "wallet_total": float, "unassigned": float, "last_updated": str|None}

    `response_model=BalanceResponse` makes FastAPI validate & shape the output and
    document it at /docs. If Supabase is unreachable, `get_balance` raises
    `DatabaseConnectionError`, which the global handler in main.py turns into a
    clean 503 JSON response instead of a 500 stack trace.

    Reachable at GET /balance  (the "" path + the "/balance" prefix from main.py).
    """
    # FastAPI coerces this dict into BalanceResponse and returns it as JSON.
    return BalanceResponse(**get_balance())
