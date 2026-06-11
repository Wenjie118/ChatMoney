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

from fastapi import APIRouter, HTTPException

# db.py lives at the project root; it's importable thanks to the sys.path line
# in main.py. We import the function we need plus the custom exception it raises.
from db import get_balance, set_balance, DatabaseConnectionError
from schemas.models import BalanceResponse

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
    document it at /docs. We catch `DatabaseConnectionError` and re-raise it as a
    503 so the frontend receives a clean JSON error instead of a 500 stack trace.

    Reachable at GET /balance  (the "" path + the "/balance" prefix from main.py).
    """
    try:
        data = get_balance()
    except DatabaseConnectionError as exc:
        # 503 Service Unavailable — the DB is unreachable, not the client's fault.
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # FastAPI coerces this dict into BalanceResponse and returns it as JSON.
    return BalanceResponse(**data)


# ===========================================================================
# TODO STUB — implement following the pattern above.
# ===========================================================================
@router.put("")
def update_balance():  # TODO: add typed body param, e.g. (payload: SetBalanceRequest)
    """Set a new manual balance.

    TODO:
        1. Accept a request body with the new amount. Create a `SetBalanceRequest`
           model in schemas/models.py (a single `amount: float` field) and add it
           as a typed parameter:  `def update_balance(payload: SetBalanceRequest)`.
        2. Call `db.set_balance(payload.amount)`.
        3. Wrap it in try/except DatabaseConnectionError -> raise HTTPException(503).
        4. Return a confirmation, e.g. the refreshed balance via get_balance(),
           or {"status": "ok"}. Set `response_model=BalanceResponse` if you return
           the refreshed snapshot.
    """
    # TODO: implement
    raise HTTPException(status_code=501, detail="Not implemented yet")
