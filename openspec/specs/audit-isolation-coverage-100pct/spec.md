# audit-isolation-coverage-100pct Specification

## Purpose
TBD - created by archiving change coverage-improvement. Update Purpose after archive.
## Requirements
### Requirement: archive_audit 模块 100% 单元测试覆盖 (MUST)
(MUST) 模块 `app/jobs/archive_audit.py` 的 `ArchiveResult.duration_seconds`
property 与 `archive_old_audit_logs` 的"row-count-mismatch 警告"
分支必须拥有可执行的 pytest 单元测试，使该模块通过
`pytest-cov` 达到 100% line coverage。

#### Scenario: `duration_seconds` property 返回 wall-clock 秒数
- **WHEN** 构造 `ArchiveResult`，`started_at` 与 `finished_at` 相差
  5 秒
- **THEN** `result.duration_seconds` MUST 等于 `5.0`
- **AND** 该测试 MUST 不需要数据库或 S3 连接（纯 dataclass 构造）

#### Scenario: `archive_old_audit_logs` 在 S3 上传 N 行但 DELETE
返回 M≠N 行时记录 warning
- **WHEN** S3 `head_bucket` 成功、S3 `put_object` 全部成功、但 PG
  DELETE `rowcount` ≠ `rows_uploaded`
- **THEN** `logger.warning` MUST 被以包含 "row count mismatch"
  字符串的消息调用至少一次
- **AND** 返回的 `ArchiveResult.rows_deleted` MUST 等于
  DELETE 实际 `rowcount`（不是 upload 计数）
- **AND** `ArchiveResult.rows_uploaded` MUST 等于 S3 成功上传的行数
- **AND** 该测试 MUST 通过 `asyncio.run(...)` 在 sync test 内
  调用 async `archive_old_audit_logs`，并使用 `_FakeSelectSession`
  / `_FakeDeleteSession` 替代真实 SQLAlchemy session

### Requirement: llm/client.compute_idempotency_key 100% 单元测试覆盖 (MUST)
(MUST) 函数 `compute_idempotency_key`（定义于 `app/llm/client.py`）
对非 dict / 非 str 类型 body 的 fallback 分支必须拥有可执行的
pytest 单元测试，使该函数达到 100% line coverage。

#### Scenario: `compute_idempotency_key` 接受 int 类型 body
- **WHEN** 调用 `compute_idempotency_key("user-1", 12345, now=1_700_000_000.0)`
- **THEN** 返回值 MUST 是 64 字符的 hex SHA-256 字符串
- **AND** 返回值 MUST 仅包含字符 `0123456789abcdef`

#### Scenario: `compute_idempotency_key` 接受 `None` body
- **WHEN** 调用 `compute_idempotency_key("user-1", None, now=1_700_000_000.0)`
- **THEN** 返回值 MUST 是 64 字符的 hex SHA-256 字符串
- **AND** 该测试 MUST 验证 `else` 分支（`str(None).encode("utf-8")`
  fallback）的行为

### Requirement: routing/table 模块 100% 单元测试覆盖 (MUST)
(MUST) 模块 `app/routing/table.py` 的 `load_routing` / `get_routing` 全
路径必须拥有可执行的 pytest 单元测试，使该模块通过
`pytest-cov` 达到 100% line coverage。覆盖路径必须包括：
in-memory + Redis pipeline 同步写入、Redis 写入失败的容错、
Redis hit 命中、Redis miss 降级到 in-memory、Redis 不可用时
的容错、未知 model 返回 `None`、Redis 返回 garbage data 时的
fallback。

#### Scenario: `load_routing` 同步填充 in-memory 与 Redis pipeline
- **WHEN** 传入 1 个有效 model 行触发 `load_routing`
- **THEN** in-memory 缓存 MUST 包含该 model
- **AND** Redis pipeline MUST 收到 `set` 调用

#### Scenario: `load_routing` 在 Redis 写入失败时继续返回成功
- **WHEN** Redis pipeline `set` 抛 `RedisError`
- **THEN** `load_routing` MUST 不抛异常（容错）
- **AND** in-memory 缓存 MUST 仍然被填充

#### Scenario: `get_routing` 在 Redis hit 时返回缓存项
- **WHEN** Redis `get` 返回非空 bytes
- **THEN** `get_routing` MUST 返回 `Rout` 对象（in-memory
  之外的 cache 命中路径）
- **AND** MUST 不查询 in-memory 缓存

#### Scenario: `get_routing` 在 Redis miss 时降级到 in-memory
- **WHEN** Redis `get` 返回 `None` 或空
- **THEN** `get_routing` MUST 查 in-memory 缓存
- **AND** 若 in-memory 命中 MUST 返回该 `Rout` 对象

#### Scenario: `get_routing` 在 Redis 不可用时降级到 in-memory
- **WHEN** Redis 客户端抛 `RedisError` 或连接异常
- **THEN** `get_routing` MUST 降级到 in-memory 缓存
- **AND** MUST 不把异常传播给调用方

#### Scenario: `get_routing` 在未知 model 时返回 `None`
- **WHEN** 传入 `model_id` 不在 in-memory 缓存中
- **THEN** `get_routing` MUST 返回 `None`
- **AND** MUST 不抛异常

#### Scenario: `get_routing` 在 Redis 返回 garbage data 时降级
- **WHEN** Redis `get` 返回非预期类型（既非 `None` 也非合法 bytes）
- **THEN** `get_routing` MUST 降级到 in-memory 缓存
- **AND** MUST 不抛异常给调用方

### Requirement: 测试套件位置与命名规范
两个测试文件 MUST 落在
`services/audit-and-isolation/tests/unit/` 目录下，文件名分别为
`test_coverage_gaps_v1_followup.py` 与
`test_routing_table_coverage.py`，与 `audit-and-isolation` 已
有测试目录的命名风格保持一致。

#### Scenario: 测试文件位置与命名
- **WHEN** 任何 followup 协作者运行 `pytest --collect-only
  services/audit-and-isolation/tests/unit/`
- **THEN** MUST 列出 2 个新文件 + 已有测试文件
- **AND** 文件名 MUST 严格匹配 `test_coverage_gaps_v1_followup.py`
  与 `test_routing_table_coverage.py`

### Requirement: pytest 收集与运行产物可预期 (MUST)
(MUST) 运行 `pytest tests/unit/test_coverage_gaps_v1_followup.py
tests/unit/test_routing_table_coverage.py` 必须产出确定性的
结果集合（在 `services/audit-and-isolation` V1.0+ 阶段、conda
环境 `chatbiz` 激活状态下），CI 可据此判定通过/失败。

#### Scenario: 测试运行结果
- **WHEN** 在 `services/audit-and-isolation` 目录下运行
  `pytest tests/unit/test_coverage_gaps_v1_followup.py
  tests/unit/test_routing_table_coverage.py --no-cov`
- **THEN** 12 个测试 MUST PASS，1 个测试 MUST SKIP
  （`test_retry_with_idempotency_raises_unreachable_no_result`，
  skip 理由为 `client.py:304` 是 defensive unreachable 分支）
- **AND** MUST 不出现 FAILED 或 ERROR
- **AND** SKIP 的 test docstring MUST 显式引用
  `retry_with_redis:121` 的 `# pragma: no cover` 约定

### Requirement: 既有生产代码契约不变
本 change MUST 不修改 `app/jobs/archive_audit.py`、
`app/llm/client.py`、`app/routing/table.py` 三个目标模块的
任何生产代码；本 change 是纯测试 followup。

#### Scenario: production diff 为零
- **WHEN** 本 change apply 完成，`git diff HEAD~<N> HEAD --
  services/audit-and-isolation/app/jobs/archive_audit.py
  services/audit-and-isolation/app/llm/client.py
  services/audit-and-isolation/app/routing/table.py`
- **THEN** 输出 MUST 为空（diff 为零字节）
- **AND** 反之，若 diff 非空则本 change 违反 "non-breaking
  test followup" 约束，必须回滚

