import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

/**
 * Accessibility (PRD section 12, D36): every main page is scanned with axe-core for WCAG
 * 2.1 A and AA problems, in English and Bangla, on a desktop and at 360 px (the two
 * projects in playwright.config.ts), and again in the dark theme, whose colours are checked
 * for contrast separately. Any violation fails the test, listed with the rule, how serious
 * it is and the elements that break it.
 */
const PASSWORD = "e2e-password-123";

const PUBLIC = ["/", "/signin", "/signup", "/forgot-password", "/companies", "/shariah", "/macro", "/rates", "/regime", "/events", "/unsubscribe"];
const SIGNED_IN = [
  "/personal",
  "/personal/income",
  "/personal/costs",
  "/personal/portfolio",
  "/personal/assets",
  "/personal/zakat",
  "/personal/fire",
  "/personal/goals",
  "/personal/alerts",
  "/personal/household",
  "/account",
];

async function scan(page: Page, path: string): Promise<string[]> {
  await page.goto(path);
  await page.waitForLoadState("networkidle");
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  return results.violations.map(
    (v) =>
      `${path}: ${v.id} (${v.impact}) ${v.help}\n` +
      v.nodes
        .slice(0, 5)
        .map((n) => `    ${n.target.join(" ")}`)
        .join("\n"),
  );
}

for (const locale of ["en", "bn"] as const) {
  test(`public pages have no accessibility violations (${locale})`, async ({ page }) => {
    test.setTimeout(120_000);
    const problems: string[] = [];
    for (const path of PUBLIC) problems.push(...(await scan(page, `/${locale}${path === "/" ? "" : path}`)));
    expect(problems, problems.join("\n")).toEqual([]);
  });
}

async function signUpWithHousehold(page: Page): Promise<void> {
  const email = `e2e-a11y-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  await page.goto("/en/signup");
  await page.getByLabel("Full name").fill("Access Tester");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  await page.goto("/en/personal");
  await page.getByLabel("Household name").fill("Access family");
  await page.getByRole("button", { name: "Create household" }).click();
  await expect(page.getByText("Access family · Owner")).toBeVisible();
}

test("signed-in pages have no accessibility violations", async ({ page }) => {
  test.setTimeout(180_000);
  await signUpWithHousehold(page);
  const problems: string[] = [];
  for (const path of SIGNED_IN) {
    problems.push(...(await scan(page, `/en${path}`)));
    problems.push(...(await scan(page, `/bn${path}`)));
  }
  expect(problems, problems.join("\n")).toEqual([]);
});

test.describe("dark theme", () => {
  // The theme follows the system setting until the person picks one.
  test.use({ colorScheme: "dark" });

  test("pages have no accessibility violations in the dark theme", async ({ page }) => {
    test.setTimeout(180_000);
    const problems: string[] = [];
    for (const path of PUBLIC) problems.push(...(await scan(page, `/en${path === "/" ? "" : path}`)));
    await signUpWithHousehold(page);
    await expect(page.locator("html.dark")).toHaveCount(1);
    for (const path of SIGNED_IN) problems.push(...(await scan(page, `/en${path}`)));
    expect(problems, problems.join("\n")).toEqual([]);
  });
});
