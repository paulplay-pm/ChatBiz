# tasks: implement-canvas-ui

> 子 skill 派发: `superpowers:subagent-driven-development`(fresh subagent per task + spec/quality 两段 review)。
> 单条任务 ≤ 2h,每条编码任务配对一条验证任务。

## 1. workflow-engine auth 升级 (Q10 触发的 follow-up)

- [x] 1.1 在 `services/workflow-engine/app/api/workflows.py` 改 `get_user_id` dependency:优先 `Authorization: Bearer <jwt>`(用 PyJWT 解析取 `sub`),fallback `X-User-Id` header
- [x] 1.2 把 7 个 router (workflows / validate / run / runs / approvals / nodes / health) 全部用新的 `get_user_id`
- [x] 1.3 加 `pyjwt>=2.8` 到 `pyproject.toml` runtime deps
- [x] 1.4 写 1 个 `test_auth_upgrade.py`:Bearer JWT 解析 / X-User-Id fallback / 无效 JWT 401 / 过期 JWT 401
- [x] 1.5 验证 + commit "feat(workflow-engine): upgrade auth to Authorization Bearer JWT"

## 2. 脚手架 + 路由

- [x] 2.1 `web/canvas/` 创建: `pnpm init` + `vite.config.ts` + `tsconfig.json`(strict) + `package.json`(19+ deps)
- [x] 2.2 写 `index.html` + `src/main.tsx` + `src/App.tsx` 框架
- [x] 2.3 装 19+ dev dep:react / react-dom / @xyflow/react / zustand / @tanstack/react-query / @rjsf/core / @rjsf/validator-ajv8 / antd / axios / eventsource-parser / react-router-dom / vitest / @testing-library/react / @playwright/test / eslint / typescript
- [x] 2.4 React Router 6 路由:`/login` / `/workflows` / `/workflows/:id/edit` / `/runs/:run_id` / `/chatflow` / `/settings` + `*` 404
- [x] 2.5 写 Vite dev proxy:`/api/auth/*` → 假 IAM 端点(localhost:9999)+ `/api/nodes/*` + `/workflows/*` + `/runs/*` + `/approvals/*` → `localhost:8001`
- [x] 2.6 写 `tsconfig.json` 严格模式(`strict: true` + `noUncheckedIndexedAccess: true` + `noImplicitAny: true`)+ `package.json` 脚本(dev / build / test / e2e / lint)
- [x] 2.7 验证:`pnpm tsc --noEmit` 0 error + `pnpm dev` 启动 OK + commit "feat(canvas-ui): scaffold + 7 routes + Vite proxy"

## 3. 全局 store + 顶部栏 + 侧边栏 (canvas-shell)

- [x] 3.1 写 `src/store/useUIStore.ts`(Zustand 持久化到 localStorage):侧边栏展开 / 暗色主题 / 当前选中 workflow_id
- [x] 3.2 写 `src/store/useAuthStore.ts`(Zustand 不持久化):JWT token + decoded user info
- [x] 3.3 写 `src/store/useCanvasEditStore.ts`(Zustand 持久化 dirty 状态):画布节点 / 边 / dirty / 最近保存版本
- [x] 3.4 写 `src/components/TopBar.tsx`(Ant Design):logo + 工具栏 + 通知 + 用户头像下拉(登出)
- [x] 3.5 写 `src/components/Sidebar.tsx`(Ant Design Menu):5 主菜单 + 可折叠 + 移动端汉堡
- [x] 3.6 写 `src/components/ErrorBoundary.tsx`:顶层 React Error Boundary + fallback UI
- [x] 3.7 写 `src/lib/apiClient.ts`:axios 实例 + Authorization Bearer header 注入 + 401 拦截跳 login
- [x] 3.8 写 `src/components/AppLayout.tsx`:TopBar + Sidebar + Outlet(react-router)
- [x] 3.9 验证 + commit "feat(canvas-ui): global stores + TopBar + Sidebar + ErrorBoundary + apiClient"

## 4. 登录页 + 假 IAM 端点 (canvas-auth)

- [x] 4.1 写 `src/pages/LoginPage.tsx`:username + password 表单 + 提交调 `/api/auth/login`
- [x] 4.2 写 `vite-plugin-dev-iam.ts`(Vite dev plugin):暴露 `POST /api/auth/login` 端点(接受任意非空 username 返 mock JWT)+ `GET /api/auth/me`(decoded JWT)
- [x] 4.3 写 `src/lib/jwt.ts`:jwt-decode 包装 + exp 过期检查
- [x] 4.4 写 `src/components/RequireAuth.tsx`:HOC 包装路由,未登录跳 `/login?redirect=<原 URL>`,已登录访问 `/login` 跳 `/workflows`
- [x] 4.5 写 `src/components/UserMenu.tsx`:Ant Design Avatar + Dropdown(登出按钮)
- [x] 4.6 写 `tests/auth.test.ts`(Vitest):login 流 / 401 重定向 / dev fallback
- [x] 4.7 验证 + commit "feat(canvas-ui): login + dev IAM + RequireAuth + dev fallback"

## 5. workflow 列表页 (canvas-workflow-list)

- [x] 5.1 写 `src/hooks/useWorkflows.ts`(React Query):list + search + filter + create + delete
- [x] 5.2 写 `src/pages/WorkflowListPage.tsx`:Ant Design List + 搜索框(debounce 300ms)+ 3 筛选(status/type/sharing)
- [x] 5.3 写 `src/components/WorkflowCard.tsx`:6 字段(name / created_at / version / status / run_count / sharing)+ 收藏按钮 + 删除按钮
- [x] 5.4 写 `src/components/CreateWorkflowModal.tsx`:name + mode(workflow/chatflow)输入 + 提交
- [x] 5.5 写 `src/components/DeleteConfirmModal.tsx`:确认删除 + 调 DELETE 端点
- [x] 5.6 写 5 个 React Query hooks:`useWorkflows` / `useCreateWorkflow` / `useDeleteWorkflow` / `useUpdateWorkflow` / `useToggleFavorite`
- [x] 5.7 验证 + commit "feat(canvas-ui): workflow list page + search + filter + create + delete"

## 6. 画布编辑器 (canvas-editor)

- [x] 6.1 写 `src/hooks/useNodeSchema.ts`:useQuery 缓存 `GET /api/nodes/:type/schema`
- [x] 6.2 写 `src/components/canvas/CanvasPage.tsx`:ReactFlowProvider + React Flow + 14 节点 wrapper + minimap + controls
- [x] 6.3 写 `src/components/canvas/NodePanel.tsx`:左侧节点面板 + 4 分类 + 14 节点图标
- [x] 6.4 写 `src/components/canvas/NodeSearchModal.tsx`:`/` 快捷键唤出 + 搜索框
- [x] 6.5 写 `src/components/canvas/ConfigPanel.tsx`:右侧 @rjsf/core 动态 config 表单
- [x] 6.6 写 `src/components/canvas/nodes/{start,end,variable_assign,condition,llm,knowledge,agent,http,code,approval,loop,iterate,subflow,extract}.tsx`:14 节点 Custom Node Wrapper(每节点 ~50-80 行)
- [x] 6.7 写 `src/components/canvas/EdgeConditionMenu.tsx`:右键边 → 设置条件 + Jinja2Editor
- [x] 6.8 写 `src/components/canvas/DragLoopDetector.ts`:本地 DFS cycle detection + 调用 `onConnect` 时阻止
- [x] 6.9 写 `src/components/canvas/AutoLayout.ts`:dagre 算法自动布局(从 dagre 库)
- [x] 6.10 写 `src/hooks/useSaveWorkflow.ts`:POST 创建 / PUT 更新 + dirty tracking
- [x] 6.11 写 `src/hooks/useUndoRedo.ts`:zundo 中间件 + 撤销/重做
- [x] 6.12 验证:`pnpm tsc --noEmit` 0 error + 14 节点可拖出 + DFS 防环 + commit "feat(canvas-ui): canvas editor + 14 nodes + DFS + rjsf forms"

## 7. 调试器 (canvas-debugger)

- [x] 7.1 写 `src/hooks/useRunEvents.ts`:EventSource 订阅 `/runs/:run_id/events` + 状态同步到 useCanvasEditStore
- [x] 7.2 写 `src/pages/RunDebuggerPage.tsx`:status badge + 节点列表 + 终态徽章 + 重试按钮
- [x] 7.3 写 `src/components/debugger/NodeEventTimeline.tsx`:node_event 时间线(按 started_at 升序)+ 过滤(status)+ 展开(input_json / output_json / error_class)
- [x] 7.4 写 `src/components/debugger/RetryCancelButtons.tsx`:"重试" 调 POST `/workflows/:id:run`;"取消" V1.0 follow-up 标 disabled
- [x] 7.5 写权限检查:started_by != current_user 时跳 403
- [x] 7.6 验证 + commit "feat(canvas-ui): debugger page + SSE consumer + node event timeline"

## 8. chatflow 对话页 (canvas-chatflow)

- [x] 8.1 写 `src/pages/ChatflowPage.tsx`:workflow 下拉 + 对话气泡流 + 输入框
- [x] 8.2 写 `src/components/chatflow/ChatBubble.tsx`:user / AI / 工具调用 / 审批卡片 4 类气泡
- [x] 8.3 写 `src/components/chatflow/ApprovalInlineCard.tsx`:若 current user 是 approver 显示 "批准/拒绝" 按钮
- [x] 8.4 写 `src/hooks/useSession.ts`:localStorage 存 X-Session-Id(URL hash 同步)
- [x] 8.5 验证 + commit "feat(canvas-ui): chatflow page + 4 bubble types + inline approval"

## 9. 设置页 + 收尾

- [x] 9.1 写 `src/pages/SettingsPage.tsx`:暗色主题切换 / 主题色 / 节点图标样式 3 个 Ant Design form
- [x] 9.2 写 `web/canvas/.gitignore`:`node_modules/` `dist/` `.vite/` `coverage/` `playwright-report/`
- [x] 9.3 写 `web/canvas/.editorconfig`(跟仓库根 .editorconfig 一致)
- [x] 9.4 写 `web/canvas/README.md`:启动 / 测试 / 部署 / 故障排查
- [x] 9.5 验证 + commit "feat(canvas-ui): settings page + gitignore + editorconfig + README"

## 10. Vitest 单元 + Playwright e2e

- [x] 10.1 写 `vitest.config.ts` + 4 个 vitest unit test:ConfigPanel / DragLoopDetector / DFS / useCanvasEditStore
- [x] 10.2 写 `playwright.config.ts` + `e2e/paul-monthly-report.spec.ts`:1 完整跨 service e2e(创建 → 拖 5 节点 → 连线 → 填 config → 保存 → 调 :run → 收 SSE 事件)
- [x] 10.3 写 `e2e/auth.spec.ts`:login + 401 重定向 + 登出
- [x] 10.4 写 `e2e/canvas-drag-loop.spec.ts`:DFS 防环
- [x] 10.5 验证:Vitest 全过(覆盖率 ≥ 100%)+ Playwright e2e 全过 + commit "feat(canvas-ui): Vitest unit + Playwright e2e + paul 月报跨 service test"

## 11. verify.py CI gate + 文档

- [x] 11.1 写 `web/canvas/verify.py` 18+ gate:7 路由 / 14 节点 wrapper / @rjsf/form / DFS / SSE / playwright 配置 / pnpm lock / TS 严格 / Vite proxy / Ant Design / Zustand 持久化 / OAuth Bearer / dev fallback / 全局 ErrorBoundary / 5 store / workflow-engine auth 升级 commit
- [x] 11.2 跑 verify.py 确认 18+ gate 全过
- [x] 11.3 写 `docs/prototype.html` 与 `web/canvas/` UI 对照表(readme 段):7 页面映射
- [x] 11.4 最终 commit "feat(canvas-ui): complete + verify gate + 1 跨 service e2e" + 整理 commit history

---

**统计**: 11 大组, ~50 子任务。每条 ≤ 2h。编码任务配对验证。

**关键路径**:
- Task 1 (workflow-engine auth 升级) → 全部前端 task 依赖
- Task 2-4 (scaffold + stores + auth) → 全部后续 task 依赖
- Task 5-6 (workflow list + canvas editor) → 用户能编辑 workflow
- Task 7 (debugger) → 用户能实时看运行
- Task 8 (chatflow) → 用户能多轮对话
- Task 9-11 (settings + tests + verify) → 收口

**实施时间估算**(subagent-driven 3-4 阶段并发): ~6-9h
