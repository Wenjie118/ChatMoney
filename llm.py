import os
import base64
import time
import calendar
import logging
from datetime import date
import json

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage
from google.genai.errors import APIError

from db import (
    get_expenses,
    get_expenses_until_today,
    get_income,
    get_balance,
    summarize_transactions,
)

logger = logging.getLogger(__name__)

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY is missing from .env")

parser_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    google_api_key=api_key
)

advisor_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.7,
    google_api_key=api_key
)

# HTTP status codes worth retrying: rate limit + transient server errors
_TRANSIENT_CODES = {429, 500, 502, 503, 504}


def _invoke_with_retry(invoke_fn, attempts: int = 3, base_delay: float = 1.5):
    """Call an LLM invoke, retrying transient API errors with exponential backoff.

    Non-transient errors (bad request, auth, etc.) are raised immediately.
    Raises the final APIError if all retries are exhausted.
    """
    for attempt in range(attempts):
        try:
            return invoke_fn()
        except APIError as e:
            if getattr(e, "code", None) not in _TRANSIENT_CODES or attempt == attempts - 1:
                raise
            time.sleep(base_delay * (2 ** attempt))


def _friendly_api_error(e: APIError) -> str:
    """Turn a Google API error into a clear, user-facing message."""
    code = getattr(e, "code", None)
    if code in {500, 502, 503, 504}:
        return (
            "The AI service is busy right now (high demand). "
            "Please wait a moment and try again."
        )
    if code == 429:
        return (
            "The AI service rate limit was reached. "
            "Please wait a minute and try again."
        )
    if code in {401, 403}:
        return (
            "The AI service rejected the request. "
            "Check that your GOOGLE_API_KEY is valid and active."
        )
    return f"The AI service returned an error (code {code}). Please try again."


# ===========================================================================
# Canonical category / source lists — the SINGLE SOURCE OF TRUTH.
#
# These are injected into the parser prompts below (no hard-coded list in the
# template text), so the values the LLM is allowed to emit can never silently
# drift from this list. The frontend's `frontend/lib/constants.ts` mirrors these
# (it drives the review dropdowns) — keep the two in sync; see the note there.
# ===========================================================================
EXPENSE_CATEGORIES = [
    "Food",
    "Transport",
    "Shopping",
    "Entertainment",
    "Health",
    "Bills",
    "Transfer",
    "Other",
]

INCOME_SOURCES = ["Salary", "Transfer", "Interest", "Other"]

# "Transfer" labels a move between the user's OWN accounts — not real spending
# or earning. Both legs (expense + income) net to zero in Balance / Net Savings.
TRANSFER = "Transfer"


def _format_options(options: list[str]) -> str:
    """Render an option list as the "[A, B, C]" text the prompts embed."""
    return "[" + ", ".join(options) + "]"


_PARSER_TEMPLATE = """
You are a financial transaction parser for a Malaysian personal finance app.

First, determine if the user message describes an EXPENSE or INCOME.

EXPENSE — money spent or paid out
Examples: bought lunch, paid Grab, spent on groceries, paid electricity bill

INCOME — money received or earned
Examples: received salary, got paid, freelance payment, received allowance

Extract ALL transactions and return ONLY a JSON array.

For EXPENSE items, each object must have:
- type: "expense"
- amount: a number (no currency symbols)
- category: one of {expense_categories}
- description: a short description string, or null if unclear
- date: in YYYY-MM-DD format

For INCOME items, each object must have:
- type: "income"
- amount: a number (no currency symbols)
- source: one of {income_sources}
- description: a short description string, or null if unclear
- date: in YYYY-MM-DD format

Rules:
- Always return a JSON array, even for a single transaction
- A single message can contain both expenses and income — extract all of them
- If no date is mentioned, use today's date: {today}
- Never return anything outside the JSON array
- No markdown, no explanation, no code blocks

User message: {user_input}
"""

# Inject the canonical lists once, at import. This leaves only {today} and
# {user_input} as live PromptTemplate variables.
PARSER_TEMPLATE = (
    _PARSER_TEMPLATE
    .replace("{expense_categories}", _format_options(EXPENSE_CATEGORIES))
    .replace("{income_sources}", _format_options(INCOME_SOURCES))
)

def _content_to_text(content) -> str:
    """Normalize an LLM response's content into a plain string.

    Gemini can return content as a list of blocks (e.g. when thinking is on),
    so join any text parts rather than assuming a bare string.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(block.get("text", ""))
        return "".join(parts)
    return str(content)


def _extract_json_array(raw) -> list[dict]:
    text = _content_to_text(raw).strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        transactions = json.loads(text)
    except json.JSONDecodeError:
        # Fallback: pull out the outermost [...] in case the model wrapped the
        # array in prose or a truncated trailer.
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1 or end < start:
            raise
        transactions = json.loads(text[start:end + 1])
    if not isinstance(transactions, list):
        raise ValueError("Expected a JSON array of transactions")
    return transactions

def parse_transaction(user_input: str) -> list[dict]:
    today = date.today().isoformat()

    prompt = PromptTemplate(
        input_variables=["today", "user_input"],
        template=PARSER_TEMPLATE
    )

    chain = prompt | parser_llm

    try:
        response = _invoke_with_retry(lambda: chain.invoke({
            "today": today,
            "user_input": user_input
        }))
    except APIError as e:
        raise ValueError(_friendly_api_error(e)) from e

    try:
        return _extract_json_array(response.content)
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(
            "Could not parse your message. Try rephrasing, e.g. 'Spent RM50 on groceries'."
        ) from e

def _format_wallets_for_prompt(wallets) -> str:
    """Wallet-matching context for the PDF parser prompt.

    `wallets` is the list of active wallet dicts (each with a 'name'). Returns a
    block naming them so the model can tag each transaction, or a clear
    'no wallets' instruction. The golden rule — never guess — is stated here and
    reinforced in the object spec + rules: a wrong wallet is worse than a blank one
    because a blank is visible in "Unassigned" and a wrong one is not.
    """
    names = [w["name"] for w in (wallets or []) if w.get("name")]
    if not names:
        return 'WALLETS: the user has no wallets set up — always set "wallet" to null.'
    joined = ", ".join(f'"{n}"' for n in names)
    return (
        "WALLETS: the user's active wallets are: " + joined + ".\n"
        'For each transaction set "wallet" to the EXACT name of the wallet it '
        "belongs to, inferred from the description. If you are not confident which "
        'wallet it is, set "wallet" to null — NEVER guess a wallet.'
    )


_PDF_PARSER_TEMPLATE = """
You are a financial statement parser for a Malaysian personal finance app.

You will be given a Malaysian bank statement PDF (e.g. Maybank, CIMB, Public Bank,
RHB, Hong Leong, Touch 'n Go eWallet, etc.). Read the entire document and extract
EVERY transaction line into a JSON array.

For each transaction:
- Determine whether it is an EXPENSE (money out / debit / withdrawal / payment) or
  INCOME (money in / credit / deposit / salary / transfer received).
- Infer the category or source from the merchant name or description.

{wallets}

Each EXPENSE object must have:
- type: "expense"
- amount: a positive number (no currency symbols, no commas)
- category: one of {expense_categories}
- description: a short description (the merchant or narration), or null if unclear
- date: in YYYY-MM-DD format
- wallet: an EXACT wallet name from the WALLETS list above, or null (see rules)

Each INCOME object must have:
- type: "income"
- amount: a positive number (no currency symbols, no commas)
- source: one of {income_sources}
- description: a short description (the payer or narration), or null if unclear
- date: in YYYY-MM-DD format
- wallet: an EXACT wallet name from the WALLETS list above, or null (see rules)

Rules:
- Extract ALL transactions you can find, in order.
- amount is always a positive number; the type field captures the direction.
- Malaysian statements often use DR/CR columns or a debit/credit sign — use those to
  decide expense vs income.
- Dates may appear as DD/MM/YYYY, DD-MM-YYYY, DD MMM YYYY, etc. Convert to YYYY-MM-DD.
  If a transaction's year is missing, infer it from the statement period.
- Ignore non-transaction lines (opening/closing balances, totals, headers, footers).
- If no date can be determined for a row, use today's date: {today}
- "wallet" MUST be either an exact name from the WALLETS list or null. When unsure,
  use null — never guess a wallet.
- Return ONLY a valid JSON array. No markdown, no code blocks, no explanation.
"""

# Inject the canonical lists once, at import. This leaves only {today} as a live
# .format() field (filled in parse_pdf_transactions below).
PDF_PARSER_TEMPLATE = (
    _PDF_PARSER_TEMPLATE
    .replace("{expense_categories}", _format_options(EXPENSE_CATEGORIES))
    .replace("{income_sources}", _format_options(INCOME_SOURCES))
)


def parse_pdf_transactions(pdf_bytes: bytes, wallets=None) -> list[dict]:
    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

    prompt_text = PDF_PARSER_TEMPLATE.format(
        today=date.today().isoformat(),
        wallets=_format_wallets_for_prompt(wallets),
    )

    message = HumanMessage(content=[
        {"type": "text", "text": prompt_text},
        {
            "type": "file",
            "source_type": "base64",
            "mime_type": "application/pdf",
            "data": pdf_base64,
        },
    ])

    try:
        response = _invoke_with_retry(lambda: parser_llm.invoke([message]))
    except APIError as e:
        raise ValueError(_friendly_api_error(e)) from e

    try:
        return _extract_json_array(response.content)
    except (json.JSONDecodeError, ValueError) as e:
        raw = _content_to_text(response.content)
        # Warning-level: a concise, safe one-liner (no giant payload on stdout).
        logger.warning(
            "parse_pdf_transactions: failed to parse Gemini output (%s); content length=%d",
            e, len(raw),
        )
        # Debug-level: the actual raw output, truncated. Only surfaces when debug
        # logging is enabled, so we can diagnose without leaking big payloads by default.
        logger.debug(
            "parse_pdf_transactions raw output (first 3000 chars):\n%s", raw[:3000]
        )
        raise ValueError(
            "Could not read transactions from this PDF. "
            "Make sure it is a readable bank statement and try again."
        ) from e

ADVISOR_TEMPLATE = """
You are a friendly and practical personal finance advisor for a Malaysian user.

Here is the user's financial data for {period}:

CURRENT BALANCE (latest overall estimate, not specific to {period}):
{balance}

SUMMARY FOR {period}:
{summary}

INCOME HISTORY FOR {period}:
{income}

EXPENSE HISTORY FOR {period}:
{expenses}

Based on this data, provide:
1. An overview of {period} — how much they earned, spent, and saved that month
2. Their latest current balance and what it means for them right now
3. Their savings rate for {period} and whether it is healthy
   (a good savings rate is 20% or above)
4. Which expense category they should control to improve their finances
5. Two or three concrete actionable tips based on their situation

Rules:
- Be specific — always reference actual RM amounts from the data
- Use Ringgit (RM) for all amounts
- All income/expense/savings figures refer to {period}
- Keep your response conversational and encouraging, not robotic
- Never make up numbers that are not in the data

Situation rules:
- If income contains Salary entries → focus on savings rate and monthly budget
- If income exists but no Salary → acknowledge irregular income, focus on expense control
- If total_income is zero → do not calculate savings rate, summarize expenses only, encourage user to log income, focus on helping them survive on their current balance
- If savings rate is negative → gently flag overspending without being harsh
- If balance is low relative to monthly expenses → mention runway without alarming the user
- current_balance is an estimate based on manual_balance plus transactions since last_updated — present it as an estimate, not a guaranteed figure
"""

# Above this many expense rows in a month, send the advisor a compact
# per-category breakdown instead of every individual row. The advice reasons over
# category totals and the summary, not line items, so this keeps quality while
# cutting prompt tokens (cost/latency, and context-limit risk) on busy months.
ADVISOR_MAX_EXPENSE_ROWS = 40


def _aggregate_expenses_by_category(expenses: list[dict]) -> dict:
    """Collapse expense rows into {category: {total, count}} for the advisor prompt.

    Preserves the real category names and RM amounts the advice must reference,
    without shipping every individual transaction.
    """
    by_category: dict[str, dict] = {}
    for e in expenses:
        cat = e.get("category") or "Other"
        entry = by_category.setdefault(cat, {"total": 0.0, "count": 0})
        entry["total"] += e.get("amount", 0)
        entry["count"] += 1
    for entry in by_category.values():
        entry["total"] = round(entry["total"], 2)
    return by_category


def get_advice(month: int | None = None, year: int | None = None) -> str:
    today = date.today()
    month = month or today.month
    year = year or today.year

    expenses = get_expenses(month=month, year=year)
    income = get_income(month=month, year=year)
    balance = get_balance()

    # Shared math (same helper the DB summary and /transactions/summary use), plus
    # the current-balance estimate the advisor prompt also references.
    summary = summarize_transactions(income, expenses)
    summary["current_balance"] = balance["current_balance"]
    period = date(year, month, 1).strftime("%B %Y")

    # For busy months, aggregate expenses per category to keep the prompt compact;
    # small months send the full row list unchanged (identical to before).
    if len(expenses) > ADVISOR_MAX_EXPENSE_ROWS:
        expenses_payload: object = {
            "note": "aggregated per-category totals (many transactions this month)",
            "expense_count": len(expenses),
            "by_category": _aggregate_expenses_by_category(expenses),
        }
    else:
        expenses_payload = expenses
    expenses_json = json.dumps(expenses_payload, indent=2)
    income_json = json.dumps(income, indent=2)
    summary_json = json.dumps(summary, indent=2)
    balance_json = json.dumps(balance, indent=2)

    prompt = PromptTemplate(
        input_variables=["period", "summary", "income", "expenses", "balance"],
        template=ADVISOR_TEMPLATE
    )

    chain = prompt | advisor_llm

    try:
        response = _invoke_with_retry(lambda: chain.invoke({
            "period": period,
            "summary": summary_json,
            "income": income_json,
            "expenses": expenses_json,
            "balance": balance_json
        }))
    except APIError as e:
        raise ValueError(_friendly_api_error(e)) from e

    return _content_to_text(response.content).strip()

SPENDING_ANALYSIS_TEMPLATE = """
You are a friendly, practical personal finance coach for a Malaysian user.

This is a PROVISIONAL, mid-month check-in. The figures below cover spending
SO FAR in {period} only — the month is NOT over yet. Always frame it that way
("so far this month", "at this pace") and never say "this month you spent" as
if it were final.

This is EXPENSE-ONLY. Do NOT mention income, savings, or savings rate, and do
NOT comment on how much they saved — you do not have that data.

SPENDING SO FAR THIS MONTH ({period}):
{summary}

How to read the data:
- days_elapsed / days_in_month tells you how far into the month we are.
- For each category, spent_so_far is the real amount spent up to today.
- projected_month_end is a SIMPLE linear estimate ALREADY CALCULATED FOR YOU
  (spent_so_far scaled from days_elapsed up to days_in_month). It is provided
  so you don't have to do any maths. Reference these exact RM numbers — do NOT
  recompute, re-scale, or invent your own projections.

Use your judgement on the projections — they are ROUGH:
- A linear projection assumes steady, recurring spending. That is reasonable for
  things like Food, Transport, or Entertainment.
- It is MISLEADING for one-off costs. If a category looks like a single large
  lump (e.g. annual insurance, a flight, a yearly subscription, a big one-time
  purchase), say so plainly, treat its projection as NOT realistic, and do NOT
  tell the user to "cut" it — it likely won't repeat this month.

Based on the data, give:
1. Which categories are running high so far this month (reference RM amounts).
2. A rough month-end projection for the RECURRING categories using the given
   projected_month_end figures, and what that pace implies if it continues.
3. Two or three concrete, specific tips to reduce spending for the REST of this
   month.

Rules:
- Use Ringgit (RM) for every amount.
- Only use the numbers given above — never make up figures.
- Keep it conversational and encouraging, not robotic or preachy.
"""


def get_spending_analysis(month: int | None = None, year: int | None = None) -> str:
    # `int | None` = "an int OR None" (PEP 604 union type). Like Java's
    # @Nullable Integer; the `| None` plus the `= None` default lets callers
    # omit the argument. Same shape as get_advice's signature.
    today = date.today()

    # 1. Default month/year to today (`a or b` returns b when a is None/0).
    month = month or today.month
    year = year or today.year

    # 2. Pull PROVISIONAL expenses (bounded to today for the current month).
    expenses = get_expenses_until_today(month=month, year=year)

    # 3. Compute everything IN CODE. The LLM does NO arithmetic.

    #    days_in_month -> calendar.monthrange(year, month)[1]
    #    (monthrange returns a (weekday_of_1st, num_days) tuple; [1] = day count)
    days_in_month = calendar.monthrange(year, month)[1]

    #    days_elapsed:
    #      - current real month -> today's day number
    #      - past/future month  -> the full month (treat as complete)
    if month == today.month and year == today.year:
        days_elapsed = today.day
    else:
        days_elapsed = days_in_month

    #    per-category totals -> dict: category(str) -> summed amount(float).
    #    dict.get(key, default) returns the default instead of raising KeyError
    #    (Java's Map.get would return null here).
    category_totals: dict[str, float] = {}
    for e in expenses:
        cat = e["category"]
        if cat == TRANSFER:
            # Internal account move, not real spending — keep it out of
            # total_so_far, the per-category breakdown, and the projection.
            continue
        category_totals[cat] = category_totals.get(cat, 0.0) + e["amount"]

    #    round each category total to 2 dp (money).
    category_totals = {cat: round(total, 2) for cat, total in category_totals.items()}

    #    total_so_far -> `sum(...)` over a generator expression (lazy one-liner,
    #    like a Java stream .mapToDouble(...).sum()).
    total_so_far = round(sum(category_totals.values()), 2)

    #    per-category linear projection = total / days_elapsed * days_in_month.
    #    DICT COMPREHENSION: "build {key: value} for each pair"; .items() yields
    #    (key, value) tuples and `for cat, total` unpacks each tuple.
    projections = {
        cat: round(total / days_elapsed * days_in_month, 2)
        for cat, total in category_totals.items()
    }

    # 4. Build the summary dict, then JSON-dump it for the prompt.
    summary = {
        "days_elapsed": days_elapsed,
        "days_in_month": days_in_month,
        "total_so_far": total_so_far,
        "categories": {
            cat: {
                "spent_so_far": total,
                "projected_month_end": projections[cat],
            }
            for cat, total in category_totals.items()
        },
    }
    summary_json = json.dumps(summary, indent=2)

    #    period string, e.g. "June 2026" (same idiom as get_advice).
    period = date(year, month, 1).strftime("%B %Y")

    # 5. Wire up the LLM call (mirror get_advice's structure exactly).
    prompt = PromptTemplate(
        input_variables=["period", "summary"],
        template=SPENDING_ANALYSIS_TEMPLATE
    )

    chain = prompt | advisor_llm

    try:
        response = _invoke_with_retry(lambda: chain.invoke({
            "period": period,
            "summary": summary_json,
        }))
    except APIError as e:
        raise ValueError(_friendly_api_error(e)) from e

    return _content_to_text(response.content).strip()