## Why

`web/canvas`（ChatBiz 前端 SPA，Vite 5 + React 18 + TypeScript）当前仅 3 个 unit test 文件（13 tests），覆盖率集中在 `AutoLayout.ts`、`DragLoopDetector.ts`、`useCanvasEditStore.ts`，其他 30+ 源文件（pages/hooks/components/stores/lib）覆盖率为 0%。`pnpm exec vitest run --coverage` 整体覆盖率约 6%。

本次 change 把覆盖率推到 100%，并把 vitest coverage gate 写入 `verify.py`，作为前端 release gate——对齐 `fix-workflow-engine-100pct-coverage` / `fix-audit-isolation-real-tests-100pct-coverage` / `fix-credential-real-tests-100pct-coverage` 三个后端 change 的工程规范。

## What Changes

**canvas 100% 覆盖率门禁**
- From: `pnpm exec vitest run --coverage` 6% 整体覆盖，0 行覆盖率门禁
- To: 100% src 覆盖（除 test setup + 类型声明 + dev iam plugin）+ `verify.py` 加 `vitest run --coverage --coverage.thresholds.100` gate
- Reason: 业务前端（7 路由 + 14 节点编辑器 + Chatflow + 调试器）需要 release gate 防止回归
- Impact: 非破坏性；只改 `tests/` + `verify.py` + `vitest.config.ts` + `package.json`

**14 节点 wrapper 渲染测试**
- From: `NodeWrapper` 组件 0 覆盖
- To: 单测覆盖 14 种节点（start/end/variable_assign/condition/llm/knowledge/agent/http/code/approval/loop/iterate/subflow/extract）的渲染 + 状态色
- Reason: 14 节点编辑器是 canvas 核心交互，必须有 release gate

**Hooks + Stores + Lib 单元覆盖**
- From: 所有 hooks / stores / lib 0 覆盖
- To: 全部 hooks（7）+ stores（3）+ lib（apiClient + jwt）单测覆盖
- Reason: useSession / useRunEvents / apiClient 等是状态管理与安全关键

**API 客户端 / 401 重定向覆盖**
- From: `apiClient.ts` 0 覆盖
- To: 单测覆盖 Bearer header 注入、401 重定向逻辑、dev fallback
- Reason: canvas-auth spec 关键契约

**组件单测**
- From: 9 个组件（TopBar/Sidebar/AppLayout/ErrorBoundary/RequireAuth 等）0 覆盖
- To: 全部组件 RTL 渲染 + 交互单测
- Reason: 顶层 UI 单元也是 release 防御

**verify.py 覆盖率门禁**
- From: `verify.py` 仅跑测试 + 安全 + OpenAPI + 14 节点 + 7 路由等结构检查
- To: 加 `pnpm exec vitest run --coverage --coverage.thresholds.lines=100 --coverage.thresholds.functions=100 --coverage.thresholds.statements=100` 作为新增 check
- Reason: 与后端 verify.py 风格一致

## Impact

- 影响代码：`web/canvas/tests/**`、`web/canvas/verify.py`、`web/canvas/vitest.config.ts`、`web/canvas/package.json`、少量产品代码 pragma
- 影响 spec：无新行为契约；canvas 6 spec 已有 requirement 不变
- 影响命令：`pnpm exec vitest run --coverage` 必须 100%；`python3 verify.py` 通过
- Non-goals：不重写组件结构、不新增功能、不修改 vite.config.ts 的 proxy 设置
- 源关联：`docs/architecture.md` §4.3.1 + `openspec/specs/canvas-*` + `openspec/specs/canvas-real-test-gates`
