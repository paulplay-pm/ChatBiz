# mcp-server-tool-discovery

**Frontend Scope: 含前端**（卡片副标题 "工具: ..." + 配置弹窗的 tools 列表）

**Impact**（被谁消费）：
- 被 admin 在 admin-web 卡片副标题消费（直观看到 server 暴露哪些 tool）
- 被配置弹窗的 "工具清单" 区域消费
- 未来被 Agent 编辑器消费（"勾选哪些 tool 给 Agent"）

## ADDED Requirements

### Requirement: Admin can list tools exposed by a MCP server

The system SHALL expose `GET /v1/mcp/servers/{id}/tools` returning a JSON array of `{name, description, input_schema}` for every tool the target server exposes. The endpoint MUST internally call the server's `HANDLER` to enumerate tools and MUST return HTTP 200 with the array, or HTTP 503 if the HANDLER is unreachable. The endpoint MUST require `mcp.admin` role.

The response MUST be cached in Redis with key `mcp:tools:{id}` and TTL 60s (`MCP_TOOL_CACHE_TTL`). The cache MUST be invalidated on `connect` success.

#### Scenario: Filesystem server lists 4 tools
- **WHEN** an admin GETs `/v1/mcp/servers/{id}/tools` for a `filesystem` server with `MCP_FS_ALLOWED_DIRS=/data`
- **THEN** the response is HTTP 200 with `[{"name": "fs_read_file", ...}, {"name": "fs_write_file", ...}, {"name": "fs_list_dir", ...}, {"name": "fs_search", ...}]`

#### Scenario: Server with missing env (filesystem, no MCP_FS_ALLOWED_DIRS)
- **WHEN** an admin GETs `/v1/mcp/servers/{id}/tools` for a `filesystem` server whose `MCP_FS_ALLOWED_DIRS` is unset
- **THEN** the response is HTTP 503 with body `{"error_class": "runtime", "error_message": "MCP_FS_ALLOWED_DIRS not configured"}`

#### Scenario: Cache hit
- **WHEN** the same admin GETs `/v1/mcp/servers/{id}/tools` twice within 60s
- **THEN** the second response is served from Redis cache (response time < 50ms)

### Requirement: Frontend shows truncated tools list in card

The admin-web card MUST show up to 4 tool names in the "工具:" line, comma-separated. If there are more than 4 tools, the card MUST append `+N more` (e.g. "工具: read_file, write_file, list_dir, search +2 more"). The full tool list MUST be shown in the configuration modal.

#### Scenario: Server with 4 tools
- **WHEN** a `filesystem` server card is rendered with 4 tools
- **THEN** the "工具:" line shows "工具: read_file, write_file, list_dir, search" (no "+N more")

#### Scenario: Server with 6 tools
- **WHEN** a `browser` server card is rendered with 6 tools (navigate, click, type, screenshot, extract, scroll)
- **THEN** the "工具:" line shows "工具: navigate, click, type, screenshot +2 more"

### Requirement: Configuration modal shows full tool list with descriptions

The admin-web configuration modal MUST render a "工具清单" section listing every tool with its name and a one-line description. The list MUST be loaded lazily on modal open (not on card render) and MUST show a loading spinner while `GET /v1/mcp/servers/{id}/tools` is in flight. If the API returns 503, the section MUST show "工具发现失败：<error_message>" in red.

#### Scenario: Modal opens with 4 tools
- **WHEN** admin opens the configuration modal for a `filesystem` server
- **THEN** the "工具清单" section lists 4 tools each with name and description

#### Scenario: Modal opens with 503 error
- **WHEN** admin opens the configuration modal for a server whose HANDLER is unreachable
- **THEN** the "工具清单" section shows the red error message
