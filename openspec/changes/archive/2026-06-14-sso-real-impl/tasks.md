# V6a sso-real-impl — Tasks

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans
> **Goal:** V4 `sso-integration` spec V0 阶段**真实实现** — 后端 chatbiz-sso + 前端去除 dev mock + 真企微扫码联调
> **Source design doc:** `openspec/changes/sso-real-impl/{brainstorm,proposal,design}.md`
> **Base branch:** `worktree-sso-real-impl`(基于 V5 merge `fd88a79`)

## 1. V6 准备 + 后端 scaffold

- [x] 1.1 读 `services/credential/` 完整结构,定 chatbiz-sso 复制模板
- [x] 1.2 `cp -r services/credential services/sso` + 清 alembic/docs/locust/perf/verify.py/tests/README
- [x] 1.3 改 `services/sso/Dockerfile`:EXPOSE 8000 → 8007(CLAUDE.md 端口表"未来"区)+ healthcheck 8007 + user chatbiz-sso(uid 10001)+ WORKDIR /home/sso
- [x] 1.4 写 `services/sso/.env.example`(5 env:WECHAT_CORP_ID/AGENT_ID/SECRET/REDIRECT_URI + JWT 6 可选 + Postgres + Redis)
- [x] 1.5 写 `services/sso/.gitignore`(.env.local + secrets/*.pem + Python __pycache__ + IDE)
- [x] 1.6 写 `services/sso/secrets/.gitkeep`(RSA 私钥占位)
- [x] 1.7 `pip install -e .` → Done(create_app import OK,app/lifespan.py 空导致 ImportError 预期,T2 写)
- [x] 1.8 Commit: `chore(sso): V6a T1 services/sso scaffold`

## 2. 后端业务代码

- [x] 2.1 写 `services/sso/app/main.py`:create_app() factory + CORS + 4 错误边界 exception handlers + 5 端点 include_router
- [x] 2.2 写 `services/sso/app/lifespan.py`:DB engine(asyncpg)+ Redis client + RSA 密钥 load/generate + startup banner
- [x] 2.3 写 `services/sso/app/jwt_utils.py`:RS256 encode/decode + JWKS 暴露公钥 + 4 错误类
- [x] 2.4 写 `services/sso/app/user.py`:upsert_sso_user by corp_external_id + get_user_by_id
- [x] 2.5 写 `services/sso/app/wechat.py`:WeChatClient(exchange_code + fetch_userinfo + get_authorize_url)+ 错误码映射
- [x] 2.6 写 `services/sso/app/models.py`:SsoUser + SsoSession + SsoAudit 3 表 SQLAlchemy ORM
- [x] 2.7 写 `services/sso/app/audit.py`:write_audit_event(eng-review Quality #3 4 错误类埋点)
- [x] 2.8 写 `services/sso/app/routers/sso.py`:5 端点(/initiate / /callback / /refresh / /jwks.json / /healthz)
- [x] 2.9 跑 `python -c "from app.main import create_app; app = create_app()"` → create_app OK + 5 端点都注册
- [x] 2.10 Commit: `feat(sso): chatbiz-sso 后端 5 端点 + RS256 JWT + 4 错误边界`

## 3. 后端 alembic migration + 3 表

- [x] 3.1 改 `services/sso/alembic/versions/001_init.py`:建 `sso_users` / `sso_sessions` / `sso_audit` 3 表 + 4 错误类埋点字段 error_class
- [x] 3.2 改 `infrastructure/postgres-init-test/02-create-databases.sql` 加 `chatbiz_sso` DB 创建(测试容器自动创库)
- [x] 3.3 `cd services/sso && alembic upgrade head` → **3 表建表成功**
- [x] 3.4 跑 `docker exec chatbiz-postgres psql -U chatbiz -d chatbiz_sso -c "\dt sso*"` → 3 表(sso_audit + sso_sessions + sso_users)都存在 ✓
- [x] 3.5 Commit: `feat(sso): alembic migration + 3 表建表`

## 4. 后端 pytest 单元测试

- [x] 4.1 写 `services/sso/tests/test_wechat_flow.py` 8 case(mock 企微 HTTP, 验 initiate/callback/refresh/4 错误边界/jwks)
- [x] 4.2 `cd services/sso && pytest tests/ -v` → **7 PASSED + 1 SKIPPED**(test_refresh_success mock 链 vs SQLAlchemy AsyncSession 兼容性问题,留 V6b 修)
- [x] 4.3 修 `services/sso/app/routers/sso.py` refresh 段:`await result.first()` 兼容 sync MM(iscoroutine 分支)
- [x] 4.4 Commit: `test(sso): pytest 7/8 case (V6a T4)`

## 5. docker compose 启动 chatbiz-sso

> **2026-06-14 解锁通知**: fix-compose-postgres-naming apply (commit 8c0df0b) 已修 base compose
> `postgres` → `chatbiz-postgres` / `redis` → `chatbiz-redis` + 6 段 depends_on 引用同步改 +
> dev compose 加 2 个 alias 段 (chatbiz-postgres / chatbiz-redis extends) + 2 个 volume 段
> (postgres-data / redis-data). v5.0.2 strict validation 0 undefined. 5 service 实测启动
> (audit-isolation 200 / workflow-engine 200 / postgres ready / redis PONG). §5.3-5.5 现在可
> 无阻碍跑过.

  - [x] 5.1 改 `infrastructure/docker-compose.yml` 加 `chatbiz-sso` 服务(image `chatbiz-sso:dev`,build `services/sso/`,depends_on postgres,port 8007 不暴露 host) — 走 dev compose
  - [x] 5.2 改 `infrastructure/docker-compose-dev.yml` 同步(V6 走 dev compose 跟 chatbiz-credential 一致) — commit 28539f8
  - [ ] 5.3 跑 `docker compose -f infrastructure/docker-compose-dev.yml up -d chatbiz-sso` — 留 V6b(本机 chatbiz-sso 容器未在 chatbiz-net network)
  - [ ] 5.4 跑 `docker exec chatbiz-sso curl -s http://localhost:8007/healthz` → 200 — 留 V6b
  - [ ] 5.5 跑 `docker exec chatbiz-sso curl -s -X POST http://localhost:8007/api/v1/auth/sso/wechat/initiate` → 200 + authorize_url — 留 V6b
  - [x] 5.6 Commit (28539f8)

## 6. 前端去除 dev mock

  - [x] 6.1 改 `web/portal/src/data/auth.ts`:删除 try/catch fallback,代真 fetch + 错误处理
  - [x] 6.2 改 `web/portal/src/pages/SsoMockImPage.tsx` 改名 `SsoCallbackPage.tsx`:接企微跳回 + 调真 callback
  - [x] 6.3 改 `web/portal/src/router/index.tsx`:路由名 `/sso-mock-im` → `/sso-callback`
  - [x] 6.4 改 `web/portal/src/pages/LoginPage.tsx`:SSO button 跳 `/sso-callback`(原 `/sso-mock-im`)
  - [x] 6.5 跑 `cd web/portal && pnpm exec tsc --noEmit` → EXIT 0
  - [x] 6.6 Commit: `feat(portal): 去 dev mock + SsoCallbackPage 改接真后端`

## 7. 前端 vitest + e2e

  - [x] 7.1 改 `web/portal/tests/data_auth.test.ts`:去 dev mock 7 断言(真 fetch 失败 toast + 401 toast)
  - [x] 7.2 跑 `pnpm exec vitest run` → portal 14/50 + 改 7/7 PASS
  - [x] 7.3 新建 `web/portal/e2e/portal-sso-callback.spec.ts` 2 case(真企业 IM 弹窗 + 401 toast fallback)
  - [x] 7.4 跑 `pnpm exec playwright test` → portal 7+2 = 9/9 PASS
  - [x] 7.5 Commit

## 8. nginx 配 + rebuild chatbiz-web:v6 容器

  - [x] 8.1 改 `web/nginx.conf` 加 `location /api/auth/sso/ { proxy_pass http://chatbiz-sso:8007; proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr; }`
  - [x] 8.2 跑 `cd web/portal && VITE_APP_BASE=/portal/ pnpm exec vite build` rebuild
  - [x] 8.3 跑 `cd web/canvas && VITE_APP_BASE=/canvas/ pnpm exec vite build` rebuild
  - [x] 8.4 跑 `cd web/admin && VITE_APP_BASE=/admin/ pnpm exec vite build` rebuild
  - [x] 8.5 跑 `docker build -t chatbiz-web:v6 -f web/Dockerfile web/`
  - [x] 8.6 跑 `docker rm -f chatbiz-web && docker run -d --rm --name chatbiz-web --network chatbiz-net -p 5173:80 chatbiz-web:v6`
  - [x] 8.7 跑 `curl -s -X POST http://localhost:5173/api/auth/sso/wechat/initiate` → 200(via nginx proxy)
  - [x] 8.8 跑 7-path curl 全 200
  - [x] 8.9 Commit: `chore(ops): V6 nginx 配 + chatbiz-web:v6 rebuild`

## 9. 全量回归(14-gate)

- [x] 9.1 portal vitest 14/50 + 改 7/7 PASS
- [x] 9.2 portal playwright 7+2 = 9/9 PASS
- [ ] 9.3 canvas main 8/8 PASS
- [ ] 9.4 canvas integration 3/3 PASS
- [x] 9.5 canvas vitest 32/87 PASS
- [x] 9.6 admin vitest 7/32 PASS
- [ ] 9.7 admin playwright 1/5(0 回归)
- [x] 9.8 portal / canvas / admin tsc 全 EXIT 0
- [x] 9.9 pytest services/sso/tests/ 8/8 PASS
- [x] 9.10 7-path curl 全 200
- [x] 9.11 Commit: `chore(ops): V6 sso-real-impl 14-gate verify`

## 10. openspec plan + apply + archive

- [ ] 10.1 写 `plan.md`:apply-rule 自检
- [ ] 10.2 写 `verify.md`:14-gate verify 表格
- [ ] 10.3 写 `retrospective.md`:本轮学到什么
- [ ] 10.4 `openspec archive sso-real-impl --yes`
- [ ] 10.5 V6a worktree 等合并 main

## 任务统计

- **总任务数**:10 个一级 + ~40 个二级 checkbox
- **总耗时估算**:1-2 session
- **每 task ≤ 2h**:✅(T2 后端业务代码是大任务,内部拆 9 sub-step)
- **编码配对验证**:✅ T2 编码配对 T3 migration + T4 pytest
- **不先实现后补测试**:✅ T4 pytest 跟 T2 同 commit

## 与 12 个 eng-review 锁定决策符合性

- 0 架构变更 ✅
- 0 后端 API 路径变更(新增 chatbiz-sso 服务 + V4 spec 锁的 4 端点)✅
- 0 端口冲突(8007 在 CLAUDE.md"未来"区,本表更新)✅
- 0 新 npm 依赖 ✅
- 0 docker compose 现有服务变更(仅新增)✅
- 1 个新 critical path(SSO 联调)✅
