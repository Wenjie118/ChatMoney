/**
 * TransactionPreview — the editable table for reviewing PDF-parsed transactions.
 *
 * This is the React replacement for Streamlit's st.data_editor. The user must be
 * able to edit cells, delete rows, add rows, then confirm-save.
 *
 * Approach options:
 *   - Simplest: keep rows in useState and render with rows.map(...) + <input>s.
 *   - Fancier:  use @tanstack/react-table (already in package.json) for sorting etc.
 * Start simple; you can upgrade later.
 */
"use client";

import { useState } from "react";
import type { ITransaction } from "@/lib/types";
// import { saveMultiple } from "@/lib/api";

interface Props {
  /** Consolidated rows returned by api.parsePDF(). */
  initialRows: ITransaction[];
  /** Optional callback after a successful save (e.g. to clear the preview). */
  onSaved?: (result: { total: number; saved: number; failed: number }) => void;
}

export default function TransactionPreview({ initialRows, onSaved }: Props) {
  // Local editable copy of the rows. All edits stay here until "Confirm & Save".
  const [rows, setRows] = useState<ITransaction[]>(initialRows);

  // TODO: updateRow(index, field, value)  -> immutably update one cell in `rows`
  // TODO: deleteRow(index)                -> remove a row from `rows`
  // TODO: addRow()                        -> append a blank ITransaction
  // TODO: handleSave()
  //         1. const result = await saveMultiple(rows)
  //         2. onSaved?.(result)
  //         3. catch + surface errors

  return (
    <div>
      {/* TODO: render a table header: Date | Type | Description | Category/Source | Amount | (delete) */}
      {/* TODO: rows.map((row, i) => <tr> with <input>s bound to updateRow(i, ...) and a delete button */}
      {/* TODO: "Add row" button -> addRow() */}
      {/* TODO: "Confirm & Save" button -> handleSave() */}
      <p className="text-gray-400">TODO: build the editable table ({rows.length} rows)</p>
    </div>
  );
}
