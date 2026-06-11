/**
 * Home page (route "/") — the tabbed shell that swaps between Chat and Dashboard.
 *
 * "use client" is required because we use useState (interactivity). Pages that
 * only render static markup can stay server components, but this one holds tab state.
 *
 * NOTE: this mirrors the old Streamlit st.tabs(). Alternatively you could use real
 * routes (/chat, /dashboard — those page files exist as stubs) and a <nav> with
 * <Link>s instead of in-memory tab state. Pick whichever you prefer; this stub
 * shows the single-page tab approach.
 */
"use client";

import { useState } from "react";
import ChatInterface from "@/components/ChatInterface";
import Dashboard from "@/components/Dashboard";

type Tab = "chat" | "dashboard";

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>("chat");

  return (
    <main className="mx-auto max-w-4xl p-4">
      {/* TODO: style this tab bar (active state, spacing). The old app used
          "💬 Chat" and "📊 Dashboard" labels. */}
      <nav className="flex gap-2 border-b mb-4">
        <button onClick={() => setActiveTab("chat")}>💬 Chat</button>
        <button onClick={() => setActiveTab("dashboard")}>📊 Dashboard</button>
      </nav>

      {/* Render the active tab's component. */}
      {activeTab === "chat" ? <ChatInterface /> : <Dashboard />}
    </main>
  );
}
