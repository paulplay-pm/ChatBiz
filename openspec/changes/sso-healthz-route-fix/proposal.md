# sso-healthz-route-fix — Proposal

## Why

`services/sso/app/routers/sso.py:14` 声明 `router = APIRouter(prefix="/api/v1/auth/sso")`,**所有** 路由 (含 `/healthz`) 继承该 prefix。结果 `chatbiz-sso-1` 实际只有 `/api/v1/auth/sso/healthz`,**没有** root `/healthz`。但 `Dockerfile:48-50` HEALTHCHECK 调 `http://127.0.0.1:8007/healthz` (无 prefix),**404**。

`sso/routers/sso.py:healthz` handler 还有第 2 个 bug: `db = request.app.state.db_sessionmaker()` 返回 `AsyncSession` 实例,然后 `async with db() as session:` 试图 call `AsyncSession` → `'AsyncSession' object is not callable` → 503。即使 prefix 修了,handler 仍 503。

后果 (本 session 实测): `Application startup complete` 但 `chatbiz-sso-1` `Up (unhealthy)`,4 个 healthcheck 调用全 404,`chatbiz-web` 3-gate 永远 block。这是 sso-real-impl (2026-06-14) 当时没 surface 的 Layer 4a + 4b pre-existing 错。

## What Changes

- **修改** `services/sso/app/main.py`:在 `create_app()` 内部、`app.include_router(sso_router.router)` **之前**,加 `@app.get("/healthz")` 装饰器直接注册 healthz 路由 (无 prefix,root level)
- **修改** `services/sso/app/routers/sso.py`:删 `# --- /healthz ---` 整段 (包括 `@router.get("/healthz")` 装饰器 + `healthz` handler 函数,共 ~15 行),改在 main.py 统一实现
- **修改** `services/sso/app/main.py` 新增 `@app.get("/healthz")` handler:用 `request.app.state.db_sessionmaker` 作 context manager (不是 `db_sessionmaker()` 调),`async with` 而非 `async with db()`
- **不** 改 Dockerfile (HEALTHCHECK 路径 `/healthz` 已正确,本 change 让它 work)
- **不** 改任何 compose / env
- **不** 改 jwt_utils / lifespan / 其他 router

## Capabilities

### New Capabilities

无。`/healthz` 健康检查端点已存在 sso-real-impl 的 spec,本 change 修其错位的实现。

### Modified Capabilities

- `sso-real-impl` (existing capability, archive 2026-06-14): **前端范围** = N/A;**后端范围** = 2 files (main.py + routers/sso.py) ~20 lines 改;**是否豁免前端** = 是 — 纯 Python 路由修。

## Impact

- **新开发者 onboarding**: `docker compose -f ... -f ... up -d` 后 `chatbiz-sso-1` 从 `Up (unhealthy)` 升到 `(healthy)`,`chatbiz-web` 3-gate 全 unlock,Web SSO 端到端可用 (`curl /api/auth/sso/jwks.json` 200)
- **CI**: 不动
- **生产部署**: 0 影响
- **被消费的下游**: 4 个 `chatbiz-web` 3-gate 内的依赖 (`sso: service_healthy`) 都 work

## Non-goals

1. **不** 改 Dockerfile
2. **不** 改 jwt_utils / lifespan / 其他 router
3. **不** 改 compose
4. **不** 改 spec/plan 文件
5. **不** 加 unit test (本 change 改 1 个集成路由,跟 sso-real-impl 的 100% cov 兼容)
