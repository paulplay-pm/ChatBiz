# mcp-fetch-server Specification

## Purpose
TBD - created by archiving change mcp-server-integration-mvp. Update Purpose after archive.
## Requirements
### Requirement: fetch MCP server MUST 提供 3 个 tools

`services/mcp/servers/fetch.py` MUST 是独立 MCP server,用 `mcp[cli]` 库实现 stdio 协议,提供 3 个 tools:`fetch_url`(GET 任意 URL,返回 body + status)/ `fetch_html`(GET + parse HTML 提取 main text)/ `fetch_json`(GET + parse JSON 返回 dict)。

#### Scenario: fetch_url 成功
- **WHEN** 调用方传 `{"url": "https://qyapi.weixin.qq.com/..."}` 给 `fetch_url` tool
- **THEN** fetch server MUST GET 该 URL + 响应体含 status + body + 调用经 `services/audit-and-isolation/app/llm/client.py` egress + PII 扫描

#### Scenario: fetch_url 超大响应
- **WHEN** 响应体 > `MCP_FETCH_MAX_BYTES`(默认 1MB)
- **THEN** fetch server MUST raise `McpResponseTooLargeError` + 错误响应体 `{error_class: "runtime", error_message: "response exceeds 1MB limit"}`

#### Scenario: fetch_json 解析失败
- **WHEN** 响应不是合法 JSON
- **THEN** fetch server MUST raise `McpParseError` + 错误响应体

### Requirement: fetch server MUST 强制 URL 白名单 + SSRF 防御

fetch server 启动时 MUST 读 `MCP_FETCH_ALLOWED_DOMAINS` env 变量(逗号分隔域名列表,如 `qyapi.weixin.qq.com,api.deepseek.com`)。所有 URL MUST resolve 域名在该白名单内,且 MUST 拒绝私网 IP(`127.0.0.0/8` / `10.0.0.0/8` / `172.16.0.0/12` / `192.168.0.0/16` / `169.254.0.0/16`)防 SSRF。

#### Scenario: 白名单配置
- **WHEN** 启动 fetch server with `MCP_FETCH_ALLOWED_DOMAINS=qyapi.weixin.qq.com`
- **THEN** server MUST 仅允许 fetch 该域名 + 子域名

#### Scenario: SSRF 攻击
- **WHEN** 调用方传 `{"url": "https://api.example.com/redirect?to=http://127.0.0.1:8080/admin"}`
- **THEN** fetch server MUST 拒绝(目标域名不在白名单)

#### Scenario: 白名单未配置
- **WHEN** 启动 fetch server 无 `MCP_FETCH_ALLOWED_DOMAINS` env
- **THEN** server MUST 启动失败(不允许"无白名单 = 允许所有")

