<!--
Delta spec for `sso-healthz-route-fix` capability.
NEW capability (no existing spec in openspec/specs/sso-healthz-route-fix/).
Followup to sso-secrets-path-fix (2026-06-16) and sso-real-impl (2026-06-14).
-->

## ADDED Requirements

### Requirement: sso /healthz 路由在 root path
The system MUST expose the sso health check endpoint at root path `/healthz` (no APIRouter prefix), so that the `sso/Dockerfile` HEALTHCHECK call `http://127.0.0.1:8007/healthz` succeeds. The endpoint MUST be defined directly in `services/sso/app/main.py` using `@app.get("/healthz")` (bypassing the `sso_router.APIRouter(prefix="/api/v1/auth/sso")` prefix), and the redundant `# --- /healthz ---` block in `services/sso/app/routers/sso.py` MUST be deleted. After this change, `grep -c "healthz" services/sso/app/routers/sso.py` MUST return `0`.

#### Scenario: main.py @app.get("/healthz") 注册
- **WHEN** a developer runs `grep '@app.get("/healthz")' services/sso/app/main.py` after the change
- **THEN** the output MUST contain at least one match (the new healthz route registration in main.py)

#### Scenario: routers/sso.py 删 healthz 段
- **WHEN** the same developer runs `grep -c "healthz" services/sso/app/routers/sso.py` after the change
- **THEN** the output MUST be `0` (the old `@router.get("/healthz")` + `healthz` handler are deleted)

#### Scenario: Dockerfile HEALTHCHECK 路径 /healthz 200
- **WHEN** the same developer runs `docker exec chatbiz-sso-1 python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8007/healthz').status)"` after rebuilding the sso image
- **THEN** the output MUST be `200` and the command MUST exit 0 (proving the root-path `/healthz` route works and returns 200, instead of the previous 404 from the APIRouter prefix mismatch)

### Requirement: healthz handler 用 async_sessionmaker context manager
The system MUST implement the sso healthz handler using `async with request.app.state.db_sessionmaker() as session:` (where `db_sessionmaker` is the `async_sessionmaker` instance, used directly as a context manager), and the handler MUST call `await session.execute(text("SELECT 1"))` to verify DB connectivity. The handler MUST NOT call the returned `AsyncSession` object again (`db = db_sessionmaker(); async with db() as session:` is incorrect because it tries to call `AsyncSession` as a function, which raises `'AsyncSession' object is not callable`).

#### Scenario: healthz handler 调 session.execute
- **WHEN** the same developer runs `grep -A 1 "async with" services/sso/app/main.py | grep session.execute` after the change
- **THEN** the output MUST contain at least one `session.execute` call inside the `async with` block

#### Scenario: healthz handler 不调 AsyncSession 作函数
- **WHEN** the same developer runs `grep "db()" services/sso/app/main.py services/sso/app/routers/sso.py` after the change
- **THEN** the output MUST be empty (no `db()` call on the returned AsyncSession object)

### Requirement: chatbiz-sso-1 (healthy) + chatbiz-web 3-gate 解锁
The system MUST result in the `chatbiz-sso-1` dev container reporting `(healthy)` after `docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose-dev.yml up -d` is run and at least 30 seconds elapse. This unlocks the dev compose `chatbiz-web` block's 3-gate `depends_on: sso + workflow-engine + mcp: service_healthy` chain, allowing `chatbiz-web` to also report `(healthy)` and the Web SSO end-to-end path (e.g. `curl http://localhost:5173/api/auth/sso/jwks.json`) to return HTTP 200 with a JSON body containing a `keys` array.

#### Scenario: chatbiz-sso-1 (healthy)
- **WHEN** a developer runs `docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose-dev.yml up -d` and waits 30 seconds, then runs `docker ps --filter name=chatbiz-sso-1 --format "{{.Status}}"`
- **THEN** the output MUST be `(healthy)` (no longer `Up (unhealthy)` as before the change)

#### Scenario: chatbiz-web 3-gate 解锁
- **WHEN** the same developer runs `docker ps --filter name=chatbiz-web --format "{{.Status}}"`
- **THEN** the output MUST be `(healthy)` (proving the 3-gate `depends_on: sso + workflow-engine + mcp: service_healthy` chain is now satisfied)

#### Scenario: Web SSO end-to-end 端点 200
- **WHEN** the same developer runs `curl -fsS http://localhost:5173/api/auth/sso/jwks.json | head -c 200`
- **THEN** the command MUST exit 0 and the output MUST contain a JSON body starting with `{"keys":` (proving the Web SSO end-to-end path is fully wired: nginx → chatbiz-sso via the upstream proxy)
