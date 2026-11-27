import { expect, type Page, test } from "@playwright/test";

/**
 * Personal finance ("My money", F12 to F26) end to end, as a new user with an empty
 * household. Needs the database, API and web app running (see playwright.config.ts).
 */
const PASSWORD = "e2e-password-123";

const SECTIONS = [
  ["/en/personal", "My money"],
  ["/en/personal/income", "Income"],
  ["/en/personal/costs", "Costs"],
  ["/en/personal/portfolio", "Accounts and holdings"],
  ["/en/personal/assets", "Property and other assets"],
  ["/en/personal/sukuk", "Sukuk and Islamic banking"],
  ["/en/personal/performance", "Performance"],
  ["/en/personal/allocation", "Allocation"],
  ["/en/personal/market-check", "Market check"],
  ["/en/personal/zakat", "Zakat"],
  ["/en/personal/tax", "Tax statement"],
  ["/en/personal/fire", "FIRE plan"],
  ["/en/personal/goals", "Goals"],
  ["/en/personal/alerts", "Alerts"],
  ["/en/personal/community", "Compare with peers"],
  ["/en/personal/household", "Household"],
] as const;

async function signUpWithHousehold(page: Page): Promise<void> {
  const email = `e2e-money-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  await page.goto("/en/signup");
  await page.getByLabel("Full name").fill("Money Tester");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();

  await page.goto("/en/personal");
  await expect(page.getByText("Start your household")).toBeVisible();
  await page.getByLabel("Household name").fill("Tester family");
  await page.getByRole("button", { name: "Create household" }).click();
  // D38: the next step is quick start; these tests go back to the overview themselves.
  await expect(page).toHaveURL(/\/en\/personal\/setup$/);
  await expect(page.getByText("Tester family · Owner")).toBeVisible();
  await page.goto("/en/personal");
}

async function pick(page: Page, label: string, option: string): Promise<void> {
  await page.getByLabel(label, { exact: true }).first().click();
  await page.getByRole("option", { name: option, exact: true }).click();
}

test("every section opens for a new household, with the disclaimer", async ({ page }) => {
  // Sixteen pages, each compiled on first visit by the dev server.
  test.setTimeout(60_000);
  await signUpWithHousehold(page);
  for (const [path, heading] of SECTIONS) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
    // The page's own notice, besides the one in the footer.
    await expect(
      page.getByRole("note").getByText("Historical analysis for education only. Not investment advice."),
    ).toBeVisible();
    await expect(page.getByText("could not be reached")).toHaveCount(0);
  }
});

test("record a cost, an account with a holding, an asset, a goal and a FIRE plan", async ({
  page,
}) => {
  // The longest journey: many pages, each compiled on first visit by the dev server.
  test.setTimeout(60_000);
  await signUpWithHousehold(page);
  // D38: a household with nothing recorded sees what to do first, not empty figures.
  await expect(page.getByRole("heading", { name: "Getting started" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your ACE", exact: true })).toHaveCount(0);

  // F12: a cost appears in the entries.
  await page.goto("/en/personal/costs");
  await page.getByLabel("Amount (৳)").first().fill("1250.50");
  await page.getByRole("button", { name: "Add cost" }).click();
  await expect(page.getByText("Cost added.")).toBeVisible();
  // Shown in the entries and in the monthly and category totals.
  await expect(page.getByRole("cell", { name: "৳1,250.50" }).first()).toBeVisible();

  // F27: income is recorded and what is left after the cost above is worked out.
  await page.goto("/en/personal/income");
  await page.getByLabel("Amount (৳)").first().fill("50000");
  await pick(page, "Kind of income", "Salary");
  await page.getByRole("button", { name: "Add income" }).click();
  await expect(page.getByText("Income added.")).toBeVisible();
  await expect(page.getByRole("cell", { name: "৳48,749.50" }).first()).toBeVisible();
  // FR27.5: the tax form shows the salary it would take from the records.
  await page.goto("/en/personal/tax");
  await expect(page.getByText(/salary ৳50,000\.00/)).toBeVisible();

  // F14: an account, then a holding in it.
  await page.goto("/en/personal/portfolio");
  await pick(page, "Type", "Cash and bank");
  await page.getByLabel("Bank, broker or issuer").fill("Test Bank");
  await page.getByLabel("Name", { exact: true }).first().fill("Current account");
  await page.getByRole("button", { name: "Add account" }).click();
  await expect(page.getByText("Test Bank · Current account").first()).toBeVisible();

  await page.reload();
  const holding = page.locator("form", { has: page.getByRole("button", { name: "Add holding" }) });
  await holding.getByLabel("Type", { exact: true }).click();
  await page.getByRole("option", { name: "Bank balance", exact: true }).click();
  await holding.getByLabel("Name", { exact: true }).fill("Salary account balance");
  await holding.getByLabel("Total cost (৳)").fill("50000");
  await holding.getByLabel("Current value (৳)").fill("52000");
  await holding.getByRole("button", { name: "Add holding" }).click();
  await expect(page.getByRole("link", { name: "Salary account balance" })).toBeVisible();
  await page.getByRole("link", { name: "Salary account balance" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Salary account balance" })).toBeVisible();

  // F25: an asset opens on its own page after it is added.
  await page.goto("/en/personal/assets");
  const asset = page.locator("form", { has: page.getByRole("button", { name: "Add asset" }) });
  await asset.getByLabel("Name", { exact: true }).fill("Plot in Savar");
  await asset.getByLabel("Cost (৳)").fill("1500000");
  await asset.getByLabel("Current value (৳)").fill("1800000");
  await asset.getByRole("button", { name: "Add asset" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Plot in Savar" })).toBeVisible();

  // F19: a goal shows with its progress.
  await page.goto("/en/personal/goals");
  await page.getByLabel("Name", { exact: true }).fill("First crore");
  await page.getByLabel("Target amount (৳)").fill("10000000");
  await page.getByRole("button", { name: "Add goal" }).click();
  await expect(page.getByText("First crore")).toBeVisible();

  // F17: a FIRE plan opens with its projection.
  await page.goto("/en/personal/fire");
  await page.getByLabel("Saved each month (৳)").fill("40000");
  await page.getByLabel("Costs a year (৳)").fill("600000");
  await page.getByLabel("Return a year (%)").fill("9");
  await page.getByLabel("Inflation a year (%)").fill("7");
  await page.getByLabel("Your age now").fill("32");
  await page.getByRole("button", { name: "Project" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "My plan" })).toBeVisible();
  await expect(page.getByText("FIRE number").first()).toBeVisible();

  // The overview reflects the records.
  await page.goto("/en/personal");
  await expect(page.getByText("Net worth").first()).toBeVisible();
  await expect(page.getByText("Tester family · Owner")).toBeVisible();
  // D21: with a plan, the overview leads with the projected FIRE age from it.
  await expect(page.getByText("Projected FIRE age")).toBeVisible();
  await expect(page.getByRole("progressbar", { name: "Progress to your FIRE number" })).toBeVisible();
});

test("a new account goes from sign-up to quick start, and can skip it (D38)", async ({ page }) => {
  await page.goto("/en/signup");
  await page.getByLabel("Full name").fill("Rina Akter");
  await page.getByLabel("Email").fill(`e2e-first-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Create account" }).click();

  // Straight into My money, with a household name suggested from the account name.
  await expect(page).toHaveURL(/\/en\/personal$/);
  await expect(page.getByLabel("Household name")).toHaveValue("Akter family");
  await page.getByRole("button", { name: "Create household" }).click();

  // Then quick start, which can be skipped.
  await expect(page).toHaveURL(/\/en\/personal\/setup$/);
  await page.getByRole("link", { name: /Skip for now/ }).click();
  await expect(page).toHaveURL(/\/en\/personal$/);
  await expect(page.getByRole("heading", { name: "Getting started" })).toBeVisible();
  await expect(page.getByText("appear here as soon as you record")).toBeVisible();
  await expect(page.getByRole("heading", { name: "All sections" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your ACE", exact: true })).toHaveCount(0);
});

test("quick start records the basics and the overview shows the FIRE picture (D22)", async ({ page }) => {
  await signUpWithHousehold(page);
  await expect(page.getByRole("heading", { name: "Getting started" })).toBeVisible();
  await expect(page.getByText("0 of 5 steps done", { exact: false })).toBeVisible();
  await page.getByRole("link", { name: "Open quick start" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Quick start" })).toBeVisible();

  await page.getByLabel("Year you were born").fill("1990");
  await page.getByLabel("Monthly take-home income (৳)").fill("100000");
  await page.getByLabel("Rent (৳ a month)").fill("25000");
  await page.getByLabel("Food and bazar (৳ a month)").fill("20000");
  await page.getByLabel("Cash and bank balances (৳)").fill("300000");
  await page.getByRole("button", { name: "Save and see my FIRE picture" }).click();

  // Back on the overview: four of five steps, an estimate from costs, and the savings rate:
  // 1,00,000 income less 45,000 costs is 55,000 saved, 55%.
  await expect(page).toHaveURL(/\/en\/personal$/);
  await expect(page.getByText("4 of 5 steps done", { exact: false })).toBeVisible();
  await expect(page.getByText("Estimated FIRE number")).toBeVisible();
  await expect(page.getByText("55%").first()).toBeVisible();
});

test("income imports from CSV and a bad row says why (FR27.7)", async ({ page }) => {
  await signUpWithHousehold(page);
  await page.goto("/en/personal/income");
  await page
    .getByLabel("Or paste the CSV here")
    .fill(["date,amount,kind", "2026-11-01,90000,salary", "2026-11-02,500,LOTTERY"].join("\n"));
  await page.getByRole("button", { name: "Import" }).click();
  await expect(page.getByText("Row 3: the kind is not one of the income kinds")).toBeVisible();
  await expect(page.getByRole("cell", { name: "৳90,000.00" }).first()).toBeVisible();
});

test("the grouped section menu reaches every section on desktop and phone", async ({ page }) => {
  await signUpWithHousehold(page);
  await page.goto("/en/personal");
  const wide = (page.viewportSize()?.width ?? 0) >= 1024;
  if (wide) {
    // Desktop: task groups open a list with a short description for each section.
    const menu = page.getByRole("navigation", { name: "My money sections" });
    await menu.getByRole("button", { name: /Capital/ }).click();
    await menu.getByRole("link", { name: /Accounts and holdings/ }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Accounts and holdings" })).toBeVisible();
    await menu.getByRole("button", { name: /Plans/ }).click();
    await menu.getByRole("link", { name: /^Goals/ }).click();
  } else {
    // Phone: one button names the current section and opens every section by group.
    await page.getByRole("button", { name: /All sections/ }).click();
    await expect(page.getByRole("dialog").getByText("Capital", { exact: true })).toBeVisible();
    await page.getByRole("dialog").getByRole("link", { name: /^Goals/ }).click();
    await expect(page.getByRole("button", { name: /Goals/ })).toBeVisible();
  }
  await expect(page.getByRole("heading", { level: 1, name: "Goals" })).toBeVisible();
});
