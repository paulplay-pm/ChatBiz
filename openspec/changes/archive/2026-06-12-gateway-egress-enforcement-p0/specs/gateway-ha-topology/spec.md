## ADDED Requirements

### Requirement: audit-and-isolation 必须以 2 实例 active-active 模式部署

MUST `services/audit-and-isolation/` 在生产环境必须以 Kubernetes Deployment `replicas=2` active-active 模式部署。任一实例故障时,前置 NGINX stream L4 LB 必须在 5 秒内将流量切换到健康实例,请求中的 `X-Trace-Id` 在实例 B 上仍可被 `GET /v1/traces/{trace_id}` 关联查询(依赖 4.1 trace 端点)。
#### Scenario: 单实例故障自动切换
- **WHEN** audit-and-isolation 实例 A 出现进程崩溃或健康检查失败
- **THEN** NGINX L4 LB 在 5 秒内停止向实例 A 转发新连接,新请求由实例 B 处理,跨实例 trace 查询可命中

#### Scenario: 双实例同时健康
- **WHEN** 两个实例均通过 `/healthz` 报告健康
- **THEN** NGINX L4 LB 以轮询策略将请求均分,任一实例承载流量比例不低于 30%


### Requirement: preStop 排空机制必须给 in-flight 请求 30s 完成时间

MUST Kubernetes 部署必须配置 `preStop` lifecycle hook,实例在收到 SIGTERM 后必须停止接受新连接,已建立的 in-flight 请求有最多 30 秒完成时间。客户端 SDK 必须实现 `Idempotency-Key` 幂等重试器以配合排空。
#### Scenario: 实例优雅下线
- **WHEN** Kubernetes 向某实例发送 SIGTERM(滚动更新或主动驱逐)
- **THEN** 实例在 1 秒内停止接受新连接(`/healthz` 返回 503),已建立的 in-flight 请求有最多 30 秒完成时间,`terminationGracePeriodSeconds=45s`(30s 排空 + 15s 缓冲),45s 后强制关闭

#### Scenario: 客户端重试
- **WHEN** 客户端 SDK 收到 `503 HA_FAILOVER` 状态码或连接被中断
- **THEN** SDK 必须使用相同的 `Idempotency-Key` 在 5 秒内向另一个实例重试请求,最多 3 次


### Requirement: 健康检查端点必须返回完整依赖状态

MUST `/healthz` 端点必须返回 200(健康)或 503(不健康),响应体包含 PostgreSQL 连接状态、Redis 连接状态、最近 30s 错误率三个字段。L4 LB 每 5 秒调用一次,连续 2 次失败才标记实例不健康。
#### Scenario: 所有依赖健康
- **WHEN** PostgreSQL 可连接、Redis 可连接、最近 30s 错误率 < 1%
- **THEN** `/healthz` 返回 200,响应体 `{"status": "healthy", "pg": "ok", "redis": "ok", "error_rate_30s": 0.002}`

#### Scenario: Redis 不可用
- **WHEN** Redis 连接失败
- **THEN** `/healthz` 返回 503,响应体 `{"status": "degraded", "pg": "ok", "redis": "down", "error_rate_30s": 0.0}`,L4 LB 在 5+5=10 秒后停止向该实例转发流量


### Requirement: 客户端 SDK 必须实现 `RetryWithIdempotency` 装饰器

MUST `services/audit-and-isolation/app/llm/client.py` 必须实现 `RetryWithIdempotency` 装饰器,基于 `Idempotency-Key`(SHA-256 of `user_id + body_hash + 5min_timestamp_bucket`),仅对 `503 HA_FAILOVER` 与连接中断触发重试,5s 内最多 3 次,不影响现有 5xx 上游重试(1 次)。

#### Scenario: HA failover 重试
- **WHEN** 网关返回 `503 HA_FAILOVER` 状态码
- **THEN** 客户端 SDK 必须在 5 秒内向另一个实例重试,使用相同 `Idempotency-Key`,最多 3 次,3 次后抛出 `HAFailoverExhausted` 异常

#### Scenario: 不与上游 5xx 重试叠加
- **WHEN** 网关返回 5xx(非 503 HA_FAILOVER)
- **THEN** 客户端 SDK **不**触发 `RetryWithIdempotency`,走现有 LLM 上游 1 次 5xx 重试逻辑

[FUTURE-IMPLEMENTATION] 本 spec 处于 pre-build 增量阶段,`deploy/audit-and-isolation/`(Deployment + Service + PDB + nginx.conf)与 `services/audit-and-isolation/app/llm/client.py` `RetryWithIdempotency` 装饰器在 apply 阶段落地。现有 `/healthz` 端点已由 `app/api/health.py` 实现(覆盖 1 个 requirement,本 spec 不重写)。
