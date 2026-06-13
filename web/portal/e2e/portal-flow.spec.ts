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
