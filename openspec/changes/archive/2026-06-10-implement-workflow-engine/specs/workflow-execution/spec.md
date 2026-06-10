# workflow-execution Specification

## Purpose
定义 workflow_engine 异步执行 / SSE 流式事件 / 重试 / workflow_run 状态机。
## Requirements
## ADDED Requirements

### Requirement: 异步执行
`POST /workflows/:id:run` MUST 立即返 202 + `run_id`(不阻塞等执行完成);实际执行 MUST 在后台 `asyncio.create_task()` 跑;workflow_run 状态机:`pending` → `running` → (`paused`|`completed`|`failed`|`cancelled`)。

#### Scenario: 异步启动
- **WHEN** POST `/workflows/:id:run` 返 202 + `run_id`
- **THEN** 系统 MUST 在 < 100ms 内返响应;workflow_run.status=pending;后台 asyncio task 开始执行 → status=running

#### Scenario: workflow_run 状态机
- **WHEN** 后台执行流进展
- **THEN** 状态 MUST 按 `pending → running → completed` 转换;每步状态变更 MUST 写 `workflow_run.status` 字段 + audit log 写 `workflow_status_change` event

#### Scenario: failed 终止
- **WHEN** 某节点走完 retry 后仍失败
- **THEN** workflow_run 状态 MUST 转 `failed` + `error_class` / `error_message` 写入;`ended_at = now()`;audit log 写终态 event

### Requirement: 节点重试策略
runtime 错误(LLM 5xx / HTTP 5xx / timeout)MUST 按节点 config 的 `retry_count` 默认重试 1 次(indexed backoff: 第 1 次 1s 后,第 2 次 2s 后);user / security 错误 MUST NOT 重试。eng-review Quality #3 锁定。

#### Scenario: LLM 5xx 重试
- **WHEN** LLM 节点 config retry_count=1 + audit-and-isolation 返 503
- **THEN** 系统 MUST 1s 后重试 1 次;成功则 `node_event.retry_count=1`;仍失败则 `node_event.status=failed` + `error_class=runtime`

#### Scenario: user 错误不重试
- **WHEN** 节点 config 缺必填 + Pydantic ValidationError
- **THEN** 系统 MUST NOT 重试,直接 `node_event.status=failed` + `error_class=user`;audit log 写

#### Scenario: security 错误不重试
- **WHEN** 凭证访问被拒 + `error_class=security`
- **THEN** 系统 MUST NOT 重试;直接 fail-fast(security 错误不重试,避免被攻击者滥用重试)

### Requirement: SSE 节点事件流
`GET /runs/:run_id/events` MUST 返 Server-Sent Events 流(Content-Type: text/event-stream);每个节点状态变更 MUST 推一条 event 给客户端(画布前端 / 测试)。

#### Scenario: SSE 事件格式
- **WHEN** workflow 节点 n2 进入 running 状态
- **THEN** SSE MUST 推一条 `event: node_running\ndata: {"run_id": "...", "node_id": "n2", "status": "running", "ts": "..."}\n\n`

#### Scenario: SSE 终态
- **WHEN** workflow_run.status 转到终态(`completed` / `failed` / `cancelled`)
- **THEN** SSE MUST 推一条 `event: run_completed` / `run_failed` / `run_cancelled`;SSE 连接 MUST 关闭;客户端可断连

#### Scenario: SSE 多客户端
- **WHEN** 2 个客户端同时 GET `/runs/:run_id/events`
- **THEN** 两者 MUST 都收到完整事件流(基于 `node_event` 表 polling + asyncio queue per-client)

### Requirement: workflow_run CRUD
系统 MUST 提供 7 个 endpoint(eng-review Q15 锁定):创建 / 读 latest / 列版本 / 读指定版本 / 更新 / 软删除 / 验证。

#### Scenario: 创建 workflow
- **WHEN** POST `/workflows` 携带 `{name, definition_json}`(无 ID)
- **THEN** 系统 MUST 生成新 UUID id + version=1 + 写 workflow_definition 表;返 201 + `{id, version, ...}`

#### Scenario: 更新生成新 version
- **WHEN** PUT `/workflows/:id` 携带新 `definition_json`
- **THEN** 系统 MUST 创建新 version(version+1)而非覆盖;旧 version MUST 保留(用于回滚);返 200 + `{id, version: N+1, ...}`

#### Scenario: 软删除
- **WHEN** DELETE `/workflows/:id`
- **THEN** 系统 MUST 设 `archived=true`(物理不删);`GET /workflows/:id` 返 410 Gone;不允许后续 :run 启动

### Requirement: 错误响应统一
所有 4xx / 5xx MUST 返 `{error_class, error_message, request_id}` 格式;Pydantic ValidationError 转 `error_class=user` + 中文错误消息;上游 5xx 转 `error_class=runtime`;权限错误转 `error_class=security`;eng-review Quality #3 锁定。

#### Scenario: 422 Validation
- **WHEN** POST `/workflows` 携带缺 `name` 字段的 body
- **THEN** 系统 MUST 返 422 + `{"error_class": "user", "error_message": "name 字段必填", "request_id": "..."}`

#### Scenario: 403 Security
- **WHEN** user_b 试图 PUT `/workflows/:id` 改 user_a 的 workflow
- **THEN** 系统 MUST 返 403 + `{"error_class": "security", "error_message": "无权访问该工作流", "request_id": "..."}`

#### Scenario: 502 Runtime
- **WHEN** LLM 节点调 audit-and-isolation 网关 5xx + retry 失败
- **THEN** 系统 MUST 写 `error_class=runtime` 到 `node_event` + workflow_run status=failed;`GET /runs/:run_id` 返 `error_class=runtime` + `error_message="LLM upstream 5xx after 1 retry"`

### Requirement: 健康检查
`GET /healthz` MUST 返 200(只要进程在)+ `GET /readyz` MUST 返 200(当 PostgreSQL + Redis + audit-and-isolation + credential 都可达)。K8s / docker-compose 用 readyz 决定 traffic。

#### Scenario: healthz
- **WHEN** GET `/healthz`
- **THEN** 系统 MUST 返 200 + `{"status": "ok"}`;不检查外部依赖(进程 in 即可)

#### Scenario: readyz 全通
- **WHEN** GET `/readyz` + 所有外部依赖可达
- **THEN** 系统 MUST 返 200 + `{"status": "ready", "checks": {"postgres": "ok", "redis": "ok", "audit_isolation": "ok", "credential": "ok"}}`

#### Scenario: readyz 故障
- **WHEN** audit-and-isolation 网关不可达
- **THEN** 系统 MUST 返 503 + `{"status": "not_ready", "checks": {"audit_isolation": "down"}}`;K8s / LB MUST 摘流量

### Requirement: 凭证权限检查
workflow 启动时若节点 config 引用 `credential_id`,系统 MUST 调 `credential:8000/v1/credentials/:id/access?user_id=:user_id` 验证 `started_by` 有访问权;无权限 MUST 返 403 + `error_class=security`,不允许启动 workflow_run。eng-review Quality #3 锁定。

#### Scenario: 有权限
- **WHEN** workflow 含 LLM 节点 + credential_id=cred-123 + started_by=user_a + credential service 返有权限
- **THEN** 系统 MUST 正常启动 workflow_run;audit log 写 `credential_access_granted`

#### Scenario: 无权限
- **WHEN** workflow 含 LLM 节点 + credential_id=cred-123 + started_by=user_a + credential service 返 403
- **THEN** 系统 MUST 返 403 + `error_class=security` + `error_message="无权限访问凭证 cred-123"`;audit log 写 `unauthorized_credential_access`
