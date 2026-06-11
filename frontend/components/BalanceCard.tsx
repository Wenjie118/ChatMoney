/**
 * BalanceCard — displays the current balance.
 *
 * This is the most "complete" component stub because it pairs with the finished
 * api.getBalance() example, so you can see the full data-fetch → render loop:
 *   useState to hold data/loading/error  ->  useEffect to fetch once  ->  render.
 *
 * It still leaves the polish (formatting, the "update balance" control) as TODO.
 */
"use client";

import { useEffect, useState } from "react";
import { getBalance } from "@/lib/api";
import type { IBalance } from "@/lib/types";

export default function BalanceCard() {
  const [balance, setBalance] = useState<IBalance | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch once on mount. (The empty [] dependency array = "run only on mount".)
    getBalance()
      .then(setBalance)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Loading balance…</p>;
  if (error) return <p className="text-red-600">{error}</p>;

  return (
    <div className="rounded-xl border p-4">
      <p className="text-sm text-gray-500">Current Balance</p>
      {/* TODO: format as Malaysian Ringgit, e.g. `RM ${balance!.current_balance.toFixed(2)}` */}
      <p className="text-2xl font-bold">RM {balance?.current_balance}</p>
      {/* TODO: show `last_updated` caption */}
      {/* TODO: add an "Update balance" button + input that calls a future
          api.setBalance() (you'll add that endpoint + client function). */}
    </div>
  );
}
