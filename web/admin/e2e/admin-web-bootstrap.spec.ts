import { test, expect } from "@playwright/test";

/**
 * spec `playwright-smoke` § Requirement: Bootstrap E2E smoke test exists
 *
 * 验证：
 *  - 深链 /mcp-tools 可达
 *  - SideNav 渲染（navigation 角色可见）
 *  - "MCP 工具" 链接拿到 aria-current="page"
 *  - 占位卡 "即将推出" 文案可见
 */
test("Open /mcp-tools and verify SideNav + Placeholder", async ({ page }) => {
  await page.goto("/mcp-tools");
  await expect(page).toHaveURL(/\/mcp-tools$/);

  const nav = page.getByRole("navigation", { name: "主导航" });
  await expect(nav).toBeVisible();

  const mcpLink = nav.getByRole("link", { name: "MCP 工具" });
  await expect(mcpLink).toHaveAttribute("aria-current", "page");

  await expect(page.getByText(/即将推出/)).toBeVisible();
  await expect(
    page.getByText(/由后续 change mcp-server-management-ui 落地/),
  ).toBeVisible();
});
