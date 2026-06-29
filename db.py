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
def save_expense(amount, category, expense_date, desc=None, allocation=None):
    client = get_supabase()
    expense = {
        "amount": amount,
        "category": category,
        "description": desc,
        "date": expense_date,
        # Optional salary-plan bucket label (e.g. "Daily Spending", "Mom"). Stays
        # None when there is no active plan; income rows never carry an allocation.
        "allocation": allocation,
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
                    allocation=t.get("allocation"),
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


# ===========================================================================
# Salary allocation plan
#
# A "plan" is how the user intends to split their salary into named buckets.
# There is at most ONE active plan (plans.is_active = true). Buckets live in
# plan_allocations. Two are mandatory defaults (is_default = true):
#   - Savings        : the BALANCING bucket, tracking_mode='leftover'.
#   - Daily Spending : the catch-all for general expenses, tracking_mode='tagged'.
# Custom buckets are tracking_mode='tagged' and soft-deleted (is_active=false),
# never hard-deleted, so historical advice stays valid.
#
# ALL planned-vs-actual arithmetic lives here in Python — the LLM never computes
# a number. The app must work with NO plan: get_active_plan() returns None and
# get_allocation_actuals() returns [].
# ===========================================================================

@with_db_connection
def get_active_plan():
    """Return the active plan + its active allocations, or None if there is none.

    Shape: {"id": int, "salary": float, "allocations": [ {row}, ... ]}
    Allocations are ordered defaults-first (Savings, Daily Spending), then by id.
    """
    client = get_supabase()
    plans = client.table("plans").select("*").eq("is_active", True).limit(1).execute().data
    if not plans:
        return None

    plan = plans[0]
    allocations = (
        client.table("plan_allocations")
        .select("*")
        .eq("plan_id", plan["id"])
        .eq("is_active", True)
        .order("is_default", desc=True)
        .order("id")
        .execute()
        .data
    )
    return {
        "id": plan["id"],
        "salary": plan["salary"],
        "allocations": allocations,
    }


@with_db_connection
def create_plan(salary: float):
    """Deactivate any active plan and insert a new active plan with the two
    mandatory default allocations. Returns the new plan id.

    Targets here are placeholders — the first save corrects them via the
    balancing rule (Savings = salary - sum(non-Savings targets)).
    """
    client = get_supabase()
    # Only ever one active plan; retire the previous one (soft — is_active flag).
    client.table("plans").update({"is_active": False}).eq("is_active", True).execute()

    plan = client.table("plans").insert({"salary": salary, "is_active": True}).execute().data[0]
    plan_id = plan["id"]

    client.table("plan_allocations").insert([
        {
            "plan_id": plan_id,
            "label": "Savings",
            "target_rm": salary,
            "tracking_mode": "leftover",
            "is_default": True,
            "is_active": True,
        },
        {
            "plan_id": plan_id,
            "label": "Daily Spending",
            "target_rm": 0,
            "tracking_mode": "tagged",
            "is_default": True,
            "is_active": True,
        },
    ]).execute()

    return plan_id


@with_db_connection
def update_plan_salary(plan_id: int, salary: float):
    """Update the salary basis on a plan."""
    client = get_supabase()
    return client.table("plans").update({"salary": salary}).eq("id", plan_id).execute()


@with_db_connection
def add_allocation(plan_id: int, label: str, target_rm: float, percent=None):
    """Insert a custom (tagged) bucket. Returns the new row.

    `percent` records the bucket's share of salary when it is %-based (e.g. EPF
    11%); None means RM-based (target_rm is the fixed source of truth)."""
    client = get_supabase()
    row = {
        "plan_id": plan_id,
        "label": label,
        "target_rm": target_rm,
        "tracking_mode": "tagged",
        "is_default": False,
        "is_active": True,
        "percent": percent,
    }
    return client.table("plan_allocations").insert(row).execute().data[0]


@with_db_connection
def update_allocation(allocation_id: int, target_rm: float, percent=None):
    """Update a bucket's RM target (and %-mode). Allowed for default buckets too —
    only the target/mode is editable; their label/existence is locked elsewhere.

    `percent` is the stored share of salary for %-based buckets; passing None
    switches the bucket back to RM-based."""
    client = get_supabase()
    return (
        client.table("plan_allocations")
        .update({"target_rm": target_rm, "percent": percent})
        .eq("id", allocation_id)
        .execute()
    )


@with_db_connection
def deactivate_allocation(allocation_id: int):
    """Soft-delete a custom bucket (is_active = false).

    GUARD: default buckets (Savings, Daily Spending) are never deletable — raise
    ValueError so the rule holds even if a caller bypasses the UI.
    """
    client = get_supabase()
    rows = (
        client.table("plan_allocations")
        .select("is_default")
        .eq("id", allocation_id)
        .limit(1)
        .execute()
        .data
    )
    if rows and rows[0]["is_default"]:
        raise ValueError("Default allocations cannot be removed.")

    return (
        client.table("plan_allocations")
        .update({"is_active": False})
        .eq("id", allocation_id)
        .execute()
    )


@with_db_connection
def set_savings_target(plan_id: int, target_rm: float):
    """Set the Savings (default, leftover) bucket's target — the balancing rule's
    computed S - T. Savings is never hand-entered."""
    client = get_supabase()
    return (
        client.table("plan_allocations")
        .update({"target_rm": target_rm})
        .eq("plan_id", plan_id)
        .eq("is_default", True)
        .eq("tracking_mode", "leftover")
        .execute()
    )


@with_db_connection
def get_allocation_actuals(year: int, month: int):
    """Deterministic month-end planned-vs-actual table. One dict per active
    allocation:
        {"label", "target_rm", "actual_rm", "variance_rm", "tracking_mode"}
    with variance_rm = actual_rm - target_rm. Returns [] when no active plan.

    tagged   -> actual = SUM(expenses.amount) where allocation == label that month
    leftover -> actual = SUM(income that month) - SUM(all expenses that month)
    """
    plan = get_active_plan()
    if plan is None:
        return []

    expenses = get_expenses(month=month, year=year)
    income = get_income(month=month, year=year)
    total_expenses = sum(e["amount"] for e in expenses)
    total_income = sum(i["amount"] for i in income)

    results = []
    for alloc in plan["allocations"]:
        label = alloc["label"]
        target_rm = alloc["target_rm"]
        mode = alloc["tracking_mode"]

        if mode == "leftover":
            actual_rm = total_income - total_expenses
        else:  # tagged
            actual_rm = sum(e["amount"] for e in expenses if e.get("allocation") == label)

        results.append({
            "label": label,
            "target_rm": target_rm,
            "actual_rm": actual_rm,
            "variance_rm": actual_rm - target_rm,
            "tracking_mode": mode,
        })

    return results