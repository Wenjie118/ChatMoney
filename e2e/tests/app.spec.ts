import { test, expect } from "@playwright/test";
import { mockBackend } from "./support/mockApi";

/**
 * Smoke test for the app shell: the sidebar loads and switching nav items swaps
 * the active view. This is the simplest end-to-end proof that the frontend boots
 * and renders against the mocked backend.
 *
 * UI reference: frontend/app/page.tsx (the NAV array + sticky <h1> title).
 */
test.describe("App shell", () => {
  test.beforeEach(async ({ page }) => {
    await mockBackend(page);
  });

  test("loads with the Chat view and the ChatMoney brand", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByText("ChatMoney").first()).toBeVisible();
    // The sidebar has all three nav items.
    await expect(page.getByRole("button", { name: "Chat" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Dashboard" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Advisor" })).toBeVisible();

    // Chat is the default view — its top-bar title is shown.
    await expect(page.getByRole("heading", { name: /Chat/ })).toBeVisible();
  });

  test("switches views when a nav item is clicked", async ({ page }) => {
    await page.goto("/");

    await page.getByRole("button", { name: "Dashboard" }).click();
    await expect(page.getByRole("heading", { name: /Dashboard/ })).toBeVisible();

    await page.getByRole("button", { name: "Advisor" }).click();
    await expect(page.getByRole("heading", { name: /Advisor/ })).toBeVisible();
  });
});
