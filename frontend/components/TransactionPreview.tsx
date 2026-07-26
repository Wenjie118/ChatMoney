/**
 * TransactionPreview — the editable table for reviewing PDF-parsed transactions.
 *
 * This is the React replacement for Streamlit's st.data_editor. The user can edit
 * any cell, delete a row, add a blank row, then "Confirm & Save" to write them all.
 *
 * KEY REACT IDEA — immutable state updates:
 *   React only re-renders when it sees a NEW array/object reference. So we never
 *   mutate `rows` in place (rows[i].amount = ...). Instead we build a fresh array
 *   with .map()/.filter() and hand it to setRows. That's why every helper below
 *   returns a new array.
 *
 * KEY REACT IDEA — stable row keys:
 *   Rows can be added and deleted, so the array index is NOT a stable identity —
 *   after a delete the indices shift and React would reconcile the controlled
 *   inputs onto the wrong logical row (mis-applied edits/focus). We therefore wrap
 *   each transaction in an `EditableRow` that carries a unique `id`, assigned when
 *   rows load and when a row is added, and use that id as the React `key`. The id
 *   is UI-only bookkeeping and is stripped before saving to the backend.
 */
"use client";

import { useState } from "react";
import type { ITransaction, IWallet } from "@/lib/types";
import { saveMultiple } from "@/lib/api";
import { optionsForType } from "@/lib/constants";

interface Props {
  /** Rows to seed the table: consolidated rows from api.parsePDF(), or a single
   *  blankRow() for manual entry. */
  initialRows: ITransaction[];
  /** Optional callback after a successful save (e.g. to clear the preview). */
  onSaved?: (result: { total: number; saved: number; failed: number }) => void;
  /** Heading text; the live row count is appended. Default: PDF-review wording. */
  title?: string;
  /** Help line under the heading. Default: PDF-review wording that explains Count. */
  helpText?: string;
  /** Show the read-only Count column (a PDF-merge artifact). Default true; pass
   *  false for manual entry, where merge counts are meaningless. */
  showCount?: boolean;
  /** Active wallets. When provided (length > 0), a per-row Wallet dropdown is
   *  shown and a wallet is COMPULSORY on every row — Save is blocked until each
   *  row (including PDF-imported ones) has a wallet picked. Omit/empty = no wallet
   *  column (e.g. the user has no wallets yet). */
  wallets?: IWallet[];
}

/** A fresh, empty row for the "Add row" button and for seeding manual entry. */
export function blankRow(): ITransaction {
  return {
    type: "expense",
    amount: NaN, // empty until the user types — renders as a blank box, not a stuck "0"
    category_or_source: "",
    description: "",
    date: new Date().toISOString().slice(0, 10), // today as "YYYY-MM-DD"
    wallet_id: null,
  };
}

/** A transaction plus a client-only, stable id used as the React key. The id is
 *  never sent to the backend — see how handleSave() maps it away. */
interface EditableRow {
  id: string;
  data: ITransaction;
}

/** Monotonic counter for row ids. Only needs to be unique within one list, and a
 *  simple counter avoids any crypto/secure-context concerns of randomUUID(). */
let rowIdCounter = 0;
function makeRow(data: ITransaction): EditableRow {
  return { id: `row-${rowIdCounter++}`, data };
}

/** True when an amount is a saveable value: a positive, finite number. A blank
 *  amount field is stored as NaN (see the amount <input> onChange), which isn't
 *  finite, so this also flags empty amounts. The backend enforces the SAME rule
 *  (TransactionRequest.amount is Field(gt=0)); it validates the whole array
 *  atomically, so one bad row 422s the entire batch. Catching it here turns that
 *  opaque failure into a friendly, row-level nudge before we ever call the API. */
function isValidAmount(amount: number): boolean {
  return Number.isFinite(amount) && amount > 0;
}

/** True when a category/source has actually been picked. A blank manual row (and
 *  the <select>'s placeholder) is an empty string, which would save an
 *  uncategorized transaction and break the per-category dashboard breakdown. The
 *  backend also skips such rows (db.save_multiple_transactions); catching it here
 *  turns that into a friendly, row-level nudge before we call the API. */
function hasCategory(row: ITransaction): boolean {
  return typeof row.category_or_source === "string" && row.category_or_source.trim() !== "";
}

export default function TransactionPreview({
  initialRows,
  onSaved,
  title = "✏️ Review & edit",
  helpText,
  showCount = true,
  wallets,
}: Props) {
  // Only show the wallet column when there are wallets to tag against.
  const showWallets = (wallets?.length ?? 0) > 0;
  // Local editable copy of the rows, each tagged with a stable id. All edits stay
  // here until "Confirm & Save". Lazy initializer so ids are assigned once, when
  // the rows first load (the parent remounts us via `key` for a new PDF).
  const [rows, setRows] = useState<EditableRow[]>(() => initialRows.map(makeRow));
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  // Rows whose amount can't be saved (<= 0 or blank). Derived live from `rows` so
  // the inline highlight and the Save guard can never disagree, and so a flagged
  // row clears itself the moment its amount is fixed.
  const invalidIds = new Set(
    rows.filter((row) => !isValidAmount(row.data.amount)).map((row) => row.id),
  );

  // Rows with no category/source picked. Same live-derivation idea as invalidIds
  // so the red highlight and the Save guard stay in lock-step.
  const missingCategoryIds = new Set(
    rows.filter((row) => !hasCategory(row.data)).map((row) => row.id),
  );

  // Rows with no wallet picked. A wallet is COMPULSORY on every expense/income
  // (product rule), enforced whenever there are wallets to choose from — same
  // live-derived, lock-step pattern as the category guard above.
  const missingWalletIds = new Set(
    showWallets
      ? rows.filter((row) => row.data.wallet_id == null).map((row) => row.id)
      : [],
  );

  /** Immutably update ONE field of the row with the given id. */
  function updateRow(id: string, field: keyof ITransaction, value: string | number) {
    setRows((prev) =>
      prev.map((row) =>
        row.id === id ? { ...row, data: { ...row.data, [field]: value } } : row,
      ),
    );
  }

  /** Set a row's wallet from the dropdown ("" = Unassigned/null). Separate from
   *  updateRow because wallet_id is a number|null, not a string|number. */
  function updateWallet(id: string, value: string) {
    const wid = value === "" ? null : Number(value);
    setRows((prev) =>
      prev.map((row) => (row.id === id ? { ...row, data: { ...row.data, wallet_id: wid } } : row)),
    );
  }

  /** Remove the row with the given id. */
  function deleteRow(id: string) {
    setRows((prev) => prev.filter((row) => row.id !== id));
  }

  /** Append a fresh blank row at the bottom. */
  function addRow() {
    setRows((prev) => [...prev, makeRow(blankRow())]);
  }

  /** Send every row to the backend's bulk-save endpoint. */
  async function handleSave() {
    if (saving || rows.length === 0) return;

    // Guard: a single amount <= 0 makes FastAPI reject the WHOLE array with a
    // generic 422 (nothing saves, no clue which row). Stop here and point at the
    // offending row(s) — the amounts are already highlighted in the table — so the
    // user can fix them and save the rest.
    if (invalidIds.size > 0) {
      const n = invalidIds.size;
      setMessage(
        `⚠️ ${n} row${n > 1 ? "s have" : " has"} an amount of 0 or less. ` +
          `Fix the highlighted amount${n > 1 ? "s" : ""} (must be greater than 0), then save.`,
      );
      return;
    }

    // Guard: an empty category/source saves an uncategorized transaction (the
    // reported bug). Block and point at the highlighted row(s) so the user picks
    // one first.
    if (missingCategoryIds.size > 0) {
      const n = missingCategoryIds.size;
      setMessage(
        `⚠️ ${n} row${n > 1 ? "s are" : " is"} missing a category/source. ` +
          `Pick one for each highlighted row, then save.`,
      );
      return;
    }

    // Guard: a wallet is compulsory on every row (when wallets exist). Block and
    // point at the highlighted row(s) so the user assigns one before saving.
    if (missingWalletIds.size > 0) {
      const n = missingWalletIds.size;
      setMessage(
        `⚠️ ${n} row${n > 1 ? "s are" : " is"} missing a wallet. ` +
          `Pick a wallet for each highlighted row, then save.`,
      );
      return;
    }

    setSaving(true);
    setMessage(null);
    try {
      // Strip the UI-only ids; the backend only ever sees ITransaction data.
      const result = await saveMultiple(rows.map((row) => row.data));
      setMessage(`✅ Saved ${result.saved} of ${result.total} transactions.`);
      onSaved?.(result);
    } catch (err) {
      setMessage(`⚠️ ${err instanceof Error ? err.message : "Save failed"}`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-3">
      <h3 className="font-semibold">
        {title} ({rows.length} rows)
      </h3>
      <p className="text-sm text-gray-500">
        {helpText ?? (
          <>
            Edit any cell, delete a row, or add new ones. <b>Count</b> shows how
            many statement lines were merged. Nothing is saved until you confirm.
          </>
        )}
      </p>

      <div className="overflow-x-auto rounded-xl border border-gray-200">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left text-gray-600">
            <tr>
              <th className="p-2">Date</th>
              <th className="p-2">Type</th>
              <th className="p-2">Description</th>
              <th className="p-2">Category/Source</th>
              {showWallets && <th className="p-2">Wallet</th>}
              <th className="p-2">Amount</th>
              {showCount && <th className="p-2">Count</th>}
              <th className="p-2"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ id, data }) => (
              <tr key={id} className="border-t">
                <td className="p-1 align-top">
                  <input
                    type="date"
                    className="w-36 rounded border px-2 py-1"
                    value={data.date}
                    onChange={(e) => updateRow(id, "date", e.target.value)}
                  />
                </td>
                <td className="p-1 align-top">
                  <select
                    className="rounded border px-2 py-1"
                    value={data.type}
                    onChange={(e) => updateRow(id, "type", e.target.value)}
                  >
                    <option value="expense">expense</option>
                    <option value="income">income</option>
                  </select>
                </td>
                <td className="p-1 align-top">
                  <input
                    className="w-full rounded border px-2 py-1"
                    value={data.description ?? ""}
                    onChange={(e) => updateRow(id, "description", e.target.value)}
                  />
                </td>
                <td className="p-1 align-top">
                  <select
                    className={`w-36 rounded border px-2 py-1 ${
                      missingCategoryIds.has(id)
                        ? "border-red-500 bg-red-50 text-red-700"
                        : ""
                    }`}
                    value={data.category_or_source ?? ""}
                    onChange={(e) => updateRow(id, "category_or_source", e.target.value)}
                    aria-invalid={missingCategoryIds.has(id)}
                  >
                    {/* Placeholder so an unpicked category shows as blank rather than
                        misleadingly displaying the first option while the value is "". */}
                    <option value="" disabled>
                      — Select —
                    </option>
                    {/* Options come from the canonical lists in lib/constants.ts,
                        switched by row type (expense=categories, income=sources). */}
                    {/* Safety: if the parsed value isn't a known option (rare),
                        keep it as an option so the data isn't silently changed. */}
                    {data.category_or_source &&
                      !optionsForType(data.type).includes(data.category_or_source) && (
                        <option value={data.category_or_source}>
                          {data.category_or_source}
                        </option>
                      )}
                    {optionsForType(data.type).map((opt) => (
                      <option key={opt} value={opt}>
                        {opt}
                      </option>
                    ))}
                  </select>
                  {missingCategoryIds.has(id) && (
                    <p className="mt-1 text-xs text-red-600">Pick one</p>
                  )}
                </td>
                {showWallets && (
                  <td className="p-1 align-top">
                    <select
                      className={`w-32 rounded border px-2 py-1 ${
                        missingWalletIds.has(id) ? "border-red-500 bg-red-50 text-red-700" : ""
                      }`}
                      value={data.wallet_id ?? ""}
                      onChange={(e) => updateWallet(id, e.target.value)}
                      aria-invalid={missingWalletIds.has(id)}
                    >
                      {/* Wallet is compulsory — a disabled placeholder means an
                          unpicked wallet shows blank and can't be re-selected. */}
                      <option value="" disabled>
                        — Select —
                      </option>
                      {wallets!.map((w) => (
                        <option key={w.id} value={w.id}>
                          {w.name}
                        </option>
                      ))}
                    </select>
                    {missingWalletIds.has(id) && (
                      <p className="mt-1 text-xs text-red-600">Pick one</p>
                    )}
                  </td>
                )}
                <td className="p-1 align-top">
                  <input
                    type="number"
                    step="0.01"
                    className={`w-24 rounded border px-2 py-1 ${
                      invalidIds.has(id)
                        ? "border-red-500 bg-red-50 text-red-700"
                        : ""
                    }`}
                    // A blank box shows as empty (NaN), not "0", so the user can
                    // clear it and type freely instead of fighting a stuck leading 0.
                    value={Number.isNaN(data.amount) ? "" : data.amount}
                    onChange={(e) => {
                      const raw = e.target.value;
                      updateRow(id, "amount", raw === "" ? NaN : Number(raw));
                    }}
                    aria-invalid={invalidIds.has(id)}
                  />
                  {invalidIds.has(id) && (
                    <p className="mt-1 text-xs text-red-600">Must be &gt; 0</p>
                  )}
                </td>
                {showCount && (
                  <td className="p-2 text-center align-top text-gray-500">{data.count ?? 1}</td>
                )}
                <td className="p-1 align-top">
                  <button
                    className="rounded px-2 py-1 text-red-600 hover:bg-red-50"
                    onClick={() => deleteRow(id)}
                    aria-label="Delete row"
                  >
                    🗑️
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium transition hover:bg-gray-50"
          onClick={addRow}
          disabled={saving}
        >
          + Add row
        </button>
        <button
          className="rounded-lg brand-gradient px-4 py-2 text-sm font-medium text-white shadow-card transition hover:opacity-90 disabled:opacity-50"
          onClick={handleSave}
          disabled={saving || rows.length === 0}
        >
          {saving ? "Saving…" : "✅ Confirm & Save"}
        </button>
        {message && <span className="text-sm text-gray-600">{message}</span>}
      </div>
    </div>
  );
}
