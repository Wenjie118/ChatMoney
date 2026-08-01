import os
import socket
from functools import wraps
from typing import NamedTuple
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
def save_expense(amount, category, expense_date, desc=None, wallet_id=None):
    client = get_supabase()
    expense = {
        "amount": amount,
        "category": category,
        "description": desc,
        "date": expense_date
    }
    # Optional wallet tag. Only included when set so untagged saves keep working
    # even before the wallets migration adds the column (income has one too).
    if wallet_id is not None:
        expense["wallet_id"] = wallet_id
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
def get_expenses_until_today(month, year):
    """Like get_expenses, but bounds the END date to today, so the CURRENT
    month is cut off at today while PAST months still return the full month.

    Same return shape as get_expenses: list[dict] with keys
    id, amount, category, description, date, created_at.
    """
    client = get_supabase()
    today = date.today()

    # start: first day of the month — identical to get_expenses.
    start = date(year, month, 1)

    # last day of the month.
    # calendar.monthrange(year, month) returns a (weekday_of_1st, num_days)
    # TUPLE. [1] grabs the 2nd element (the day count). In Python you index a
    # tuple like an array; there is no getter method.
    month_end = date(year, month, calendar.monthrange(year, month)[1])

    # end: the EARLIER of today and the month's last day.
    # min() works directly on date objects because dates are orderable in
    # Python (the < operator is defined for them — no Comparable boilerplate).
    #   - current month  -> today is before month_end  -> min picks today
    #   - past month     -> today is after  month_end  -> min picks month_end (full month)
    end = min(today, month_end)

    # Mirror get_expenses' query exactly, but with the start/end above.
    response = (
        client.table("expenses")
        .select("*")
        .gte("date", start.isoformat())
        .lte("date", end.isoformat())
        .execute()
    )
    return response.data


@with_db_connection
def save_income(amount, source, income_date, desc=None, wallet_id=None):
    client = get_supabase()
    income = {
        "amount": amount,
        "source": source,
        "description": desc,
        "date": income_date
    }
    # Optional wallet tag (see save_expense). Omitted when None so pre-migration
    # untagged saves still succeed.
    if wallet_id is not None:
        income["wallet_id"] = wallet_id
    response = client.table("income").insert(income).execute()
    return response

@with_db_connection
def get_income(month, year):
    client = get_supabase()
    start = date(year, month, 1).isoformat()
    end = date(year, month, calendar.monthrange(year, month)[1]).isoformat()
    response = client.table("income").select("*").gte("date", start).lte("date", end).execute()
    return response.data

def summarize_transactions(income: list[dict], expenses: list[dict]) -> dict:
    """Compute the headline monthly figures from a month's income + expense rows.

    THE single source of truth for the {total_income, total_expenses,
    net_savings, savings_rate} math shared by get_monthly_summary, the
    /transactions/summary route, and llm.get_advice. The divide-by-zero guard
    (savings_rate = 0.0 when there is no income) lives here, in one place.

    `current_balance` is intentionally NOT included — it comes from get_balance()
    and is added by the callers that need it.
    """
    total_income = sum(i["amount"] for i in income)
    total_expenses = sum(e["amount"] for e in expenses)
    net_savings = total_income - total_expenses
    savings_rate = (net_savings / total_income * 100) if total_income > 0 else 0.0
    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_savings": net_savings,
        "savings_rate": savings_rate,
    }


@with_db_connection
def get_monthly_summary():
    current = date.today()

    incomes = get_income(current.month, current.year)
    expenses = get_expenses(current.month, current.year)

    details = summarize_transactions(incomes, expenses)
    details["current_balance"] = get_balance()["current_balance"]

    return details

@with_db_connection
def get_balance():
    """Current balance — DERIVED from wallets, never stored as its own figure.

        current_balance = Σ(active wallet balances) + unassigned

    So editing a wallet MOVES the total by exactly that much, instead of stacking
    on top of a separate balance number. There is no "set the balance" action any
    more: you set a wallet, and the balance follows.

    `unassigned` is real money that isn't in a wallet yet (e.g. a PDF import whose
    wallet couldn't be inferred). It's counted so money is never silently dropped,
    and the UI surfaces those rows for assignment — once everything is assigned,
    current_balance is exactly the sum of your wallets.

    The `balance` table is no longer a source of money. Its latest row survives ONLY
    as the wallet-era ANCHOR (see _balance_anchor); its manual_balance column is
    ignored.

    Returns {current_balance, wallet_total, unassigned, last_updated}, where
    last_updated is the date of the most recent movement (None when there are none).
    """
    client = get_supabase()
    moves = _post_anchor_movements(client, _balance_anchor(client))
    active_ids = _active_wallet_ids(client)

    balances = _compute_wallet_balances(active_ids, moves)
    wallet_total = sum(balances.values())
    unassigned = _compute_unassigned(active_ids, moves)

    return {
        "current_balance": round(wallet_total + unassigned, 2),
        "wallet_total":    round(wallet_total, 2),
        "unassigned":      round(unassigned, 2),
        "last_updated":    _latest_movement_date(moves),
    }


def save_multiple_transactions(transactions: list) -> dict:
    saved = 0
    failed = 0
    for t in transactions:
        try:
            # Reject rows with no category/source (e.g. a manual row where the
            # dropdown was never picked). Saving these produces uncategorized
            # transactions that break the per-category dashboard breakdown, so we
            # skip and count them as failed rather than writing bad data.
            label = t.get("category") or t.get("source")
            if not label or not str(label).strip():
                failed += 1
                continue
            if t["type"] == "income":
                save_income(
                    amount=t["amount"],
                    source=t.get("source") or t.get("category"),
                    income_date=t["date"],
                    desc=t.get("description"),
                    wallet_id=t.get("wallet_id"),
                )
            elif t["type"] == "expense":
                save_expense(
                    amount=t["amount"],
                    category=t.get("category") or t.get("source"),
                    expense_date=t["date"],
                    desc=t.get("description"),
                    wallet_id=t.get("wallet_id"),
                )
            else:
                failed += 1
                continue
            saved += 1
        except DatabaseConnectionError:
            # Supabase is unreachable — this is a total outage, not a bad row.
            # Propagate so the route returns a 503 ("database is down") instead of
            # silently counting every row as a per-row failure and returning 200.
            raise
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
# Wallets — virtual sub-wallets with COMPUTED, ledger-based balances.
#
# A wallet's balance is never stored; it is summed on read from its movements:
#   tagged income (+), transfer in (+), transfer out (−), tagged expense (−),
#   adjustment (± its signed amount).
#
# THREE KINDS OF MOVEMENT, deliberately kept in separate tables:
#   • income / expenses      money entering or leaving your life — a BUDGET EVENT,
#                            so these are the only rows the monthly summary,
#                            category charts and AI advisor ever read.
#   • wallet_transfers       money changing wallet; nets to zero system-wide.
#   • wallet_adjustments     a correction to what a wallet holds ("it should
#                            actually be RM 500"). Real money, so it moves the
#                            wallet and the balance — but it is NOT a budget
#                            event, so it must never reach a report. Keeping it
#                            out of income/expenses is what guarantees that.
#
# THE INVARIANT (correctness gate):
#     Σ(active wallet balances) + unassigned == current_balance
# This now holds BY CONSTRUCTION rather than by coincidence: get_balance() is
# literally defined as that sum. Wallets and Unassigned partition every movement
# inside the horizon exactly once — money tagged to a NULL wallet OR to a
# soft-deleted (inactive) wallet falls to Unassigned, so nothing is lost or
# double-counted, even after a delete.
#
# The aggregation is split into pure, network-free helpers (_compute_*) so the
# invariant can be unit-tested without touching Supabase.
# ===========================================================================

# ---- Wallet CRUD (Layer 1) ------------------------------------------------

@with_db_connection
def create_wallet(name: str):
    """Create an active wallet. Returns the new row."""
    client = get_supabase()
    return client.table("wallets").insert({"name": name, "is_active": True}).execute().data[0]


@with_db_connection
def get_wallets(active_only: bool = True):
    """List wallets, oldest first. active_only hides soft-deleted ones."""
    client = get_supabase()
    query = client.table("wallets").select("*")
    if active_only:
        query = query.eq("is_active", True)
    return query.order("id").execute().data


@with_db_connection
def rename_wallet(wallet_id: int, name: str):
    """Rename a wallet."""
    client = get_supabase()
    return client.table("wallets").update({"name": name}).eq("id", wallet_id).execute()


@with_db_connection
def deactivate_wallet(wallet_id: int):
    """Soft-delete a wallet (is_active = false). Never hard-delete — its ledger
    rows stay valid and its money folds into Unassigned.

    GUARD: refuses to remove the LAST active wallet. The app is wallet-centric
    (balance = sum of wallets, entry requires a wallet), so it always keeps at
    least one to avoid no-wallet error states."""
    client = get_supabase()
    active = client.table("wallets").select("id").eq("is_active", True).execute().data
    if len(active) <= 1:
        raise ValueError("You must keep at least one wallet.")
    return client.table("wallets").update({"is_active": False}).eq("id", wallet_id).execute()


@with_db_connection
def set_wallet_balance(wallet_id: int, target_amount: float):
    """Correct a wallet to an exact balance by recording an ADJUSTMENT for the
    delta, tagged to the wallet.

    This is the "edit a wallet's balance" action: it means "this wallet should
    actually hold this much", so it changes the wallet AND the overall balance
    (which is the sum of wallet balances). Money is not moved between wallets —
    that is the transfer feature. Balances stay computed/auditable (no stored
    balance). Returns the delta applied (0.0 when already at target).

    The delta goes to `wallet_adjustments`, NOT to income/expenses. A correction
    is not something you earned or spent, so counting it as either would inflate
    the monthly summary, the category charts and the advisor's savings rate — the
    whole reason that table exists."""
    current = get_wallet_balance(wallet_id)
    delta = round(float(target_amount) - current, 2)
    if abs(delta) < 0.005:
        return 0.0

    create_wallet_adjustment(wallet_id, delta, desc="Wallet balance adjustment")
    return delta


@with_db_connection
def create_wallet_adjustment(wallet_id: int, amount: float, desc=None, adj_date=None):
    """Record a signed correction against a wallet (+ raises it, − lowers it).

    Deliberately NOT an income or expense row — see the module header. Defaults to
    today's date, matching how the other manual entry points behave."""
    if amount == 0:
        raise ValueError("An adjustment cannot be zero.")
    client = get_supabase()
    row = {
        "wallet_id": wallet_id,
        "amount": amount,
        "description": desc,
        "date": adj_date or date.today().isoformat(),
    }
    return client.table("wallet_adjustments").insert(row).execute().data[0]


# ---- Balance horizon + fetch helpers --------------------------------------

def _balance_anchor(client):
    """created_at of the latest `balance` row — the WALLET-ERA HORIZON.

    Only movements recorded strictly after it count toward wallets and the balance;
    older rows are pre-wallet history that the anchor row already summarised, so
    counting them again would double up. The row's manual_balance is NOT read —
    balance is the sum of wallets now, not a stored figure.

    Returns None when no balance row exists, which means there is no pre-wallet
    history to exclude and every movement counts (see _post_anchor_movements)."""
    resp = (
        client.table("balance").select("created_at")
        .order("created_at", desc=True).limit(1).execute()
    )
    return resp.data[0]["created_at"] if resp.data else None


def _active_wallet_ids(client):
    """ids of every active (not soft-deleted) wallet."""
    return [w["id"] for w in client.table("wallets").select("id").eq("is_active", True).execute().data]


class Movements(NamedTuple):
    """Every row that can move a wallet, already filtered to the balance horizon.

    Bundled rather than passed as four positional lists so the pure _compute_*
    helpers can't silently receive them in the wrong order."""
    income: list
    expenses: list
    transfers: list
    adjustments: list


def _post_anchor_movements(client, anchor):
    """Fetch the Movements inside the balance horizon: recorded strictly after
    `anchor`, or ALL rows when there is no anchor at all.

    Batched: one query per table (no per-wallet N+1)."""
    def rows(table):
        query = client.table(table).select("*")
        if anchor is not None:
            query = query.gt("created_at", anchor)
        return query.execute().data

    return Movements(
        income=rows("income"),
        expenses=rows("expenses"),
        transfers=rows("wallet_transfers"),
        adjustments=rows("wallet_adjustments"),
    )


def _latest_movement_date(moves: Movements):
    """The most recent `date` across all movements, or None when there are none.
    This is what "last updated" means now that there is no manual balance row to
    date-stamp: the last time money actually moved."""
    dates = [str(r["date"])[:10] for group in moves for r in group if r.get("date")]
    return max(dates) if dates else None


# ---- Pure aggregation (unit-testable, no network) -------------------------

def _compute_wallet_balances(active_ids, moves: Movements):
    """{wallet_id: balance} for the given active wallet ids, from the supplied
    (already horizon-filtered) movements. Movements tagged to a wallet_id NOT
    in active_ids are ignored here — they belong to Unassigned."""
    active = set(active_ids)
    balances = {wid: 0.0 for wid in active}
    for i in moves.income:
        w = i.get("wallet_id")
        if w in balances:
            balances[w] += i["amount"]
    for e in moves.expenses:
        w = e.get("wallet_id")
        if w in balances:
            balances[w] -= e["amount"]
    for t in moves.transfers:
        tw, fw = t.get("to_wallet"), t.get("from_wallet")
        if tw in balances:
            balances[tw] += t["amount"]
        if fw in balances:
            balances[fw] -= t["amount"]
    for a in moves.adjustments:
        w = a.get("wallet_id")
        if w in balances:
            balances[w] += a["amount"]      # already signed
    return balances


def _compute_unassigned(active_ids, moves: Movements):
    """Unassigned total = every movement NOT tied to an active wallet (NULL wallet
    or a soft-deleted one). Transfer sides touching a non-active wallet net in/out
    of Unassigned. Complementary to _compute_wallet_balances, so together they
    partition all money exactly once — which is what makes
    Σ(wallet balances) + unassigned == current_balance true by construction."""
    active = set(active_ids)
    total = 0.0
    total += sum(i["amount"] for i in moves.income if i.get("wallet_id") not in active)
    total -= sum(e["amount"] for e in moves.expenses if e.get("wallet_id") not in active)
    total += sum(t["amount"] for t in moves.transfers if t.get("to_wallet") not in active)
    total -= sum(t["amount"] for t in moves.transfers if t.get("from_wallet") not in active)
    total += sum(a["amount"] for a in moves.adjustments if a.get("wallet_id") not in active)
    return total


# ---- Public balance reads (Layer 1) ---------------------------------------

@with_db_connection
def get_all_wallet_balances():
    """[{id, name, balance}] for every ACTIVE wallet, batched (no N+1)."""
    client = get_supabase()
    wallets = client.table("wallets").select("*").eq("is_active", True).order("id").execute().data
    active_ids = [w["id"] for w in wallets]
    moves = _post_anchor_movements(client, _balance_anchor(client))
    balances = _compute_wallet_balances(active_ids, moves)
    # Round at the read boundary so the wallet cards and the balance (their sum)
    # agree to the cent instead of showing float noise like 100.00000000000013.
    return [
        {"id": w["id"], "name": w["name"], "balance": round(balances.get(w["id"], 0.0), 2)}
        for w in wallets
    ]


@with_db_connection
def get_wallet_balance(wallet_id: int):
    """Computed balance of a single wallet (works for inactive wallets too, for
    the ledger detail view). No date filtering beyond the shared balance anchor."""
    client = get_supabase()
    moves = _post_anchor_movements(client, _balance_anchor(client))
    return round(_compute_wallet_balances([wallet_id], moves)[wallet_id], 2)


@with_db_connection
def get_unassigned_total():
    """Total money not held in any active wallet (NULL/inactive-tagged movements).
    Part of the invariant: Σ(active balances) + this == current_balance."""
    client = get_supabase()
    moves = _post_anchor_movements(client, _balance_anchor(client))
    return round(_compute_unassigned(_active_wallet_ids(client), moves), 2)


@with_db_connection
def get_unassigned_rows():
    """The NULL-wallet (or inactive-wallet) income/expense rows a user can resolve
    by assigning a wallet. Newest first.

    Only income/expenses appear: transfers and adjustments still COUNT toward the
    Unassigned total when they touch a non-active wallet, but there is no
    assign-a-wallet action for them, so listing them as resolvable would be a
    dead end."""
    client = get_supabase()
    moves = _post_anchor_movements(client, _balance_anchor(client))
    active = set(_active_wallet_ids(client))

    rows = []
    for i in moves.income:
        if i.get("wallet_id") not in active:
            rows.append({
                "id": i["id"], "type": "income", "amount": i["amount"],
                "category_or_source": i.get("source"),
                "description": i.get("description"), "date": i["date"],
            })
    for e in moves.expenses:
        if e.get("wallet_id") not in active:
            rows.append({
                "id": e["id"], "type": "expense", "amount": e["amount"],
                "category_or_source": e.get("category"),
                "description": e.get("description"), "date": e["date"],
            })
    rows.sort(key=lambda r: str(r["date"]), reverse=True)
    return rows


# ---- Transfers, tagging resolution & ledger (Layer 2) ---------------------

@with_db_connection
def create_transfer(from_wallet, to_wallet, amount, description=None, transfer_date=None):
    """Record a wallet-to-wallet transfer. amount must be > 0 and the two wallets
    must differ. NULL wallet sides are permitted at this layer only for future PDF
    import; the API enforces both-required on the manual path."""
    if amount is None or amount <= 0:
        raise ValueError("Transfer amount must be greater than 0.")
    if from_wallet is not None and to_wallet is not None and from_wallet == to_wallet:
        raise ValueError("A transfer must be between two different wallets.")
    client = get_supabase()
    row = {
        "from_wallet": from_wallet,
        "to_wallet": to_wallet,
        "amount": amount,
        "description": description,
        "date": transfer_date or date.today().isoformat(),
    }
    return client.table("wallet_transfers").insert(row).execute().data[0]


@with_db_connection
def update_transfer_wallets(transfer_id: int, from_wallet, to_wallet):
    """Fill in previously-NULL wallet sides of an imported transfer."""
    if from_wallet is not None and to_wallet is not None and from_wallet == to_wallet:
        raise ValueError("A transfer must be between two different wallets.")
    client = get_supabase()
    return (
        client.table("wallet_transfers")
        .update({"from_wallet": from_wallet, "to_wallet": to_wallet})
        .eq("id", transfer_id)
        .execute()
    )


@with_db_connection
def update_expense_wallet(expense_id: int, wallet_id):
    """Resolve a NULL-wallet expense by tagging it to a wallet (or back to NULL)."""
    client = get_supabase()
    return client.table("expenses").update({"wallet_id": wallet_id}).eq("id", expense_id).execute()


@with_db_connection
def update_income_wallet(income_id: int, wallet_id):
    """Resolve a NULL-wallet income by tagging it to a wallet (or back to NULL)."""
    client = get_supabase()
    return client.table("income").update({"wallet_id": wallet_id}).eq("id", income_id).execute()


@with_db_connection
def get_wallet_ledger(wallet_id: int):
    """Chronological movements affecting a wallet (post-anchor, so the ledger sums
    to the wallet's balance). Each row: {date, kind, description, amount,
    signed_amount}.
    kind ∈ income | expense | transfer_in | transfer_out | adjustment.

    Adjustments are hidden from every income/expense report, but they belong HERE —
    this is the audit trail that explains why a wallet holds what it holds."""
    client = get_supabase()
    moves = _post_anchor_movements(client, _balance_anchor(client))
    income, expenses, transfers = moves.income, moves.expenses, moves.transfers

    entries = []
    for i in income:
        if i.get("wallet_id") == wallet_id:
            entries.append({"date": i["date"], "kind": "income",
                            "description": i.get("description"),
                            "amount": i["amount"], "signed_amount": i["amount"]})
    for e in expenses:
        if e.get("wallet_id") == wallet_id:
            entries.append({"date": e["date"], "kind": "expense",
                            "description": e.get("description"),
                            "amount": e["amount"], "signed_amount": -e["amount"]})
    for t in transfers:
        if t.get("to_wallet") == wallet_id:
            entries.append({"date": t["date"], "kind": "transfer_in",
                            "description": t.get("description"),
                            "amount": t["amount"], "signed_amount": t["amount"]})
        if t.get("from_wallet") == wallet_id:
            entries.append({"date": t["date"], "kind": "transfer_out",
                            "description": t.get("description"),
                            "amount": t["amount"], "signed_amount": -t["amount"]})
    for a in moves.adjustments:
        if a.get("wallet_id") == wallet_id:
            entries.append({"date": a["date"], "kind": "adjustment",
                            "description": a.get("description"),
                            "amount": abs(a["amount"]), "signed_amount": a["amount"]})

    entries.sort(key=lambda x: str(x["date"]))
    return entries