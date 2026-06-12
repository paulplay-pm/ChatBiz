# Brainstorm — mcp-server-management-ui

> **Raw capture**：本档原样捕捉 superpowers:brainstorming 的对话链产物，**不**强制结构。
> design.md 已经从本档抽取并重组为结构化设计文件（Context / Goals / Decisions / Risks / Migration）——本档与 design.md 互补，**不**互相复制。
> 来源：原型 `docs/prototype.html:4112-4164`（MCP 工具配置页）+ eng-review Arch #5 + PRD §1162 V1.0 P1 + 用户输入 "mcp-server-management-ui 参考 prototype.html 的 MCP 工具页面"。

---

## 背景

`mcp-server-integration-mvp`（archive 2026-06-11）落地了 `services/mcp/` 容器：3 server（filesystem / fetch / postgres）+ `McpRouter` + HTTP/SSE 入口（端口 8004）+ 100% 测试覆盖 + 走 audit-and-isolation egress。但**没有管理面**——admin 只能 SSH 进容器改 env + `docker compose restart`。

eng-review 12 决策里：
- Arch #5：MVP 包含 MCP 集成（已落地）
- Quality #1：UI / StateGraph / schema / validator 4 份代码必须从 1 份生成（针对 12 节点场景，但精神一致）
- Quality #2：状态双层 PG (source of truth) + Redis (实时缓存)
- Test #2 critical path #4：**插件加载降级**必须 100% 覆盖
- PRD §1162 / §1706：MCP 工具配置页是 V1.0 P1

**必中 wedge**：admin / paul / leo / anny 能在 admin 直接增删 / 启停 MCP server，**不**走 SSH 改 env。

---

## 决策链

### Q1：管理面挂在哪里？

**A. 现有 `services/mcp` 容器内挂 REST**（已选）
- 复用 `app/router.py` 的 `McpRouter`、`app/security.py` 的 `McpSecurityPolicy`、3 个 server 的 `HANDLER`
- 新增 `app/registry.py`（CRUD + 状态机）+ `app/api.py`（Starlette 路由）
- 容器端口 8004 不变

**B. 开新 `services/mcp-admin/` 容器**
- 单独占端口、单独 deploy、独立 health check
- 拒绝理由：违反 eng-review Arch #1 "egress 强制点"（admin 操作只是 CRUD 元数据，**真正**的 LLM/MCP 出口在 `services/mcp` 本身）；多一层网络 hop；MVP 阶段没人力维护两个 service

**C. REST 端点挂到 admin 的 BFF 进程**
- admin 是 Vite/React，没有 Python 进程
- 要么引 Python BFF（= 选 B），要么直接调 audit-and-isolation（强耦合，破坏 mcp 单 service 自洽）
- 拒绝

→ **锁定 A**

### Q2：状态机持久化用 PG 还是 Redis？

**A. PG 唯一真理源，Redis 仅做探活 30s 缓存**（已选）
- 前端 GET 走 API 拿 PG 实时值（不读 Redis）
- Redis 仅做"避免短时间内重复探活"去重

**B. Redis 做实时状态，PG 做"最终一致性"落盘**
- 拒绝：eng-review Quality #2 明文 PG = source of truth
- 且 connect/disconnect 走审计（写 PG），写两边会让 audit 链对不上

**C. 不引 Redis，PG 读多写少扛得住**
- 可接受但失去"探活 30s 缓存"的 Perf #1 价值
- 拒绝（不接受 Perf 倒退）

→ **锁定 A**

### Q3：探活怎么做？spawn 子进程还是调 HANDLER？

**A. 调 `servers/<name>/HANDLER`（单 server 隔离）**（已选）
- 复用 `mcp-server-integration-mvp` 的 HANDLER
- 由 HANDLER 内部判断 env 是否配置（filesystem 缺 `MCP_FS_ALLOWED_DIRS` 抛 `McpSecurityError`）
- 快（毫秒级），覆盖"配置正确性"，**不**覆盖"子进程能起来"

**B. 真 `stdio_server` spawn**
- 拒绝：admin 视角的"能连"应该是配置正确就够了
- 真 spawn 留到 `apply` 后第一次 dispatch 真实调 tool 时做

**C. HTTP 探活**
- MCP 不规定，统一走 A

→ **锁定 A**

### Q4：UI / API / 审计 / DB 4 处 schema 怎么生成？

**A. Python 侧 1 份 TypedDict 生成 4 处**（已选）
- `class McpServerRegistration(TypedDict)` 在 `services/mcp/app/registry_types.py`
- 导出 4 个函数 `to_pydantic()` / `to_sqlalchemy_column_spec()` / `to_audit_payload()` / `to_frontend_json()`
- 精神同 eng-review Quality #1 "4 份代码从 1 份生成"

**B. 引 Pydantic + 自动 codegen 到 TS**
- 拒绝：admin 仓库结构未定（monorepo vs submodule），跨语言 codegen 工具要等
- 短期手工对齐 + 单元测试覆盖

**C. 每处独立定义**
- 拒绝：违反 eng-review Quality #1 精神，4 处漂移风险

→ **锁定 A**

### Q5：HTTP 框架用 Starlette 还是 FastAPI？

**A. 继续 Starlette Route**（已选）
- `services/mcp/app/main.py` 已用 Starlette 0.40+
- 30 行内 5 个 REST 端点 + 手写 OpenAPI 文档够用

**B. 引 FastAPI**
- 拒绝：eng-review §4.4 不要求 admin API 必须 FastAPI
- 多一个 ASGI 框架、更多 import、更多学习成本

**C. 纯 ASGI 函数**
- 拒绝：可读性差

→ **锁定 A**

### Q6：前端状态实时刷新用 WebSocket、SSE、还是轮询？

**A. SWR 5s 轮询**（已选）
- admin 已有 React + Hooks 栈
- 引入 `swr` 做 `revalidateInterval: 5000`
- 简单，CDN 友好

**B. WebSocket**
- 拒绝：admin 没有 WS gateway，5s 轮询延迟对 admin 视角可接受

**C. SSE**
- 拒绝：admin 不引 EventSource 抽象

→ **锁定 A**

### Q7：MCP server 凭据（env / command）怎么存？

**A. 明文 JSONB 存 PG，列级 `pgcrypto` 加密**（已选）
- V1.5 接 secret store（HashiCorp Vault 或类似）
- 本 change 在 spec 顶部声明 `[FUTURE-IMPLEMENTATION]`

**B. 现在就接 HashiCorp Vault**
- 拒绝：V1.0 P1 没人力

**C. 完全明文不加密**
- 拒绝：违反"内部数据不出域"合规红线

→ **锁定 A，但需 FUTURE-IMPLEMENTATION 标注**

### Q8：4 错误边界怎么映射 HTTP 状态码？

**A. 7-class `app/security.py` 错误 → 4xx/5xx 显式映射**（已选）

| 错误类 | HTTP | 触发场景 |
|---|---|---|
| `McpSecurityError` | 403 | 未授权 modify / 路径越界 / 凭据错 |
| `McpUserError` (Pydantic ValidationError) | 400 | 参数不全、name 重复、JSON 解析失败 |
| `McpResponseTooLargeError` (runtime) | 502 | 探活时 router 返 5xx / 限额 |
| `McpUnknownToolError` (runtime) | 500 | 内部 bug（不该发生） |
| `RuntimeError` (audit-and-isolation fail-open 已吞) | 200 + 字段 `audit_status: fail_open` | 探活成功但审计失败 |

**B. 全部转 500**
- 拒绝：违反 eng-review Quality #3 "4 错误边界"

→ **锁定 A**

### Q9：admin 仓库结构是 monorepo 还是 submodule？

**A. 未知，需前置门**
- 仓库根当时**没有** `web/admin/` 目录（CLAUDE.md 写"0 行源代码"）
- prototype.html 是 `docs/` 下的 HTML
- 决策点：本 change 在 tasks.md 写"前置 0.1 = 确认 admin 仓库路径"
- 否则 spec 标 [BLOCKED]

**B. 现在就假设 monorepo**
- 拒绝：可能错（如果团队决定 submodule 方案，本 change 的 `web/admin/` 提交会被 revert）

→ **锁定 A（前置门 0.1）**

### Q10：审计面板要不要做？

**A. N/A — UI 由后续 `audit-and-isolation-admin-ui` change 落地**（已选）
- 本 change 仅生成 audit 记录，不展示
- V1.5 之后做审计面板

**B. 本 change 一起做审计面板**
- 拒绝：scope 蔓延；审计面板是 audit-and-isolation service 的事，不是 mcp 的事

→ **锁定 A，`mcp-server-audit-trail` capability 顶部声明 `Frontend Scope: N/A`**

---

## 设计 trade-off

| Trade-off | 选了 | 拒绝的另一极 |
|---|---|---|
| **单 service 简化 vs 多 service 解耦** | 现有 mcp 容器内挂 REST（Q1-A） | 新开 mcp-admin service（Q1-B） |
| **PG 真理源 vs Redis 实时** | PG source of truth + Redis 30s 缓存（Q2-A） | Redis 实时 + PG 落盘（Q2-B） |
| **配置正确性探活 vs 真 spawn 探活** | HANDLER 调用（Q3-A） | 真 stdio_server spawn（Q3-B） |
| **1 份 Python schema vs 全 codegen** | 1 份 + 手工对齐 TS（Q4-A） | Pydantic → TS 自动 codegen（Q4-B） |
| **Starlette vs FastAPI** | Starlette（Q5-A） | FastAPI（Q5-B） |
| **轮询 vs 推送** | SWR 5s 轮询（Q6-A） | WebSocket / SSE（Q6-B/C） |
| **明文加密 vs Vault** | 明文 + pgcrypto + FUTURE tag（Q7-A） | 立即接 Vault（Q7-B） |

---

## Open Questions（仍未决）

- OQ1：admin 是 monorepo 还是 submodule？→ 任务 0.1 前置门验
- OQ2：MCP server 注册元数据是否要 export 给其他 service（agent-runtime 拿 `pg_server_registrations` 决定可调 tool）？→ 当前 REST 暴露，未来 V1.5 走 `pg_notify` 推送
- OQ3：`mcp-server-audit-trail` capability UI = N/A，但**要不要**在 admin 加个"操作历史"标签？→ 当前 N/A，未来 V1.5 走 `audit-and-isolation-admin-ui`
- OQ4：admin 误删 MCP server 时的引用检查，扫 `agents.spec.tools[]` + `workflows.spec.nodes[]` 范围多大？→ 当前 stub，未来 agent / workflow service 落地后补真实扫

---

## 必中 wedge 校验（brainstorming 规则：3 个具名用户的工作流必须在视图中）

| 用户 | 触点 | 本 change 提供 |
|---|---|---|
| **paul**（财务运营） | 想让 Agent 自动读 /data 下的财务月报 | 能注册 filesystem MCP server + 把 `MCP_FS_ALLOWED_DIRS=/data` 配好 + 一次性"连接"看状态 |
| **leo**（基础服务） | 想让 Agent 查公司 PG 库 | 能注册 postgres MCP server + 配 DSN + 看探活是否过 |
| **anny**（增值服务） | 想让 Agent 浏览外网 + 抽数据 | 能注册 fetch MCP server + 配 `MCP_FETCH_ALLOWED_DOMAINS` + 启停控制 |

3 个用户**不**走 SSH 改 env，全部走本 change 提供的 UI。✓

---

## eng-review 决策引用（brainstorming 规则：触及 12 锁定决策时直接引用 finding 编号，不重提）

- **[ENG-Arch#1]** 数据隔离网关 = egress 强制点（Q1 拒绝 B、Q2 拒绝 B）
- **[ENG-Arch#5]** MVP 包含 MCP 集成（背景、Q1-A 复用）
- **[ENG-Quality#1]** 4 份代码从 1 份生成（Q4-A 精神一致）
- **[ENG-Quality#2]** PG source of truth + Redis 实时（Q2-A）
- **[ENG-Quality#3]** 4 错误边界（Q8 映射表）
- **[ENG-Test#2]** 4 critical path 100% 覆盖：本 change 直接覆盖 #4 插件加载降级（spec Requirement `Critical path "插件加载降级" is fully covered`）
- **[ENG-Perf#1]** 探活 30s 缓存（Q2-A + Q6-A）

未触发的：Arch #2（12 节点 Node Contract）、Arch #3（4 层记忆）、Arch #4（Workflow+Chatflow StateGraph）、Arch #6（人工审批）、Quality #1（节点 codegen）、Test #1（3 层测试金字塔 + LLM eval，部分触发）、Perf #2（5 存储量预估）——这些属于其他 change 的 scope。
