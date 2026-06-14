# sso-real-impl Specification

## Purpose
TBD - created by archiving change sso-real-impl. Update Purpose after archive.
## Requirements
### Requirement: 后端 `chatbiz-sso` 服务 (port 8007)

`services/sso/` MUST 是 Python FastAPI 服务,提供 4 端点:
- `POST /api/v1/auth/sso/wechat/initiate` — 返 `{authorize_url, state}`(含企微 OAuth2 authorize URL + CSRF state)
- `POST /api/v1/auth/sso/wechat/callback` — 接 `{code, state}`,内部用 code 换 access_token,再拉 userinfo,**upsert sso_users** 后 mint RS256 JWT
- `POST /api/v1/auth/sso/refresh` — 接 refresh token,续期 JWT(access 1h / refresh 7d)
- `GET /api/v1/auth/sso/jwks.json` — 暴露 RSA 公钥 JWKS(给 V1 OIDC 客户端用)
- `GET /healthz` — 200 iff DB 可达

#### Scenario: initiate 返企微 authorize URL

- **WHEN** 调 `POST /api/v1/auth/sso/wechat/initiate`
- **THEN** 返 `200 OK` + JSON `{authorize_url, state}`,`authorize_url` MUST 是 `https://open.weixin.qq.com/connect/oauth2/authorize?appid=<corpId>&redirect_uri=<configured>&response_type=code&scope=snsapi_login&state=<state>`
- **THEN** 后端 MUST 写 `sso_audit.event_type='initiate'` + `state` 存 Redis TTL 5min 防 CSRF

#### Scenario: callback 完整流程

- **WHEN** 企微跳回 `redirect_uri?code=...&state=...`,前端 POST `/api/v1/auth/sso/wechat/callback` body `{code, state}`
- **THEN** 后端 MUST 验证 `state` 在 Redis 内且未过期
- **THEN** 后端 MUST POST `https://api.weixin.qq.com/sns/oauth2/access_token?appid=...&secret=...&code=...&grant_type=authorization_code` 拿 access_token + openid
- **THEN** 后端 MUST POST `https://api.weixin.qq.com/sns/userinfo?access_token=<token>&openid=<openid>` 拉 userinfo(name + email)
- **THEN** 后端 MUST upsert `sso_users` (by wechat_userid, 首次创建)
- **THEN** 后端 MUST mint RS256 JWT(claim 含 sub + name + email + groups + iat + exp + iss + aud)
- **THEN** 后端 MUST 写 `sso_audit.event_type='login_success'`
- **THEN** 后端 MUST 返 `200 OK` + JSON `{jwt, refresh, expires_in, user}`

#### Scenario: corpId env 缺失返 503

- **WHEN** `WECHAT_CORP_ID` / `WECHAT_AGENT_ID` / `WECHAT_SECRET` env 任一缺失
- **THEN** `POST /api/v1/auth/sso/wechat/initiate` MUST 返 `503 Service Unavailable` + `{"error":{"code":"sso.wechat_unavailable","message":"企微服务未配置"}}`
- **THEN** 前端 MUST toast "企业登录服务暂不可用,请联系管理员"
- **THEN** 不再 fallback 静默 mock(对比 V4 dev mock 行为)

### Requirement: RS256 JWT 签名

JWT MUST 用 RS256 RSA 签名,2048-bit 私钥,首次启动自动 generate + 持久化到 `services/sso/secrets/jwt_private.pem`(gitignore 排除)。JWKS 暴露公钥。

#### Scenario: JWT claim 结构

- **WHEN** mint JWT
- **THEN** header MUST `{alg: 'RS256', typ: 'JWT'}`
- **THEN** payload MUST 含:
  - `sub`: sso_users.id
  - `name`: 中文姓名
  - `email`: 邮箱
  - `groups`: array of role strings
  - `iat`: issue time (Unix epoch)
  - `exp`: expiry time (access 1h, refresh 7d)
  - `iss`: `'https://sso.chatbiz.local'`
  - `aud`: `'chatbiz-web'`

#### Scenario: JWKS 端点

- **WHEN** 调 `GET /api/v1/auth/sso/jwks.json`
- **THEN** 返 `200 OK` + JSON Web Key Set 包含公钥
- **THEN** 公钥 MUST 是 RS256 模数,base64url-encoded
- **THEN** 私钥 MUST NOT 出现在 JWKS

### Requirement: 4 错误边界

`chatbiz-sso` MUST 走 eng-review Quality #3 的 4 错误边界:
- `SecurityError` → 401 / 403
- `UserError` → 400
- `WorkflowRuntimeError` → 502 / 504
- `audit-and-isolation/errors.py` 7 类 → 500

#### Scenario: 4 错误类映射

- **WHEN** 后端抛错
- **THEN** HTTP status + error code MUST 如下:
  - `SecurityError` → 401 + `security.unauthorized` / 403 + `security.forbidden`
  - `UserError` → 400 + `user.invalid_input` / `user.missing_param`
  - `WorkflowRuntimeError` → 502 + `runtime.wechat_5xx` / 504 + `runtime.wechat_timeout`
  - 7-class `audit-and-isolation/errors.py` → 500 + `internal.<具体子类>`
- **THEN** 前端 MUST 根据 error_code 类别显示对应 toast + 建议操作

### Requirement: 前端去除 dev mock

`web/portal/src/data/auth.ts` MUST 删除 `try/catch fallback 返 mock JWT` 行为,改为:
- `ssoInitiate` 真 fetch `/api/auth/sso/wechat/initiate`
- `ssoCallback` 真 fetch `/api/auth/sso/wechat/callback`
- 失败 MUST 抛错 + 前端 toast 错误

#### Scenario: 真 fetch 成功

- **WHEN** `ssoInitiate()` 调真后端
- **THEN** 返 `{authorize_url, state}`,`window.location.assign(authorize_url)`

#### Scenario: 真 fetch 失败(503)

- **WHEN** `ssoInitiate()` 真后端返 503 + `sso.wechat_unavailable`
- **THEN** 前端 MUST toast "企业登录服务暂不可用,请联系管理员"
- **THEN** **不再 fallback 到 mock JWT**

### Requirement: nginx 配 `/api/auth/sso/*` 反向代理

`web/nginx.conf` MUST 加 `location /api/auth/sso/ { proxy_pass http://chatbiz-sso:8007; proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr; }`,portal 走 nginx 5173 → chatbiz-sso 8007(同 chatbiz-net)。

#### Scenario: 代理路径生效

- **WHEN** 浏览器调 `http://localhost:5173/api/auth/sso/wechat/initiate`
- **THEN** nginx MUST proxy 到 `chatbiz-sso:8007` 同路径
- **THEN** 后端响应 MUST 透传(不缓存,带 CORS 头)
- **THEN** X-Real-IP MUST 是客户端真实 IP(用于 sso_audit)

### Requirement: 5 新增 e2e + 3 pytest 不回归

V6a MUST 不改 V5 既有 canvas 8/8 e2e + portal 7/7 e2e + integration 3/3 + admin 1/5 e2e。新增:
- `web/portal/e2e/portal-sso-callback.spec.ts` 2 case(真企业 IM 弹窗 + 401 toast fallback)
- `services/sso/tests/test_wechat_flow.py` 8 case(mock 企微 HTTP, 验 initiate/callback/refresh/4 错误边界)
- `web/portal/tests/data_auth.test.ts` 改写 7 断言(去 dev mock + 错误处理)

#### Scenario: e2e 全部不回归

- **WHEN** 跑 `pnpm exec playwright test` 在 canvas → **8/8 PASS**
- **WHEN** 跑 `pnpm exec playwright test` 在 portal → **7/7 + 2 new = 9/9 PASS**
- **WHEN** 跑 `pnpm exec playwright test --config=playwright.integration.config.ts` → **3/3 PASS**
- **WHEN** 跑 `pnpm exec playwright test` 在 admin → **1/5 PASS**(V5 baseline, 0 回归)
- **WHEN** 跑 `pnpm exec vitest run` 全套 → 14-gate verify
- **WHEN** 跑 `pytest services/sso/tests/` → **8/8 PASS**

