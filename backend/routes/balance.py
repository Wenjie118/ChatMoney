"""
Balance endpoints.

    GET  /balance   -> current balance snapshot              (COMPLETE — example)
    PUT  /balance   -> set a new manual balance              (TODO stub)

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
from db import get_balance, set_balance
from schemas.models import BalanceResponse, SetBalanceRequest

router = APIRouter()


# ===========================================================================
# COMPLETE EXAMPLE — study this, then mirror it for the other endpoints.
# ===========================================================================
@router.get("", response_model=BalanceResponse)
def read_balance() -> BalanceResponse:
    """Return the latest balance snapshot.

    Calls `db.get_balance()`, which returns a dict:
        {"current_balance": float, "manual_balance": float, "last_updated": str|None}

    `response_model=BalanceResponse` makes FastAPI validate & shape the output and
    document it at /docs. If Supabase is unreachable, `get_balance` raises
    `DatabaseConnectionError`, which the global handler in main.py turns into a
    clean 503 JSON response instead of a 500 stack trace.

    Reachable at GET /balance  (the "" path + the "/balance" prefix from main.py).
    """
    # FastAPI coerces this dict into BalanceResponse and returns it as JSON.
    return BalanceResponse(**get_balance())


# ===========================================================================
# TODO STUB — implement following the pattern above.
# ===========================================================================
@router.put("", response_model=BalanceResponse)
def update_balance(payload: SetBalanceRequest) -> BalanceResponse:
    """Set a new manual balance, then return the refreshed snapshot.

    `db.set_balance` writes a new balance row; `db.get_balance` then re-reads the
    latest balance (recomputed from that anchor + any later income/expenses). We
    return the refreshed snapshot — typed as BalanceResponse — so the frontend can
    update the card from the response without a second request.

    A Supabase outage raises `DatabaseConnectionError`, mapped to 503 by the
    global handler in main.py.
    """
    set_balance(payload.amount)
    return BalanceResponse(**get_balance())
