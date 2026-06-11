## Context

`web/canvas` 是 ChatBiz 前端 SPA，承载 7 路由（login / workflows / canvas editor / debugger / chatflow / settings / 404）。eng-review 锁定它必须与 3 个后端服务（workflow-engine:8001 / audit-and-isolation:8080 / credential:8000）以 Vite proxy + 容器化方式对接。前端 Node Contract 走 `GET /api/nodes/:type/schema` + `rjsf/core` 动态表单渲染 14 节点类型。

当前 13 个 vitest tests / 6% 覆盖率 / 0 release gate，与已完成的 3 个后端覆盖率 change（`fix-workflow-engine` / `fix-audit-isolation` / `fix-credential`）规格不对齐。

本 change 走 `superpowers-bridge` schema，**只改 tests 与测试基础设施**，对生产代码做最小（必要时）的 pragma 调整。

## Goals / Non-Goals

**Goals:**

- 让 `web/canvas/src/**` 达到 vitest 100% 行/函数/分支覆盖
- 维持 `pnpm test` / `pnpm typecheck` / `pnpm build` 全过
- 维持 3 个 playwright e2e spec（`auth.spec.ts` / `node-schema.spec.ts` / `paul-monthly-report.spec.ts`）通过
- 把 vitest coverage gate 加进 `verify.py`，与后端 verify 风格一致
- 对不可达代码（如未触发的可选回调）使用 `# pragma: no cover` 而非 artificial monkeypatch 测试

**Non-Goals:**

- 不重写任何 React 组件结构
- 不新增功能或路由
- 不修改 vite.config.ts 的 proxy 配置
- 不引入新的 npm 依赖（已用 @testing-library/react + @testing-library/user-event + jsdom）
- 不实现新的 14 节点类型或新 spec

## Decisions

### D1：测试环境用 jsdom + @testing-library/react

- **选择**：vitest 在 `jsdom` 环境跑 React 组件测试；hooks 用 `renderHook` 单独测试
- **理由**：与现有 `tests/AutoLayout.test.ts` / `tests/DragLoopDetector.test.ts` / `tests/useCanvasEditStore.test.ts` 一致
- **已考虑 alternative**：用 happy-dom——vitest v1.6 + jsdom v24 + RTL v16 是当前项目 stack；切换会增加 drift

### D2：组件测试用 RTL render + userEvent

- **选择**：复杂组件用 `@testing-library/react` 的 `render` + `screen` 断言；用户交互用 `userEvent`；不引 `mock-service-worker`
- **理由**：RTL 已装；mock-service-worker 在本项目无现有用法
- **已考虑 alternative**：直接挂载 `react-dom/test-utils`——RTL 更现代、断言更清晰

### D3：apiClient 测试用 axios mock adapter / fetch mock

- **选择**：用 `vi.mock("axios")` mock axios 实例
- **理由**：apiClient 内部用 axios；mock 实现即可捕获 401 redirect、Authorization header
- **已考虑 alternative**：MSW（mock service worker）——增加依赖，axios mock 足够

### D4：真测试优先 + 最小 pragma

- **选择**：只测真实行为，外部边界用 mock；不可达防御性兜底用 `# pragma: no cover` + 注释
- **理由**：与 `fix-workflow-engine-100pct-coverage` / `fix-credential-real-tests-100pct-coverage` 同等级别纪律
- **已考虑 alternative**：放宽 `--coverage.thresholds` 到 80%——但 100% 是 3 个后端都达到的 release bar，前端应一致

### D5：vitest coverage 配置

- **选择**：在 `vitest.config.ts` 配 `coverage.thresholds.lines/functions/statements/branches=100`，CI 失败 fast
- **理由**：vitest 1.6 支持原生 threshold 配置
- **已考虑 alternative**：用 `verify.py` 跑 `vitest run --coverage --coverage.thresholds.lines=100`——CLI flag 与 config 同时给均可

### D6：spec canvas-real-test-gates 不变

- **选择**：本 change 强化 canvas-real-test-gates 的 "vitest unit tests" + "playwright e2e specs >= 3" check
- **理由**：与现有 verify.py check 7/12 一致
- **已考虑 alternative**：拆出新 spec（test-coverage-100）——但 canvas-real-test-gates 名称已足够涵盖

## Risks / Trade-offs

- [Risk] 14 节点 wrapper 的 META map 复杂，render 全部 14 个测试可能难以维护 → Mitigation: 写一个数据驱动的 `it.each` 表格，结构清晰
- [Risk] apiClient 全测要 mock axios + window.location.href 跳转 → Mitigation: 用 `vi.stubGlobal("location", { href: "" })`
- [Risk] 组件用 `useEffect` / `useState` + React Query 时 RTL 行为复杂 → Mitigation: 必要时用 `await waitFor`
- [Risk] 配置 pragma 后回归真实不可达 → Mitigation: 注释说明为什么不可达 + verify.md 列表
- [Trade-off] 不引 e2e 新 spec 覆盖率提高 → 接受：现有 3 个 e2e 已覆盖关键 user flow

## Migration Plan

1. **Baseline**：跑 `pnpm exec vitest run --coverage`，记录 baseline 覆盖率表
2. **Tests first**：按模块从底层到 UI 写测试
   - lib/ (apiClient, jwt)
   - hooks/ (useDebounce, useSession, useWorkflows, useNodeSchema, useRunEvents, useSaveWorkflow, useUndoRedo)
   - stores/ (useUIStore, useAuthStore, useCanvasEditStore 已部分覆盖)
   - components/ (TopBar, Sidebar, AppLayout, ErrorBoundary, RequireAuth)
   - components/canvas/ (NodePanel, NodeSearchModal, EdgeConditionMenu, ConfigPanel, AutoLayout, DragLoopDetector, nodes/index)
   - components/chatflow/ (ChatBubble, ApprovalInlineCard)
   - components/debugger/ (NodeEventTimeline, RetryCancelButtons)
   - pages/ (CanvasPage, ChatflowPage, LoginPage, NotFoundPage, RunDebuggerPage, SettingsPage, WorkflowListPage)
3. **Pragmas**：仅在不可达分支加 `# pragma: no cover` + 注释
4. **verify.py**：加 `pnpm exec vitest run --coverage` 门禁
5. **Docs**：写 `verify.md` / `retrospective.md`

Rollback：本 change 不改产品功能；如需回退，删 `tests/` 新增 + 改 `verify.py` 即可。

## Open Questions

1. 是否把 vitest 跑在 worker pool size 设为 4（并行加速）？默认即可。
2. 是否对 useRunEvents 的 EventSource mock 复杂到需 polyfill？当前决定用 `vi.fn()` mock EventSource 类。
3. 是否需要把 antd 5 组件库的某些 props 也加入 RTL 断言？默认仅断言关键 prop 即可。
