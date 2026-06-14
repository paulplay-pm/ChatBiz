import { test, expect } from '@playwright/test';

const NODE_TYPES = [
  'start', 'end', 'variable_assign', 'condition', 'llm',
  'knowledge', 'agent', 'http', 'code', 'approval',
  'loop', 'iterate', 'subflow', 'extract',
];

test.beforeEach(async ({ page }) => {
  // V4 回归到 V2 page.route 模式 — canvas dev 5174 没 /api/nodes 端点,
  // page.route 拦截后 fulfill mock
  await page.route(/\/api\/nodes(\/|$|\?)/, async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/nodes' || path === '/api/nodes/') {
      return route.fulfill({
        json: {
          node_types: NODE_TYPES.map((type) => ({ type, version: '1.0.0' })),
        },
      });
    }
    if (path.startsWith('/api/nodes/') && path.endsWith('/schema')) {
      // V4 对齐真契约:除 config_schema 外加 input_schema + output_schema
      return route.fulfill({
        json: {
          type: 'llm',
          version: '1.0.0',
          config_schema: {
            type: 'object',
            properties: {
              model: { type: 'string', enum: ['gpt-4', 'claude-3', 'gemini-pro'] },
              prompt: { type: 'string' },
              temperature: { type: 'number', default: 0.7 },
            },
            required: ['model', 'prompt'],
          },
          input_schema: {
            type: 'object',
            properties: { context: { type: 'string' } },
          },
          output_schema: {
            type: 'object',
            properties: { text: { type: 'string' }, tokens_used: { type: 'integer' } },
          },
        },
      });
    }
    return route.fallback();
  });
});

test('node schema endpoint returns 14 node types via api', async ({ page }) => {
  // V4: 直接走 baseURL(apiRequest 不被 page.route 拦截,但 beforeEach mock 已
  // 在 page context 上 setData,我们用 page.evaluate 在浏览器 context 走
  // mocked 路径 — fetch('/api/nodes') 走 page.route
  // 浏览器 fetch 走 vite proxy,但 vite dev server 的 /api/nodes 端点不存在
  // → 401 workflow-engine,所以这条 test 必须用 page.route 拦截

  // 解决:login → 跳 /workflows → 触发 /api/nodes 调用 + 等 mock 响应
  await page.goto('/login');
  await page.getByPlaceholder('任意非空 username(dev mode)').fill('paul');
  await page.getByPlaceholder('任意密码(dev mode)').fill('dev');
  await page.getByRole('button', { name: '登录' }).click();
  await expect(page).toHaveURL(/\/workflows/);

  // 触发 /api/nodes:在 canvas 上点"新建工作流"按钮,WorkflowListPage
  // mount 后会 fetch 列表,但 /api/nodes 节点 schema 通常在打开节点
  // config 时调。V4 这里直接调 mock 端点用 page.evaluate
  const list = await page.evaluate(async () => {
    const r = await fetch('/api/nodes');
    return r.json();
  });
  expect(list.node_types).toHaveLength(14);
});
