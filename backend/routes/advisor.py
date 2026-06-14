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

from llm import get_advice
from db import get_logged_periods, DatabaseConnectionError
from schemas.models import AdviceRequest, AdviceResponse

router = APIRouter()


@router.post("/advice", response_model=AdviceResponse)
def get_financial_advice(payload: AdviceRequest) -> AdviceResponse:
    """Return AI-generated financial advice for a chosen month.

    Thin endpoint: it forwards the (optional) month/year to llm.get_advice, which
    fetches that month's data and calls Gemini internally. When month/year are None
    (the user picked nothing), get_advice defaults to today's month.

    Errors map to 503 ("service unavailable") because they mean a dependency is
    down — Gemini busy (ValueError) or Supabase unreachable (DatabaseConnectionError)
    — not bad input from the user.
    """
    try:
        advice = get_advice(month=payload.month, year=payload.year)
    except (ValueError, DatabaseConnectionError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return AdviceResponse(advice=advice)


@router.get("/periods")
def list_periods() -> list[dict]:
    """List the (year, month) periods that actually have logged transactions.

    Lets the frontend dropdown offer ONLY months that have data. db.get_logged_periods
    returns (year, month) tuples newest-first; we reshape each into a small
    {"year", "month"} object so the JSON is self-describing for the frontend.
    """
    try:
        periods = get_logged_periods()
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return [{"year": year, "month": month} for year, month in periods]
