/**
 * API client — the ONE place the frontend knows how to talk to the backend.
 *
 * Components never call fetch() directly; they call these functions. That keeps
 * the base URL, error handling, and JSON parsing in a single spot.
 *
 * Study `getBalance()` below — it's the complete reference pattern:
 *   build URL -> fetch -> check res.ok -> parse JSON -> type the result.
 * The other functions are TODO stubs; copy the pattern into each.
 */

import type {
  IBalance,
  ITransaction,
  IAdviceRequest,
  IAdviceResponse,
  ISaveMultipleResult,
  IMonthlySummary,
  IPeriod,
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

// ===========================================================================
// COMPLETE EXAMPLE — study this, then mirror it for the stubs below.
// ===========================================================================
/**
 * GET /balance — fetch the current balance snapshot.
 * @throws Error if the network call fails or the API returns a non-2xx status.
 */
export async function getBalance(): Promise<IBalance> {
  try {
    const res = await fetch(`${API_URL}/balance`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      cache: "no-store", // always fetch fresh balance, don't use Next's cache
    });
    return await handle<IBalance>(res);
  } catch (err) {
    // Re-throw so the calling component can show a message. Log for debugging.
    console.error("getBalance failed:", err);
    throw err;
  }
}

// ===========================================================================
// TODO STUBS — implement following the getBalance pattern above.
// ===========================================================================

/**
 * POST /transactions/parse — send free text; backend parses + saves it and returns
 * the saved transactions. Same shape as getBalance(), but a POST with a JSON body.
 * @throws Error on network failure or a non-2xx status (e.g. 422 unparseable text).
 */
export async function parseTransaction(text: string): Promise<ITransaction[]> {
  try {
    const res = await fetch(`${API_URL}/transactions/parse`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }), // must match ParseTextRequest { text }
    });
    return await handle<ITransaction[]>(res);
  } catch (err) {
    console.error("parseTransaction failed:", err);
    throw err;
  }
}

/**
 * POST /transactions/parse-pdf — upload a PDF, get back consolidated rows to review.
 * TODO:
 *   - build FormData: const fd = new FormData(); fd.append("file", file);
 *   - fetch with method "POST" and body: fd  (do NOT set Content-Type — the browser
 *     sets the multipart boundary automatically)
 *   - return await handle<ITransaction[]>(res)
 */
export async function parsePDF(file: File): Promise<ITransaction[]> {
  try {
    // FormData = the browser's multipart/form-data builder (how file uploads
    // are sent). "file" must match the FastAPI param name: File(...) on `file`.
    const fd = new FormData();
    fd.append("file", file);

    const res = await fetch(`${API_URL}/transactions/parse-pdf`, {
      method: "POST",
      body: fd,
      // NOTE: do NOT set a Content-Type header here. The browser sets it to
      // multipart/form-data AND adds the required boundary string automatically;
      // setting it by hand would omit the boundary and break the upload.
    });
    return await handle<ITransaction[]>(res);
  } catch (err) {
    console.error("parsePDF failed:", err);
    throw err;
  }
}

/**
 * POST /transactions/save-multiple — bulk-save the reviewed rows.
 * Sends the array as the JSON body (the backend validates it as list[TransactionRequest]).
 */
export async function saveMultiple(rows: ITransaction[]): Promise<ISaveMultipleResult> {
  try {
    const res = await fetch(`${API_URL}/transactions/save-multiple`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(rows), // the whole array IS the body
    });
    return await handle<ISaveMultipleResult>(res);
  } catch (err) {
    console.error("saveMultiple failed:", err);
    throw err;
  }
}

/**
 * GET /transactions/summary?month=&year= — the 4 dashboard numbers for one month.
 */
export async function getSummary(month: number, year: number): Promise<IMonthlySummary> {
  try {
    const res = await fetch(
      `${API_URL}/transactions/summary?month=${month}&year=${year}`,
      { method: "GET", cache: "no-store" },
    );
    return await handle<IMonthlySummary>(res);
  } catch (err) {
    console.error("getSummary failed:", err);
    throw err;
  }
}

/**
 * GET /transactions/recent?month=&year= — that month's transactions (income +
 * expenses), newest first. Used for the recent table and to derive the charts.
 */
export async function getRecent(month: number, year: number): Promise<ITransaction[]> {
  try {
    const res = await fetch(
      `${API_URL}/transactions/recent?month=${month}&year=${year}`,
      { method: "GET", cache: "no-store" },
    );
    return await handle<ITransaction[]>(res);
  } catch (err) {
    console.error("getRecent failed:", err);
    throw err;
  }
}

/**
 * PUT /balance — set a new manual balance; returns the refreshed snapshot.
 */
export async function setBalance(amount: number): Promise<IBalance> {
  try {
    const res = await fetch(`${API_URL}/balance`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount }), // matches SetBalanceRequest { amount }
    });
    return await handle<IBalance>(res);
  } catch (err) {
    console.error("setBalance failed:", err);
    throw err;
  }
}

/**
 * POST /advisor/advice — get AI advice for a month.
 * Sends {month, year} (either may be omitted = current month), returns the advice.
 */
export async function getAdvice(req: IAdviceRequest): Promise<IAdviceResponse> {
  try {
    const res = await fetch(`${API_URL}/advisor/advice`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req), // must match AdviceRequest { month?, year? }
    });
    return await handle<IAdviceResponse>(res);
  } catch (err) {
    console.error("getAdvice failed:", err);
    throw err;
  }
}

/**
 * GET /advisor/periods — the months that actually have logged data, newest-first.
 * Used to populate the Advisor's month dropdown.
 */
export async function getPeriods(): Promise<IPeriod[]> {
  try {
    const res = await fetch(`${API_URL}/advisor/periods`, {
      method: "GET",
      cache: "no-store",
    });
    return await handle<IPeriod[]>(res);
  } catch (err) {
    console.error("getPeriods failed:", err);
    throw err;
  }
}
