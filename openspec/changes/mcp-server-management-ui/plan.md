# mcp-server-management-ui Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development
> to implement this plan task-by-task.

**Goal:** 在 admin-web 提供 MCP server 增删改查 + 启停状态管理（卡片网格 + 配置弹窗），覆盖 eng-review Test #2 critical path #4 插件加载降级；不引新微服务，不引 FastAPI，复用现有 `services/mcp` 容器（端口 8004）。

**Architecture:** `services/mcp` 容器内挂 6 个 Starlette REST 端点（GET/POST/PATCH/DELETE + connect/disconnect）+ 1 个 tools discovery 端点；元数据落 PostgreSQL `mcp_server_registrations`（source of truth），探活结果缓存 Redis 30s；admin-web 用 React + SWR 5s 轮询；所有写操作经 audit-and-isolation egress（eng-review Arch #1，工具名 `mcp_admin.<action>`）；前端 TS interface 与 Python TypedDict 字段手工对齐（Q4 trade-off 接受短期的对齐工作）。

**Tech Stack:**
- Python 3.12 (conda env `chatbiz`) + Starlette 0.46+ + SQLAlchemy 2.0 async + Alembic + Redis asyncio
- React 18 + TypeScript strict + SWR + react-hook-form + zod + Playwright
- PostgreSQL 16+ (已有 `x-pg-env`) + Redis 7 (已有) + audit-and-isolation (eng-review 锁定)

---

> **OPT — writing-plans skill fallback**：
> 当前 session 的 skills 列表**未**装载 `superpowers:writing-plans`（plugin 缓存里有，但 enable 列表未启用）。
> 按 schema `plan.instruction` 提示，本 plan **手写**采用"节级 micro-step 模板 + 关键 task 完整展开"模式，避免 36 task × 5 micro-step × 完整内容 = 几百行不可维护。
> 关键 task（带 ★）给出完整 micro-step；其余 task 在每节用"Repeat above pattern for N tasks"压缩。
> apply 阶段由 subagent-driven-development 按本 plan 跑——agent 应在每个 task 落地前**自行展开** micro-step，不机械照抄本 plan。

---

## Task 1.1 ★: registry_types.py — McpServerRegistration TypedDict

**Files:**
- Create: `services/mcp/app/registry_types.py`
- Create: `services/mcp/tests/unit/test_registry_types.py`

**Step 1**: Write failing test
```bash
cd services/mcp && conda activate chatbiz && pytest tests/unit/test_registry_types.py::test_to_pydantic_roundtrip -x
```
Expected: `ModuleNotFoundError: No module named 'app.registry_types'`

**Step 2**: Create module
```python
# services/mcp/app/registry_types.py
from __future__ import annotations
from typing import TypedDict, Literal, Any
from uuid import UUID
from datetime import datetime

class McpServerRegistration(TypedDict):
    id: UUID
    name: str
    transport: Literal["stdio", "sse", "http"]
    command: str
    args: list[str]
    env: dict[str, str]
    security_config: dict[str, Any]
    status: Literal["disconnected", "connecting", "connected", "error"]
    last_health_check_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime

def to_pydantic(reg: McpServerRegistration) -> "McpServerRegistrationPD": ...
def to_sqlalchemy_column_spec() -> list[dict]: ...
def to_audit_payload(reg: McpServerRegistration) -> dict: ...
def to_frontend_json(reg: McpServerRegistration) -> dict: ...
```

**Step 3**: Implement 4 to_* functions
- `to_pydantic` 用 pydantic v2 `model_validate`
- `to_sqlalchemy_column_spec` 返 `Column` spec 列表（被 `app/registry.py` 用）
- `to_audit_payload` 调 `_redact()` 替换 secret
- `to_frontend_json` 序列化 UUID + datetime → str

**Step 4**: Run tests
```bash
conda activate chatbiz && pytest tests/unit/test_registry_types.py --cov=app/registry_types --cov-fail-under=100
```
Expected: 8 passed, coverage 100%

**Step 5**: Commit
```bash
git add services/mcp/app/registry_types.py services/mcp/tests/unit/test_registry_types.py
git commit -m "feat(mcp): add McpServerRegistration TypedDict + 4 to_* converters"
```

---

## Task 1.2: test_registry_types.py — 8 round-trip cases

**Pattern** (repeat for each to_* function):
- **Step 1**: Write test with valid input → assert output matches expected shape
- **Step 2**: Run test, expect pass
- **Step 3**: Add 1 invalid-input case (e.g. `transport="ftp"`) → assert Pydantic ValidationError
- **Step 4**: Run, expect pass
- **Step 5**: Commit (combine with 1.1)

**Coverage target**: 100% (all 4 to_* + 1 Pydantic error case + 1 secret redact case + 2 round-trip)

---

## Task 2.1: Alembic init

**Files:**
- Create: `services/mcp/alembic.ini`
- Create: `services/mcp/alembic/env.py`
- Create: `services/mcp/alembic/script.py.mako`

**Step 1**: `cd services/mcp && alembic init alembic`
**Step 2**: Edit `alembic.ini` → `sqlalchemy.url = ${MCP_DATABASE_URL}`
**Step 3**: Edit `alembic/env.py` → `from app.registry import Base; target_metadata = Base.metadata` (use async engine)
**Step 4**: Verify: `alembic current` → `[]` (no migrations yet)
**Step 5**: Commit

## Task 2.2 ★: migration 0001 — create mcp_server_registrations

**Files:**
- Create: `services/mcp/alembic/versions/0001_mcp_server_registrations.py`

**Step 1**: Write failing test (testcontainers PG)
```python
# tests/integration/test_migration.py
def test_upgrade_creates_table(pg_container):
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    assert row_exists(pg_container, "mcp_server_registrations")
```

**Step 2**: Generate migration skeleton
```bash
alembic revision -m "create mcp_server_registrations"
```

**Step 3**: Fill `upgrade()` / `downgrade()` with all spec columns + indexes
- `id` UUID PK
- `name` text UNIQUE NOT NULL
- `transport` enum (`create_type=False` for downgrade)
- `args` / `env` / `security_config` jsonb
- `status` enum default `disconnected`
- `last_health_check_at` / `last_error` nullable
- `created_at` / `updated_at` timestamptz default now()
- Index: `idx_mcp_server_registrations_status`

**Step 4**: Run test
```bash
pytest tests/integration/test_migration.py -x
```
Expected: 1 passed

**Step 5**: Run `alembic downgrade base` then `alembic upgrade head` round-trip in test
**Step 6**: Commit

## Task 2.3: test_migration.py — round-trip test

**Pattern**: Same as 2.1 step 1; commit combined with 2.2.

---

## Task 3.1 ★: registry.py — McpRegistry (5 CRUD methods + reference check)

**Files:**
- Create: `services/mcp/app/registry.py`
- Create: `services/mcp/tests/unit/test_registry.py`

**Step 1**: Write failing tests
- 5 methods × 2 cases (success + error) = 10 cases
- 1 reference check (unreferenced → delete ok; referenced → raise)
- 1 secret injection (name="'; DROP TABLE..." → ValidationError)

**Step 2**: Implement `McpRegistry(session_factory)`
- `list_servers()` → `SELECT * FROM mcp_server_registrations ORDER BY created_at`
- `create_server(payload, actor)` → INSERT, return new row, emit audit `mcp_admin.create`
- `update_server(id, payload, actor)` → reject if `command`/`env` change while `status='connected'` (409), emit audit
- `delete_server(id, actor)` → call `_check_references()` first, return list of refs; emit audit `mcp_admin.delete` or `mcp_admin.delete_denied`
- `get_server(id)` → SELECT one
- `_check_references(id)` → stub for now: return `[]` (agents / workflows tables not in this change)

**Step 3**: Run
```bash
pytest tests/unit/test_registry.py --cov=app/registry --cov-fail-under=100
```
Expected: 12 passed, coverage 100%

**Step 4**: Commit

## Task 3.2: test_registry.py — 12 cases

**Pattern**: Standard TDD per method; combined commit with 3.1.

## Task 3.3 ★: api.py — 7 Starlette Routes (CRUD + connect/disconnect + tools)

**Files:**
- Create: `services/mcp/app/api.py`
- Create: `services/mcp/tests/integration/test_api.py`
- Modify: `services/mcp/app/main.py` (mount routes)

**Step 1**: Write failing integration tests
- 6 endpoints × 1 happy path + 1 error case = 12 cases
- 1 X-Trace-Id header check
- 1 audit emit check per write endpoint

**Step 2**: Implement Routes
```python
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse

async def list_servers(request: Request) -> JSONResponse:
    registry = request.app.state.registry
    servers = await registry.list_servers()
    return JSONResponse([to_frontend_json(s) for s in servers])

async def create_server(request: Request) -> JSONResponse:
    payload = await request.json()
    actor = request.headers.get("X-User-Id", "anonymous")
    trace_id = request.state.trace_id
    server = await request.app.state.registry.create_server(payload, actor=actor)
    await emit_audit("mcp_admin.create", server["id"], actor, payload, trace_id)
    return JSONResponse(to_frontend_json(server), status_code=201,
                        headers={"Location": f"/v1/mcp/servers/{server['id']}",
                                 "X-Trace-Id": trace_id})
# ... 5 more routes

routes = [
    Route("/v1/mcp/servers", list_servers, methods=["GET"]),
    Route("/v1/mcp/servers", create_server, methods=["POST"]),
    Route("/v1/mcp/servers/{id}", update_server, methods=["PATCH"]),
    Route("/v1/mcp/servers/{id}", delete_server, methods=["DELETE"]),
    Route("/v1/mcp/servers/{id}:connect", connect_server, methods=["POST"]),
    Route("/v1/mcp/servers/{id}:disconnect", disconnect_server, methods=["POST"]),
    Route("/v1/mcp/servers/{id}/tools", list_server_tools, methods=["GET"]),
]
```

**Step 3**: Mount in `main.py`
- `app.state.registry = McpRegistry(session_factory)`
- `app.state.probe_cache = ProbeCache(redis_url)`
- `app.router.routes.extend(routes)`

**Step 4**: Run integration tests
```bash
pytest tests/integration/test_api.py --cov=app/api --cov-fail-under=100
```
Expected: 14 passed

**Step 5**: Commit

## Task 3.4: test_api.py — 14 integration cases

**Pattern**: httpx + LifespanManager + 假 audit (FakeAuditArchive 复用 `mcp-server-integration-mvp` 模式); combined commit with 3.3.

---

## Task 4.1 ★: probe.py — probe_server() with semaphore + timeout

**Files:**
- Create: `services/mcp/app/probe.py`
- Create: `services/mcp/tests/unit/test_probe.py`

**Step 1**: Write 8 failing tests
- filesystem ok / missing env (SecurityError) / permission denied
- fetch ok / timeout / 5xx
- postgres ok / unknown transport
- concurrency cap (10 calls but semaphore=5)
- cache hit (Redis returns stale)
- (8 cases total)

**Step 2**: Implement
```python
import asyncio
from typing import TypedDict, Literal

class ProbeResult(TypedDict):
    status: Literal["connected", "error"]
    tools: list[dict] | None
    error: str | None

_PROBE_SEMAPHORE = asyncio.Semaphore(5)
_TIMEOUT_SECONDS = 30

async def probe_server(server_id: str, registry, cache) -> ProbeResult:
    server = await registry.get_server(server_id)
    # Check cache first
    cached = await cache.get_probe(server_id)
    if cached:
        return cached
    async with _PROBE_SEMAPHORE:
        try:
            handler = _import_handler(server["name"])  # filesystem / fetch / postgres
            result = await asyncio.wait_for(
                handler("list_advertised_tools", {}),
                timeout=_TIMEOUT_SECONDS,
            )
            return {"status": "connected", "tools": result, "error": None}
        except asyncio.TimeoutError:
            return {"status": "error", "tools": None, "error": "probe timeout"}
        except Exception as e:
            return {"status": "error", "tools": None, "error": str(e)}
```

**Step 3**: Run
```bash
pytest tests/unit/test_probe.py --cov=app/probe --cov-fail-under=100
```
Expected: 8 passed

**Step 4**: Commit

## Task 4.2: test_probe.py — 8 cases (TDD per case)
## Task 4.3: connect/disconnect async task
- **Step 1**: Implement async task `asyncio.create_task(_do_connect(server_id))` registered in `app.state.background_tasks`
- **Step 2**: After task completes, update PG `status` field via `registry.update_status()`
- **Step 3**: try/finally to ensure task is awaited/cancelled cleanly
- **Step 4**: Test with `asyncio.wait_for` mocking probe to return after 100ms; verify status updated within 5s
- **Step 5**: Commit

## Task 4.4 ★: cache.py — ProbeCache (Redis asyncio)

**Files:**
- Create: `services/mcp/app/cache.py`
- Tests: combined in 4.2 (mock Redis)

**Step 1**: Write 3 failing tests
- `get_probe(id)` returns None on miss
- `set_probe(id, result, ttl=30)` writes to Redis
- Redis write failure logs WARNING, does NOT raise

**Step 2**: Implement
```python
import redis.asyncio as redis
import json
import logging

log = logging.getLogger(__name__)

class ProbeCache:
    def __init__(self, redis_url: str):
        self._redis = redis.from_url(redis_url)
    
    async def get_probe(self, server_id: str) -> dict | None:
        try:
            raw = await self._redis.get(f"mcp:probe:{server_id}")
            return json.loads(raw) if raw else None
        except Exception as e:
            log.warning("redis get failed: %s", e)
            return None
    
    async def set_probe(self, server_id: str, result: dict, ttl: int = 30) -> None:
        try:
            await self._redis.setex(f"mcp:probe:{server_id}", ttl, json.dumps(result))
        except Exception as e:
            log.warning("redis set failed: %s", e)
```

**Step 3**: Run
```bash
pytest tests/unit/test_probe.py::TestCache -x
```
Expected: 3 passed

**Step 4**: Commit

## Task 4.5: stale-connecting recovery hook (lifespan startup)
- **Step 1**: In `app/main.py` lifespan `startup`, add SQL: `UPDATE mcp_server_registrations SET status='error', last_error='probe timed out (startup recovery)' WHERE status='connecting' AND updated_at < now() - interval '30 seconds'`
- **Step 2**: Log affected row count
- **Step 3**: Wrap in try/except so hook failure doesn't block startup
- **Step 4**: Test: insert row with `updated_at=now()-1min`, run startup, assert row's `status='error'`
- **Step 5**: Commit

---

## Task 5.1 ★: audit.py — emit_audit() + redaction

**Files:**
- Create: `services/mcp/app/audit.py`
- Create: `services/mcp/tests/unit/test_audit.py`

**Step 1**: Write 6 failing tests
- 5 redact cases (`MCP_GITHUB_TOKEN`, `MCP_API_KEY`, `MCP_DB_SECRET`, `password`, `api_key` → `***REDACTED***`)
- 1 non-redact (`MCP_FS_ALLOWED_DIRS` unchanged)
- 1 emit happy path (calls `audit_archive` from `app.router`)

**Step 2**: Implement
```python
import re
import logging
from app.router import audit_archive

log = logging.getLogger(__name__)

_REDACT_PATTERNS = [
    re.compile(r"MCP_.*_KEY", re.IGNORECASE),
    re.compile(r"MCP_.*_TOKEN", re.IGNORECASE),
    re.compile(r"MCP_.*_SECRET", re.IGNORECASE),
    re.compile(r"^password$", re.IGNORECASE),
    re.compile(r"^api_key$", re.IGNORECASE),
]

def _redact(payload: dict) -> dict:
    out = {}
    for k, v in payload.items():
        if any(p.match(k) for p in _REDACT_PATTERNS):
            out[k] = "***REDACTED***"
        else:
            out[k] = v
    return out

async def emit_audit(action, resource_id, actor, payload, trace_id, error_class=None, error_message=None):
    redacted = _redact(payload)
    body = {
        "service": "chatbiz-mcp",
        "action": action,
        "resource_id": str(resource_id),
        "actor": actor,
        "payload": redacted,
        "trace_id": trace_id,
    }
    if error_class:
        body["error_class"] = error_class
        body["error_message"] = error_message
    result = await audit_archive(action, body, trace_id)
    return result  # contains "status": "archived" | "fail_open"
```

**Step 3**: Run
```bash
pytest tests/unit/test_audit.py --cov=app/audit --cov-fail-under=100
```
Expected: 7 passed

**Step 4**: Commit

## Task 5.2: trace_id middleware
- **Step 1**: Add `BaseHTTPMiddleware` in `app/api.py` that:
  - Reads `X-Trace-Id` from request headers (if present, validate via `uuid.UUID()`)
  - Else generates `uuid.uuid4()`
  - Sets `request.state.trace_id = tid`
  - Adds `X-Trace-Id` to response headers
- **Step 2**: Test: client sends `X-Trace-Id: <valid uuid>` → response echoes it
- **Step 3**: Test: client sends `X-Trace-Id: not-a-uuid` → server generates new one (validates input)
- **Step 4**: Test: client doesn't send → server generates one
- **Step 5**: Commit

## Task 5.3: test_audit_egress.py — 5 integration cases (respx mock)
- **Step 1**: Mock `MCP_AUDIT_BASE_URL` with respx
- **Step 2**: 5 cases: create / patch / delete / connect / disconnect each emit 1 audit POST
- **Step 3**: Assert body contains `service="chatbiz-mcp"`, `action`, `trace_id`, `payload`
- **Step 4**: Commit

---

## Task 6.1: docker-compose.yml — add chatbiz-mcp-migrate

**Files:**
- Modify: `infrastructure/docker-compose.yml`

**Step 1**: Find `chatbiz-mcp:` service block
**Step 2**: Add below it:
```yaml
  chatbiz-mcp-migrate:
    image: chatbiz-mcp:${MCP_IMAGE_TAG:-latest}
    profiles: ["mcp-migrate"]
    restart: "no"
    command: ["python", "-m", "alembic", "upgrade", "head"]
    environment:
      - MCP_DATABASE_URL=${MCP_DATABASE_URL}
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - chatbiz-internal
```

**Step 3**: Add `depends_on` block to `chatbiz-mcp`:
```yaml
  chatbiz-mcp:
    ...
    depends_on:
      postgres:
        condition: service_healthy
      chatbiz-mcp-migrate:
        condition: service_completed_successfully
```

**Step 4**: Verify
```bash
docker compose config | grep -A5 "chatbiz-mcp-migrate"
```
Expected: 5 lines of yaml

**Step 5**: Commit

## Task 6.2: CLAUDE.md 端口表 — verify (no change)
- 8004 已存在，本 change 不新占
- **不**需要改端口表
- **不** commit

---

## Task 7.1 ★: admin-web/src/api/mcp.ts — 7 client functions

**Files:**
- Create: `apps/admin-web/src/api/mcp.ts`
- Create: `apps/admin-web/src/api/mcp.test.ts`

**Step 1**: Write failing test (mock fetch)
- 7 functions × 1 success + 1 error case = 14 cases

**Step 2**: Implement
```typescript
import { z } from "zod";
import type { McpServer, McpTool } from "../types/mcp";

const McpServerSchema = z.object({...});  // mirror registry_types.py

async function listServers(): Promise<McpServer[]> {
  const res = await fetch("/v1/mcp/servers", { credentials: "include" });
  if (!res.ok) throw await mapError(res);
  return z.array(McpServerSchema).parse(await res.json());
}
// ... 6 more
```

**Step 3**: Run
```bash
cd apps/admin-web && pnpm vitest src/api/mcp.test.ts
```
Expected: 14 passed

**Step 4**: `tsc --noEmit` 0 errors
**Step 5**: Commit

## Task 7.2: types/mcp.ts — TS interface + Zod (mirror Python TypedDict)
- **Step 1**: Hand-write McpServer / McpTool interfaces, **字段一一对应** registry_types.py
- **Step 2**: Add Zod schema for runtime validation
- **Step 3**: Secret field rendering: `value?.includes("KEY") || value?.includes("TOKEN") || value?.includes("SECRET")` → render `***REDACTED***`
- **Step 4**: `tsc --noEmit` 0 errors
- **Step 5**: Commit

## Task 7.3 ★: views/mcp/McpToolsView.tsx — main view (SWR 5s)
- **Step 1**: Mock 3 servers in dev, render card grid
- **Step 2**: `useSWR('/v1/mcp/servers', listServers, { refreshInterval: 5000 })`
- **Step 3**: Render `<McpServerCard>` for each server + dashed "+ 添加 MCP Server" card
- **Step 4**: Empty state when `data.length === 0`
- **Step 5**: `tsc --noEmit` 0 errors
- **Step 6**: Commit

## Task 7.4: components/mcp/McpServerCard.tsx — card with 4 status variants
## Task 7.5: components/mcp/McpServerForm.tsx — modal form (react-hook-form + zod)
## Task 7.6: components/mcp/DisconnectConfirmModal.tsx — confirm modal
## Task 7.7: router/index.tsx — add /mcp-tools route (lazy, route guard)
## Task 7.8: SideNav.tsx — activate "MCP 工具" menu item

(Each follows the same TDD pattern: test → implement → typecheck → commit)

---

## Task 8.1 ★: e2e/mcp-tools.spec.ts — Playwright (critical path #4)
**Files:**
- Create: `apps/admin-web/e2e/mcp-tools.spec.ts`

**Step 1**: Write 4 test cases
- admin sees 3 cards with correct badges
- click "连接" → badge turns green within 5s
- delete env → badge turns red + tooltip shows last_error
- delete referenced server → 409 modal appears

**Step 2**: Implement with `testcontainers` (chatbiz-mcp + PG + audit-and-isolation mock)
- `test.beforeAll` → start containers
- `test.afterAll` → stop containers

**Step 3**: Run
```bash
pnpm playwright test e2e/mcp-tools.spec.ts
```
Expected: 4 passed

**Step 4**: Commit

## Task 8.2: playwright.config.ts — add mcp-tools project
- **Step 1**: Add project block with `webServer: { command: 'pnpm dev', port: 5173 }`
- **Step 2**: Run `pnpm playwright test --project=mcp-tools` (separate from full E2E)
- **Step 3**: Commit

---

## Task 9.1 ★: integration/test_lifecycle_e2e.py — full HTTP roundtrip
- **Step 1**: Spawn `chatbiz-mcp` subprocess (testcontainers PG + Redis)
- **Step 2**: POST /v1/mcp/servers (register filesystem) → assert 201
- **Step 3**: POST /v1/mcp/servers/{id}:connect → assert 202; poll GET until status='connected' (timeout 30s)
- **Step 4**: GET /v1/mcp/servers/{id}/tools → assert 4 tools
- **Step 5**: DELETE /v1/mcp/servers/{id} → assert 204; assert PG row removed
- **Step 6**: Cleanup containers
- **Step 7**: Commit

## Task 9.2 ★: integration/test_critical_path_plugin_degradation.py — Test #2 #4 coverage
- **Step 1**: Register filesystem (env unset) + postgres (env set)
- **Step 2**: Connect filesystem → wait for status='error' (within 30s)
- **Step 3**: GET /v1/mcp/servers → assert both rows present, filesystem has status='error'
- **Step 4**: GET /v1/mcp/servers/{postgres_id}/tools → assert 200 (filesystem error doesn't propagate)
- **Step 5**: Cleanup
- **Step 6**: Commit

## Task 9.3: Full coverage check
- **Step 1**: `pytest services/mcp/ --cov=services/mcp/app --cov-fail-under=100`
- **Step 2**: Expected: ≥100% (Python); 8/8 unit + 3/3 integration pass

## Task 9.4: Frontend coverage
- **Step 1**: `pnpm --filter admin-web test --coverage`
- **Step 2**: Expected: ≥80% (frontend not 100% per openspec/config.yaml spec rules 第 53 行)

---

## Task 10.1: services/mcp/docs/management-api.md — OpenAPI 3.1 (hand-written)
- **Step 1**: Write 7 endpoint docs (path / method / request / response / errors)
- **Step 2**: `npx @redocly/cli lint services/mcp/docs/management-api.md` → 0 errors
- **Step 3**: Commit

## Task 10.2: Update docs/prd.md §4.4.2
- **Step 1**: Find MCP row in plugin types table
- **Step 2**: Append "V1.0 P1 已落地：见 `mcp-server-management-ui` (commit <sha>)"
- **Step 3**: Commit

## Task 10.3: Update docs/architecture.md §4.3.6
- **Step 1**: Find §4.3.6 "插件运行时"
- **Step 2**: Append paragraph: 管理面在 `services/mcp` 容器内挂 REST（`McpRegistry` + 状态机 + audit-and-isolation egress）
- **Step 3**: Commit

## Task 10.4: write retrospective.md (after verify PASS)
- **Step 1**: Run `git log <base>..HEAD --oneline` to populate §0 Evidence
- **Step 2**: Fill 6 sections (Wins / Misses / Plan deviations / Skill compliance / Surprises / Promote candidates)
- **Step 3**: Commit

## Task 10.5: Final validate
- **Step 1**: `openspec schema validate mcp-server-management-ui` → 0 exit
- **Step 2**: `openspec list` shows change as ready for archive

---

## 配对验证总结（openspec/config.yaml 规则第 56 行：编码任务配对验证任务）

| 编码 | 配对验证 | 同 commit |
|---|---|---|
| 1.1 | 1.2 | ✓ |
| 2.1 | 2.3 | ✓ |
| 2.2 (migration) | 2.3 | ✓ |
| 3.1 | 3.2 | ✓ |
| 3.3 | 3.4 | ✓ |
| 4.1 | 4.2 | ✓ |
| 4.3 (async) | 4.2 | (covered by 4.2 cases) |
| 4.4 (cache) | 4.2 TestCache | ✓ |
| 4.5 (recovery) | 9.2 critical path | separate commit |
| 5.1 | 5.3 | ✓ |
| 5.2 (middleware) | 3.4 (X-Trace-Id check) | separate commit |
| 6.1 (compose) | `docker compose config` | (manual) |
| 7.1 (api) | 7.1 test | ✓ |
| 7.2 (types) | 7.1 Zod parse | ✓ |
| 7.3-7.8 (UI) | 8.1 E2E | (separate) |
| 8.1 (E2E) | 8.2 (config) | ✓ |
| 9.1 (e2e) | 9.3 (coverage) | (aggregate) |
| 9.2 (critical path) | 9.3 (coverage) | (aggregate) |
| 10.1 (docs) | 10.5 (validate) | (aggregate) |

---

## Critical Path 覆盖矩阵

| Critical Path (eng-review Test #2) | 覆盖 spec Requirement | 覆盖 task |
|---|---|---|
| ① paul 财务月报 end-to-end | 不在本 change (workflow-engine 后续 change) | — |
| ② 数据隔离网关 PII 拦截 | 不在本 change (audit-and-isolation 后续 change) | — |
| ③ 人工审批中断续接 | 不在本 change (workflow-engine 后续 change) | — |
| **④ 插件加载降级** | `mcp-server-audit-trail` § Requirement: Critical path "插件加载降级" is fully covered | **Task 9.2** (test_critical_path_plugin_degradation.py) |

Critical path #4 = 本 change 唯一直接覆盖项；其他 3 个由其他 change 负责（不重提）。

---

## Estimated time budget (per tasks.md estimates)

| Section | Tasks | Estimated hours |
|---|---|---|
| 0. 前置门 | 3 | 2h (等 admin-web 就位) |
| 1. 契约层 | 2 | 1.5h |
| 2. DB | 3 | 2h |
| 3. 后端 CRUD | 4 | 4h |
| 4. 探活 | 5 | 3h |
| 5. 审计 | 3 | 2h |
| 6. compose | 1 | 0.5h |
| 7. 前端 | 8 | 6h (等 admin-web 就位后) |
| 8. E2E | 2 | 3h |
| 9. 集成 | 4 | 3h |
| 10. 收尾 | 5 | 2h |
| **Total** | **40** | **~29h**（含前置门等待） |
