/**
 * BalanceCard — displays the current balance (read-only).
 *
 * The balance is DERIVED from wallets: current_balance === wallet_total +
 * unassigned. Edit a wallet in the Wallets tab and this number moves by exactly
 * that much — there is nothing else stacked underneath it. So this card only READS
 * `GET /balance`; there is no "update balance" control (and no PUT /balance).
 */
"use client";

import { useEffect, useState } from "react";
import { getBalance } from "@/lib/api";
import type { IBalance } from "@/lib/types";

export default function BalanceCard() {
  const [balance, setBalanceState] = useState<IBalance | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch once on mount. (The empty [] dependency array = "run only on mount".)
    getBalance()
      .then(setBalanceState)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

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
        <p className="mt-1 text-xs text-white/70">Last movement: {balance!.last_updated}</p>
      )}

      {/* Show the derivation only when there's unassigned money to explain the gap;
          otherwise the balance IS the wallet total and a breakdown adds noise. */}
      {Math.abs(balance!.unassigned) > 0.005 ? (
        <p className="mt-3 text-xs text-white/70">
          Wallets RM {balance!.wallet_total.toFixed(2)} + unassigned RM{" "}
          {balance!.unassigned.toFixed(2)} — assign it in the{" "}
          <span className="font-medium">Wallets</span> tab.
        </p>
      ) : (
        <p className="mt-3 text-xs text-white/70">
          The total of your wallets. Change it by editing a wallet in the{" "}
          <span className="font-medium">Wallets</span> tab.
        </p>
      )}
    </div>
  );
}
