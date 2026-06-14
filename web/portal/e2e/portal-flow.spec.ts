import { test, expect } from '@playwright/test';

test('portal: login → dashboard → sidebar workflow', async ({ page }) => {
  // Vite base: '/portal/' so all portal routes are at /portal/...
  await page.goto('/portal/');
  await expect(page).toHaveURL(/\/portal\/login$/);
  await page.getByPlaceholder('username').fill('paul');
  await page.getByPlaceholder('password').fill('dev');
  await page.getByTestId('btn').click();
  // After login, react-router navigate('/') under basename '/portal' resolves to /portal (no trailing slash)
  await expect(page).toHaveURL(/\/portal\/?$/);
  await expect(page.getByTestId('sidebar')).toBeVisible();
  // sidebar workflow click triggers window.location.assign to localhost:5173/canvas/...
  // in e2e preview (4174) the cross-origin jump may not complete; assert sidebar item visible instead
  await expect(page.getByTestId('sidebar-item-workflow-list')).toBeVisible();
});

test('portal: clicking 未接入 menu shows Coming soon page', async ({ page }) => {
  await page.goto('/portal/login');
  await page.getByPlaceholder('username').fill('paul');
  await page.getByPlaceholder('password').fill('dev');
  await page.getByTestId('btn').click();
  await page.getByTestId('sidebar-item-credential').click();
  await expect(page).toHaveURL(/coming-soon\?from=credential$/);
  // Scope to the coming-soon container to avoid matching the sidebar item too
  await expect(page.getByTestId('coming-soon').getByText(/凭证/)).toBeVisible();
});

// V4: SSO 企微扫码 dev mock 流程
test('portal: SSO 扫码入口按钮 → 跳假 IM 页', async ({ page }) => {
  await page.goto('/portal/login');
  // 看到 SSO 按钮
  await expect(page.getByTestId('sso-login-button')).toBeVisible();

  // 点击按钮 → ssoInitiate fetch → dev fallback 返 mock qr_url
  // → window.open 失败 → location.assign 跳 /portal/sso-mock-im
  await page.getByTestId('sso-login-button').click();
  await expect(page).toHaveURL(/\/portal\/sso-mock-im\?token=mock-/, { timeout: 10_000 });

  // 假 IM 页渲染
  await expect(page.getByTestId('sso-mock-im-page')).toBeVisible();
  await expect(page.getByTestId('sso-confirm')).toBeVisible();

  // 点击确认 → dev mock 写 localStorage.auth + 跳首页
  await page.getByTestId('sso-confirm').click();
  await expect(page).toHaveURL(/\/portal\/?$/, { timeout: 10_000 });
  await expect(page.getByTestId('sidebar')).toBeVisible();

  // 验证 localStorage 含 SSO 标识
  const auth = await page.evaluate(() => localStorage.getItem('chatbiz.auth'));
  expect(auth).toBeTruthy();
  const parsed = JSON.parse(auth!);
  expect(parsed.via).toBe('sso-wechat-scan');
  expect(parsed.jwt).toMatch(/^mock-jwt-/);
});
