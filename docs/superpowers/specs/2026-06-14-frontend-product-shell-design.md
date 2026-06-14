# frontend-product-shell — Design Doc

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 ChatBiz 前端 3 个子应用 (portal/canvas/admin) 跟 docs/prototype.html 的 9 张目标图对齐,实现"登录 → 主框架 → 工作流/Chatflow 编辑器 + 5 个系统管理子页"的完整用户路径。

**Architecture:** portal 承担登录 + 主框架 + 工作台 Dashboard,canvas 承担 workflow list + canvas 编辑器 + chatflow + run debugger(已存在),admin 承担 14 个 menu 项的侧边导航 + 5 个真实子页(用户/角色/部门/权限/数据权限)+ 9 个仍为 PlaceholderView。统一入口 5173 nginx 路径分发不变(portal/canvas/admin)。

**Tech Stack:** Vite 5 + React 18 + TypeScript 严格 + react-router-dom v6 + web/ui primitives(已存在,无 antd) + TailwindCSS 3.4 + FontAwesome。

---

## 1. 背景与现状

### 1.1 现状盘点(V1 main `932777d`)

| 模块 | 状态 | 备注 |
|---|---|---|
| `web/index.html` | 静态三卡跳转页 | 访问 `/` 见 portal/canvas/admin 三张卡 — 不符合产品形态 |
| `web/portal/` | `web-portal-shell` ✓ Complete | LoginPage + Sidebar + DashboardPage + 30+ menu item + ToastProvider + RequireAuth |
| `web/canvas/` | 23 个 antd 引用待清(V2 已清) + WorkflowListPage + CanvasPage + ChatflowPage + RunDebuggerPage | |
| `web/admin/` | `admin-web-bootstrap` ✓ Complete | 14 menu + SideNav + AppShell + HealthIndicator,所有页面 PlaceholderView |
| `web/nginx.conf` | 已 3 path + 5 path curl PASS | |

### 1.2 9 张目标图(V3 要还原)

| # | 主题 | 归属 app | 现状差距 |
|---|---|---|---|
| #2 | `/` 直接进登录页 | web/index.html | 当前是三卡 ❌ |
| #5 | 主页 dashboard + 左侧导航 5 分组 | web/portal | Dashboard 简陋(4 metric),Sidebar 30+ 项但分组与图不一致 |
| #6 | 工作流卡片列表 | web/canvas | WorkflowListPage 已有(antd 版) |
| #7 | canvas 编辑器(节点 + 右侧属性) | web/canvas | CanvasPage 已有(antd 版,V2 worktree 已清) |
| #8 | 用户管理(列表 + 审核) | web/admin | PlaceholderView ❌ |
| #9 | 角色管理(4 卡 + 权限配置) | web/admin | PlaceholderView ❌ |
| #10 | 部门管理(树状) | web/admin | PlaceholderView ❌ |
| #12 | 权限管理(矩阵) | web/admin | PlaceholderView ❌ |
| #13 | 数据权限(3 规则 + 共享记录) | web/admin | PlaceholderView ❌ |

### 1.3 已 lock-in 的 12 个工程决策(eng-review 2026-06-10)

不重写:`docs/architecture.md` §4 + 12 个 locked-in finding;前端 5 storage 估算:canvas JSON 500MB / MinIO 10TB/year 等。

## 2. 架构(D1)

### 2.1 三 app 边界

```
5173 nginx
├── /                  → web/index.html (改:meta refresh → /portal/login)
├── /portal/<path>     → web/portal SPA (login → main frame)
├── /canvas/<path>     → web/canvas SPA (workflow list + canvas editor + chatflow)
└── /admin/<path>      → web/admin SPA  (14 menu + 5 real sub-pages)
```

portal Sidebar 跨 app 跳转:
- `/canvas/...` → `window.location.assign('http://localhost:5173/canvas/...')`
- `/admin/...` → `window.location.assign('http://localhost:5173/admin/...')`
- 内部 portal 路由 → `useNavigate()`

### 2.2 文件结构

**新增/修改文件**:

```
web/index.html                                         (改:meta refresh)
web/portal/src/data/menu.ts                            (改:分组 + 链接对 5 分组对齐)
web/portal/src/pages/DashboardPage.tsx                 (改:5 metric + 快速开始 + 最近访问 + 最近动态)
web/portal/src/components/AppLayout.tsx                (可能微调 header 区)
web/admin/src/router/index.tsx                         (改:5 path 替换 PlaceholderView)
web/admin/src/config/menuItems.ts                      (改:增加 5 个 admin 专属 path:users, users/audit, roles, departments, permissions, data-permissions)
web/admin/src/components/SideNav.tsx                   (微调:分组 label 按 admin 5 分组)
web/admin/src/components/AppShell.tsx                  (微调:header 标题改"系统管理",加当前 section 面包屑)
web/admin/src/views/                                   (新增)
  ├── UsersPage.tsx
  ├── UserAuditPage.tsx
  ├── RolesPage.tsx
  ├── DepartmentsPage.tsx
  ├── PermissionsPage.tsx
  └── DataPermissionsPage.tsx
web/admin/src/data/                                    (新增)
  ├── users.ts                                         (mock 3-5 行)
  ├── roles.ts                                         (mock 4 角色 + 权限)
  ├── departments.ts                                   (mock 树状)
  ├── permissions.ts                                   (7 模块 × 11 权限点 × 6 操作)
  └── dataPermissions.ts                               (3 规则 + 4 共享记录)
web/admin/src/components/primitives/                   (可能:加 Table/Tree/PermissionMatrix 等)
web/admin/src/components/users/                        (新增:UserRow, RoleCard, DepartmentTreeNode, PermissionMatrix, ShareRecordTable)
web/admin/tests/views_UsersPage.test.tsx               (新增:渲染 + 行数)
web/admin/tests/views_RolesPage.test.tsx               (新增:4 角色卡渲染)
web/admin/tests/views_DepartmentsPage.test.tsx         (新增:树状结构)
web/admin/tests/views_PermissionsPage.test.tsx         (新增:矩阵 checkbox)
web/admin/tests/views_DataPermissionsPage.test.tsx     (新增:3 规则 + 共享记录)
web/portal/tests/pages_DashboardPage.test.tsx          (改:断言 4 metric + 快速开始 + 最近访问 + 最近动态)
web/portal/e2e/portal-flow.spec.ts                     (可能微调:跳转路径)
```

### 2.3 状态管理

- 全 mock 数据 — 不接后端 API(0 后端)
- `web/admin/src/data/*.ts` 静态导出 const 数组
- React state 为主(useState / useReducer),不上 zustand

## 3. 组件设计

### 3.1 web/index.html(D5 修复)

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta http-equiv="refresh" content="0; url=/portal/login" />
  <title>ChatBiz</title>
  <link rel="canonical" href="/portal/login" />
</head>
<body>
  <p>正在跳转 <a href="/portal/login">登录</a> ...</p>
</body>
</html>
```

不依赖 JavaScript,任意设备可进。

### 3.2 portal DashboardPage(D2)

布局跟图 #5:

```
┌──────────────────────────────────────────────────────┐
│  h1: 工作台                                          │
│  p:  欢迎回来,张三!以下是您的工作概览                 │
│  ────────────────────────────────────────            │
│  [我的工作流 12] [我的 Agent 5] [今日调用 2,456] [Token 消耗 456K]  ← 4 MetricCard
│  ────────────────────────────────────────            │
│  ┌─ 快速开始 ─────────────────┐  ┌─ 最近访问 ──────┐│
│  │ [+] 新建工作流              │  │ 智能客服机器人   ││
│  │     可视化编排              │  │ 工作流 · 2小时前  ││
│  │ [🤖] 创建 Agent            │  │ 数据分析助手     ││
│  │     智能体配置              │  │ Agent · 5小时前  ││
│  │ [📚] 上传知识库            │  │ 产品知识库       ││
│  │     文档管理                │  │ 知识库 · 1天前   ││
│  │ [💬] 开始对话              │  └──────────────────┘│
│  │     测试 Agent              │                       │
│  └────────────────────────────┘                       │
│  ────────────────────────────────────────            │
│  ┌─ 最近动态 ──────────────────────────────────────┐│
│  │ • 工作流 智能客服机器人 执行成功     10 分钟前     ││
│  │ • Agent 数据分析助手 已发布          1 小时前      ││
│  └─────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────┘
```

数据:
- `web/portal/src/data/dashboard.ts` 静态导出 `metrics`、`quickStarts`、`recentAccesses`、`recentActivities`

### 3.3 portal Sidebar(D3)

5 分组,每组一个 Section + 多 item:

```ts
// web/portal/src/data/menu.ts
export const SECTIONS = [
  { id: 'workspace', title: '工作区' },
  { id: 'explore',   title: '探索' },
  { id: 'config',    title: '配置中心' },
  { id: 'ops',       title: '运维' },
  { id: 'system',    title: '系统管理' },
];

export const MENU: MenuItem[] = [
  // 工作区
  { section: 'workspace', id: 'dashboard',  href: '/',                        status: 'ready' },
  { section: 'workspace', id: 'chat',       href: '/coming-soon?from=chat',   status: 'coming-soon' },
  { section: 'workspace', id: 'favorites',  href: '/coming-soon?from=favorites', status: 'coming-soon' },
  { section: 'workspace', id: 'workflow',   href: 'http://localhost:5173/canvas/workflows', status: 'ready', external: true },
  { section: 'workspace', id: 'agent',      href: 'http://localhost:5173/canvas/agent', status: 'ready', external: true },
  { section: 'workspace', id: 'knowledge',  href: 'http://localhost:5173/canvas/knowledge', status: 'ready', external: true },
  // 探索
  { section: 'explore',   id: 'template',   href: '/coming-soon?from=template', status: 'coming-soon' },
  { section: 'explore',   id: 'team',       href: '/coming-soon?from=team',     status: 'coming-soon' },
  // 配置中心
  { section: 'config',    id: 'plugin',     href: '/coming-soon?from=plugin',  status: 'coming-soon' },
  { section: 'config',    id: 'model',      href: '/coming-soon?from=model',   status: 'coming-soon' },
  { section: 'config',    id: 'channel',    href: '/coming-soon?from=channel', status: 'coming-soon' },
  { section: 'config',    id: 'credential', href: '/coming-soon?from=credential', status: 'coming-soon' },
  { section: 'config',    id: 'skill',      href: '/coming-soon?from=skill',   status: 'coming-soon' },
  // 运维
  { section: 'ops',       id: 'monitor',    href: '/coming-soon?from=monitor', status: 'coming-soon' },
  { section: 'ops',       id: 'logs',       href: '/coming-soon?from=logs',    status: 'coming-soon' },
  { section: 'ops',       id: 'api',        href: '/coming-soon?from=api',     status: 'coming-soon' },
  { section: 'ops',       id: 'trace',      href: '/coming-soon?from=trace',   status: 'coming-soon' },
  { section: 'ops',       id: 'infra',      href: '/coming-soon?from=infra',   status: 'coming-soon' },
  // 系统管理 — 都跳 admin
  { section: 'system',    id: 'settings',   href: 'http://localhost:5173/admin/workflow', status: 'ready', external: true },
  { section: 'system',    id: 'user-list',  href: 'http://localhost:5173/admin/users',    status: 'ready', external: true },
  { section: 'system',    id: 'user-audit', href: 'http://localhost:5173/admin/users/audit', status: 'ready', external: true },
  { section: 'system',    id: 'role',       href: 'http://localhost:5173/admin/roles',    status: 'ready', external: true },
  { section: 'system',    id: 'department', href: 'http://localhost:5173/admin/departments', status: 'ready', external: true },
  { section: 'system',    id: 'permission', href: 'http://localhost:5173/admin/permissions', status: 'ready', external: true },
  { section: 'system',    id: 'data-perm',  href: 'http://localhost:5173/admin/data-permissions', status: 'ready', external: true },
  { section: 'system',    id: 'system-config', href: '/coming-soon?from=system-config', status: 'coming-soon' },
  { section: 'system',    id: 'billing',    href: '/coming-soon?from=billing', status: 'coming-soon' },
];
```

`AppLayout.handleSelect` 检测 `external: true` → `window.location.assign(item.href)`,否则 `useNavigate(item.href)`(useNavigate 在 portal basename `/portal` 下走内部)。

### 3.4 admin 5 子页

#### 3.4.1 UsersPage(图 #8)

```tsx
// /admin/users
<div>
  <div className="flex items-center mb-4">
    <h1>用户管理</h1>
    <div className="ml-auto flex gap-2">
      <Input placeholder="搜索用户" />
      <Button>批量导入</Button>
      <Button>导出</Button>
      <Button primary>+ 添加用户</Button>
    </div>
  </div>
  <Table
    columns={[
      { key: 'user',     title: '用户',     render: r => <UserCell user={r} /> },
      { key: 'dept',     title: '部门' },
      { key: 'role',     title: '角色',     render: r => <Tag>{r.role}</Tag> },
      { key: 'status',   title: '状态',     render: r => <StatusTag status={r.status} /> },
      { key: 'lastSeen', title: '最后登录' },
      { key: 'actions',  title: '操作',     render: r => <><EditIcon /><DisableIcon /></> },
    ]}
    rows={MOCK_USERS}
  />
</div>
```

`UserAuditPage` 子菜单:仅 status='pending' 过滤 + 顶部"待审核 (N)" badge。

#### 3.4.2 RolesPage(图 #9)

4 角色卡(超管/部门管理员/开发者/普通用户)+ 选中后下方展开权限矩阵(工作流/对话 × 查看/创建/编辑/删除/发布/执行)。矩阵用 `<table>` + `<input type="checkbox">` 实现,纯前端 mock。

#### 3.4.3 DepartmentsPage(图 #10)

`<DepartmentTree>` 组件递归渲染部门 + 子部门 + 成员头像 + 数字 badge。点击"添加子部门"弹 modal(`web/ui/primitives/Modal`)。

#### 3.4.4 PermissionsPage(图 #12)

`<PermissionMatrix>` 大表:
- 列:功能模块 / 权限点 / 查看 / 创建 / 编辑 / 删除 / 发布 / 执行
- 行:7 模块(工作流/Agent/知识库/对话/模板/插件/系统管理)
- 仅读,顶部 dropdown 切换"超级管理员/部门管理员/开发者/普通用户"4 个角色
- 数据:`web/admin/src/data/permissions.ts` 静态矩阵

#### 3.4.5 DataPermissionsPage(图 #13)

两段:
- **数据权限规则**:3 张可点击卡(个人数据默认/部门数据/跨部门共享),展开"修改"按钮
- **数据共享记录表**:资源名称/类型/创建者/所属部门/共享范围/操作

## 4. 数据流

### 4.1 登录流(已存在,沿用)

`/portal/login` → 输入 username/password → `localStorage.setItem('chatbiz.auth', ...)` → `useNavigate('/')` → RequireAuth 通过 → AppLayout + DashboardPage。

### 4.2 跨 app 跳转

portal Sidebar click → `AppLayout.handleSelect` → `item.external ? window.location.assign(item.href) : useNavigate(item.href)`。

`/portal/login` 已存在,跨 app 跳转后目标 app 仍需重新登录(目前没有共享 session) — 这是当前限制,V4 再做 SSO。

### 4.3 5 子页纯前端

无 API 调用。`MOCK_USERS = [...]` 静态。组件接收 `MOCK_USERS` 后渲染。后续 V4 接入真后端时,把 `import { MOCK_USERS } from '@/data/users'` 替换成 `useQuery(() => api.get('/admin/users'))`。

## 5. 错误处理

| 场景 | 处理 |
|---|---|
| portal 跨 app 跳转失败(5173 不可达) | 浏览器自动重试或显示 network error(V3 不做离线降级) |
| admin 5 子页 mock 数据缺失 | TypeScript strict 编译失败 — 在测试覆盖 |
| Sidebar 点击 `external` 但 target app 未启动 | 浏览器跳到目标 URL,得到 502(沿用 nginx 当前行为) |
| 路径分发 404 | nginx `try_files` 兜底到各 app `index.html` |

## 6. 测试

### 6.1 单元测试(vitest)

- `web/portal/tests/pages_DashboardPage.test.tsx` — 4 metric + 4 快速开始 + 3 最近访问 + N 最近动态
- `web/admin/tests/views_UsersPage.test.tsx` — 表格行数 + 列数 + 状态 tag + 操作按钮
- `web/admin/tests/views_RolesPage.test.tsx` — 4 角色卡 + 点击切换 + 权限矩阵
- `web/admin/tests/views_DepartmentsPage.test.tsx` — 树状 + 节点数
- `web/admin/tests/views_PermissionsPage.test.tsx` — 矩阵行/列 + 7 模块 11 权限点
- `web/admin/tests/views_DataPermissionsPage.test.tsx` — 3 规则卡 + 共享记录表
- 沿用 V1 覆盖率门槛:单元 ≥100% / 接口 100%

### 6.2 E2E (playwright)

- `web/portal/e2e/portal-flow.spec.ts` 改:登录 → dashboard 4 metric 可见 → 点 workflow → 跳 /canvas/workflows
- `web/portal/e2e/cross-app-jump.spec.ts`(V2 已建)保留,加 1 case:portal → /admin/users
- `web/admin/e2e/admin-flow.spec.ts` 新建:登入 admin → /admin/users 看到 3 mock 用户 → 点 "用户审核" 看到 N pending → 点 "角色管理" 看到 4 角色 → 点 "权限管理" 看到 7×11 矩阵

### 6.3 tsc / build

- `pnpm exec tsc --noEmit` 在 portal/canvas/admin 0 error
- `vite build` 3 个子 app 全 PASS

## 7. 范围外(V4 / 后续)

- 真后端 API 接入(workflow-engine / credential / audit-and-isolation 都有 stub,目前 mock)
- SSO 跨 app session 共享
- 用户审核/角色变更/权限变更的写操作(纯 mock UI,不动 backend)
- 9 个 admin 仍为 PlaceholderView 的子项(图未指定,留 V4)
- 探索/配置中心/运维 5 分组中所有 coming-soon 项的真实页
- canvas WorkflowListPage / CanvasPage 的 antd → web/ui primitives 迁移(由 V2 worktree 提供,V3 merge 后)
- 2 个 react-flow drag e2e 修复(`canvas-connection.spec.ts` + `canvas-edge-deletion.spec.ts`)— V4 单独 change

## 8. 风险

| 风险 | 缓解 |
|---|---|
| 9 张图细节 vs 当前 Sidebar 30+ 项 冲突 | 严格按图保留 5 分组,删除非图项 |
| V2 canvas antd 清理未 merge | V3 plan 第一步:把 V2 worktree 关键 commit cherry-pick 到 V3(只 src/,不 merge 整 branch) |
| portal Sidebar 跨 app 跳转 vs react-router 内部 | `external: true` 标记 + AppLayout 路由分流 |
| admin mock 数据漂移 | 单测断言行数 + 列名 |
| `localStorage` 跨 app 不共享 → portal 跳 admin 需重登 | 当前 V3 接受,V4 SSO |
| V3 跟 V2 worktree 分支冲突 | V3 基于 V1 main `932777d`,V2 在 worktree-v2-canvas-refactor,merge 时再处理 |

## 9. 实施计划(走 openspec tasks.md)

V3 tasks 应当**逐项可验证**(每 task ≤ 2h,编码配对验证):

1. T1: scaffold frontend-product-shell change 5 个 artifact(brainstorm/proposal/design/specs/tasks)— 已完成
2. T2: 改 web/index.html meta refresh + 5-path curl verify
3. T3: portal menu.ts 5 分组 + 跨 app href external: true + 单测
4. T4: portal DashboardPage 4 metric + 4 快速开始 + 3 最近访问 + 2 最近动态 + 单测
5. T5: admin router 6 path 路由(UsersPage/UserAuditPage/RolesPage/DepartmentsPage/PermissionsPage/DataPermissionsPage)
6. T6: admin data/{users,roles,departments,permissions,dataPermissions}.ts mock 文件
7. T7: admin Views 5 个子页 + 1 个 UserAuditPage = 6 文件实现
8. T8: admin views 6 文件 vitest 单测
9. T9: 跨 app e2e(portal → /admin/users)扩展 V2 cross-app-jump
10. T10: 14-gate verify(4 vitest + 3 playwright + 3 tsc + 3 vite build + 1 nginx 5-path curl)
11. T11: archive frontend-product-shell

总耗时估算:2.5-3 个 session(每 session 3-4 task)。

## 10. V2 worktree cherry-pick 顺序

V3 要把 V2 的 canvas 改动拿到 V1 main 上(因为 V2 在 worktree 上,V3 在 V1 main 上)。策略:
- V2 worktree 有 9 个 commit,从 `9655018` (portal dual-React 修复) 到 `bb1f7ae` (T9 cross-app e2e)
- 跟 V3 相关的:59cfc26(canvas 23 .tsx 删 antd)、abb985c + b48c200(canvas vitest fix)、5c08a7a(canvas package.json + vitest config)、ef61023(web T8 nginx portal)、bb1f7ae(portal cross-app e2e)
- 不需要的:953a462/9619ece (docs commits)
- cherry-pick 顺序:从最早 canvas 改到最近,逐个解冲突

或者更简单:V3 plan 第一步是 merge V2 branch into V3,然后 V3 在合并后的代码上做 admin 5 子页。

**待用户决定 merge vs cherry-pick**(V3 计划中加一行 ask)。

## 11. 变更产物文件清单

设计完毕。下一步:openspec instructions 拉 `tasks.md` 模板 + 填充 tasks,把本文档 commit + 自我审。
