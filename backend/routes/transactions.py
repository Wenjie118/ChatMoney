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

from datetime import date

from fastapi import APIRouter, HTTPException, UploadFile, File

from llm import parse_transaction, parse_pdf_transactions
from db import (
    save_expense,
    save_income,
    save_multiple_transactions,
    get_expenses,
    get_income,
    DatabaseConnectionError,
)
from utils.transactions import consolidate_transactions
from schemas.models import (
    ParseTextRequest,
    TransactionRequest,
    TransactionResponse,
    SaveMultipleResponse,
    SummaryResponse,
)

router = APIRouter()


# ===========================================================================
# SLICE 1 — DONE (example). Mirror this shape for the stubs below.
# ===========================================================================
@router.post("/parse", response_model=list[TransactionResponse])
def parse_text(payload: ParseTextRequest) -> list[TransactionResponse]:
    """Parse a natural-language message (e.g. "spent RM50 on coffee") and save it.

    Flow:
        1. FastAPI validates the body into `ParseTextRequest` (gives `payload.text`).
        2. llm.parse_transaction(text) returns a list of transaction dicts.
        3. Route each by `type` to db.save_income / db.save_expense.
        4. Build a TransactionResponse for each saved row to send back, flattening
           category/source into one `category_or_source` field.

    Errors:
        - llm raises ValueError on a bad/empty parse or busy AI -> 422.
        - db raises DatabaseConnectionError if Supabase is down       -> 503.
    """
    # Step 2 — parse (LLM call).
    try:
        parsed = parse_transaction(payload.text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Step 3 + 4 — save each row and build the response.
    saved: list[TransactionResponse] = []
    try:
        for t in parsed:
            if t["type"] == "income":
                save_income(
                    amount=t["amount"],
                    source=t["source"],
                    income_date=t["date"],
                    desc=t.get("description"),
                )
                cat_or_src = t["source"]
            elif t["type"] == "expense":
                save_expense(
                    amount=t["amount"],
                    category=t["category"],
                    expense_date=t["date"],
                    desc=t.get("description"),
                )
                cat_or_src = t["category"]
            else:
                continue  # skip unknown types

            saved.append(TransactionResponse(
                type=t["type"],
                amount=t["amount"],
                category_or_source=cat_or_src,
                description=t.get("description"),
                date=t["date"],
            ))
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

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

    # Step 2 + 3 — parse with the LLM, then merge duplicates.
    try:
        parsed = parse_pdf_transactions(pdf_bytes)
    except ValueError as exc:
        # Unreadable PDF, nothing parseable, or the AI model was busy/errored.
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    consolidated = consolidate_transactions(parsed)

    # Step 4 — coerce each dict into the typed response. The keys already match
    # TransactionResponse (type/amount/category_or_source/description/date/count).
    return [TransactionResponse(**row) for row in consolidated]


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

    try:
        expenses = get_expenses(month=month, year=year)
        income = get_income(month=month, year=year)
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    rows: list[TransactionResponse] = []
    for e in expenses:
        rows.append(TransactionResponse(
            type="expense",
            amount=e["amount"],
            category_or_source=e.get("category"),
            description=e.get("description"),
            date=e["date"],
        ))
    for i in income:
        rows.append(TransactionResponse(
            type="income",
            amount=i["amount"],
            category_or_source=i.get("source"),
            description=i.get("description"),
            date=i["date"],
        ))

    # Newest first. ISO date strings compare correctly as plain strings.
    rows.sort(key=lambda r: r.date, reverse=True)
    return rows


@router.get("/summary", response_model=SummaryResponse)
def summary(month: int, year: int) -> SummaryResponse:
    """Return the four headline numbers for ONE month (income, expenses, savings, rate).

    `month` and `year` are REQUIRED query params here (no default) because the
    dashboard always knows which month it's showing. db.get_monthly_summary() does
    the same math but is hard-wired to the current month — we replicate it for any
    month using get_expenses/get_income.
    """
    try:
        expenses = get_expenses(month=month, year=year)
        income = get_income(month=month, year=year)
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    total_income = sum(i["amount"] for i in income)
    total_expenses = sum(e["amount"] for e in expenses)
    net_savings = total_income - total_expenses
    # Guard against divide-by-zero when there's no income yet.
    savings_rate = (net_savings / total_income * 100) if total_income > 0 else 0.0

    return SummaryResponse(
        total_income=total_income,
        total_expenses=total_expenses,
        net_savings=net_savings,
        savings_rate=savings_rate,
    )


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
        }
        for t in payload
    ]

    try:
        result = save_multiple_transactions(rows)
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # result is {"total": ..., "saved": ..., "failed": ...}
    return SaveMultipleResponse(**result)
