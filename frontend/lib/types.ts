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
  /** Wallet this transaction is tagged to (null = Unassigned). Optional because
   *  older callers/rows don't set it. Mirrors TransactionResponse.wallet_id. */
  wallet_id?: number | null;
}

/** Mirrors backend BalanceResponse / db.get_balance().
 *  The balance is derived: current_balance === wallet_total + unassigned. */
export interface IBalance {
  current_balance: number;
  /** Σ of active wallet balances. */
  wallet_total: number;
  /** Real money not assigned to a wallet yet. */
  unassigned: number;
  /** Date of the most recent movement (null when there are none). */
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

/** Response from POST /advisor/spending — the mid-month provisional,
 *  expense-only spending analysis. Reuses IAdviceRequest for the request. */
export interface ISpendingAnalysisResponse {
  analysis: string;
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
// Wallets — virtual sub-wallets with computed, ledger-based balances.
// Mirror backend WalletResponse / TransferResponse / etc.
// ===========================================================================

/** A wallet with its COMPUTED balance (GET /wallets). */
export interface IWallet {
  id: number;
  name: string;
  balance: number;
}

/** One movement in a wallet's ledger (GET /wallets/{id}/ledger). */
export interface ILedgerEntry {
  date: string;
  /** income | expense | transfer_in | transfer_out */
  kind: string;
  description: string | null;
  amount: number;
  /** + into the wallet, − out of it */
  signed_amount: number;
}

/** A NULL-wallet income/expense row the user can resolve. */
export interface IUnassignedRow {
  id: number;
  type: "expense" | "income";
  amount: number;
  category_or_source: string | null;
  description: string | null;
  date: string;
}

/** GET /wallets/unassigned — total (incl. pre-wallet baseline) + resolvable rows. */
export interface IUnassigned {
  total: number;
  rows: IUnassignedRow[];
}

/** A stored transfer row (POST /transfers). */
export interface ITransfer {
  id: number;
  from_wallet: number | null;
  to_wallet: number | null;
  amount: number;
  description: string | null;
  date: string;
}
