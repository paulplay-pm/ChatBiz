import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './e2e',
  webServer: { command: 'pnpm exec vite preview --port 4174', port: 4174, reuseExistingServer: true },
  use: { baseURL: 'http://localhost:4174' },
});
