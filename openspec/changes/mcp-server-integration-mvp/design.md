# Design:MCP server 集成 MVP(eng-review Arch #5)

## Context

eng-review 2026-06-10 锁定的 12 个工程决策中,Arch #5 明确"MVP 包含 MCP 集成"+ 3+ core MCP server(filesystem / fetch / postgres)。仓库现状:`services/` 完全没有 MCP 实现。MVP 不做插件市场 + 自定义插件(eng-review 明确 out of scope),只做 MCP 标准协议。本次 change 落地 `services/mcp/` 独立 service + 3 server + 1 router + 1 security 模块,所有调用经 `services/audit-and-isolation/` egress(eng-review #1 锁定)。

仓库 0 行代码起步,本 spec 落地后约 1500-2500 行 Python(3 server + router + security + tests)。

## Goals

- **G1:** `services/mcp/` 独立 service,3 server + 1 router + 1 security 模块
- **G2:** 3 server 各自覆盖 filesystem / fetch / postgres 6+ tools
- **G3:** 全程经 `services/audit-and-isolation/` egress(eng-review #1 锁定)
- **G4:** 3 server 各自安全策略(目录白名单 / URL 白名单 + 响应大小限制 / 只读 PG 用户)
- **G5:** 100% 测试覆盖率(沿用 `services/audit-and-isolation/pyproject.toml` 的 `--cov-fail-under=100`)
- **G6:** MCP 协议 client simulator 测试(eng-review 提到"用现有 reference servers",本 spec 用 `mcp[cli]` PyPI 包 + `mcp.client.session` 写测试)

## Decisions

| ID | 决策 | 出处 |
|---|---|---|
| D1 | 3 server = filesystem / fetch / postgres(eng-review 锁定) | eng-review Arch #5 |
| D2 | MCP 协议 = stdio(eng-review 锁定 MVP 简单) | eng-review Arch #5 |
| D3 | 用 `mcp[cli]>=0.5` PyPI 包(eng-review "use existing reference servers") | eng-review Arch #5 |
| D4 | `services/mcp/` 独立 service,不嵌进 agent-runtime | eng-review §4.3.4 工具/扩展系统 范畴 |
| D5 | 全部调用经 `services/audit-and-isolation/app/llm/client.py`(eng-review #1 egress) | eng-review #1 |
| D6 | filesystem:目录白名单(`MCP_FS_ALLOWED_DIRS` env),chroot 模拟(逻辑白名单) | 安全 |
| D7 | fetch:URL 白名单(`MCP_FETCH_ALLOWED_DOMAINS` env),响应大小限制(`MCP_FETCH_MAX_BYTES`,默认 1MB) | 安全 |
| D8 | postgres:只读 PG 用户(REVOKE INSERT/UPDATE/DELETE),query timeout 30s,result row limit 1000 | 安全 |
| D9 | security 统一接口 `McpSecurityPolicy`,env 变量配置 | 设计 |
| D10 | 测试用 `mcp.client.session` 写 client simulator(不引 docker testcontainer) | 测试 |

## 与 source of truth 的对应关系

- `services/audit-and-isolation/` —— 引用(eng-review #1 egress 强制)
- eng-review Arch #5 —— 本 spec 是它锁定的 MCP 集成落地
- `mcp[cli]` PyPI —— 引用(eng-review 提到用现有 reference server)
- `docs/architecture.md` §4.3.4 工具与扩展系统 —— 引用(MCP 是其子集)
- `docs/architecture.md` §4.3.Y PII 规则集 —— 引用(document 上传 PII 扫描)

## Risks

- **R1:** `mcp[cli]` PyPI 包版本兼容 —— 缓解:锁 `mcp>=0.5,<1.0`
- **R2:** filesystem chroot 逻辑白名单 vs 真 chroot —— 缓解:用逻辑白名单(MVP,留真 chroot V1.0+)
- **R3:** fetch SSRF 攻击 —— 缓解:URL 白名单 + 私网 IP 拒绝(`127.0.0.1` / `10.0.0.0/8` / `172.16.0.0/12` / `192.168.0.0/16`)
- **R4:** postgres 误写 —— 缓解:REVOKE INSERT/UPDATE/DELETE + query timeout + row limit
- **R5:** MCP server 调用不经 audit-and-isolation egress —— 缓解:D5 强制 + test 验证调用栈
- **R6:** MCP 协议 stdio 进程间通信复杂度 —— 缓解:用 `mcp[cli]` 库封装,不自己实现 stdio 协议

## 跨 spec 依赖图

```
T8 (本 spec) ─┬─→ T2 Node Contract "工具调用"节点引用 MCP server
              ├─→ T11 4 错误边界 MCP 失败 → runtime boundary;path 越权 → security boundary
              └─→ (V1.0+) SSE over HTTP 协议 + 5+ server(git / web-search 等)
```

## Migration

不适用。仓库 0 行 MCP 代码,从 0 写。

## Open Questions(交给 apply 阶段)

- **OQ1:** `mcp[cli]` 版本锁 vs latest —— 决定:`>=0.5,<1.0`
- **OQ2:** postgres 只读用户密码管理 —— 决定:env 变量(MVP,K8s Secret 后续)
- **OQ3:** filesystem chroot 逻辑白名单 vs 真 chroot —— 决定:逻辑白名单
- **OQ4:** 3 subagent 各自独立 worktree 实施还是串行 —— 决定:并行(独立目录,无冲突)
