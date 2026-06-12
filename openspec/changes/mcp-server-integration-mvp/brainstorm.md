<!--
Raw capture of superpowers:brainstorming output for change `mcp-server-integration-mvp`.
设计来源:eng-review 2026-06-10 锁定的 Arch #5(locked-in,不再重新讨论)。
eng-review 原始 finding(逐字引用):
> Arch #5 (P2, 7/10) — "MCP + 自定义插件" hidden scope. Resolution: MVP 包含 MCP 集成.
> 5+ core MCP servers (filesystem / fetch / postgres) in MVP scope. Avoids leo's
> enterprise-integration blocker.
-->

# Brainstorm:MCP server 集成 MVP(eng-review #5)

## 背景(来自 eng-review 报告)

eng-review 2026-06-10 锁定的 12 个工程决策中,Arch #5 明确"MVP 包含 MCP 集成"
+ 3+ core MCP server(filesystem / fetch / postgres)。MVP 不做插件市场 + 自定义
插件,只做 MCP 标准协议,让 leo 基础服务数据查询场景不被 enterprise-integration
阻塞。

仓库现状:`services/` 完全没有 MCP 实现。`.playwright-mcp/` 是 e2e test 工具,
不是 MCP server。MVP 需要从 0 写。

## 决策链(已知,user 已在 eng-review 锁定,本段不需 user 确认)

### Q1:范围边界

- **选项 A** MVP 3 server(filesystem / fetch / postgres)+ 1 wrapper service(让 agent / workflow 透明调)
- B:5+ server(filesystem / fetch / postgres + git + web-search)
- C:1 server 起步,后续追加

**选 A**(eng-review 锁定 3 个 core server)。后续 V1.0+ 扩到 5+。

### Q2:MCP 协议实现方式

- **选项 A** 自研 Python 实现 MCP stdio/SSE 协议(轻量, ~500 行)
- B:用 `mcp` PyPI 包(eng-review 提到 "use existing reference servers ... rather than reimplementing")
- C:用 LangChain MCP 适配器

**选 B**(eng-review 锁定)。用 `mcp[cli]` PyPI 包 + 现有 filesystem / fetch / postgres 参考 server 代码。

### Q3:Server 与 ChatBiz 的集成

- **选项 A** 独立 service `services/mcp/` 3 server + 1 router
- B:嵌进 `services/agent-runtime/` 作为子模块
- C:embed 进 `services/audit-and-isolation/`(LLM 调)

**选 A**。eng-review §4.3.1 提到 MCP 是 工具/扩展系统 的 §4.3.4 范畴,独立 service 边界清晰。**MCP server 调用经 audit-and-isolation egress**(eng-review #1 锁定),所以 server 仍需在 LLM 网关后面跑。

### Q4:filesystem / fetch / postgres 3 server 优先级

- eng-review 锁定顺序:**filesystem**(MVP 必备)→ **fetch**(web 数据)→ **postgres**(企业数据)
- 3 server 一起交付,不分阶段
- 测试:MCP 协议 client simulator + 真实 server 启动 + 工具调用 e2e

### Q5:失败模式与安全

- filesystem:path 越权(必须白名单目录,见 4.x 安全)
- fetch:URL 白名单(避免 SSRF 攻击)+ 响应大小限制(避免内存溢出)
- postgres:connection 加密 + 只读用户(避免误写)
- 全部经 audit-and-isolation egress(PII 扫描 + trace)

## 4 大要点(call sites / 写入 / 读取 / 容量)

### filesystem MCP server
- **协议**:stdio(MCP 默认),Tools: `read_file` / `write_file` / `list_dir` / `search`
- **安全**:白名单目录(env `MCP_FS_ALLOWED_DIRS`),chroot 模拟
- **容量**:无明确数字;由白名单目录大小决定

### fetch MCP server
- **协议**:stdio,Tools: `fetch_url` / `fetch_html` / `fetch_json`
- **安全**:URL 白名单(env `MCP_FETCH_ALLOWED_DOMAINS`),响应大小限制(env `MCP_FETCH_MAX_BYTES`,默认 1MB)
- **容量**:无明确数字;由 fetch 调用频率决定

### postgres MCP server
- **协议**:stdio,Tools: `execute_query`(只读)/ `list_tables` / `describe_table`
- **安全**:只读 PG 用户(REVOKE INSERT/UPDATE/DELETE),query timeout 默认 30s,result row limit 默认 1000
- **容量**:无明确数字;由企业 PG 数据量决定

## 设计取捨

| 取捨点 | 选 A | 选 B | 我们选 | 理由 |
|---|---|---|---|---|
| MCP 协议 | stdio | SSE over HTTP | stdio | MVP 简单,后续可加 SSE |
| Server 启动方式 | 独立进程 | 嵌入 Python 多线程 | 独立进程 | 故障隔离 |
| 调用链 | agent-runtime → audit-and-isolation → MCP server | agent-runtime → MCP server (skip gateway) | 经 audit-and-isolation | eng-review #1 egress 强制 |
| Tool schema | JSON Schema | Pydantic | JSON Schema | MCP 标准 |
| 错误处理 | MCP error code (-32602 等) | HTTP 4xx/5xx | MCP error code | MCP 协议标准 |

## 被拒方案

1. **自研 MCP 协议** —— eng-review 明确"用现有 reference server"
2. **跳过 audit-and-isolation egress** —— 违反 eng-review #1
3. **filesystem / fetch 用 docker 容器** —— MVP 阶段过重,stdin 进程足够

## 触发 wedge 场景

- **paul 财务月报**:filesystem 读 `~/reports/2024-q4.xlsx`,postgres 查 `finance.revenue_2024`
- **leo 数据查询**:postgres 查 `erp.orders` 表(只读)
- **anny 文档审核**:filesystem 读 `~/docs/contract.pdf`,fetch 拉外部 API 验证

## 跨 spec 依赖

| 后续 spec | 怎么依赖本 spec |
|---|---|
| T2 Node Contract | "工具调用"节点引用 MCP server |
| T11 4 错误边界 | MCP 失败 → runtime boundary;path 越权 → security boundary |
| (新) filesystem server 实施 spec | 继承本 spec filesystem 段 |
| (新) fetch server 实施 spec | 继承本 spec fetch 段 |
| (新) postgres server 实施 spec | 继承本 spec postgres 段 |

## Open Questions(交给 apply 阶段)

- **OQ1:** `mcp[cli]` 版本选择 → 0.5+ 还是 0.6+
- **OQ2:** postgres 只读用户密码管理 → Vault 短期 token 还是 K8s Secret
- **OQ3:** filesystem chroot 是真 chroot(`os.chroot`)还是逻辑白名单(更安全)
