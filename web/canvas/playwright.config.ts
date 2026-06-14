import { defineConfig, devices } from '@playwright/test';
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  // V4: 起 canvas dev server 在 5174(5173 是统一 nginx 容器,留给 SPA 集成 e2e)
  // webServer command `pnpm dev --port 5174 --host 127.0.0.1` 跟 vite.config 5173 冲突,
  // 但 V4 已知 nginx 占 5173,canvas dev 改跑 5174 + 配套 VITE_API_BASE 指向 workflow-engine
  webServer: {
    command: 'VITE_APP_BASE=/ pnpm dev --port 5174 --host 127.0.0.1 --strictPort',
    url: 'http://localhost:5174',
    reuseExistingServer: true,
    timeout: 120_000,
  },
  use: {
    baseURL: 'http://localhost:5174',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});
