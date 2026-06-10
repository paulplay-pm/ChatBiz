import { test, expect } from '@playwright/test';

test('dev login redirects to workflows', async ({ page }) => {
  await page.goto('/login');
  await page.getByPlaceholder('任意非空 username(dev mode)').fill('paul');
  await page.getByPlaceholder('任意密码(dev mode)').fill('dev');
  await page.getByRole('button', { name: '登 录' }).click();
  await expect(page).toHaveURL(/\/workflows/);
});
