# db.py
import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in your .env file")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def save_expense(amount, category, date, desc=None):
    expense = {
        "amount" : amount,
        "category" : category,
        "description" : desc,
        "date" : date
    }

    response = supabase.table("expenses").insert(expense).execute()
    return response

def get_all_expenses():
    response = supabase.table("expenses").select("*").execute()
    return response.data

def get_expenses_by_daterange(start, end):
    response = supabase.table("expenses").select("*").gte("date", start).lte("date", end).execute()
    return response.data