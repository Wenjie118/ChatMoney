/**
 * Dashboard — the Dashboard tab (replaces the old Streamlit charts/metrics).
 *
 * Responsibilities:
 *   - show the balance (reuse <BalanceCard />)
 *   - show 4 metric cards (income, expenses, net savings, savings rate)
 *   - show charts (spending by category, income by source) — add Recharts later
 *   - month/year picker (only months with data) — mirror the old dropdown
 *
 * Stub only. Wire it to the backend as you add the corresponding endpoints.
 */
"use client";

import BalanceCard from "./BalanceCard";
// import { useEffect, useState } from "react";
// NOTE: you'll need a backend endpoint for the monthly summary + charts data.
//       (e.g. GET /transactions/summary?month=&year=, backed by db.get_monthly_summary
//        / db.get_expenses / db.get_income). Add it, then a client fn in api.ts.

export default function Dashboard() {
  // TODO: useState for summary metrics, expenses, income, selected month/year
  // TODO: useEffect to fetch summary + transactions when the selected month changes

  return (
    <div className="space-y-4">
      {/* Balance section (this one already works via the completed example). */}
      <BalanceCard />

      {/* TODO: month/year <select> populated from a GET /advisor/periods style
          endpoint so only logged months appear. */}

      {/* TODO: 4 metric cards in a grid:
          Total Income | Total Expenses | Net Savings | Savings Rate */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <p className="text-gray-400">TODO: metric cards</p>
      </div>

      {/* TODO: charts. Install Recharts and render e.g. <BarChart> for spending by
          category and <PieChart> for distribution. */}
      <div className="rounded-xl border p-4">
        <p className="text-gray-400">TODO: charts (Recharts)</p>
      </div>

      {/* TODO: recent expenses table (sorted latest -> oldest, Date column first). */}
    </div>
  );
}
