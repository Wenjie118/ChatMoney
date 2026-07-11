/**
 * Shared constants for the frontend.
 *
 * SOURCE OF TRUTH — the backend owns these lists. `llm.py` defines
 * `EXPENSE_CATEGORIES` / `INCOME_SOURCES` and injects them into the parser
 * prompts, so the values the LLM may emit come from there. This file is the
 * frontend MIRROR that drives the review dropdowns, and it must be kept in sync
 * with `llm.py`: if you change the allowed categories/sources, change them in
 * BOTH places (backend `llm.py` first, then here).
 */

/** Allowed expense categories — mirror of llm.py `EXPENSE_CATEGORIES`. */
export const EXPENSE_CATEGORIES = [
  "Food",
  "Transport",
  "Shopping",
  "Entertainment",
  "Health",
  "Bills",
  "Transfer", // internal account move; pairs with the "Transfer" income source
  "Other",
] as const;

/** Allowed income sources — mirror of llm.py `INCOME_SOURCES`. */
export const INCOME_SOURCES = ["Salary", "Transfer", "Interest", "Other"] as const;

/**
 * Pick the right option list for a transaction row: expenses use categories,
 * income uses sources. (Both share the single `category_or_source` field.)
 */
export function optionsForType(type: string): readonly string[] {
  return type === "income" ? INCOME_SOURCES : EXPENSE_CATEGORIES;
}
