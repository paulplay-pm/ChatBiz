# web-e2e-orchestration Specification

## Purpose
TBD - created by archiving change web-integration-test-suite. Update Purpose after archive.
## Requirements
### Requirement: 统一测试启动矩阵（test compose 与 production 互斥）

`infrastructure/docker-compose-test.yml` MUST 提供一键启动命令，覆盖 `web`（nginx 5173）+ 4 个后端 service（`credential:8000` / `workflow-engine:8001` / `mcp:8004` / `audit-and-isolation:8080`）+ 共享 `postgres:5432` + 共享 `redis:6379`。test compose MUST 使用 `--project-name chatbiz-test` 与 production compose 互斥（同一时刻仅一组在跑）。所有 service MUST 含 `healthcheck`，且 `depends_on` 链 `service_composedly_successfully`。

#### Scenario: 启动命令一键拉起
- **WHEN** 在仓库根执行 `make test-integration` 或 `bash scripts/test-integration.sh up`
- **THEN** compose 启动所有 service 并在所有 service `healthy` 后返回 exit code 0
- **AND** `docker compose -p chatbiz-test ps` 列出 7 个 service 全部 `State: healthy`

#### Scenario: 与 production compose 互斥
- **WHEN** production compose（`--project-name chatbiz`）正在运行
- **THEN** `make test-integration up` MUST fail 并提示"请先 `docker compose -p chatbiz down`"

#### Scenario: 单 service 健康检查
- **WHEN** 启动后访问 `curl http://localhost:5173/healthz`
- **THEN** MUST 返回 200 + `{"status": "ok"}`（来自 `chatbiz-mcp:8080/healthz`，经 nginx proxy）

### Requirement: 4 critical path 中 ① paul 财务月报端到端 100% 覆盖（简化版）

`web/canvas/e2e/integration/paul-monthly-report.spec.ts` MUST 走真实 test compose 栈：登录 → 新建 workflow → 打开 editor → 验证 workflow 在 `workflow-engine` 持久化。本 change **不**覆盖"拖 LLM 节点 + run + 看结果"（真实后端上该路径复杂，作为后续增强）。spec MUST 含 ≥3 个 `test()` case 覆盖：登录成功 / workflow 创建 / 持久化验证。

#### Scenario: 登录后进入 workflow 列表
- **WHEN** user 打开 `http://localhost:5173/canvas/` 并输入有效凭据
- **THEN** page 跳转到 `/canvas/workflows` 并显示 workflow 列表

#### Scenario: 创建 workflow 并持久化
- **WHEN** user 点击"新建 workflow" → 输入名称 → 保存
- **THEN** `POST /workflows` 返回 201
- **AND** `GET /workflows` 列表中出现新建的 workflow
- **AND** page 跳转到 `/canvas/workflows/:id/edit`

#### Scenario: 4 critical path 覆盖声明
- **WHEN** 查看 `web/canvas/e2e/integration/paul-monthly-report.spec.ts` 的测试列表
- **THEN** MUST 包含覆盖"paul 财务月报 end-to-end"链路的所有 case
- **AND** 标注 `// critical-path-1: paul-monthly-report` 注释供 verify 阶段 grep

### Requirement: LLM echo stub 作为 audit-and-isolation `/v1/chat/completions` 的旁路（eng-review Arch #1 兼容）

`services/audit-and-isolation/app/api/chat.py` 的 `chat_completions` handler MUST 在 `get_settings().environment == "integration"` 且 `body.get("model") == "echo-test"` 时走旁路：直接返回 OpenAI 兼容响应 `{"choices": [{"message": {"content": "ECHO: <last user message>"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": <n>, "completion_tokens": <n>, "total_tokens": <n>}}`。**所有** LLM 调用（含 echo） MUST 经过 `audit-and-isolation` egress 强制点，旁路代码 MUST 仍调用既有 `AuditLog` enqueue（eng-review Arch #1）。

#### Scenario: echo stub 仅在 integration env 时可达
- **WHEN** `audit-and-isolation` 容器以 `ENVIRONMENT=integration` 启动
- **THEN** `POST /v1/chat/completions` 含 `model = "echo-test"` MUST 返回 echo 响应

- **WHEN** `audit-and-isolation` 容器以 `ENVIRONMENT=production` 启动
- **THEN** `POST /v1/chat/completions` 含 `model = "echo-test"` MUST 返回 400（`RoutingError`：模型未在路由表注册）

#### Scenario: 真实 LLM 模型不受影响
- **WHEN** test 栈中请求 `model = "gpt-4"` 或其他真实模型
- **THEN** MUST 走原真实 LLM 路径（如已配置）或返回 400（未配置），**不**被 echo 拦截

#### Scenario: 审计埋点工作
- **WHEN** echo stub 返回响应
- **THEN** `audit-and-isolation` 的 `audit_log` outbox MUST 新增一条记录（`trace_id` + `model = "echo-test"` + `prompt_hash`）

### Requirement: Playwright 走统一入口 `localhost:5173`（CLAUDE.md "单端口 5173" 约定）

所有 E2E spec（含本 change + 后续 change）的 `baseURL` MUST 设为 `http://localhost:5173`。Playwright MUST 通过 nginx 路径分发访问 canvas（`/canvas/`）和 admin（`/admin/`），**不**直连后端端口（`workflow-engine:8001` / `mcp:8004` / 等）。

#### Scenario: canvas E2E 走 nginx
- **WHEN** Playwright 打开 `http://localhost:5173/canvas/`
- **THEN** nginx MUST 代理到 `web-canvas` 容器并返回 SPA HTML

#### Scenario: admin E2E 走 nginx
- **WHEN** Playwright 打开 `http://localhost:5173/admin/`
- **THEN** nginx MUST 代理到 `web-admin` 容器并返回 SPA HTML

#### Scenario: API 走 nginx proxy
- **WHEN** page 调 `POST /workflows`
- **THEN** nginx MUST 代理到 `chatbiz-workflow-engine:8001`（非直连）

### Requirement: 测试数据隔离（独立 user + cleanup）

每个 spec MUST 在 setup 阶段创建独立 `user_id = uuid`（当前后端用 `created_by == user_id` 做权限隔离，尚无 `tenant_id` 概念），创建独立 `workflow`；teardown MUST 删除该 user 创建的所有 workflow。**禁止**用全局 seed 数据。**禁止**在多 spec 间共享 user 状态。

#### Scenario: spec 间不互相干扰
- **WHEN** spec A 和 spec B 并发跑（`fullyParallel: true`）
- **THEN** spec A 的 workflow 创建 MUST 不出现在 spec B 的列表中
- **AND** spec A 失败 MUST 不污染 spec B 的 setup

#### Scenario: teardown 清理数据
- **WHEN** spec 完成（无论 pass / fail）
- **THEN** teardown MUST 删除该 `user_id` 在 `workflow-engine` 数据库创建的 workflows

#### Scenario: 错误处理 4 边界在集成测试中验证
- **WHEN** 集成测试断言 401 / 400 / 5xx
- **THEN** MUST 验证后端返回 `error_class` 字段可映射到 4 错误边界之一（canvas drag / runtime / user / security，eng-review Quality #3）
- **AND** 至少 3 个测试 case 分别覆盖 security / user / runtime 边界

### Requirement: 单命令入口 `make test-integration`（或 `scripts/test-integration.sh`）

`Makefile`（或 `scripts/test-integration.sh`） MUST 提供 `up` / `down` / `test` / `logs` 4 个子命令：
- `make test-integration up` —— 启动 test compose
- `make test-integration down` —— 停止 test compose
- `make test-integration test` —— 跑全部集成测试（canvas API + canvas E2E + admin E2E）
- `make test-integration logs` —— tail 所有 service 日志

#### Scenario: 单命令跑全测试
- **WHEN** 在仓库根执行 `make test-integration test`（前提 `up` 已起）
- **THEN** MUST 依次跑：① canvas vitest integration ② canvas playwright integration ③ admin playwright integration
- **AND** 全部 pass 时 exit code 0

### Requirement: Extension points 为 4 critical path 的 ②③④ 留 spec 钩子

本 spec MUST 在"Extension points"Scenario 中显式声明 ②③④ 的接入点，后续独立 change 复用本基础设施：

#### Scenario: ② 网关 PII 拦截扩展点
- **WHEN** 后续 `gateway-pii-e2e` change 落地
- **THEN** MUST 在 `web/canvas/e2e/integration/` 添加新 spec，**复用**本 change 的 compose + echo stub + audit-and-isolation 链路
- **AND** 验证 `audit-and-isolation` 对含 PII 的 prompt 返回 4xx 拒绝

#### Scenario: ③ 人工审批中断续接扩展点
- **WHEN** 后续 `manual-approval-resume` change 落地
- **THEN** MUST 复用本 change 的 compose，复用 LangGraph Checkpointer 到 PG（既有 spec 锁定）
- **AND** 验证"workflow 暂停 → 审批人 web UI 重新进入 → 24h 内恢复"链路

#### Scenario: ④ 插件加载降级扩展点
- **WHEN** 后续 `plugin-degradation` change 落地
- **THEN** MUST 复用本 change 的 compose，验证"plugin 加载失败 → 走降级路径"链路
- **AND** 验证 frontend 不崩 + workflow 不挂

