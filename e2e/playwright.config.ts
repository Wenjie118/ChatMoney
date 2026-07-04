import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config for ChatMoney's end-to-end tests.
 *
 * The backend is MOCKED in the tests (see tests/support/mockApi.ts), so this
 * config only needs to start the Next.js frontend. No Supabase / Gemini secrets
 * are required to run these tests locally or in CI.
 *
 * Docs: https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  testDir: "./tests",
  // Fail the build on CI if you accidentally left test.only in the source.
  forbidOnly: !!process.env.CI,
  // Retry on CI only (flake insurance); no retries locally.
  retries: process.env.CI ? 2 : 0,
  // Opt out of parallel workers on CI for stability.
  workers: process.env.CI ? 1 : undefined,
  reporter: [["list"], ["html", { open: "never" }]],

  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    // Add more browsers/viewports as the suite grows, e.g.:
    // { name: "mobile-chrome", use: { ...devices["Pixel 7"] } },
  ],

  /**
   * Start the frontend before the tests and shut it down after.
   * `cwd` points at ../frontend so `npm run dev` runs the Next.js app.
   * NEXT_PUBLIC_API_URL just needs to be *defined* (frontend/lib/api.ts asserts
   * it with `!`); the value is never actually hit because page.route()
   * intercepts every backend request.
   */
  webServer: {
    command: "npm run dev",
    cwd: "../frontend",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      NEXT_PUBLIC_API_URL: "http://localhost:8000",
    },
  },
});
