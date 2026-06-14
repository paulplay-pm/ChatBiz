# frontend-product-shell — Tasks

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 ChatBiz portal/canvas/admin 三前端对齐 `docs/prototype.html` 9 张目标图(登录 → 主框架 → 工作流 + 5 个系统管理子页)。

**Source design doc:** `docs/superpowers/specs/2026-06-14-frontend-product-shell-design.md`
**Source openspec design:** `openspec/changes/frontend-product-shell/design.md`
**Base branch:** `worktree-v3-admin-refactor`(已 merge V2 via `ee776aa`)

---

## 1. 入口修复

- [x] 1.1 改 `web/index.html` 删静态三卡,加 `<meta http-equiv="refresh" content="0; url=/portal/login">` + `<link rel="canonical" href="/portal/login">` + body 内 `<a href="/portal/login">` 降级链接
- [x] 1.2 验证 `curl -s http://localhost:5173/ | grep -c 'meta http-equiv="refresh"'` ≥ 1 → 1 ✓
- [x] 1.3 验证 `curl -s http://localhost:5173/ | grep -c 'card'` = 0 → 0 ✓
- [x] 1.4 Commit: `fix(web): index.html 改 meta refresh → /portal/login` → `6e42907`

## 2. portal Sidebar 5 分组

- [x] 2.1 改 `web/portal/src/data/menu.ts`:SECTIONS 5 项(工作区/探索/配置中心/运维/系统管理)+ MenuItem 加 `external: boolean` 字段
- [x] 2.2 把 ~24 个 menu item 按 5 分组填好(系统管理 6 项 `external: true` 跳 admin,工作流/Chatflow/Agent 3 项 `external: true` 跳 canvas)
- [x] 2.3 改 `web/portal/src/components/AppLayout.tsx`:`handleSelect` 检测 `item.external` → `window.location.assign(item.href)`,否则 `useNavigate`
- [x] 2.4 改 `web/portal/tests/menu.test.ts` 断言 5 section + 24 item + system 6 项全部 `external: true`
- [x] 2.5 跑 `pnpm exec vitest run web/portal/tests/menu.test.ts` → 8/8 PASS
- [x] 2.6 跑 `pnpm exec tsc --noEmit` 在 portal → EXIT 0
- [x] 2.7 Commit: `refactor(portal): menu 5 分组 + external 跨 app 跳转` → `e5f38dc`

## 3. portal DashboardPage 4 metric + 快速开始 + 最近访问/动态

- [x] 3.1 新建 `web/portal/src/data/dashboard.ts` 导出 `METRICS`(4 项,spec 锁 12/5/2,456/456K)、`QUICK_STARTS`(4 项)、`RECENT_ACCESSES`(3 项)、`RECENT_ACTIVITIES`(2 条)
- [x] 3.2 改 `web/portal/src/pages/DashboardPage.tsx`:`<h1>工作台</h1>` + 4 MetricCard + 4 快速开始卡(2×2,跨 app 跳 canvas)+ 最近访问 List + 最近动态 List
- [x] 3.3 改 `web/portal/tests/pages_DashboardPage.test.tsx` 5 断言(工作台标题 + 4 metric 值 + 4 快速开始 + 3 最近访问 + 2 动态 + mock 来源)
- [x] 3.4 跑 `pnpm exec vitest run` → 5/5 PASS
- [x] 3.5 跑 `pnpm exec tsc --noEmit` → EXIT 0
- [x] 3.6 Commit: `feat(portal): DashboardPage 4 metric + 快速开始 + 最近访问/动态` → `8979b2b`

## 4. admin mock data 5 文件

- [x] 4.1 新建 `web/admin/src/data/users.ts` 导出 `MOCK_USERS`(3 行:张三/李四/王五)
- [x] 4.2 新建 `web/admin/src/data/roles.ts` 导出 `MOCK_ROLES`(4 角色:超管/部门管理员/开发者/普通用户,各 3+ 成员,矩阵 workflow+conversation × 5 操作)
- [x] 4.3 新建 `web/admin/src/data/departments.ts` 导出 `MOCK_DEPARTMENTS`(树状:技术部→后端组/前端组,产品部,运营部)
- [x] 4.4 新建 `web/admin/src/data/permissions.ts` 导出 `MOCK_MODULES`(7 模块 × 11 权限点)+ `PERMISSION_ACTIONS`(6 操作)+ `ROLE_OPTIONS`(4 角色)+ `MOCK_PERMISSIONS`(4 角色 × 11 点 × 6 操作矩阵)
- [x] 4.5 新建 `web/admin/src/data/dataPermissions.ts` 导出 `MOCK_RULES`(3 规则:个人/部门/跨部门)+ `MOCK_SHARES`(4 共享记录)
- [x] 4.6 跑 `pnpm exec tsc --noEmit` 在 admin → EXIT 0
- [x] 4.7 Commit: `feat(admin): data/ 5 个 mock 文件`

## 5. admin router 6 path 替换 PlaceholderView

- [ ] 5.1 新建 `web/admin/src/views/UsersPage.tsx` 渲染 Table(7 列,3 行)+ 工具栏(搜索/批量导入/导出/添加用户)
- [ ] 5.2 新建 `web/admin/src/views/UserAuditPage.tsx` 过滤 status='pending' + 通过/拒绝按钮
- [ ] 5.3 新建 `web/admin/src/views/RolesPage.tsx` 4 角色卡 + 权限矩阵 + 顶部 info bar
- [ ] 5.4 新建 `web/admin/src/views/DepartmentsPage.tsx` 树状 + +添加部门按钮
- [ ] 5.5 新建 `web/admin/src/views/PermissionsPage.tsx` 矩阵大表 + 角色 dropdown + 只读 toggle
- [ ] 5.6 新建 `web/admin/src/views/DataPermissionsPage.tsx` 3 规则卡 + 共享记录表 + 基于部门 badge
- [ ] 5.7 改 `web/admin/src/router/index.tsx`:为 6 path 注册新 view(用 lazy import),其余 8 path 仍指向 PlaceholderView
- [ ] 5.8 跑 `pnpm exec tsc --noEmit` 在 admin 期望 EXIT 0
- [ ] 5.9 Commit: `feat(admin): 6 个真 view 替换 PlaceholderView`

## 6. admin views 6 文件 vitest 单测

- [ ] 6.1 新建 `web/admin/tests/views_UsersPage.test.tsx` 断言 3 行 + 7 列
- [ ] 6.2 新建 `web/admin/tests/views_UserAuditPage.test.tsx` 断言只显示 pending 行
- [ ] 6.3 新建 `web/admin/tests/views_RolesPage.test.tsx` 断言 4 角色卡 + 权限矩阵
- [ ] 6.4 新建 `web/admin/tests/views_DepartmentsPage.test.tsx` 断言树状节点数
- [ ] 6.5 新建 `web/admin/tests/views_PermissionsPage.test.tsx` 断言 7 模块 11 权限点
- [ ] 6.6 新建 `web/admin/tests/views_DataPermissionsPage.test.tsx` 断言 3 规则 + 4 共享记录
- [ ] 6.7 跑 `pnpm exec vitest run web/admin/tests/views_*.test.tsx` 期望全部 PASS
- [ ] 6.8 Commit: `test(admin): views 6 文件 vitest 单测`

## 7. admin SideNav + AppShell 微调

- [ ] 7.1 改 `web/admin/src/components/SideNav.tsx`:把顶部"工作区"label 改成"系统管理"(跟原型图 #8-13 一致)
- [ ] 7.2 改 `web/admin/src/components/AppShell.tsx`:header 标题从"ChatBiz Admin" 改成"系统管理",用户头像保留
- [ ] 7.3 跑 `pnpm exec tsc --noEmit` 在 admin 期望 EXIT 0
- [ ] 7.4 跑 `pnpm exec vitest run` 在 admin 期望全 PASS
- [ ] 7.5 Commit: `refactor(admin): SideNav/AppShell 标题改"系统管理"`

## 8. 跨 app e2e(portal → /admin/users)扩展 V2

- [ ] 8.1 改 `web/portal/e2e/cross-app-jump.spec.ts`:加 1 case "portal: 点击系统管理→用户列表跳 /admin/users"(需先确认 nginx 容器起 5173)
- [ ] 8.2 跑 `pnpm exec playwright test --config=playwright.cross-app.config.ts` 期望 3/3 PASS
- [ ] 8.3 跑 `pnpm exec playwright test` 在 canvas 期望 6/8(=baseline)
- [ ] 8.4 跑 `pnpm exec playwright test` 在 admin 期望 ≥ baseline(1/4,若新增 5 子页 e2e 通过更多)
- [ ] 8.5 Commit: `test(portal): 跨 app e2e 加 portal → /admin/users`

## 9. portal→canvas 5-path curl + V1 baseline 对比

- [ ] 9.1 停 chatbiz-web 容器 + 重新 build `docker build -t chatbiz-web:v3 -f web/Dockerfile web/` + 起 v3 容器
- [ ] 9.2 5-path curl:`/` `/portal/login` `/canvas/` `/admin/` `/health` 全 200
- [ ] 9.3 用 playwright 跑 `cross-app-jump` 在新容器,期望 3/3 PASS(也验证 meta refresh)
- [ ] 9.4 对比 V1 baseline bundle:portal 201KB / canvas 838KB / admin 225KB,期望 0 回归

## 10. 14-gate verify

- [ ] 10.1 4 vitest:portal 33+N / canvas 84 / admin 1+N / ui N/A
- [ ] 10.2 3 playwright:portal 2+1 / canvas 6/8 / admin 1+ baseline
- [ ] 10.3 3 tsc:portal 0 / canvas 0 / admin 0
- [ ] 10.4 3 vite build:portal ~201KB / canvas ~838KB / admin ~225KB
- [ ] 10.5 1 nginx 5-path curl:全 200
- [ ] 10.6 14-gate 全 PASS,记 commit: `chore(ops): V3 frontend-product-shell 14-gate verify`

## 11. archive V3 change

- [ ] 11.1 `openspec archive frontend-product-shell --yes`
- [ ] 11.2 验证 `openspec/changes/archive/2026-06-14-frontend-product-shell/` 含 design.md + tasks.md + specs/ + proposal.md + brainstorm.md
- [ ] 11.3 Commit archive + push branch
- [ ] 11.4 V3 worktree 等合并到 main,后续 PR 由 V4 接管 SSO + react-flow e2e 修

---

## 任务统计

- **总任务数**:11 个一级 + ~30 个二级 checkbox
- **总耗时估算**:2.5-3 个 session(每 session 3-4 task)
- **每 task ≤ 2h**:✅ 全部符合
- **编码配对验证**:✅ T2-T8 每 task 都有 vitest/tsc 验证
- **不先实现后补测试**:✅ 单测在 view 实现同 commit 内

## 与 12 个 eng-review 锁定决策符合性

- 0 架构变更 ✅
- 0 后端 API 变更 ✅
- 0 端口变更 ✅
- 0 新 npm 依赖 ✅
- 0 docker compose 变更 ✅
- 仅前端形态重构 ✅
