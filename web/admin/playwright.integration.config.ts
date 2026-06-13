// Playwright integration config for admin E2E.
//
// Difference from unit config (web/admin/playwright.config.ts):
// - testDir: './e2e/integration' (does NOT include the existing
//   admin-web-bootstrap.spec.ts unit smoke)
// - No webServer: the test compose stack already serves 5173.
// - fullyParallel: false — admin health is a single global probe; multi-
//   worker concurrent stop/start of the mcp container would race.

import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e/integration",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  forbidOnly: !!process.env["CI"],
  retries: process.env["CI"] ? 2 : 1,
  workers: 1,
  reporter: process.env["CI"] ? "github" : "list",
  use: {
    baseURL: "http://localhost:5173",
    headless: true,
    screenshot: "only-on-failure",
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
