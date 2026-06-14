/**
 * Route "/chat" — a dedicated page for the chat interface.
 *
 * Exists so you can deep-link to the chat (and as an alternative to the in-memory
 * tabs in app/page.tsx). It simply renders the ChatInterface component.
 */
import ChatInterface from "@/components/ChatInterface";

export default function ChatPage() {
  return (
    <main className="mx-auto max-w-4xl p-4">
      {/* TODO: optional page heading / breadcrumb */}
      <ChatInterface />
    </main>
  );
}
