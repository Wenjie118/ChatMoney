# db.py
import os
from dotenv import load_dotenv
from supabase import create_client, Client
import calendar
from datetime import date

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in your .env file")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def save_expense(amount, category, expense_date, desc=None):
    expense = {
        "amount" : amount,
        "category" : category,
        "description" : desc,
        "date" : expense_date
    }

    response = supabase.table("expenses").insert(expense).execute()
    return response

def get_all_expenses():
    response = supabase.table("expenses").select("*").execute()
    return response.data

def get_expenses_by_daterange(start, end):
    response = supabase.table("expenses").select("*").gte("date", start).lte("date", end).execute()
    return response.data

def save_income(amount, source, income_date, desc=None):
    income = {
        "amount" : amount,
        "source" : source,
        "description": desc,
        "date" : income_date
    }

    response = supabase.table("income").insert(income).execute()
    return response

def get_income(month, year):
    start = date(year,month,1)
    end = date(year,month,calendar.monthrange(year, month)[1])
    response = supabase.table("income").select("*").gte("date", start).lte("date", end).execute()
    return response.data

def get_monthly_summary():
    current = date.today()

    details = {
        "total_income":   0.0,
        "total_expenses": 0.0,
        "net_savings":    0.0,
        "savings_rate":   0.0
    }

    #calculation for total income
    incomes = get_income(current.month,current.year)
    for income in incomes:
        details["total_income"] += income["amount"]

    #calculation for total expenses
    start = date(current.year,current.month,1)
    end = date(current.year,current.month,calendar.monthrange(current.year, current.month)[1])
    expenses = get_expenses_by_daterange(start,end)
    for expense in expenses:
        details["total_expenses"] += expense["amount"]

    #calculation for net savings
    details["net_savings"] = details["total_income"] - details["total_expenses"]

    #calculation for savings rate
    details["savings_rate"] = (details["net_savings"]/details["total_income"])*100 if details["total_income"] > 0 else 0.0

    return details

