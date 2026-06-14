# V6a sso-real-impl — Proposal

> **Schema:** superpowers-bridge
> **Base branch:** `worktree-sso-real-impl`(基于 V5 merge `fd88a79`)
> **Source design:** docs/architecture.md + docs/prd.md + design doc
> **决策链:** 见 `brainstorm.md` §1(D1 single chatbiz-sso / D2 复用 chatbiz-postgres / D3 前端去除 mock / D4 联调策略 / D5 RS256 / D6 严格 0 回归)

## Why

V5 (`canvas-drag-handle-fix`) 10/10 task + 14-gate verify 全 PASS,merge 到 main `fd88a79`。V5 留 V4 `sso-integration` spec V0 阶段**未实现**:前端 dev mock(portal ssoInitiate fetch 失败 fallback 返假 jwt) + 后端 0 行 + 联调 0 行。

V6a 把 V4 spec V0 契约**真实实现**:
1. 后端 `chatbiz-sso` 服务(services/sso/)Python FastAPI + RS256 JWT + 3 表 + 真企微扫码后端
2. 前端 `web/portal` 去除 dev mock,代真 fetch 真后端
3. 真企微 sandbox corpId 联调(你提供 → 填 .env 跑通)
4. 0 回归(canvas 8/8 + portal 7/7 + integration 3/3 + admin 1/5)

**这是从"V4 dev mock 跑通" → "V6a 真实生产 SSO 联调"的关键跨越**。V6a 跑通后,V6b OIDC + V6c SAML 接续,3-tier SSO 完整。

## What Changes

### 1 个 ADDED capability

#### `sso-real-impl` (新)

真实企微扫码联调 + chatbiz-sso 后端服务 + 前端去除 dev mock。包含企微 OAuth2 code → access_token → userid → 本地 user upsert → JWT mint 完整流程 + 401/503 错误处理 + 审计埋点。

### 影响的源码

| 路径 | 类型 | 行数估 |
|------|------|------|
| `services/sso/pyproject.toml` | New | +50 (跟 credential 对齐) |
| `services/sso/Dockerfile` | New | +20 (跟 credential 对齐) |
| `services/sso/alembic/versions/001_init.py` | New | +80 (3 表 migration) |
| `services/sso/app/main.py` | New | +120 (FastAPI app + lifespan + CORS + exception handlers) |
| `services/sso/app/lifespan.py` | New | +60 (DB engine + Redis client + RSA 密钥生成/加载) |
| `services/sso/app/audit.py` | New | +50 (SSO 审计埋点) |
| `services/sso/app/models/sso_user.py` | New | +40 |
| `services/sso/app/models/sso_session.py` | New | +35 |
| `services/sso/app/models/sso_audit.py` | New | +30 |
| `services/sso/app/services/jwt_utils.py` | New | +120 (RS256 签名 + JWKS + verify) |
| `services/sso/app/services/user.py` | New | +80 (本地 user upsert from 企微 userid) |
| `services/sso/app/services/wechat.py` | New | +150 (企微 OAuth2 code → access_token + userid) |
| `services/sso/app/routers/sso.py` | New | +120 (`/api/v1/auth/sso/wechat/{initiate,callback}` + `/api/v1/auth/sso/jwks.json` + `/healthz`) |
| `services/sso/tests/test_wechat_flow.py` | New | +200 (pytest mock 企微 HTTP, 8 case) |
| `services/sso/secrets/.gitkeep` | New | +5 |
| `services/sso/.env.example` | New | +20 (WECHAT_CORP_ID 等 4 个变量) |
| `services/sso/secrets/jwt_private.pem` | New | +30 (RSA 2048 私钥,gitignore) |
| `infrastructure/docker-compose.yml` | Modify | +15 (chatbiz-sso 服务) |
| `infrastructure/postgres-init-test/001_sso.sql` | New | +20 (3 表 DDL) |
| `web/nginx.conf` | Modify | +8 (`/api/auth/sso/*` 反向代理 chatbiz-sso:8007) |
| `web/portal/src/data/auth.ts` | Modify | -10 + 30 (去 dev mock + 真 fetch + 错误处理) |
| `web/portal/src/pages/SsoMockImPage.tsx` | Rename → `SsoCallbackPage.tsx` | ~100 (callback 处理 + 真 fetch) |
| `web/portal/src/router/index.tsx` | Modify | +3 (改路由名) |
| `web/portal/tests/data_auth.test.ts` | Modify | -20 + 30 (改写 7 断言) |
| `web/portal/e2e/portal-sso-callback.spec.ts` | New | +60 (2 case: 真企业 IM 弹窗 + 401 fallback) |
| `CLAUDE.md` | Modify | +3 (端口表更新 8007) |

**总估**: ~25 文件改/新建,后端 ~1000 行,前端 ~200 行,配置 ~50 行。

### 影响的 spec 增量

- **新增 1 spec 目录**:`openspec/specs/sso-real-impl/spec.md`(5-7 Requirement + 5-7 Scenario)
- 1 个 modify:`openspec/specs/canvas-auth/spec.md`(V4 已 Modify,V6a 追加真实 corpId 字段 / RS256 验证路径 / 401 跳 login 流程)

## Impact

### 影响的 spec 增量

- **新增 1 spec 目录**:`openspec/specs/sso-real-impl/spec.md`

### 影响的源码

后端 + 前端 + 配置,具体见上表。

## Non-Goals(V6a 显式不做)

- V1 OIDC 联调(留 V6b)
- V2 SAML 联调(留 V6c)
- Keycloak 容器化(留 V6b)
- 真企微 corpId 强制联调(若你没提供 corpId,V6a 走 mock 企微 server)
- Admin 4 fail e2e 修复
- 任何 frontend 既有 e2e 改动
- 任何 portal/canvas/admin 既有所见 UI 改动
- docs/architecture.md 改动
- 0 后端端口变更(8007 在 CLAUDE.md"未来"区,本表更新)

## 与 12 个 eng-review 锁定决策符合性

| Finding | 影响 |
|---|---|
| Arch #1 数据隔离网关 | 0 冲突(chatbiz-sso 走 audit-and-isolation egress 强制点) |
| Arch #4 Workflow/Chatflow | 0 冲突 |
| Arch #5 MVP MCP | 0 冲突 |
| Arch #6 人工审批 | 0 冲突 |
| Quality #1 Node Contract codegen | 0 冲突 |
| Quality #3 4 错误边界 | 0 冲突(JWT 错误走 4 边界) |
| Test #1-#2 3 层测试 + critical path | **正向贡献**(SSO 联调 1 个新 critical path) |
| Perf #1-#2 | 0 冲突 |

**0 架构变更** ✅
**0 前端 npm 新依赖** ✅
**0 docker compose 端口冲突** ✅(8007 落在"未来"区)
**0 docs/architecture.md 改动** ✅

## 风险与依赖

### 依赖前置

- V4 spec `sso-integration` 已落地(`openspec/specs/sso-integration/spec.md`)
- V4 spec `canvas-auth` Modify 已落地(回跳 + refresh 路径已锁)
- chatbiz-credential 服务作为模板可用
- chatbiz-postgres 容器已在跑(V1/V2/V3/V4 复用)

### 风险

- **R1**: 真企微 corpId 申请 / 联调时间窗(中等)→ 缓解:`chatbiz-sso-mock` 模拟企微 OAuth2 流程,真 corpId 后填 .env
- **R2**: 企微 OAuth2 强制 https(高)→ 缓解:dev mode 走 mock server HTTP;prod 部署走 HTTPS
- **R3**: JWT 私钥持久化(低)→ 缓解:gitignore + 首次启动 generate
- **R4**: 端口 8007 nginx 反向代理冲突(低)→ 缓解:T7 跑全 curl

## 决策点(已 locked)

| ID | 决策 | 选择 |
|----|------|------|
| D1 | 后端架构 | **单服务 `chatbiz-sso` (port 8007)** |
| D2 | 数据库 | **复用 chatbiz-postgres,新增 3 表** |
| D3 | 前端去除 dev mock | **真 fetch + 错误处理 toast,不再静默 mock** |
| D4 | 企微联调策略 | **后端真 + 真 corpId 走真企微;env 缺失返 503 toast** |
| D5 | JWT 签名 | **RS256 RSA 非对称(对齐 OIDC / SAML)** |
| D6 | 0 前端 e2e 回归 | **严格 0 改既有 7 portal e2e;V6a 仅新增 1 sso callback e2e** |
