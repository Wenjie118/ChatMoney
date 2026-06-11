/**
 * Shared TypeScript types — the frontend's view of the API contract.
 *
 * These should MIRROR the Pydantic models in backend/schemas/models.py. When you
 * change a field on one side, change it on the other so the two stay in sync.
 *
 * Convention here: interfaces are prefixed with `I` (ITransaction, IBalance, ...).
 */

/** A single transaction, parsed from text/PDF or fetched from the DB. */
export interface ITransaction {
  type: "expense" | "income";
  amount: number;
  /** category (for expenses) OR source (for income) — one combined field for the UI */
  categoryOrSource: string | null;
  description: string | null;
  /** ISO date string, "YYYY-MM-DD" */
  date: string;
  // TODO: add `count?: number` if you display consolidated PDF rows (merged duplicates).
}

/** Mirrors backend BalanceResponse / db.get_balance(). */
export interface IBalance {
  current_balance: number;
  manual_balance: number;
  last_updated: string | null;
}

/** Body for POST /advisor/advice. */
export interface IAdviceRequest {
  // TODO: optional month/year so the user can pick which month to analyze
  month?: number | null;
  year?: number | null;
}

/** Response from POST /advisor/advice. */
export interface IAdviceResponse {
  // TODO: the advice markdown string (and optionally the analyzed period)
  advice: string;
  // period?: string;
}

/** Response from POST /transactions/save-multiple (mirrors db.save_multiple_transactions). */
export interface ISaveMultipleResult {
  total: number;
  saved: number;
  failed: number;
}

// TODO: add more interfaces as you build endpoints, e.g.
//   IParseTextRequest { text: string }
//   IMonthlySummary { total_income; total_expenses; net_savings; savings_rate }
