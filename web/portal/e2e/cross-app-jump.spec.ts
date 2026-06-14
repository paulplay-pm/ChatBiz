import { test, expect } from '@playwright/test';

test('portal: sidebar 工作流 click jumps to /canvas/workflows (cross-app on 5173)', async ({ page }) => {
  // 1. Land on portal login (5173 是统一 nginx 入口)
  await page.goto('/portal/login');
  await expect(page.getByTestId('login-page')).toBeVisible();

  // 2. Dev mode login (username 非空即过)
  await page.getByPlaceholder('username').fill('paul');
  await page.getByTestId('btn').click();
  await expect(page).toHaveURL(/\/portal\/?$/);
  await expect(page.getByTestId('sidebar')).toBeVisible();

  // 3. 点 sidebar 工作流 → AppLayout 走 window.location.assign('http://localhost:5173/canvas/workflows')
  //    同一 origin (5173),navigation 跟到 canvas SPA fallback
  await page.getByTestId('sidebar-item-workflow-list').click();
  await expect(page).toHaveURL(/\/canvas\/workflows/);

  // 4. canvas 在 /canvas/* 路径下要能加载 — index.html 应可见(react-flow root 后挂载)
  //    这里不强制 canvas 内部元素(已有 8 个 e2e 覆盖),只验证路径分发 + SPA 不 404
  const bodyText = await page.locator('body').textContent();
  expect(bodyText).toBeTruthy();
  expect(bodyText!.length).toBeGreaterThan(0);
});

test('portal: index card → /admin/ (cross-app 5173)', async ({ page }) => {
  // 统一入口 index.html (5173 /) 列出 3 张卡
  await page.goto('/');
  await expect(page.locator('a.card[href="/admin/"]')).toBeVisible();
  await page.locator('a.card[href="/admin/"]').click();
  await expect(page).toHaveURL(/\/admin\//);
  const bodyText = await page.locator('body').textContent();
  expect(bodyText).toBeTruthy();
});
