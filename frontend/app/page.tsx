/**
 * Home page (route "/") — the APP SHELL: a persistent sidebar + sticky top bar
 * wrapped around the active view. Navigation is in-memory state (not routes), so
 * switching views never reloads the page — it feels like a single-page app.
 *
 * "use client" is required because we hold the active-view state with useState.
 */
"use client";

import { useState } from "react";
import ChatInterface from "@/components/ChatInterface";
import Dashboard from "@/components/Dashboard";
import Advisor from "@/components/Advisor";
import { BusyProvider } from "@/lib/busy";

type View = "chat" | "dashboard" | "advisor";

/** The navigation items, shared by the desktop sidebar and the mobile drawer. */
const NAV: { id: View; label: string; icon: string; subtitle: string }[] = [
  { id: "chat", label: "Chat", icon: "💬", subtitle: "Log expenses & import statements" },
  { id: "dashboard", label: "Dashboard", icon: "📊", subtitle: "Your monthly overview" },
  { id: "advisor", label: "Advisor", icon: "🤖", subtitle: "AI-powered financial advice" },
];

export default function Home() {
  const [view, setView] = useState<View>("chat");
  const [mobileOpen, setMobileOpen] = useState(false); // mobile drawer toggle
  const current = NAV.find((n) => n.id === view)!;

  /** A single nav button (reused in both the sidebar and the mobile drawer). */
  function NavButton({ item }: { item: (typeof NAV)[number] }) {
    const active = view === item.id;
    return (
      <button
        onClick={() => {
          setView(item.id);
          setMobileOpen(false);
        }}
        className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
          active
            ? "brand-gradient text-white shadow-card"
            : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
        }`}
      >
        <span className="text-lg">{item.icon}</span>
        <span>{item.label}</span>
      </button>
    );
  }

  /** The sidebar's inner content (brand + nav). Shared by desktop + drawer. */
  const sidebarBody = (
    <>
      <div className="flex items-center gap-3 border-b border-gray-200 px-5 py-4">
        <span className="brand-gradient grid h-9 w-9 place-items-center rounded-lg text-lg">
          💰
        </span>
        <div>
          <p className="text-sm font-bold leading-tight">ChatMoney</p>
          <p className="text-xs text-gray-400">Finance assistant</p>
        </div>
      </div>
      <nav className="flex-1 space-y-1 p-3">
        {NAV.map((item) => (
          <NavButton key={item.id} item={item} />
        ))}
      </nav>
      <div className="border-t border-gray-200 p-4 text-xs text-gray-400">v1.0 · Local</div>
    </>
  );

  return (
    <BusyProvider>
    <div className="flex min-h-screen">
      {/* Sidebar — desktop only (md+). */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-gray-200 bg-white md:flex">
        {sidebarBody}
      </aside>

      {/* Main column. */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Sticky top bar showing the current view's title. */}
        <header className="sticky top-0 z-10 flex items-center gap-3 border-b border-gray-200 bg-white/80 px-4 py-3 backdrop-blur md:px-8">
          <button
            className="rounded-lg p-2 text-lg hover:bg-gray-100 md:hidden"
            onClick={() => setMobileOpen(true)}
            aria-label="Open menu"
          >
            ☰
          </button>
          <div>
            <h1 className="flex items-center gap-2 text-base font-semibold">
              <span>{current.icon}</span>
              {current.label}
            </h1>
            <p className="text-xs text-gray-400">{current.subtitle}</p>
          </div>
        </header>

        {/* Active view. */}
        <main className="mx-auto w-full max-w-5xl flex-1 p-4 md:p-8">
          {view === "chat" && <ChatInterface />}
          {view === "dashboard" && <Dashboard />}
          {view === "advisor" && <Advisor />}
        </main>
      </div>

      {/* Mobile drawer — an overlay sidebar shown when the ☰ button is tapped. */}
      {mobileOpen && (
        <div className="fixed inset-0 z-20 md:hidden">
          {/* Dimmed backdrop; tapping it closes the drawer. */}
          <div
            className="absolute inset-0 bg-black/30"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="absolute left-0 top-0 flex h-full w-64 flex-col bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4">
              <span className="font-bold">💰 ChatMoney</span>
              <button
                className="rounded-lg p-1 text-gray-500 hover:bg-gray-100"
                onClick={() => setMobileOpen(false)}
                aria-label="Close menu"
              >
                ✕
              </button>
            </div>
            <nav className="flex-1 space-y-1 p-3">
              {NAV.map((item) => (
                <NavButton key={item.id} item={item} />
              ))}
            </nav>
          </aside>
        </div>
      )}
    </div>
    </BusyProvider>
  );
}
