import type { Config } from "tailwindcss";

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
      // TODO: add the ChatMoney brand palette (the old purple gradient #667eea→#764ba2)
      // e.g. colors: { brand: { from: "#667eea", to: "#764ba2" } }
    },
  },
  plugins: [],
};

export default config;
