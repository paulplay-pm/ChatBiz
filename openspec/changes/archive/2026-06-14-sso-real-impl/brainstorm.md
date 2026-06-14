# V6a sso-real-impl — Brainstorm

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:brainstorming
> **Schema:** superpowers-bridge (中文 + 严格测试/审计/标签规则)
> **Base branch:** `worktree-sso-real-impl`(基于 V5 merge `fd88a79`)
> **Source design 引用:** `docs/architecture.md` + `docs/prd.md` + `~/.gstack/projects/paulplay-pm-ChatBiz/paulwang-main-design-20260609-230548.md` + `openspec/specs/sso-integration/`(V4 落地)

## 0. 背景

V5 (`canvas-drag-handle-fix`) 10/10 task + 14-gate verify 全 PASS,merge 到 main `fd88a79`。V5 留下 V4 sso-integration spec V0 阶段:**真实企微扫码联调 + 后端 IAM 服务 + 前端去除 dev mock**。

V6a 是 V4 spec V0 阶段的**真实实现**。V4 锁定的契约:`/api/auth/sso/wechat/{initiate,callback}` 端点 + JWT mint + refresh + 本地 user 映射。

V6a 范围(已 locked):
- **后端**:`services/sso/` Python FastAPI 服务,port 8007,SQLAlchemy + asyncpg + 审计埋点 + RS256 JWT
- **前端**:`web/portal/src/data/auth.ts` 去除 dev mock,代真 fetch + popup + callback
- **联调**:用户提供真实企微 sandbox corpId + agentId + secret(env 配);V6a 失败 fallback 是 401 + 友好提示(不静默 mock)
- **JWT**:RS256 RSA 非对称(对齐 OIDC v1 / SAML v2)
- **用户 schema**:扩展现有 `web/admin/src/data/users.ts` mock + 真实 PostgreSQL `sso_users` 表

## 1. 决策链(locked-in)

### D1: 后端单服务 `chatbiz-sso` (port 8007)

- **理由**:3-tier SSO(V0 企微 + V1 OIDC + V2 SAML)走同 1 服务,共享 JWT 签名 + JWKS + 审计埋点
- 模板:copy `services/credential/` 结构(`app/main.py + app/routers/ + app/models.py + app/services.py + app/lifespan.py + app/audit.py + pyproject.toml + Dockerfile + alembic/`)
- **跟 credential / workflow-engine 共享**:`requirements.txt` 走 SQLAlchemy[asyncio] + asyncpg + python-jose(cryptography 替换 PyJWT,RS256 强)
- 端口 8007:**CLAUDE.md 端口表"已分配"行**未列,落在 8006+(可用)

### D2: 数据库 — 复用 `chatbiz-postgres`,新增 3 表

- `sso_users`(id, corp_external_id, wechat_userid, email, name, role, created_at, last_login_at)
- `sso_sessions`(id, user_id, jwt_jti, refresh_token_hash, issued_at, expires_at, revoked_at)
- `sso_audit`(id, user_id, event_type, ip, user_agent, created_at, request_id)
- Alembic migration 一次性建表
- 复用 V4 已有 `chatbiz-postgres` 容器

### D3: 前端去除 dev mock,代真 fetch

- `web/portal/src/data/auth.ts`:删除 try/catch fallback 到 mock JWT,改为真 fetch + 错误处理(401 / 502 / network error → 弹 toast)
- `web/portal/src/pages/SsoMockImPage.tsx`:保留(企业 IM 弹窗 UI 概念不变),改名 `SsoCallbackPage.tsx` 更准确
- `web/portal/src/pages/LoginPage.tsx`:SSO button 行为不变(同窗口跳),callback page 真实接收 code + state,调 `/api/auth/sso/wechat/callback` 拿 JWT
- V4 dev IAM `vite-plugin-dev-iam.ts` canvas 端保留(V4 canvas 登录 dev mode 仍用)

### D4: WeChat sandbox corpId 联调

- `.env.local`(不入库)装 `WECHAT_CORP_ID` / `WECHAT_AGENT_ID` / `WECHAT_SECRET` / `WECHAT_REDIRECT_URI`(默认 `http://localhost:5173/portal/sso-callback`)
- 真企微 OAuth2 流程:`/api/auth/sso/wechat/initiate` → 返 `{authorize_url, state}` → 浏览器跳 `https://open.weixin.qq.com/connect/oauth2/authorize?appid=...&redirect_uri=...&response_type=code&scope=snsapi_login&state=...` → 企微跳回 `redirect_uri?code=...&state=...` → 前端 callback page 调 `/api/auth/sso/wechat/callback?code=...&state=...` → 后端用 corpsecret 换 access_token + userid → mint JWT
- **失败 fallback**:env 缺失 / 联调失败时,后端返 503 + 错误码 `sso.wechat_unavailable`,前端 toast "企微服务暂不可用,请联系管理员"(**不再 mock 静默成功**)
- 单元测试 / e2e:用 pytest mock 企微 HTTP 调用,V6a 走 chatbiz-credential 测试模板,跑 `pytest` 全 PASS

### D5: JWT 签名 RS256

- 后端用 `python-jose[cryptography]`(支持 RS256)
- 私钥 2048-bit RSA,首次启动 generate + 持久化到 `services/sso/secrets/jwt_private.pem`(gitignore)
- 公钥通过 `/.well-known/jwks.json` 暴露(给 V1 OIDC 客户端用)
- JWT claim:`sub` (sso_users.id) + `name` + `email` + `groups` (RBAC roles) + `iat` + `exp` + `iss` (`https://sso.chatbiz.local`) + `aud` (`chatbiz-web`)
- refresh token:7 天;access token:1 小时
- 复用 V4 `canvas-auth spec` Modify 部分(回跳 + refresh + 401 跳 login)

### D6: 范围严格 — 0 改前端 e2e test(只新增)

- canvas e2e 8/8 + integration 3/3 + portal e2e 7/7 **0 回归**(V5 baseline)
- V6a 新增 e2e:`portal-sso-callback.spec.ts`(1 case 真企业 IM 弹窗流程 + 1 case 401 fallback toast)
- V6a 新增 vitest:`data_auth.test.ts` 改写 7 断言(fetch 失败 toast + 401 toast)
- V6a 新增 pytest:`test_wechat_flow.py` mock 企微 HTTP,验 code → access_token → user → JWT

## 2. 根因分析

| 假设 | 概率 | 失败原因 |
|---|---|---|
| H1: 真企微 corpId 申请限制 | 中 | 个人开发者 corpId 申请需 1-3 天;V6a 等不起 |
| H2: 企微 redirect_uri 需 HTTPS | 高 | 企微 OAuth2 强制 `redirect_uri` 用 https;dev mode localhost 不通过 |
| H3: SAML 证书 + IdP metadata XML 配置 | 中 | V2 留 V6c |
| H4: Keycloak 容器化 + realm 配置 | 中 | V1 留 V6b |

**H2 真实企微 OAuth2 强制 https 是 V6a 真实障碍**。dev 模式解决:
- 选项 A:用 `https://xxx.ngrok.io` tunnel localhost
- 选项 B:跳过企微真联调,改用 `chatbiz-sso-mock` 本地 Python fastapi 服务模拟企微 OAuth2 流程(同 V4 dev mock 模式但服务端化)
- 选项 C:企微 corpId 有 dev 环境白名单

**推荐选项 B**(`chatbiz-sso-mock`):跟 V4 dev mock 模式对齐,生产 corpId 直接替换 mock server URL。但 user 锁定"提供真实企微 sandbox corpId + secret",**真实 corpId 走选项 A**(ngrok 临时 + 你配 corpId 白名单 localhost)。

## 3. 备选方案(rejected)

### Option A — V6a 跑真企微 + 真实 corpId 联调
- user sandbox corpId + ngrok HTTPS + 强制 https
- 复杂度高、跨域网络、需要你提供 corpId + 测试时间窗

### Option B — V6a 后端 + 真 corpId 走真企微(失败 fallback 到 mock 弹窗)
- V6a 后端真 + 真 corpId 走真企微;若 env 缺失 + 联调失败,后端返 503 + 前端 toast 提示
- user 沙箱 corpId 可省略(测试时填)
- **推荐**

### Option C — V6a 跳过真联调,只 spec + 后端 + 前端去除 mock(e2e 走 mock 企微 server)
- 最简单,无企微联调,留 V7 真实联调
- **若 user 不提供 corpId 是这个**

### Option D — V6a 拆两阶段:6a.1 后端 + spec,6a.2 联调
- 太长,跨多 session

## 4. 10 task outline(跟 V3/V4/V5 一致节奏)

```
T1  V6 准备 + 后端 services/sso/ scaffold
    (services/sso/{app/main.py + app/lifespan.py + pyproject.toml + Dockerfile + alembic/}
     + 配 chatbiz-test network + 端口 8007)
T2  后端 chatbiz-sso 业务代码
    (app/routers/sso.py + app/services/{wechat.py, jwt_utils.py, jwks.py, user.py}
     + app/models/{sso_user.py, sso_session.py, sso_audit.py}
     + alembic migration 建 3 表)
T3  后端 pytest 单元测试
    (test_wechat_flow.py mock 企微 HTTP,V6a 走 credential 测试模板)
T4  docker compose 启动 chatbiz-sso + 验证 200
    (docker compose up -d chatbiz-sso + curl /healthz + curl /api/v1/auth/sso/wechat/initiate)
T5  前端去除 dev mock
    (web/portal/src/data/auth.ts 改 fetch 真后端
     + web/portal/src/pages/SsoMockImPage.tsx 改名 callback page
     + web/portal/src/router/index.tsx 改路由)
T6  前端 e2e + vitest
    (portal-sso-callback.spec.ts 新增 2 case
     + data_auth.test.ts 改写 7 断言)
T7  nginx 配 /api/auth/sso/* 反向代理
    (web/nginx.conf 加 location /api/auth/sso/ proxy_pass http://chatbiz-sso:8007)
    + rebuild chatbiz-web 容器
T8  全量回归(14-gate)
    (canvas 8/8 + portal 7+/7+ + integration 3/3 + admin 1/5 不回归
     + 新增 sso callback e2e)
T9  openspec plan + apply
T10 archive V6a
```

## 5. 关键约束

- 0 前端 npm 新依赖(只改现有 fetch + react-router)
- 0 docker compose 端口变更(8007 落在 CLAUDE.md 端口表"未来"区)
- 0 eng-review 12 finding 冲突
- 后端 ~5-10 个 Python 文件 ~500 行
- 前端 ~3-4 个文件改 ~150 行

## 6. 与 12 个 eng-review 锁定决策符合性

- Arch #1 数据隔离网关:0 冲突(V6a 不动 audit-and-isolation)
- Arch #4 Workflow/Chatflow 共享 StateGraph:0 冲突
- Arch #5 MVP MCP:0 冲突
- Arch #6 人工审批:0 冲突
- Quality #1 Node Contract codegen:0 冲突
- Quality #3 4 错误边界:0 冲突(V6a JWT 错误走 4 边界)
- Test #1-#2 3 层测试 + critical path:正向贡献(SSO 联调 1 个新 critical path)
- Perf #1-#2:0 冲突

## 7. 风险与决策点

### R1: 真实企微 corpId 申请 / 联调时间窗
- **决策**:V6a 后端完整 + 前端去除 mock,联调走 `chatbiz-sso-mock` 本地服务(模拟企微 OAuth2 流程);真 corpId 由你后续提供
- 缓解:V6a 范围**不强制**真企微联调;e2e 用 mock 企微 server 跑;真 corpId 部署时填 .env

### R2: 企微 OAuth2 强制 https
- **决策**:dev mode 走 `chatbiz-sso-mock` HTTP;prod 部署走真企微 HTTPS
- 缓解:e2e 用 mock 绕过 https 要求

### R3: JWT 私钥持久化
- **决策**:`services/sso/secrets/jwt_private.pem` 文件持久化 + `.gitignore` 排除;首次启动若不存在则 generate
- 缓解:`.gitignore` + `secrets/.gitkeep`

### R4: 端口 8007 nginx 反向代理冲突
- **决策**:`web/nginx.conf` 加 `location /api/auth/sso/ { proxy_pass http://chatbiz-sso:8007; }`;portal 走 nginx 5173 → chatbiz-sso 8007(同 network)
- 缓解:T7 跑全 curl 验证

## 8. 待 V6 期间用户裁决的潜在 Q

- Q1: 真企微 corpId 何时提供?(V6a 跑完前 OR V6a 跑完后填 .env 部署)
- Q2: chatbiz-sso 服务名 / 端口 8007 是否 OK?(CLAUDE.md 端口表"未来"区,本表需更新)
- Q3: V6b OIDC + V6c SAML 后续规划?

## 9. 关联引用

- [[sso-integration]] V4 spec
- [[canvas-auth]] V4 spec Modify
- [[chatbiz-credential]] Python service 模板
- [[eng-review-12-finding]] locked 决策
- docs/architecture.md §4.3.5 企业安全
- docs/prd.md line 861 (SY-019 SSO P1)
- ~/.gstack/projects/paulplay-pm-ChatBiz/paulwang-main-design-20260609-230548.md line 212/335
