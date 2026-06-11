## MODIFIED Requirements

### Requirement: 构建产物 + dev proxy
`pnpm build` MUST 输出 dist/ 静态资源(总 < 5MB);Vite dev server MUST proxy `/api/auth/*` → 假 IAM 端点 + `/api/nodes/*` + `/workflows/*` + `/runs/*` + `/approvals/*` → workflow-engine:8001。`pnpm typecheck` 和 `pnpm build` MUST 真实运行并退出码 0。

#### Scenario: build 成功
- **WHEN** `pnpm build` 跑
- **THEN** 系统 MUST 输出 `dist/index.html` + `dist/assets/*.js` + `dist/assets/*.css`;允许 bundle-size warning;命令退出码 MUST 为 0

#### Scenario: Vite proxy 跨域
- **WHEN** dev 模式 fetch `/api/nodes/llm/schema`
- **THEN** 系统 MUST proxy 到 `http://localhost:8001/api/nodes/llm/schema` + 带 `Authorization: Bearer <jwt>`;无 CORS 错

#### Scenario: typecheck 成功
- **WHEN** `pnpm typecheck` 跑
- **THEN** 命令 MUST 退出码 0,TypeScript strict 模式无 error
