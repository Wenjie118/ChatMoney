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
      <body>
        {/* TODO: add a shared app header / brand bar here (the old "💰 ChatMoney" banner). */}
        {/* TODO (later): wrap {children} in any global context providers you add. */}
        {children}
      </body>
    </html>
  );
}
