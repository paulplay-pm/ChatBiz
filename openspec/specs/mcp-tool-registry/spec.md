# mcp-tool-registry Specification

## Purpose
TBD - created by archiving change sso-and-canvas-e2e-fix. Update Purpose after archive.
## Requirements
### Requirement: MCP server 统一注册表

MCP tool registry MUST 维护所有已注册 MCP server 的清单,含 `id` / `transport` / `endpoint` / `credential_ref` / `health_check_url`,暴露 `GET /api/v1/mcp/servers` 给 platform 内其他服务查询。

#### Scenario: 注册表列表 API

- **WHEN** platform 服务请求 `GET /api/v1/mcp/servers`
- **THEN** 返 `200 OK` + JSON 数组,每项含 `{id, name, transport: "stdio|http|sse", endpoint, health_status, tools_count}`
- **THEN** 包含 MVP 锁定的 3 server:filesystem / fetch / postgres

#### Scenario: server 健康检查

- **WHEN** registry 每 30s 主动 ping 每个 server 的 `health_check_url`
- **THEN** `health_status` 字段更新为 `healthy` / `degraded` / `down`
- **THEN** 连续 3 次 ping 失败后,标记 `down` 并触发 `alert_event` 写 audit-and-isolation log

### Requirement: 插件加载失败降级

当 MCP server 加载失败或返回错误,workflow runtime MUST 降级到 mock 响应而不是中断整个 workflow,降级事件写入 audit-and-isolation log。

#### Scenario: 工具调用失败降级

- **WHEN** workflow 节点调用 MCP tool `<tool_name>` 但 registry 显示该 tool 所属 server `health_status = down`
- **THEN** 节点不抛异常,使用 mock 响应 `{"degraded":true,"reason":"mcp_server_down","mock_output":{...}}` 继续
- **THEN** 写 audit-and-isolation log: `{event_type: "mcp_degraded", workflow_id, node_id, tool_name, server_id, mock_strategy}`

#### Scenario: server 恢复后切回真调用

- **WHEN** degraded server 恢复 `health_status = healthy`
- **THEN** 后续 tool 调用自动切回真实 server,不再走 mock

