# admin-web-bootstrap — Tasks

> **Scope**：建 `web/admin-web/` 最小骨架。**不**引业务逻辑，**不**引鉴权，**不**引 docker-compose 容器。
> 完成后 `mcp-server-management-ui` 的 task 7.1-7.8 + 8.1-8.2 解 BLOCKED。

## 0. 前置门

- [x] 0.1 验 `node --version >= 20` + `pnpm --version >= 8`。当前环境：node 24.14.1 / pnpm 10.33.0。验：`node -v` + `pnpm -v`。

## 1. 项目 init

- [x] 1.1 `pnpm create vite web/admin-web --template react-ts`（或手写 `package.json` + `tsconfig.json`，避免模板带入不必要文件）。**编码规范**：用 Vite 5 + React 18 模板。**安全清单**：不引过期依赖。验：`cd web/admin-web && pnpm install` 0 错。
- [x] 1.2 改 `package.json` 加 `"type": "module"` + `"engines": { "node": ">=20" }` + 删模板的 README/CSS/logo。**编码规范**：dependencies 分类（runtime vs dev）。验：`cat package.json` 包含所有字段。
- [x] 1.3 加 `tsconfig.node.json`（Vite 官方推荐）+ `tsconfig.json` 开 `"strict": true` + `"noUncheckedIndexedAccess": true` + `"exactOptionalPropertyTypes": true` + `paths: { "@/*": ["./src/*"] }`。**安全清单**：禁止 `// @ts-ignore`（用 `// @ts-expect-error <reason>` 替代）。验：`pnpm tsc --noEmit` 0 错。

## 2. Vite + path alias

- [x] 2.1 写 `web/admin-web/vite.config.ts`：`@vitejs/plugin-react` + `vite-tsconfig-paths` + 别名 `@` → `./src`。**编码规范**：TypeScript 配置，不引 JS 文件。验：`pnpm dev` 启动 2s 内。
- [x] 2.2 写 `web/admin-web/index.html`：Vite 入口，`<div id="root">` + `<script type="module" src="/src/main.tsx">`。**安全清单**：不引外部 CDN。验：浏览器打开 `http://localhost:5173` 看到白屏（无错误）。

## 3. Tailwind + 色板

- [x] 3.1 装 `tailwindcss@^3.4` + `postcss` + `autoprefixer`（devDependency）+ `pnpm dlx tailwindcss init -p`。验：`tailwind.config.js` + `postcss.config.js` 生成。
- [x] 3.2 改 `tailwind.config.js`：`content: ['./index.html', './src/**/*.{ts,tsx}']` + theme.extend.colors 加 `ink-50~900` + `brand-500~900`（10 + 5 = 15 个色值，spec `tailwind-theme-prototype-sync` § Requirement: prototype.html ink palette is mapped）。验：`pnpm build` 后 `text-ink-900` 编译为 `#111827`。
- [x] 3.3 写 `web/admin-web/src/index.css`：`@tailwind base; @tailwind components; @tailwind utilities;` + 删模板的 `App.css`。验：`pnpm dev` 浏览器看到 Tailwind reset。
- [x] 3.4 装 `@fortawesome/fontawesome-free@^6`（dependency）+ 在 `main.tsx` 导入 `@fortawesome/fontawesome-free/css/all.min.css`。验：`<i class="fas fa-robot">` 渲染图标。

## 4. AppShell + SideNav

- [x] 4.1 写 `web/admin-web/src/components/SideNav.tsx`：14 menu item 列表（spec `side-nav-shell` § Requirement: SideNav renders 14 menu items）+ `<NavLink>` from react-router-dom + active class `bg-brand-50 text-brand-600`。**编码规范**：TypeScript strict + 用 `clsx` 拼接 className。验：浏览器看到 14 个菜单项。
- [x] 4.2 写 `web/admin-web/src/components/AppShell.tsx`：`<div class="flex h-screen">` + `<aside class="w-64 ...">` + `<main class="flex-1">` + header bar + content `<Outlet />`。**安全清单**：用 semantic HTML（`<aside>` `<main>` `<nav>`）。验：浏览器看到双栏布局。
- [x] 4.3 写 `web/admin-web/src/main.tsx` + `src/App.tsx`：mount React + RouterProvider + import index.css + import fontawesome CSS。验：浏览器看到双栏 + 占位。

## 5. Router + PlaceholderView

- [x] 5.1 装 `react-router-dom@^6`。验：`pnpm list react-router-dom` 显示版本。
- [x] 5.2 写 `web/admin-web/src/views/PlaceholderView.tsx`：接受 `{ menuItemName, changeName }` props，渲染 `+` icon + "🚧 <name> 即将推出" + "由后续 change <change> 落地"（spec `placeholder-view`）。验：浏览器 `/mcp-tools` 看到占位卡。
- [x] 5.3 写 `web/admin-web/src/router/index.tsx`：`createBrowserRouter` + 15 个 routes（14 + `/` redirect） + 14 个 PlaceholderView（每个不同 menuItemName/changeName） + lazy import + `routes: RouteObject[]` export。验：浏览器深链 `/mcp-tools` 看到对应占位 + SideNav 激活。

## 6. SWR + health check

- [x] 6.1 装 `swr@^2`（dependency）。验：`pnpm list swr` 显示版本。
- [x] 6.2 写 `web/admin-web/src/api/health.ts`：`useHealth()` hook 用 SWR 调 `GET /healthz`（fetch `http://localhost:8004/healthz`，与 `services/mcp` 容器端口对齐）+ 5s 轮询。**安全清单**：失败 fallback 返回 `{ status: "unknown" }`，不抛。验：浏览器 console 看到 fetch 请求（即使 404 也不崩）。
- [x] 6.3 改 `AppShell.tsx` header bar 加一个 `<HealthIndicator>` 小组件，从 `useHealth()` 读 status 渲染绿/灰/红圆点。**安全清单**：圆点旁 aria-label "服务健康"。验：浏览器看到圆点 + tooltip。

## 7. 类型 + 导出

- [x] 7.1 写 `web/admin-web/src/types/index.ts`：export `MenuItem = { name: string; href: string; icon: string; changeName: string }` + `HealthStatus = "healthy" | "degraded" | "down" | "unknown"`。**编码规范**：用 `as const` 收窄字面量类型。验：`tsc --noEmit` 0 错。
- [x] 7.2 写 `web/admin-web/.gitignore`：`node_modules/`, `dist/`, `.vite/`, `coverage/`, `test-results/`, `playwright-report/`, `*.log`, `.DS_Store`。验：`git status` 不列这些。
- [x] 7.3 写 `web/admin-web/README.md`：开发命令（`pnpm dev` / `pnpm build` / `pnpm test` / `pnpm e2e`）+ 目录结构 + 后续 change 怎么 mount。**安全清单**：不暴露任何 env var / 凭据。验：手读通顺。

## 8. Vitest + Playwright

- [x] 8.1 装 `vitest@^1` + `jsdom@^24` + `@testing-library/react@^14` + `@testing-library/jest-dom@^6`（devDependency）。验：`pnpm list vitest` 显示版本。
- [x] 8.2 写 `web/admin-web/vitest.config.ts`：复用 vite.config.ts 的 alias + `test.environment: 'jsdom'` + `test.setupFiles: ['./tests/unit/setup.ts']`。验：`pnpm test` 启动 vitest。
- [x] 8.3 写 `web/admin-web/tests/unit/setup.ts`：`import '@testing-library/jest-dom'`。验：vitest 启动不报 "no matchers registered"。
- [x] 8.4 写 `web/admin-web/tests/unit/AppShell.test.tsx`：1 个 test 验 14 menu item + 14 href（spec `playwright-smoke` § Requirement: Bootstrap unit test exists）。验：`pnpm test` 1/1 pass。
- [x] 8.5 装 `@playwright/test@^1.40`（devDependency）。验：`pnpm list @playwright/test` 显示版本。
- [x] 8.6 写 `web/admin-web/playwright.config.ts`（spec `playwright-smoke` § Requirement: Playwright is configured）。验：`pnpm e2e` 启动 playwright。
- [x] 8.7 写 `web/admin-web/e2e/admin-web-bootstrap.spec.ts`：1 个 E2E 打开 `/mcp-tools` 验 SideNav + 占位（spec `playwright-smoke` § Requirement: Bootstrap E2E smoke test exists）。**安全清单**：用 `getByRole` / `getByText` 而非 CSS selector。验：`pnpm e2e` 1/1 pass。
- [x] 8.8 跑 `npx playwright install chromium` 下载浏览器（首次需要）。验：`~/.cache/ms-playwright/chromium-*` 存在。

## 9. 收尾

- [x] 9.1 跑全量验证：`pnpm tsc --noEmit` 0 错 + `pnpm build` 0 错 + `pnpm test` 1/1 + `pnpm e2e` 1/1。验：所有命令 exit 0。
- [x] 9.2 改仓库根 `.gitignore` 加 `web/admin-web/node_modules/` 等（task 7.2 已经在 admin-web 内 .gitignore，再在根保险）。验：`git status` 不列 `web/admin-web/node_modules/`。
- [x] 9.3 写 `openspec/changes/admin-web-bootstrap/retrospective.md`（apply 后填，spec `superpowers-bridge` § retrospective 模板）。验：archive 流程要求。
- [x] 9.4 跑 `openspec schema validate admin-web-bootstrap`。验：返 0 exit code。
- [x] 9.5 更新 `mcp-server-management-ui` 的 tasks.md：在 task 0.1 加注释 "由 admin-web-bootstrap archive 后验 `web/admin-web/package.json` 存在"。验：grep 该路径在 tasks.md。

## 配对验证总结（openspec/config.yaml 规则第 56 行）

| 编码 task | 配对验证 task | 同 commit |
|---|---|---|
| 1.1-1.3 项目 init | 1.3 末 `tsc --noEmit` | ✓ |
| 2.1-2.2 Vite + 入口 | 2.2 末 `pnpm dev` 启动 | ✓ |
| 3.1-3.4 Tailwind + 色板 | 3.2 末 `pnpm build` 编译 | ✓ |
| 4.1-4.3 AppShell + SideNav | 4.3 末浏览器看到双栏 | (manual) |
| 5.1-5.3 Router + Placeholder | 5.3 末浏览器深链 | (manual) |
| 6.1-6.3 SWR + health | 6.2 末 console fetch | ✓ |
| 7.1-7.3 类型 + 导出 | 7.3 末手读 README | ✓ |
| 8.1-8.8 Vitest + Playwright | 8.4 末 1/1 + 8.7 末 1/1 | ✓ |
| 9.1-9.5 收尾 | 9.4 末 validate | ✓ |

## 时间估计

| Section | Tasks | Hours |
|---|---|---|
| 0 前置门 | 1 | 0.1h |
| 1 项目 init | 3 | 1h |
| 2 Vite | 2 | 0.5h |
| 3 Tailwind | 4 | 1h |
| 4 AppShell | 3 | 1.5h |
| 5 Router | 3 | 1.5h |
| 6 SWR | 3 | 0.5h |
| 7 类型 | 3 | 0.5h |
| 8 测试 | 8 | 2h |
| 9 收尾 | 5 | 0.5h |
| **Total** | **33** | **~9h** |
