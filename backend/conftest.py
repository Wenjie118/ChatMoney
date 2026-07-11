"""
Pytest bootstrap for the backend test suite.

Mirrors the sys.path setup in main.py so tests can `import db, llm` (root-level
modules) and `from utils... / routes... import ...` (backend package modules).

db.py and llm.py refuse to import without their env vars, so we set DUMMY values
here. The tests mock every Supabase/Gemini call, so no real secrets or network
access are ever used — the dummies just get the modules past their import checks.
"""

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent

# Insert PROJECT_ROOT first, then BACKEND_DIR, so BACKEND_DIR ends up at index 0
# (both are on the path either way).
for path in (PROJECT_ROOT, BACKEND_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("GOOGLE_API_KEY", "test-key")
os.environ.setdefault("LOG_LEVEL", "WARNING")
