/**
 * Shared constants for the frontend.
 *
 * IMPORTANT — keep these in sync with the backend prompt in `llm.py`
 * (PARSER_TEMPLATE / PDF_PARSER_TEMPLATE). The LLM is instructed to only ever
 * output one of these values, so the review dropdowns offer exactly the same set.
 * If you change the allowed categories/sources, change them in BOTH places.
 */

/** Allowed expense categories (llm.py: "category: one of [...]"). */
export const EXPENSE_CATEGORIES = [
  "Food",
  "Transport",
  "Shopping",
  "Entertainment",
  "Health",
  "Bills",
  "Other",
] as const;

/** Allowed income sources (llm.py: "source: one of [...]"). */
export const INCOME_SOURCES = ["Salary", "Transfer", "Interest", "Other"] as const;

/**
 * Pick the right option list for a transaction row: expenses use categories,
 * income uses sources. (Both share the single `category_or_source` field.)
 */
export function optionsForType(type: string): readonly string[] {
  return type === "income" ? INCOME_SOURCES : EXPENSE_CATEGORIES;
}
