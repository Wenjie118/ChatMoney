"""
CORS (Cross-Origin Resource Sharing) configuration.

WHY THIS EXISTS
    Browsers block JavaScript on origin A (the Next.js dev server,
    http://localhost:3000) from calling an API on origin B (this FastAPI server,
    http://localhost:8000) unless the API explicitly says "that origin is allowed".
    This module adds the middleware that sends those permission headers.

This file is written out completely because it's configuration, not app logic.
You mainly need to keep `ALLOWED_ORIGINS` in sync with where your frontend runs.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Origins allowed to call this API. The frontend dev server is localhost:3000.
# TODO (production): add your deployed frontend URL here, e.g.
#   "https://chatmoney.vercel.app"
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


def configure_cors(app: FastAPI) -> None:
    """Attach CORS middleware to the FastAPI app.

    Called once from main.py. `allow_credentials=True` lets the browser send
    cookies/auth headers; if you ever switch to `allow_origins=["*"]` you must
    set `allow_credentials=False` (the spec forbids wildcard + credentials).
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],   # GET, POST, PUT, DELETE, OPTIONS, ...
        allow_headers=["*"],   # Content-Type, Authorization, ...
    )
