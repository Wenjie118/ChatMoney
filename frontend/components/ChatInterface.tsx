/**
 * ChatInterface — the Chat tab (replaces the old Streamlit chat + PDF uploader).
 *
 * Responsibilities:
 *   - text input to log a transaction in natural language
 *   - PDF upload to import a bank statement
 *   - render the running message list
 *   - show a loading state while the backend works
 *
 * Everything below is a stub. Build it incrementally using the api.ts functions.
 */
"use client";

import { useState } from "react";
// import { parseTransaction, parsePDF } from "@/lib/api";
// import type { ITransaction } from "@/lib/types";
// import TransactionPreview from "./TransactionPreview";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function ChatInterface() {
  // TODO: state for the message list
  const [messages, setMessages] = useState<Message[]>([]);
  // TODO: state for the text input value
  // TODO: state for `loading` (true while an API call is in flight)
  // TODO: state for the parsed-PDF rows to feed into <TransactionPreview />

  // TODO: handleSendText()
  //   1. push the user's message into `messages`
  //   2. setLoading(true)
  //   3. const parsed = await parseTransaction(text)
  //   4. push an assistant confirmation message
  //   5. catch errors -> push an error message
  //   6. finally setLoading(false)

  // TODO: handleUploadPdf(file: File)
  //   1. setLoading(true)
  //   2. const rows = await parsePDF(file)
  //   3. store rows in state and render <TransactionPreview rows={rows} />
  //   4. catch errors; finally setLoading(false)

  return (
    <div>
      {/* TODO: render messages.map(...) as chat bubbles */}
      {/* TODO: when loading, show a spinner */}
      {/* TODO: <TransactionPreview /> once a PDF has been parsed */}

      {/* TODO: file input -> onChange calls handleUploadPdf(e.target.files[0]) */}
      {/* TODO: text input + send button -> onClick calls handleSendText() */}
      <p className="text-gray-400">TODO: build the chat UI</p>
    </div>
  );
}
