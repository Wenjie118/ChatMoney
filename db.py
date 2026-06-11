import os
import socket
from functools import wraps
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from supabase import create_client
import calendar
from datetime import date, datetime

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()

SUPABASE_CONNECTION_HELP = (
    "Cannot connect to Supabase. Update your `.env` file:\n"
    "1. Open https://supabase.com/dashboard and open your project\n"
    "2. Go to **Project Settings → API**\n"
    "3. Set `SUPABASE_URL` to **Project URL** (e.g. `https://abcdefgh.supabase.co`)\n"
    "4. Set `SUPABASE_KEY` to the **anon public** key\n"
    "5. Save `.env` and restart the app\n\n"
    "If the project was deleted or paused, restore or create a new project first."
)


class DatabaseConnectionError(Exception):
    """Raised when Supabase cannot be reached."""


if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in your .env file")


def _validate_supabase_url(url: str) -> str:
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    if parsed.scheme != "https" or not hostname.endswith(".supabase.co"):
        raise ValueError(
            f"SUPABASE_URL must look like https://<project-ref>.supabase.co (got: {url!r})"
        )
    return hostname


def _resolve_host(hostname: str) -> None:
    try:
        socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise DatabaseConnectionError(
            f"Cannot resolve Supabase host `{hostname}`. "
            "The project URL is wrong, or the project was deleted/paused.\n\n"
            + SUPABASE_CONNECTION_HELP
        ) from e


def check_supabase_connection() -> tuple[bool, str | None]:
    try:
        _resolve_host(_validate_supabase_url(SUPABASE_URL))
        return True, None
    except (ValueError, DatabaseConnectionError) as e:
        return False, str(e)


def with_db_connection(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (httpx.ConnectError, httpx.NetworkError, httpx.TimeoutException) as e:
            raise DatabaseConnectionError(SUPABASE_CONNECTION_HELP) from e
    return wrapper


def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

@with_db_connection
def save_expense(amount, category, expense_date, desc=None):
    client = get_supabase()
    expense = {
        "amount": amount,
        "category": category,
        "description": desc,
        "date": expense_date
    }
    response = client.table("expenses").insert(expense).execute()
    return response

@with_db_connection
def get_expenses(month, year):
    client = get_supabase()
    start = date(year, month, 1).isoformat()
    end = date(year, month, calendar.monthrange(year, month)[1]).isoformat()
    response = client.table("expenses").select("*").gte("date", start).lte("date", end).execute()
    return response.data

@with_db_connection
def save_income(amount, source, income_date, desc=None):
    client = get_supabase()
    income = {
        "amount": amount,
        "source": source,
        "description": desc,
        "date": income_date
    }
    response = client.table("income").insert(income).execute()
    return response

@with_db_connection
def get_income(month, year):
    client = get_supabase()
    start = date(year, month, 1).isoformat()
    end = date(year, month, calendar.monthrange(year, month)[1]).isoformat()
    response = client.table("income").select("*").gte("date", start).lte("date", end).execute()
    return response.data

@with_db_connection
def get_monthly_summary():
    current = date.today()

    details = {
        "total_income":    0.0,
        "total_expenses":  0.0,
        "net_savings":     0.0,
        "savings_rate":    0.0,
        "current_balance": 0.0
    }

    incomes = get_income(current.month, current.year)
    for income in incomes:
        details["total_income"] += income["amount"]

    expenses = get_expenses(current.month, current.year)
    for expense in expenses:
        details["total_expenses"] += expense["amount"]

    details["net_savings"] = details["total_income"] - details["total_expenses"]
    details["savings_rate"] = (details["net_savings"] / details["total_income"]) * 100 if details["total_income"] > 0 else 0.0

    balance = get_balance()
    details["current_balance"] = balance["current_balance"]

    return details

@with_db_connection
def set_balance(amount):
    client = get_supabase()
    balance = {
        "manual_balance": amount,
        "last_updated": date.today().isoformat(),
    }
    response = client.table("balance").insert(balance).execute()
    return response

@with_db_connection
def get_balance():
    client = get_supabase()
    response = client.table("balance").select("*").order("created_at", desc=True).limit(1).execute()

    if not response.data:
        return {
            "current_balance": 0.0,
            "manual_balance":  0.0,
            "last_updated":    None
        }

    row = response.data[0]
    manual_balance = row["manual_balance"]
    last_updated = datetime.strptime(row["last_updated"], "%Y-%m-%d").date().isoformat()

    anchor = row["created_at"]

    incomes  = client.table("income").select("*").gt("created_at", anchor).execute().data
    expenses = client.table("expenses").select("*").gt("created_at", anchor).execute().data

    total_income  = sum(i["amount"] for i in incomes)
    total_expense = sum(e["amount"] for e in expenses)

    current_balance = manual_balance + total_income - total_expense

    return {
        "current_balance": current_balance,
        "manual_balance":  manual_balance,
        "last_updated":    str(last_updated)
    }


def save_multiple_transactions(transactions: list) -> dict:
    saved = 0
    failed = 0
    for t in transactions:
        try:
            if t["type"] == "income":
                save_income(
                    amount=t["amount"],
                    source=t.get("source") or t.get("category"),
                    income_date=t["date"],
                    desc=t.get("description"),
                )
            elif t["type"] == "expense":
                save_expense(
                    amount=t["amount"],
                    category=t.get("category") or t.get("source"),
                    expense_date=t["date"],
                    desc=t.get("description"),
                )
            else:
                failed += 1
                continue
            saved += 1
        except Exception:
            failed += 1
    return {"total": len(transactions), "saved": saved, "failed": failed}


@with_db_connection
def get_logged_periods():
    """Return (year, month) pairs that have at least one logged transaction,
    sorted newest first. Used to offer only months that actually have data."""
    client = get_supabase()
    periods = set()
    for table in ("expenses", "income"):
        rows = client.table(table).select("date").execute().data or []
        for row in rows:
            raw = row.get("date")
            if not raw:
                continue
            try:
                d = datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
            except ValueError:
                continue
            periods.add((d.year, d.month))
    return sorted(periods, reverse=True)