# mcp-server-management-ui — Proposal

## Why

`mcp-server-integration-mvp` 已经把 `services/mcp/`（filesystem / fetch / postgres 三 server + router + HTTP/SSE 入口）落地了，但**没有任何管理面**。用户看不到自己接了哪些 MCP server、连没连、有哪些 tool、怎么配 `MCP_FS_ALLOWED_DIRS` 之类的安全参数——而 eng-review Arch #5 + PRD §4.4.2 把"插件市场"列为 V1.0 P1，MCP 工具配置页是其中**第一刀可交付的部分**（PRD §1162、§1706）。

不改这个面会发生什么：admin / paul / leo 只能 SSH 到容器改 env + `docker compose restart`，违反 eng-review Quality #1 "管理动作走带权限渲染的前端"、Test #2 critical path 之一"插件加载降级"也没法在 UI 触发。

参考原型 `docs/prototype.html:4112-4164`（"MCP 工具配置" 视图）：卡片网格 + 状态徽章 + 工具清单 + 配置/断开按钮。

## What Changes

- **新增** MCP server 注册中心（CRUD 元数据 + 启停状态 + 探活），存 PostgreSQL（新增表 `mcp_server_registrations`，见 eng-review Quality #2 双层状态：PG 是 source of truth）。
- **新增** 后端 API `services/mcp/` 内部挂载的 REST 端点：`GET /v1/mcp/servers`、`POST /v1/mcp/servers`、`PATCH /v1/mcp/servers/{id}`、`DELETE /v1/mcp/servers/{id}`、`POST /v1/mcp/servers/{id}:connect`、`POST /v1/mcp/servers/{id}:disconnect`、`GET /v1/mcp/servers/{id}/tools`。所有写操作**不直接 spawn 子进程**，仅把元数据写 PG + 通过现有 `McpRouter.dispatch` 探活（调 `list_advertised_tools` 走 audit-and-isolation egress）。
- **新增** 审计：每次 connect / disconnect / 探活 / 配置修改都走 `MCP_AUDIT_BASE_URL`（eng-review Arch #1，egress 强制点，不旁路）。
- **新增** 前端 `apps/admin-web/src/views/mcp/McpToolsView.tsx` 复刻 prototype.html 的卡片网格、状态徽章、工具清单、配置弹窗、断开确认。
- **修改** 前端路由 `apps/admin-web/src/router/index.tsx` 注册 `/mcp-tools`。
- **修改** 左侧导航 `apps/admin-web/src/components/SideNav.tsx` 激活 "MCP 工具" 菜单项（已在 prototype.html:315 出现）。
- **不** 引新微服务。后端加在现有 `services/mcp/` 容器内（端口 8004 不变），复用 `app/security` / `app/router` / `app/servers/*`。

## Capabilities

### New Capabilities

- `mcp-server-registry`：CRUD MCP server 元数据（name / transport / command / args / env / allowed-dirs / allowed-domains / dsn），落 PostgreSQL，含幂等 + 名称唯一约束。**前端** = 卡片列表 + 弹窗表单 + 状态徽章；**后端** = REST 端点 + SQLAlchemy 模型 + 审计埋点；**是否豁免前端** = 否。
- `mcp-server-lifecycle`：connect / disconnect 状态机，状态字段在 PG，每次转换写一行 audit。**前端** = "连接 / 断开" 按钮 + 确认弹窗 + 状态轮询；**后端** = `/v1/mcp/servers/{id}:connect|disconnect` + 探活（`router.list_advertised_tools` 一次调用）；**是否豁免前端** = 否。
- `mcp-server-tool-discovery`：从 router 拉该 server 暴露的 tool 列表，前端卡片副标题展示。**前端** = 卡片 "工具" 字段 + 配置弹窗的 tools 列表；**后端** = `GET /v1/mcp/servers/{id}/tools`，内部 call `McpRouter.list_advertised_tools` 后按 server 过滤；**是否豁免前端** = 否。
- `mcp-server-audit-trail`：所有写 + connect/disconnect 走 audit-and-isolation egress，UI 暂不展示（"无管理动作 = 无 UI"豁免：审计是**被**消费的下游，不是被用户消费的产品能力）。**前端** = N/A — 审计面板属于 `audit-and-isolation` service 的另一个 change，**影响**：本 change 在 spec 顶部显式声明 Frontend Scope: N/A — 审计是**被** audit-and-isolation / 合规团队消费的产品能力，UI 由后续 change（`audit-and-isolation-admin-ui`）落地。**后端** = 7-class 错误映射（eng-review Quality #3 4 边界） + audit-and-isolation HTTP egress。

### Modified Capabilities

无。本 change 是 additive；不动 `mcp-server-integration-mvp` 已 archive 的任何 spec。

## Impact

- **代码层**：
  - `services/mcp/app/registry.py`（新）：SQLAlchemy 2.0 async model + 增删改查 + 状态字段。
  - `services/mcp/app/api.py`（新）：FastAPI 子应用，挂载到现有 `Starlette` 入口（eng-review 不引新框架，复用 Starlette + uvicorn）。
  - `services/mcp/app/main.py`（改）：增加 `/v1/mcp/*` 路由。
  - `services/mcp/pyproject.toml`（改）：加 `fastapi>=0.110`（或维持 Starlette Route——决策点见 design.md）。倾向**不加 FastAPI**，保持 Starlette 单一框架。
  - `apps/admin-web/src/views/mcp/McpToolsView.tsx`（新）：卡片网格。
  - `apps/admin-web/src/api/mcp.ts`（新）：封装 REST 调用。
  - `apps/admin-web/src/router/index.tsx`（改）：加路由。
  - `apps/admin-web/src/components/SideNav.tsx`（改）：激活菜单项。
- **数据库**：新增 1 张表 `mcp_server_registrations`（id / name UNIQUE / transport enum{stdio,sse,http} / command / args jsonb / env jsonb / security_config jsonb / status enum{disconnected,connecting,connected,error} / last_health_check_at / last_error / created_at / updated_at）。需新增 `services/mcp/alembic/` + `services/mcp-migrate` 一次性容器（`openspec/config.yaml` apply 规则第 81 行）。
- **依赖**：现 `services/mcp` 已连 audit-and-isolation（8004 内的 `MCP_AUDIT_BASE_URL` env 已配），本 change 复用同一 env，不引新依赖。
- **端口**：`services/mcp` 容器已占 8004，宿主 8004→容器 8004 不变（CLAUDE.md 端口表行已注册）。**不**占新端口。
- **docker-compose**：本 change 改 `infrastructure/docker-compose.yml` 在 `chatbiz-mcp` service 下加 `<service>-migrate` 子 service（apply 规则第 81 行）；admin-web service 早就注册在 compose 里，本次**不**加。
- **eng-review 决策关联**：
  - **Arch #1**：所有 connect / disconnect / 探活操作走 audit-and-isolation egress，**不**直连 MCP 子进程。
  - **Arch #5**：MVP 已含 3 server（filesystem/fetch/postgres），本 change 是**管理面**而非新增 server。
  - **Quality #1**：UI / API / 审计 三层共享 1 份 dataclass schema（`McpServerRegistration` TypedDict），从 1 份生成 3 处。
  - **Quality #2**：状态双层——PG 是 source of truth（status 字段），Redis 仅缓存"前端轮询结果 / 探活最新时间"，不替代 PG。
  - **Quality #3**：4 错误边界——`SecurityError`（未授权 modify）/`UserError`（参数不全，name 重复）/`WorkflowRuntimeError`（探活失败：MCP server 启不来）/`canvas drag-loop` 不适用（本 change 无画布）。
  - **Test #1**：3 层测试金字塔——pytest 单元 / httpx 集成（真实 router + 假 audit）/ Playwright E2E（点连接按钮 → 看徽章变绿）。
  - **Test #2 critical path**：本 change 直接覆盖 **#4 插件加载降级**（disconnected 状态正确降级到错误徽章，不抛 500）。
  - **Perf #1**：探活走缓存——`list_advertised_tools` 结果在 Redis 缓存 30s（`MCP_TOOL_CACHE_TTL`），不每次点连接按钮都 spawn。

## Non-goals

- **不**做插件市场浏览/安装（PRD §4.4.1 的 browse / install）——那是 `plugin-marketplace` 后续 change 的事，本 change 只管"已注册的 MCP server"。
- **不**做 OAuth / 凭据管理（PRD §4.4 后续）——本 change 的 env / command 字段以明文存 PG（V1.0 P1 内，V1.5 走 secret store）。
- **不**做 MCP server 自定义开发 / 上传（PRD §4.4.4 插件开发规范）——本 change 不接 npm/pypi 仓库。
- **不**改 `services/mcp` 容器外的代码：credential / workflow-engine / knowledge-base / agent-runtime / audit-and-isolation 都**不**在本 change 触碰。
- **不**支持运行时改 server 的 command / env（注册时定稿，修改 = 删除重建），避免热更新引发子进程泄漏。
- **不**做"连接配额 / 多租户隔离 / SSO"——V1.5 之后。
