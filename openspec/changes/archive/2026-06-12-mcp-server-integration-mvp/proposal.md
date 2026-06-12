## Why

eng-review 2026-06-10 锁定的 12 个工程决策中,Arch #5 明确"MVP 包含 MCP 集成"+ 3+ core MCP server(filesystem / fetch / postgres)。MVP 不做插件市场 + 自定义插件,只做 MCP 标准协议。仓库 `services/` 完全没有 MCP 实现,`.playwright-mcp/` 是 e2e test 工具而非 MCP server。本次 change **从 0 写** `services/mcp/` 独立 service,3 server + 1 router,所有调用经 `services/audit-and-isolation/` egress(eng-review #1 锁定)。MVP 完成后 leo 基础服务数据查询场景不被 enterprise-integration 阻塞。

## What Changes

**新增 service**(eng-review Arch #5 锁定)
- From:`services/` 完全没有 MCP 实现
- To:新增 `services/mcp/`(Python 3.12 + `mcp[cli]` 包),3 server(filesystem / fetch / postgres)+ 1 router,stdio 协议
- Reason:eng-review Arch #5 锁定 + leo enterprise-integration 阻塞
- Impact:新增 `services/mcp/`(~10 文件)+ 3 server 测试

**egress 强制**(eng-review #1 锁定)
- From:MCP server 直连 LLM provider(违反 eng-review #1)
- To:MCP server 调用经 `services/audit-and-isolation/` 走 PII 扫描 + trace_id 关联 + 审计
- Reason:eng-review #1 egress 强制
- Impact:MCP server 在 audit-and-isolation 后跑,**不**直连 LLM

**安全**
- filesystem:目录白名单(env `MCP_FS_ALLOWED_DIRS`),chroot 模拟
- fetch:URL 白名单(env `MCP_FETCH_ALLOWED_DOMAINS`),响应大小限制(env `MCP_FETCH_MAX_BYTES`,默认 1MB)
- postgres:只读 PG 用户(REVOKE INSERT/UPDATE/DELETE),query timeout 30s,result row limit 1000

**CI**
- 新增 `services/mcp/tests/` 3 server 单元测试 + MCP 协议 client simulator 集成测试
- 跟 `services/gateway-scanner/` 集成:scanner 扫 `services/mcp/` 必须 0 violation

## Capabilities

### New Capabilities

- `mcp-filesystem-server`:filesystem MCP server,提供 `read_file` / `write_file` / `list_dir` / `search` tools,目录白名单
- `mcp-fetch-server`:fetch MCP server,提供 `fetch_url` / `fetch_html` / `fetch_json` tools,URL 白名单 + 响应大小限制
- `mcp-postgres-server`:postgres MCP server,提供 `execute_query`(只读)/ `list_tables` / `describe_table` tools,只读 PG 用户
- `mcp-router`:MCP server router,接受 agent-runtime 调用,转发到对应 server,经 audit-and-isolation egress
- `mcp-security-policy`:3 server 的安全策略统一接口(env 变量白名单 + audit log)

### Modified Capabilities

无。本 spec 是新增。

## Impact

- **新增代码**:
  - `services/mcp/`(Python 3.12 + FastAPI,~10 文件)
  - `services/mcp/servers/{filesystem,fetch,postgres}.py` 3 server
  - `services/mcp/router.py`
  - `services/mcp/security.py` 统一安全策略
  - `services/mcp/tests/` 3 server 测试 + protocol simulator
  - `services/mcp/Dockerfile`
- **CI 变更**:GitHub Actions 新增 `mcp-server-tests` job
- **egress 影响**:3 server 调用经 `services/audit-and-isolation/app/llm/client.py`(eng-review #1 锁定 egress)
- **依赖**:`mcp[cli]>=0.5` + `httpx`(fetch)+ `asyncpg`(postgres)+ `pyyaml`(安全策略)
- **[FUTURE-IMPLEMENTATION]** 5+ server(git / web-search 等)留 V1.0+ 扩
- **[FUTURE-IMPLEMENTATION]** SSE over HTTP 协议留 V1.0+(MVP 用 stdio)
- **[FUTURE-IMPLEMENTATION]** 插件市场 + 自定义插件 eng-review 明确"out of scope"

## Non-goals

- **不**做插件市场 + 自定义插件(eng-review 明确 out of scope)
- **不**做 5+ server(MVP 只 3 个)
- **不**用 SSE over HTTP 协议(MVP stdio 够用)
- **不**绕过 `services/audit-and-isolation/` egress(eng-review #1 锁定)
- **不**实现 MCP server 写权限(只读 / 受限)
- **不**实现缓存层(MCP 协议层无状态,缓存由 audit-and-isolation perf contract 实现)
- **不**动 12 个 eng-review 决策中的任何其他 11 项
