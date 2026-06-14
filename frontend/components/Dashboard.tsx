/**
 * Dashboard — the Dashboard tab (replaces the old Streamlit charts/metrics).
 *
 * One month/year picker drives EVERYTHING on this screen:
 *   - getSummary(month, year)  -> the 4 metric cards
 *   - getRecent(month, year)   -> the recent table AND the category chart data
 *
 * DATA-FETCH PATTERN: we keep the fetched data in useState and refetch inside a
 * useEffect whose dependency array is [month, year]. React re-runs that effect
 * every time the user changes the picker, so the screen always matches the
 * selected month. (BalanceCard uses the same pattern but with an empty [] = fetch
 * once on mount.)
 */
"use client";

import { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import BalanceCard from "./BalanceCard";
import { getSummary, getRecent, getPeriods } from "@/lib/api";
import type { IMonthlySummary, ITransaction, IPeriod } from "@/lib/types";

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
// A small palette for the pie slices (cycled with the modulo operator below).
const COLORS = ["#7c3aed", "#2563eb", "#059669", "#d97706", "#dc2626", "#0891b2", "#db2777"];

/** Format a number as Malaysian Ringgit, e.g. 1234.5 -> "RM 1234.50". */
function rm(n: number): string {
  return `RM ${n.toFixed(2)}`;
}

/** One metric card. Pulled out so the four cards stay consistent. */
function MetricCard({
  label,
  value,
  icon,
  accent,
}: {
  label: string;
  value: string;
  icon: string;
  accent: string; // tailwind text color class for the value
}) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-card transition hover:shadow-md">
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <span className="text-base">{icon}</span>
        <span>{label}</span>
      </div>
      <p className={`mt-2 text-2xl font-bold tracking-tight ${accent}`}>{value}</p>
    </div>
  );
}

export default function Dashboard() {
  const today = new Date();
  const [month, setMonth] = useState(today.getMonth() + 1); // getMonth() is 0-based
  const [year, setYear] = useState(today.getFullYear());

  const [summary, setSummary] = useState<IMonthlySummary | null>(null);
  const [recent, setRecent] = useState<ITransaction[]>([]);
  const [periods, setPeriods] = useState<IPeriod[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // On mount, load the months that actually have data and jump to the newest one.
  useEffect(() => {
    getPeriods()
      .then((ps) => {
        setPeriods(ps);
        if (ps.length > 0) {
          // getPeriods returns newest-first, so ps[0] is the most recent month.
          setYear(ps[0].year);
          setMonth(ps[0].month);
        }
      })
      .catch(() => {
        /* offline / no data: fall back to the current month already in state */
      });
  }, []);

  // Refetch whenever the selected month/year changes.
  useEffect(() => {
    let cancelled = false; // guard against a slow response landing after a newer one
    setLoading(true);
    setError(null);

    Promise.all([getSummary(month, year), getRecent(month, year)])
      .then(([s, r]) => {
        if (cancelled) return;
        setSummary(s);
        setRecent(r);
      })
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));

    return () => {
      cancelled = true;
    };
  }, [month, year]);

  // Derive "spending by category" from the expense rows (for the charts).
  const byCategory: Record<string, number> = {};
  for (const t of recent) {
    if (t.type === "expense") {
      const key = t.category_or_source ?? "Uncategorized";
      byCategory[key] = (byCategory[key] ?? 0) + t.amount;
    }
  }
  const chartData = Object.entries(byCategory).map(([name, value]) => ({ name, value }));

  // Build the dropdown options from the logged periods: which years have data,
  // and for each year, which months have data (so we never offer an empty month).
  const monthsByYear: Record<number, number[]> = {};
  for (const p of periods) {
    (monthsByYear[p.year] ??= []).push(p.month);
  }
  Object.values(monthsByYear).forEach((ms) => ms.sort((a, b) => a - b));

  const yearsWithData = Object.keys(monthsByYear).map(Number).sort((a, b) => b - a);
  // Fall back to the current selection when there's no data yet, so the
  // dropdowns are never empty.
  const yearOptions = yearsWithData.length ? yearsWithData : [year];
  const monthOptions = monthsByYear[year] ?? [month];

  return (
    <div className="space-y-5">
      {/* Balance section (already works via the completed example). */}
      <BalanceCard />

      {/* Month / year picker. */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-gray-500">Showing</span>
        <select
          className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm outline-none transition focus:border-violet-500 focus:ring-2 focus:ring-violet-200"
          value={month}
          onChange={(e) => setMonth(Number(e.target.value))}
        >
          {monthOptions.map((m) => (
            <option key={m} value={m}>
              {MONTHS[m - 1]}
            </option>
          ))}
        </select>
        <select
          className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm outline-none transition focus:border-violet-500 focus:ring-2 focus:ring-violet-200"
          value={year}
          onChange={(e) => {
            const y = Number(e.target.value);
            setYear(y);
            // If the month we're on has no data in the newly-picked year, jump to
            // that year's latest month with data.
            const ms = monthsByYear[y] ?? [];
            if (ms.length && !ms.includes(month)) setMonth(ms[ms.length - 1]);
          }}
        >
          {yearOptions.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {loading && (
        <p className="text-sm text-gray-400">
          Loading {MONTHS[month - 1]} {year}…
        </p>
      )}

      {/* 4 metric cards. */}
      {summary && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <MetricCard icon="💵" label="Total Income" value={rm(summary.total_income)} accent="text-emerald-600" />
          <MetricCard icon="💸" label="Total Expenses" value={rm(summary.total_expenses)} accent="text-rose-600" />
          <MetricCard
            icon="💰"
            label="Net Savings"
            value={rm(summary.net_savings)}
            accent={summary.net_savings >= 0 ? "text-emerald-600" : "text-rose-600"}
          />
          <MetricCard icon="📈" label="Savings Rate" value={`${summary.savings_rate.toFixed(1)}%`} accent="text-violet-600" />
        </div>
      )}

      {/* Charts: spending by category (bar + pie). Only shown when there are expenses. */}
      {chartData.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-card">
            <p className="mb-3 text-sm font-semibold text-gray-700">📊 Spending by Category</p>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={chartData}>
                <XAxis dataKey="name" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis fontSize={11} tickLine={false} axisLine={false} />
                <Tooltip
                  cursor={{ fill: "rgba(124,58,237,0.06)" }}
                  contentStyle={{ borderRadius: 12, border: "1px solid #e5e7eb", fontSize: 12 }}
                />
                <Bar dataKey="value" fill="#7c3aed" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-card">
            <p className="mb-3 text-sm font-semibold text-gray-700">🥧 Expense Distribution</p>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={chartData} dataKey="value" nameKey="name" outerRadius={80} label>
                  {chartData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #e5e7eb", fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Recent transactions table (already sorted newest-first by the backend). */}
      <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-card">
        <p className="border-b border-gray-100 px-5 py-3 text-sm font-semibold text-gray-700">
          📋 Transactions for {MONTHS[month - 1]} {year}
        </p>
        {recent.length === 0 ? (
          <p className="p-5 text-sm text-gray-400">No transactions for this month.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
                <tr>
                  <th className="px-5 py-2.5 font-medium">Date</th>
                  <th className="px-5 py-2.5 font-medium">Type</th>
                  <th className="px-5 py-2.5 font-medium">Description</th>
                  <th className="px-5 py-2.5 font-medium">Category/Source</th>
                  <th className="px-5 py-2.5 text-right font-medium">Amount</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((t, i) => (
                  <tr key={i} className="border-t border-gray-100 transition hover:bg-gray-50">
                    <td className="px-5 py-2.5 text-gray-600">{t.date}</td>
                    <td className="px-5 py-2.5">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          t.type === "income"
                            ? "bg-emerald-100 text-emerald-700"
                            : "bg-rose-100 text-rose-700"
                        }`}
                      >
                        {t.type}
                      </span>
                    </td>
                    <td className="px-5 py-2.5 text-gray-700">{t.description}</td>
                    <td className="px-5 py-2.5 text-gray-700">{t.category_or_source}</td>
                    <td
                      className={`px-5 py-2.5 text-right font-medium ${
                        t.type === "income" ? "text-emerald-600" : "text-rose-600"
                      }`}
                    >
                      {t.type === "income" ? "+" : "-"}
                      {rm(t.amount)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
