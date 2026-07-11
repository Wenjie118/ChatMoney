import { test, expect } from "@playwright/test";
import { mockBackend } from "./support/mockApi";

/**
 * Balance card flow — a fuller example showing how to assert on mocked data and
 * drive a write (PUT /balance). BalanceCard lives inside the Dashboard view
 * (frontend/components/Dashboard.tsx renders <BalanceCard/>), so we open
 * Dashboard first.
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

  test("updating the balance reflects the new value", async ({ page }) => {
    await page.getByRole("button", { name: "Update balance" }).click();

    await page.getByPlaceholder("e.g. 5000").fill("1234.5");
    await page.getByRole("button", { name: "Save" }).click();

    // The mock echoes the submitted amount back, so the card shows RM 1234.50.
    await expect(page.getByText("RM 1234.50")).toBeVisible();
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
