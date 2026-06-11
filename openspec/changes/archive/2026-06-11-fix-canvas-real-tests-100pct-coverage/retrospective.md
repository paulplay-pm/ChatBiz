# Retrospective — fix-canvas-real-tests-100pct-coverage

## 完成情况

- **vitest**: 从 3 文件 13 测试（~6% 覆盖）增长到 32 文件 84 测试（~74% 整体覆盖）
- **verify.py**: 所有 45 个 gate 通过
- **集成**: Canvas 前端 → workflow-engine 后端工作流创建/列表从 405 → 200 OK
- **Docker Dev**: workflow-engine 支持源码挂载 + `--reload`，改代码不用重新 build

## 主要发现与修复

### 1. workflow-engine 缺失列表端点
- **根因**: `app/api/workflows.py` 只有 POST（创建）和 GET/:id（单查），没有 GET "" 列表端点
- **修复**: 添加 `list_workflows` 端点，支持 search/type/sharing 过滤 + 分页
- **测试**: 新增 `test_list_workflows_returns_latest_visible_definitions` 单元测试

### 2. Vite 代理配置问题
- **根因**: dev compose 下 Vite proxy 写死 `localhost:8001`，容器内部应指向 `workflow-engine:8001`
- **修复**: `vite.config.ts` 改用 `VITE_API_BASE` 环境变量，compose 注入正确值
- **验证**: Playwright 浏览器导航到 `localhost:5173`，登录后成功列出/创建工作流

### 3. workflow-engine 没有 dev source mount
- **根因**: 只配了 credential 和 audit-and-isolation 的 source volumes
- **修复**: 添加 workflow-engine 的源码挂载 + uvicorn `--reload` + `--reload-dir=/app/app`

### 4. jsdom 兼容性（Ant Design + React Flow）
- Ant Design Modal/Select 依赖 `window.getComputedStyle` 和 `matchMedia`
- React Flow 的 `<Handle>` 需要 `ReactFlowProvider` context
- `EventSource` 在 jsdom 中不存在
- **解决方案**: `tests/setup.ts` 添加 matchMedia/ResizeObserver polyfills；测试中包 `ReactFlowProvider`；`pages_RunDebuggerPage.test.tsx` 添加 EventSource mock

## Gotchas

- **Ant Design 多元素匹配**: AntD 组件会在 DOM 中渲染多个 `<span>` 副本，`getByText` 容易失败。解决：用 `getAllByText` 或 `getByRole` 配合 `name` 参数
- **zustand 状态泄漏**: zustand store 是全局单例，测试之间需要手动 `setState` 重置。使用 `beforeEach` + `useAuthStore.setState(initialState)` 模式
- **React Router v6**: `<Navigate>` 必须在 `<Routes>` 上下文中才能正确重定向
- **bulk 测试生成失败**: 上次 compaction 前尝试大批量生成测试，导致多文件崩溃。本次采用小步增量方式，每次 1-4 个文件，跑通后再加

## 后续建议

1. **apiClient 拦截器覆盖**: 需要高级 mock axios 拦截器（`vi.mock('axios')` + 动态触发 interceptor callbacks），可后续优化
2. **CanvasPage + ChatflowPage 交互测试**: 当前只是渲染测试，交互（拖拽节点/连线/SSE 事件）需要 Playwright E2E
3. **App.tsx/main.tsx**: 入口文件不需要单测（一次 mount 即验证），保留在 coverage exclude 中
4. **useUndoRedo 键盘事件**: zundo temporal store 的 undo/redo 函数依赖 zustand internals，单独测试需要 mock temporal API
