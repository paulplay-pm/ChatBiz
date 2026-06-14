# frontend-product-shell — Brainstorm 原始记录

> **状态:** 已通过 superpowers:brainstorming 完成,本文件是决策链的精简记录。
> **完整 design 见:** `docs/superpowers/specs/2026-06-14-frontend-product-shell-design.md`

## 背景

用户 9 张图(已附图 #2/#5/#6/#7/#8/#9/#10/#12/#13)显示 ChatBiz portal/canvas/admin 三前端当前不符合原型 `docs/prototype.html` 形态:

1. `web/index.html` 是静态三卡跳转页,不是产品登录页
2. portal Dashboard 简陋(4 metric card),Sidebar 30+ 项,但分组与原型不一致
3. admin 14 个 menu 全是 PlaceholderView,5 个目标页(用户/角色/部门/权限/数据权限)需实现

## 决策链

### Q1: V3 change 实际 scope 应叫什么?

**选项 A: frontend-product-shell(大整合)** — 修 index.html + portal dashboard + sidebar 分组 + admin 5 子页实现
**选项 B: admin-5-pages + index-redirect(拆 2 个)** — 只做 admin + index,portal dashboard 留 V4
**选项 C: 先做 V3 收尾(canvas-drag-e2e-fix)再 V4** — 推迟 9 张图

**选 A**(用户已选)。理由:portal 跟 admin 都需要重构,拆 2 个 change 增加 openspec 治理负担;图 #2 跟 #5-13 是同一产品形态的不同切面,放一个 change 内部一致。

### Q2: V3 走哪个方案?

**A: 5 子项全做(推荐)** — index.html 改 redirect + portal DashboardPage 细改 + portal Sidebar 5 分组 + admin 5 子页实现 + portal→admin 跨 app 跳转
**B: 只 admin + index** — portal dashboard 留 V4
**C: A + 修 2 个 react-flow drag e2e**

**选 A**(用户已选)。理由:C 的 e2e 修跟 V3 frontend 整合正交,放单独 change 更干净;V3 先做产品形态,e2e 修放 V4。

### Q3: 9 张图细节 vs 当前 portal/admin 现状?

**决策**:严格按图保留 5 分组,删除非图项(原 30+ item 减到 ~24 个);admin 5 子页 mock 静态数据,0 后端调用。

### Q4: V2 worktree 怎么拿到 V3?

**Merge**(`git merge worktree-v2-canvas-refactor`,0 冲突) — 已执行 `ee776aa`。V2 8 commit 全进 V3,V3 在合并后的代码上做 admin 5 子页。

## 设计 trade-offs(已写进 design doc)

| Trade-off | 选择 | 理由 |
|---|---|---|
| portal Sidebar 跨 app 跳转 vs react-router 内部 | external: true 标记 + AppLayout 路由分流 | 跨 origin 不能 useNavigate |
| admin 5 子页 mock vs 真后端 | 纯 mock UI | 当前 V3 不接 backend,避免 scope 爆炸 |
| 5 子页数据 | `web/admin/src/data/*.ts` 静态 const | 类型安全 + 易测 + V4 替换 useQuery |
| 状态管理 | React useState/useReducer | 5 子页都是 CRUD-light,无 zustand 必要 |
| 跨 app session 共享 | 暂不做(V4 SSO) | localStorage 跨 app 不共享,接受重新登录 |
| V2 cherry-pick vs merge | merge | 0 冲突 + 简单 |

## 未决问题

- **章节 10 风险**: merge 后 V3 在 V2 基础上,5 子页实施时需 import `web/ui/primitives` (V2 移过去的),不能 import `web/portal/src/components/primitives`(已删除)。

## 接下来

- 用户已确认设计 OK + 选 merge
- 写 `proposal.md` + `specs/*.md` + `tasks.md`
- openspec 走完 5 artifact → apply-ready
