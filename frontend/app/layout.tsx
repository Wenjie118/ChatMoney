/**
 * Root layout — wraps EVERY page in the app.
 *
 * In the Next.js App Router, this file is required. Whatever you render here
 * (header, fonts, providers) appears on all routes. `children` is the active page.
 */
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ChatMoney",
  description: "Your AI-powered personal finance assistant",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      {/* The app shell (sidebar + top bar) lives in app/page.tsx so navigation
          state can be shared. The layout just sets global chrome + background. */}
      <body>{children}</body>
    </html>
  );
}
