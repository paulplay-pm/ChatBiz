# Tasks: mcp-server-integration-mvp

## 1. 服务骨架 + 依赖(1h,2 个 task)

- [ ] 1.1 创建 `services/mcp/` 目录结构(`pyproject.toml` + `app/` + `app/servers/` + `app/security.py` + `tests/`),`pyproject.toml` 加 `mcp[cli]>=0.5,<1.0` + `httpx` + `asyncpg` + `pyyaml` + `pydantic` + `pytest` + `pytest-asyncio` + `pytest-cov` + `ruff`
- [ ] 1.2 创建 `services/mcp/Dockerfile`(参考 audit-and-isolation 现有 Dockerfile)+ `services/mcp/README.md`

## 2. security 模块(env 变量配置 + 统一接口)(1.5h,2 个 task)

- [ ] 2.1 实现 `services/mcp/app/security.py::McpSecurityPolicy`:env 变量读取 + 路径白名单验证(`Path.resolve()` 防绕过)+ URL 域名白名单验证 + 私网 IP 拒绝
- [ ] 2.2 写 `services/mcp/tests/unit/test_security.py`:覆盖 4 个场景(路径越权 / URL 越权 / 私网 IP 拒绝 / env 未配置启动失败)

## 3. filesystem MCP server(2h,3 个 task)

- [ ] 3.1 实现 `services/mcp/servers/filesystem.py`:用 `mcp[cli]` 库,4 tools(`read_file` / `write_file` / `list_dir` / `search`),目录白名单强制,所有 path 走 `Path.resolve()` 防绕过
- [ ] 3.2 实现 filesystem server 集成 audit-and-isolation egress:每个 tool 调用后,通过 `httpx` 调 `services/audit-and-isolation/app/api/audit_archive` 写 audit log(eng-review #1 锁定)
- [ ] 3.3 写 `services/mcp/tests/unit/test_filesystem_server.py`:覆盖 4 场景(白名单内读 / 越权 raise / resolve 绕过 / 白名单未配置启动失败)+ audit 写入 mock 验证

## 4. fetch MCP server(2h,3 个 task)

- [ ] 4.1 实现 `services/mcp/servers/fetch.py`:用 `mcp[cli]` 库 + `httpx`,3 tools(`fetch_url` / `fetch_html` / `fetch_json`),URL 白名单 + 响应大小限制 + SSRF 防御
- [ ] 4.2 实现 fetch server 集成 audit-and-isolation egress(同 3.2 模式)
- [ ] 4.3 写 `services/mcp/tests/unit/test_fetch_server.py`:覆盖 4 场景(白名单内 fetch / 超大响应 raise / 私网 IP 拒绝 / 非 JSON 解析失败)+ audit mock

## 5. postgres MCP server(2h,3 个 task)

- [ ] 5.1 实现 `services/mcp/servers/postgres.py`:用 `mcp[cli]` 库 + `asyncpg`,3 tools(`execute_query` / `list_tables` / `describe_table`),只读用户 + `SET TRANSACTION READ ONLY` + statement_timeout + row limit
- [ ] 5.2 实现 postgres server 集成 audit-and-isolation egress(同 3.2 模式)
- [ ] 5.3 写 `services/mcp/tests/unit/test_postgres_server.py`:覆盖 4 场景(SELECT 成功 / INSERT 拒绝 / 超时取消 / 超行数截断)+ audit mock

## 6. router(统一入口 + 协议分发)(1h,2 个 task)

- [ ] 6.1 实现 `services/mcp/app/router.py::McpRouter`:接受 agent-runtime 调用(JSON-RPC over stdio),根据 `tool_name` 分发到对应 server,所有调用经 audit-and-isolation egress
- [ ] 6.2 写 `services/mcp/tests/integration/test_router.py`:用 `mcp.client.session` 写 client simulator,3 server 端到端调用

## 7. CI 集成(30min,2 个 task)

- [ ] 7.1 在 `services/gateway-scanner/blocklist.yaml` 加 `mcp` 注释(允许 `services/mcp/servers/*.py` 直连 LLM provider,因 server 本身就是 LLM 调用入口)
- [ ] 7.2 跑 `python -m gateway_scanner services/mcp/` 验证 exit 0

## 8. 收尾(30min,2 个 task)

- [ ] 8.1 跑 `pytest services/mcp/tests/ --cov=services/mcp/app --cov-fail-under=100` 验证 100% 覆盖
- [ ] 8.2 写 `verify.md` + `retrospective.md` + `openspec archive` 同步 spec delta

---

**总计 15 个 task**:1 骨架 + 1 security + 3 server × (2 实施 + 1 测试)= 9 + 1 router + 2 CI + 1 收尾。每个 task ≤ 2h,无超大 task。

**编码与验证配对**:
- task 2.1 ↔ 2.2
- task 3.1 ↔ 3.3
- task 4.1 ↔ 4.3
- task 5.1 ↔ 5.3
- task 6.1 ↔ 6.2
- task 8.1 ↔ 8.2(全量覆盖率 + verify + archive)

无孤儿。任务粒度全部 ≤ 2h(总预估 ~10h,3 subagent 并行可降至 ~4h wall clock)。
