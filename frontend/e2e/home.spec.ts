import { expect, test } from "@playwright/test";

/** The landing page: promise, calls to action, feature sections, questions and disclaimer. */
test("the landing page explains the product and leads to sign-up and the market pages", async ({ page }) => {
  await page.goto("/en");
  await expect(page.getByRole("heading", { level: 1, name: /Invest with clarity/ })).toBeVisible();
  await expect(page.getByText("Illustration with a fictional company")).toBeVisible();

  for (const heading of [
    "Answers to the questions you actually ask",
    "Understand DSE stocks before you decide",
    "Your whole household's money, organised",
    "Up and running in three steps",
    "Built on trust, not tips",
    "Common questions",
  ]) {
    await expect(page.getByRole("heading", { level: 2, name: heading })).toBeVisible();
  }

  // Questions open in place, without scripts.
  await page.getByText("Is this investment advice?").click();
  await expect(page.getByText(/never recommends buying, selling or holding/)).toBeVisible();
  await expect(page.getByRole("note").getByText("Historical analysis for education only. Not investment advice.")).toBeVisible();

  await page.getByRole("link", { name: "See a screen" }).click();
  await expect(page).toHaveURL(/\/en\/shariah$/);
  await page.goto("/en");
  await page.getByRole("link", { name: "Create your account" }).first().click();
  await expect(page).toHaveURL(/\/en\/signup$/);
});

test("the landing page reads in Bangla", async ({ page }) => {
  await page.goto("/bn");
  await expect(page.getByRole("heading", { level: 1, name: /স্পষ্টভাবে বিনিয়োগ করুন/ })).toBeVisible();
});
