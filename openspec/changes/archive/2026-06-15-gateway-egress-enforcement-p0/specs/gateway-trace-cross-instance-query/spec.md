## ADDED Requirements

### Requirement: 必须暴露 `GET /v1/traces/{trace_id}` 跨实例查询端点 (MUST)
(MUST)
`services/audit-and-isolation/app/api/traces.py` 必须实现 `GET /v1/traces/{trace_id}` 端点,从 Redis(`trace:cache:*` namespace,db 0,5min TTL)优先查询 → PG `audit_log` 表降级 → 404(都无)。端点必须支持跨实例查询:实例 A 写入的 trace 必须能被实例 B 查到。

#### Scenario: Redis 命中
- **WHEN** 调用 `GET /v1/traces/{trace_id}`,Redis 中存在 `trace:cache:{trace_id}` key
- **THEN** 端点返回该 trace 关联的所有事件(从 `audit_log` 行还原),按 `created_at` 升序,P99 < 100ms

#### Scenario: Redis miss + PG 命中
- **WHEN** Redis 中无 key,但 `audit_log` 表中存在匹配 `trace_id` 的行
- **THEN** 端点从 PG 查询并返回完整事件列表,P99 < 500ms,异步回填 Redis 缓存 5min TTL

#### Scenario: 都不命中
- **WHEN** Redis 与 PG `audit_log` 均无该 `trace_id` 记录
- **THEN** 端点返回 404,响应体 `{"error": "trace_not_found", "trace_id": "..."}`

#### Scenario: 跨实例查询
- **WHEN** 实例 A 写入 audit_log(trace_id=X),实例 B 收到 `GET /v1/traces/X` 请求
- **THEN** 实例 B 从 PG 查到(Redis 在 5min 内也命中),返回完整事件列表

### Requirement: trace 端点必须使用独立的 Redis namespace 避免污染 canvas realtime (MUST)
(MUST)
trace 缓存必须使用 `trace:cache:*` key prefix 与 Redis db 0,与 `services/audit-and-isolation` 现有的 PII 反向映射(per-trace,30min TTL)共用 db 0 但不同 prefix。`web/canvas/` 实时状态若未来使用 Redis,必须用 db 1 隔离(D2.2 锁定)。

#### Scenario: namespace 隔离
- **WHEN** trace 缓存写入 `trace:cache:{trace_id}` key
- **THEN** PII 反向映射的 `pii:rev:{trace_id}` key 不受影响,eviction policy 分别配置

### Requirement: trace_id 格式必须兼容现有透传模式 (MUST)
(MUST)
调用方传 `X-Trace-Id` 时,网关必须复用,不再生成;缺失时网关必须生成 UUIDv7 作为兜底。生成器实现在 `services/audit-and-isolation/app/trace/id_gen.py`(DC3 决策)。

#### Scenario: 透传已有 trace_id
- **WHEN** 请求携带 `X-Trace-Id` 头(格式合法)
- **THEN** 网关必须复用该 `trace_id`,不再生成新值,也不校验其与 UUIDv7 格式一致

#### Scenario: 缺失 trace_id
- **WHEN** 请求未携带 `X-Trace-Id`
- **THEN** 网关必须生成新的 UUIDv7 作为 `trace_id`,写入 `audit_log`,响应头 `X-Trace-Id` 返回

[FUTURE-IMPLEMENTATION] 本 spec 处于 pre-build 增量阶段,`app/api/traces.py` + `app/trace/id_gen.py` + `app/trace/store.py` 在 apply 阶段落地;`audit_log` 表已由 `alembic/versions/001_create_audit_log.py` 实现,本 spec **不**修改表结构,只新增查询端点。Redis 写入逻辑 `app/redis_client.py` 已存在,本 spec 加 1 个 `set_trace_cache` / `get_trace_cache` 包装方法。
