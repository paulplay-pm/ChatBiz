## MODIFIED Requirements

### Requirement: 登录页 + 假 IAM 端点
`/login` 路由 MUST 提供 username + password 输入框(dev 模式:任何非空 username 都能登录,password 任意);点 "登录" → POST `/api/auth/login` 返 `{token: <jwt>, user: {id, name, email}}`;前端用 jwt-decode 解析存 useAuthStore。production 接 Keycloak 时只改 `/api/auth/login` 内部实现,UI 不变。该流程 MUST 被 Playwright e2e 覆盖。

#### Scenario: dev 模式登录
- **WHEN** 用户输入 username="paul" + password="任意" + 点 "登录"
- **THEN** Vite proxy MUST POST `/api/auth/login` → 假 IAM 端点返 `{token: "eyJ...", user: {id: "u-paul", name: "Paul", email: "paul@chatbiz"}}`;前端存 useAuthStore

#### Scenario: 假 IAM 端点实现
- **WHEN** dev 模式启动
- **THEN** 系统 MUST 暴露 `POST /api/auth/login` 在 dev server;`password` 字段 MUST 接受任意非空字符串;token MUST 是有效 JWT 结构(可 jwt-decode 解析,含 sub + exp claims)

#### Scenario: Playwright 登录 e2e
- **WHEN** 执行 `npx playwright test e2e/auth.spec.ts`
- **THEN** 测试 MUST 打开 `/login`,填写 username/password,点击登录,并断言进入 `/workflows`
