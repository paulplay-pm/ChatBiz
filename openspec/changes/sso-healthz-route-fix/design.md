# sso-healthz-route-fix — Design

## Context

sso-real-impl (archive 2026-06-14) 的 `services/sso/app/routers/sso.py:14` 声明 `router = APIRouter(prefix="/api/v1/auth/sso")`,但 `# --- /healthz ---` 段 (在同 file 里) 也注册到该 router → `/healthz` 实际路径 `/api/v1/auth/sso/healthz`,**而** `Dockerfile:48-50` HEALTHCHECK 调 `http://127.0.0.1:8007/healthz` (无 prefix) → 404。

第 2 个错 (Layer 4b) 在 `healthz` handler:`db = request.app.state.db_sessionmaker()` 调 `async_sessionmaker` 工厂,返回 `AsyncSession` 实例,然后 `async with db() as session:` 试图 call `AsyncSession` —— `'AsyncSession' object is not callable` → 503。

后果链 (本 session 2026-06-16 实测):
- lifespan 跑通 (Application startup complete, RSA key 生成, secret 文件 `/home/chatbiz-sso/.sso/secrets/jwt_private.pem` 存在)
- 但 healthcheck fail → `chatbiz-sso-1` `Up (unhealthy)`
- `chatbiz-web` 3-gate `depends_on: sso: service_healthy` fail
- Web SSO 端到端不可用

上游三件源:本 change 不触 `docs/architecture.md` / `docs/prd.md` / design doc。

## Goals / Non-Goals

**Goals** (1 条):
1. 改 2 处 Python source 让 `chatbiz-sso-1` Dockerfile HEALTHCHECK 路径 `/healthz` 返回 200

**Non-Goals** (4 条,显式 YAGNI):
1. **不** 改 Dockerfile
2. **不** 改 jwt_utils / lifespan / 其他 router
3. **不** 改 compose
4. **不** 加 unit test (本 change 改 1 个集成路由,跟 sso-real-impl 100% cov 兼容)

## Decisions

### D1: 把 `/healthz` 移到 main.py (no prefix),删 routers/sso.py 里的重复

**Context**: 现在 `/healthz` 误放在 `APIRouter(prefix="/api/v1/auth/sso")` 下,需要 root level。

**选项**:
- **A (已选)**: 在 `main.py:create_app()` 内部加 `@app.get("/healthz")` 直接注册 (绕过 router prefix),`routers/sso.py` 删 `# --- /healthz ---` 段。2 files 改,~20 lines 净
- B: 在 `routers/sso.py` 拆 2 个 router (1 个 prefix `/api/v1/auth/sso` 含业务路由, 1 个 no prefix 含 `/healthz`) — 拒绝理由:多 1 个 router 实例,main.py 多 include 1 次,侵入面更大
- C: 改 `routers/sso.py:14` `prefix="/api/v1/auth/sso"` → `prefix=""` — 拒绝理由:会让 4 个业务路由都失去 prefix (`/wechat/initiate` 而不是 `/api/v1/auth/sso/wechat/initiate`),改 frontend / 客户 / nginx proxy 都要重写

**结论**: 选 A。

### D2: healthz handler 用 `async with request.app.state.db_sessionmaker() as session:` 直接

**Context**: `db_sessionmaker` 是 `async_sessionmaker` 实例,支持 context manager 协议,`async with db_sessionmaker() as session:` 是正确用法。原代码 `db = db_sessionmaker(); async with db() as session:` 错 (第二次 `()` call 在 `AsyncSession` 上,不是 `async_sessionmaker`)。

**选项**:
- **A (已选)**: 改 handler 用 `async with request.app.state.db_sessionmaker() as session:` 直接 (1 行)。context manager `__enter__` 调 `db_sessionmaker()` 拿 `AsyncSession`,`__exit__` 关 session
- B: 改 handler 用 `async with db_sessionmaker.begin() as session:` 拿 transactional session — 拒绝理由:healthz 是 read-only,不需要 transaction
- C: 改 handler 用 try/except + `db_sessionmaker()` + `async with session:` 拆 2 步 — 拒绝理由:verbose,跟 A 等价但 3 行 vs 1 行

**结论**: 选 A。

### D3: 验证方法

**选项**:
- **A (已选)**: 重建 sso image + `docker compose ... up -d` + 等 30s + 检查 3 个状态: (1) `chatbiz-sso-1` `(healthy)`, (2) `chatbiz-web` `(healthy)` (3-gate 全 unlock), (3) `curl http://localhost:5173/api/auth/sso/jwks.json` 返回 JSON 200
- B: 只跑 unit test — 拒绝理由:本 change 改集成路由,unit test 覆盖不到

**结论**: 选 A。

## Risks / Trade-offs

- **Risk 1 (低)**: 移 `/healthz` 到 main.py 后,`routers/sso.py` 的 `# --- /healthz ---` 段被删,如果有人 grep "healthz" 找健康检查路由,会先去 routers/sso.py 找不到。**Mitigation**: 在 main.py 的 `/healthz` 装饰器上加 docstring 说明这是 system-level healthcheck (no prefix),与 sso_router 的业务路由分离
- **Risk 2 (低)**: `request.app.state.db_sessionmaker` 可能在 lifespan 失败时为 None,`async with None as session:` 会 raise AttributeError (不是 503) — 拒绝理由:lifespan 现在能正常完成,`db_sessionmaker` 必不为 None。如果 lifespan 真失败,healthcheck 该 503,改为 raise 不优雅但功能性等价

## Migration Plan

| # | Step | 产物 |
|---|---|---|
| 1 | 改 `services/sso/app/main.py`:在 `app.include_router(sso_router.router)` 之前加 `@app.get("/healthz")` 装饰器 + healthz handler 函数 | 1 file, ~15 lines added |
| 2 | 改 `services/sso/app/routers/sso.py`:删 `# --- /healthz ---` 整段 (含 `@router.get("/healthz")` + `async def healthz` 函数) | 1 file, ~17 lines removed |
| 3 | `git diff` 验证 2 files 改 | 2 files, net 0 lines (移) |
| 4 | 重建 sso image | `chatbiz/sso:dev` |
| 5 | `docker compose ... up -d` 跑 30s, 期望 sso-1 (healthy) + chatbiz-web (healthy) + curl /api/auth/sso/jwks.json 200 | 端到端验证 |

**Rollback**: 任何步骤失败 → `git revert` 已 push 的 commits。

## Verification

| # | 验证项 | 命令 | 期望 |
|---|---|---|---|
| V1 | main.py 含 `@app.get("/healthz")` | `grep '@app.get("/healthz")' services/sso/app/main.py` | 1 行输出 |
| V2 | main.py healthz handler 用 `async with ... db_sessionmaker()` | `grep "async with .* db_sessionmaker" services/sso/app/main.py` | 至少 1 行 |
| V3 | routers/sso.py 删 healthz 段 | `grep -c "healthz" services/sso/app/routers/sso.py` | 0 行 (无 healthz 残留) |
| V4 | diff scope | `git diff --stat` | 2 files, ~20 lines net 移 |
| V5 | sso-1 (healthy) | `docker ps --filter name=chatbiz-sso-1 --format "{{.Status}}"` | `(healthy)` |
| V6 | sso-1 /healthz 200 | `docker exec chatbiz-sso-1 python -c "urllib.urlopen('http://127.0.0.1:8007/healthz').status"` | `200` |
| V7 | chatbiz-web 3-gate 解锁 | `docker ps --filter name=chatbiz-web --format "{{.Status}}"` | `(healthy)` |
| V8 | Web SSO 端到端 | `curl -fsS http://localhost:5173/api/auth/sso/jwks.json \| head -c 200` | JSON `{"keys":` 200 |

## Open Questions

无。trivial ~20 lines 移 1 个 handler + 修 1 行 context manager call,无 Open Questions。
