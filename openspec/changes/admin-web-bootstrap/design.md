# admin-web-bootstrap — Design

## Context

仓库当前 0 行源代码。`mcp-server-management-ui` change 落地完整 8 阶段（brainstorm / proposal / design / specs / tasks / plan）+ tasks 36 项，**前置门 0.1 验 `web/admin-web/package.json` 存在**——但当时 `web/admin-web/` 尚未就位。该 change 的 task 7.1-7.8（前端组件）+ task 8.1-8.2（Playwright E2E）共 10 个 task **强依赖** `web/admin-web/` 存在。

本 change 解 `mcp-server-management-ui` 的 BLOCKED——**只**建前端骨架（Vite + React 18 + TS strict + SWR + 11 个菜单 static 占位 + 1 个 Playwright smoke E2E），**不**引业务逻辑，**不**引鉴权，**不**引 docker-compose 容器。

上游基线：
- `docs/prototype.html`（4562 行 HTML 原型，复用其色板 + 图标 + 布局）
- `docs/architecture.md §4.3.6` 插件运行时（前端 admin-web 入口）
- `docs/prd.md §4.4.1` 插件管理（左侧导航 "插件市场" 是入口之一）
- `openspec/config.yaml §62` 前端规范（React 组件化 + TypeScript 严格 + Hooks + 状态隔离）

12 个 eng-review 决策**未**被本 change 触发（纯前端骨架）。引用：
- `openspec/config.yaml §62` 前端规范
- `Test #1` 部分触发（提供 Playwright + Vitest 框架，不写实际测试）

## Goals / Non-Goals

**Goals：**
- `web/admin-web/` 目录存在 + `pnpm install` 成功 + `pnpm dev` 启动 Vite 5 dev server 在 `localhost:5173`
- 11 个 menu item 在 SideNav 显示，prototype.html 视觉 1:1
- 点击任一未实现 menu item → 中央显示 "Coming soon — 由 <后续 change> 落地" 占位卡片
- `pnpm test`（vitest）通过 ≥1 个 smoke 测试
- `pnpm e2e`（playwright）通过 ≥1 个 E2E：打开 /mcp-tools 看到 SideNav + 占位
- TypeScript strict mode 0 错（`tsc --noEmit`）
- ESLint 0 错（用 Vite 默认 + react/recommended）

**Non-Goals：**
- 见 `proposal.md` Non-goals 节
- **不**触发 12 个 eng-review 决策（不涉及 LLM / 工作流 / 记忆 / MCP / 错误边界 / 性能 / 存储量）
- **不**做业务逻辑

## Decisions

### D1：Vite 5 + React 18

**Context**：构建工具选择。prototype.html 是静态 HTML，admin-web 要 React 化。

**选项**：
- A. **（已选）** Vite 5 + React 18 + plugin-react。启动快，HMR 稳，dev server 1s 内就绪。
- B. Next.js 15：拒绝——admin-web 是企业内部 SPA，SSR 反而引入 Node runtime；eng-review §4.4 不列 Next.js。
- C. 纯 HTML + ESM：拒绝——与 TypeScript 严格 + Hooks + 状态隔离（openspec/config.yaml §62）冲突。

**结论**：选 A。

### D2：Tailwind CSS 3.4（与 prototype.html 视觉 1:1）

**Context**：样式方案。prototype.html 已用 tailwind utility 模式（`<div class="bg-white rounded-xl border border-ink-200 p-5">`）。

**选项**：
- A. **（已选）** Tailwind 3.4 + `tailwind.config.js` 把 prototype.html 色板（ink-50 ~ ink-900, brand-500 ~ brand-900）映射成 theme extension，FontAwesome 6 通过 `@fortawesome/fontawesome-free` 提供 `fas fa-*` class 兼容。
- B. CSS Modules：拒绝——与 prototype.html 视觉对齐需重写所有 class，token 对齐工作量大。
- C. styled-components / emotion：拒绝——runtime CSS-in-JS 增加 bundle 体积；admin-web 不需要动态主题。

**色板映射**（从 prototype.html 采样）：
- `ink-50` = `#f9fafb` (背景)
- `ink-100` = `#f3f4f6` (次级背景)
- `ink-200` = `#e5e7eb` (边框)
- `ink-300` = `#d1d5db` (虚线边框)
- `ink-400` = `#9ca3af` (次要文字 / 图标)
- `ink-500` = `#6b7280` (中等文字)
- `ink-600` = `#4b5563` (次要标题)
- `ink-700` = `#374151` (主要标题)
- `ink-800` = `#1f2937` (深色文字)
- `ink-900` = `#111827` (主文字)
- `brand-500` = `#3b82f6` (主品牌色 / 蓝色)
- `brand-600` = `#2563eb` (按钮 hover)
- `brand-700` = `#1d4ed8` (深色)

**结论**：选 A。

### D3：React Router 6（不用 TanStack Router）

**Context**：路由方案。11 个 menu item 需要稳定路由 + 深链接。

**选项**：
- A. **（已选）** React Router 6 + `createBrowserRouter` + nested route + lazy import。
- B. TanStack Router：拒绝——type-safe routing 强但学习成本高，本 change scope 不需要。
- C. state-driven view switch（`view-section` 隐藏/显示）：拒绝——违反"组件化 + 状态隔离"；路由要支持深链接。

**结论**：选 A。

### D4：SWR + React Context（不引 Redux/Zustand）

**Context**：状态管理。

**选项**：
- A. **（已选）** 服务端状态走 SWR（缓存 + 重新验证 + 5s 轮询），用户/权限/UI 状态走 React Context（`UserProvider` / `ThemeProvider`）。
- B. Redux Toolkit：拒绝——admin-web 早期不需要复杂状态机；后续真有再加。
- C. Zustand：拒绝——SWR + Context 已能覆盖 80% 场景，引入 Zustand 多一个概念。

**结论**：选 A。

### D5：react-hook-form + zod

**Context**：表单方案。`mcp-server-management-ui` task 7.5 已规划用 react-hook-form + zod resolver。admin-web 自身**不**有表单（骨架无业务），但**预装**让后续 change 直接用。

**选项**：
- A. **（已选）** 装 `react-hook-form@7` + `zod@3` + `@hookform/resolvers@3` 作为 dependency，**不**写实际 form（后续 change 写）。
- B. 不装：拒绝——后续 mcp-server-management-ui task 7.5 要用，admin-web 必须先预装。
- C. Formik：拒绝——API 旧；react-hook-form 更现代、性能更好。

**结论**：选 A（**预装不写**）。

### D6：FontAwesome 6 Solid（与 prototype.html 视觉一致）

**Context**：图标库。prototype.html 用 `<i class="fas fa-file-code">` FontAwesome。

**选项**：
- A. **（已选）** `@fortawesome/fontawesome-free@6` 全量包（~10MB，但 admin-web 内部 Vite build tree-shake）+ `@fortawesome/react-fontawesome` React 组件。**Tree-shake 后** bundle 增量 ~50KB。
- B. `react-icons/fa6`：拒绝——react-icons 用 import path，className `fas fa-*` 不生效，与 prototype.html 视觉 1:1 复制要重写所有 class。
- C. lucide-react：拒绝——线条图标 vs fa 实体图标视觉不一致。
- D. 自定义 SVG：拒绝——11+ 个图标每个要画。

**结论**：选 A。

### D7：Vitest + Playwright（不引 Jest/Cypress）

**Context**：测试框架。eng-review Test #1 强制 3 层金字塔（pytest / 集成 / Playwright E2E）。

**选项**：
- A. **（已选）** Vitest 1.x（Vite 原生）+ Playwright 1.40+。配置零成本，Vite ecosystem 一致。
- B. Jest + Cypress：拒绝——与 Vite 集成差；Cypress 慢。
- C. 不写测试：拒绝——eng-review Test #1 强制 + 后续 change 都要用。

**Vitest 配置要点**：
- `vitest.config.ts` 复用 vite.config.ts 的 alias
- `tests/unit/setup.ts` 引 `@testing-library/jest-dom` 匹配器
- 1 个 smoke: `AppShell renders 14 menu items`

**Playwright 配置要点**：
- `playwright.config.ts` 设 `baseURL: http://localhost:5173`, `webServer: { command: 'pnpm dev', port: 5173, reuseExistingServer: !process.env.CI }`
- 1 个 E2E: `admin-web-bootstrap.spec.ts` 打开 `/mcp-tools` 验证 SideNav 14 菜单 + "Coming soon" 文案

**结论**：选 A。

### D8：浏览器矩阵 = Chromium only

**Context**：E2E 浏览器覆盖。

**选项**：
- A. **（已选）** Chromium headless only。
- B. Chromium + Firefox + WebKit：拒绝——MVP 阶段性价比低；admin-web 是企业内部工具，不面向 C 端多浏览器；eng-review Test #1 没说多浏览器要求。

**结论**：选 A。

### D9：11 个 menu item 全部 static 占位

**Context**：左侧导航菜单策略。

**选项**：
- A. **（已选）** 11 个 menu item 全部 visible（无权限过滤）+ 点击未实现 menu item 跳 `<slug>` 路由 + 中央显示 "Coming soon — 由 <后续 change> 落地" 占位卡片。
- B. 只挂 MCP 工具菜单：拒绝——违反"前端规范：状态隔离"精神；admin-web 是 shell，业务 change 各自挂页面。
- C. 不挂菜单，只挂中央视图：拒绝——prototype.html 有完整左侧导航 shell，admin-web 复刻才有 1:1 视觉。

**11 个 menu item 列表**（从 prototype.html:235-410 采样）：
1. 工作流 → `/workflow` (后续 `workflow-engine` change)
2. Agent → `/agent` (后续 `agent-runtime` change)
3. 知识库 → `/knowledge` (后续 `knowledge-base` change)
4. 模板广场 → `/templates`
5. 团队共享 → `/team`
6. 插件市场 → `/plugins` (后续 `plugin-marketplace` change)
7. 模型管理 → `/models`
8. 通道管理 → `/channels`
9. 凭证管理 → `/credentials` (后续 `credential` change)
10. 技能管理 → `/skills`
11. MCP 工具 → `/mcp-tools` (后续 `mcp-server-management-ui` change)
12. 中间件链 → `/middleware`
13. 监控 → `/monitoring`
14. 日志 → `/logs`

**实际是 14 个 menu item**（draft 算错了，重数 prototype.html 后修正）。

**结论**：选 A。

### D10：不引 docker-compose 容器

**Context**：admin-web 的部署形态。

**选项**：
- A. **（已选）** 本 change 不引容器；admin-web 留作 `web/admin-web/` 源码 + 配置；`pnpm dev` 即可 dev；后续 V1.0 由 `admin-web-deploy` change 加 nginx 容器。
- B. 立即加 admin-web nginx 容器：拒绝——MVP 不需要；本 change scope 收敛。

**结论**：选 A。

### D11：TypeScript strict + path alias @/*

**Context**：TypeScript 配置。

**选项**：
- A. **（已选）** `tsconfig.json` 开 `"strict": true` + `"noUncheckedIndexedAccess": true` + `"exactOptionalPropertyTypes": true`；`vite-tsconfig-paths` 插件读 tsconfig 配 path alias `@/* → src/*`。
- B. 关闭 strict：拒绝——openspec/config.yaml §62 "TypeScript 严格" 强制。
- C. 不用 path alias：拒绝——后续 change 跨文件 import 难读。

**结论**：选 A。

### D12：i18n 策略 = 中文 hard-code

**Context**：国际化。

**选项**：
- A. **（已选）** 中文 hard-code（与 prototype.html 一致），不引 i18n 库。V1.0+ 走 react-i18next。
- B. 立即引 react-i18next：拒绝——MVP scope 不需要，prototype.html 也没 i18n。

**结论**：选 A。

## Risks / Trade-offs

- **[Risk] pnpm install 失败（node 版本不匹配 / 锁文件漂移）** → Mitigation：`engines.node = ">=20"` 在 package.json；lockfile commit。
- **[Risk] Playwright 浏览器下载失败（CI 环境无外网）** → Mitigation：`PLAYWRIGHT_BROWSERS_PATH=0` + `npx playwright install chromium` 在 README 文档化；CI 后续配。
- **[Risk] Tailwind config 与 prototype.html 色板不完全 1:1** → Mitigation：D2 列了完整色板映射表；task 1.4 配 visual regression 暂不写（V1.0 写）。
- **[Risk] ESLint 报警（如 react-hooks/exhaustive-deps）** → Mitigation：用 Vite 默认 + react/recommended + react-hooks 规则，0 错才能 commit。
- **[Risk] admin-web 与 prototype.html 视觉漂移** → Mitigation：task 7.1-7.8 后续 change 落地时复用本骨架 SideNav，不重写。
- **[Risk] 路径 alias `@/*` 与 mcp-server-management-ui 的 `web/admin-web/src/types/mcp.ts` 引用冲突** → Mitigation：所有跨文件 import 走 `@/types/...`（不要相对路径），由 ESLint 规则强制。

## Migration Plan

**无历史数据可迁**——0 行源代码，admin-web 从无到有。

**Deploy steps**（dev 环境）：
1. `cd web/admin-web && pnpm install`
2. `pnpm dev` → http://localhost:5173 看到 SideNav + 占位
3. `pnpm test` → 1/1 vitest pass
4. `pnpm e2e` → 1/1 playwright pass

**Production deploy**：本 change **不**含——后续 `admin-web-deploy` change 走 `pnpm build` → nginx 容器化 → docker-compose。

**Rollback**：`git revert <commit>` 即可，admin-web 不影响任何已落地 service。

## Open Questions

- OQ1：Vite dev server 是否需要 `--host 0.0.0.0` 让 docker 容器外访问？**当前决定**：不需要，dev 用 `localhost:5173` 即可。后续 V1.0 docker 化时再考虑。
- OQ2：Tailwind config 放 `web/admin-web/tailwind.config.js` 还是仓库根？**当前决定**：前者——admin-web 是独立 module。
- OQ3：TypeScript path alias `@/*` vs `~/*`？**当前决定**：`@/*`（Vite + Next.js 业界主流）。
- OQ4：左侧导航 14 个 menu item 立即都 visible 还是只 visible 已实现？**当前决定**：全 visible（本 change 全部占位）；后续 change 改 role-aware。
- OQ5：`AppShell` 用 `useState` 控制 mobile drawer 还是 CSS-only？**当前决定**：CSS-only（`lg:hidden` + `lg:block`），admin-web 桌面优先。
