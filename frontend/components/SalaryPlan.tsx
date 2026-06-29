/**
 * SalaryPlan — the "Salary Plan" tab.
 *
 * Lets the user describe how they intend to split their salary into buckets, then
 * shows this month's planned-vs-actual adherence. The whole tab is an editable
 * DRAFT with Save / Cancel:
 *   - Cancel  -> reload the last-saved plan from getPlan().
 *   - Save    -> PUT /plans; the backend validates + computes Savings.
 *
 * The app works WITHOUT a plan: getPlan() returns null, and this tab renders a
 * starter draft (just "Daily Spending") the user can build and Save to create one.
 *
 * BALANCING RULE (mirrored from the backend for live feedback): Savings is never
 * hand-entered — it equals salary − sum(non-Savings targets). When that sum
 * exceeds salary, Save is blocked and the readout turns into a warning.
 */
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getPlan, savePlan, getActuals } from "@/lib/api";
import type { IPlan, IAllocationActual } from "@/lib/types";

/** Format a number as Malaysian Ringgit, e.g. 1234.5 -> "RM 1234.50". */
function rm(n: number): string {
  return `RM ${n.toFixed(2)}`;
}

/** Round to 2 decimals as a number (for derived input values — strips the long
 *  floating tail without turning the field into a fixed-2dp string). */
function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

/** A NON-Savings bucket as edited in the draft. Savings is computed, not edited.
 *
 *  Single source of truth per bucket: `mode` says which field drives, and `value`
 *  holds that field's number (RM amount when mode==="rm", else the percentage).
 *  Both display figures are DERIVED from `value` + the current salary, so editing
 *  the salary or either field stays in sync with no extra bookkeeping. */
interface DraftBucket {
  /** existing allocation id, or undefined for a not-yet-saved bucket */
  id?: number;
  label: string;
  /** Daily Spending is a default: its label is locked and it can't be deleted. */
  is_default: boolean;
  /** which field is authoritative — survives salary changes (e.g. EPF stays 11%) */
  mode: "rm" | "percent";
  /** RM amount when mode==="rm"; the percentage of salary when mode==="percent" */
  value: number;
}

/** Effective RM for a bucket at salary S (derives from % when %-based). */
function effRm(b: DraftBucket, S: number): number {
  return b.mode === "percent" ? (S * b.value) / 100 : b.value;
}

/** Effective % of salary for a bucket at salary S (derives from RM when RM-based). */
function effPct(b: DraftBucket, S: number): number {
  if (b.mode === "percent") return b.value;
  return S > 0 ? (b.value / S) * 100 : 0;
}

/** Build the editable draft (salary + tagged buckets) from a loaded plan, or a
 *  starter draft when there's no plan yet (just the Daily Spending default).
 *  A bucket's mode comes from whether it has a stored percent (%-based) or not. */
function draftFromPlan(plan: IPlan | null): { salaryStr: string; buckets: DraftBucket[] } {
  if (!plan) {
    return {
      salaryStr: "",
      buckets: [{ label: "Daily Spending", is_default: true, mode: "rm", value: 0 }],
    };
  }
  return {
    salaryStr: String(plan.salary),
    buckets: plan.allocations
      .filter((a) => a.tracking_mode === "tagged")
      .map((a) =>
        a.percent != null
          ? { id: a.id, label: a.label, is_default: a.is_default, mode: "percent" as const, value: a.percent }
          : { id: a.id, label: a.label, is_default: a.is_default, mode: "rm" as const, value: a.target_rm },
      ),
  };
}

export default function SalaryPlan() {
  const today = new Date();
  const curMonth = today.getMonth() + 1; // getMonth() is 0-based
  const curYear = today.getFullYear();

  // Last-saved plan (for Cancel) + the editable draft.
  const [plan, setPlan] = useState<IPlan | null>(null);
  const [salaryStr, setSalaryStr] = useState("");
  const [buckets, setBuckets] = useState<DraftBucket[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // "Add bucket" inputs.
  const [newLabel, setNewLabel] = useState("");
  const [newTarget, setNewTarget] = useState("");

  // This month's adherence (read-only) — the same data fed to the advisor.
  const [actuals, setActuals] = useState<IAllocationActual[]>([]);

  const loadActuals = useCallback(() => {
    getActuals(curMonth, curYear)
      .then(setActuals)
      .catch(() => setActuals([])); // no plan / offline: just show nothing
  }, [curMonth, curYear]);

  // Load the plan + adherence on mount.
  useEffect(() => {
    setLoading(true);
    getPlan()
      .then((p) => {
        setPlan(p);
        const d = draftFromPlan(p);
        setSalaryStr(d.salaryStr);
        setBuckets(d.buckets);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load plan"))
      .finally(() => setLoading(false));
    loadActuals();
  }, [loadActuals]);

  // Derived live figures (computed in the browser; the server recomputes on save).
  const S = parseFloat(salaryStr) || 0;
  const T = useMemo(() => buckets.reduce((sum, b) => sum + effRm(b, S), 0), [buckets, S]);
  const savingsAuto = S - T;
  const exceeds = T > S;

  /** Set a bucket to RM-mode with the given RM amount. */
  function editRm(index: number, rm: number) {
    setBuckets((prev) => prev.map((b, i) => (i === index ? { ...b, mode: "rm", value: rm } : b)));
  }

  /** Set a bucket to %-mode with the given percentage (stays locked to salary). */
  function editPct(index: number, pct: number) {
    setBuckets((prev) => prev.map((b, i) => (i === index ? { ...b, mode: "percent", value: pct } : b)));
  }

  /** Remove a custom bucket from the draft (deactivated on Save). */
  function removeBucket(index: number) {
    setBuckets((prev) => prev.filter((_, i) => i !== index));
  }

  /** Append a new custom bucket (starts RM-based; edit its % to lock it to salary). */
  function addBucket() {
    const label = newLabel.trim();
    if (!label) return;
    setBuckets((prev) => [
      ...prev,
      { label, is_default: false, mode: "rm", value: parseFloat(newTarget) || 0 },
    ]);
    setNewLabel("");
    setNewTarget("");
  }

  /** Discard edits — reload the last-saved plan into the draft. */
  function handleCancel() {
    const d = draftFromPlan(plan);
    setSalaryStr(d.salaryStr);
    setBuckets(d.buckets);
    setError(null);
    setNotice(null);
  }

  /** Validate locally, then persist. The backend is authoritative (re-validates). */
  async function handleSave() {
    if (saving) return;
    setError(null);
    setNotice(null);

    if (S <= 0) {
      setError("Enter a salary greater than 0 before saving.");
      return;
    }
    if (exceeds) {
      setError(`Your allocations exceed your salary by ${rm(T - S)}. Reduce a bucket before saving.`);
      return;
    }

    setSaving(true);
    try {
      const saved = await savePlan({
        salary: S,
        buckets: buckets.map((b) => ({
          id: b.id ?? null,
          label: b.label,
          target_rm: effRm(b, S),
          // %-based buckets send their percent so the server stores the mode and
          // recomputes RM; RM-based send null.
          percent: b.mode === "percent" ? b.value : null,
        })),
      });
      setPlan(saved);
      const d = draftFromPlan(saved);
      setSalaryStr(d.salaryStr);
      setBuckets(d.buckets);
      setNotice("✅ Plan saved.");
      loadActuals(); // targets changed -> refresh adherence
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save the plan");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <p className="text-sm text-gray-400">Loading your plan…</p>;
  }

  return (
    <div className="space-y-5">
      {/* ---------- Section A — Plan setup ---------- */}
      <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-card">
        <h2 className="mb-3 text-sm font-semibold text-gray-700">💼 Plan setup</h2>
        {!plan && (
          <p className="mb-3 rounded-lg bg-violet-50 px-3 py-2 text-xs text-violet-700">
            You don&apos;t have a plan yet. Set your salary, add buckets, and Save to create one.
            Until then, ChatMoney keeps tracking without a plan.
          </p>
        )}
        <label className="block text-sm font-medium text-gray-600">Monthly salary (RM)</label>
        <input
          type="number"
          step="0.01"
          min="0"
          className="mt-1 w-48 rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm outline-none transition focus:border-violet-500 focus:ring-2 focus:ring-violet-200"
          value={salaryStr}
          onChange={(e) => setSalaryStr(e.target.value)}
          placeholder="e.g. 5000"
        />

        {/* Live readout (over-allocation turns it into a warning). */}
        <div
          className={`mt-4 rounded-xl px-4 py-3 text-sm ${
            exceeds ? "bg-rose-50 text-rose-700" : "bg-gray-50 text-gray-700"
          }`}
        >
          <span className="font-medium">Allocated (non-Savings): {rm(T)}</span>
          <span className="mx-2 text-gray-300">|</span>
          <span>Salary: {rm(S)}</span>
          <span className="mx-2 text-gray-300">|</span>
          <span className="font-medium">
            Savings (auto): {rm(savingsAuto)}
          </span>
          {exceeds && (
            <p className="mt-1 font-medium">
              ⚠️ Allocations exceed salary by {rm(T - S)}. Reduce a bucket before saving.
            </p>
          )}
        </div>
      </div>

      {/* ---------- Section B — Buckets ---------- */}
      <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-card">
        <h2 className="border-b border-gray-100 px-5 py-3 text-sm font-semibold text-gray-700">
          🪣 Buckets
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
              <tr>
                <th className="px-5 py-2.5 font-medium">Bucket</th>
                <th className="px-5 py-2.5 font-medium">Target (RM)</th>
                <th className="px-5 py-2.5 font-medium">% of salary</th>
                <th className="px-5 py-2.5"></th>
              </tr>
            </thead>
            <tbody>
              {/* Savings — the balancing bucket. Always shown, read-only. */}
              <tr className="border-t border-gray-100 bg-emerald-50/40">
                <td className="px-5 py-2.5 font-medium text-emerald-700">Savings (auto)</td>
                <td className="px-5 py-2.5 text-gray-700">{rm(savingsAuto)}</td>
                <td className="px-5 py-2.5 text-gray-500">
                  {S > 0 ? `${((savingsAuto / S) * 100).toFixed(1)}%` : "—"}
                </td>
                <td className="px-5 py-2.5 text-xs text-gray-400">balancing</td>
              </tr>

              {/* Tagged buckets — Daily Spending (default, no delete) + customs.
                  Both Target (RM) and % are editable and kept in sync: editing one
                  sets the bucket's mode so it stays locked to that field (e.g. EPF
                  in %-mode auto-rescales when salary changes). */}
              {buckets.map((b, i) => (
                <tr key={b.id ?? `new-${i}`} className="border-t border-gray-100">
                  <td className="px-5 py-2.5 text-gray-700">
                    {b.label}
                    {b.mode === "percent" && (
                      <span className="ml-2 rounded bg-violet-100 px-1.5 py-0.5 text-[10px] font-medium text-violet-700">
                        % locked
                      </span>
                    )}
                  </td>
                  <td className="px-5 py-2.5">
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      className="w-28 rounded border border-gray-300 px-2 py-1"
                      // Active (RM) field shows the raw value; otherwise the value
                      // derived from the % the user locked.
                      value={b.mode === "rm" ? b.value : round2(effRm(b, S))}
                      onChange={(e) => editRm(i, Number(e.target.value))}
                    />
                  </td>
                  <td className="px-5 py-2.5">
                    <div className="flex items-center gap-1">
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        className="w-20 rounded border border-gray-300 px-2 py-1"
                        value={b.mode === "percent" ? b.value : round2(effPct(b, S))}
                        onChange={(e) => editPct(i, Number(e.target.value))}
                      />
                      <span className="text-gray-400">%</span>
                    </div>
                  </td>
                  <td className="px-5 py-2.5">
                    {b.is_default ? (
                      <span className="text-xs text-gray-400">default</span>
                    ) : (
                      <button
                        className="rounded px-2 py-1 text-red-600 hover:bg-red-50"
                        onClick={() => removeBucket(i)}
                        aria-label={`Delete ${b.label}`}
                      >
                        🗑️
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Add bucket. */}
        <div className="flex flex-wrap items-center gap-2 border-t border-gray-100 px-5 py-3">
          <input
            className="w-40 rounded border border-gray-300 px-2 py-1 text-sm"
            placeholder="New bucket (e.g. Mom)"
            value={newLabel}
            onChange={(e) => setNewLabel(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addBucket()}
          />
          <input
            type="number"
            step="0.01"
            min="0"
            className="w-28 rounded border border-gray-300 px-2 py-1 text-sm"
            placeholder="Target"
            value={newTarget}
            onChange={(e) => setNewTarget(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addBucket()}
          />
          <button
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium transition hover:bg-gray-50"
            onClick={addBucket}
          >
            + Add bucket
          </button>
        </div>
      </div>

      {/* Save / Cancel. */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          className="rounded-lg brand-gradient px-4 py-2 text-sm font-medium text-white shadow-card transition hover:opacity-90 disabled:opacity-50"
          onClick={handleSave}
          disabled={saving || exceeds || S <= 0}
        >
          {saving ? "Saving…" : "Save plan"}
        </button>
        <button
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium transition hover:bg-gray-50 disabled:opacity-50"
          onClick={handleCancel}
          disabled={saving}
        >
          Cancel
        </button>
        {notice && <span className="text-sm text-emerald-600">{notice}</span>}
        {error && <span className="text-sm text-rose-600">{error}</span>}
      </div>

      {/* ---------- Section C — This month's adherence ---------- */}
      <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-card">
        <h2 className="border-b border-gray-100 px-5 py-3 text-sm font-semibold text-gray-700">
          📊 This month&apos;s adherence
        </h2>
        {actuals.length === 0 ? (
          <p className="p-5 text-sm text-gray-400">
            No plan adherence to show yet. Save a plan to see planned-vs-actual here.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
                <tr>
                  <th className="px-5 py-2.5 font-medium">Bucket</th>
                  <th className="px-5 py-2.5 text-right font-medium">Target</th>
                  <th className="px-5 py-2.5 text-right font-medium">Actual</th>
                  <th className="px-5 py-2.5 text-right font-medium">Variance</th>
                </tr>
              </thead>
              <tbody>
                {actuals.map((a) => {
                  // Savings (leftover): beating the target is GOOD (green). Spending
                  // buckets: going over target is what to flag (red).
                  const good =
                    a.tracking_mode === "leftover" ? a.variance_rm >= 0 : a.variance_rm <= 0;
                  return (
                    <tr key={a.label} className="border-t border-gray-100">
                      <td className="px-5 py-2.5 text-gray-700">{a.label}</td>
                      <td className="px-5 py-2.5 text-right text-gray-600">{rm(a.target_rm)}</td>
                      <td className="px-5 py-2.5 text-right text-gray-600">{rm(a.actual_rm)}</td>
                      <td
                        className={`px-5 py-2.5 text-right font-medium ${
                          good ? "text-emerald-600" : "text-rose-600"
                        }`}
                      >
                        {a.variance_rm >= 0 ? "+" : ""}
                        {rm(a.variance_rm)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
