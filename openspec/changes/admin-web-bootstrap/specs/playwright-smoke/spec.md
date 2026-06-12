# playwright-smoke

**Frontend Scope: 含前端**（Playwright 配置 + 1 个 E2E smoke）

**Impact**（被谁消费）：
- 被 CI 消费（未来 V1.0 接入 CI 后跑）
- 被本地 dev 消费（`pnpm e2e` 验骨架可用）
- 未来被所有"前端业务 change"复用（添加新 E2E）

## ADDED Requirements

### Requirement: Playwright is configured

The system MUST have `web/admin-web/playwright.config.ts` with:
- `testDir: './e2e'`
- `timeout: 30_000`
- `fullyParallel: true`
- `use: { baseURL: 'http://localhost:5173', headless: true, screenshot: 'only-on-failure' }`
- `webServer: { command: 'pnpm dev', port: 5173, reuseExistingServer: !process.env.CI, timeout: 30_000 }`
- `projects: [{ name: 'chromium', use: { browserName: 'chromium' } }]`

`@playwright/test@^1.40.0` MUST be in `devDependencies`.

#### Scenario: Playwright launches
- **WHEN** developer runs `pnpm e2e`
- **THEN** Playwright starts Vite dev server (if not running), opens Chromium, runs e2e suite

#### Scenario: CI mode
- **WHEN** `CI=true` env var is set
- **THEN** Playwright does NOT reuse existing server, fails fast if port busy

### Requirement: Bootstrap E2E smoke test exists

The file `web/admin-web/e2e/admin-web-bootstrap.spec.ts` MUST contain exactly 1 test scenario: "Open /mcp-tools and verify SideNav + Placeholder". The test MUST:
1. `await page.goto('/mcp-tools')`
2. Verify URL is `/mcp-tools`
3. Verify SideNav is visible (`await expect(page.getByRole('navigation')).toBeVisible()`)
4. Verify "MCP 工具" menu item is highlighted (`await expect(page.getByRole('link', { name: 'MCP 工具' })).toHaveAttribute('aria-current', 'page')`)
5. Verify "Coming soon" text appears (`await expect(page.getByText(/即将推出/)).toBeVisible()`)

#### Scenario: E2E passes
- **WHEN** developer runs `pnpm e2e`
- **THEN** 1/1 test passes in chromium

#### Scenario: E2E fails on broken SideNav
- **WHEN** developer deletes the "MCP 工具" menu item from SideNav
- **THEN** the E2E test fails with assertion error "expected element to have aria-current=page"

### Requirement: Vitest is configured

The system MUST have `web/admin-web/vitest.config.ts` with:
- `test.environment: 'jsdom'`
- `test.setupFiles: ['./tests/unit/setup.ts']`
- `test.globals: true`
- `resolve.alias` matching Vite (`@` → `./src`)

`vitest@^1.0.0` + `jsdom@^24.0.0` + `@testing-library/react@^14.0.0` + `@testing-library/jest-dom@^6.0.0` MUST be in `devDependencies`.

`tests/unit/setup.ts` MUST `import '@testing-library/jest-dom'`.

#### Scenario: Vitest launches
- **WHEN** developer runs `pnpm test`
- **THEN** Vitest runs and reports at least 1 test

### Requirement: Bootstrap unit test exists

The file `web/admin-web/tests/unit/AppShell.test.tsx` MUST contain 1 test:
- `renders 14 menu items`: render `<MemoryRouter><AppShell /></MemoryRouter>` and assert 14 `<a>` elements with the expected hrefs (`/workflow`, `/agent`, ..., `/logs`)

#### Scenario: Unit test passes
- **WHEN** developer runs `pnpm test`
- **THEN** 1/1 test passes

#### Scenario: Unit test fails on missing item
- **WHEN** developer removes the "MCP 工具" menu item from SideNav
- **THEN** the unit test fails with assertion error "expected 14 elements, got 13"
