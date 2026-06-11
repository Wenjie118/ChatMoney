"""
Pydantic models = the typed "contracts" between the frontend and backend.

    * Request models  -> FastAPI validates the incoming JSON body against them.
                         Bad input is auto-rejected with a 422 + helpful error.
    * Response models -> FastAPI serializes your return value through them and
                         documents the exact shape at /docs.

These should MIRROR the TypeScript interfaces in frontend/lib/types.ts so both
sides agree on field names and types.

Only `BalanceResponse` is fully written (the GET /balance example depends on it).
Everything else is a stub: fill in the fields where marked.
"""

from pydantic import BaseModel


# ===========================================================================
# COMPLETE — matches db.get_balance()'s return dict.
# ===========================================================================
class BalanceResponse(BaseModel):
    """Shape of GET /balance.

    Mirrors db.get_balance(): current/manual balance plus an optional date string.
    `last_updated` is Optional because get_balance returns None when no balance row
    exists yet.
    """
    current_balance: float
    manual_balance: float
    last_updated: str | None = None


# ===========================================================================
# STUBS — define the fields, then wire each into its route.
# ===========================================================================
class TransactionRequest(BaseModel):
    """Input for POST /transactions/parse (free-text) and items in /save-multiple.

    TODO: decide the fields. For the free-text parse endpoint you likely only need:
        text: str
    For a reviewed/edited row going into /save-multiple you likely need the full
    transaction:
        type: str                  # "expense" | "income"
        amount: float
        category: str | None       # category (expense) or source (income)
        description: str | None
        date: str                  # "YYYY-MM-DD"
    HINT: you may prefer TWO models (e.g. ParseTextRequest vs TransactionRequest)
    rather than overloading one. Use `Field(...)` for constraints (e.g. amount > 0).
    """
    # TODO: add fields


class TransactionResponse(BaseModel):
    """A single transaction returned to the frontend (parsed or fetched).

    TODO: add fields, e.g.
        type: str
        amount: float
        category: str | None
        description: str | None
        date: str
    Consider including a `count: int` field if you return consolidated PDF rows.
    """
    # TODO: add fields


class SaveMultipleResponse(BaseModel):
    """Result of POST /transactions/save-multiple.

    TODO: mirror db.save_multiple_transactions()'s return dict:
        total: int
        saved: int
        failed: int
    """
    # TODO: add fields


class AdviceRequest(BaseModel):
    """Input for POST /advisor/advice.

    TODO: add optional month/year so the user can pick which month to analyze:
        month: int | None = None
        year: int | None = None
    """
    # TODO: add fields


class AdviceResponse(BaseModel):
    """Output of POST /advisor/advice.

    TODO: add the advice text (markdown string):
        advice: str
    Optionally echo back the period analyzed, e.g. `period: str`.
    """
    # TODO: add fields
