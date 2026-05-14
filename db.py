import os
from dotenv import load_dotenv
from supabase import create_client, Client
import calendar
from datetime import date, datetime

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in your .env file")

def get_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    return create_client(url, key)

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

def get_all_expenses():
    client = get_supabase()
    response = client.table("expenses").select("*").execute()
    return response.data

def get_expenses_by_daterange(start, end):
    client = get_supabase()
    response = client.table("expenses").select("*").gte("date", start).lte("date", end).execute()
    return response.data

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

def get_income(month, year):
    client = get_supabase()
    start = date(year, month, 1).isoformat()
    end = date(year, month, calendar.monthrange(year, month)[1]).isoformat()
    response = client.table("income").select("*").gte("date", start).lte("date", end).execute()
    return response.data

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

    start = date(current.year, current.month, 1).isoformat()
    end = date(current.year, current.month, calendar.monthrange(current.year, current.month)[1]).isoformat()
    expenses = get_expenses_by_daterange(start, end)
    for expense in expenses:
        details["total_expenses"] += expense["amount"]

    details["net_savings"] = details["total_income"] - details["total_expenses"]
    details["savings_rate"] = (details["net_savings"] / details["total_income"]) * 100 if details["total_income"] > 0 else 0.0

    balance = get_balance()
    details["current_balance"] = balance["current_balance"]

    return details

def set_balance(amount):
    client = get_supabase()
    balance = {
        "manual_balance": amount,
        "last_updated": date.today().isoformat(),
    }
    response = client.table("balance").insert(balance).execute()
    return response

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