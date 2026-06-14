/**
 * BalanceCard — displays the current balance and lets the user set a new one.
 *
 * Pairs with api.getBalance() (read) and api.setBalance() (write), so it shows the
 * full data loop: useState holds data/loading/error -> useEffect fetches once on
 * mount -> the update control writes, then stores the refreshed snapshot the PUT
 * returns (no second GET needed).
 */
"use client";

import { useEffect, useState } from "react";
import { getBalance, setBalance } from "@/lib/api";
import type { IBalance } from "@/lib/types";

export default function BalanceCard() {
  const [balance, setBalanceState] = useState<IBalance | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // The "update balance" control's own state.
  const [editing, setEditing] = useState(false);
  const [input, setInput] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    // Fetch once on mount. (The empty [] dependency array = "run only on mount".)
    getBalance()
      .then(setBalanceState)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleUpdate() {
    const amount = Number(input);
    if (Number.isNaN(amount) || saving) return;
    setSaving(true);
    try {
      // PUT returns the refreshed snapshot, so we store it directly.
      const updated = await setBalance(amount);
      setBalanceState(updated);
      setEditing(false);
      setInput("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="h-32 animate-pulse rounded-2xl bg-gray-200" aria-label="Loading balance" />
    );
  }
  if (error) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-700">{error}</div>
    );
  }

  return (
    <div className="brand-gradient relative overflow-hidden rounded-2xl p-6 text-white shadow-card">
      {/* Decorative soft circle in the corner for depth. */}
      <div className="pointer-events-none absolute -right-8 -top-8 h-32 w-32 rounded-full bg-white/10" />

      <p className="text-sm font-medium text-white/80">Current Balance</p>
      <p className="mt-1 text-4xl font-bold tracking-tight">
        RM {balance!.current_balance.toFixed(2)}
      </p>
      {balance!.last_updated && (
        <p className="mt-1 text-xs text-white/70">Last updated: {balance!.last_updated}</p>
      )}

      {editing ? (
        <div className="mt-4 flex flex-wrap gap-2">
          <input
            type="number"
            step="0.01"
            className="w-36 rounded-lg border-0 bg-white/95 px-3 py-1.5 text-sm text-gray-900 placeholder-gray-400 outline-none focus:ring-2 focus:ring-white"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="e.g. 5000"
            autoFocus
          />
          <button
            className="rounded-lg bg-white px-3 py-1.5 text-sm font-medium text-violet-700 transition hover:bg-white/90 disabled:opacity-50"
            onClick={handleUpdate}
            disabled={saving}
          >
            {saving ? "Saving…" : "Save"}
          </button>
          <button
            className="rounded-lg border border-white/40 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-white/10"
            onClick={() => setEditing(false)}
            disabled={saving}
          >
            Cancel
          </button>
        </div>
      ) : (
        <button
          className="mt-4 rounded-lg border border-white/40 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-white/10"
          onClick={() => setEditing(true)}
        >
          Update balance
        </button>
      )}
    </div>
  );
}
