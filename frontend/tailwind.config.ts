import type { Config } from "tailwindcss";
import typography from "@tailwindcss/typography";

/**
 * Tailwind config. `content` tells Tailwind which files to scan for class names
 * so it can tree-shake unused styles. Make sure every folder containing JSX is
 * listed here, or your classes won't generate.
 */
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // The ChatMoney brand purple→indigo gradient stops, reusable as
        // bg-brand-from / to-brand-to etc.
        brand: { from: "#7c3aed", to: "#4f46e5" },
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(0 0 0 / 0.04), 0 1px 3px 0 rgb(0 0 0 / 0.06)",
      },
    },
  },
  // The typography plugin gives us the `prose` classes used to render the
  // advisor's Markdown (headings, bold, lists) with nice spacing.
  plugins: [typography],
};

export default config;
