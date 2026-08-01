/**
 * API client — the ONE place the frontend knows how to talk to the backend.
 *
 * Components never call fetch() directly; they call these functions. That keeps
 * the base URL, error handling, and JSON parsing in a single spot.
 *
 * Every exported function delegates to the shared `request<T>()` helper below,
 * which centralizes: prefixing the base URL, running the fetch, checking the
 * response via `handle()`, and logging + re-throwing on failure. Each function
 * only has to describe its own path + method + body.
 */

import type {
  IBalance,
  ITransaction,
  IAdviceRequest,
  IAdviceResponse,
  ISpendingAnalysisResponse,
  ISaveMultipleResult,
  IMonthlySummary,
  IPeriod,
  IWallet,
  ILedgerEntry,
  IUnassigned,
  ITransfer,
} from "./types";

// Base URL of the FastAPI backend, from frontend/.env.local.
// The `!` asserts it's defined; if it's missing you'll get a clear runtime error.
const API_URL = process.env.NEXT_PUBLIC_API_URL!;

/**
 * Small shared helper: throws a useful Error when the response isn't 2xx.
 * FastAPI puts error messages in a `detail` field, so we surface that.
 */
async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* response had no JSON body — keep statusText */
    }
    throw new Error(`API ${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

/**
 * The single request pipeline shared by every endpoint function:
 *   build URL -> fetch -> handle() (status check + JSON parse) -> type the result,
 * logging and re-throwing on any failure so callers can show a message.
 *
 * `path` is appended to API_URL; `init` is a normal fetch RequestInit (method,
 * headers, body, cache). Adding a cross-cutting concern (a header, auth, tracing)
 * now means editing this one function instead of ~11 near-identical wrappers.
 */
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  try {
    const res = await fetch(`${API_URL}${path}`, init);
    return await handle<T>(res);
  } catch (err) {
    console.error(`API ${init.method ?? "GET"} ${path} failed:`, err);
    throw err;
  }
}

/** Build a JSON-body request init (Content-Type + serialized body). */
function jsonBody(method: string, data: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  };
}

/**
 * GET /balance — fetch the current balance snapshot.
 * @throws Error if the network call fails or the API returns a non-2xx status.
 */
export async function getBalance(): Promise<IBalance> {
  return request<IBalance>("/balance", { method: "GET", cache: "no-store" });
}

/**
 * POST /transactions/parse — send free text; backend parses + saves it and returns
 * the saved transactions.
 * @throws Error on network failure or a non-2xx status (e.g. 422 unparseable text).
 */
export async function parseTransaction(
  text: string,
  walletId?: number | null,
): Promise<ITransaction[]> {
  // body must match ParseTextRequest { text, wallet_id? }. wallet_id tags every
  // transaction parsed from this message (the chat UI requires picking one).
  return request<ITransaction[]>(
    "/transactions/parse",
    jsonBody("POST", { text, wallet_id: walletId ?? null }),
  );
}

/**
 * POST /transactions/parse-pdf — upload a PDF, get back consolidated rows to review.
 */
export async function parsePDF(file: File): Promise<ITransaction[]> {
  // FormData = the browser's multipart/form-data builder (how file uploads
  // are sent). "file" must match the FastAPI param name: File(...) on `file`.
  const fd = new FormData();
  fd.append("file", file);

  // NOTE: do NOT set a Content-Type header here. The browser sets it to
  // multipart/form-data AND adds the required boundary string automatically;
  // setting it by hand would omit the boundary and break the upload.
  return request<ITransaction[]>("/transactions/parse-pdf", { method: "POST", body: fd });
}

/**
 * POST /transactions/save-multiple — bulk-save the reviewed rows.
 * Sends the array as the JSON body (the backend validates it as list[TransactionRequest]).
 */
export async function saveMultiple(rows: ITransaction[]): Promise<ISaveMultipleResult> {
  // the whole array IS the body
  return request<ISaveMultipleResult>("/transactions/save-multiple", jsonBody("POST", rows));
}

/**
 * GET /transactions/summary?month=&year= — the 4 dashboard numbers for one month.
 */
export async function getSummary(month: number, year: number): Promise<IMonthlySummary> {
  return request<IMonthlySummary>(
    `/transactions/summary?month=${month}&year=${year}`,
    { method: "GET", cache: "no-store" },
  );
}

/**
 * GET /transactions/recent?month=&year= — that month's transactions (income +
 * expenses), newest first. Used for the recent table and to derive the charts.
 */
export async function getRecent(month: number, year: number): Promise<ITransaction[]> {
  return request<ITransaction[]>(
    `/transactions/recent?month=${month}&year=${year}`,
    { method: "GET", cache: "no-store" },
  );
}

// NOTE: there is no setBalance(). The balance is derived from wallets — change it
// with setWalletBalance() (PATCH /wallets/{id}/balance) instead.

/**
 * POST /advisor/advice — get AI advice for a month.
 * Sends {month, year} (either may be omitted = current month), returns the advice.
 */
export async function getAdvice(req: IAdviceRequest): Promise<IAdviceResponse> {
  // body must match AdviceRequest { month?, year? }
  return request<IAdviceResponse>("/advisor/advice", jsonBody("POST", req));
}

/**
 * POST /advisor/spending — get the mid-month, provisional, expense-only spending
 * analysis for a month. Same request shape as getAdvice ({month?, year?}); the
 * response has an `analysis` string instead of `advice`.
 */
export async function getSpendingAnalysis(
  req: IAdviceRequest,
): Promise<ISpendingAnalysisResponse> {
  // body must match AdviceRequest { month?, year? }
  return request<ISpendingAnalysisResponse>("/advisor/spending", jsonBody("POST", req));
}

/**
 * GET /advisor/periods — the months that actually have logged data, newest-first.
 * Used to populate the Advisor's month dropdown.
 */
export async function getPeriods(): Promise<IPeriod[]> {
  return request<IPeriod[]>("/advisor/periods", { method: "GET", cache: "no-store" });
}

// ===========================================================================
// Wallets — virtual sub-wallets with computed, ledger-based balances.
// ===========================================================================

/** GET /wallets — active wallets with their computed balances. */
export async function getWallets(): Promise<IWallet[]> {
  return request<IWallet[]>("/wallets", { method: "GET", cache: "no-store" });
}

/** POST /wallets — create a wallet (starts at balance 0). */
export async function createWallet(name: string): Promise<IWallet> {
  return request<IWallet>("/wallets", jsonBody("POST", { name }));
}

/** PATCH /wallets/{id} — rename; returns it with its current balance. */
export async function renameWallet(id: number, name: string): Promise<IWallet> {
  return request<IWallet>(`/wallets/${id}`, jsonBody("PATCH", { name }));
}

/** DELETE /wallets/{id} — soft-delete (money folds into Unassigned). */
export async function deleteWallet(id: number): Promise<{ status: string; id: number }> {
  return request(`/wallets/${id}`, { method: "DELETE" });
}

/** GET /wallets/{id}/ledger — the wallet's movement history. */
export async function getWalletLedger(id: number): Promise<ILedgerEntry[]> {
  return request<ILedgerEntry[]>(`/wallets/${id}/ledger`, { method: "GET", cache: "no-store" });
}

/** PATCH /wallets/{id}/balance — correct a wallet to an exact amount (records an
 *  adjustment for the difference). Changes the wallet AND the overall balance. */
export async function setWalletBalance(id: number, amount: number): Promise<IWallet> {
  return request<IWallet>(`/wallets/${id}/balance`, jsonBody("PATCH", { amount }));
}

/** GET /wallets/unassigned — total (incl. baseline) + resolvable rows. */
export async function getUnassigned(): Promise<IUnassigned> {
  return request<IUnassigned>("/wallets/unassigned", { method: "GET", cache: "no-store" });
}

/** POST /transfers — move money between two wallets (both required). */
export async function createTransfer(
  fromWallet: number,
  toWallet: number,
  amount: number,
  description?: string | null,
  date?: string | null,
): Promise<ITransfer> {
  return request<ITransfer>(
    "/transfers",
    jsonBody("POST", {
      from_wallet: fromWallet,
      to_wallet: toWallet,
      amount,
      description: description ?? null,
      date: date ?? null,
    }),
  );
}

/** PATCH /transactions/{id}/wallet?type= — resolve an Unassigned income/expense. */
export async function resolveTransactionWallet(
  id: number,
  type: "expense" | "income",
  walletId: number | null,
): Promise<{ status: string }> {
  return request(
    `/transactions/${id}/wallet?type=${type}`,
    jsonBody("PATCH", { wallet_id: walletId }),
  );
}
