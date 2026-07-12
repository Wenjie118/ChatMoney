/**
 * ChatInterface — the Chat tab (Slice 1: text only).
 *
 * Flow: user types -> handleSend() -> api.parseTransaction() -> backend parses &
 * saves -> we show a confirmation bubble. State pattern mirrors BalanceCard.tsx
 * (data + loading + error), adapted for an on-submit action instead of on-mount.
 *
 * (PDF upload + <TransactionPreview> come later in Slice 4.)
 */
"use client";

import { useState } from "react";
import { parseTransaction, parsePDF } from "@/lib/api";
import type { ITransaction } from "@/lib/types";
import TransactionPreview, { blankRow } from "./TransactionPreview";
import { useBusy } from "@/lib/busy";

interface Message {
  role: "user" | "assistant";
  content: string;
}

/** Turn a saved transaction into a friendly confirmation line. */
function formatSaved(t: ITransaction): string {
  if (t.type === "income") {
    return `✅ Saved Income: RM${t.amount} from ${t.category_or_source}`;
  }
  return `✅ Saved Expense: RM${t.amount} on ${t.category_or_source}`;
}

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  // PDF import (Slice 4): the parsed rows awaiting review.
  const [pdfRows, setPdfRows] = useState<ITransaction[] | null>(null);
  // Manual entry: rows for the editable table when adding transactions by hand
  // (no PDF, no LLM). `null` = the table is closed. Reuses TransactionPreview and
  // the same /transactions/save-multiple endpoint as the PDF flow.
  const [manualRows, setManualRows] = useState<ITransaction[] | null>(null);
  // Global busy overlay — freezes the WHOLE app while the PDF is being parsed.
  const { setBusy } = useBusy();

  /** Open the manual-entry table (seeded with one blank row) or close it. */
  function toggleManual() {
    setManualRows((prev) => (prev ? null : [blankRow()]));
  }

  /** Runs when the user picks a PDF file. Parses it, then shows the preview table. */
  async function handlePdf(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setPdfRows(null);
    setBusy("📄 Reading your statement…\nThis can take a moment — please wait.");
    try {
      const rows = await parsePDF(file);
      setPdfRows(rows);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Could not read that PDF";
      setMessages((prev) => [...prev, { role: "assistant", content: `⚠️ ${msg}` }]);
    } finally {
      setBusy(null); // unfreeze the app
      // Reset the input so picking the SAME file again still fires onChange.
      e.target.value = "";
    }
  }

  async function handleSend() {
    const text = input.trim();
    if (!text || loading) return;

    // 1. show the user's message immediately and clear the box
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setLoading(true);

    // 2. call the API, then push an assistant reply (or an error)
    try {
      const saved = await parseTransaction(text);
      const reply =
        saved.length > 0
          ? saved.map(formatSaved).join("\n")
          : "⚠️ I couldn't find any transactions in that message. Try 'Spent RM50 on groceries'.";
      setMessages((prev) => [...prev, { role: "assistant", content: reply }]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Something went wrong";
      setMessages((prev) => [...prev, { role: "assistant", content: `⚠️ ${msg}` }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      {/* message list */}
      <div className="flex min-h-[340px] flex-col gap-3 rounded-2xl border border-gray-200 bg-white p-4 shadow-card">
        {messages.length === 0 && (
          <div className="m-auto max-w-sm text-center text-gray-400">
            <p className="text-3xl">👋</p>
            <p className="mt-2 text-sm">
              Tell me about a transaction — try{" "}
              <span className="font-medium text-gray-600">&quot;spent RM50 on coffee&quot;</span>{" "}
              or{" "}
              <span className="font-medium text-gray-600">&quot;earned RM5000 salary&quot;</span>.
            </p>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
            <span
              className={`inline-block max-w-[80%] whitespace-pre-line rounded-2xl px-4 py-2.5 text-sm shadow-sm ${
                m.role === "user"
                  ? "brand-gradient rounded-br-sm text-white"
                  : "rounded-bl-sm bg-gray-100 text-gray-800"
              }`}
            >
              {m.content}
            </span>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <span className="inline-flex items-center gap-2 rounded-2xl bg-gray-100 px-4 py-2.5 text-sm text-gray-500">
              <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400" />
              Saving…
            </span>
          </div>
        )}
      </div>

      {/* input row */}
      <div className="flex gap-2">
        <input
          className="flex-1 rounded-xl border border-gray-300 bg-white px-4 py-2.5 text-sm shadow-sm outline-none transition focus:border-violet-500 focus:ring-2 focus:ring-violet-200"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSend();
          }}
          placeholder="e.g. Spent RM50 on groceries"
          disabled={loading}
        />
        <button
          className="rounded-xl brand-gradient px-5 py-2.5 text-sm font-medium text-white shadow-card transition hover:opacity-90 disabled:opacity-50"
          onClick={handleSend}
          disabled={loading}
        >
          Send
        </button>
      </div>

      {/* PDF import (Slice 4): upload a bank statement -> review table -> save. */}
      <div className="space-y-3 rounded-2xl border border-dashed border-gray-300 bg-white p-5">
        <label className="block text-sm font-medium text-gray-700">
          📄 Or import a bank statement (PDF)
        </label>
        <input
          type="file"
          accept="application/pdf"
          onChange={handlePdf}
          className="block w-full text-sm text-gray-500 file:mr-3 file:rounded-lg file:border-0 file:bg-violet-50 file:px-4 file:py-2 file:text-sm file:font-medium file:text-violet-700 hover:file:bg-violet-100"
        />

        {/* Once parsed, show the editable preview. `key` forces a fresh table when
            a new file is parsed; onSaved clears it after a successful save. */}
        {pdfRows && (
          <TransactionPreview
            key={pdfRows.length + "-" + (pdfRows[0]?.date ?? "")}
            initialRows={pdfRows}
            onSaved={() => setPdfRows(null)}
          />
        )}
      </div>

      {/* Manual entry: add transactions straight into the editable table — no PDF,
          no LLM. Same table + same save endpoint as the PDF flow. */}
      <div className="space-y-3 rounded-2xl border border-dashed border-gray-300 bg-white p-5">
        <div className="flex items-center justify-between gap-2">
          <label className="block text-sm font-medium text-gray-700">
            ✏️ Or add transactions manually
          </label>
          <button
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium transition hover:bg-gray-50"
            onClick={toggleManual}
          >
            {manualRows ? "Close" : "➕ Add transactions manually"}
          </button>
        </div>

        {/* Mount/unmount gives a fresh blank row each time it's opened. On save we
            drop a confirmation into the chat (the table's own message unmounts with
            it) and close the table. */}
        {manualRows && (
          <TransactionPreview
            initialRows={manualRows}
            showCount={false}
            title="✏️ Enter transactions"
            helpText="Add a row for each transaction, edit the cells, then save. No file needed."
            onSaved={(result) => {
              setMessages((prev) => [
                ...prev,
                {
                  role: "assistant",
                  content: `✅ Saved ${result.saved} of ${result.total} transactions.`,
                },
              ]);
              setManualRows(null);
            }}
          />
        )}
      </div>
    </div>
  );
}
