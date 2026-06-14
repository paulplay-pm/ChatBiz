# frontend-product-shell — Design (openspec artifact)

> **本文件是 openspec 5 artifact 之一**,是 `brainstorm.md` 重组后的结构化设计,跟 `docs/superpowers/specs/2026-06-14-frontend-product-shell-design.md`(详细 design doc)互补,本文偏 openspec schema 要求的"架构 + 决策"。

## Context

ChatBiz 前端 3 个子应用(portal/canvas/admin)在 V1 main `932777d` 上已搭建骨架,但未对齐 `docs/prototype.html` 的产品形态。当前用户从 `/` 进入看到的是静态三卡跳转页(portal/canvas/admin 各一张),不是产品登录页;portal Sidebar 30+ 项但分组跟原型不一致;admin 14 个 menu 全是 PlaceholderView,5 个目标页(用户/角色/部门/权限/数据权限)未实现。

**V2 worktree**(`worktree-v2-canvas-refactor`,已在 V3 merge via `ee776aa`)完成了:
- canvas 23 个 .tsx/.ts 删 antd 改 web/ui primitives(commit 59cfc26)
- canvas vitest + e2e 修(abb985c + b48c200 + 5c08a7a)
- portal 跨 app 跳转(ef61023 nginx + bb1f7ae cross-app-jump.spec.ts)
- dual-React prod-build 修复(9655018)

**V3** 是在 V2 之上做"产品形态对齐",不动 backend、不改架构、不重写 12 个 locked-in 决策。

**Stakeholders**:
- paul(财务运营)— 主用户,登录后看工作台 → 工作流
- anny/leo(基础服务/增值服务)— 系统管理 5 子页的潜在使用方

## Goals

1. 用户从 `/` 1 跳进 portal 登录页(无中间跳转卡)
2. portal Dashboard 跟原型图 #5 一致(工作台 4 metric + 快速开始 4 卡 + 最近访问 + 最近动态)
3. portal Sidebar 5 分组(工作区/探索/配置中心/运维/系统管理),与原型图 #5 #8-13 对齐
4. admin 5 个目标子页(用户/角色/部门/权限/数据权限)有真实 UI(纯 mock,不动 backend)
5. portal → admin 跨 app 跳转走 `window.location.assign(5173/admin/...)`
6. 14-gate verify 0 回归(对 V1 main baseline + V2 增量 baseline)

## Non-goals

- 真后端 API 接入(5 子页纯 mock,留 V4)
- SSO 跨 app session 共享(接受重新登录,留 V4)
- 写操作(5 子页只读,留 V4)
- admin 9 个仍为 PlaceholderView 的子项(图未指定,留 V4)
- 探索/配置中心/运维 5 分组中所有 coming-soon 项的真实页(留 V4)
- canvas WorkflowListPage / CanvasPage 的 antd 清理(已由 V2 合并提供)
- 2 个 react-flow drag e2e 修复(留 V4)

## Decisions

### D1. web/index.html 修复方式

**选**:meta refresh → `/portal/login`(纯 HTML,无 JS)
**拒**:client-side React 重定向(需要 portal SPA 先加载,加载时间用户多看 1 张静态页)
**拒**:nginx `rewrite`(改 nginx.conf,V3 范围外,且 V1 CLAUDE.md 强制 web/ 变更走 openspec)

### D2. portal Dashboard 数据来源

**选**:`web/portal/src/data/dashboard.ts` 静态 mock const(`metrics`、`quickStarts`、`recentAccesses`、`recentActivities`)
**拒**:从 `/api/dashboard/metrics` 拉(无后端)
**拒**:完全 hard-code 在 JSX 里(无法单测,且无类型安全)

### D3. portal Sidebar 跨 app 跳转实现

**选**:`MenuItem.external: boolean` 标记 + `AppLayout.handleSelect` 检测 `external` → `window.location.assign(item.href)`,否则 `useNavigate(item.href)`
**拒**:全部用 `window.location.assign`(portal 内部路由会触发整页刷新)
**拒**:全部用 `useNavigate`(跨 origin 不可用)

### D4. admin 5 子页状态管理

**选**:React `useState` + 静态 const 数据文件
**拒**:zustand(5 子页都是 CRUD-light,无 cross-component state 共享)
**拒**:react-query(无 backend,V4 接入真 API 时再上)

### D5. admin mock 数据文件位置

**选**:`web/admin/src/data/{users,roles,departments,permissions,dataPermissions}.ts`
**拒**:每个 view 文件内部 const(无复用,V4 接入 query 时难替换)
**拒**:`web/admin/src/views/<Page>/data.ts`(违反"data 在 src/data/" 的 V1 约定)

### D6. admin 14 menu 怎么处理 5 子页

**选**:router 中 `/users`、`/users/audit`、`/roles`、`/departments`、`/permissions`、`/data-permissions` 6 path 用真 view 替换 PlaceholderView;其余 8 个仍为 PlaceholderView
**拒**:全部 14 个都实现(超出 9 张图,V4 接管)
**拒**:5 子页不进 admin 路由,放别处(违反 9 张图 — 图 #8-13 都是 admin SideNav 下)

### D7. 测试策略

**选**:vitest 单元 + playwright e2e + tsc + vite build
**拒**:jest(V1 main 已用 vitest)
**拒**:cypress(跟 V1 playwright 重叠)

### D8. V2 worktree 怎么拿到 V3

**选**:`git merge worktree-v2-canvas-refactor` — 0 冲突,8 commit 全进 V3
**拒**:cherry-pick canvas 改动(冲突多,canvas antd 清理跟 vitest config 互相依赖)

## Architecture

### 三 app 边界(不变)

```
5173 nginx
├── /                  → web/index.html (改:meta refresh → /portal/login)
├── /portal/<path>     → web/portal SPA
├── /canvas/<path>     → web/canvas SPA
└── /admin/<path>      → web/admin SPA
```

### 文件结构变化(31 个文件)

| 类别 | 路径 | 改/新 |
|---|---|---|
| 入口 | `web/index.html` | 改 |
| portal 数据 | `web/portal/src/data/menu.ts` | 改(5 分组) |
| portal 数据 | `web/portal/src/data/dashboard.ts` | 新 |
| portal 页面 | `web/portal/src/pages/DashboardPage.tsx` | 改 |
| portal 布局 | `web/portal/src/components/AppLayout.tsx` | 改(跨 app 跳转) |
| admin 配置 | `web/admin/src/config/menuItems.ts` | 改(增加 6 path) |
| admin 路由 | `web/admin/src/router/index.tsx` | 改(6 path 真 view) |
| admin 布局 | `web/admin/src/components/SideNav.tsx` | 改(分组 label) |
| admin 布局 | `web/admin/src/components/AppShell.tsx` | 改(header 标题) |
| admin 数据 | `web/admin/src/data/{users,roles,departments,permissions,dataPermissions}.ts` | 新 5 |
| admin views | `web/admin/src/views/{UsersPage,UserAuditPage,RolesPage,DepartmentsPage,PermissionsPage,DataPermissionsPage}.tsx` | 新 6 |
| admin 组件 | `web/admin/src/components/{users,roles,departments,permissions,data-permissions}/*.tsx` | 新 8-12 |
| 测试 | `web/admin/tests/views_*.test.tsx` | 新 6 |
| 测试 | `web/portal/tests/pages_DashboardPage.test.tsx` | 改 1 |
| e2e | `web/portal/e2e/portal-flow.spec.ts` | 改 1(加 portal→admin) |
| e2e | `web/portal/e2e/cross-app-jump.spec.ts` | 改(V2 已建,扩 1 case) |

### 状态流

- portal Sidebar click → `AppLayout.handleSelect` → 检测 `external` → `window.location.assign` OR `useNavigate`
- admin 5 子页 click → react-router `NavLink` (admin 内部,不跨 app)
- admin 5 子页数据:静态 const,V4 替换为 `useQuery`

## Risks / Trade-offs

| 风险 | 缓解 |
|---|---|
| 9 张图细节 vs 当前 Sidebar 30+ 项 冲突 | 严格按图保留 5 分组,删除非图项 |
| V2 canvas antd 清理未 merge | **已 merge**(`ee776aa`) |
| portal Sidebar 跨 app 跳转 vs react-router 内部 | external: true 标记 + AppLayout 路由分流 |
| admin mock 数据漂移 | 单测断言行数 + 列名 |
| `localStorage` 跨 app 不共享 → portal 跳 admin 需重登 | V3 接受,V4 SSO |
| 5 子页 V4 接 API 时改动大 | 数据集中在 `src/data/*.ts`,替换为 `useQuery` 一处 |
| V3 跟 V2 merge 后 web/ui 路径全改,V3 import 写错 | 走 V2 已有 commit:`import { Button } from 'ui/primitives/Button'` |

## Migration Plan

V3 无数据库 schema 变更、无 backend 部署,**只是前端构建产物替换**:

1. 在 V3 worktree 上完成 11 task(每 task ≤ 2h)
2. `pnpm exec vite build` 3 个子 app 重新出 dist
3. `docker build -t chatbiz-web:v3 -f web/Dockerfile web/` 重新出镜像
4. `docker run -d --rm --name chatbiz-web-v3 -p 5173:80 chatbiz-web:v3` 起 v3 容器
5. 停 v2 容器(`docker stop chatbiz-web`)+ 5-path curl 验证
6. `git push origin worktree-v3-admin-refactor` → PR → 合并到 main
7. 后续 PR 触发:web/Dockerfile 镜像重建(V1 main CI)— 这步走 V1 main 现有 CI 流程

**回滚**:`git revert` merge commit + 重建镜像 + 替换容器。

## Open Questions

1. **Admin 14 menu 图标**:原型图 #8-13 用了 FontAwesome 图标,V1 main admin menuItems.ts 已有 icon 字段。但图 #8 用户管理展开用 chevron-down,V1 main SideNav 无展开/折叠逻辑。**V3 决策**:5 子页的"用户管理"用 NavLink 父子路径(`/users` + `/users/audit` 都直接列在 SideNav),无折叠(简化)。
2. **portal Dashboard "快速开始"按钮 跳转**:4 卡都跳外部 app(工作流 → /canvas/workflows;Agent → /canvas/agent;知识库 → /canvas/knowledge;对话 → 内部 `/coming-soon?from=chat`)。**V3 决策**:`external: true` 标记处理外部,内部走 useNavigate。
3. **admin 权限管理矩阵只读还是可写**:图 #12 顶部"只读查看" toggle 暗示支持编辑。**V3 决策**:只读(纯 mock,V4 接 API 后再做写)。

## 与三件源对齐

| 决策 | 来源 | 节 |
|---|---|---|
| 三 app 边界 + 5173 单端口 | `docs/architecture.md` §4.5 部署架构 + V1 CLAUDE.md | |
| 12 个 locked-in 决策无冲突 | design doc `## GSTACK REVIEW REPORT` | 全部 12 |
| 9 张图产品形态 | `docs/prototype.html` + `docs/prd.md` §4 + §6 | §6 系统管理 → admin 5 子页 |
| 前端栈 React 18 + TS 严格 + Vite 5 | `docs/architecture.md` §4.4 + V1 CLAUDE.md | |

## 范围外证据

- 0 后端 API 改动 — 仅前端 mock
- 0 端口分配变更 — 5173 仍是 web 唯一入口
- 0 npm 新依赖 — 复用 V2 已清干净的 web/ui primitives
- 0 docker compose 改动 — 只换 web 容器镜像
