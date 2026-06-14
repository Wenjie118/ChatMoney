/**
 * Busy overlay — a tiny global "the app is working, please wait" state.
 *
 * WHY A CONTEXT: the PDF parse happens inside ChatInterface, but we want the
 * WHOLE app frozen while it runs (including the sidebar/top bar). Rather than
 * thread a callback through every component, we expose a shared `setBusy` via
 * React Context. Any component can call it; the provider renders a full-screen
 * blocking overlay that sits above everything (z-50) and swallows all clicks —
 * so no other action is possible until it clears.
 */
"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

interface BusyContextValue {
  /** A message to show, or null when the app is idle. */
  busy: string | null;
  /** Set a message to freeze the app; pass null to unfreeze. */
  setBusy: (message: string | null) => void;
}

const BusyContext = createContext<BusyContextValue | null>(null);

export function BusyProvider({ children }: { children: ReactNode }) {
  const [busy, setBusy] = useState<string | null>(null);

  return (
    <BusyContext.Provider value={{ busy, setBusy }}>
      {children}

      {/* The blocking overlay. `fixed inset-0` covers the viewport; because it's
          on top, it intercepts every click/tap, freezing the UI beneath it. */}
      {busy && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
          aria-live="assertive"
          aria-busy="true"
        >
          <div className="flex flex-col items-center gap-4 rounded-2xl bg-white px-10 py-8 shadow-xl">
            <span className="h-10 w-10 animate-spin rounded-full border-4 border-violet-500 border-t-transparent" />
            <p className="max-w-xs whitespace-pre-line text-center text-sm font-medium text-gray-700">{busy}</p>
          </div>
        </div>
      )}
    </BusyContext.Provider>
  );
}

/** Hook to read/set the global busy state.
 *
 * Falls back to a harmless no-op when there's NO provider above it — e.g. the
 * standalone /chat route renders <ChatInterface /> outside the app shell. The
 * real app (the "/" sidebar shell) always has the provider, so the freeze
 * overlay works there; on the orphan route nothing freezes, which is fine. */
export function useBusy(): BusyContextValue {
  const ctx = useContext(BusyContext);
  return ctx ?? { busy: null, setBusy: () => {} };
}
