import { readFile } from "node:fs/promises";

import { expect, test } from "@playwright/test";

/**
 * PDF statements (F13). Needs a signed-in person whose household has records and who has
 * given the Zakat consent: set E2E_DEMO_EMAIL and E2E_DEMO_PASSWORD (the demo seed creates
 * demo@example.com).
 */
test("a Zakat calculation downloads as a PDF in the page language (F13)", async ({ page }) => {
  const email = process.env.E2E_DEMO_EMAIL;
  const password = process.env.E2E_DEMO_PASSWORD;
  test.skip(!email || !password, "Set E2E_DEMO_EMAIL and E2E_DEMO_PASSWORD to run this test.");

  await page.goto("/en/signin");
  await page.getByLabel("Email").fill(email ?? "");
  await page.getByLabel("Password").fill(password ?? "");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();

  await page.goto("/en/personal/zakat");
  await page.getByRole("button", { name: "Calculate" }).click();
  await expect(page).toHaveURL(/\/en\/personal\/zakat\/[0-9a-f-]{36}$/);

  for (const locale of ["en", "bn"] as const) {
    if (locale === "bn") await page.goto(page.url().replace("/en/", "/bn/"));
    const link = page.getByRole("link", { name: locale === "en" ? "Download PDF" : "PDF ডাউনলোড করুন" });
    const [download] = await Promise.all([page.waitForEvent("download"), link.click()]);
    expect(download.suggestedFilename()).toMatch(new RegExp(`^analysisace-zakat-.*-${locale}\\.pdf$`));
    const path = await download.path();
    const head = (await readFile(path)).subarray(0, 4).toString();
    expect(head).toBe("%PDF");
  }
});
