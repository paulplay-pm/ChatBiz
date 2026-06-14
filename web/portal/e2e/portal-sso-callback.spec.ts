import { test, expect } from '@playwright/test';

// V6a: portal SSO callback page e2e
// Vite base '/portal/' — react-router 内部 path /sso-callback 在 preview 实际是 /portal/sso-callback

test('SsoCallbackPage 渲染 code + state + 完成登录按钮', async ({ page }) => {
  await page.goto('/portal/sso-callback?code=test-code-abc&state=test-state-xyz');
  await expect(page.getByTestId('sso-callback-page')).toBeVisible();
  await expect(page.getByTestId('sso-code')).toHaveText('test-code-abc');
  await expect(page.getByTestId('sso-state')).toHaveText('test-state-xyz');
  await expect(page.getByTestId('sso-exchange')).toBeEnabled();
});

test('SsoCallbackPage 缺 code 或 state 显示 error + 按钮 disabled', async ({ page }) => {
  await page.goto('/portal/sso-callback?state=state-only');
  await expect(page.getByTestId('sso-error')).toContainText('缺少');
  await expect(page.getByTestId('sso-exchange')).toBeDisabled();
});

test('SsoCallbackPage 后端 401 错误时显示错误消息', async ({ page }) => {
  // mock 真后端 /api/auth/sso/wechat/callback 返回 401
  await page.route('**/api/auth/sso/wechat/callback*', (route) =>
    route.fulfill({ status: 401, body: 'Unauthorized' }),
  );
  await page.goto('/portal/sso-callback?code=any-code&state=any-state');
  await page.getByTestId('sso-exchange').click();
  await expect(page.getByTestId('sso-error')).toContainText(/401/);
});
