# ChatMoney — Project Context

> A copy-paste-ready overview of this project's purpose, tech stack, and structure.
> Hand this to another chat/developer to get them up to speed quickly.

## What it is
ChatMoney is an **AI-powered personal finance assistant** aimed at Malaysian users (currency is RM / Ringgit). You log income and expenses in plain English ("spent RM50 on groceries"), or upload a bank-statement PDF, and an LLM parses them into structured transactions. It tracks your balance, shows a monthly dashboard with charts, and generates personalized AI financial advice.

It was **originally a Streamlit app** and was migrated to a **React (Next.js) frontend + FastAPI backend** architecture. The original `db.py` and `llm.py` were kept at the project root **unchanged**, and the new backend imports and reuses them.

## Tech Stack

**Backend (Python)**
- **FastAPI** — HTTP API (entry point `backend/main.py`, served by **uvicorn**)
- **Pydantic** — request/response models (`backend/schemas/models.py`)
- **Supabase** (`supabase-py`) — Postgres database via `db.py`
- **LangChain** + **langchain-google-genai** — LLM orchestration in `llm.py`
- **Google Gemini** (`gemini-2.5-flash`) — transaction parsing, PDF parsing, advice generation
- **python-dotenv** — env config; **python-multipart** for PDF uploads

**Frontend (TypeScript)**
- **Next.js 14** (App Router) + **React 18**
- **Tailwind CSS** (+ `@tailwindcss/typography` for markdown rendering)
- **Recharts** — bar + pie charts on the dashboard
- **react-markdown** — renders the AI advice (Gemini returns markdown)
- `@tanstack/react-table` is a dependency but the preview table is hand-rolled

**Infra / dev**
- Database: **Supabase** — `expenses`, `income`, `balance` (anchor only), `wallets`, `wallet_transfers`
- LLM: **Google AI Studio** API key
- `ChatMoney.bat` — Windows launcher that boots backend (uvicorn :8000) + frontend (next dev :3000) and opens the browser
- Secrets in `.env` (root, for `db.py`/`llm.py`) and `frontend/.env.local` (`NEXT_PUBLIC_API_URL`)

## Request flow
```
React component → lib/api.ts (fetch) → FastAPI route → db.py / llm.py → Supabase / Gemini
```

## Project Structure

```
ChatMoney/
├── db.py                      # Supabase data layer (ROOT, reused unchanged)
├── llm.py                     # Gemini/LangChain layer (ROOT, reused unchanged)
├── .env                       # SUPABASE_URL, SUPABASE_KEY, GOOGLE_API_KEY
├── ChatMoney.bat              # Windows one-click launcher (backend + frontend)
│
├── backend/                   # FastAPI app
│   ├── main.py                # app instance, CORS, router wiring, /health
│   │                          #   adds project root to sys.path so it can `import db, llm`
│   ├── requirements.txt
│   ├── routes/
│   │   ├── balance.py         # GET /balance (read-only — derived from wallets)
│   │   ├── transactions.py    # /transactions/{parse, parse-pdf, recent, summary, save-multiple}
│   │   └── advisor.py         # POST /advisor/advice, GET /advisor/periods
│   ├── schemas/models.py      # Pydantic request/response models (mirror frontend types)
│   └── utils/
│       ├── cors.py            # CORS config (allows localhost:3000)
│       └── transactions.py    # consolidate_transactions() — merges dup PDF rows
│
└── frontend/                  # Next.js (App Router)
    ├── app/
    │   ├── layout.tsx         # root layout (global chrome)
    │   ├── page.tsx           # "/" — app shell: sidebar + topbar, in-memory tab switching
    │   │                      #        (Chat / Dashboard / Advisor), wrapped in BusyProvider
    │   ├── chat/page.tsx      # "/chat" deep-link route
    │   ├── dashboard/page.tsx # "/dashboard" deep-link route
    │   └── globals.css        # Tailwind + brand-gradient utility
    ├── components/
    │   ├── ChatInterface.tsx       # text input + PDF upload, chat-bubble confirmations
    │   ├── TransactionPreview.tsx  # editable review table before bulk-saving PDF rows
    │   ├── Dashboard.tsx           # month picker → 4 metric cards + bar/pie charts + table
    │   ├── BalanceCard.tsx         # shows current balance (read-only; edit via Wallets)
    │   └── Advisor.tsx             # month dropdown → "Get advice" → renders markdown
    ├── lib/
    │   ├── api.ts             # the ONE place fetch() is called; one fn per endpoint
    │   ├── types.ts           # TS interfaces (I-prefixed) mirroring Pydantic models
    │   ├── constants.ts       # EXPENSE_CATEGORIES / INCOME_SOURCES (must match llm.py prompts)
    │   └── busy.tsx           # React Context global "busy" full-screen overlay
    ├── package.json
    ├── tailwind.config.ts / postcss.config.mjs / next.config.mjs / tsconfig.json
```

## Key code conventions & design decisions

- **Single transaction shape everywhere.** The LLM emits `category` (expenses) or `source` (income); these are flattened into one `category_or_source` field used across backend `TransactionResponse`, frontend `ITransaction`, and the DB-save layer. Pydantic models (`backend/schemas/models.py`) and TS types (`frontend/lib/types.ts`) are intentionally kept mirrored.
- **db.py / llm.py untouched.** New logic that didn't fit there (like PDF row consolidation, ported from the old Streamlit `app.py`) lives in `backend/utils/`.
- **Thin routes.** Each route: validate via Pydantic → call db/llm function → map domain errors to HTTP → return typed response. Pattern errors: `DatabaseConnectionError` → **503**, LLM `ValueError` (unparseable / AI busy) → **422**.
- **Centralized API client.** Components never call `fetch` directly — only `lib/api.ts` does. It reads `NEXT_PUBLIC_API_URL` and surfaces FastAPI's `detail` field in thrown errors.
- **Frontend data pattern.** `useState` (data/loading/error) + `useEffect` to fetch (empty `[]` = on mount, e.g. BalanceCard; `[month, year]` = refetch on change, e.g. Dashboard, with a `cancelled` guard against race conditions). Expensive AI calls (Advisor) fire on button click, not on mount.
- **Immutable state updates** in `TransactionPreview` (map/filter to new arrays, never mutate in place).
- **Categories/sources are duplicated** in `lib/constants.ts` and the `llm.py` prompt templates — must be changed in both places.

## LLM details (`llm.py`)
- Two Gemini instances: `parser_llm` (temp 0, for parsing) and `advisor_llm` (temp 0.7, for advice).
- Three prompt templates: `PARSER_TEMPLATE` (free text → JSON array), `PDF_PARSER_TEMPLATE` (PDF bytes sent base64 as a file message → JSON array), `ADVISOR_TEMPLATE` (financial data → markdown advice).
- Robustness: `_invoke_with_retry` (exponential backoff on 429/5xx), `_friendly_api_error` (user-facing messages), `_extract_json_array` (strips code fences, falls back to slicing outermost `[...]`).

## Database (`db.py`)
- Tables: `expenses` (amount, category, description, date, wallet_id), `income` (amount, source, description, date, wallet_id), `balance` (manual_balance, last_updated, created_at), `wallets`, `wallet_transfers`, `wallet_adjustments`.
- **Three kinds of movement, in separate tables on purpose.** `income`/`expenses` are *budget events* and are the only rows the monthly summary, category charts and AI advisor read. `wallet_transfers` move money between wallets (net zero). `wallet_adjustments` are corrections to what a wallet holds ("it should actually be RM 500") — real money that moves the wallet and the balance, but **never** counted as earning or spending. Keeping them out of `income`/`expenses` is the entire mechanism; there is no filtering flag to remember.
- **Balance is derived from wallets**, never stored: `current_balance = Σ(active wallet balances) + unassigned`. Editing a wallet (`PATCH /wallets/{id}/balance`) records an adjustment for the delta, so the total moves by exactly that much. There is **no `PUT /balance`** — writing a balance would drop a new anchor row dated now and reset every wallet to zero.
- The `balance` table is only the **wallet-era anchor**: its latest `created_at` is the horizon (movements strictly after it count; older pre-wallet rows are excluded). Its `manual_balance` column is no longer read — see `sql/05_retire_manual_balance.sql`. Never delete the anchor row.
- `unassigned` = money inside the horizon not tagged to an active wallet (NULL or soft-deleted wallet). It keeps untagged imports from being silently dropped; once every row is assigned, `current_balance` equals the wallet total exactly.
- Connection hardening: validates `SUPABASE_URL`, DNS-resolves the host, wraps calls in `with_db_connection` to raise a friendly `DatabaseConnectionError`.

## How to run
```bash
# Backend
cd backend && pip install -r requirements.txt
uvicorn main:app --reload          # http://localhost:8000  (docs at /docs)

# Frontend
cd frontend && npm install && npm run dev   # http://localhost:3000
```
Or run `ChatMoney.bat` on Windows to launch both. Requires `.env` (Supabase + Google keys) and `frontend/.env.local` (`NEXT_PUBLIC_API_URL=http://localhost:8000`).
