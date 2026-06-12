# mcp-server-management-ui — Tasks

> **前置门**：任务 0 必须先完成（admin-web 仓库就位），否则后续任务标 [BLOCKED]。

## 0. 前置门

- [ ] 0.1 确认 `web/admin-web/` 仓库路径（monorepo 还是 submodule）并 init 到本仓库根——若为 submodule 则本 change 在子模块仓提交；若为 monorepo 则本 change 在 `web/admin-web/` 目录内提交。**否则 [BLOCKED]**。验：仓库根 `web/admin-web/package.json` 存在。<br/>**[2026-06-12 更新]** 由 `admin-web-bootstrap` change（archive 后）落地 `web/admin-web/` monorepo 子目录 — 含 Vite 5 + React 18 + TS strict + Tailwind + Router + SWR + Vitest + Playwright 骨架。本 change apply 时验：`ls web/admin-web/package.json` 存在 + `pnpm --filter @chatbiz/admin-web install` 0 错。
- [ ] 0.2 确认 admin-web 已装 React 18 + TypeScript 严格 + SWR；若未装则先开一个前置 change `admin-web-bootstrap`。验：`web/admin-web/package.json` 包含 `react`, `typescript`, `swr`。
- [ ] 0.3 拉 `mcp-server-integration-mvp` 已 archive 的 `services/mcp/` 代码到 worktree。验：`services/mcp/app/main.py` 存在且 import 不报错。

## 1. 契约层（Node Contract 类比，先 schema 后代码）

- [ ] 1.1 写 `services/mcp/app/registry_types.py`：定义 `class McpServerRegistration(TypedDict)` + 4 个导出函数 `to_pydantic()` / `to_sqlalchemy_column_spec()` / `to_audit_payload()` / `to_frontend_json()`。**编码规范清单**：Python 3.12 类型注解严格；任何 Pydantic model 必须有 `Field` description；不得使用 `Any` 作为字段类型。**安全清单**：env 字段 schema 标注 `secret: bool` 元信息。验：`python -c "from app.registry_types import McpServerRegistration"` 不报错。
- [ ] 1.2 写 `services/mcp/tests/unit/test_registry_types.py`：4 个 to_* 函数各 1 个 round-trip 测试 + 1 个 Pydantic ValidationError 用例。验：`pytest tests/unit/test_registry_types.py` 8/8 pass + 覆盖率 100%。

## 2. 数据库层

- [ ] 2.1 在 `services/mcp/` 下 init Alembic：`alembic init alembic` + 配置 `alembic.ini` 读 `MCP_DATABASE_URL` env。**编码规范**：异步 engine（`create_async_engine`）。验：`alembic current` 返 `[]`。
- [ ] 2.2 写 migration `alembic/versions/0001_mcp_server_registrations.py`：`upgrade()` 建表 `mcp_server_registrations` 含 spec 中所有列 + 索引 `idx_mcp_server_registrations_name UNIQUE` + `idx_mcp_server_registrations_status`。`downgrade()` 删表。**安全清单**：表注释 + 列注释写明用途。验：`alembic upgrade head` 成功 + `psql ... \d mcp_server_registrations` 显示所有列。
- [ ] 2.3 写 `services/mcp/tests/integration/test_migration.py`：临时 PG 容器，跑 `upgrade head` → 验证表存在 → `downgrade base` → 验证表消失。验：`pytest tests/integration/test_migration.py` 1/1 pass。

## 3. 后端 CRUD（mcp-server-registry capability）

- [ ] 3.1 写 `services/mcp/app/registry.py`：`McpRegistry` 类封装 SQLAlchemy 2.0 async session，提供 `list_servers()` / `create_server(payload)` / `update_server(id, payload)` / `delete_server(id)` / `get_server(id)` 5 个方法 + 引用检查 `_check_references(id) -> list[ReferenceEntity]`（扫 `agents.spec.tools[]` + `workflows.spec.nodes[]`，注：本 change 不实现 agents/workflows 表，但写接口留 stub）。**编码规范**：SQLAlchemy 2.0 async + 审计埋点（每个方法末尾调 `audit_archive`）。**安全清单**：所有 write 方法必须接受 `actor: str` 参数并写入 audit。验：`python -c "from app.registry import McpRegistry"` 不报错 + `mypy --strict app/registry.py` 0 错。
- [ ] 3.2 写 `services/mcp/tests/unit/test_registry.py`：5 个方法各 2 个用例（success + error）+ 引用检查 2 个用例（unreferenced / referenced-with-1-agent）。**安全测试**：注入恶意 `name="'; DROP TABLE..."` 验证 Pydantic 拒绝。验：覆盖率 100%。
- [ ] 3.3 写 `services/mcp/app/api.py`：6 个 Starlette Route 挂载 `GET/POST/PATCH/DELETE /v1/mcp/servers` + `/v1/mcp/servers/{id}:connect|disconnect` + `GET /v1/mcp/servers/{id}/tools`。每个 Route 必须有：request Pydantic 校验、actor 提取（从 `request.headers["X-User-Id"]` 占位）、`McpRegistry` 调用、`audit_archive` 埋点、错误映射（4 边界 → HTTP 状态码见 design.md D8）。**安全清单**：Pydantic schema 拒绝 `name='__proto__'` / `command='rm -rf /'` 等危险值。验：手 `curl` 6 端点 200/4xx 各一遍。
- [ ] 3.4 写 `services/mcp/tests/integration/test_api.py`：用 `httpx.AsyncClient` + `LifespanManager` + 真实 registry + 假 audit 测 6 端点 happy path + 4xx + 5xx 各 1 例。验：覆盖率 100% + 6 端点全 PATCH。

## 4. 后端探活（mcp-server-lifecycle capability）

- [ ] 4.1 写 `services/mcp/app/probe.py`：`async def probe_server(server_id: str) -> ProbeResult` 调 `servers.<transport>.HANDLER.list_advertised_tools()`（NOT `McpRouter.list_advertised_tools`），用 `asyncio.Semaphore(5)` 包并发，30s `asyncio.wait_for` 超时。ProbeResult 包含 `status: connected|error` + `tools: list[Tool]` + `error: str | None`。**编码规范**：返回 TypedDict，**不**用 `dataclass`（保持与 registry_types 一致）。**安全清单**：HANDLER 调用必须在 `try/except` 内捕获 `McpSecurityError` 并归类为 `error` 而非 `connected`。验：单测覆盖 3 个 transport + 超时分支。
- [ ] 4.2 写 `services/mcp/tests/unit/test_probe.py`：8 个用例（filesystem ok / filesystem missing env / fetch ok / fetch timeout / postgres ok / unknown transport / 并发 10 但只跑 5 / 缓存命中）。验：覆盖率 100%。
- [ ] 4.3 写 `services/mcp/app/api.py` 的 connect/disconnect handler：调 `probe_server` 异步（`asyncio.create_task`），任务完成后写 PG `status` 字段。**安全清单**：探测任务用 `try/finally` 确保 task 不悬挂（注册到 `app.state.background_tasks` set）。验：单测模拟 30s 超时后 `status='error'`。
- [ ] 4.4 写 `services/mcp/app/cache.py`：`ProbeCache` 类封装 Redis 读写，key 格式 `mcp:probe:{id}` / `mcp:tools:{id}`，TTL 30s / 60s。**编码规范**：用 `redis.asyncio` 而非同步 redis。**安全清单**：Redis 写失败必须 log WARNING 不 raise。验：单测覆盖 hit / miss / 写失败。
- [ ] 4.5 写启动期 stale-connecting 恢复 hook：在 `services/mcp/app/main.py` 的 lifespan `startup` 阶段跑 SQL `UPDATE ... WHERE status='connecting' AND updated_at < now() - interval '30 seconds'`，log 每次 UPDATE 行数。**安全清单**：hook 失败不能阻塞 startup（包 try/except）。验：单测 mock PG session + 验证 UPDATE SQL 字符串。

## 5. 审计集成（mcp-server-audit-trail capability）

- [ ] 5.1 写 `services/mcp/app/audit.py`：`async def emit_audit(action, resource_id, actor, payload, trace_id, error_class=None, error_message=None)`。**关键**：复用 `app.router.audit_archive` helper（spec 要求），**不**新写 httpx 客户端。内部调 `_redact(payload)` 替换 secret 字段为 `***REDACTED***`。**安全清单**：redact helper 必须基于白名单（`MCP_*_KEY|TOKEN|SECRET`、`password`、`api_key`）而非黑名单。验：单测覆盖 5 个 redact case + 1 个 non-redact case。
- [ ] 5.2 写 trace_id 中间件：在 `services/mcp/app/api.py` 加一个 `BaseHTTPMiddleware`，每个请求生成 uuid4 trace_id，挂到 `request.state.trace_id` + 响应 header `X-Trace-Id`。**安全清单**：trace_id 必须用 `uuid.UUID(...)` 验证上游传入（防注入）——若上游传 `X-Trace-Id` 则使用上游值。验：单测覆盖上游传/不传 2 case。
- [ ] 5.3 写 `services/mcp/tests/integration/test_audit_egress.py`：用 `respx` mock `MCP_AUDIT_BASE_URL` 验证 emit_audit 触发的请求体包含 `service="chatbiz-mcp"` + `action` + `trace_id` + `payload`。验：5 个场景（create / patch / delete / connect / disconnect）。

## 6. docker-compose 同步（apply 规则第 81 行）

- [ ] 6.1 改 `infrastructure/docker-compose.yml`：在 `chatbiz-mcp` service 下加 `chatbiz-mcp-migrate` 子 service（`restart: "no"`, `command: python -m alembic upgrade head`），`chatbiz-mcp` `depends_on` 加 `chatbiz-mcp-migrate: {condition: service_completed_successfully}`。**安全清单**：migrate service 复用 `chatbiz-mcp` 的 image + env（DATABASE_URL 共享）。验：`docker compose config` 不报错。
- [ ] 6.2 验 CLAUDE.md 端口表：本 change 不新占端口（8004 沿用）。若不新占则**不**改端口表。验：`grep "8004" CLAUDE.md` 显示 mcp 行已存在。

## 7. 前端（mcp-server-registry + mcp-server-lifecycle + mcp-server-tool-discovery capabilities）

- [ ] 7.1 在 `web/admin-web/src/api/mcp.ts` 写 TS 客户端：`listServers()` / `createServer(payload)` / `updateServer(id, payload)` / `deleteServer(id)` / `connectServer(id)` / `disconnectServer(id)` / `listServerTools(id)`，每个返回 `Promise<...>` + 用 Zod 校验响应。**编码规范**：TypeScript strict + Hooks + 状态隔离。**安全清单**：所有错误必须归类为 `McpError` 子类（`Security` / `User` / `Runtime`），不暴露 stack。验：`tsc --noEmit` 0 错。
- [ ] 7.2 在 `web/admin-web/src/types/mcp.ts` 写 TS interface `McpServer` / `McpTool` / `McpServerStatus` enum + Zod schema，**与 `services/mcp/app/registry_types.py` 字段一一对应**（手工对齐，**不**自动生成——admin-web 在另一个仓库或 monorepo，跨语言生成要等 codegen 工具就位）。**安全清单**：env 字段在 TS 端类型为 `Record<string, string>` 但 UI 上对 key 含 `*KEY|*TOKEN|*SECRET` 的值渲染为 `***REDACTED***`。验：手 import 跑通。
- [ ] 7.3 在 `web/admin-web/src/views/mcp/McpToolsView.tsx` 写主视图：复制 prototype.html:4112-4164 的卡片网格、状态徽章、工具行、按钮布局。用 SWR `useSWR('/v1/mcp/servers', listServers, {refreshInterval: 5000})`。**编码规范**：组件用 function component + Hooks；不引 class component；不引 Redux。**安全清单**：按钮 disabled 时不响应 click；模态关闭清空表单 state。验：手打开 `/mcp-tools` 看到 3 卡片（开发环境 mock）。
- [ ] 7.4 在 `web/admin-web/src/components/mcp/McpServerCard.tsx` 写卡片组件：复用 prototype.html 视觉（图标 + 标题 + 副标题 + 状态徽章 + Server/Transport 行 + 工具行 + 配置/断开按钮）。**安全清单**：状态徽章用 4 个色值（green/gray/yellow/red）+ WCAG AA 对比度。验：Storybook 跑通 4 个状态变体。
- [ ] 7.5 在 `web/admin-web/src/components/mcp/McpServerForm.tsx` 写弹窗表单：fields 见 spec mcp-server-registry `前端 form`。表单用 `react-hook-form` + `zod` resolver。**安全清单**：transport = `connected` 时 disable command/env 字段。验：手填表提交成功。
- [ ] 7.6 在 `web/admin-web/src/components/mcp/DisconnectConfirmModal.tsx` 写确认弹窗：标题"确认断开 <name> 吗？" + Cancel / 断开 按钮。**安全清单**：默认焦点在 Cancel（防误触）。验：Storybook 跑通。
- [ ] 7.7 在 `web/admin-web/src/router/index.tsx` 注册 `/mcp-tools` 路由 + lazy import `McpToolsView`。**安全清单**：route guard 检查 `useUser().roles.includes('mcp.admin')`，无权限跳 `/403`。验：`tsc --noEmit` 0 错。
- [ ] 7.8 在 `web/admin-web/src/components/SideNav.tsx` 激活 "MCP 工具" 菜单项（prototype.html:315 已有）。**安全清单**：菜单项对无 `mcp.admin` 角色用户隐藏。验：手切角色看菜单变化。

## 8. E2E 测试（Playwright，critical path #4 插件加载降级）

- [ ] 8.1 写 `web/admin-web/e2e/mcp-tools.spec.ts`：4 个场景——① admin 看到 3 卡片徽章正确 ② 点击"连接" 5s 内徽章变绿 ③ 故意删 env 触发 error，徽章变红 + tooltip 显示 last_error ④ 删除被引用的 server 返 409 弹窗。**安全清单**：E2E 用真实后端（testcontainers 起 `chatbiz-mcp` + PG + audit-and-isolation mock），不 mock 网络层。验：`pnpm playwright test e2e/mcp-tools.spec.ts` 4/4 pass。
- [ ] 8.2 在 `web/admin-web/playwright.config.ts` 加 `mcp-tools` project，依赖 admin-web dev server。验：`pnpm playwright test --project=mcp-tools` 单独跑通。

## 9. 集成 / 端到端验证

- [ ] 9.1 写 `services/mcp/tests/integration/test_lifecycle_e2e.py`：在测试内 spawn `chatbiz-mcp` 进程（testcontainers），`POST /v1/mcp/servers` 注册一个 filesystem server → `POST .../connect` → 验 `status='connected'` → `GET .../tools` 返 4 工具 → `DELETE` 返 204 → 验 PG 表 row 删除。**安全清单**：测试结束后清理 PG + Redis。验：1/1 pass。
- [ ] 9.2 写 `services/mcp/tests/integration/test_critical_path_plugin_degradation.py`：注册 1 filesystem + 1 postgres，filesystem env 故意 unset → connect filesystem → 验 status='error'，然后调 list tools for postgres → 验返 200（filesystem error 不影响 postgres）。**安全清单**：测试结束清理 env。验：1/1 pass。
- [ ] 9.3 跑全量 `pytest services/mcp/ --cov=services/mcp/app --cov-fail-under=100`。验：覆盖率 ≥100%。
- [ ] 9.4 跑 `pnpm --filter admin-web test --coverage` + `pnpm --filter admin-web e2e`。验：覆盖率 ≥80%（前端不强制 100%）。

## 10. 文档 / 收尾

- [ ] 10.1 写 `services/mcp/docs/management-api.md`：6 端点 OpenAPI 3.1 文档（手写 YAML）。**安全清单**：每个端点必须有 401/403/500 示例。验：`npx @redocly/cli lint services/mcp/docs/management-api.md` 0 错。
- [ ] 10.2 更新 `docs/prd.md` §4.4.2：在"插件类型"表格的 MCP 行加"V1.0 P1 已落地：见 `mcp-server-management-ui`"链接。验：`grep "mcp-server-management-ui" docs/prd.md` 显示 1 行。
- [ ] 10.3 更新 `docs/architecture.md` §4.3.6：补一段"管理面"——引用本 change + 提到 `McpRegistry` + 状态机 + audit-and-isolation egress。验：`grep "McpRegistry" docs/architecture.md` ≥1 行。
- [ ] 10.4 写 `openspec/changes/mcp-server-management-ui/retrospective.md`（apply 后填）：本 change 实际耗时、eng-review 12 决策触发情况、critical path #4 覆盖证据、未结 open questions 状态。验：archive 流程要求。
- [ ] 10.5 跑 `openspec schema validate mcp-server-management-ui`。验：返 0 exit code。

## 配对验证总结（openspec/config.yaml 规则第 56 行：编码任务配对验证任务）

| 编码任务 | 配对验证任务 |
|---|---|
| 1.1 registry_types.py | 1.2 test_registry_types.py |
| 2.1, 2.2 alembic init + migration | 2.3 test_migration.py |
| 3.1 registry.py | 3.2 test_registry.py |
| 3.3 api.py | 3.4 test_api.py |
| 4.1 probe.py | 4.2 test_probe.py |
| 4.4 cache.py | (单测在 4.2 内合并) |
| 5.1 audit.py | 5.3 test_audit_egress.py |
| 6.1 docker-compose 改 | (验 task 用 `docker compose config`) |
| 7.1, 7.2 前端 client + types | (单测在 7.3-7.6 组件单测内) |
| 7.3-7.8 前端组件 | 8.1, 8.2 Playwright E2E |
| 9.1, 9.2 后端 e2e | (本身即验证任务) |
