// Admin health E2E — proves the nginx /healthz → chatbiz-mcp:8080 proxy works.
//
// This spec requires the test compose stack to be running. The mcp
// container is stopped/started via docker compose to simulate failure
// and recovery. The header bar's "服务健康：X" label is the assertion target.
//
// The dev-only VITE_ADMIN_HEALTH_DIRECT=1 path is NOT exercised here —
// we want the production path (relative /healthz → nginx → mcp).

import { execSync } from "node:child_process";
import { expect, test } from "@playwright/test";

const COMPOSE = "docker compose -p chatbiz-test -f infrastructure/docker-compose-test.yml";

function exec(cmd: string): string {
  return execSync(cmd, { encoding: "utf-8" }).trim();
}

test.describe("admin health E2E", () => {
  test.afterAll(() => {
    // Best-effort: restart mcp so other specs / devs can keep working
    try {
      exec(`${COMPOSE} start mcp`);
    } catch {
      // ignore
    }
  });

  test("shows green dot when mcp is healthy", async ({ page }) => {
    await page.goto("http://localhost:5173/admin/");
    // HealthIndicator is mounted in AppShell; wait for the polling response
    await expect(page.locator('[aria-label^="服务健康"]')).toHaveAttribute(
      "aria-label",
      "服务健康：健康",
      { timeout: 15_000 },
    );
  });

  test("shows red dot when mcp is stopped", async ({ page }) => {
    exec(`${COMPOSE} stop mcp`);
    // Give nginx a moment to register the upstream is down
    await new Promise((r) => setTimeout(r, 1_000));

    await page.goto("http://localhost:5173/admin/");
    await expect(page.locator('[aria-label^="服务健康"]')).toHaveAttribute(
      "aria-label",
      "服务健康：不可用",
      { timeout: 15_000 },
    );
  });

  test("recovers green when mcp is restarted", async ({ page }) => {
    exec(`${COMPOSE} start mcp`);
    // Wait for mcp healthcheck to flip back to healthy
    await new Promise((r) => setTimeout(r, 5_000));

    await page.goto("http://localhost:5173/admin/");
    await expect(page.locator('[aria-label^="服务健康"]')).toHaveAttribute(
      "aria-label",
      "服务健康：健康",
      { timeout: 15_000 },
    );
  });
});
