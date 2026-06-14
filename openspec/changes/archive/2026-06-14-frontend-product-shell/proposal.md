# frontend-product-shell — Proposal

## Why

ChatBiz portal/canvas/admin 三前端当前不符合 `docs/prototype.html` 9 张目标图的形态:
1. `web/index.html` 是静态三卡跳转页,不是产品登录页(用户从 `/` 进入看到的是 "ChatBiz Web Portal" 标题 + 三张卡)
2. portal Dashboard 简陋(4 metric + "新建工作流"按钮),Sidebar 30+ 项但分组与原型不一致
3. admin 14 个 menu 全是 PlaceholderView,5 个目标页(用户/角色/部门/权限/数据权限)需实现

源头:`docs/prototype.html`(前端 HTML 原型,9 张图目标)+ `docs/prd.md` §4 工作流 + §6 系统管理。

## What Changes

1. **改 `web/index.html`**:删静态三卡,改成 meta refresh → `/portal/login`
2. **portal DashboardPage**:按图 #5 改写 — 工作台 4 metric + 快速开始 4 卡 + 最近访问 + 最近动态
3. **portal Sidebar**:5 分组(工作区/探索/配置中心/运维/系统管理),跨 app 跳转用 `external: true` 标记
4. **admin 5 子页**:`/users` 列表 + `/users/audit` 审核 + `/roles` 4 卡 + 权限矩阵 + `/departments` 树状 + `/permissions` 矩阵 + `/data-permissions` 3 规则 + 共享记录
5. **admin mock 数据**:`web/admin/src/data/{users,roles,departments,permissions,dataPermissions}.ts`
6. **跨 app e2e**:portal → `/admin/users` 跳转(扩 V2 `cross-app-jump.spec.ts`)

## Capabilities

### New Capabilities

| Capability | Spec 文件 | 范围 |
|---|---|---|
| `portal-index-redirect` | `specs/portal-index-redirect/spec.md` | 改 `web/index.html` 跳转 |
| `portal-dashboard-page` | `specs/portal-dashboard-page/spec.md` | 改 `web/portal/src/pages/DashboardPage.tsx` + mock 数据 |
| `portal-sidebar-five-sections` | `specs/portal-sidebar-five-sections/spec.md` | 改 `web/portal/src/data/menu.ts` + `AppLayout` |
| `admin-user-list` | `specs/admin-user-list/spec.md` | 新增 `views/UsersPage.tsx` + `data/users.ts` |
| `admin-user-audit` | `specs/admin-user-audit/spec.md` | 新增 `views/UserAuditPage.tsx` |
| `admin-role-management` | `specs/admin-role-management/spec.md` | 新增 `views/RolesPage.tsx` + `data/roles.ts` |
| `admin-department-management` | `specs/admin-department-management/spec.md` | 新增 `views/DepartmentsPage.tsx` + `data/departments.ts` |
| `admin-permission-matrix` | `specs/admin-permission-matrix/spec.md` | 新增 `views/PermissionsPage.tsx` + `data/permissions.ts` |
| `admin-data-permission` | `specs/admin-data-permission/spec.md` | 新增 `views/DataPermissionsPage.tsx` + `data/dataPermissions.ts` |
| `admin-menu-update` | `specs/admin-menu-update/spec.md` | 改 `web/admin/src/config/menuItems.ts` + `router/index.tsx` |

### Modified Capabilities

无(全部是 new capabilities,因为 web/admin + web/portal 没有现存 `openspec/specs/*` 文档)。

## Non-goals

- **真后端 API 接入**(workflow-engine / credential / audit-and-isolation 都有 stub,目前 mock)
- **SSO 跨 app session 共享**(`localStorage` 跨 app 不共享,接受重新登录)
- **写操作** — 5 子页只读 mock UI,不动 backend
- **9 个 admin 仍为 PlaceholderView 的子项** — V4 接管
- **探索/配置中心/运维 5 分组中所有 coming-soon 项的真实页** — V4
- **canvas WorkflowListPage / CanvasPage 的 antd → web/ui primitives 迁移** — 由 V2 worktree 提供(V3 已 merge)
- **2 个 react-flow drag e2e 修复**(`canvas-connection` + `canvas-edge-deletion`)— V4 单独 change

## Impact

### 前端范围
- `web/index.html`(改 1 文件)
- `web/portal/src/{data/menu.ts, pages/DashboardPage.tsx, components/AppLayout.tsx}`(改 3 文件)
- `web/admin/src/{config/menuItems.ts, router/index.tsx, views/*.tsx(6 新增), data/*.ts(5 新增), components/(可能新增树/矩阵/表)}`(改 6 + 新 11 = 17 文件)
- `web/portal/tests/pages_DashboardPage.test.tsx`(改 1)
- `web/admin/tests/views_*.test.tsx`(新 6)
- `web/portal/e2e/portal-flow.spec.ts`(改 1,加 portal→admin 跳转)
- `web/portal/e2e/cross-app-jump.spec.ts`(V2 已建,扩 1 case)

### 后端范围
**0**。5 子页纯前端 mock,无后端 API 调用。[FUTURE-IMPLEMENTATION] V4 接入 workflow-engine / audit-and-isolation 真实 API。

### 依赖影响
- `web/ui/primitives/*`(V2 移过去的共享 components)— V3 复用
- 0 新 npm 依赖
- 0 docker compose 端口变更

## 锁定决策符合性

- 12 个 eng-review 锁定决策 100% 符合 — 不重写架构,只重构前端形态
- 端口表无变更(5173 仍是 web 统一入口)
- Tech stack 跟 `docs/architecture.md` §4.4 一致:React 18 + TS 严格 + Vite 5 + web/ui primitives
- 任务粒度 ≤ 2h(章节 9 实施计划 11 task)
