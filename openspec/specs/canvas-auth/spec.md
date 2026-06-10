# canvas-auth Specification

## Purpose
TBD - created by archiving change implement-canvas-ui. Update Purpose after archive.
## Requirements
### Requirement: 登录页 + 假 IAM 端点
`/login` 路由 MUST 提供 username + password 输入框(dev 模式:任何非空 username 都能登录,password 任意);点 "登录" → POST `/api/auth/login` 返 `{token: <jwt>, user: {id, name, email}}`;前端用 jwt-decode 解析存 useAuthStore。production 接 Keycloak 时只改 `/api/auth/login` 内部实现,UI 不变。eng-review Q10 锁定。

#### Scenario: dev 模式登录
- **WHEN** 用户输入 username="paul" + password="任意" + 点 "登录"
- **THEN** Vite proxy MUST POST `/api/auth/login` → 假 IAM 端点返 `{token: "eyJ...", user: {id: "u-paul", name: "Paul", email: "paul@chatbiz"}}`;前端存 useAuthStore

#### Scenario: 假 IAM 端点实现
- **WHEN** dev 模式启动
- **THEN** 系统 MUST 暴露 `POST /api/auth/login` 在 dev server(同一 Vite 进程);`password` 字段 MUST 接受任意非空字符串(开发期简化);token MUST 是有效 JWT 结构(可 jwt-decode 解析,含 sub + exp claims)

### Requirement: 401 自动重定向到 login
任何 fetch 返 401 时,前端 MUST 清空 useAuthStore + 跳 `/login?redirect=<原 URL>`;login 成功后跳回。eng-review Q10 锁定。

#### Scenario: 401 重定向
- **WHEN** 用户已登录 + JWT 过期 + fetch 任意 API 返 401
- **THEN** 前端 MUST 清空 useAuthStore + 弹 "会话过期,请重新登录" toast + 跳 `/login?redirect=<原 URL>`

#### Scenario: 401 后回原 URL
- **WHEN** 登录成功后
- **THEN** 浏览器 MUST 跳回 `?redirect=<原 URL>`(若存在且合法);否则跳 `/workflows`

### Requirement: Authorization Bearer header
所有 API 请求 MUST 带 `Authorization: Bearer <jwt>` header;useAuthStore.token 存在时自动加;workflow-engine 后端 MUST 同时支持 `Authorization: Bearer` (主) + `X-User-Id` header (dev fallback)。eng-review Q10 触发 workflow-engine follow-up。

#### Scenario: Bearer header 注入
- **WHEN** 前端发任意 fetch
- **THEN** 系统 MUST 加 `Authorization: Bearer <jwt>`(从 useAuthStore);若 jwt 为空,跳 login(不发请求)

#### Scenario: workflow-engine 双 header 支持
- **WHEN** workflow-engine 后端收到请求
- **THEN** 系统 MUST 优先解析 `Authorization: Bearer` 的 jwt(取 sub claim);若无 Bearer + 有 `X-User-Id` header,用 X-User-Id 作 user_id(dev mode)

### Requirement: dev fallback username
开发环境(无假 IAM 端点或 Vite proxy 失败) MUST 接受本地 username 直登;本地 username 写入 `X-User-Id` header(legacy,workflow-engine 后端兼容);不返 JWT;后续 production IAM 部署后此 fallback 关闭。

#### Scenario: dev fallback
- **WHEN** Vite proxy 失败 / `POST /api/auth/login` 返 503
- **THEN** 前端 MUST 退化为本地 username 直登,token = `dev:<username>`,所有 API 请求带 `X-User-Id: <username>` header(workflow-engine dev fallback);log warn "dev fallback auth in use"

#### Scenario: 关闭 dev fallback
- **WHEN** production build
- **THEN** 前端 MUST NOT 启用 dev fallback;若 `/api/auth/login` 返 5xx,弹 "认证服务不可用,请联系管理员"

### Requirement: 路由保护
所有 `/workflows*` / `/runs/*` / `/chatflow` / `/settings` 路由 MUST 在未登录时跳 `/login`;`/login` 路由 MUST 在已登录时跳 `/workflows`(避免死循环)。eng-review Q10 + Q3 React Router 锁定。

#### Scenario: 未登录访问
- **WHEN** user 未登录 + 访问 `/workflows/abc/edit`
- **THEN** 系统 MUST 跳 `/login?redirect=/workflows/abc/edit`;login 后回原 URL

#### Scenario: 已登录访问 login 页
- **WHEN** user 已登录 + 访问 `/login`
- **THEN** 系统 MUST 跳 `/workflows`(避免死循环)

### Requirement: 登出
"登出" 按钮(顶部栏用户头像下拉) MUST 清空 useAuthStore + 跳 `/login`;`POST /api/auth/logout` 调后端(若实现,仅 blacklist JWT)。eng-review Q10 锁定。

#### Scenario: 登出
- **WHEN** 用户点 "登出"
- **THEN** 系统 MUST POST `/api/auth/logout`(若实现)+ 清空 useAuthStore + 跳 `/login`;后续 API 请求 MUST NOT 带 Authorization

#### Scenario: 登出后回访
- **WHEN** user 登出后访问 `/workflows`
- **THEN** 系统 MUST 跳 `/login`(未登录重定向规则)

