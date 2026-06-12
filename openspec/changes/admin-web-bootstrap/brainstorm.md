# Brainstorm — admin-web-bootstrap

> **Raw capture**：本档原样捕捉 brainstorming 决策链产物，**不**强制结构。
> design.md 从本档抽取并重组为结构化设计文件——本档与 design.md 互补，**不**互相复制。
> 来源：用户对话"开前置 change admin-web-bootstrap，先把前端骨架建到本仓"+ CLAUDE.md "0 行源代码"+ `docs/prototype.html` 视觉基线。

---

## 背景

仓库当前 0 行源代码。`mcp-server-management-ui` change 已 plan 完整 8 阶段 + tasks 36 项，**前置门 0.1 = 验 `apps/admin-web/package.json` 存在**——但 `apps/` 目录**不存在**。

**阻塞链**：
- `mcp-server-management-ui` task 7.1-7.8（前端组件）+ task 8.1-8.2（Playwright E2E）**必须** `apps/admin-web/` 存在
- `mcp-server-management-ui` task 0.1 前置门要求 admin-web 路径方案

**本 change 解锁**：建 `apps/admin-web/` 最小骨架（Vite + React 18 + TS strict + SWR + react-hook-form + zod + Playwright + 复用 prototype.html 主题），不引业务逻辑，**只**让骨架可被后续 change mount。

**关键约束**（eng-review 锁定）：
- 前端规范：React 组件化 + TypeScript 严格 + Hooks + 状态隔离（`openspec/config.yaml` §62）
- 视觉基线：`docs/prototype.html:4562 行` 已有 tailwind-ish 主题（ink-50/100/200/.../brand-500/600 等色板 + fontawesome icons）
- 12 类节点不涉及（Node Contract 锁定决策 Arch #2 不触发）
- 测试 3 层金字塔（Test #1）：Playwright E2E + vitest 单测 + 集成（与后端联调）

**必中 wedge**：admin / paul / leo / anny 在浏览器里看到 prototype.html 等价的"工作流 / Agent / 知识库 / 插件市场 / 模板广场 / 团队共享 / 配置中心 / MCP 工具 / 凭据 / 技能 / 运维"左侧导航 + 空白中央视图（具体页面由后续 change 落地）。

---

## 决策链

### Q1：前端构建工具用哪个？

**A. Vite 5**（已选）
- 用户原话没指定；从 openspec 行业标准 + prototype.html 是静态 HTML 推测 React 18 主流
- 启动快（~1s dev server），HMR 稳

**B. Next.js 15**
- 拒绝：本 change 不需要 SSR；admin-web 是企业内部 SPA，SSR 反而引入 Node runtime
- eng-review §4.4 技术栈未列 Next.js

**C. 纯 HTML + ESM**
- 拒绝：与 TypeScript 严格 + Hooks + 状态隔离（`openspec/config.yaml` §62）冲突

→ **锁定 A**

### Q2：样式方案 = tailwind？styled-components？CSS modules？

**A. Tailwind CSS 3.4**（已选）
- prototype.html 已用 tailwind utility 模式（`<div class="bg-white rounded-xl border border-ink-200 p-5">`）
- 配置 tailwind.config.js 把 prototype.html 的色板（ink-50 ~ ink-900, brand-500, brand-600）映射成 Tailwind 主题
- 视觉一致性：prototype.html 直接 copy-paste 即可工作

**B. CSS Modules**
- 拒绝：与 prototype.html 视觉对齐需要重写所有 class，token 对齐工作量大

**C. styled-components / emotion**
- 拒绝：runtime CSS-in-JS 增加 bundle 体积；admin-web 不需要动态主题

→ **锁定 A**

### Q3：路由 = React Router 还是 TanStack Router？

**A. React Router 6**（已选）
- 主流，社区资源多
- `useRoutes()` + nested route + lazy import 都支持
- 与 prototype.html 视图切换（`view-section` 隐藏/显示）的简单模式等价

**B. TanStack Router**
- 拒绝：type-safe routing 强但学习成本高，本 change scope 不需要

**C. 不用路由（state-driven view switch）**
- 拒绝：违反"组件化 + 状态隔离"前端规范；路由要支持深链接

→ **锁定 A**

### Q4：状态管理 = Redux / Zustand / React Context？

**A. SWR + React Context（轻量）**（已选）
- 服务端状态走 SWR（缓存 + 重新验证 + 5s 轮询）
- 用户/权限/UI 状态走 React Context（`UserProvider` / `ThemeProvider`）
- 不引 Redux/Zustand

**B. Redux Toolkit**
- 拒绝：admin-web 早期不需要复杂状态机；后续真有再加

**C. Zustand**
- 拒绝：SWR + Context 已能覆盖 80% 场景，引入 Zustand 多一个概念

→ **锁定 A**

### Q5：表单 = react-hook-form + zod 吗？

**A. 是**（已选）
- `mcp-server-management-ui` task 7.5 已规划用 react-hook-form + zod resolver
- zod schema 同时校验 client + server 响应（`apps/admin-web/src/api/mcp.ts` 用 zod parse）
- 与 openspec/config.yaml §62 "TypeScript 严格" 一致（zod 给运行时类型，TS 给编译时类型）

**B. Formik**
- 拒绝：API 旧；react-hook-form 更现代、性能更好

**C. 原生 form + useState**
- 拒绝：mcp 注册表单字段多（name / transport / command / args / env / security_config），原生表单代码冗长

→ **锁定 A**

### Q6：图标库 = FontAwesome（与 prototype.html 一致）？

**A. 是，react-icons/fa6**（已选）
- prototype.html 大量使用 `<i class="fas fa-file-code">` 等 FontAwesome
- `@fortawesome/react-fontawesome` + `free-solid-svg-icons`（仅 solid 子集，bundle 友好）
- 与 prototype.html 视觉 1:1

**B. lucide-react**
- 拒绝：与 prototype.html 视觉不一致（lucide 线条 vs fa 实体）

**C. 自定义 SVG**
- 拒绝：开发成本高，11 个左侧导航图标每个要画

→ **锁定 A**

### Q7：测试 = Vitest + Playwright？

**A. 是**（已选）
- Vitest：Vite 原生，配置零成本
- Playwright：eng-review Test #1 强制 Playwright E2E
- 不引 Jest（与 Vite 集成差）+ 不引 Cypress（与 Playwright 功能重叠）

**B. Jest + Cypress**
- 拒绝：与 Vite 集成差；Cypress 慢

**C. 不写测试**
- 拒绝：eng-review Test #1 强制 3 层金字塔

→ **锁定 A**

### Q8：E2E 浏览器矩阵 = Chromium only？

**A. 是**（已选）
- MVP 阶段只跑 Chromium（headless）
- admin-web 是企业内部工具，不面向 C 端多浏览器
- eng-review Test #1 没说多浏览器要求

**B. Chromium + Firefox + WebKit**
- 拒绝：MVP 阶段性价比低；后续 V1.0 可加

→ **锁定 A**

### Q9：左侧导航 11 个菜单项的占位怎么处理？

**A. 11 个 menu item 全部 static 占位**（已选）
- 工作流 / Agent / 知识库 / 模板广场 / 团队共享 / 插件市场 / 模型管理 / 通道管理 / 凭证管理 / 技能管理 / MCP 工具 / 中间件链 / 监控 / 日志
- 每个 menu item 跳 `/<slug>`，中央视图显示 "Coming soon" 占位卡片 + prototype.html 等价的 header

**B. 只挂 MCP 工具菜单**
- 拒绝：违反"前端规范：状态隔离"精神，admin-web 是 shell 业务 change 各自挂页面

**C. 不挂菜单，只挂中央视图**
- 拒绝：prototype.html 有完整左侧导航 shell，admin-web 复刻才有 1:1 视觉

→ **锁定 A**

### Q10：docker-compose 同步？

**A. 不引 admin-web 容器到 compose**（已选）
- admin-web 是 Vite dev server / 静态构建产物
- 后续 V1.0 真正部署时再开 `admin-web-deploy` change 加 nginx 容器
- 本 change 只产出 `apps/admin-web/` 源码 + 配置文件

**B. 立即加 admin-web 容器**
- 拒绝：MVP 不需要，dev 用 `pnpm dev` 即可

→ **锁定 A**

---

## 设计 trade-off

| Trade-off | 选了 | 拒绝的另一极 |
|---|---|---|
| **构建工具** | Vite（Q1-A） | Next.js / 纯 ESM |
| **样式方案** | Tailwind（Q2-A） | CSS Modules / styled-components |
| **路由** | React Router 6（Q3-A） | TanStack Router / state switch |
| **状态管理** | SWR + Context（Q4-A） | Redux / Zustand |
| **表单** | react-hook-form + zod（Q5-A） | Formik / 原生 |
| **图标** | react-icons/fa6（Q6-A） | lucide-react / 自定义 |
| **测试** | Vitest + Playwright（Q7-A） | Jest + Cypress |
| **浏览器矩阵** | Chromium only（Q8-A） | 多浏览器 |
| **菜单策略** | 11 个 static 占位（Q9-A） | 只挂 MCP / 不挂菜单 |
| **部署耦合** | 不引 compose 容器（Q10-A） | 立即加 nginx |

---

## Open Questions

- OQ1：Vite 启动时是否要用 `pnpm dev --host 0.0.0.0` 让容器外能访问？（MVP 阶段 `localhost:5173` 即可；后续 docker 化时再考虑）
- OQ2：Tailwind 配置是放 `apps/admin-web/tailwind.config.js` 还是 monorepo 根 `tailwind.config.js`？（本 change 选前者——admin-web 是独立 module）
- OQ3：TypeScript path alias `@/*` → `apps/admin-web/src/*` 是否现在就开？（开，便于后续 change 跨文件 import；用 `vite-tsconfig-paths` 插件）
- OQ4：左侧导航 11 个菜单项的"权限渲染"占位怎么做？（本 change 全 visible；后续 `mcp-server-management-ui` task 7.8 会改成 role-aware）

---

## 必中 wedge 校验（brainstorming 规则：3 个具名用户的工作流必须在视图中）

| 用户 | 触点 | 本 change 提供 |
|---|---|---|
| **paul**（财务运营） | 浏览器打开 admin-web → 看到左侧导航 → 占位中央视图 | 11 个菜单项 + "Coming soon" 占位 |
| **leo**（基础服务） | 同上 | 同上 |
| **anny**（增值服务） | 同上 | 同上 |

3 个用户**不**做业务操作（业务由后续 change 落地），本 change 只**让 admin-web 在浏览器里能跑起来**。✓

---

## eng-review 决策引用（brainstorming 规则：触及 12 锁定决策时直接引用 finding 编号）

**未触发 12 决策中的任何一条**——本 change 是纯前端骨架，不涉及 LLM / 工作流 / 记忆 / MCP / 错误边界 / 性能 / 测试 / 存储量。

唯一相关的是：
- **openspec/config.yaml §62 前端规范**："React 组件化 + TypeScript 严格 + Hooks + 状态隔离" → Q3 / Q4 / Q5 全部对齐
- **Test #1 partial**：本 change 提供 Playwright 框架 + Vitest 框架（不写实际测试），后续 change 写

---

## 范围

**本 change 包含**：
- `apps/admin-web/package.json` + pnpm-lock.yaml
- `apps/admin-web/vite.config.ts` + `tsconfig.json` (strict mode)
- `apps/admin-web/tailwind.config.js` + `postcss.config.js`
- `apps/admin-web/index.html` (入口)
- `apps/admin-web/src/main.tsx` + `App.tsx` + 路由
- `apps/admin-web/src/components/SideNav.tsx` + `AppShell.tsx`
- `apps/admin-web/src/views/PlaceholderView.tsx`（11 个 menu item 的占位视图）
- `apps/admin-web/src/api/health.ts`（与后端联调的最小 client）
- `apps/admin-web/src/types/index.ts`（共用 TS 类型）
- `apps/admin-web/tests/unit/setup.ts`（vitest 配置）
- `apps/admin-web/e2e/admin-web-bootstrap.spec.ts`（1 个 E2E：能打开 / 看到 11 个菜单 / 点 MCP 工具 → 看到占位）
- `apps/admin-web/playwright.config.ts` + `apps/admin-web/vitest.config.ts`
- `apps/admin-web/.gitignore` + `apps/admin-web/README.md`

**本 change 不包含**：
- 任何业务逻辑（mcp 注册 / workflow 编辑 / RAG / Agent 配置）
- 任何 docker-compose 改动
- 任何凭据 / 鉴权实现（auth 由后续 `credential` change 落地）
- 任何后端 API 调用（除 `/healthz` 探活）
- 任何 CI / 部署配置
