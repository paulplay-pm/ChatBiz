import { test, expect } from '@playwright/test';

// Helper: only intercept XHR/fetch (not initial HTML document)
const isXhr = (req: import('@playwright/test').Request) => {
  const h = req.headers();
  return h['accept']?.includes('application/json') || h['x-requested-with'] === 'XMLHttpRequest' || h['sec-fetch-mode'] === 'cors';
};

const NODE_TYPES = [
  'start', 'end', 'variable_assign', 'condition', 'llm',
  'knowledge', 'agent', 'http', 'code', 'approval',
  'loop', 'iterate', 'subflow', 'extract',
];

test.beforeEach(async ({ page }) => {
  // Mock /api/nodes list(14 type)+ /api/nodes/<type>/schema
  await page.route(/\/api\/nodes(\/|$|\?)/, async (route) => {
    if (!isXhr(route.request())) return route.fallback();
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
    return route.fulfill({ status: 200, json: {} });
  });
});

test('node schema endpoint returns 14 node types via api', async ({ page }) => {
  // V4: 真消费契约 — 14 node types 列表 + 单 type schema 含 config/input/output 3 schema
  // 1. list 端点返回 14 type
  const listResponse = await page.request.get('/api/nodes');
  expect(listResponse.ok()).toBe(true);
  const list = await listResponse.json();
  expect(list.node_types).toHaveLength(14);

  // 2. per-type schema 端点返回 3 schema 字段
  const schemaResponse = await page.request.get('/api/nodes/llm/schema');
  expect(schemaResponse.ok()).toBe(true);
  const schema = await schemaResponse.json();
  expect(schema.type).toBe('llm');
  expect(schema.config_schema).toBeTruthy();
  expect(schema.config_schema.type).toBe('object');
  expect(schema.config_schema.properties.model).toBeTruthy();
  expect(schema.config_schema.required).toContain('model');
  expect(schema.input_schema).toBeTruthy();
  expect(schema.output_schema).toBeTruthy();
});
