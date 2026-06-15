# audit-cold-archive Specification

## Purpose
TBD - created by archiving change gateway-egress-enforcement-p0. Update Purpose after archive.
## Requirements
### Requirement: 90 天后 audit_log 数据必须归档到 MinIO (MUST)
(MUST)
`services/audit-and-isolation/jobs/archive_audit.py` 定时任务必须每日 02:00 UTC 跑一次,把 `audit_log` 表中 `created_at` 超过 90 天的行 COPY 到 MinIO `s3://chatbiz-audit-cold/yyyy/mm/dd.parquet`,PG 端 DELETE。归档任务部署为 K8s CronJob,失败时 PG 端保留数据,下次重试(断点续传)。

#### Scenario: 正常归档
- **WHEN** 定时任务触发,PG 中有 1000 行超过 90 天的 audit_log
- **THEN** 1000 行被 COPY 到 MinIO `s3://chatbiz-audit-cold/2026/03/15.parquet`,PG 端 DELETE 1000 行,任务日志记录归档行数

#### Scenario: MinIO 不可用
- **WHEN** MinIO 连接失败或上传超时
- **THEN** 归档任务跳过本次删除,PG 端数据保留,日志记录失败原因与下次重试时间

#### Scenario: 归档数据完整性
- **WHEN** 归档成功后
- **THEN** MinIO parquet 文件可被独立工具读回,字段与 PG `audit_log` 表完全一致(14 字段)

### Requirement: 必须提供 `GET /v1/audit/archive` 冷查询端点 (MUST)
(MUST)
`services/audit-and-isolation/app/api/audit_archive.py` 必须实现 `GET /v1/audit/archive?from=...&to=...&user_id=...&page=...&page_size=...`,从 MinIO 拉 parquet 异步返回,响应头 `X-Audit-Source: cold`,MinIO 失败返回 503。

#### Scenario: 冷数据查询成功
- **WHEN** 客户端调用 `GET /v1/audit/archive?from=2026-03-01&to=2026-03-15&user_id=paul`
- **THEN** 端点从 MinIO 拉取对应日期的 parquet 文件,过滤 `user_id=paul`,分页返回,响应头 `X-Audit-Source: cold`,响应体包含 `data[]` 与 `pagination{total, page, page_size}`

#### Scenario: MinIO 不可用
- **WHEN** MinIO 连接失败
- **THEN** 端点返回 503,响应体 `{"error": "archive_unavailable"}`,不返回部分数据

#### Scenario: 日期范围超出 MinIO retention
- **WHEN** 查询的 from/to 超出 MinIO 实际保留范围(如 MinIO 已清理 3 年前数据)
- **THEN** 端点返回 200 + 空数据 `{"data": [], "pagination": {"total": 0}}`,响应头 `X-Audit-Source: cold,partial`

### Requirement: 归档容量预估必须与 eng-review Perf #2 #1 对齐 (MUST)
(MUST)
PG 热数据预估 90 天 × 50K 事件/天 × 2KB/事件 ≈ 9GB(远低于 PG 容量);MinIO 冷数据预估 780GB/3mo(eng-review Perf #2 #1 锁定);MinIO retention 3 年。

#### Scenario: 容量校验
- **WHEN** 归档任务跑完一个完整 90 天周期
- **THEN** MinIO `s3://chatbiz-audit-cold/` 总大小应在 250-280GB 范围(与 780GB/3mo 推算一致),超过 320GB 触发告警

[FUTURE-IMPLEMENTATION] 本 spec 处于 pre-build 增量阶段,`jobs/archive_audit.py` + `app/api/audit_archive.py` + K8s CronJob manifest 在 apply 阶段落地。`audit_log` 表已由 `alembic/versions/001_create_audit_log.py` 实现,本 spec **不**修改表结构。

