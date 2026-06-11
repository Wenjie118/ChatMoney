import os
import base64
import time
from datetime import date
import json

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage
from google.genai.errors import APIError

from db import get_expenses, get_income, get_balance

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

PARSER_TEMPLATE = """
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
- category: one of [Food, Transport, Shopping, Entertainment, Health, Bills, Other]
- description: a short description string, or null if unclear
- date: in YYYY-MM-DD format

For INCOME items, each object must have:
- type: "income"
- amount: a number (no currency symbols)
- source: one of [Salary, Transfer, Interest, Other]
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

PDF_PARSER_TEMPLATE = """
You are a financial statement parser for a Malaysian personal finance app.

You will be given a Malaysian bank statement PDF (e.g. Maybank, CIMB, Public Bank,
RHB, Hong Leong, Touch 'n Go eWallet, etc.). Read the entire document and extract
EVERY transaction line into a JSON array.

For each transaction:
- Determine whether it is an EXPENSE (money out / debit / withdrawal / payment) or
  INCOME (money in / credit / deposit / salary / transfer received).
- Infer the category or source from the merchant name or description.

Each EXPENSE object must have:
- type: "expense"
- amount: a positive number (no currency symbols, no commas)
- category: one of [Food, Transport, Shopping, Entertainment, Health, Bills, Other]
- description: a short description (the merchant or narration), or null if unclear
- date: in YYYY-MM-DD format

Each INCOME object must have:
- type: "income"
- amount: a positive number (no currency symbols, no commas)
- source: one of [Salary, Transfer, Interest, Other]
- description: a short description (the payer or narration), or null if unclear
- date: in YYYY-MM-DD format

Rules:
- Extract ALL transactions you can find, in order.
- amount is always a positive number; the type field captures the direction.
- Malaysian statements often use DR/CR columns or a debit/credit sign — use those to
  decide expense vs income.
- Dates may appear as DD/MM/YYYY, DD-MM-YYYY, DD MMM YYYY, etc. Convert to YYYY-MM-DD.
  If a transaction's year is missing, infer it from the statement period.
- Ignore non-transaction lines (opening/closing balances, totals, headers, footers).
- If no date can be determined for a row, use today's date: {today}
- Return ONLY a valid JSON array. No markdown, no code blocks, no explanation.
"""

def parse_pdf_transactions(pdf_bytes: bytes) -> list[dict]:
    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

    message = HumanMessage(content=[
        {"type": "text", "text": PDF_PARSER_TEMPLATE.format(today=date.today().isoformat())},
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
        print("=" * 60)
        print("[parse_pdf_transactions] Failed to parse Gemini output.")
        print(f"  error: {e}")
        print(f"  content length: {len(raw)}")
        print(f"  raw output (first 3000 chars):\n{raw[:3000]}")
        print("=" * 60)
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

def get_advice(month: int | None = None, year: int | None = None) -> str:
    today = date.today()
    month = month or today.month
    year = year or today.year

    expenses = get_expenses(month=month, year=year)
    income = get_income(month=month, year=year)
    balance = get_balance()

    total_income = sum(i["amount"] for i in income)
    total_expenses = sum(e["amount"] for e in expenses)
    net_savings = total_income - total_expenses
    savings_rate = (net_savings / total_income * 100) if total_income > 0 else 0.0

    summary = {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_savings": net_savings,
        "savings_rate": savings_rate,
        "current_balance": balance["current_balance"],
    }
    period = date(year, month, 1).strftime("%B %Y")

    expenses_json = json.dumps(expenses, indent=2)
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