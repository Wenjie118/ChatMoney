/**
 * Advisor — the AI Advisor tab (Slice 2).
 *
 * Flow: the user picks a month -> clicks "Get advice" -> we call getAdvice() ->
 * the backend forwards to llm.get_advice() (Gemini) -> we render the returned
 * Markdown. The month dropdown is populated from getPeriods() so it only lists
 * months that actually have logged data.
 *
 * State pattern: like BalanceCard we fetch the period list once on mount
 * (useEffect with []), but the advice itself is fetched on a button click —
 * because an AI call is expensive and should only run when the user asks for it.
 */
"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { getAdvice, getPeriods } from "@/lib/api";
import type { IPeriod } from "@/lib/types";

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

/** Encode a period as a single string value for the <select> (e.g. "2026-6"). */
function periodKey(p: IPeriod): string {
  return `${p.year}-${p.month}`;
}

export default function Advisor() {
  const today = new Date();

  // The month list for the dropdown + the user's current selection.
  const [periods, setPeriods] = useState<IPeriod[]>([]);
  const [selected, setSelected] = useState<IPeriod>({
    year: today.getFullYear(),
    month: today.getMonth() + 1, // getMonth() is 0-based
  });

  // The advice result + UI flags.
  const [advice, setAdvice] = useState<string | null>(null);
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

  async function handleGetAdvice() {
    if (loading) return;
    setLoading(true);
    setError(null);
    setAdvice(null);
    try {
      const res = await getAdvice({ month: selected.month, year: selected.year });
      setAdvice(res.advice);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not get advice");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
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
          onClick={handleGetAdvice}
          disabled={loading}
        >
          {loading ? "Thinking…" : "Get advice"}
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
          Analyzing your finances and writing advice…
        </div>
      )}

      {/* Empty state before any advice has been requested. */}
      {!advice && !loading && !error && (
        <div className="rounded-2xl border border-dashed border-gray-300 bg-white p-8 text-center text-gray-400">
          <p className="text-3xl">🤖</p>
          <p className="mt-2 text-sm">Pick a month and click <b>Get advice</b> for a personalized financial breakdown.</p>
        </div>
      )}

      {/* get_advice returns Markdown; ReactMarkdown turns it into real HTML
          (headings, bold, bullet lists). The `prose` classes style it nicely. */}
      {advice && (
        <article className="prose prose-sm prose-violet max-w-none rounded-2xl border border-gray-200 bg-white p-6 shadow-card">
          <ReactMarkdown>{advice}</ReactMarkdown>
        </article>
      )}
    </div>
  );
}
