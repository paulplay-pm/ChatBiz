import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.route('**/workflows*', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({ json: { id: 'paul-monthly', version: 1, name: 'paul 月报', created_by: 'u-paul', created_at: new Date().toISOString(), archived: false, definition_json: { nodes: [], edges: [], variables: {}, mode: 'workflow' } } });
    } else {
      await route.fulfill({ json: { workflows: [], total: 0 } });
    }
  });
  await page.route('**/workflows/paul-monthly', async (route) => {
    await route.fulfill({ json: { id: 'paul-monthly', version: 1, name: 'paul 月报', definition_json: { nodes: [], edges: [], variables: {}, mode: 'workflow' } } });
  });
  await page.route('**/api/nodes*', async (route) => {
    await route.fulfill({ json: { node_types: [{ type: 'llm', version: '1.0.0' }] } });
  });
});

test('workflow list can create paul monthly report and navigate to editor', async ({ page }) => {
  await page.goto('/login');
  await page.getByPlaceholder('任意非空 username(dev mode)').fill('paul');
  await page.getByRole('button', { name: '登录' }).click();
  await expect(page).toHaveURL(/\/workflows/);
  await page.getByRole('button', { name: /新建工作流/ }).click();
  await page.getByPlaceholder('例:paul 财务月报').fill('paul 月报');
  await page.getByRole('button', { name: '创建' }).click();
  await expect(page).toHaveURL(/\/workflows\/paul-monthly\/edit/);
});
