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

import logging
import os
import sys
import time
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

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from db import DatabaseConnectionError
from utils.cors import configure_cors
from routes import balance, transactions, advisor, wallets, transfers

# ---------------------------------------------------------------------------
# Logging
#
# Configure the root logger once, at the app entry point, so our own modules
# (this file, llm.py's logger, etc.) emit to stdout at a level you can tune via
# the LOG_LEVEL env var (default INFO). Uvicorn keeps its own access log; this
# gives *our* code a consistent, structured channel instead of stray print()s.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("chatmoney.request")

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


# ---------------------------------------------------------------------------
# Request logging / timing middleware
#
# Logs method, path, status code, and elapsed ms for every request. LLM and
# Supabase calls can be slow, so this gives basic visibility into latency and
# failure rates. Overhead is a single perf_counter() pair per request.
# ---------------------------------------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "%s %s -> unhandled error (%.1f ms)",
            request.method, request.url.path, elapsed_ms,
        )
        raise
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s -> %d (%.1f ms)",
        request.method, request.url.path, response.status_code, elapsed_ms,
    )
    return response


# ---------------------------------------------------------------------------
# Global exception handlers
#
# Map domain errors to HTTP responses in ONE place, so routes don't each repeat
# the same try/except. Both return the same {"detail": ...} envelope FastAPI's
# HTTPException produces, so the frontend's error handling is unchanged.
#
#   DatabaseConnectionError -> 503  (Supabase unreachable — a dependency is down)
#   ValueError              -> 422  (unparseable input / domain rule violation)
#
# NOTE: a route that needs a *different* mapping (e.g. the advisor treats a busy
# LLM's ValueError as a 503, not a 422) still catches it locally and raises its
# own HTTPException — that wins because the ValueError never escapes the route.
# ---------------------------------------------------------------------------
@app.exception_handler(DatabaseConnectionError)
async def handle_db_connection_error(request: Request, exc: DatabaseConnectionError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(ValueError)
async def handle_value_error(request: Request, exc: ValueError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


# ---------------------------------------------------------------------------
# Routers — each file in routes/ exposes an `APIRouter` named `router`.
# `prefix` is prepended to every path in that router; `tags` groups them in /docs.
# ---------------------------------------------------------------------------
app.include_router(balance.router, prefix="/balance", tags=["balance"])
app.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
app.include_router(advisor.router, prefix="/advisor", tags=["advisor"])
app.include_router(wallets.router, prefix="/wallets", tags=["wallets"])
app.include_router(transfers.router, prefix="/transfers", tags=["transfers"])


@app.get("/health")
def health_check() -> dict:
    """Liveness probe.

    Returns a tiny JSON payload so the frontend (or a deploy platform) can
    confirm the API process is up. Keep this dependency-free and fast.
    """
    return {"status": "ok"}
