/**
 * Wallets — the Wallets tab.
 *
 * A wallet is a named virtual container whose balance is COMPUTED from its ledger
 * (tagged income/expenses + transfers), never stored. This screen lets the user:
 *   - create / rename / soft-delete wallets and see each computed balance,
 *   - resolve the "Unassigned" bucket (money not in any active wallet),
 *   - move money between wallets via the transfer form,
 *   - inspect a wallet's ledger.
 *
 * Data pattern follows BalanceCard/Dashboard: useState + useEffect load, then a
 * shared reload() after every mutation so balances + Unassigned stay live.
 */
"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getWallets,
  getUnassigned,
  createWallet,
  renameWallet,
  deleteWallet,
  createTransfer,
  getWalletLedger,
  resolveTransactionWallet,
} from "@/lib/api";
import type { IWallet, IUnassigned, ILedgerEntry } from "@/lib/types";

/** Format a number as Malaysian Ringgit, e.g. 1234.5 -> "RM 1234.50". */
function rm(n: number): string {
  return `RM ${n.toFixed(2)}`;
}

export default function Wallets() {
  const [wallets, setWallets] = useState<IWallet[]>([]);
  const [unassigned, setUnassigned] = useState<IUnassigned | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create-wallet input.
  const [newName, setNewName] = useState("");
  // Inline rename: which wallet id is being edited + its draft name.
  const [renamingId, setRenamingId] = useState<number | null>(null);
  const [renameDraft, setRenameDraft] = useState("");
  // Ledger detail: the wallet whose ledger is open + its rows.
  const [ledgerWallet, setLedgerWallet] = useState<IWallet | null>(null);
  const [ledger, setLedger] = useState<ILedgerEntry[]>([]);

  // Transfer form.
  const [fromId, setFromId] = useState<number | "">("");
  const [toId, setToId] = useState<number | "">("");
  const [transferAmount, setTransferAmount] = useState("");
  const [transferDate, setTransferDate] = useState(new Date().toISOString().slice(0, 10));
  const [transferMsg, setTransferMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    setError(null);
    try {
      const [ws, un] = await Promise.all([getWallets(), getUnassigned()]);
      setWallets(ws);
      setUnassigned(un);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load wallets");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  async function handleCreate() {
    const name = newName.trim();
    if (!name || busy) return;
    setBusy(true);
    try {
      await createWallet(name);
      setNewName("");
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create wallet");
    } finally {
      setBusy(false);
    }
  }

  async function handleRename(id: number) {
    const name = renameDraft.trim();
    if (!name) return;
    try {
      await renameWallet(id, name);
      setRenamingId(null);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not rename wallet");
    }
  }

  async function handleDelete(w: IWallet) {
    if (!confirm(`Delete wallet "${w.name}"? Its money moves to Unassigned. This can't be undone.`)) return;
    try {
      await deleteWallet(w.id);
      if (ledgerWallet?.id === w.id) setLedgerWallet(null);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not delete wallet");
    }
  }

  async function openLedger(w: IWallet) {
    setLedgerWallet(w);
    setLedger([]);
    try {
      setLedger(await getWalletLedger(w.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load ledger");
    }
  }

  async function handleTransfer() {
    setTransferMsg(null);
    if (fromId === "" || toId === "") return;
    const amount = parseFloat(transferAmount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setTransferMsg("Enter an amount greater than 0.");
      return;
    }
    if (fromId === toId) {
      setTransferMsg("Choose two different wallets.");
      return;
    }
    setBusy(true);
    try {
      await createTransfer(Number(fromId), Number(toId), amount, null, transferDate);
      setTransferAmount("");
      setTransferMsg("✅ Transfer saved.");
      await reload();
    } catch (e) {
      setTransferMsg(e instanceof Error ? e.message : "Transfer failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleResolve(rowId: number, type: "expense" | "income", walletId: number) {
    try {
      await resolveTransactionWallet(rowId, type, walletId);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not assign wallet");
    }
  }

  const transferValid =
    fromId !== "" && toId !== "" && fromId !== toId && parseFloat(transferAmount) > 0;

  if (loading) return <p className="text-sm text-gray-400">Loading wallets…</p>;

  return (
    <div className="space-y-5">
      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* ---- Create wallet ---- */}
      <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-gray-200 bg-white p-4 shadow-card">
        <span className="text-sm font-medium text-gray-600">New wallet</span>
        <input
          className="w-48 rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-200"
          placeholder="e.g. Savings, Rent, Fun"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleCreate()}
        />
        <button
          className="rounded-lg brand-gradient px-4 py-2 text-sm font-medium text-white shadow-card transition hover:opacity-90 disabled:opacity-50"
          onClick={handleCreate}
          disabled={busy || !newName.trim()}
        >
          + Create
        </button>
      </div>

      {/* ---- Wallet cards ---- */}
      {wallets.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-gray-300 bg-white p-6 text-center text-sm text-gray-400">
          No wallets yet. Create one above to start organizing your money.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {wallets.map((w) => (
            <div key={w.id} className="rounded-2xl border border-gray-200 bg-white p-4 shadow-card">
              {renamingId === w.id ? (
                <div className="flex gap-1">
                  <input
                    className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
                    value={renameDraft}
                    onChange={(e) => setRenameDraft(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleRename(w.id)}
                    autoFocus
                  />
                  <button className="rounded px-2 text-sm text-violet-700" onClick={() => handleRename(w.id)}>
                    Save
                  </button>
                  <button className="rounded px-2 text-sm text-gray-500" onClick={() => setRenamingId(null)}>
                    ✕
                  </button>
                </div>
              ) : (
                <div className="flex items-start justify-between gap-2">
                  <p className="font-semibold text-gray-800">{w.name}</p>
                  <div className="flex gap-1 text-xs">
                    <button
                      className="rounded px-1.5 py-0.5 text-gray-500 hover:bg-gray-100"
                      onClick={() => {
                        setRenamingId(w.id);
                        setRenameDraft(w.name);
                      }}
                      aria-label={`Rename ${w.name}`}
                    >
                      ✏️
                    </button>
                    <button
                      className="rounded px-1.5 py-0.5 text-red-600 hover:bg-red-50"
                      onClick={() => handleDelete(w)}
                      aria-label={`Delete ${w.name}`}
                    >
                      🗑️
                    </button>
                  </div>
                </div>
              )}
              <p className={`mt-2 text-2xl font-bold tracking-tight ${w.balance < 0 ? "text-rose-600" : "text-gray-900"}`}>
                {rm(w.balance)}
              </p>
              <button
                className="mt-2 text-xs font-medium text-violet-600 hover:underline"
                onClick={() => openLedger(w)}
              >
                View ledger →
              </button>
            </div>
          ))}
        </div>
      )}

      {/* ---- Unassigned card (only when non-zero) ---- */}
      {unassigned && Math.abs(unassigned.total) > 0.005 && (
        <div className="rounded-2xl border border-amber-300 bg-amber-50 p-4 shadow-card">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-sm font-semibold text-amber-800">🟡 Unassigned</p>
              <p className="text-xs text-amber-700">
                Money not yet in any wallet (incl. your pre-wallet balance). Assign the rows below.
              </p>
            </div>
            <p className="text-2xl font-bold text-amber-800">{rm(unassigned.total)}</p>
          </div>

          {unassigned.rows.length > 0 && (
            <div className="mt-3 overflow-x-auto rounded-xl border border-amber-200 bg-white">
              <table className="w-full text-sm">
                <thead className="bg-amber-100/50 text-left text-xs uppercase tracking-wide text-amber-800">
                  <tr>
                    <th className="px-3 py-2 font-medium">Date</th>
                    <th className="px-3 py-2 font-medium">Type</th>
                    <th className="px-3 py-2 font-medium">Description</th>
                    <th className="px-3 py-2 text-right font-medium">Amount</th>
                    <th className="px-3 py-2 font-medium">Assign to</th>
                  </tr>
                </thead>
                <tbody>
                  {unassigned.rows.map((r) => (
                    <tr key={`${r.type}-${r.id}`} className="border-t border-amber-100">
                      <td className="px-3 py-2 text-gray-600">{r.date}</td>
                      <td className="px-3 py-2 text-gray-600">{r.type}</td>
                      <td className="px-3 py-2 text-gray-700">
                        {r.description || r.category_or_source || "—"}
                      </td>
                      <td className="px-3 py-2 text-right text-gray-700">{rm(r.amount)}</td>
                      <td className="px-3 py-2">
                        <select
                          className="rounded border border-gray-300 px-2 py-1 text-sm"
                          defaultValue=""
                          disabled={wallets.length === 0}
                          onChange={(e) =>
                            e.target.value && handleResolve(r.id, r.type, Number(e.target.value))
                          }
                        >
                          <option value="" disabled>
                            {wallets.length === 0 ? "Create a wallet first" : "— Select wallet —"}
                          </option>
                          {wallets.map((w) => (
                            <option key={w.id} value={w.id}>
                              {w.name}
                            </option>
                          ))}
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ---- Transfer form ---- */}
      <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-card">
        <p className="mb-3 text-sm font-semibold text-gray-700">🔁 Move money between wallets</p>
        {wallets.length < 2 ? (
          <p className="text-sm text-gray-400">Create at least two wallets to transfer between them.</p>
        ) : (
          <div className="flex flex-wrap items-end gap-2">
            <label className="text-sm">
              <span className="mb-1 block text-xs text-gray-500">From</span>
              <select
                className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                value={fromId}
                onChange={(e) => setFromId(e.target.value ? Number(e.target.value) : "")}
              >
                <option value="">— Select —</option>
                {wallets.map((w) => (
                  <option key={w.id} value={w.id}>{w.name}</option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-xs text-gray-500">To</span>
              <select
                className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                value={toId}
                onChange={(e) => setToId(e.target.value ? Number(e.target.value) : "")}
              >
                <option value="">— Select —</option>
                {wallets.map((w) => (
                  <option key={w.id} value={w.id}>{w.name}</option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-xs text-gray-500">Amount (RM)</span>
              <input
                type="number"
                step="0.01"
                min="0"
                className="w-28 rounded-lg border border-gray-300 px-3 py-2 text-sm"
                value={transferAmount}
                onChange={(e) => setTransferAmount(e.target.value)}
              />
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-xs text-gray-500">Date</span>
              <input
                type="date"
                className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                value={transferDate}
                onChange={(e) => setTransferDate(e.target.value)}
              />
            </label>
            <button
              className="rounded-lg brand-gradient px-4 py-2 text-sm font-medium text-white shadow-card transition hover:opacity-90 disabled:opacity-50"
              onClick={handleTransfer}
              disabled={busy || !transferValid}
            >
              Transfer
            </button>
            {transferMsg && <span className="text-sm text-gray-600">{transferMsg}</span>}
          </div>
        )}
      </div>

      {/* ---- Ledger detail ---- */}
      {ledgerWallet && (
        <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-card">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-sm font-semibold text-gray-700">📜 {ledgerWallet.name} — ledger</p>
            <button className="text-sm text-gray-500 hover:underline" onClick={() => setLedgerWallet(null)}>
              Close
            </button>
          </div>
          {ledger.length === 0 ? (
            <p className="text-sm text-gray-400">No movements yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
                  <tr>
                    <th className="px-3 py-2 font-medium">Date</th>
                    <th className="px-3 py-2 font-medium">Kind</th>
                    <th className="px-3 py-2 font-medium">Description</th>
                    <th className="px-3 py-2 text-right font-medium">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {ledger.map((e, i) => (
                    <tr key={i} className="border-t border-gray-100">
                      <td className="px-3 py-2 text-gray-600">{e.date}</td>
                      <td className="px-3 py-2 text-gray-600">{e.kind.replace("_", " ")}</td>
                      <td className="px-3 py-2 text-gray-700">{e.description || "—"}</td>
                      <td
                        className={`px-3 py-2 text-right font-medium ${
                          e.signed_amount >= 0 ? "text-emerald-600" : "text-rose-600"
                        }`}
                      >
                        {e.signed_amount >= 0 ? "+" : "−"}
                        {rm(Math.abs(e.signed_amount))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
