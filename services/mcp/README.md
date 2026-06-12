# ChatBiz MCP Server Integration

`services/mcp/` 独立 Python 3.12 service,eng-review Arch #5 锁定的 MCP 集成 MVP。

## 职责

落地 3 个 MCP server(filesystem / fetch / postgres)+ 1 个统一 router + 1 个 security 策略模块,所有调用经 `services/audit-and-isolation/` egress(eng-review #1 锁定)。

## 3 server 概览

| Server | tools | 安全策略 |
|---|---|---|
| filesystem | `read_file` / `write_file` / `list_dir` / `search` | `MCP_FS_ALLOWED_DIRS` 目录白名单 + `Path.resolve()` 防 `../` 绕过 |
| fetch | `fetch_url` / `fetch_html` / `fetch_json` | `MCP_FETCH_ALLOWED_DOMAINS` URL 白名单 + 拒绝私网 IP(`127.0.0.0/8` / `10.0.0.0/8` / `172.16.0.0/12` / `192.168.0.0/16` / `169.254.0.0/16`)+ `MCP_FETCH_MAX_BYTES`(默认 1MB)响应大小限制 |
| postgres | `execute_query` / `list_tables` / `describe_table` | 只读 PG 用户(`MCP_PG_READONLY_USER` / `MCP_PG_READONLY_PASSWORD`)+ `SET TRANSACTION READ ONLY` + `MCP_PG_QUERY_TIMEOUT`(默认 30s)+ `MCP_PG_MAX_ROWS`(默认 1000) |

## 安全策略(`app/security.py`)

`McpSecurityPolicy` 统一 env 变量入口:

- `check_path(path) -> None` —— 路径在 `MCP_FS_ALLOWED_DIRS` 内
- `check_url(url) -> None` —— 域名在 `MCP_FETCH_ALLOWED_DOMAINS` 内 + 拒绝私网 IP
- `validate_config() -> None` —— 启动时强制所有必需 env 变量已设置

3 server 各自启动时调 `validate_config()`,fail-loud,不允许"无白名单 = 允许所有"。

## Router(`app/router.py`)

`McpRouter` 通过 stdio JSON-RPC 接收 agent-runtime 调用,根据 `tool_name` 前缀分发给对应 server,所有调用经 audit-and-isolation egress(`httpx` 调 `/v1/audit/archive` 写 audit log)。

## 测试

```bash
cd services/mcp
pip install -e ".[dev]"
pytest tests/ --cov=app --cov-fail-under=100
```

100% 覆盖率强制(沿用 `services/audit-and-isolation/pyproject.toml` 的 `--cov-fail-under=100`)。

## 开发约束

- Python 3.12(本机 `conda activate chatbiz`)
- 100% 测试覆盖率
- ruff lint 无 error
- 不直接 import LLM provider SDK(server 本身就是 LLM 调用入口)