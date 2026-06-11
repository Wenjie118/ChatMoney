"""
AI advisor endpoint.

    POST /advisor/advice   -> generate personalized advice for a month   (TODO)

Existing function (VERIFIED):
    llm.get_advice(month: int | None = None, year: int | None = None) -> str

    `get_advice` already fetches expenses/income/balance internally for the given
    month and calls Gemini. So the endpoint is thin — it mostly validates input
    and forwards the month/year. (You do NOT need to fetch the data yourself unless
    you want to also return the raw figures alongside the advice text.)
"""

from fastapi import APIRouter, HTTPException

# from llm import get_advice
# from db import DatabaseConnectionError
# from schemas.models import AdviceRequest, AdviceResponse

router = APIRouter()


@router.post("/advice")
def get_financial_advice():  # TODO: (payload: AdviceRequest) -> AdviceResponse
    """Return AI-generated financial advice for a chosen month.

    TODO:
        1. Accept an `AdviceRequest` body with optional `month` and `year`
           (both `int | None`; when omitted, llm.get_advice defaults to today).
        2. Call `llm.get_advice(month=payload.month, year=payload.year)` -> str.
        3. Catch llm's ValueError (model busy / API error) -> HTTPException(503).
           Catch DatabaseConnectionError -> HTTPException(503).
        4. Return `AdviceResponse(advice=...)`.

    OPTIONAL: to show the user *which* months they can pick, add a second endpoint
        GET /advisor/periods  ->  db.get_logged_periods()  (returns [(year, month), ...])
        so the frontend dropdown only lists months that actually have data.
    """
    # TODO: implement
    raise HTTPException(status_code=501, detail="Not implemented yet")
