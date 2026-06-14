import { test, expect } from '@playwright/test';

// 跨 app e2e — 跑在统一 nginx 5173 上,验证 portal/canvas/admin 路径分发 + meta refresh + 跨跳。
// 前置: docker run --rm -d --name chatbiz-web -p 5173:80 chatbiz-web:v3
// 配套 14-gate verify 的 "1 nginx curl"。

test('cross-app: 5173 / meta refresh → /portal/login', async ({ page }) => {
  // T1: 入口修复 — meta refresh 0;url=/portal/login
  await page.goto('/');
  // 浏览器自动 follow meta refresh;最终 URL 应跳到 /portal/login
  await expect(page).toHaveURL(/\/portal\/login/);
});

test('cross-app: portal sidebar 工作流 click → /canvas/workflows (window.location.assign)', async ({ page }) => {
  // 1. Land on portal login (5173 是统一 nginx 入口)
  await page.goto('/portal/login');
  await expect(page.getByTestId('login-page')).toBeVisible();

  // 2. Dev mode login
  await page.getByPlaceholder('username').fill('paul');
  await page.getByTestId('btn').click();
  await expect(page).toHaveURL(/\/portal\/?$/);
  await expect(page.getByTestId('sidebar')).toBeVisible();

  // 3. 点 sidebar 工作流 → AppLayout 走 window.location.assign
  await page.getByTestId('sidebar-item-workflow-list').click();
  await expect(page).toHaveURL(/\/canvas\/workflows/);
});

test('cross-app: portal 系统管理 → 用户列表跳 /admin/users (T5 真路由)', async ({ page }) => {
  // 1. Login
  await page.goto('/portal/login');
  await page.getByPlaceholder('username').fill('paul');
  await page.getByTestId('btn').click();
  await expect(page.getByTestId('sidebar')).toBeVisible();

  // 2. 点 sidebar 用户列表 (T2 系统管理分组,external: true 跳 /admin/users)
  await page.getByTestId('sidebar-item-user-list').click();
  await expect(page).toHaveURL(/\/admin\/users$/);

  // 3. admin /users 应渲染 UsersPage 3 行 + 6 列头
  await expect(page.getByTestId('users-page')).toBeVisible();
  await expect(page.getByTestId('users-table')).toBeVisible();
  await expect(page.getByTestId('add-user')).toBeVisible();
});

test('cross-app: portal 系统管理 → 角色管理跳 /admin/roles (T5 多 path)', async ({ page }) => {
  await page.goto('/portal/login');
  await page.getByPlaceholder('username').fill('paul');
  await page.getByTestId('btn').click();
  await expect(page.getByTestId('sidebar')).toBeVisible();

  await page.getByTestId('sidebar-item-role').click();
  await expect(page).toHaveURL(/\/admin\/roles$/);
  await expect(page.getByTestId('roles-page')).toBeVisible();
  await expect(page.locator('[data-testid="role-card"]')).toHaveCount(4);
});
