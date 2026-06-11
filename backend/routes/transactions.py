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

from fastapi import APIRouter, HTTPException, UploadFile, File

# from llm import parse_transaction, parse_pdf_transactions
# from db import (
#     save_expense, save_income, save_multiple_transactions,
#     get_expenses, DatabaseConnectionError,
# )
# from utils.transactions import consolidate_transactions
# from schemas.models import (
#     TransactionRequest, TransactionResponse, SaveMultipleResponse,
# )

router = APIRouter()


@router.post("/parse")
def parse_text():  # TODO: (payload: TransactionRequest) -> TransactionResponse
    """Parse a natural-language message (e.g. "spent RM50 on coffee") and save it.

    TODO:
        1. Accept a JSON body with the user's text. Use `TransactionRequest`
           (field: `text: str`).
        2. Call `llm.parse_transaction(payload.text)` -> list[dict]. Each dict is
           {type, amount, category|source, description, date}.
        3. Loop the results and route by `type`:
              type == "income"  -> db.save_income(amount, source, date, desc)
              type == "expense" -> db.save_expense(amount, category, date, desc)
        4. Catch llm's ValueError (bad/empty parse) -> HTTPException(422).
           Catch DatabaseConnectionError -> HTTPException(503).
        5. Return a confirmation summarizing what was saved (TransactionResponse).
    """
    # TODO: implement
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.post("/parse-pdf")
async def parse_pdf(file: UploadFile = File(...)):  # TODO: -> list[TransactionResponse]
    """Parse an uploaded bank-statement PDF into a reviewable list (NOT yet saved).

    NOTE: this is `async def` because reading an UploadFile is awaitable.

    TODO:
        1. Read the bytes:  `pdf_bytes = await file.read()`.
        2. Call `llm.parse_pdf_transactions(pdf_bytes)` -> list[dict].
        3. Call `consolidate_transactions(...)` to merge duplicates.
        4. Catch llm's ValueError (unreadable PDF / busy model) -> HTTPException(422/503).
        5. Return the consolidated list so the frontend can show the editable table.
           Do NOT save here — saving happens after the user reviews, via /save-multiple.
    """
    # TODO: implement
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/recent")
def recent_transactions():  # TODO: -> list[TransactionResponse]
    """Return recent transactions for display.

    HEADS-UP: there is NO `get_recent_expenses()` in your db.py. You have two options:
        (a) Add a new function to db.py (allowed — that's your file), e.g.
            `get_recent_expenses(limit=20)` that selects ordered by created_at; or
        (b) Reuse `db.get_expenses(month, year)` for the current month here.

    TODO:
        1. Pick option (a) or (b) above and fetch the rows.
        2. Wrap DB access in try/except DatabaseConnectionError -> HTTPException(503).
        3. Return the rows as a JSON array (list[TransactionResponse]).
    """
    # TODO: implement
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.post("/save-multiple")
def save_multiple():  # TODO: (payload: list[TransactionRequest]) -> SaveMultipleResponse
    """Bulk-save the transactions the user reviewed in the PDF preview table.

    TODO:
        1. Accept a JSON body that is a list of transaction objects (the edited rows).
        2. Convert them into the dict shape db.save_multiple_transactions expects:
           {type, amount, category|source, date, description}.
        3. Call `db.save_multiple_transactions(rows)` -> {total, saved, failed}.
        4. Catch DatabaseConnectionError -> HTTPException(503).
        5. Return that dict as `SaveMultipleResponse`.
    """
    # TODO: implement
    raise HTTPException(status_code=501, detail="Not implemented yet")
