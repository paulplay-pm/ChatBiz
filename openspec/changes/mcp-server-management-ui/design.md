# mcp-server-management-ui — Design

## Context

`mcp-server-integration-mvp`（archive 2026-06-11）已把 `services/mcp/` 容器跑起来：`McpRouter` 接受 JSON-RPC 调用，3 server（filesystem / fetch / postgres）通过 `servers/<name>/HANDLER` 暴露能力，每次 dispatch 走 `MCP_AUDIT_BASE_URL` 写到 audit-and-isolation。HTTP/SSE 入口在 `services/mcp/app/main.py`，端口 8004。

`mcp-server-management-ui` 落地**管理面**——让 admin / paul / leo / anny 在 admin-web 里看见/增删/启停这些 MCP server，**不**改 MCP 协议层、**不**改单 server 实现。

上游三件源：
- `docs/architecture.md §4.3.6` 插件运行时（含 MCP 集成）
- `docs/architecture.md §4.3.5` 企业安全（白名单 / PII）
- `docs/prd.md §4.4.2` 插件类型（含 MCP）+ §1162 "MCP 工具配置页 | 工作区 | MCP Server 配置、工具发现、权限控制 | P1"
- `docs/prototype.html:4112-4164` "MCP 工具配置" 视图

12 个 eng-review 决策见 `openspec/config.yaml` `eng-review-decisions`；本设计触及其中的 Arch #1 / #5、Quality #1-#3、Test #1-#2、Perf #1。

## Goals / Non-Goals

**Goals：**
- 让 admin 在 admin-web 看到当前已注册的 MCP server 卡片（图标、名称、副标题、连接状态、Transport、工具列表、配置/断开按钮），与 prototype.html 视觉一致
- 支持 MCP server 注册的 CRUD（name / transport / command / args / env / security_config）
- 支持 connect / disconnect 状态切换，状态真实反映"探活能否成功调通 `list_advertised_tools`"
- 所有写操作（CRUD + connect / disconnect）经 audit-and-isolation egress，**不**直连 MCP 子进程
- 测试覆盖：单元 100%（单 service 内部） + 集成（router 真实 + 假 audit） + Playwright E2E（点按钮看状态变绿） + 4 critical path 之 "插件加载降级" 100% 覆盖

**Non-Goals：**
- 见 `proposal.md` Non-goals 节（不做插件市场浏览、不做 OAuth、不做命令热更新、不做多租户）
- 不引新微服务；不引新框架（继续 Starlette + uvicorn，不引 FastAPI）
- 不改 `mcp-server-integration-mvp` 的任何 spec

## Decisions

### D1：管理面挂在现有 `services/mcp` 容器内，不开新 service

**Context**：原型是 admin-web 一张视图，后端需要 1 组 REST 端点。

**选项**：
- A. **（已选）** 在 `services/mcp` 内挂 REST：复用 `app/router.py` 的 `McpRouter`、`app/security.py` 的 `McpSecurityPolicy`、3 个 server 的 `HANDLER`。新增 `app/registry.py`（CRUD + 状态机）+ `app/api.py`（Starlette 路由）。容器端口不变。
- B. 开 `services/mcp-admin/` 独立容器：单独占端口、单独 deploy、独立 health check。**拒绝理由**：违反 eng-review Arch #1 "egress 强制点"（admin 操作只是 CRUD 元数据，**真正**的 LLM/MCP 出口在 `services/mcp` 本身），开新 service 反而多一层网络 hop；且本 change 是 MVP 的 P1，没人力维护两个 service。
- C. 把 REST 端点直接挂到 admin-web 的 BFF 进程：拒绝，因为 admin-web 是 Vite/React，没有 Python 进程；要么引 Python BFF（= 选 B），要么直接调 audit-and-isolation（强耦合，破坏 mcp 单 service 自洽）。

**结论**：选 A。

### D2：状态机持久化用 PostgreSQL（不引 Redis 做 source of truth）

**Context**：eng-review Quality #2 锁了"PG source of truth + Redis 实时缓存"双层。本 change 是**状态字段**（disconnected / connecting / connected / error）的真理源在哪里的问题。

**选项**：
- A. **（已选）** PG 唯一真理源，Redis 仅作"前端轮询节流"缓存（`{server_id} → status`，TTL 30s）。前端 GET 走 API 拿 PG 实时值（不读 Redis），Redis 仅做"避免短时间内重复探活"的去重。
- B. Redis 做实时状态，PG 做"最终一致性"落盘：拒绝，因为 eng-review Quality #2 明文 PG = source of truth；且 connect/disconnect 走审计（写 PG），写两边会让 audit 链对不上。
- C. 不引 Redis，PG 读多写少扛得住：可接受但失去"探活 30s 缓存"的 Perf #1 价值。

**结论**：选 A。

### D3：探活用 `McpRouter.list_advertised_tools`（不真 spawn 子进程）

**Context**：admin 想知道"这个 server 实际能不能跑"，但 spawn 子进程是 5-10s 级别且要 env/command/env 文件；audit-and-isolation 已经做了白名单。

**选项**：
- A. **（已选）** 调 `McpRouter.list_advertised_tools()`：复用 `mcp-server-integration-mvp` 的 `servers/<name>/HANDLER`，由 HANDLER 内部判断 env 是否配置（filesystem 缺 `MCP_FS_ALLOWED_DIRS` 抛 `McpSecurityError`）。快（毫秒级），覆盖"配置正确性"，**不**覆盖"子进程能起来"。
- B. 真 `stdio_server` spawn：拒绝——admin 视角的"能连"应该是配置正确就够了；真 spawn 留到 `apply` 后第一次 dispatch 真实调 tool 时做。
- C. HTTP 探活：MCP 不规定，统一走 A。

**结论**：选 A。

### D4：UI / API / 审计 3 层共享 1 份 `McpServerRegistration` TypedDict

**Context**：eng-review Quality #1 强约束"4 份代码从 1 份生成"（针对 12 节点）；本 change 是非节点场景，但**精神一致**——管理面 + API + 审计 + DB 4 处必须共用 1 份 schema。

**实现**：在 `services/mcp/app/registry.py` 写 1 份 `class McpServerRegistration(TypedDict)`，导出 4 个函数：`to_pydantic()` / `to_sqlalchemy_column_spec()` / `to_audit_payload()` / `to_frontend_json()`。前端 TypeScript 端**不**自动生成（eng-review Quality #1 是 Python 侧的 4 份生成，前端 TS 端在 openspec/config.yaml 的"前端规范"里以手写 + 单元测试覆盖为主）。前端类型从 OpenAPI 文档 import（FastAPI-style），但本设计**不引 FastAPI**——决策点见 D5。

**结论**：选 Python 侧 1 份生成 4 处；前端手写 TS interface + Zod schema 对齐。

### D5：HTTP 框架 = Starlette Route（不引 FastAPI）

**Context**：eng-review §4.4 技术栈 = Python 异步；现有 `services/mcp/app/main.py` 已用 Starlette 0.40+。

**选项**：
- A. **（已选）** 继续 Starlette，用 `Route` + `Request` + `JSONResponse`。admin-web 调用方代码量 0 多余依赖。
- B. 引 FastAPI：拒绝——`services/mcp` 容器已有的 starlette/uvicorn 够用，引 FastAPI = 多一个 ASGI 框架、更多 import、更多学习成本。eng-review 不要求 admin API 必须 FastAPI。
- C. 改用纯 ASGI 函数：拒绝，可读性差。

**结论**：选 A。devx：30 行内 5 个 REST 端点 + 1 个 OpenAPI 文档（手写）够用。

### D6：前端轮询用 SWR（不引 WebSocket / SSE）

**Context**：admin 卡片需要 status 实时变化（探活完成从 connecting→connected）。

**选项**：
- A. **（已选）** admin-web 已有 React + Hooks 栈，引入 `swr` 做 5s 间隔轮询 `GET /v1/mcp/servers`。MVP 简单，CDN 友好。
- B. WebSocket：拒绝——admin-web 没有 WS gateway，5s 轮询延迟对 admin 视角可接受。
- C. SSE：拒绝，admin-web 不引 EventSource 抽象。

**结论**：选 A。`revalidateInterval: 5000`。

### D7：MCP server 凭据（env / command）明文存 PG

**Context**：V1.0 P1 不要求 secret store。

**选项**：
- A. **（已选）** 明文 JSONB 存 PG，DB 层用 `pgcrypto` 加密列（`services/mcp` 容器连的 PG 已是 16+ 自带 pgcrypto）。V1.5 接 secret store。
- B. 现在就接 HashiCorp Vault：拒绝，V1.0 没人力。

**结论**：选 A。**风险**：本 change 写成 spec 时**必须**显式标注 `[FUTURE-IMPLEMENTATION] secret store`，避免后人误以为"明文存是终态"。

### D8：错误边界 — 4 类映射到 HTTP 状态码

**Context**：eng-review Quality #3 4 边界 + MCP service 已有 7-class `app/security.py` 错误。

**映射**：

| 错误类 | HTTP | 触发场景 |
|---|---|---|
| `McpSecurityError` | 403 | 未授权 modify / 路径越界 / 凭据错 |
| `McpUserError` (Pydantic ValidationError) | 400 | 参数不全、name 重复、JSON 解析失败 |
| `McpResponseTooLargeError` (runtime) | 502 | 探活时 router 返 5xx / 限额 |
| `McpUnknownToolError` (runtime) | 500 | 内部 bug（不该发生） |
| `RuntimeError` (audit-and-isolation fail-open 已吞) | 200 + 字段 `audit_status: fail_open` | 探活成功但审计失败 |

**结论**：spec 里 SHALL 规定每类错误的 HTTP 映射。

## Risks / Trade-offs

- **[Risk] 明文存凭据被 PG dump 泄露** → Mitigation：V1.5 改 secret store（见 D7）；本 change 在 spec 顶部声明 `[FUTURE-IMPLEMENTATION]`。
- **[Risk] admin 误删 MCP server 导致引用它的 Agent / Workflow 失效** → Mitigation：`DELETE` 端点先做"被引用检查"（扫 `agents.spec.tools[]` + `workflows.spec.nodes[]`），命中返 409 Conflict + 引用方列表；UI 弹"先解绑"提示。
- **[Risk] 探活在 100 RPS 高并发下打爆 router** → Mitigation：eng-review Perf #1 缓存 30s（`MCP_TOOL_CACHE_TTL`）；探活并发上限 5（asyncio.Semaphore）。
- **[Risk] `McpRouter.list_advertised_tools` 调 3 个 server（fs/fetch/pg）的 HANDLE 是混合调用，不区分 server** → Mitigation：本 change 探活时**只调目标 server 的 HANDLER**（不调全 router），见 `tasks.md` task 4.3。
- **[Risk] `services/mcp` 容器重启时，正在 connecting 的请求悬挂** → Mitigation：状态机设 30s `connecting → error` 超时（DB 侧 cron 或 API 端拉起时检查 `updated_at < now - 30s`）。
- **[Risk] admin-web 不在本 change scope（前端仓库），但需要改 `SideNav.tsx` + `router/index.tsx`** → Mitigation：开**两个** change 入口（`mcp-server-management-ui` 主 + `admin-web-nav-update` 微），或者本 change 在 `web/admin-web/` 提交，依赖前置：`admin-web` 仓库已 git submodule 或 monorepo。**当前仓库结构**：`web/admin-web/` 目录在 `admin-web-bootstrap` 前**尚未就位**（CLAUDE.md 提示 admin-web 尚未搭建）。**决策点**：本 change 在 tasks.md 写"前置：确认 `web/admin-web/` 已 init"，否则 spec 不 apply。

## Migration Plan

无历史数据可迁——`services/mcp` 容器是 archive `mcp-server-integration-mvp` 落地的，**没有**已经注册的 MCP server 在生产跑（eng-review 12 决策 + MVP 仍在 month 2-3）。

**Deploy steps**：
1. `services/mcp-migrate` 一次性容器跑 `alembic upgrade head`（PG 加表 `mcp_server_registrations`）
2. `services/mcp` 容器滚动重启
3. admin-web 部署新版本（含 `/mcp-tools` 路由）
4. 验证：`curl http://chatbiz-mcp:8004/v1/mcp/servers` 返 `[]`，admin-web 看到空状态

**Rollback**：
- `alembic downgrade -1` 删表
- admin-web 切回旧版本
- `services/mcp` 容器回滚镜像 tag

## Open Questions

- OQ1：admin-web 是 monorepo 还是 submodule？现状：仓库根当时**没有** `web/admin-web/` 目录（CLAUDE.md 写"0 行源代码"），prototype.html 是 `docs/` 下的 HTML。前端代码仓库路径未定。**行动**：本 change 在 `tasks.md` 写"前置任务 = 等 admin-web 仓库就位"，否则 spec 标 `[BLOCKED]`。
- OQ2：MCP server 注册元数据是否要 export 给其他 service（agent-runtime 拿 `pg_server_registrations` 决定可调 tool）？**当前决定**：是，本 change 暴露 `GET /v1/mcp/servers` REST，agent-runtime 通过 audit-and-isolation / mcp 网关间接拿。**未来**：可能要 `pg_notify` 推送给 agent-runtime，V1.5 再做。
- OQ3：`mcp-server-audit-trail` capability 声明 `Frontend Scope: N/A`（被 audit-and-isolation 消费，UI 由后续 change），**还是要**做审计面板（让 admin 看见"谁改了 MCP server 配置"）？**当前决定**：N/A，admin 视角只看"现在哪些 server 在线 / 离线"，不看历史。**未来**：V1.5 走 `audit-and-isolation-admin-ui` 落地。
