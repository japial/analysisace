import { expect, type Page, test } from "@playwright/test";

/**
 * Accounts and roles end to end: PRD section 10 (Auth), FR23 and user management.
 *
 * The admin test needs an administrator: create one with backend/scripts/create_admin.py
 * and pass it as E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD. Without them that test is skipped.
 */
const PASSWORD = "e2e-password-123";
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL;
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD;

function uniqueEmail(tag: string): string {
  return `e2e-${tag}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
}

async function signUp(page: Page, email: string, name = "Test Person"): Promise<void> {
  await page.goto("/en/signup");
  await page.getByLabel("Full name").fill(name);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
}

async function signIn(page: Page, email: string, password: string): Promise<void> {
  await page.goto("/en/signin");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

async function signOut(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("link", { name: "Sign in" })).toBeVisible();
}

test("sign up, sign out, sign in again", async ({ page }) => {
  const email = uniqueEmail("signup");
  await signUp(page, email);
  await expect(page).toHaveURL(/\/en$/);

  await page.goto("/en/account");
  await expect(page.getByRole("heading", { name: "My account" })).toBeVisible();
  await expect(page.locator('input[name="email"]')).toHaveValue(email);

  await signOut(page);
  // A protected page now sends the visitor to sign in, then back where they wanted to go.
  await page.goto("/en/account");
  await expect(page).toHaveURL(/\/en\/signin\?next=%2Faccount/);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/en\/account$/);
});

test("wrong password shows one error that does not reveal which part was wrong", async ({
  page,
}) => {
  await signIn(page, uniqueEmail("nobody"), "wrong-password");
  await expect(page.getByText("The email or password is not correct.")).toBeVisible();
  await expect(page).toHaveURL(/\/en\/signin/);
});

test("sign-up without consent is refused (FR23.1)", async ({ page }) => {
  await page.goto("/en/signup");
  await page.getByLabel("Full name").fill("No Consent");
  await page.getByLabel("Email").fill(uniqueEmail("noconsent"));
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  // The browser blocks the form on the required checkbox; no account is created.
  await expect(page).toHaveURL(/\/en\/signup/);
  await expect(page.getByRole("button", { name: "Account menu" })).toHaveCount(0);
});

test("Bangla pages and the forgot-password answer", async ({ page }) => {
  await page.goto("/bn/signin");
  await expect(page.getByRole("heading", { name: "প্রবেশ করুন" })).toBeVisible();
  await page.getByRole("link", { name: "পাসওয়ার্ড ভুলে গেছেন?" }).click();
  await page.getByLabel("ইমেইল").fill(uniqueEmail("unknown"));
  await page.getByRole("button", { name: "লিংক পাঠান" }).click();
  // The same answer for known and unknown emails.
  await expect(page.getByRole("status")).toContainText("লিংক পাঠানো হয়েছে");
});

test("privacy choices are saved and can be withdrawn (FR23.1, FR23.2)", async ({ page }) => {
  await signUp(page, uniqueEmail("consent"));
  await page.goto("/en/account");
  const religious = page.getByRole("switch", { name: "Zakat and Shariah preferences" });
  await expect(religious).not.toBeChecked();
  await religious.click();
  await page.getByRole("button", { name: "Save changes" }).nth(1).click();
  await expect(page.getByRole("status")).toHaveText("Saved.");

  await page.reload();
  await expect(religious).toBeChecked();
  await religious.click();
  await page.getByRole("button", { name: "Save changes" }).nth(1).click();
  await page.reload();
  await expect(religious).not.toBeChecked();
});

test("change password, then delete the account (FR23.4)", async ({ page }) => {
  const email = uniqueEmail("delete");
  const newPassword = "e2e-new-password-456";
  await signUp(page, email);
  await page.goto("/en/account");

  await page.getByLabel("Current password").fill(PASSWORD);
  await page.getByLabel("New password").fill(newPassword);
  await page.getByRole("button", { name: "Change password" }).click();
  await expect(page.getByRole("status")).toHaveText("Password changed.");

  await page.getByRole("button", { name: "Delete my account" }).click();
  const dialog = page.getByRole("alertdialog");
  await dialog.getByLabel("Password").fill(newPassword);
  await dialog.getByRole("button", { name: "Delete permanently" }).click();
  await expect(page).toHaveURL(/\/en$/);
  await expect(page.getByRole("link", { name: "Sign in" })).toBeVisible();

  await signIn(page, email, newPassword);
  await expect(page.getByText("The email or password is not correct.")).toBeVisible();
});

test("an ordinary user cannot see user management", async ({ page }) => {
  await signUp(page, uniqueEmail("plain"));
  await expect(page.getByRole("link", { name: "Users" })).toHaveCount(0);
  const response = await page.goto("/en/admin/users");
  expect(response?.status()).toBe(404);
});

test("an administrator changes a user's role and access", async ({ page, browser }) => {
  test.skip(!ADMIN_EMAIL || !ADMIN_PASSWORD, "Set E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD");
  const email = uniqueEmail("managed");
  const name = `Managed ${Date.now()}`;

  // The managed user signs up in a separate browser session.
  const other = await browser.newContext();
  const otherPage = await other.newPage();
  await signUp(otherPage, email, name);

  await signIn(page, ADMIN_EMAIL ?? "", ADMIN_PASSWORD ?? "");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  await page.goto(`/en/admin/users?q=${encodeURIComponent(email)}`);
  await expect(page.getByText(email)).toBeVisible();

  await page.getByRole("combobox", { name: `Role for ${name}` }).click();
  await page.getByRole("option", { name: "Analyst" }).click();
  await expect(page.getByRole("combobox", { name: `Role for ${name}` })).toHaveText("Analyst");
  await page.reload();
  await expect(page.getByRole("combobox", { name: `Role for ${name}` })).toHaveText("Analyst");

  // Turning access off signs the user out at once.
  await page.getByRole("switch", { name: `Access for ${name}` }).click();
  await expect(page.getByText("Access off")).toBeVisible();
  await otherPage.goto("/en/account");
  await expect(otherPage).toHaveURL(/\/en\/signin/);
  await other.close();

  await page.goto("/en/admin/roles");
  await expect(page.getByRole("heading", { name: "Roles and permissions" })).toBeVisible();
  await expect(page.getByText("Manage users", { exact: true })).toBeVisible();
});
