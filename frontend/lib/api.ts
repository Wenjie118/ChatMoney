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
 * POST /transactions/parse — send free text, backend parses + saves it.
 * TODO:
 *   - fetch(`${API_URL}/transactions/parse`, { method: "POST", headers, body: JSON.stringify({ text }) })
 *   - return await handle<...>(res)
 */
export async function parseTransaction(text: string): Promise<ITransaction[]> {
  // TODO: implement
  throw new Error("Not implemented");
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
  // TODO: implement
  throw new Error("Not implemented");
}

/**
 * POST /transactions/save-multiple — bulk-save reviewed rows.
 * TODO: POST the array as JSON, return ISaveMultipleResult.
 */
export async function saveMultiple(rows: ITransaction[]): Promise<ISaveMultipleResult> {
  // TODO: implement
  throw new Error("Not implemented");
}

/**
 * POST /advisor/advice — get AI advice for a month.
 * TODO: POST the IAdviceRequest as JSON, return IAdviceResponse.
 */
export async function getAdvice(req: IAdviceRequest): Promise<IAdviceResponse> {
  // TODO: implement
  throw new Error("Not implemented");
}
