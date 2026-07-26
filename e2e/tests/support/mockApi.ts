import type { Page, Route } from "@playwright/test";

/**
 * Backend mock for the ChatMoney E2E tests.
 *
 * ChatMoney's real backend (FastAPI + Supabase + Google Gemini) can't run in CI
 * without secrets, and the LLM makes real responses non-deterministic. Instead of
 * booting it, we intercept every request the frontend makes to the API and answer
 * with fixed JSON that matches the backend's response shapes.
 *
 * The frontend calls the backend only through `frontend/lib/api.ts`, using
 * `NEXT_PUBLIC_API_URL` (set to http://localhost:8000 in playwright.config.ts).
 * `page.route()` catches those requests so no network call ever leaves the box.
 *
 * Response shapes mirror:
 *   - frontend/lib/types.ts        (the TS interfaces the UI expects)
 *   - backend/schemas/models.py    (the Pydantic models the API returns)
 *
 * Usage in a spec:
 *   test.beforeEach(async ({ page }) => {
 *     await mockBackend(page);            // sensible defaults
 *   });
 *
 *   // Override a single endpoint for one test:
 *   await mockBackend(page, {
 *     "GET /balance": { status: 503, json: { detail: "DB down" } },
 *   });
 */

// ---------------------------------------------------------------------------
// Default fixture data (edit freely — these are just realistic examples).
// ---------------------------------------------------------------------------

const DEFAULT_BALANCE = {
  current_balance: 5000.0,
  manual_balance: 5000.0,
  last_updated: "2026-07-01",
};

const DEFAULT_TRANSACTIONS = [
  {
    type: "expense",
    amount: 50.0,
    category_or_source: "Groceries",
    description: "Weekly groceries",
    date: "2026-07-02",
  },
  {
    type: "income",
    amount: 5000.0,
    category_or_source: "Salary",
    description: "Monthly salary",
    date: "2026-07-01",
  },
];

const DEFAULT_SUMMARY = {
  total_income: 5000.0,
  total_expenses: 50.0,
  net_savings: 4950.0,
  savings_rate: 99.0,
};

const DEFAULT_PERIODS = [{ year: 2026, month: 7 }];

const DEFAULT_ADVICE = {
  advice:
    "## Your Financial Snapshot\n\nYou saved **99%** of your income this month. " +
    "Keep building that emergency fund!",
};

const DEFAULT_SAVE_RESULT = { total: 2, saved: 2, failed: 0 };

// At least one wallet so the Chat tab's required wallet selector is populated and
// Send is enabled (it's disabled with zero wallets).
const DEFAULT_WALLETS = [
  { id: 1, name: "Daily", balance: 1000.0 },
  { id: 2, name: "Savings", balance: 4000.0 },
];

const DEFAULT_UNASSIGNED = { total: 0, rows: [] };

const DEFAULT_TRANSFER = {
  id: 1,
  from_wallet: 1,
  to_wallet: 2,
  amount: 100.0,
  description: null,
  date: "2026-07-20",
};

// ---------------------------------------------------------------------------
// Override plumbing.
// ---------------------------------------------------------------------------

/** A per-endpoint override: return custom JSON and/or a non-200 status. */
export interface MockOverride {
  status?: number;
  json?: unknown;
}

/** Keys are "<METHOD> <path>", e.g. "GET /balance" or "POST /transactions/parse". */
export type MockOverrides = Record<string, MockOverride>;

/**
 * The default response for each endpoint the UI calls. `parse` echoes back a
 * transaction derived from nothing (a fixed example), which is enough for the
 * confirmation-bubble assertions.
 */
function defaultFor(method: string, path: string): MockOverride | null {
  if (method === "GET" && path.startsWith("/balance")) return { json: DEFAULT_BALANCE };
  if (method === "PUT" && path.startsWith("/balance")) {
    // Echo the requested amount back as the new balance (handled specially below).
    return { json: DEFAULT_BALANCE };
  }
  if (method === "POST" && path.startsWith("/transactions/parse-pdf"))
    return { json: DEFAULT_TRANSACTIONS };
  if (method === "POST" && path.startsWith("/transactions/parse"))
    return { json: [DEFAULT_TRANSACTIONS[0]] };
  if (method === "POST" && path.startsWith("/transactions/save-multiple"))
    return { json: DEFAULT_SAVE_RESULT };
  if (method === "GET" && path.startsWith("/transactions/summary"))
    return { json: DEFAULT_SUMMARY };
  if (method === "GET" && path.startsWith("/transactions/recent"))
    return { json: DEFAULT_TRANSACTIONS };
  if (method === "POST" && path.startsWith("/advisor/advice")) return { json: DEFAULT_ADVICE };
  if (method === "GET" && path.startsWith("/advisor/periods")) return { json: DEFAULT_PERIODS };

  // Wallets — specific paths BEFORE the bare "/wallets" list, so subpaths match.
  if (method === "GET" && path.startsWith("/wallets/unassigned")) return { json: DEFAULT_UNASSIGNED };
  if (method === "GET" && /^\/wallets\/\d+\/ledger$/.test(path)) return { json: [] };
  if (method === "GET" && path.startsWith("/wallets")) return { json: DEFAULT_WALLETS };
  if (method === "POST" && path.startsWith("/wallets")) return { json: { id: 3, name: "New", balance: 0 } };
  if (method === "PATCH" && /^\/wallets\/\d+$/.test(path)) return { json: { id: 1, name: "Renamed", balance: 0 } };
  if (method === "DELETE" && /^\/wallets\/\d+$/.test(path)) return { json: { status: "deactivated", id: 1 } };
  if (method === "POST" && path.startsWith("/transfers")) return { json: DEFAULT_TRANSFER };
  if (method === "PATCH" && /^\/transactions\/\d+\/wallet$/.test(path)) return { json: { status: "updated" } };
  return null;
}

/** Look up an override by "<METHOD> <path-prefix>", matching on path prefix. */
function findOverride(
  overrides: MockOverrides,
  method: string,
  path: string,
): MockOverride | null {
  for (const [key, value] of Object.entries(overrides)) {
    const [oMethod, oPath] = key.split(" ");
    if (oMethod === method && path.startsWith(oPath)) return value;
  }
  return null;
}

// ---------------------------------------------------------------------------
// Public helper.
// ---------------------------------------------------------------------------

/**
 * Intercept all backend (`**\/localhost:8000/**`) requests for this page and
 * answer them with mock JSON. Pass `overrides` to customize specific endpoints.
 */
export async function mockBackend(page: Page, overrides: MockOverrides = {}): Promise<void> {
  await page.route("**://localhost:8000/**", async (route: Route) => {
    const request = route.request();
    const method = request.method();
    // Strip the origin + query string down to just the path for matching.
    const path = new URL(request.url()).pathname;

    const override = findOverride(overrides, method, path) ?? defaultFor(method, path);

    if (!override) {
      // Unmocked endpoint — fail loudly so tests don't silently pass on a 404.
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: `No mock for ${method} ${path}` }),
      });
      return;
    }

    let json = override.json;

    // Special case: PUT /balance echoes the submitted amount as the new balance
    // so the "update balance" flow shows the value the user just typed.
    if (method === "PUT" && path.startsWith("/balance") && override.status === undefined) {
      try {
        const body = request.postDataJSON() as { amount?: number };
        if (typeof body?.amount === "number") {
          json = { ...DEFAULT_BALANCE, current_balance: body.amount, manual_balance: body.amount };
        }
      } catch {
        /* no/invalid body — fall back to the default balance */
      }
    }

    await route.fulfill({
      status: override.status ?? 200,
      contentType: "application/json",
      body: JSON.stringify(json ?? {}),
    });
  });
}
