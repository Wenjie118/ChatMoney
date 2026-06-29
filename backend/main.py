"""
ChatMoney — FastAPI application entry point.

This is the single process that the React/Next.js frontend talks to over HTTP.
It wires together three things:

    1. CORS         — so the browser (localhost:3000) is allowed to call this API.
    2. Routers      — modular groups of endpoints living in `routes/`.
    3. Your code    — the existing `db.py` and `llm.py` at the project ROOT are
                      reused unchanged; routes import and call them.

Request flow:
    React  --HTTP-->  FastAPI route  --function call-->  db.py / llm.py  -->  Supabase

────────────────────────────────────────────────────────────────────────────
HOW TO RUN (backend)
    cd backend
    pip install -r requirements.txt
    uvicorn main:app --reload          # serves on http://localhost:8000
    # interactive API docs:  http://localhost:8000/docs

HOW TO RUN (frontend)  — see frontend/README or package.json
    cd frontend
    npm install
    npm run dev                        # serves on http://localhost:3000
────────────────────────────────────────────────────────────────────────────
"""

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Make the existing root-level modules importable.
#
# db.py and llm.py live ONE LEVEL UP from this `backend/` folder. When you run
# `uvicorn main:app` from inside `backend/`, Python's working dir is `backend/`,
# so `import db` would fail. Adding the project root to sys.path fixes that
# WITHOUT modifying db.py / llm.py.
#
# NOTE: this must run BEFORE we import any route module, because the routes do
# `import db` / `import llm` at their own import time.
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI

from utils.cors import configure_cors
from routes import balance, transactions, advisor, plans

# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="ChatMoney API",
    description="Backend for the ChatMoney personal finance app.",
    version="1.0.0",
)

# CORS: allow the frontend origin to call this API (see utils/cors.py).
configure_cors(app)

# TODO (middleware): add any cross-cutting middleware here, e.g.
#   - request logging / timing
#   - global exception handler that turns DatabaseConnectionError into a clean
#     503 JSON response instead of a 500 stack trace
#   - rate limiting
# Pattern:  app.add_middleware(SomeMiddleware, ...)

# ---------------------------------------------------------------------------
# Routers — each file in routes/ exposes an `APIRouter` named `router`.
# `prefix` is prepended to every path in that router; `tags` groups them in /docs.
# ---------------------------------------------------------------------------
app.include_router(balance.router, prefix="/balance", tags=["balance"])
app.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
app.include_router(advisor.router, prefix="/advisor", tags=["advisor"])
app.include_router(plans.router, prefix="/plans", tags=["plans"])


@app.get("/health")
def health_check() -> dict:
    """Liveness probe.

    Returns a tiny JSON payload so the frontend (or a deploy platform) can
    confirm the API process is up. Keep this dependency-free and fast.
    """
    return {"status": "ok"}
