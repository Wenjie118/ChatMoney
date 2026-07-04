import { test, expect } from "@playwright/test";
import { mockBackend } from "./support/mockApi";

/**
 * BLUEPRINT / TEMPLATE — copy these into real specs as you build out coverage.
 *
 * These are marked `test.skip` so CI stays green while they're just scaffolding.
 * Each one shows the pattern for a key user flow: mock the backend, drive the UI,
 * assert on the result. Remove `.skip` (and adjust the assertions) to activate.
 *
 * UI references:
 *   - Chat:      frontend/components/ChatInterface.tsx
 *   - Dashboard: frontend/components/Dashboard.tsx
 *   - Advisor:   frontend/components/Advisor.tsx
 */
test.describe("User flows (blueprint)", () => {
  test.beforeEach(async ({ page }) => {
    await mockBackend(page);
    await page.goto("/");
  });

  // Chat: type an expense -> Send -> confirmation bubble from POST /transactions/parse.
  test.skip("logs an expense from the chat box", async ({ page }) => {
    await page.getByPlaceholder("e.g. Spent RM50 on groceries").fill("Spent RM50 on groceries");
    await page.getByRole("button", { name: "Send" }).click();

    // The mock's parse response is a RM50 Groceries expense; ChatInterface
    // formats it as "✅ Saved Expense: RM50 on Groceries".
    await expect(page.getByText(/Saved Expense: RM50 on Groceries/)).toBeVisible();
  });

  // Dashboard: metric cards + recent table populate from summary/recent mocks.
  test.skip("dashboard renders metrics and the transactions table", async ({ page }) => {
    await page.getByRole("button", { name: "Dashboard" }).click();

    await expect(page.getByText("Total Income")).toBeVisible();
    await expect(page.getByText("RM 5000.00")).toBeVisible(); // total_income
    await expect(page.getByText("Groceries")).toBeVisible(); // a row from /recent
  });

  // Advisor: pick a period -> Get advice -> markdown from POST /advisor/advice.
  test.skip("advisor renders AI advice markdown", async ({ page }) => {
    await page.getByRole("button", { name: "Advisor" }).click();
    // TODO: select a period, click the "Get advice" button, then assert the
    // rendered markdown heading from DEFAULT_ADVICE is visible.
    await expect(page.getByText(/Your Financial Snapshot/)).toBeVisible();
  });
});
