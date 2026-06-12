# mcp-postgres-server Specification

## Purpose
TBD - created by archiving change mcp-server-integration-mvp. Update Purpose after archive.
## Requirements
### Requirement: postgres MCP server MUST 提供 3 个 tools(只读)

`services/mcp/servers/postgres.py` MUST 是独立 MCP server,用 `mcp[cli]` 库实现 stdio 协议,提供 3 个 tools:`execute_query`(SELECT only)/ `list_tables`(列当前 schema 所有表)/ `describe_table`(列某表 schema)。

#### Scenario: execute_query SELECT
- **WHEN** 调用方传 `{"sql": "SELECT id, name FROM users WHERE active = true"}` 给 `execute_query` tool
- **THEN** postgres server MUST 跑该查询 + 返回 rows + 调用经 `services/audit-and-isolation/app/llm/client.py` egress + PII 扫描 + audit log

#### Scenario: execute_query INSERT
- **WHEN** 调用方传 `{"sql": "INSERT INTO users (name) VALUES ('hacker')"}` 给 `execute_query` tool
- **THEN** postgres server MUST raise `McpSecurityError` + 错误响应体 `{error_class: "security", error_message: "INSERT not allowed (read-only user)"}`(PG 用户 REVOKE INSERT/UPDATE/DELETE)

#### Scenario: execute_query 超时
- **WHEN** 查询运行 > 30s(`MCP_PG_QUERY_TIMEOUT` env,默认 30s)
- **THEN** postgres server MUST 取消查询 + raise `McpTimeoutError` + 错误响应体

#### Scenario: execute_query 超行数
- **WHEN** 结果集 > 1000 行(`MCP_PG_MAX_ROWS` env,默认 1000)
- **THEN** postgres server MUST 截断结果 + 响应体含 `truncated: true, total_rows: <N>`

### Requirement: postgres server MUST 用只读 PG 用户

postgres server 启动时 MUST 用专用只读 PG 用户(env `MCP_PG_READONLY_USER` + `MCP_PG_READONLY_PASSWORD`)。应用层必须在 connect 时额外执行 `SET TRANSACTION READ ONLY` + `SET statement_timeout = '30s'`。REVOKE INSERT/UPDATE/DELETE 必须在 DB 端配置(不在 server 代码)。

#### Scenario: 只读用户配置
- **WHEN** 启动 postgres server with `MCP_PG_READONLY_USER=mcp_reader`
- **THEN** server MUST 用该用户 connect + DB 端必须已 `REVOKE INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM mcp_reader`

#### Scenario: 用户未配置
- **WHEN** 启动 postgres server 无 `MCP_PG_READONLY_USER` env
- **THEN** server MUST 启动失败(不允许"无只读用户 = 超级用户")

