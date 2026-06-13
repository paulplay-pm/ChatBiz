# portal-shell Specification

## Purpose
TBD - created by archiving change web-portal-shell. Update Purpose after archive.
## Requirements
### Requirement: 登录页 + localStorage 标记

`/portal/login` 路由 MUST 提供 username + password 输入框(dev 模式:任何非空 username 都能登录,password 任意);点 "登录" → 写 `localStorage['chatbiz.auth'] = JSON.stringify({ username, loginAt: <epoch_ms> })` + 跳 `/portal/`。该流程 MUST 被 Playwright e2e 覆盖。V1 期间 portal 登录不与 `specs/canvas-auth/spec.md` 冲突 — canvas LoginPage 保留作为兜底;V2 由独立 change 统一登录入口。

#### Scenario: dev 模式登录
- **WHEN** 用户在 `/portal/login` 输入 username="paul" + password="任意" + 点 "登录"
- **THEN** 前端 MUST 写 `localStorage['chatbiz.auth']` 包含 `{ username: "paul", loginAt: <number> }` + 跳 `/portal/`(即 portal `/` 路由)

#### Scenario: 已登录访问 login
- **WHEN** `localStorage['chatbiz.auth']` 存在 + 用户访问 `/portal/login`
- **THEN** 前端 MUST 跳 `/portal/`(避免死循环)

#### Scenario: 未登录访问受保护路由
- **WHEN** `localStorage['chatbiz.auth']` 不存在 + 用户访问 `/portal/` 或 `/portal/coming-soon`
- **THEN** 前端 MUST 跳 `/portal/login`

#### Scenario: Playwright 登录 e2e
- **WHEN** 执行 `pnpm --dir web/portal exec playwright test e2e/portal-flow.spec.ts`
- **THEN** 测试 MUST 打开 `/portal/login`、填写 username/password、点击登录、断言进入 `/portal/` 且 `localStorage` 含 `chatbiz.auth`

### Requirement: 主框架 AppLayout(顶部 glass header + 左侧 Sidebar + 右侧 Outlet)

`AppLayout` MUST 渲染固定顶部 glass header(brand-500 logo + DM Sans 标题 + 半透明背景 + `backdrop-filter: blur(20px)`)+ 左侧 `Sidebar`(30+ 项菜单,分 5 个 section)+ 右侧 `<Outlet/>` 渲染当前路由页面。eng-review Quality #1 UI 风格以 `docs/prototype.html` 顶部栏 / 侧边栏为蓝本。

#### Scenario: 顶部栏渲染
- **WHEN** 任何已登录页面打开
- **THEN** AppLayout MUST 渲染固定顶部 glass header(brand-500 logo 左对齐 + DM Sans 标题居中);不依赖具体页面 props

#### Scenario: 侧边栏导航
- **WHEN** 用户点击侧边栏 "工作流" 菜单
- **THEN** AppLayout MUST 调用 `navigate(href)` 或 `window.location.assign(href)` 跳到目标(`status: 'ready'` 跳 `/canvas/workflows`;`status: 'coming-soon'` 跳 `/portal/coming-soon?from=<id>`)

#### Scenario: Outlet 内容渲染
- **WHEN** 路由命中 `AppLayout` 子路由
- **THEN** AppLayout MUST 在右侧 `<main>` 内渲染 `<Outlet/>` 对应的 page 组件

### Requirement: 30+ 项侧栏菜单 + 5 个 section

`web/portal/src/data/menu.ts` MUST 导出 5 个 `MenuSection`(`对话` / `工作流` / `Agent` / `知识库` / `系统设置`)+ 30+ 个 `MenuItem`(`id` / `label` / `icon` / `section` / `status: 'ready' | 'coming-soon'` / `href`)。`Sidebar` 组件 MUST 按 section 分组渲染所有 `MenuItem`;`status` 字段 MUST 是 `'ready'` 或 `'coming-soon'` 二选一。

#### Scenario: 5 个 section 标题渲染
- **WHEN** Sidebar 渲染
- **THEN** 5 个 section 标题 MUST 全部 visible(对话 / 工作流 / Agent / 知识库 / 系统设置)

#### Scenario: 30+ 项菜单渲染
- **WHEN** Sidebar 渲染
- **THEN** `MENU` 数组的每个元素 MUST visible;`status` 字段全部 `ready` 或 `coming-soon`

#### Scenario: active 状态高亮
- **WHEN** 用户访问 `/portal/coming-soon?from=credential`
- **THEN** SidebarItem 的 id=`credential` MUST 应用 `bg-brand-50 text-brand-600` 高亮(prototype 视觉)

### Requirement: ComingSoonPage 单组件占位

`/portal/coming-soon?from=<menu_id>` MUST 由 `ComingSoonPage` 组件渲染,组件 MUST 读 `useSearchParams()` 拿 `from` query,从 `MENU` 数组查对应 `MenuItem.label`,渲染 "Coming soon — V1.0+ 接入" + 菜单名卡片。

#### Scenario: 已知 from 渲染菜单名
- **WHEN** 用户访问 `/portal/coming-soon?from=credential`
- **THEN** ComingSoonPage MUST 渲染 "凭证管理"(从 MENU 查 label)

#### Scenario: 未知 from
- **WHEN** 用户访问 `/portal/coming-soon?from=non-existent-id`
- **THEN** ComingSoonPage MUST 渲染 "此功能将由 V1.0+ 接入" 兜底文案(不报错)

#### Scenario: 无 from
- **WHEN** 用户访问 `/portal/coming-soon`(无 query)
- **THEN** ComingSoonPage MUST 渲染 "Coming soon" 兜底

### Requirement: DashboardPage 4 个 metric + 1 个 quick action

`/`(DashboardPage) MUST 渲染 4 个 `MetricCard`(工作流 / Agent / 运行次数 / 知识库 各 1 个)+ 1 个 "新建工作流" 按钮(点击跳 `/canvas/workflows`)。

#### Scenario: 4 个 metric 渲染
- **WHEN** DashboardPage 渲染
- **THEN** MUST 有 4 个 `data-testid="metric-card"` 元素

#### Scenario: quick action 按钮
- **WHEN** DashboardPage 渲染
- **THEN** MUST 有 1 个 `data-testid="quick-action"` 元素,点击后 `window.location.assign('/canvas/workflows')` 或 `navigate('/canvas/workflows')`

### Requirement: Vite 5 + React 18 + TypeScript 严格

V1 MUST 使用 Vite 5 + React 18 + TypeScript 5.4 strict 模式(`strict: true` + `noUncheckedIndexedAccess: true` + `noImplicitAny: true` + `noUnusedLocals: true` + `noUnusedParameters: true`);所有前端代码 MUST 编译无 error;Vite base MUST 是 `/portal/`;dev server MUST 跑 5174 端口;`tsc --noEmit && vite build` MUST 退出码 0。

#### Scenario: TS 严格模式编译
- **WHEN** `pnpm --dir web/portal exec tsc --noEmit` 跑
- **THEN** 命令 MUST exit 0;`tsconfig.json` MUST 启用 `strict: true` + `noUncheckedIndexedAccess: true` + `noImplicitAny: true`

#### Scenario: Vite build 成功
- **WHEN** `pnpm --dir web/portal exec vite build` 跑
- **THEN** 系统 MUST 输出 `web/portal/dist/index.html` + `web/portal/dist/assets/index-*.js` + `web/portal/dist/assets/index-*.css`;命令退出码 MUST 为 0;`vite.config.ts` 的 `base` MUST 是 `/portal/`

#### Scenario: 5174 dev server
- **WHEN** `pnpm --dir web/portal exec vite` 跑
- **THEN** Vite MUST 在 5174 端口启动;`http://localhost:5174/` 返 200 HTML

### Requirement: Playwright e2e 关键路径

V1 MUST 跑 2 个 Playwright e2e spec:(a) 登录 → Dashboard → sidebar workflow → `/canvas/workflows`;(b) sidebar credential → `/portal/coming-soon?from=credential`。`pnpm --dir web/portal exec playwright test` MUST 退出码 0。

#### Scenario: 登录跳转 spec
- **WHEN** 执行 `pnpm --dir web/portal exec playwright test e2e/portal-flow.spec.ts`
- **THEN** 第 1 个 spec MUST 跑通:打开 `/portal/login` → 填写 paul/dev → 点登录 → 断言 URL 变 `/portal/` → 断言 sidebar 可见 → 点击 sidebar workflow → 断言跳 `/canvas/workflows`

#### Scenario: 占位页 spec
- **WHEN** 执行 `pnpm --dir web/portal exec playwright test e2e/portal-flow.spec.ts`
- **THEN** 第 2 个 spec MUST 跑通:登录后点击 sidebar credential → 断言跳 `/portal/coming-soon?from=credential` → 断言页面含 "凭证" 文案

