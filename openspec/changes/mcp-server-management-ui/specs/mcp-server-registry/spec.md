# mcp-server-registry

**Frontend Scope: 含前端**（卡片列表 + 弹窗表单 + 状态徽章 + 权限渲染）

**Impact**（被谁消费）：
- 被 admin / paul / leo / anny 在 admin "MCP 工具" 页面消费
- 被 `mcp-server-lifecycle` 内部消费（CRUD 出元数据后由 lifecycle 改 status）
- 未来被 `agent-runtime` 通过 `GET /v1/mcp/servers` 间接消费（拉 server 列表决定 Agent 可用 tool）

## ADDED Requirements

### Requirement: Admin can list all registered MCP servers

The system SHALL expose `GET /v1/mcp/servers` returning a JSON array of every registered MCP server, sorted by `created_at` ascending. Each element MUST contain `id`, `name`, `transport`, `command`, `args`, `env` (with secret values redacted as `***`), `security_config`, `status`, `last_health_check_at`, `last_error`, `created_at`, `updated_at`.

The endpoint MUST require an authenticated admin session and SHALL return 401 for unauthenticated callers.

#### Scenario: Empty registry
- **WHEN** an authenticated admin calls `GET /v1/mcp/servers` and no MCP servers are registered
- **THEN** the response body is `[]` with HTTP 200

#### Scenario: Three servers registered
- **WHEN** three MCP servers exist in PostgreSQL (`filesystem` / `browser` / `code-execution`)
- **THEN** the response body is a 3-element JSON array ordered by `created_at ASC` and HTTP 200

#### Scenario: Unauthenticated caller
- **WHEN** an unauthenticated caller hits `GET /v1/mcp/servers`
- **THEN** the response is HTTP 401 with body `{"error_class": "security", "error_message": "unauthenticated"}`

### Requirement: Admin can register a new MCP server

The system SHALL expose `POST /v1/mcp/servers` accepting a JSON body `{name, transport, command, args, env, security_config}`. The system MUST validate `name` matches `^[a-z][a-z0-9-]{2,63}$`, `transport` is one of `{stdio, sse, http}`, and `name` is unique across the registry. On success the system MUST persist a row in `mcp_server_registrations` with `status='disconnected'` and return HTTP 201 with the new resource.

#### Scenario: Successful registration
- **WHEN** an authenticated admin POSTs `{name: "filesystem-mcp", transport: "stdio", command: "python", args: ["-m", "servers.filesystem"], env: {"MCP_FS_ALLOWED_DIRS": "/data"}, security_config: {"allowed_dirs": ["/data"]}}`
- **THEN** the response is HTTP 201 with the new resource and a `Location: /v1/mcp/servers/{id}` header

#### Scenario: Duplicate name rejected
- **WHEN** an admin POSTs a server with `name="filesystem-mcp"` and one already exists
- **THEN** the response is HTTP 409 with body `{"error_class": "user", "error_message": "name already exists"}`

#### Scenario: Invalid name pattern
- **WHEN** an admin POSTs `{name: "F@O"}` (uppercase, special char)
- **THEN** the response is HTTP 400 with body `{"error_class": "user", "error_message": "name must match ^[a-z][a-z0-9-]{2,63}$"}`

#### Scenario: Forbidden transport
- **WHEN** an admin POSTs `{transport: "ftp"}`
- **THEN** the response is HTTP 400 with body `{"error_class": "user", "error_message": "transport must be one of stdio, sse, http"}`

### Requirement: Admin can update MCP server metadata

The system SHALL expose `PATCH /v1/mcp/servers/{id}` accepting a partial JSON body. The system MUST reject updates to `command` and `env` while the server's `status='connected'` (returns 409 Conflict). On success the system MUST update `updated_at` and return HTTP 200 with the updated resource.

#### Scenario: Update allowed-dirs while disconnected
- **WHEN** an admin PATCHes `{security_config: {"allowed_dirs": ["/new"]}}` on a server with `status='disconnected'`
- **THEN** the response is HTTP 200 with the updated resource

#### Scenario: Update command while connected
- **WHEN** an admin PATCHes `{command: "new-cmd"}` on a server with `status='connected'`
- **THEN** the response is HTTP 409 with body `{"error_class": "user", "error_message": "disconnect before modifying command/env"}`

### Requirement: Admin can delete MCP server

The system SHALL expose `DELETE /v1/mcp/servers/{id}` which MUST first check the server is not referenced by any Agent (`agents.spec.tools[]` includes a tool from this server) or Workflow (`workflows.spec.nodes[]` references this server's tools). If referenced, the endpoint MUST return HTTP 409 with a list of `{type, id, name}` of referencing entities. Otherwise the system MUST delete the row and return HTTP 204.

#### Scenario: Delete unreferenced server
- **WHEN** an admin DELETEs a server with no Agent or Workflow references
- **THEN** the row is removed and the response is HTTP 204

#### Scenario: Delete server referenced by an Agent
- **WHEN** an admin DELETEs a server referenced by Agent `paul-monthly-report`
- **THEN** the response is HTTP 409 with body `{"error_class": "user", "error_message": "server referenced", "referenced_by": [{"type": "agent", "id": "...", "name": "paul-monthly-report"}]}`

### Requirement: Frontend renders MCP server cards

The admin view `/mcp-tools` MUST render one card per registered MCP server. Each card MUST show: icon (chosen by transport), name, subtitle, status badge (green "已连接" / gray "未连接" / yellow "连接中" / red "错误"), `Server: <name> | Transport: <transport>` line, tools list (truncated to 4 with `+N more`), and action buttons (`配置` / `断开` / `连接`). Cards MUST be laid out in a responsive grid (1 col mobile, 2 col md, 3 col lg).

The view MUST be route-guarded: only users with role `mcp.admin` can see it; others get HTTP 403 from the API and the route is hidden in the nav.

#### Scenario: Three connected servers rendered
- **WHEN** an admin with `mcp.admin` role opens `/mcp-tools` and 3 servers have `status='connected'`
- **THEN** the page renders 3 cards each with green badge and the appropriate action buttons

#### Scenario: Non-admin user
- **WHEN** a user without `mcp.admin` role opens `/mcp-tools`
- **THEN** the API returns 403 and the route renders an empty-state "无权限访问"

#### Scenario: Empty registry
- **WHEN** an admin opens `/mcp-tools` and no servers are registered
- **THEN** the page renders only the dashed "+ 添加 MCP Server" placeholder card

### Requirement: Frontend form to add/edit MCP server

The admin MUST provide a modal form (opened from the "+ 添加 MCP Server" button or card "配置" action) with fields: name (text), transport (select stdio/sse/http), command (text), args (chip input), env (key-value pair editor), security_config (JSON editor for `allowed_dirs` / `allowed_domains` / `dsn`). The form MUST validate client-side (matching backend rules) and submit to `POST` or `PATCH` accordingly. On 409 (duplicate name) the form MUST highlight the name field and show the error inline.

#### Scenario: Add server form submission
- **WHEN** admin fills in the form with valid data and clicks "保存"
- **THEN** the form calls `POST /v1/mcp/servers`, closes on 201, and the new card appears in the grid

#### Scenario: Edit server form
- **WHEN** admin clicks "配置" on a `disconnected` card
- **THEN** the form opens pre-filled and the "command" / "env" fields are enabled

#### Scenario: Edit connected server
- **WHEN** admin clicks "配置" on a `connected` card
- **THEN** the form opens pre-filled but "command" / "env" fields are disabled with a tooltip "请先断开连接"

### Requirement: Database migration is reversible

The system MUST provide an Alembic migration that creates the `mcp_server_registrations` table with columns: `id` (uuid pk), `name` (text unique not null), `transport` (enum not null), `command` (text), `args` (jsonb default `[]`), `env` (jsonb default `{}`), `security_config` (jsonb default `{}`), `status` (enum default `disconnected`), `last_health_check_at` (timestamptz nullable), `last_error` (text nullable), `created_at` (timestamptz default now()), `updated_at` (timestamptz default now()). The `downgrade()` MUST drop the table.

#### Scenario: Upgrade applies
- **WHEN** `alembic upgrade head` is run
- **THEN** the table `mcp_server_registrations` exists with all listed columns and constraints

#### Scenario: Downgrade reverses
- **WHEN** `alembic downgrade -1` is run after upgrade
- **THEN** the table `mcp_server_registrations` is dropped and no other schema is affected
