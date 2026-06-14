import { defineConfig } from '@playwright/test';

// 跨 app e2e — 跑在统一 nginx 5173 上,验证 portal/canvas/admin 路径分发。
// 配套 14-gate verify 的 "1 nginx curl"。
// 前置: docker run --rm -d --name chatbiz-web-e2e -p 5173:80 chatbiz-web:v2
export default defineConfig({
  testDir: './e2e',
  testMatch: /cross-app-jump\.spec\.ts/,
  use: { baseURL: 'http://localhost:5173' },
});
