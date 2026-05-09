import os
from datetime import date
import json

from dotenv import load_dotenv
load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

from db import save_expense, save_income, get_all_expenses, get_income, get_monthly_summary

# --- API Key Guard ---
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY is missing from .env")

# --- Model Initialization ---
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

def parse_transaction(user_input: str) -> list[dict]:
    today = date.today().isoformat()

    prompt = PromptTemplate(
        input_variables=["today", "user_input"],
        template=PARSER_TEMPLATE
    )

    chain = prompt | parser_llm

    response = chain.invoke({
        "today": today,
        "user_input": user_input
    })

    raw = response.content.strip()
    transactions = json.loads(raw)

    return transactions

ADVISOR_TEMPLATE = """
You are a friendly and practical personal finance advisor for a Malaysian user.

Here is the user's financial data for this month:

MONTHLY SUMMARY:
{summary}

INCOME HISTORY:
{income}

EXPENSE HISTORY:
{expenses}

Based on this data, provide:
1. A monthly overview — how much they earned, spent, and saved this month
2. Their current savings rate and whether it is healthy
   (a good savings rate is 20% or above)
3. Which expense category they should control to improve their savings
4. A specific and realistic savings rate target they should aim for
   based on their actual income and spending
5. Two or three concrete actionable tips to reach that target

Rules:
- Be specific — always reference actual RM amounts from the data
- Use Ringgit (RM) for all amounts
- Keep your response conversational and encouraging, not robotic
- If savings rate is negative, gently flag that they are overspending
- If there is no data, tell the user to add some transactions first
- Never make up numbers that are not in the data

# ADD THIS
- If total_income is zero, do not calculate savings rate. Instead, summarize expenses only and encourage the user to log their income for a complete financial picture
"""

def get_advice() -> str:
    expenses = get_all_expenses()
    
    today = date.today()
    income = get_income(month=today.month, year=today.year)
    
    summary = get_monthly_summary()

    expenses_json = json.dumps(expenses, indent=2)
    income_json = json.dumps(income, indent=2)
    summary_json = json.dumps(summary, indent=2)

    prompt = PromptTemplate(
        input_variables=["summary", "income", "expenses"],
        template=ADVISOR_TEMPLATE
    )

    chain = prompt | advisor_llm

    response = chain.invoke({
        "summary": summary_json,
        "income": income_json,
        "expenses": expenses_json
    })

    return response.content.strip()