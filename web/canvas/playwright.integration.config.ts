// Playwright integration config — separate from the unit config (which
// uses page.route() mocks and the vite dev server webServer).
//
// The integration config:
// - testDir: './e2e/integration' (does NOT include the existing mock-based
//   specs in ./e2e/auth.spec.ts, ./e2e/paul-monthly-report.spec.ts, etc.)
// - No webServer: the test compose stack already provides 5173.
// - baseURL: http://localhost:5173 (CLAUDE.md single-port convention).

import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e/integration',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: 'http://localhost:5173',
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});
