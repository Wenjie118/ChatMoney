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

from pydantic import BaseModel, Field


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
# SLICE 1 — DONE (example). Study these two, then mirror them for later slices.
# ===========================================================================
class ParseTextRequest(BaseModel):
    """Input for POST /transactions/parse — the free-text the user typed.

    Dedicated to the text-parse endpoint. (We DON'T reuse one big TransactionRequest
    for everything, because /save-multiple later needs the full transaction shape —
    a separate model keeps each endpoint's contract clear.)
    """
    text: str


class TransactionResponse(BaseModel):
    """A single transaction sent back to the frontend (parsed, fetched, or saved).

    The parsed dicts from llm.py have EITHER `category` (expense) or `source`
    (income); we flatten that into one `category_or_source` field so the frontend
    has a single column to show. Mirror this exactly in frontend/lib/types.ts.
    """
    type: str                          # "expense" | "income"
    amount: float
    category_or_source: str | None = None
    description: str | None = None
    date: str                          # "YYYY-MM-DD"
    # How many statement lines were merged into this row (PDF import only).
    # Optional + default None so the text-parse and /recent endpoints — which
    # never merge anything — can omit it. It's only populated by /parse-pdf.
    count: int | None = None
    # Salary-plan bucket label for expenses (e.g. "Daily Spending", "Mom"). The
    # LLM guesses it during PDF parsing; the review table lets the user adjust it.
    # Null for income, or when there's no active plan. Mirrors expenses.allocation.
    allocation: str | None = None


# ===========================================================================
# STUBS — define the fields, then wire each into its route (later slices).
# ===========================================================================
class TransactionRequest(BaseModel):
    """One reviewed transaction sent up in POST /transactions/save-multiple (Slice 5).

    This is the SHAPE THE FRONTEND EDITS in the PDF preview table, so it mirrors
    `ITransaction` / `TransactionResponse` (same `category_or_source` flattening).
    The route handler converts each of these into the {type, amount, category|source,
    date, description} dict that db.save_multiple_transactions expects.
    """
    type: str                          # "expense" | "income"
    amount: float = Field(gt=0)        # reject 0 / negative amounts at the door
    category_or_source: str | None = None
    description: str | None = None
    date: str                          # "YYYY-MM-DD"
    # The preview rows carry a merge count; we accept it so the JSON validates,
    # even though save-multiple ignores it (it only writes amount/category/etc.).
    count: int | None = None
    # Chosen salary-plan bucket for expenses; persisted into expenses.allocation
    # by save_multiple_transactions. Null for income / no active plan.
    allocation: str | None = None


class SaveMultipleResponse(BaseModel):
    """Result of POST /transactions/save-multiple — mirrors db.save_multiple_transactions()."""
    total: int
    saved: int
    failed: int


class SummaryResponse(BaseModel):
    """The four headline numbers for the Dashboard, for ONE chosen month (Slice 3).

    db.get_monthly_summary() computes these for the CURRENT month only; our
    GET /transactions/summary endpoint computes the same figures for any month/year.
    Mirror this in frontend/lib/types.ts as IMonthlySummary.
    """
    total_income: float
    total_expenses: float
    net_savings: float
    savings_rate: float                # percentage, e.g. 23.5 means 23.5%


class SetBalanceRequest(BaseModel):
    """Input for PUT /balance (Slice 6) — the new manual balance the user typed."""
    amount: float = Field(ge=0)        # a balance can be 0 but not negative


class AdviceRequest(BaseModel):
    month: int | None = None
    year: int | None = None

 
class AdviceResponse(BaseModel):
    advice: str


# ===========================================================================
# Salary allocation plan — mirrors db.get_active_plan() / plan_allocations rows.
# Mirror these in frontend/lib/types.ts (IPlan / IAllocation / ...).
# ===========================================================================
class AllocationModel(BaseModel):
    """One bucket in the active plan.

    `percent` is the STORED share of salary for %-based buckets (e.g. EPF 11%);
    None means the bucket is RM-based (target_rm is the fixed source of truth).
    The UI derives the display % itself from the current salary draft.
    """
    id: int
    label: str
    target_rm: float
    tracking_mode: str                 # "tagged" | "leftover"
    is_default: bool
    is_active: bool
    percent: float | None = None


class PlanResponse(BaseModel):
    """The active plan. GET /plans returns this OR null when no plan exists."""
    id: int
    salary: float
    allocations: list[AllocationModel]


class PlanBucket(BaseModel):
    """One NON-Savings bucket in a save draft. Savings is computed, never sent.

    `percent` non-null = the bucket is %-based; the server computes its RM as
    salary * percent / 100. Null = RM-based: target_rm is used as-is.
    """
    id: int | None = None              # existing allocation id, or None if new
    label: str
    target_rm: float = Field(ge=0)
    percent: float | None = Field(default=None, ge=0)


class PlanSaveRequest(BaseModel):
    """Body for PUT /plans — the whole editable draft.

    `buckets` holds every active NON-Savings bucket (Daily Spending + customs).
    The server computes Savings = salary - sum(bucket targets) and rejects the
    save when that sum exceeds salary.
    """
    salary: float = Field(gt=0)
    buckets: list[PlanBucket]


class AllocationActual(BaseModel):
    """One row of the deterministic planned-vs-actual table (GET /plans/actuals)."""
    label: str
    target_rm: float
    actual_rm: float
    variance_rm: float
    tracking_mode: str

