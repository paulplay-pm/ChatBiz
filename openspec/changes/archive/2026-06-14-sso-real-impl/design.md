# V6a sso-real-impl — Design

> **Schema:** superpowers-bridge
> **依赖:** `brainstorm.md` §1 决策链 + `proposal.md` 1 capability
> **Source of truth:** docs/architecture.md + docs/prd.md + design doc

## Context

V5 (`canvas-drag-handle-fix`) 10/10 task + 14-gate verify 全 PASS,merge 到 main `fd88a79`。V5 留 V4 `sso-integration` spec V0 阶段未实现:
- 前端 dev mock(portal ssoInitiate fetch 失败 fallback 返假 jwt)
- 后端 0 行
- 联调 0 行

V6a 把 V4 spec V0 契约**真实实现**:后端 `chatbiz-sso` 服务 + 前端去除 dev mock + 真实企微扫码联调。

## Goals

- **G1** 后端 `chatbiz-sso` 服务跑通 `/api/v1/auth/sso/wechat/{initiate,callback}` + JWKS + `/healthz`
- **G2** RS256 JWT 签名 + 私钥持久化 + JWKS 暴露
- **G3** 前端 portal 去 dev mock,代真 fetch + 401/503 错误处理 toast
- **G4** 真企微 sandbox corpId 联调成功(若你提供),无 corpId 时走 mock 企微 server
- **G5** 0 回归(canvas 8/8 + portal 7/7 + integration 3/3 + admin 1/5)
- **G6** archive + 14-gate verify 全 PASS

## Non-Goals

- V1 OIDC 联调(留 V6b)
- V2 SAML 联调(留 V6c)
- Keycloak 容器化(留 V6b)
- Admin 4 fail e2e 修复
- 任何 frontend 既有 e2e 改动
- 任何 portal/canvas/admin 既有所见 UI 改动
- docs/architecture.md 改动

## Decisions

### D1: 后端 `chatbiz-sso` (port 8007) Python FastAPI 服务

- 模板:copy `services/credential/` 结构
- 依赖:SQLAlchemy[asyncio] + asyncpg + python-jose[cryptography] + redis + alembic
- lifespan:DB engine + Redis client + RSA 私钥加载/生成
- 路由:`/api/v1/auth/sso/wechat/{initiate,callback}` + `/api/v1/auth/sso/jwks.json` + `/api/v1/auth/sso/refresh` + `/healthz`

### D2: 数据库 3 表(复用 chatbiz-postgres)

- `sso_users`(id PK, corp_external_id UNIQUE, wechat_userid, email, name, role, created_at, last_login_at)
- `sso_sessions`(id PK, user_id FK, jwt_jti UNIQUE, refresh_token_hash, issued_at, expires_at, revoked_at)
- `sso_audit`(id PK, user_id FK NULL, event_type, ip, user_agent, request_id, created_at)
- Alembic migration 一次性建表
- 审计埋点(eng-review 12 Quality #3):4 错误边界 `SecurityError` / `UserError` / `WorkflowRuntimeError` / 7-class `audit-and-isolation/errors.py`

### D3: JWT RS256 RSA 2048

- 私钥 2048-bit RSA,首次启动 generate + 持久化到 `services/sso/secrets/jwt_private.pem`(gitignore)
- 公钥通过 `/.well-known/jwks.json` 暴露(给 V1 OIDC 客户端用)
- JWT claim:`sub` (sso_users.id) + `name` + `email` + `groups` (RBAC roles) + `iat` + `exp` + `iss` (`https://sso.chatbiz.local`) + `aud` (`chatbiz-web`)
- refresh token:7 天,access token:1 小时
- `services/sso/secrets/.gitkeep` 占位 + `services/sso/.gitignore` 排除 secrets/

### D4: 企微 OAuth2 联调流程

```
[portal LoginPage] 
  ↓ click SSO button
[fetch GET /api/v1/auth/sso/wechat/initiate]
  ↓
[chatbiz-sso 后端]
  - generate state (CSRF, 存 Redis TTL 5min)
  - 返 {authorize_url: 'https://open.weixin.qq.com/connect/oauth2/authorize?appid=...&redirect_uri=http://localhost:5173/portal/sso-callback&state=...'}
  ↓
[portal SsoCallbackPage 跳 authorize_url]
  ↓ 企微登录页
[企微跳回 redirect_uri?code=...&state=...]
  ↓
[SsoCallbackPage]
  - verify state in Redis
  - fetch POST /api/v1/auth/sso/wechat/callback {code, state}
  ↓
[chatbiz-sso 后端]
  - 拿 code 换 access_token (POST https://api.weixin.qq.com/sns/oauth2/access_token)
  - 拿 access_token + openid 拉 userinfo (https://api.weixin.qq.com/sns/userinfo)
  - upsert sso_users (corp_external_id = 企微 userid)
  - mint JWT (RS256) + refresh token (7d)
  - 写 sso_audit
  - 返 {jwt, refresh, expires_in, user}
  ↓
[SsoCallbackPage]
  - localStorage.setItem('chatbiz.auth', JSON.stringify({...auth, via: 'sso-wechat-scan'}))
  - navigate('/portal/')
```

### D5: 前端去除 dev mock

- `web/portal/src/data/auth.ts`:删除 try/catch fallback 到 mock JWT,改为:
  ```ts
  const r = await fetch('/api/auth/sso/wechat/initiate', { method: 'POST' });
  if (!r.ok) throw new Error(`sso_initiate_${r.status}`);
  return r.json();
  ```
- `web/portal/src/pages/SsoMockImPage.tsx` 改名 `SsoCallbackPage.tsx`(语义更准确,接企微跳回)
- `web/portal/src/router/index.tsx`:改路由名 `/sso-mock-im` → `/sso-callback`
- 错误处理:401 / 503 → toast "企业登录服务暂不可用,请联系管理员"

### D6: nginx + compose 配

- `web/nginx.conf` 加 `location /api/auth/sso/ { proxy_pass http://chatbiz-sso:8007; }`
- `infrastructure/docker-compose.yml` 加 `chatbiz-sso` 服务(port 8007 在 chatbiz-net)
- `chatbiz-sso` 走 `audit-and-isolation` 网关 egress 强制点(eng-review Arch #1)
- rebuild `chatbiz-web:v6` 容器

## Architecture

### 模块流

```
[portal LoginPage] --[click SSO]--> [SsoCallbackPage navigate]
                                          |
                                          v
              [GET /api/auth/sso/wechat/initiate]   --> [chatbiz-sso:8007]
                                          |               |
                                          |   <-- {authorize_url, state} ---
                                          v
                              [window.location.assign(authorize_url)]
                                          |
                                          v
              [WeChat OAuth2 page] --[code + state]--> [redirect_uri]
                                          |
                                          v
                              [SsoCallbackPage?code=...&state=...]
                                          |
                                          v
              [POST /api/auth/sso/wechat/callback {code, state}]
                                          |
                                          v
              [chatbiz-sso] --[code exchange]--> [WeChat /sns/oauth2/access_token]
                                          |
                                          v
              [chatbiz-sso] --[userinfo]--> [WeChat /sns/userinfo]
                                          |
                                          v
              [upsert sso_users + mint JWT + write sso_audit]
                                          |
                                          v
              <-- {jwt, refresh, user} ---
                                          |
                                          v
              [SsoCallbackPage: localStorage.setItem + navigate('/portal/')]
```

### 数据流

| 表 | 关键字段 | 写入时机 |
|---|---|---|
| `sso_users` | `wechat_userid` UNIQUE + `name` + `email` + `role` | 首次扫码登录(upsert by wechat_userid) |
| `sso_sessions` | `jwt_jti` UNIQUE + `user_id` + `refresh_token_hash` + `expires_at` | 每次 mint JWT 写 1 行 |
| `sso_audit` | `user_id` + `event_type` + `ip` + `user_agent` + `request_id` | 每次 SSO 端点调用 |

### 错误处理

- `sso_initiate_503`:`env` 缺失 / 联调失败 → 前端 toast
- `sso_callback_401`:`code` 无效 / `state` 失配 → 前端 toast
- `sso_callback_500`:后端内部错 → 写 `sso_audit.event_type='error'` + 前端 toast
- `jwt_401`:access token 过期 → 前端 `POST /refresh` → 续期

## Risks

- **R1**: 真企微 corpId 申请 / 联调时间窗(中等)→ 缓解:`chatbiz-sso-mock` 模拟企微 OAuth2 流程,真 corpId 后填 .env
- **R2**: 企微 OAuth2 强制 https(高)→ 缓解:dev mode 走 mock server HTTP;prod 部署走 HTTPS
- **R3**: JWT 私钥持久化(低)→ 缓解:gitignore + 首次启动 generate
- **R4**: 端口 8007 nginx 反向代理冲突(低)→ 缓解:T7 跑全 curl
- **R5**: pytest mock 企微 HTTP 调用(低)→ 跟 chatbiz-credential 测试模板对齐

## Migration

- 无数据迁移(新表,空)
- 无 UI 迁移
- CLAUDE.md 端口表更新 8007

## Open Questions (V6 期间可能 surface)

- **Q1**: 真企微 corpId 何时提供?(V6a 跑完前 OR V6a 跑完后填 .env 部署)
- **Q2**: V6b OIDC + V6c SAML 后续规划?
- **Q3**: chatbiz-sso 服务名 / 端口 8007 是否 OK?

## 10 task 速览(详见 tasks.md)

```
T1  V6 准备 + 后端 services/sso/ scaffold
T2  后端 chatbiz-sso 业务代码(routers + services + models + jwt_utils + wechat)
T3  后端 alembic migration + 3 表建表
T4  后端 pytest 单元测试(mock 企微 HTTP)
T5  docker compose 启动 chatbiz-sso + /healthz 验证
T6  前端去除 dev mock(auth.ts + SsoCallbackPage + router)
T7  前端 vitest + e2e(data_auth 改写 + portal-sso-callback 新增)
T8  nginx 配 + rebuild chatbiz-web:v6 容器
T9  全量回归 14-gate
T10 openspec plan + apply + verify + archive
```
