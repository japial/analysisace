import { expect, test } from "@playwright/test";

/** The landing page: the FIRE promise, how FIRE works, the ACE levers, questions and disclaimer. */
test("the landing page explains FIRE and ACE and leads to sign-up and the stock tools", async ({ page }) => {
  await page.goto("/en");
  await expect(page.getByRole("heading", { level: 1, name: /Find the year work becomes optional/ })).toBeVisible();
  await expect(page.getByText("Illustration with fictional figures")).toBeVisible();

  for (const heading of [
    "Financial independence in three ideas",
    "Your savings rate decides more than your returns",
    "Assets, Capital and Earnings move your FIRE date",
    "A FIRE plan made for life here",
    "Questions on the way to independence",
    "Holding DSE shares? Understand them better",
    "Your FIRE plan in three steps",
    "Built on trust, not tips",
    "Common questions",
  ]) {
    await expect(page.getByRole("heading", { level: 2, name: heading })).toBeVisible();
  }

  // The savings-rate illustration is a table with its assumptions stated.
  await expect(page.getByRole("rowheader", { name: "Save 40%" })).toBeVisible();
  await expect(page.getByText(/Illustration, not a forecast/)).toBeVisible();

  // Questions open in place, without scripts.
  await page.getByText("Is my FIRE age a promise?").click();
  await expect(page.getByText(/It is a projection from the figures you enter/)).toBeVisible();
  await expect(page.getByRole("note").getByText("Historical analysis for education only. Not investment advice.")).toBeVisible();

  await page.getByRole("link", { name: "See a screen" }).click();
  await expect(page).toHaveURL(/\/en\/shariah$/);
  await page.goto("/en");
  await page.getByRole("link", { name: "Start your FIRE plan" }).first().click();
  await expect(page).toHaveURL(/\/en\/signup$/);
});

test("the landing page reads in Bangla", async ({ page }) => {
  await page.goto("/bn");
  await expect(page.getByRole("heading", { level: 1, name: /কোন বছর থেকে কাজ হবে আপনার ইচ্ছা/ })).toBeVisible();
});
