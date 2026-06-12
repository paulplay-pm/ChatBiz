# mcp-server-audit-trail

**Frontend Scope: N/A — 审计是**被** audit-and-isolation / 合规团队消费的产品能力。**审计面板 UI 由后续 change `audit-and-isolation-admin-ui` 落地（V1.5 之后），本 change 仅生成 audit 记录，不展示。**

**Impact**（被谁消费）：
- **被** `services/audit-and-isolation` 写入 PostgreSQL `audit_events` 表
- **被** 合规团队在审计面板（未来 change）查询
- **被** Agent / Workflow 故障排查时回溯"配置变更历史"
- 关联 `mcp-server-registry` / `mcp-server-lifecycle` / `mcp-server-tool-discovery` 三个 capability（任何写操作都触发 audit）

## ADDED Requirements

### Requirement: All write operations emit audit events

The system MUST emit one audit event to `MCP_AUDIT_BASE_URL` (the audit-and-isolation egress, eng-review Arch #1) for every successful `POST /v1/mcp/servers`, `PATCH /v1/mcp/servers/{id}`, `DELETE /v1/mcp/servers/{id}`, `POST /v1/mcp/servers/{id}:connect`, `POST /v1/mcp/servers/{id}:disconnect`, and `GET /v1/mcp/servers/{id}/tools` (probe). The audit payload MUST contain `{service: "chatbiz-mcp", action, resource_id, actor, payload, trace_id, timestamp}`.

The system MUST also emit an audit event for **failed** operations (4xx / 5xx) with the same shape and `error_class` / `error_message` fields populated.

The system MUST use Fail-Open semantics (eng-review Arch #1 Risk #3: audit-and-isolation outage must not block admin actions): on `httpx.HTTPError` the audit write is logged at WARNING and the operation continues. The API response MUST include `audit_status: "archived" | "fail_open"` so callers can detect.

#### Scenario: Successful create audited
- **WHEN** an admin POSTs a new server and the audit-and-isolation endpoint returns 200
- **THEN** the audit event `{action: "create", resource_id: "<new uuid>", actor: "<admin user id>", payload: {...}, trace_id: "<uuid>"}` is POSTed to `MCP_AUDIT_BASE_URL/v1/audit/archive`

#### Scenario: Audit endpoint down (fail-open)
- **WHEN** an admin POSTs a new server and `MCP_AUDIT_BASE_URL` is unreachable (httpx.ConnectError)
- **THEN** a WARNING is logged with the payload, the new server row is still persisted, and the API response includes `audit_status: "fail_open"`

#### Scenario: Failed delete audited
- **WHEN** an admin DELETEs a server referenced by an Agent (returns 409)
- **THEN** an audit event `{action: "delete_denied", error_class: "user", error_message: "server referenced", ...}` is emitted

### Requirement: Audit events include trace_id for cross-service correlation

The system MUST generate a `trace_id` (uuid4) per incoming HTTP request and propagate it to the audit event payload AND to the response header `X-Trace-Id`. The trace_id MUST also be propagated to downstream calls to `McpRouter.dispatch` / `McpRouter.list_advertised_tools` so the audit-and-isolation service can correlate MCP tool dispatches with management actions.

#### Scenario: Trace ID propagation
- **WHEN** an admin issues `POST /v1/mcp/servers/{id}:connect` and the response includes `X-Trace-Id: abc-123`
- **THEN** the audit event for this connect action has `trace_id: "abc-123"`, and any downstream `McpRouter` call uses the same trace_id

### Requirement: PII / secret redaction in audit payloads

The system MUST redact values of fields named `env.MCP_*_KEY`, `env.MCP_*_TOKEN`, `env.MCP_*_SECRET`, `security_config.password`, `security_config.api_key` (case-insensitive) as `***REDACTED***` before emitting the audit payload. The redaction MUST be applied centrally in a `_redact(payload) -> dict` helper used by every audit-emitting path.

#### Scenario: Env with secret
- **WHEN** an admin POSTs `{env: {"MCP_FS_ALLOWED_DIRS": "/data", "MCP_GITHUB_TOKEN": "ghp_xxx"}}`
- **THEN** the audit event's `payload.env` is `{"MCP_FS_ALLOWED_DIRS": "/data", "MCP_GITHUB_TOKEN": "***REDACTED***"}`

#### Scenario: Non-secret env passes through
- **WHEN** an admin POSTs `{env: {"MCP_FS_ALLOWED_DIRS": "/data"}}`
- **THEN** the audit event's `payload.env` is unchanged

### Requirement: Critical path "插件加载降级" is fully covered

Per eng-review Test #2 critical path #4, the system MUST handle plugin load failure with graceful degradation. This means:
- A server with `status='error'` MUST NOT cause the `/v1/mcp/servers` list endpoint to fail (the list returns the row with `status='error'`, the rest are unaffected).
- A server with `status='error'` MUST NOT cause the `list_advertised_tools` of OTHER servers to fail (the router's per-server HANDLER must isolate the error).
- The admin card MUST render the `error` state with a red badge and a tooltip showing `last_error`.

#### Scenario: List endpoint not affected by one error server
- **WHEN** 3 servers exist, 1 with `status='error'`, and admin GETs `/v1/mcp/servers`
- **THEN** the response is HTTP 200 with all 3 rows including the errored one

#### Scenario: Router isolates per-server error
- **WHEN** `filesystem` server has `status='error'` and admin GETs tools for `postgres` server
- **THEN** the response is HTTP 200 with postgres tools (filesystem failure does not propagate)

#### Scenario: Frontend error badge
- **WHEN** admin views a card with `status='error'`
- **THEN** the card shows a red badge "错误" with a tooltip containing `last_error`

### Requirement: Audit egress reuses mcp-server-integration-mvp's `audit_archive` helper

The system MUST call the existing `app.router.audit_archive(tool_name, args, trace_id)` helper for audit emission (NOT a new HTTP client). The helper is already configured to POST to `MCP_AUDIT_BASE_URL/v1/audit/archive` with Fail-Open. The management action's `tool_name` MUST be a synthetic name of the form `mcp_admin.<action>` (e.g. `mcp_admin.create`, `mcp_admin.connect`) so the audit-and-isolation service can filter MCP-management events from real MCP-tool events.

#### Scenario: Audit helper called for create
- **WHEN** admin POSTs a new server
- **THEN** the code path calls `audit_archive("mcp_admin.create", {...}, trace_id)` exactly once

#### Scenario: Audit helper called for failed operation
- **WHEN** admin POSTs a server with invalid name (400)
- **THEN** the code path calls `audit_archive("mcp_admin.create_denied", {...}, trace_id)` exactly once
