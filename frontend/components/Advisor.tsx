/**
 * Advisor — the AI Advisor tab (Slice 2).
 *
 * Two modes, toggled at the top:
 *   - "Month review"   -> getAdvice()          -> llm.get_advice()  (complete month:
 *                          income, expenses, savings rate)
 *   - "Spending so far" -> getSpendingAnalysis() -> llm.get_spending_analysis()
 *                          (provisional, expense-only, forward-looking projection)
 * Both take the same {month, year} and return Markdown that we render the same way;
 * only the endpoint, button label, and copy change. The month dropdown is populated
 * from getPeriods() so it only lists months that actually have logged data.
 *
 * State pattern: like BalanceCard we fetch the period list once on mount
 * (useEffect with []), but the result itself is fetched on a button click —
 * because an AI call is expensive and should only run when the user asks for it.
 */
"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { getAdvice, getSpendingAnalysis, getPeriods } from "@/lib/api";
import type { IPeriod } from "@/lib/types";

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

/** Which advisor is active. */
type AdvisorMode = "advice" | "spending";

/** Per-mode copy so the toggle, button, and empty state stay in sync. */
const MODE_META: Record<AdvisorMode, { tab: string; button: string; hint: string }> = {
  advice: {
    tab: "Month review",
    button: "Get advice",
    hint: "for a full breakdown of that month's income, spending and savings.",
  },
  spending: {
    tab: "Spending so far",
    button: "Analyze spending",
    hint: "for a provisional look at your spending so far this month and where it's heading.",
  },
};

/** Encode a period as a single string value for the <select> (e.g. "2026-6"). */
function periodKey(p: IPeriod): string {
  return `${p.year}-${p.month}`;
}

export default function Advisor() {
  const today = new Date();

  // Which of the two advisors is showing.
  const [mode, setMode] = useState<AdvisorMode>("advice");

  // The month list for the dropdown + the user's current selection.
  const [periods, setPeriods] = useState<IPeriod[]>([]);
  const [selected, setSelected] = useState<IPeriod>({
    year: today.getFullYear(),
    month: today.getMonth() + 1, // getMonth() is 0-based
  });

  // The result text (Markdown) + UI flags. Shared by both modes.
  const [result, setResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch the list of logged months once, on mount. Default the picker to the
  // newest one so the user starts on a month that has data.
  useEffect(() => {
    getPeriods()
      .then((ps) => {
        setPeriods(ps);
        if (ps.length > 0) setSelected(ps[0]); // getPeriods returns newest-first
      })
      .catch((e) => setError(e.message));
  }, []);

  // Switching mode clears any previous result so the two never get confused.
  function switchMode(next: AdvisorMode) {
    if (next === mode) return;
    setMode(next);
    setResult(null);
    setError(null);
  }

  async function handleGenerate() {
    if (loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const req = { month: selected.month, year: selected.year };
      // Same request/response text shape either way — pick the endpoint by mode.
      const text =
        mode === "advice"
          ? (await getAdvice(req)).advice
          : (await getSpendingAnalysis(req)).analysis;
      setResult(text);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not generate a response");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      {/* Mode toggle — segmented control switching the active advisor. */}
      <div className="inline-flex rounded-xl border border-gray-200 bg-gray-50 p-1">
        {(Object.keys(MODE_META) as AdvisorMode[]).map((m) => (
          <button
            key={m}
            onClick={() => switchMode(m)}
            className={
              "rounded-lg px-4 py-1.5 text-sm font-medium transition " +
              (mode === m
                ? "bg-white text-violet-700 shadow-sm"
                : "text-gray-500 hover:text-gray-700")
            }
          >
            {MODE_META[m].tab}
          </button>
        ))}
      </div>

      {/* Controls card. */}
      <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-gray-200 bg-white p-4 shadow-card">
        <span className="text-sm font-medium text-gray-500">Analyze</span>
        <select
          className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm outline-none transition focus:border-violet-500 focus:ring-2 focus:ring-violet-200"
          value={periodKey(selected)}
          onChange={(e) => {
            const [year, month] = e.target.value.split("-").map(Number);
            setSelected({ year, month });
          }}
        >
          {periods.length === 0 ? (
            // No logged data yet: still let them try the current month.
            <option value={periodKey(selected)}>
              {MONTHS[selected.month - 1]} {selected.year}
            </option>
          ) : (
            periods.map((p) => (
              <option key={periodKey(p)} value={periodKey(p)}>
                {MONTHS[p.month - 1]} {p.year}
              </option>
            ))
          )}
        </select>

        <button
          className="rounded-lg brand-gradient px-5 py-2 text-sm font-medium text-white shadow-card transition hover:opacity-90 disabled:opacity-50"
          onClick={handleGenerate}
          disabled={loading}
        >
          {loading ? "Thinking…" : MODE_META[mode].button}
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-3 rounded-2xl border border-gray-200 bg-white p-5 text-sm text-gray-500 shadow-card">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-violet-500 border-t-transparent" />
          {mode === "advice"
            ? "Analyzing your finances and writing advice…"
            : "Adding up your spending so far and projecting the month…"}
        </div>
      )}

      {/* Empty state before any result has been requested. */}
      {!result && !loading && !error && (
        <div className="rounded-2xl border border-dashed border-gray-300 bg-white p-8 text-center text-gray-400">
          <p className="text-3xl">🤖</p>
          <p className="mt-2 text-sm">
            Pick a month and click <b>{MODE_META[mode].button}</b> {MODE_META[mode].hint}
          </p>
        </div>
      )}

      {/* Both advisors return Markdown; ReactMarkdown turns it into real HTML
          (headings, bold, bullet lists). The `prose` classes style it nicely. */}
      {result && (
        <article className="prose prose-sm prose-violet max-w-none rounded-2xl border border-gray-200 bg-white p-6 shadow-card">
          <ReactMarkdown>{result}</ReactMarkdown>
        </article>
      )}
    </div>
  );
}
