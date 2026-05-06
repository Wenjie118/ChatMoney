import os
from datetime import date
import json

from dotenv import load_dotenv
load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

from db import save_expense

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

# --- Parser Prompt Template ---
PARSER_TEMPLATE = """
You are a financial expense parser for a Malaysian personal finance app.

Extract ALL expenses from the user's message and return ONLY a JSON array.
Each expense object must have exactly these fields:
- amount: a number (no currency symbols)
- category: one of [Food, Transport, Shopping, Entertainment, Health, Bills, Other]
- description: a short description string, or null if unclear
- date: in YYYY-MM-DD format

Rules:
- Always return a JSON array, even if there is only one expense
- If no date is mentioned, use today's date: {today}
- Never return anything outside the JSON array
- No markdown, no explanation, no code blocks

User message: {user_input}
"""

# --- Parser Function ---
def parse_expense(user_input: str) -> list[dict]:
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
    expenses = json.loads(raw)

    for expense in expenses:
        save_expense(
            amount=expense["amount"],
            category=expense["category"],
            date=expense["date"],
            desc=expense.get("description")
        )

    return expenses

# --- Advisor Prompt Template ---
ADVISOR_TEMPLATE = """
You are a friendly and practical personal finance advisor for a Malaysian user.

Here is the user's full spending history in JSON format:
{expenses}

Based on this data, provide:
1. A short summary of their spending patterns
2. Which category they are overspending in
3. Two or three concrete actionable tips to improve their finances

Rules:
- Be specific, reference actual amounts and categories from the data
- Use Ringgit (RM) for all amounts
- Keep your response conversational and encouraging, not robotic
- If there is no data, tell the user to add some expenses first
"""

# --- Advisor Function ---
def get_advice(expenses: list[dict]) -> str:
    expenses_json = json.dumps(expenses, indent=2)

    prompt = PromptTemplate(
        input_variables=["expenses"],
        template=ADVISOR_TEMPLATE
    )

    chain = prompt | advisor_llm

    response = chain.invoke({
        "expenses": expenses_json
    })

    return response.content.strip()