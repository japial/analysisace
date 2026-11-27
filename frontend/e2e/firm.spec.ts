import { readFile } from "node:fs/promises";

import { expect, type Page, test } from "@playwright/test";

/**
 * Firm features (F9, D30). Needs the API started with FIRM_FEATURES_ENABLED=true and a firm
 * admin: set E2E_FIRM_EMAIL and E2E_FIRM_PASSWORD (the demo seed creates firm@example.com,
 * admin of "Demo Brokerage Ltd."). Without them these tests are skipped.
 */
const FIRM_EMAIL = process.env.E2E_FIRM_EMAIL;
const FIRM_PASSWORD = process.env.E2E_FIRM_PASSWORD;

async function signIn(page: Page): Promise<void> {
  await page.goto("/en/signin");
  await page.getByLabel("Email").fill(FIRM_EMAIL ?? "");
  await page.getByLabel("Password").fill(FIRM_PASSWORD ?? "");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
}

test.beforeEach(() => {
  test.skip(!FIRM_EMAIL || !FIRM_PASSWORD, "Set E2E_FIRM_EMAIL and E2E_FIRM_PASSWORD");
});

test("a firm admin reaches the firm page, exports data and creates an API key (FR9.2, FR9.3)", async ({ page }) => {
  await signIn(page);
  await page.goto("/en/firm");
  await expect(page.getByRole("heading", { level: 1, name: "Demo Brokerage Ltd." })).toBeVisible();
  await expect(page.getByText("Historical analysis for education only. Not investment advice.").first()).toBeVisible();

  // CSV export downloads with its disclaimer line.
  const [csv] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: "Shariah screen (CSV)" }).click(),
  ]);
  const text = await readFile((await csv.path()) ?? "", "utf-8");
  expect(text.split("\n")[0]).toBe("ticker,name,sector,status,method_version,screened_at,market_cap");
  expect(text).toContain("# Historical analysis for education only. Not investment advice.");

  // A new key is shown once.
  await page.getByLabel("Key name").fill(`E2E ${Date.now()}`);
  await page.getByRole("button", { name: "Create key" }).click();
  await expect(page.getByText("Copy this key now. It will not be shown again")).toBeVisible();
  // The full key, not the short prefixes in the list above it.
  await expect(page.getByText(/^aace_[\w-]{30,}$/)).toBeVisible();
});

test("the firm menu item and page work at phone width (FR9.1)", async ({ page }) => {
  await signIn(page);
  await page.goto("/en/firm");
  await expect(page.getByRole("heading", { name: "White-label weekly report" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Members" })).toBeVisible();
  const width = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(width).toBeLessThanOrEqual(0);
});

test("a platform admin sees the firms screen (FR9.3)", async ({ page }) => {
  const email = process.env.E2E_ADMIN_EMAIL;
  const password = process.env.E2E_ADMIN_PASSWORD;
  test.skip(!email || !password, "Set E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD");
  await page.goto("/en/signin");
  await page.getByLabel("Email").fill(email ?? "");
  await page.getByLabel("Password").fill(password ?? "");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  await page.goto("/en/admin");
  await page.getByRole("link", { name: "Firms" }).click();
  await expect(page.getByRole("heading", { name: "All firms" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Demo Brokerage Ltd.", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "New firm" })).toBeVisible();
});
