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

from llm import get_advice, get_spending_analysis
from db import get_logged_periods, DatabaseConnectionError
from schemas.models import AdviceRequest, AdviceResponse, SpendingAnalysisResponse

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


@router.post("/spending", response_model=SpendingAnalysisResponse)
def get_spending_analysis_endpoint(payload: AdviceRequest) -> SpendingAnalysisResponse:
    """Return the mid-month, provisional, expense-only spending analysis.

    Sibling of /advice but a different question: it looks at spending SO FAR in
    the chosen month and projects where it's heading, rather than reviewing a
    completed month. Thin like /advice — it forwards the optional month/year to
    llm.get_spending_analysis, which fetches the to-date expenses and calls Gemini
    internally (defaulting to the current month when month/year are None).

    Same error mapping as /advice: dependency failures (Gemini busy / Supabase
    down) surface as 503, not user input errors.
    """
    try:
        analysis = get_spending_analysis(month=payload.month, year=payload.year)
    except (ValueError, DatabaseConnectionError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return SpendingAnalysisResponse(analysis=analysis)


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
