# ChatBiz Canvas UI

ChatBiz 可视化画布 SPA — Vite + React 18 + TypeScript 5.4 + React Flow 12 + Zustand 4 + React Query 5。

## 启动

```bash
cd web/canvas
pnpm install          # 安装 19+ 依赖
cp .env.example .env  # 复制环境变量
pnpm dev              # http://localhost:5173
```

## 依赖后端

| 服务 | 端口 | 用途 |
|------|------|------|
| workflow-engine | 8001 | 画布 CRUD + 节点 schema + 调试 SSE |
| audit-and-isolation | 8080 | LLM 网关(经 workflow-engine) |
| credential | 8000 | 凭证管理(经 workflow-engine) |

## 测试

```bash
pnpm test              # vitest 单元
pnpm test:coverage     # + 覆盖率
pnpm e2e               # playwright
pnpm typecheck         # tsc --noEmit

## 构建

```bash
pnpm build            # → dist/
pnpm preview          # 本地预览构建产物
```

## 7 个页面

| 路由 | 页面 |
|------|------|
| /login | 登录(dev IAM mock) |
| /workflows | 工作流列表 |
| /workflows/:id/edit | 画布编辑器(React Flow + 14 nodes) |
| /runs/:runId | 调试器(SSE实时) |
| /chatflow | Chatflow 对话 |
| /settings | 设置 |
| * | 404 |

## 技术栈

- Vite 5 + React 18 + TypeScript 5.4 strict
- @xyflow/react 12(画布)
- Zustand 4(画布 state)
- React Query 5(服务端 state)
- @rjsf/core 5(动态 config 表单)
- Ant Design 5(UI 组件)
- Vitest + RTL + Playwright(测试)
