import { expect, test } from "@playwright/test";

/**
 * Market layer (F1 to F8) end to end. Needs the database, API and web app running, with
 * market data loaded and the analytics run (the demo seed does both).
 *
 * The analyst test needs a user with DATA_REVIEW and CONTENT_PUBLISH: set
 * E2E_ANALYST_EMAIL and E2E_ANALYST_PASSWORD (the demo seed creates analyst@example.com).
 */
const DISCLAIMER = "Historical analysis for education only. Not investment advice.";

const PAGES = [
  ["/en/shariah", "Shariah list"],
  ["/en/rates", "Interest rates and rate sensitivity"],
  ["/en/events", "Shock playbook"],
  ["/en/macro", "Weekly macro notes"],
  ["/en/regime", "Macro regime"],
] as const;

test("every market page opens with the disclaimer and no load error", async ({ page }) => {
  for (const [path, heading] of PAGES) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
    await expect(page.getByRole("note").getByText(DISCLAIMER)).toBeVisible();
    await expect(page.getByText("could not be reached")).toHaveCount(0);
    await expect(page.getByText("could not be loaded")).toHaveCount(0);
  }
});

test("the Shariah list links to a company's screen with every rule shown (FR1.2, FR2.1)", async ({ page }) => {
  await page.goto("/en/shariah");
  const firstCompany = page.getByRole("table").getByRole("link").first();
  const ticker = (await firstCompany.textContent())?.trim() ?? "";
  await firstCompany.click();
  await expect(page).toHaveURL(new RegExp(`/en/companies/${ticker}$`));
  await expect(page.getByText("Shariah screen", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Last screened").first()).toBeVisible();
  await expect(page.getByText("Rate sensitivity", { exact: true })).toBeVisible();
});

test("an event shows how the market moved after it (FR5.2)", async ({ page }) => {
  await page.goto("/en/events");
  await page.getByRole("link", { name: "Open" }).first().click();
  await expect(page.getByText("Market (DSEX)")).toBeVisible();
  await expect(page.getByText("After 1 session").first()).toBeVisible();
  await expect(page.getByText("Similar events")).toBeVisible();
});

test("Bangla pages use Bangla labels", async ({ page }) => {
  await page.goto("/bn/regime");
  await expect(page.getByRole("heading", { level: 1, name: "সামষ্টিক অর্থনৈতিক পরিস্থিতি" })).toBeVisible();
});

test("an analyst writes and publishes the weekly note (FR4)", async ({ page }) => {
  const email = process.env.E2E_ANALYST_EMAIL;
  const password = process.env.E2E_ANALYST_PASSWORD;
  test.skip(!email || !password, "Set E2E_ANALYST_EMAIL and E2E_ANALYST_PASSWORD to run this test.");

  await page.goto("/en/signin");
  await page.getByLabel("Email").fill(email ?? "");
  await page.getByLabel("Password").fill(password ?? "");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();

  await page.goto("/en/admin");
  const main = page.locator("#main");
  await expect(main.getByRole("link", { name: "Macro notes" })).toBeVisible();
  await expect(main.getByRole("link", { name: "Users" })).toHaveCount(0);

  await page.goto("/en/admin/notes");
  await page.getByRole("button", { name: "Write draft" }).first().click();
  await expect(page.getByText("Saved.").first()).toBeVisible();
  // The innermost block holding both the English label and a Publish button is that note's header.
  const englishHeader = page
    .locator("div")
    .filter({ has: page.getByText(/^English ·/) })
    .filter({ has: page.getByRole("button", { name: "Publish", exact: true }) })
    .last();
  if (await englishHeader.count()) {
    await englishHeader.getByRole("button", { name: "Publish", exact: true }).click();
    await expect(page.getByRole("button", { name: "Unpublish" }).first()).toBeVisible();
  }
  await page.goto("/en/macro");
  await expect(page.getByText("Figures this week")).toBeVisible();

  await page.goto("/en/admin/data");
  await expect(page.getByText("Review queue")).toBeVisible();
});
