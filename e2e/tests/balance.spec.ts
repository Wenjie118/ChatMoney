import { test, expect } from "@playwright/test";
import { mockBackend } from "./support/mockApi";

/**
 * Balance card flow — asserts the read-only balance display and its error state.
 * BalanceCard lives inside the Dashboard view (frontend/components/Dashboard.tsx
 * renders <BalanceCard/>), so we open Dashboard first. The balance is now managed
 * via the Wallets tab (this card no longer has an "Update balance" control).
 *
 * UI reference: frontend/components/BalanceCard.tsx.
 */
test.describe("Balance card", () => {
  test.beforeEach(async ({ page }) => {
    await mockBackend(page);
    await page.goto("/");
    await page.getByRole("button", { name: "Dashboard" }).click();
  });

  test("shows the current balance from GET /balance", async ({ page }) => {
    await expect(page.getByText("Current Balance")).toBeVisible();
    // The RM value sits in the <p> right after the "Current Balance" label.
    // Scope to it so we don't collide with the same amount elsewhere on the
    // dashboard (metric card / table row). DEFAULT_BALANCE = 5000 -> "RM 5000.00".
    const balanceValue = page
      .getByText("Current Balance")
      .locator("xpath=following-sibling::p[1]");
    await expect(balanceValue).toHaveText("RM 5000.00");
  });

  test("has no balance-editing control (managed via Wallets now)", async ({ page }) => {
    await expect(page.getByRole("button", { name: "Update balance" })).toHaveCount(0);
  });

  test("surfaces an error when the balance endpoint fails", async ({ page }) => {
    // Re-mock with a failing GET /balance for this test only.
    await mockBackend(page, {
      "GET /balance": { status: 503, json: { detail: "Database unavailable" } },
    });
    await page.goto("/");
    await page.getByRole("button", { name: "Dashboard" }).click();

    await expect(page.getByText(/Database unavailable/)).toBeVisible();
  });
});
