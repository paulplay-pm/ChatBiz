## ADDED Requirements

### Requirement: LLM echo stub 集成

audit-and-isolation 网关在 dev/test 环境 MUST 集成 LLM echo stub(返回固定 mock 响应),用于 e2e + 集成测试不需要真实 LLM provider 的场景。生产环境不启用 stub。

#### Scenario: dev 环境 LLM echo stub

- **WHEN** audit-and-isolation 网关收到 LLM 调用请求且 `ENV = dev | test`
- **THEN** 网关走 stub 分支,返固定响应 `{"echo":true,"tokens_used":100,"mock":true,"latency_ms":50}`,不调真实 LLM provider
- **THEN** stub 调用写 audit log,`event_type = "llm_echo_stub"` 区分真实调用

### Requirement: Redis Sentinel HA 配置

audit-and-isolation 网关 2 实例 MUST 通过 Redis Sentinel 做状态共享(workflow state 双层架构的 Redis 层),Sentinel 监控 + 自动 failover < 30s。

#### Scenario: Sentinel failover

- **WHEN** 主 Redis 实例 down
- **THEN** Sentinel 在 30s 内选举新主,audit-and-isolation 实例自动切到新主
- **THEN** 切主期间不接受新 LLM 调用(返 `503 Service Unavailable`),已建立的 SSE 流标记断流让客户端重连

### Requirement: trace-id 跨 service 关联

audit-and-isolation MUST 在每个 LLM 调用注入 `X-Trace-Id` header,该 trace-id 跨 workflow-engine / agent-runtime / mcp / credential 等所有下游 service 传递并写各自 audit log。

#### Scenario: trace-id 注入 + 跨服务传递

- **WHEN** portal 发 LLM 调用请求到 audit-and-isolation 网关
- **THEN** 网关生成 `trace_id = uuid()`,注入 response header `X-Trace-Id` + 写自身 audit log
- **THEN** 网关转发请求到下游 service 时,保留 `X-Trace-Id` 在 request header
- **THEN** 下游 service 写 audit log 时,把 `trace_id` 写入 `audit_log.trace_id` 字段
- **THEN** admin `/audit-logs` 页面支持按 `trace_id` 跨服务查询完整调用链

### Requirement: 4 错误边界契约

audit-and-isolation MUST 区分 4 类错误边界,每类有独立错误类 + HTTP status code + error code + 前端展示策略。

#### Scenario: 4 错误类

- **WHEN** 网关拒绝请求
- **THEN** 返 HTTP status + error code 如下:
  - `SecurityError` → 401 / 403,error_code `security.unauthorized` / `security.forbidden`
  - `UserError` → 400,error_code `user.invalid_input` / `user.missing_param`
  - `WorkflowRuntimeError` → 502 / 504,error_code `runtime.llm_5xx` / `runtime.llm_timeout` / `runtime.quota_exceeded`
  - `audit-and-isolation/errors.py` 7 类 → 500,error_code `internal.<具体子类>`
- **THEN** 前端 toast 根据 error_code 类别显示对应文案 + 建议操作(重试 / 重新登录 / 联系 admin)
