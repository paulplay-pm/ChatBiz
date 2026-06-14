# V6a sso-real-impl — Tasks

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans
> **Goal:** V4 `sso-integration` spec V0 阶段**真实实现** — 后端 chatbiz-sso + 前端去除 dev mock + 真企微扫码联调
> **Source design doc:** `openspec/changes/sso-real-impl/{brainstorm,proposal,design}.md`
> **Base branch:** `worktree-sso-real-impl`(基于 V5 merge `fd88a79`)

## 1. V6 准备 + 后端 scaffold

- [ ] 1.1 读 `services/credential/` 完整结构,定 chatbiz-sso 复制模板
- [ ] 1.2 `cd services/sso && cp -r ../credential/{app,alembic,alembic.ini,pyproject.toml,Dockerfile,requirements*.txt,Madefile,verify.py} .` + 改 `pyproject.toml` name = "chatbiz-sso"
- [ ] 1.3 改 `services/sso/Dockerfile`:FROM python:3.12-slim + 安装 requirements + 暴露 port 8007
- [ ] 1.4 写 `services/sso/.env.example` 4 个 env:`WECHAT_CORP_ID` / `WECHAT_AGENT_ID` / `WECHAT_SECRET` / `WECHAT_REDIRECT_URI`(默认 `http://localhost:5173/portal/sso-callback`)
- [ ] 1.5 写 `services/sso/.gitignore`:`secrets/*.pem` + `__pycache__` + `.env.local`
- [ ] 1.6 写 `services/sso/secrets/.gitkeep`
- [ ] 1.7 跑 `cd services/sso && pip install -e .` 验 pyproject 可装
- [ ] 1.8 Commit: `chore(sso): V6 T1 后端 services/sso scaffold`

## 2. 后端业务代码

- [ ] 2.1 写 `services/sso/app/main.py`:create_app() factory + lifespan (DB engine + Redis + RSA 密钥 load/generate) + CORS + exception handlers + 4 routers 注册
- [ ] 2.2 写 `services/sso/app/lifespan.py`:DB engine (asyncpg) + Redis client + RSA 私钥从 `secrets/jwt_private.pem` 加载,首次启动 generate 2048-bit
- [ ] 2.3 写 `services/sso/app/services/jwt_utils.py`:encode_jwt (RS256) + decode_jwt + get_jwks (公钥导出)
- [ ] 2.4 写 `services/sso/app/services/user.py`:upsert_sso_user (by corp_external_id, 首次创建) + get_user_by_id
- [ ] 2.5 写 `services/sso/app/services/wechat.py`:exchange_code (POST 企微 /sns/oauth2/access_token) + fetch_userinfo (POST /sns/userinfo) + 4 错误边界
- [ ] 2.6 写 `services/sso/app/models/{sso_user,sso_session,sso_audit}.py`:SQLAlchemy 异步 ORM
- [ ] 2.7 写 `services/sso/app/audit.py`:write_audit_event (4 错误类映射)
- [ ] 2.8 写 `services/sso/app/routers/sso.py`:4 端点(`/initiate` / `/callback` / `/refresh` + `/jwks.json` + `/healthz`)
- [ ] 2.9 跑 `cd services/sso && python -c "from app.main import create_app; print(create_app())"` 验 import OK
- [ ] 2.10 Commit: `feat(sso): chatbiz-sso 后端 4 端点 + RS256 JWT + 4 错误边界`

## 3. 后端 alembic migration + 3 表

- [ ] 3.1 改 `services/sso/alembic/versions/001_init.py`:建 `sso_users` / `sso_sessions` / `sso_audit` 3 表
- [ ] 3.2 写 `infrastructure/postgres-init-test/001_sso.sql` 测试容器初始化 DDL
- [ ] 3.3 `cd services/sso && alembic upgrade head` 验 schema
- [ ] 3.4 跑 `psql -h chatbiz-postgres -U chatbiz -d chatbiz_test -c "\dt sso*"` 验 3 表存在
- [ ] 3.5 Commit

## 4. 后端 pytest 单元测试

- [ ] 4.1 写 `services/sso/tests/test_wechat_flow.py` 8 case:
  1. initiate 返 200 + authorize_url
  2. initiate env 缺失返 503
  3. callback code 换 access_token 成功 + upsert user + mint JWT
  4. callback state 失配返 401
  5. callback 企微 5xx 返 502
  6. refresh 续期成功
  7. refresh token 失效返 401
  8. jwks.json 暴露公钥不暴露私钥
- [ ] 4.2 `cd services/sso && pytest tests/ -v` → 8/8 PASS
- [ ] 4.3 Commit

## 5. docker compose 启动 chatbiz-sso

- [ ] 5.1 改 `infrastructure/docker-compose.yml` 加 `chatbiz-sso` 服务(image `chatbiz-sso:dev`,build `services/sso/`,depends_on postgres,port 8007 不暴露 host)
- [ ] 5.2 改 `infrastructure/docker-compose-dev.yml` 同步(V6 走 dev compose 跟 chatbiz-credential 一致)
- [ ] 5.3 跑 `docker compose -f infrastructure/docker-compose-dev.yml up -d chatbiz-sso`
- [ ] 5.4 跑 `docker exec chatbiz-sso curl -s http://localhost:8007/healthz` → 200
- [ ] 5.5 跑 `docker exec chatbiz-sso curl -s -X POST http://localhost:8007/api/v1/auth/sso/wechat/initiate` → 200 + authorize_url
- [ ] 5.6 Commit

## 6. 前端去除 dev mock

- [ ] 6.1 改 `web/portal/src/data/auth.ts`:删除 try/catch fallback,代真 fetch + 错误处理
- [ ] 6.2 改 `web/portal/src/pages/SsoMockImPage.tsx` 改名 `SsoCallbackPage.tsx`:接企微跳回 + 调真 callback
- [ ] 6.3 改 `web/portal/src/router/index.tsx`:路由名 `/sso-mock-im` → `/sso-callback`
- [ ] 6.4 改 `web/portal/src/pages/LoginPage.tsx`:SSO button 跳 `/sso-callback`(原 `/sso-mock-im`)
- [ ] 6.5 跑 `cd web/portal && pnpm exec tsc --noEmit` → EXIT 0
- [ ] 6.6 Commit: `feat(portal): 去 dev mock + SsoCallbackPage 改接真后端`

## 7. 前端 vitest + e2e

- [ ] 7.1 改 `web/portal/tests/data_auth.test.ts`:去 dev mock 7 断言(真 fetch 失败 toast + 401 toast)
- [ ] 7.2 跑 `pnpm exec vitest run` → portal 14/50 + 改 7/7 PASS
- [ ] 7.3 新建 `web/portal/e2e/portal-sso-callback.spec.ts` 2 case(真企业 IM 弹窗 + 401 toast fallback)
- [ ] 7.4 跑 `pnpm exec playwright test` → portal 7+2 = 9/9 PASS
- [ ] 7.5 Commit

## 8. nginx 配 + rebuild chatbiz-web:v6 容器

- [ ] 8.1 改 `web/nginx.conf` 加 `location /api/auth/sso/ { proxy_pass http://chatbiz-sso:8007; proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr; }`
- [ ] 8.2 跑 `cd web/portal && VITE_APP_BASE=/portal/ pnpm exec vite build` rebuild
- [ ] 8.3 跑 `cd web/canvas && VITE_APP_BASE=/canvas/ pnpm exec vite build` rebuild
- [ ] 8.4 跑 `cd web/admin && VITE_APP_BASE=/admin/ pnpm exec vite build` rebuild
- [ ] 8.5 跑 `docker build -t chatbiz-web:v6 -f web/Dockerfile web/`
- [ ] 8.6 跑 `docker rm -f chatbiz-web && docker run -d --rm --name chatbiz-web --network chatbiz-net -p 5173:80 chatbiz-web:v6`
- [ ] 8.7 跑 `curl -s -X POST http://localhost:5173/api/auth/sso/wechat/initiate` → 200(via nginx proxy)
- [ ] 8.8 跑 7-path curl 全 200
- [ ] 8.9 Commit: `chore(ops): V6 nginx 配 + chatbiz-web:v6 rebuild`

## 9. 全量回归(14-gate)

- [ ] 9.1 portal vitest 14/50 + 改 7/7 PASS
- [ ] 9.2 portal playwright 7+2 = 9/9 PASS
- [ ] 9.3 canvas main 8/8 PASS
- [ ] 9.4 canvas integration 3/3 PASS
- [ ] 9.5 canvas vitest 32/87 PASS
- [ ] 9.6 admin vitest 7/32 PASS
- [ ] 9.7 admin playwright 1/5(0 回归)
- [ ] 9.8 portal / canvas / admin tsc 全 EXIT 0
- [ ] 9.9 pytest services/sso/tests/ 8/8 PASS
- [ ] 9.10 7-path curl 全 200
- [ ] 9.11 Commit: `chore(ops): V6 sso-real-impl 14-gate verify`

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
