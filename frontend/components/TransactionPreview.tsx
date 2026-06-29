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
 */
"use client";

import { useState } from "react";
import type { ITransaction } from "@/lib/types";
import { saveMultiple } from "@/lib/api";
import { optionsForType } from "@/lib/constants";

interface Props {
  /** Consolidated rows returned by api.parsePDF(). */
  initialRows: ITransaction[];
  /** Active plan's TAGGED bucket labels. When non-empty, an editable Allocation
   *  column is shown so each expense can be tagged to a bucket. Empty/omitted =
   *  no active plan, so the column is hidden and allocations stay null. */
  allocationOptions?: string[];
  /** Optional callback after a successful save (e.g. to clear the preview). */
  onSaved?: (result: { total: number; saved: number; failed: number }) => void;
}

/** Fallback bucket when an expense has no allocation but a plan is active. */
const DEFAULT_ALLOCATION = "Daily Spending";

/** A fresh, empty row for the "Add row" button. */
function blankRow(): ITransaction {
  return {
    type: "expense",
    amount: 0,
    category_or_source: "",
    description: "",
    date: new Date().toISOString().slice(0, 10), // today as "YYYY-MM-DD"
    allocation: null,
  };
}

export default function TransactionPreview({ initialRows, allocationOptions, onSaved }: Props) {
  // Only offer allocation tagging when there's an active plan with tagged buckets.
  const showAllocation = (allocationOptions?.length ?? 0) > 0;
  // Local editable copy of the rows. All edits stay here until "Confirm & Save".
  const [rows, setRows] = useState<ITransaction[]>(initialRows);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  /** Immutably update ONE field of ONE row. */
  function updateRow(index: number, field: keyof ITransaction, value: string | number) {
    setRows((prev) =>
      prev.map((row, i) => (i === index ? { ...row, [field]: value } : row)),
    );
  }

  /** Remove the row at `index`. */
  function deleteRow(index: number) {
    setRows((prev) => prev.filter((_, i) => i !== index));
  }

  /** Append a fresh blank row at the bottom. */
  function addRow() {
    setRows((prev) => [...prev, blankRow()]);
  }

  /** Send every row to the backend's bulk-save endpoint. */
  async function handleSave() {
    if (saving || rows.length === 0) return;
    setSaving(true);
    setMessage(null);
    try {
      // Normalize allocation: only expenses carry one, and only when a plan is
      // active. An untouched expense (null) falls back to "Daily Spending" so it
      // matches what the dropdown displays. Income is always null.
      const payload = rows.map((r) => ({
        ...r,
        allocation:
          showAllocation && r.type === "expense"
            ? r.allocation || DEFAULT_ALLOCATION
            : null,
      }));
      const result = await saveMultiple(payload);
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
      <h3 className="font-semibold">✏️ Review &amp; edit ({rows.length} rows)</h3>
      <p className="text-sm text-gray-500">
        Edit any cell, delete a row, or add new ones. <b>Count</b> shows how many
        statement lines were merged. Nothing is saved until you confirm.
      </p>

      <div className="overflow-x-auto rounded-xl border border-gray-200">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left text-gray-600">
            <tr>
              <th className="p-2">Date</th>
              <th className="p-2">Type</th>
              <th className="p-2">Description</th>
              <th className="p-2">Category/Source</th>
              {showAllocation && <th className="p-2">Allocation</th>}
              <th className="p-2">Amount</th>
              <th className="p-2">Count</th>
              <th className="p-2"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className="border-t">
                <td className="p-1">
                  <input
                    className="w-28 rounded border px-2 py-1"
                    value={row.date}
                    onChange={(e) => updateRow(i, "date", e.target.value)}
                  />
                </td>
                <td className="p-1">
                  <select
                    className="rounded border px-2 py-1"
                    value={row.type}
                    onChange={(e) => updateRow(i, "type", e.target.value)}
                  >
                    <option value="expense">expense</option>
                    <option value="income">income</option>
                  </select>
                </td>
                <td className="p-1">
                  <input
                    className="w-full rounded border px-2 py-1"
                    value={row.description ?? ""}
                    onChange={(e) => updateRow(i, "description", e.target.value)}
                  />
                </td>
                <td className="p-1">
                  <select
                    className="w-36 rounded border px-2 py-1"
                    value={row.category_or_source ?? ""}
                    onChange={(e) => updateRow(i, "category_or_source", e.target.value)}
                  >
                    {/* Options come from the canonical lists in lib/constants.ts,
                        switched by row type (expense=categories, income=sources). */}
                    {/* Safety: if the parsed value isn't a known option (rare),
                        keep it as an option so the data isn't silently changed. */}
                    {row.category_or_source &&
                      !optionsForType(row.type).includes(row.category_or_source) && (
                        <option value={row.category_or_source}>
                          {row.category_or_source}
                        </option>
                      )}
                    {optionsForType(row.type).map((opt) => (
                      <option key={opt} value={opt}>
                        {opt}
                      </option>
                    ))}
                  </select>
                </td>
                {showAllocation && (
                  <td className="p-1">
                    {row.type === "expense" ? (
                      <select
                        className="w-36 rounded border px-2 py-1"
                        value={row.allocation ?? DEFAULT_ALLOCATION}
                        onChange={(e) => updateRow(i, "allocation", e.target.value)}
                      >
                        {/* Keep an unknown LLM guess as an option so it isn't lost. */}
                        {row.allocation &&
                          !allocationOptions!.includes(row.allocation) && (
                            <option value={row.allocation}>{row.allocation}</option>
                          )}
                        {allocationOptions!.map((opt) => (
                          <option key={opt} value={opt}>
                            {opt}
                          </option>
                        ))}
                      </select>
                    ) : (
                      // Income rows are never tagged.
                      <span className="text-gray-300">—</span>
                    )}
                  </td>
                )}
                <td className="p-1">
                  <input
                    type="number"
                    step="0.01"
                    className="w-24 rounded border px-2 py-1"
                    value={row.amount}
                    // <input type=number> still yields a string; coerce to a real number.
                    onChange={(e) => updateRow(i, "amount", Number(e.target.value))}
                  />
                </td>
                <td className="p-2 text-center text-gray-500">{row.count ?? 1}</td>
                <td className="p-1">
                  <button
                    className="rounded px-2 py-1 text-red-600 hover:bg-red-50"
                    onClick={() => deleteRow(i)}
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
