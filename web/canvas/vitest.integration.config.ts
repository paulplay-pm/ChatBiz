// Vitest integration config — separate from unit config.
//
// Why: vitest default include is '**/*.{test,spec}.{ts,tsx}' which would
// swallow the e2e/ directory and clash with Playwright's test() runner.
// See admin-bootstrap retrospective §2 — same issue there.
//
// The integration tests run against the real test compose stack at
// http://localhost:5173. globalSetup waits for /healthz to return 200
// before any test runs.

import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') },
  },
  test: {
    include: ['tests/integration/**/*.spec.ts'],
    exclude: ['e2e/**', 'node_modules/**', 'dist/**', 'tests/unit/**'],
    environment: 'node',
    testTimeout: 30_000,
    hookTimeout: 30_000,
    globalSetup: ['./tests/integration/global-setup.ts'],
  },
});
