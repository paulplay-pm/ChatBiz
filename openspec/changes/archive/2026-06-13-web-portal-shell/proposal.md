## Why

`web/` 下当前缺一个统一的"主框架"入口:`web/canvas` 已有 6 路由 + 24 单测 + 2 e2e,但登录后无全局侧栏、用户进 `/canvas/workflows` 看不到"控制台 / 知识库 / 凭证"等未来模块的入口;`web/admin` 由 `admin-web-bootstrap`(2026-06-12)落地骨架,缺主框架统一;`web/index.html` 跳板是 dev 期卡片,无登录态;`docs/prototype.html` 4562 行定义了完整设计语言(brand/ink 调色板、glass header、30+ 项侧栏、DM Sans/Space Mono 字体),但前端 0 行 portal 代码。

现在处理的原因:V2 (`canvas` 删 antd 改 tailwind) 与 V3 (`admin` 删 antd 改 tailwind) 都依赖 1 份共享 primitives 库(Button / Card / Modal / Form / Input / Sidebar / Toast),若先 V2 / V3,canvas 与 admin 会各自重写一遍相同组件;先 V1 落地 portal + primitives,V2 / V3 直接 import 复用,可避免重复实现。预期收益:(1) V2 / V3 删 antd 时 1/2 机械迁移工作被 portal primitives 覆盖;(2) portal 30+ 项占位菜单为 V1.0+ 各后端服务预留导航位,避免 V1.0 接入时再做 SPA 路由重构;(3) portal 独立 Vite dev server (5174),V1 期间独立可跑通、不阻塞 V2 / V3。

## What Changes

**1. 新建 `web/portal` 子应用(独立 Vite 构建)**

- From: `web/` 下没有 portal 入口,`web/index.html` 跳板是静态卡片
- To: 新建 `web/portal/`,含 `package.json` / `tsconfig.json` / `vite.config.ts` / `tailwind.config.js` / `postcss.config.js` / `index.html` / `src/{main,App,index.css}` / `src/data/menu.ts` / `src/components/{AppLayout,RequireAuth}.tsx` / `src/components/primitives/{Button,Card,MetricCard,StatusDot,Input,Form,Modal,Toast,useToast,Sidebar,SidebarItem,SidebarSection}.tsx` / `src/pages/{LoginPage,DashboardPage,ComingSoonPage}.tsx` / `src/router/index.tsx` / `tests/*.test.{ts,tsx}` / `e2e/portal-flow.spec.ts` / `playwright.config.ts` / `vitest.config.ts`
- Reason: V1 范围 — portal 单独跑通,后续 V2 / V3 复用 primitives
- Impact: 非破坏性 — V1 不动 canvas / admin / nginx.conf / Dockerfile / 任何已 archive 的 spec

**2. 设计 token 落地(prototype brand/ink)**

- From: prototype 的 brand/ink 调色板 + DM Sans / Space Mono 字体定义在 `docs/prototype.html:7-40`
- To: `web/portal/tailwind.config.js` 复制 prototype 完整 brand-50..900 / ink-50..950 + font-sans(DM Sans) + font-mono(Space Mono);`src/index.css` 引入 Google Fonts + `.glass` 工具类
- Reason: portal 视觉与 prototype 1:1 对齐;V2 / V3 直接复用同份 tailwind config
- Impact: V1 内部新增;canvas / admin 不动(V2 / V3 接管)

**3. portal 30+ 项侧栏菜单**

- From: prototype 中 30+ 项菜单 + 5 个 section 标题
- To: `web/portal/src/data/menu.ts` 导出 30+ 项 `MenuItem`(`id` / `label` / `icon` / `section` / `status: 'ready' | 'coming-soon'` / `href`)+ 5 个 `MenuSection`(`id` / `title`:`对话` / `工作流` / `Agent` / `知识库` / `系统设置`)
- Reason: 占位菜单允许提前评审导航信息架构;`status: 'ready'` 跳 `/canvas/<path>`(SPA navigate),`'coming-soon'` 跳 `/portal/coming-soon?from=<id>`
- Impact: V1 内部新增;`MenuItem` 类型在 V2 / V3 也复用

**4. portal 登录入口(沿用 canvas-auth dev fallback 契约)**

- From: 登录入口在 `web/canvas/src/pages/LoginPage.tsx`(antd 风格)
- To: portal `LoginPage` 沿用 `specs/canvas-auth/spec.md` 的 dev fallback(username 任意非空 + 任意密码 → 写 `localStorage['chatbiz.auth'] = JSON.stringify({ username, loginAt })`);canvas 现有 LoginPage **保留不动**(V2 才改)
- Reason: V1 不破坏 `canvas-auth` 契约;portal 登录后跳 `/portal/`(即 `/` 路由)
- Impact: V1 内部新增;canvas LoginPage 在 V1 期间仍是兜底(用户直接打开 `/canvas/workflows` 时仍用 canvas LoginPage)

**5. portal 主框架(顶部 glass header + 左侧 30+ 侧栏 + 右侧 Outlet)**

- From: 无
- To: `AppLayout` 固定顶部 glass header(brand-500 logo + DM Sans 标题)+ 左侧 `Sidebar`(30+ 项)+ 右侧 `<Outlet/>`
- Reason: 与 prototype 主框架 1:1 对齐
- Impact: V1 内部新增;V1 期间 canvas / admin 各自保留自身 Layout(V2 改造)

**6. 路由表 + 5 个页面**

- From: 无
- To: `web/portal/src/router/index.tsx` 定义 `/login` / `/` (Dashboard) / `/coming-soon` 3 个 portal 路由 + 1 个 `RequireAuth` 守卫 + 通配 fallback;Dashboard / ComingSoon / Login 3 个 page
- Reason: V1 单独跑通(独立 dev 5174,不依赖 nginx)
- Impact: V1 内部新增;canvas 现有 routes 不动

**7. primitives 库(被 V2 / V3 复用)**

- From: 无
- To: `web/portal/src/components/primitives/` 暴露 Button / Card / MetricCard / StatusDot / Input / Form / Modal / Toast(useToast hook)/ Sidebar / SidebarItem / SidebarSection,每个组件配 ≥1 个 vitest snapshot/test
- Reason: 替代 antd 的 `Button` / `Form` / `Input` / `Modal` / `Layout` / `notification` / `Table`;V2 / V3 删 antd 时 import portal primitives
- Impact: V1 内部新增;V2 决定 canvas 怎么 import(Vite 跨子应用 import path 调整,留 V2 解决)

**8. e2e(登录 → 跳转 → 占位)**

- From: 无
- To: `web/portal/e2e/portal-flow.spec.ts` 2 个 spec:(a) login → dashboard → sidebar workflow → /canvas/workflows;(b) sidebar credential → /portal/coming-soon?from=credential
- Reason: V1 关键路径 e2e 覆盖
- Impact: V1 内部新增

**V1 不做的(显式范围边界)**:

- ❌ 不修改 `web/canvas/` 任何文件 — V2 接管
- ❌ 不修改 `web/admin/` 任何文件 — V3 接管
- ❌ 不修改 `web/nginx.conf` / `web/Dockerfile` — V2 + V3 一起做
- ❌ 不修改 `web/index.html` 跳板 — V2 一并跳
- ❌ 不修改任何 `openspec/specs/<capability>/spec.md` — V2 才配 `canvas-shell` MODIFIED delta
- ❌ 不部署 / 不集成到 nginx 5173 — V1 独立 dev 5174 跑通即可;V2 + V3 集成
- ❌ 不集成 test(portal ↔ canvas ↔ admin 5173) — V3 之后独立 change

## Capabilities

### New Capabilities

- `portal-shell`: portal 子应用的主框架(Layout / Sidebar / Header / 主路由表 / Login / ComingSoon / Dashboard)
- `design-tokens`: portal 用的设计 token(brand/ink 调色板 + 字体栈 + glass 工具类),通过 `web/portal/tailwind.config.js` 维护(V2 / V3 复用同份 config)
- `tailwind-primitive-library`: portal 用的 React + tailwind 原语(Button / Card / MetricCard / StatusDot / Input / Form / Modal / Toast / Sidebar 等),位于 `web/portal/src/components/primitives/`

### Modified Capabilities

- 无(本 V1 不修改任何既有 spec;canvas / admin 的现有 spec 保持 locked)

## Impact

- **影响代码**:`web/portal/`(全新)
- **影响 API**: 无(纯前端 dev-mode mock)
- **影响依赖**:`web/portal/package.json` 新增 react / react-dom / react-router-dom 6 / tailwindcss 3.4 / postcss / autoprefixer / typescript 5.4 / vite 5 / @tanstack/react-query 5 / vitest 1 / @testing-library/react 16 / @playwright/test 1 / jsdom
- **影响测试**:`web/portal/tests/` 新增(估计 8-10 个 vitest spec);`web/portal/e2e/` 新增(2 个 playwright spec)
- **影响 spec**: 无 V1 范围内;V2 配 `canvas-shell` MODIFIED delta
- **影响基础设施**: `infrastructure/docker-compose*.yml` 0 改动;`web/nginx.conf` 0 改动;`web/Dockerfile` 0 改动
- **影响文档**: V1 不写新 README(留 V2 写统一 `web/README.md`);V1 期间 docs/prototype.html 引用在 `web/portal/README.md`(新建)记录

**前端范围 / 后端范围 / 豁免理由**:
- portal-shell: 仅前端。后端范围:无
- design-tokens: 仅前端
- tailwind-primitive-library: 仅前端
- 后端豁免理由:仓库当前 0 行后端代码;任何"portal 调后端 API"逻辑属于后续独立 change(如 `auth-bff` / `workflow-engine-api` 等)。本 V1 不引入新 API 端点,只做 UI 脚手架。

## [FUTURE-IMPLEMENTATION] 标注

以下工作 V1 触及但不实现,留 V2 / V3 / 后续 change:

- **[FUTURE-IMPLEMENTATION] V2 canvas 删 antd 改 tailwind**:portal primitives 已就绪,canvas 通过 Vite 跨子应用 import 复用(具体 import path 配置留 V2 解决)
- **[FUTURE-IMPLEMENTATION] V3 admin 删 antd 改 tailwind**:同 V2 模式
- **[FUTURE-IMPLEMENTATION] V2 / V3 集成到 nginx 5173**:`web/nginx.conf` 新增 `location /portal/` + `web/Dockerfile` 多 COPY `web/portal/dist`
- **[FUTURE-IMPLEMENTATION] V2 配 `specs/canvas-shell/spec.md` MODIFIED delta**:顶部栏 + 侧边栏 / 错误边界 + 全局 toast 两个 Requirement 改动
- **[FUTURE-IMPLEMENTATION] V2 写 `web/README.md`**:统一三套子应用入口说明
- **[FUTURE-IMPLEMENTATION] 集成 test(portal ↔ canvas ↔ admin 5173)**:V3 之后独立 change
