# mcp-filesystem-server Specification

## Purpose
TBD - created by archiving change mcp-server-integration-mvp. Update Purpose after archive.
## Requirements
### Requirement: filesystem MCP server MUST 提供 4 个 tools

`services/mcp/servers/filesystem.py` MUST 是独立 MCP server,用 `mcp[cli]` 库实现 stdio 协议,提供 4 个 tools:`read_file` / `write_file` / `list_dir` / `search`。每个 tool 接受 JSON Schema 描述的参数,返回 dict。

#### Scenario: read_file 成功
- **WHEN** 调用方传 `{"path": "<file under MCP_FS_ALLOWED_DIRS>"}` 给 `read_file` tool
- **THEN** filesystem server MUST 返回文件内容 + 调用经 `services/audit-and-isolation/app/llm/client.py`(eng-review #1 egress)+ PII 扫描

#### Scenario: read_file 越权
- **WHEN** 调用方传 `{"path": "/etc/passwd"}`(不在 MCP_FS_ALLOWED_DIRS)给 `read_file` tool
- **THEN** filesystem server MUST raise `McpSecurityError` + 错误响应体 `{error_class: "security", error_message: "path not in allowed dirs"}`

#### Scenario: write_file 落 audit
- **WHEN** 调用方传 `{"path": "<allowed>", "content": "..."}` 给 `write_file` tool
- **THEN** filesystem server MUST 写文件 + 写 audit log(`audit-and-isolation` `audit_log` 表,trace_id 关联)

### Requirement: filesystem server MUST 强制目录白名单(chroot 模拟)

filesystem server 启动时 MUST 读 `MCP_FS_ALLOWED_DIRS` env 变量(逗号分隔路径列表,如 `/home/paul/reports,/home/leo/data`)。所有 path 参数 MUST resolve 后在该白名单内,否则 raise `McpSecurityError`。

#### Scenario: 白名单配置
- **WHEN** 启动 filesystem server with `MCP_FS_ALLOWED_DIRS=/home/paul/reports`
- **THEN** server MUST 仅允许 read/write `/home/paul/reports/*` 与子目录路径

#### Scenario: 路径解析绕过
- **WHEN** 调用方传 `{"path": "/home/paul/reports/../../etc/passwd"}`
- **THEN** filesystem server MUST resolve 真实路径(用 `Path.resolve()`)+ 拒绝(不在白名单内)

#### Scenario: 白名单未配置
- **WHEN** 启动 filesystem server 无 `MCP_FS_ALLOWED_DIRS` env
- **THEN** server MUST 启动失败 + 明确错误(不允许"无白名单 = 允许所有")

