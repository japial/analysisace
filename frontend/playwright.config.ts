import { defineConfig, devices } from "@playwright/test";

/**
 * Browser tests for key flows (PRD section 15). They run against a live stack, so start
 * the database, the API and the web app first (see CLAUDE.md), then `npm run test:e2e`.
 */
export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  fullyParallel: false,
  workers: 1,
  // In CI (D29) a test gets one more try, and failures are annotated on the pull request.
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["github"]] : [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    // PRD section 12: usable at 360 px width.
    { name: "phone", use: { ...devices["Desktop Chrome"], viewport: { width: 360, height: 740 } } },
  ],
});
