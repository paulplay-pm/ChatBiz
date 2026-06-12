# mcp-server-lifecycle

**Frontend Scope: 含前端**（连接 / 断开 按钮 + 确认弹窗 + 状态轮询 + 状态徽章实时刷新）

**Impact**（被谁消费）：
- 被 admin 在 admin 卡片操作区消费（"连接" / "断开" 按钮）
- 状态机状态变化触发 `mcp-server-audit-trail` 写 audit-and-isolation（联动）

## ADDED Requirements

### Requirement: Admin can initiate connection to a MCP server

The system SHALL expose `POST /v1/mcp/servers/{id}:connect` which transitions a server from `disconnected` to `connecting` synchronously, then asynchronously runs the health probe (calling the target server's `HANDLER` via the existing `McpRouter` integration) and transitions to `connected` or `error` based on the probe result. The endpoint MUST return HTTP 202 with `{status: "connecting"}` immediately. The probe MUST be capped at 30s wall-clock and on timeout transitions the server to `error` with `last_error="probe timeout"`.

The endpoint MUST require `mcp.admin` role and SHALL return 403 otherwise.

#### Scenario: Disconnected → connecting → connected
- **WHEN** an admin POSTs `/v1/mcp/servers/{id}:connect` on a `disconnected` server whose target HANDLER is reachable
- **THEN** the response is HTTP 202 with `{"status": "connecting"}`, and within 30s the server row's `status` becomes `connected` and `last_health_check_at` is set to `now()`

#### Scenario: Probe fails
- **WHEN** an admin POSTs `/v1/mcp/servers/{id}:connect` on a server whose HANDLER raises `McpSecurityError` (e.g. `MCP_FS_ALLOWED_DIRS` unset)
- **THEN** the response is HTTP 202 with `{"status": "connecting"}`, and within 30s the server row's `status` becomes `error` and `last_error` is the security error message

#### Scenario: Already connected
- **WHEN** an admin POSTs `/v1/mcp/servers/{id}:connect` on a `connected` server
- **THEN** the response is HTTP 409 with body `{"error_class": "user", "error_message": "server already connected"}`

#### Scenario: Concurrent connect
- **WHEN** two admin sessions POST `/v1/mcp/servers/{id}:connect` simultaneously on a `disconnected` server
- **THEN** the first receives HTTP 202 and the second receives HTTP 409 with `error_message="another connect in progress"`

### Requirement: Admin can disconnect a MCP server

The system SHALL expose `POST /v1/mcp/servers/{id}:disconnect` which transitions any non-`disconnected` server to `disconnected`, clears `last_error`, and returns HTTP 202 with `{status: "disconnected"}`. The endpoint MUST require `mcp.admin` role.

The system MUST NOT cancel in-flight tool calls (per `mcp-server-integration-mvp` design, the router handles streaming; this endpoint only flips the registration row's status — actual subprocess lifecycle is handled by the router on next dispatch).

#### Scenario: Connected → disconnected
- **WHEN** an admin POSTs `/v1/mcp/servers/{id}:disconnect` on a `connected` server
- **THEN** the response is HTTP 202 with `{"status": "disconnected"}` and the row's `status` becomes `disconnected` within 1s

#### Scenario: Already disconnected
- **WHEN** an admin POSTs `/v1/mcp/servers/{id}:disconnect` on a `disconnected` server
- **THEN** the response is HTTP 202 with `{"status": "disconnected"}` (idempotent)

#### Scenario: Error → disconnected (recovery)
- **WHEN** an admin POSTs `/v1/mcp/servers/{id}:disconnect` on an `error` server
- **THEN** the response is HTTP 202 with `{"status": "disconnected"}` and `last_error` is cleared

### Requirement: Stale connecting state is auto-recovered

The system SHALL provide a startup hook (run in `services/mcp` container's lifespan) that scans `mcp_server_registrations` for rows with `status='connecting'` and `updated_at < now() - interval '30 seconds'`, and transitions them to `error` with `last_error="probe timed out (startup recovery)"`. The hook MUST log each transition to stdout.

#### Scenario: Container restart during in-flight connect
- **WHEN** a row has `status='connecting'`, `updated_at=2026-06-12T10:00:00Z`, and the container restarts at `2026-06-12T10:01:00Z`
- **THEN** after the lifespan hook runs, the row's `status` is `error` and `last_error="probe timed out (startup recovery)"`

#### Scenario: Recent connecting (within 30s)
- **WHEN** a row has `status='connecting'`, `updated_at=2026-06-12T10:00:55Z`, and the container restarts at `2026-06-12T10:01:00Z`
- **THEN** the row's `status` is **not** modified by the recovery hook

### Requirement: Frontend shows real-time status with optimistic update

The admin card MUST optimistically update its badge to "连接中" (yellow) on click of "连接" and to "未连接" (gray) on click of "断开", and then poll `GET /v1/mcp/servers` every 5s until the actual status matches. The polling MUST stop when the card unmounts. If the optimistic state diverges from the server state for more than 30s, the UI MUST show an error toast "状态刷新失败" and revert to the server state.

#### Scenario: Connect button click
- **WHEN** admin clicks "连接" on a `disconnected` card
- **THEN** the badge immediately turns yellow, the button becomes disabled with a spinner, and within 5-30s the badge turns green "已连接"

#### Scenario: Disconnect button click
- **WHEN** admin clicks "断开" on a `connected` card and confirms in the modal
- **THEN** the badge immediately turns gray "未连接" and within 5s the server response confirms

#### Scenario: Disconnect confirmation
- **WHEN** admin clicks "断开" on a `connected` card
- **THEN** a modal appears "确认断开 <name> 吗？" with Cancel / 断开 buttons; only on confirmation does the call fire

#### Scenario: Probe failure toast
- **WHEN** admin clicks "连接" and the probe fails (server returns 5xx)
- **THEN** the badge reverts to gray and a red toast appears "连接失败：<error_message>"

### Requirement: Probe uses router's per-server handler with concurrency cap

The connect probe MUST invoke the target server's `HANDLER` directly (not the full `McpRouter.list_advertised_tools` which would call all 3 servers). The probe MUST be wrapped in an `asyncio.Semaphore(5)` to cap concurrent probes, and the probe result MUST be cached in Redis with key `mcp:probe:{id}` and TTL 30s (`MCP_PROBE_CACHE_TTL`). The cache MUST be invalidated on `connect` (not on `disconnect`, since disconnect doesn't need fresh probe data).

#### Scenario: Probe targets correct server
- **WHEN** admin connects a `filesystem` server
- **THEN** the probe calls `servers.filesystem.HANDLER` with a synthetic `list_advertised_tools` argument, NOT `McpRouter.list_advertised_tools`

#### Scenario: Cache hit on rapid retry
- **WHEN** admin connects server A, it succeeds, admin immediately clicks "断开" then "连接" again within 30s
- **THEN** the second connect probe reads from Redis cache and returns within 100ms

#### Scenario: Concurrency cap
- **WHEN** 10 admin sessions click "连接" on different servers simultaneously
- **THEN** at most 5 probes run concurrently; the others queue and proceed as slots free up
