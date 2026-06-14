import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.route('**/workflows*', async (route) => {
    if (route.request().method() === 'POST') {
      // V4 对齐真契约:服务端返回 uuid,而非 client 硬编码 'paul-monthly' 字面量
      // v1 API 响应格式:{ id: uuid, version, name, created_by, created_at, archived, definition_json }
      await route.fulfill({
        json: {
          id: 'b3d4e5f6-7890-1234-5678-9abcdef01234',
          version: 1,
          name: 'paul 月报',
          created_by: 'u-paul',
          created_at: new Date().toISOString(),
          archived: false,
          definition_json: { nodes: [], edges: [], variables: {}, mode: 'workflow' },
        },
      });
    } else {
      await route.fulfill({ json: { workflows: [], total: 0 } });
    }
  });
  await page.route('**/workflows/b3d4e5f6-7890-1234-5678-9abcdef01234', async (route) => {
    await route.fulfill({
      json: {
        id: 'b3d4e5f6-7890-1234-5678-9abcdef01234',
        version: 1,
        name: 'paul 月报',
        definition_json: { nodes: [], edges: [], variables: {}, mode: 'workflow' },
      },
    });
  });
  await page.route('**/api/nodes*', async (route) => {
    await route.fulfill({
      json: {
        node_types: [
          'start', 'end', 'variable_assign', 'condition', 'llm',
          'knowledge', 'agent', 'http', 'code', 'approval',
          'loop', 'iterate', 'subflow', 'extract',
        ].map((type) => ({ type, version: '1.0.0' })),
      },
    });
  });
});

test('workflow list can create paul monthly report and navigate to editor', async ({ page }) => {
  await page.goto('/login');
  await page.getByPlaceholder('任意非空 username(dev mode)').fill('paul');
  await page.getByPlaceholder('任意密码(dev mode)').fill('dev');
  await page.getByRole('button', { name: '登录' }).click();
  await expect(page).toHaveURL(/\/workflows/);
  await page.getByRole('button', { name: /新建工作流/ }).click();
  await page.getByPlaceholder(/paul/).fill('paul 月报');
  await page.getByRole('button', { name: '创建' }).click();
  // V4: 路径用 mock uuid,非字面量 'paul-monthly'
  await expect(page).toHaveURL(/\/workflows\/[0-9a-f-]{36}\/edit/);
});
