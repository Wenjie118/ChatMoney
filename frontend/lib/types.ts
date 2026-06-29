/**
 * Shared TypeScript types — the frontend's view of the API contract.
 *
 * These should MIRROR the Pydantic models in backend/schemas/models.py. When you
 * change a field on one side, change it on the other so the two stay in sync.
 *
 * Convention here: interfaces are prefixed with `I` (ITransaction, IBalance, ...).
 */

/** A single transaction, parsed from text/PDF or fetched from the DB.
 *  Field names MATCH the backend TransactionResponse exactly (snake_case) so the
 *  JSON maps straight onto this type with no renaming. */
export interface ITransaction {
  type: "expense" | "income";
  amount: number;
  /** category (for expenses) OR source (for income) — one combined field for the UI */
  category_or_source: string | null;
  description: string | null;
  /** ISO date string, "YYYY-MM-DD" */
  date: string;
  /** How many statement lines were merged into this row (PDF import only).
   *  Optional `?` because text-parse and /recent rows never set it. Mirrors the
   *  optional `count` on the backend TransactionResponse. */
  count?: number | null;
  /** Salary-plan bucket for expenses (e.g. "Daily Spending", "Mom"). The LLM
   *  guesses it on PDF import; the review table lets the user adjust it. Null for
   *  income / no active plan. Mirrors TransactionResponse.allocation. */
  allocation?: string | null;
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

/** One {year, month} pair that has logged data — from GET /advisor/periods.
 *  Used to populate the Advisor's month dropdown with only months that exist. */
export interface IPeriod {
  year: number;
  month: number;
}

/** Response from POST /transactions/save-multiple (mirrors db.save_multiple_transactions). */
export interface ISaveMultipleResult {
  total: number;
  saved: number;
  failed: number;
}

/** Response from GET /transactions/summary (mirrors backend SummaryResponse).
 *  The four headline numbers shown on the dashboard for one month. */
export interface IMonthlySummary {
  total_income: number;
  total_expenses: number;
  net_savings: number;
  /** percentage, e.g. 23.5 means 23.5% */
  savings_rate: number;
}

// ===========================================================================
// Salary allocation plan — mirrors backend AllocationModel / PlanResponse / etc.
// ===========================================================================

/** One bucket in the active plan (mirrors backend AllocationModel). */
export interface IAllocation {
  id: number;
  label: string;
  target_rm: number;
  /** "tagged" (sum of tagged expenses) or "leftover" (Savings balancing bucket). */
  tracking_mode: "tagged" | "leftover";
  is_default: boolean;
  is_active: boolean;
  /** STORED share of salary for %-based buckets (e.g. EPF 11%); null = RM-based
   *  (target_rm is the fixed source of truth). The UI derives the display %. */
  percent: number | null;
}

/** The active plan, or null when none exists yet (GET /plans). */
export interface IPlan {
  id: number;
  salary: number;
  allocations: IAllocation[];
}

/** One NON-Savings bucket in a save draft. Savings is computed, never sent. */
export interface IPlanBucket {
  /** existing allocation id, or omitted/null when it's a new bucket */
  id?: number | null;
  label: string;
  target_rm: number;
  /** non-null = %-based (server computes RM = salary * percent / 100);
   *  null = RM-based (target_rm used as-is). */
  percent?: number | null;
}

/** Body for PUT /plans — the whole editable draft (mirrors PlanSaveRequest). */
export interface IPlanSaveRequest {
  salary: number;
  buckets: IPlanBucket[];
}

/** One row of the planned-vs-actual table (GET /plans/actuals). */
export interface IAllocationActual {
  label: string;
  target_rm: number;
  actual_rm: number;
  variance_rm: number;
  tracking_mode: "tagged" | "leftover";
}
