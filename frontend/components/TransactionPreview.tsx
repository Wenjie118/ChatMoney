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
import type { ITransaction } from "@/lib/types";
import { saveMultiple } from "@/lib/api";
import { optionsForType } from "@/lib/constants";

interface Props {
  /** Consolidated rows returned by api.parsePDF(). */
  initialRows: ITransaction[];
  /** Optional callback after a successful save (e.g. to clear the preview). */
  onSaved?: (result: { total: number; saved: number; failed: number }) => void;
}

/** A fresh, empty row for the "Add row" button. */
function blankRow(): ITransaction {
  return {
    type: "expense",
    amount: 0,
    category_or_source: "",
    description: "",
    date: new Date().toISOString().slice(0, 10), // today as "YYYY-MM-DD"
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

export default function TransactionPreview({ initialRows, onSaved }: Props) {
  // Local editable copy of the rows, each tagged with a stable id. All edits stay
  // here until "Confirm & Save". Lazy initializer so ids are assigned once, when
  // the rows first load (the parent remounts us via `key` for a new PDF).
  const [rows, setRows] = useState<EditableRow[]>(() => initialRows.map(makeRow));
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  /** Immutably update ONE field of the row with the given id. */
  function updateRow(id: string, field: keyof ITransaction, value: string | number) {
    setRows((prev) =>
      prev.map((row) =>
        row.id === id ? { ...row, data: { ...row.data, [field]: value } } : row,
      ),
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
              <th className="p-2">Amount</th>
              <th className="p-2">Count</th>
              <th className="p-2"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ id, data }) => (
              <tr key={id} className="border-t">
                <td className="p-1">
                  <input
                    className="w-28 rounded border px-2 py-1"
                    value={data.date}
                    onChange={(e) => updateRow(id, "date", e.target.value)}
                  />
                </td>
                <td className="p-1">
                  <select
                    className="rounded border px-2 py-1"
                    value={data.type}
                    onChange={(e) => updateRow(id, "type", e.target.value)}
                  >
                    <option value="expense">expense</option>
                    <option value="income">income</option>
                  </select>
                </td>
                <td className="p-1">
                  <input
                    className="w-full rounded border px-2 py-1"
                    value={data.description ?? ""}
                    onChange={(e) => updateRow(id, "description", e.target.value)}
                  />
                </td>
                <td className="p-1">
                  <select
                    className="w-36 rounded border px-2 py-1"
                    value={data.category_or_source ?? ""}
                    onChange={(e) => updateRow(id, "category_or_source", e.target.value)}
                  >
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
                </td>
                <td className="p-1">
                  <input
                    type="number"
                    step="0.01"
                    className="w-24 rounded border px-2 py-1"
                    value={data.amount}
                    // <input type=number> still yields a string; coerce to a real number.
                    onChange={(e) => updateRow(id, "amount", Number(e.target.value))}
                  />
                </td>
                <td className="p-2 text-center text-gray-500">{data.count ?? 1}</td>
                <td className="p-1">
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
