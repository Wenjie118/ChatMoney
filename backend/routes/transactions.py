"""
Transaction endpoints (expenses + income).

    POST /transactions/parse           -> parse a free-text message and save      (TODO)
    POST /transactions/parse-pdf       -> parse an uploaded bank-statement PDF     (TODO)
    GET  /transactions/recent          -> list recent transactions                (TODO)
    POST /transactions/save-multiple   -> bulk-save reviewed transactions          (TODO)

Follow the pattern from routes/balance.py:
    import the db/llm function -> call it -> map errors -> return a typed response.

Relevant existing functions (VERIFIED against your current code):
    llm.parse_transaction(user_input: str) -> list[dict]      # NOTE: singular name
    llm.parse_pdf_transactions(pdf_bytes: bytes) -> list[dict]
    db.save_expense(amount, category, expense_date, desc=None)
    db.save_income(amount, source, income_date, desc=None)
    db.save_multiple_transactions(transactions: list) -> {total, saved, failed}
    db.get_expenses(month, year) -> list[dict]
    db.get_income(month, year) -> list[dict]
    utils.transactions.consolidate_transactions(transactions) -> list[dict]   # port from app.py
"""

import logging
from datetime import date, datetime

from fastapi import APIRouter, HTTPException, UploadFile, File

from llm import parse_transaction, parse_pdf_transactions
from db import (
    save_expense,
    save_income,
    save_multiple_transactions,
    get_expenses,
    get_income,
    summarize_transactions,
    get_wallets,
    update_expense_wallet,
    update_income_wallet,
)
from utils.transactions import consolidate_transactions
from schemas.models import (
    ParseTextRequest,
    TransactionRequest,
    TransactionResponse,
    SaveMultipleResponse,
    SummaryResponse,
    ResolveWalletRequest,
)

router = APIRouter()

logger = logging.getLogger(__name__)


def _validate_pdf(pdf_bytes: bytes) -> None:
    """Reject obviously-unreadable PDFs BEFORE spending an LLM call.

    Gemini returns a cryptic 'The document has no pages' (400 INVALID_ARGUMENT)
    error for empty, non-PDF, or password-protected files. Bank statements —
    especially Malaysian bank e-statements — are very often password-protected,
    which Gemini cannot decrypt. We detect these cases here and raise a clear 422
    instead of letting the user hit the confusing Gemini error.
    """
    if not pdf_bytes:
        raise HTTPException(
            status_code=422,
            detail="The uploaded file is empty (0 bytes). Please choose a valid PDF.",
        )
    # Every real PDF starts with the "%PDF" magic header.
    if not pdf_bytes.startswith(b"%PDF"):
        raise HTTPException(
            status_code=422,
            detail="That file doesn't look like a PDF. Please upload a PDF bank statement.",
        )
    # Encrypted PDFs carry an /Encrypt entry in their trailer. Gemini can't read
    # them, so guide the user to upload an unlocked copy.
    if b"/Encrypt" in pdf_bytes:
        raise HTTPException(
            status_code=422,
            detail=(
                "This PDF is password-protected, so it can't be read. "
                "Open it, enter the password, then print/save it as a NEW PDF "
                "(File → Print → Save as PDF) and upload that unlocked copy."
            ),
        )


# ===========================================================================
# SLICE 1 — DONE (example). Mirror this shape for the stubs below.
# ===========================================================================
def _clean_parsed_row(t: dict) -> dict | None:
    """Normalize ONE LLM-parsed transaction into a safe, saveable row, or return
    None to skip it.

    The model can omit or malform fields (a missing `category`, a non-numeric
    `amount`, no `date`). Reading keys with `[]` 500s on the first missing one, so
    we read everything defensively: drop rows we cannot save (unknown type or a
    non-positive/non-numeric amount) and fill sensible defaults for the rest
    (category/source -> "Other", missing or garbled date -> today). This mirrors the
    tolerant `.get()` handling the PDF path already uses via consolidate_transactions.
    """
    if not isinstance(t, dict):
        return None

    ttype = t.get("type")
    if ttype not in ("income", "expense"):
        return None

    # Amount must be a positive number; a missing/garbage amount is unsaveable.
    try:
        amount = float(t.get("amount"))
    except (TypeError, ValueError):
        return None
    if amount <= 0:
        return None

    # The parser is told to default a missing date to today; backstop it here so a
    # blank/malformed date never blocks an otherwise-valid row.
    try:
        cleaned_date = datetime.strptime(str(t.get("date"))[:10], "%Y-%m-%d").date().isoformat()
    except (TypeError, ValueError):
        cleaned_date = date.today().isoformat()

    cat_or_src = (t.get("source") if ttype == "income" else t.get("category")) or "Other"

    return {
        "type": ttype,
        "amount": amount,
        "category_or_source": cat_or_src,
        "description": t.get("description"),
        "date": cleaned_date,
    }


@router.post("/parse", response_model=list[TransactionResponse])
def parse_text(payload: ParseTextRequest) -> list[TransactionResponse]:
    """Parse a natural-language message (e.g. "spent RM50 on coffee") and save it.

    Flow:
        1. FastAPI validates the body into `ParseTextRequest` (gives `payload.text`).
        2. llm.parse_transaction(text) returns a list of transaction dicts.
        3. Route each by `type` to db.save_income / db.save_expense.
        4. Build a TransactionResponse for each saved row to send back, flattening
           category/source into one `category_or_source` field.

    Errors (mapped centrally by the global handlers in main.py):
        - llm raises ValueError on a bad/empty parse or busy AI -> 422.
        - db raises DatabaseConnectionError if Supabase is down  -> 503.
    """
    # Step 2 — parse (LLM call). A ValueError here (unparseable / busy AI) escapes
    # to the global handler -> 422.
    parsed = parse_transaction(payload.text)

    # Step 3 + 4 — clean/validate each parsed row, then save it and build the
    # response. Unsaveable rows (unknown type, missing/non-positive amount) are
    # skipped rather than crashing the whole request, so the valid rows in the same
    # message still get saved. A DatabaseConnectionError escapes to the global
    # handler -> 503.
    saved: list[TransactionResponse] = []
    for t in parsed:
        row = _clean_parsed_row(t)
        if row is None:
            continue

        if row["type"] == "income":
            save_income(
                amount=row["amount"],
                source=row["category_or_source"],
                income_date=row["date"],
                desc=row["description"],
                wallet_id=payload.wallet_id,
            )
        else:  # expense
            save_expense(
                amount=row["amount"],
                category=row["category_or_source"],
                expense_date=row["date"],
                desc=row["description"],
                wallet_id=payload.wallet_id,
            )

        saved.append(TransactionResponse(
            type=row["type"],
            amount=row["amount"],
            category_or_source=row["category_or_source"],
            description=row["description"],
            date=row["date"],
            wallet_id=payload.wallet_id,
        ))

    return saved


@router.post("/parse-pdf", response_model=list[TransactionResponse])
async def parse_pdf(file: UploadFile = File(...)) -> list[TransactionResponse]:
    """Parse an uploaded bank-statement PDF into a reviewable list (NOT yet saved).

    This is `async def` because reading an UploadFile is an awaitable I/O operation;
    `await file.read()` streams the bytes without blocking the server.

    Flow:
        1. Read the uploaded file's bytes.
        2. Hand the bytes to the LLM, which returns a flat list of transaction dicts.
        3. Merge duplicate lines with consolidate_transactions (one tidy row each).
        4. Return the consolidated rows for the user to review/edit. We do NOT save
           here — saving happens only after the user confirms, via /save-multiple.
    """
    # Step 1 — pull the raw bytes off the multipart upload.
    pdf_bytes = await file.read()
    logger.info("parse-pdf received '%s' — %d bytes", file.filename, len(pdf_bytes))

    # Step 1b — reject empty / non-PDF / password-protected files up front, so the
    # user gets a clear message instead of Gemini's cryptic 'no pages' error.
    _validate_pdf(pdf_bytes)

    # Step 1c — active wallets give the parser names to match against, and let us
    # map the inferred name back to an id. A Supabase outage -> 503 (global handler).
    wallets = get_wallets()

    # Step 2 + 3 — parse with the LLM (with wallet context), then merge duplicates.
    # An unreadable PDF / nothing parseable / busy AI raises ValueError -> 422.
    parsed = parse_pdf_transactions(pdf_bytes, wallets=wallets)

    consolidated = consolidate_transactions(parsed)

    # Step 4 — map the parser's inferred wallet NAME to an id (case-insensitive;
    # unknown/absent -> None = Unassigned), then coerce each row into the response.
    name_to_id = {str(w["name"]).lower(): w["id"] for w in wallets}
    result: list[TransactionResponse] = []
    for row in consolidated:
        wname = row.pop("wallet", None)
        row["wallet_id"] = name_to_id.get(str(wname).lower()) if wname else None
        result.append(TransactionResponse(**row))
    return result


@router.get("/recent", response_model=list[TransactionResponse])
def recent_transactions(
    month: int | None = None,
    year: int | None = None,
) -> list[TransactionResponse]:
    """Return a month's transactions (income + expenses) for the dashboard list/charts.

    `month`/`year` are optional query params; when omitted we default to today's
    month. We combine both tables into ONE list of TransactionResponse (flattening
    each row's `category`/`source` into `category_or_source`) and sort newest-first,
    matching how the old Streamlit dashboard showed the recent table.

    (The guide offered adding a dedicated db.get_recent_expenses(); reusing the
    existing get_expenses/get_income keeps db.py untouched and lets the same month
    picker drive the cards, the recent table, AND the charts.)
    """
    today = date.today()
    month = month or today.month
    year = year or today.year

    # A Supabase outage raises DatabaseConnectionError -> 503 (global handler).
    expenses = get_expenses(month=month, year=year)
    income = get_income(month=month, year=year)

    rows: list[TransactionResponse] = []
    for e in expenses:
        rows.append(TransactionResponse(
            type="expense",
            amount=e["amount"],
            category_or_source=e.get("category"),
            description=e.get("description"),
            date=e["date"],
            wallet_id=e.get("wallet_id"),
        ))
    for i in income:
        rows.append(TransactionResponse(
            type="income",
            amount=i["amount"],
            category_or_source=i.get("source"),
            description=i.get("description"),
            date=i["date"],
            wallet_id=i.get("wallet_id"),
        ))

    # Newest first. ISO date strings compare correctly as plain strings.
    rows.sort(key=lambda r: r.date, reverse=True)
    return rows


@router.get("/summary", response_model=SummaryResponse)
def summary(month: int, year: int) -> SummaryResponse:
    """Return the four headline numbers for ONE month (income, expenses, savings, rate).

    `month` and `year` are REQUIRED query params here (no default) because the
    dashboard always knows which month it's showing. db.get_monthly_summary() is
    hard-wired to the current month, but both share db.summarize_transactions()
    for the actual math — this route just fetches any month's rows and feeds them
    in (the divide-by-zero guard lives in that helper).

    A Supabase outage raises DatabaseConnectionError -> 503 (global handler).
    """
    expenses = get_expenses(month=month, year=year)
    income = get_income(month=month, year=year)

    return SummaryResponse(**summarize_transactions(income, expenses))


@router.post("/save-multiple", response_model=SaveMultipleResponse)
def save_multiple(payload: list[TransactionRequest]) -> SaveMultipleResponse:
    """Bulk-save the transactions the user reviewed in the PDF preview table.

    The body is a JSON array of transaction objects (FastAPI validates each against
    TransactionRequest). We convert the frontend's flattened `category_or_source`
    back into the {category, source} keys db.save_multiple_transactions reads — we
    set BOTH to the same value and let that function pick the right one per `type`.
    """
    rows = [
        {
            "type": t.type,
            "amount": t.amount,
            # save_multiple_transactions uses `source` for income and `category`
            # for expenses (with a fallback to the other). Supplying both = the
            # one combined value means it always finds what it needs.
            "category": t.category_or_source,
            "source": t.category_or_source,
            "date": t.date,
            "description": t.description,
            # Chosen wallet for this row (null = Unassigned).
            "wallet_id": t.wallet_id,
        }
        for t in payload
    ]

    # A total Supabase outage raises DatabaseConnectionError -> 503 (global
    # handler); per-row failures are counted in the returned {saved, failed}.
    result = save_multiple_transactions(rows)

    # result is {"total": ..., "saved": ..., "failed": ...}
    return SaveMultipleResponse(**result)


@router.patch("/{transaction_id}/wallet")
def resolve_wallet(
    transaction_id: int,
    type: str,
    payload: ResolveWalletRequest,
) -> dict:
    """Assign (or null out) the wallet on a previously-unassigned income/expense.

    `type` is a query param ("expense" | "income") selecting which table to
    update — this is how an Unassigned row is resolved from the UI. Passing
    wallet_id=null moves it back to Unassigned.
    """
    if type == "expense":
        update_expense_wallet(transaction_id, payload.wallet_id)
    elif type == "income":
        update_income_wallet(transaction_id, payload.wallet_id)
    else:
        raise HTTPException(status_code=422, detail="type must be 'expense' or 'income'.")

    return {"status": "updated", "id": transaction_id, "type": type, "wallet_id": payload.wallet_id}
