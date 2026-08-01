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

    Mirrors db.get_balance(). The balance is DERIVED — `current_balance` is exactly
    `wallet_total + unassigned` — so the response ships its own breakdown and the UI
    never has to re-add anything. `last_updated` (date of the most recent movement)
    is Optional because there may not be any movements yet.
    """
    current_balance: float
    wallet_total: float                # Σ of active wallet balances
    unassigned: float                  # real money not in a wallet yet
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
    # Wallet the logged transaction(s) belong to. The chat UI requires it before
    # sending; the API keeps it optional so a null just lands the row in Unassigned
    # (the invariant handles that) rather than hard-failing the request.
    wallet_id: int | None = None


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
    # Wallet this transaction is tagged to (null = Unassigned). On /parse-pdf this
    # is the parser's inferred wallet mapped name->id; on /recent it's the stored tag.
    wallet_id: int | None = None


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
    # Chosen wallet for this row (null = Unassigned). Persisted into the row's
    # wallet_id by save_multiple_transactions.
    wallet_id: int | None = None


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


class AdviceRequest(BaseModel):
    month: int | None = None
    year: int | None = None

 
class AdviceResponse(BaseModel):
    advice: str


class SpendingAnalysisResponse(BaseModel):
    """Response from POST /advisor/spending — the mid-month, provisional,
    expense-only spending analysis text. Reuses AdviceRequest for input (same
    optional month/year). Named `analysis` (not `advice`) to keep the two
    advisors' contracts distinct. Mirror this in frontend/lib/types.ts."""
    analysis: str


# ===========================================================================
# Wallets — virtual sub-wallets with computed, ledger-based balances.
# Mirror these in frontend/lib/types.ts (IWallet / ITransfer / ...).
# ===========================================================================
class WalletCreate(BaseModel):
    """Body for POST /wallets."""
    name: str = Field(min_length=1)


class WalletRename(BaseModel):
    """Body for PATCH /wallets/{id}."""
    name: str = Field(min_length=1)


class WalletResponse(BaseModel):
    """A wallet with its COMPUTED balance (never stored)."""
    id: int
    name: str
    balance: float


class LedgerEntry(BaseModel):
    """One movement in a wallet's ledger (GET /wallets/{id}/ledger)."""
    date: str
    # income | expense | transfer_in | transfer_out | adjustment
    # "adjustment" is a correction to what the wallet holds — real money, but not
    # a budget event, so it never appears in the summary/charts/advisor.
    kind: str
    description: str | None = None
    amount: float
    signed_amount: float               # + into the wallet, − out of it


class UnassignedRow(BaseModel):
    """A NULL-wallet income/expense row the user can resolve."""
    id: int
    type: str                          # "expense" | "income"
    amount: float
    category_or_source: str | None = None
    description: str | None = None
    date: str


class UnassignedResponse(BaseModel):
    """GET /wallets/unassigned — the total (incl. pre-wallet baseline) plus the
    resolvable rows. The baseline is part of `total` but is not a row."""
    total: float
    rows: list[UnassignedRow]


class TransferCreate(BaseModel):
    """Body for POST /transfers. BOTH wallets are REQUIRED on this manual path —
    the required int fields make FastAPI reject a missing side with a 422."""
    from_wallet: int
    to_wallet: int
    amount: float = Field(gt=0)
    description: str | None = None
    date: str | None = None            # defaults to today in db.create_transfer


class TransferResponse(BaseModel):
    """A stored transfer row."""
    id: int
    from_wallet: int | None = None
    to_wallet: int | None = None
    amount: float
    description: str | None = None
    date: str


class TransferPatch(BaseModel):
    """Body for PATCH /transfers/{id} — fill in previously-NULL wallet sides."""
    from_wallet: int | None = None
    to_wallet: int | None = None


class ResolveWalletRequest(BaseModel):
    """Body for PATCH /transactions/{id}/wallet — assign (or null out) a wallet on
    a previously-unassigned income/expense row."""
    wallet_id: int | None = None


class SetWalletBalanceRequest(BaseModel):
    """Body for PATCH /wallets/{id}/balance — the exact amount the wallet should
    hold. The backend records an adjustment for the difference (see
    db.set_wallet_balance)."""
    amount: float = Field(ge=0)

