# admin-web-bootstrap — Proposal

## Why

`mcp-server-management-ui` change 落地 8 阶段（brainstorm / proposal / design / specs / tasks / plan / apply / verify / retrospective）完毕，前置门 0.1 验 `web/admin-web/package.json` 存在——但当时仓库前端代码尚未就位。该 change 的 task 7.1-7.8（前端组件）+ task 8.1-8.2（Playwright E2E）共 10 个 task **强依赖** `web/admin-web/` 存在。

不改这个：要么把 mcp-server-management-ui 的 task 7-8 全砍（违反"前后端同步"openspec/config.yaml 规则），要么等下个 session 重新解决路径——两个都不优。

改：开本 change 落地**最小前端骨架**（Vite + React 18 + TS strict + SWR + 11 个菜单 static 占位 + 1 个 Playwright smoke E2E），**不引业务逻辑**，让 `web/admin-web/` 可被后续 change mount。视觉 1:1 复用 `docs/prototype.html`（已 4562 行 tailwind-ish 主题）。

参考基线：`docs/prototype.html:1-100`（HTML 入口 + tailwind 主题类）+ `docs/prototype.html:300-450`（左侧导航 11 个 menu item）+ `docs/prototype.html:4112-4164`（MCP 工具页 — 后续 `mcp-server-management-ui` 实现）。

## What Changes

- **新增** `web/admin-web/` 目录，含 Vite 5 + React 18 + TypeScript strict + Tailwind CSS 3.4 + React Router 6 + SWR + react-hook-form + zod + Vitest + Playwright 全栈配置。
- **新增** `web/admin-web/tailwind.config.js`：复用 `docs/prototype.html` 的色板（ink-50/100/200/.../900 + brand-500/600）作为 Tailwind theme extension，1:1 视觉。
- **新增** `web/admin-web/src/components/SideNav.tsx`：复刻 prototype.html 左侧导航（11 个 menu item：工作流 / Agent / 知识库 / 模板广场 / 团队共享 / 插件市场 / 模型管理 / 通道管理 / 凭证管理 / 技能管理 / MCP 工具 / 中间件链 / 监控 / 日志；本 change 全 visible，后续 change 改 role-aware）。
- **新增** `web/admin-web/src/components/AppShell.tsx`：复刻 prototype.html 的 sidebar + main 双栏布局。
- **新增** `web/admin-web/src/views/PlaceholderView.tsx`：每个未实现 menu item 的占位视图（"Coming soon — 由 <后续 change 名> 落地"卡片）。
- **新增** `web/admin-web/src/router/index.tsx`：11 个路由 + `/` 默认重定向到 `/workflow`。
- **新增** `web/admin-web/src/api/health.ts`：与 `services/mcp` 联调的最小 client（GET `/healthz`），SWR 5s 轮询，作为后续 change 的引用模板。
- **新增** `web/admin-web/src/main.tsx` + `App.tsx` + `index.html`：Vite 入口。
- **新增** `web/admin-web/tests/unit/`：Vitest 1 个 smoke（`AppShell 渲染 14 个菜单项`）。
- **新增** `web/admin-web/e2e/admin-web-bootstrap.spec.ts`：Playwright 1 个 E2E（打开 `/mcp-tools` → 看到 SideNav + 占位视图 + "Coming soon" 文案）。
- **新增** `web/admin-web/{package.json, tsconfig.json, vite.config.ts, postcss.config.js, .gitignore, README.md, playwright.config.ts, vitest.config.ts}`。
- **修改** `.gitignore`：添加 `web/admin-web/{node_modules, dist, .vite, coverage, test-results, playwright-report}` 排除。
- **不** 引 docker-compose 容器（admin-web 由后续 `admin-web-deploy` change 走 nginx 化）。
- **不** 引业务逻辑 / 鉴权 / 凭据（auth 由后续 `credential` change 落地）。
- **不** 引 npm/yarn（用 pnpm，符合 openspec/config.yaml §62 + 用户偏好）。

## Capabilities

### New Capabilities

- `vite-bootstrap`：`web/admin-web/package.json` + Vite 5 + dev server 启动 + 1 个空 `<div id="root">` 入口。**前端** = N/A（基础设施），**后端** = N/A，**豁免** = 该 capability 是基础脚手架，无 UI/业务/协议场景。
- `tailwind-theme-prototype-sync`：把 `docs/prototype.html` 的色板映射到 Tailwind theme。**前端** = `tailwind.config.js` + `index.html` 引入，**后端** = N/A，**豁免** = 纯配置无业务。
- `side-nav-shell`：11 个 menu item 的 SideNav 组件 + AppShell 布局。**前端** = 含，**后端** = N/A，**豁免** = UI shell 组件（纯前端，无 API 依赖）。
- `route-skeleton`：React Router 6 + 11 条路由 + `/` 重定向到 `/workflow`。**前端** = 含，**后端** = N/A，**豁免** = UI 路由（无 API 依赖）。
- `placeholder-view`：未实现 menu item 的占位视图。**前端** = 含，**后端** = N/A，**豁免** = UI 静态内容。
- `playwright-smoke`：Playwright 配置 + 1 个 E2E（打开 /mcp-tools → 验证 SideNav + 占位）。**前端** = 含，**后端** = N/A，**豁免** = 测试基础设施。

### Modified Capabilities

无。本 change 是 additive；不动 `mcp-server-management-ui` 的任何 spec。

## Impact

- **代码层**：
  - `web/admin-web/package.json`（新）：pnpm 项目文件
  - `web/admin-web/vite.config.ts`（新）：React + path alias
  - `web/admin-web/tsconfig.json`（新）：strict mode + path alias
  - `web/admin-web/tailwind.config.js`（新）：prototype.html 色板
  - `web/admin-web/postcss.config.js`（新）
  - `web/admin-web/index.html`（新）：Vite 入口
  - `web/admin-web/src/main.tsx`（新）
  - `web/admin-web/src/App.tsx`（新）
  - `web/admin-web/src/components/SideNav.tsx`（新）
  - `web/admin-web/src/components/AppShell.tsx`（新）
  - `web/admin-web/src/views/PlaceholderView.tsx`（新）
  - `web/admin-web/src/router/index.tsx`（新）
  - `web/admin-web/src/api/health.ts`（新）
  - `web/admin-web/src/types/index.ts`（新）
  - `web/admin-web/tests/unit/AppShell.test.tsx`（新）
  - `web/admin-web/e2e/admin-web-bootstrap.spec.ts`（新）
  - `web/admin-web/playwright.config.ts`（新）
  - `web/admin-web/vitest.config.ts`（新）
  - `web/admin-web/.gitignore`（新）
  - `web/admin-web/README.md`（新）
- **依赖**（pnpm 新增）：
  - runtime: `react@18`, `react-dom@18`, `react-router-dom@6`, `swr@2`, `react-hook-form@7`, `zod@3`, `react-icons/fa6`, `clsx@2`
  - dev: `vite@5`, `@vitejs/plugin-react@4`, `typescript@5`, `@types/react`, `@types/react-dom`, `tailwindcss@3`, `postcss`, `autoprefixer`, `vitest@1`, `@testing-library/react@14`, `@testing-library/jest-dom`, `jsdom`, `@playwright/test@1.40`, `vite-tsconfig-paths@4`
- **.gitignore**：在仓库根 `.gitignore` 添加 `web/admin-web/node_modules/`, `web/admin-web/dist/`, `web/admin-web/.vite/`, `web/admin-web/coverage/`, `web/admin-web/test-results/`, `web/admin-web/playwright-report/`。
- **docker-compose**：**不**改。
- **端口**：admin-web 用 5173（Vite dev server 默认），后续 V1.0 nginx 化时再占端口。
- **CLAUDE.md 端口表**：**不**改（5173 是 dev port，不进容器端口表）。

## Non-goals

- **不**做业务逻辑（mcp 注册 / workflow 编辑 / RAG / Agent 配置 / 任何业务 API 调用）
- **不**做鉴权 / 凭据（auth 由后续 `credential` change 落地）
- **不**做 SSR / Next.js 集成
- **不**做 docker-compose 容器化（admin-web 由后续 `admin-web-deploy` change 走 nginx）
- **不**做 i18n（中文 hard-code，prototype.html 也无 i18n）
- **不**做主题切换（prototype.html 仅 light 主题）
- **不**做无障碍深度优化（基础 semantic HTML + aria-label，V1.0 深度 a11y 后续）
- **不**做 mobile responsive 深度优化（admin-web 是桌面工具，prototype.html 桌面优先）
- **不**做 npm/yarn（用 pnpm）
- **不**做 Jest/Cypress（Vite 生态用 Vitest + Playwright）
- **不**做 admin-web 与后端的真实联调（除 `/healthz` 探活；mcp server 实际 API 由 `mcp-server-management-ui` 接入）
- **不**改 `mcp-server-management-ui` 的 8 阶段产物（artifacts 都已落地，不动）
