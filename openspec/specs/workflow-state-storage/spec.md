# workflow-state-storage Specification

## Purpose
TBD - created by archiving change implement-workflow-engine. Update Purpose after archive.
## Requirements
### Requirement: 5 张业务表 schema
系统 MUST 在 PostgreSQL `workflow_engine` database 创建 5 张表:`workflow_definition` / `workflow_run` / `node_event` / `approval` + LangGraph 官方 `checkpoints`(由 `langgraph-checkpoint-postgres` 包自动创建)。所有字段类型 MUST 与 Pydantic 模型严格对应。

#### Scenario: workflow_definition 表
- **WHEN** Alembic migration 执行 `001_workflow_definition.py`
- **THEN** 系统 MUST 创建 `workflow_definition` 表:列 `(id UUID PK, version INT NOT NULL, name TEXT NOT NULL, created_by TEXT NOT NULL, definition_json JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), archived BOOLEAN NOT NULL DEFAULT false)`;唯一约束 `(id, version)`;索引 `(id, version DESC)` 用于 latest version 查询

#### Scenario: workflow_run 表
- **WHEN** Alembic migration 执行 `002_workflow_run.py`
- **THEN** 系统 MUST 创建 `workflow_run` 表:列 `(run_id UUID PK, workflow_id UUID NOT NULL, workflow_version INT NOT NULL, thread_id TEXT NOT NULL, mode TEXT NOT NULL CHECK (mode IN ('workflow', 'chatflow')), status TEXT NOT NULL CHECK (status IN ('pending','running','paused','completed','failed','cancelled')), started_by TEXT NOT NULL, started_at TIMESTAMPTZ NOT NULL DEFAULT now(), ended_at TIMESTAMPTZ, error_class TEXT, error_message TEXT)`;索引 `(workflow_id, started_at DESC)` + `(thread_id)`(chatflow 关联)

#### Scenario: node_event 表
- **WHEN** Alembic migration 执行 `003_node_event.py`
- **THEN** 系统 MUST 创建 `node_event` 表:列 `(id BIGSERIAL PK, run_id UUID NOT NULL, node_id TEXT NOT NULL, status TEXT NOT NULL CHECK (status IN ('pending','running','completed','failed','skipped')), input_json JSONB, output_json JSONB, started_at TIMESTAMPTZ, ended_at TIMESTAMPTZ, retry_count INT NOT NULL DEFAULT 0, error_class TEXT, error_message TEXT)`;外键 `run_id` → `workflow_run.run_id` ON DELETE CASCADE;索引 `(run_id, started_at)` 用于节点时间线查询

#### Scenario: approval 表
- **WHEN** Alembic migration 执行 `004_approval.py`
- **THEN** 系统 MUST 创建 `approval` 表:列 `(approval_id UUID PK, run_id UUID NOT NULL, node_id TEXT NOT NULL, approver_user_id TEXT NOT NULL, status TEXT NOT NULL CHECK (status IN ('pending','approved','rejected','timeout','cancelled')), created_at TIMESTAMPTZ NOT NULL DEFAULT now(), responded_at TIMESTAMPTZ, response_payload JSONB)`;外键 `run_id` → `workflow_run.run_id` ON DELETE CASCADE;索引 `(approver_user_id, status, created_at)` 用于查待审批

#### Scenario: langgraph_checkpoints 表
- **WHEN** langgraph-checkpoint-postgres 包首次连接 PostgreSQL
- **THEN** 系统 MUST 通过 `AsyncPostgresSaver.setup()` 自动创建 LangGraph 官方表 `checkpoints`(列 + 索引由 LangGraph 决定);不允许手动 schema 改动(避免升级 LangGraph 时不兼容)

### Requirement: 数据回滚
Alembic MUST 支持 `alembic downgrade -1` 回滚上一 migration;所有 down revision MUST 重建 schema 到上一稳定状态。多 migration chain 合并时 MUST 无 schema 冲突。

#### Scenario: 单步回滚
- **WHEN** DBA 跑 `alembic downgrade -1` 从 `head` 回退一版
- **THEN** 系统 MUST 删最近一张业务表(保留 LangGraph 表)+ 数据保留由 backup 负责(alembic 不备份数据)

#### Scenario: 多版本升级
- **WHEN** DBA 跑 `alembic upgrade head` 跨多 migration
- **THEN** 系统 MUST 顺序执行所有 migration 无错误;每步 migration 必须是 idempotent(重复跑不出错)

### Requirement: 多租户隔离
workflow_definition.created_by / workflow_run.started_by MUST 是租户/用户 ID(目前是内部 username 字符串,V1.0+ 接 IAM 后切 UUID);所有 SELECT / UPDATE 端点 MUST 检查 created_by / started_by == request.user_id(隔离强制;非工作流 owner MUST NOT 读 / 改)。

#### Scenario: 跨用户访问拒绝
- **WHEN** user_a 创建 workflow_definition,user_b 发 GET `/workflows/:id`
- **THEN** 系统 MUST 返 403 + `error_class=security` + audit log 写 `unauthorized_workflow_access`(即使 workflow_definition 存在)

#### Scenario: 跨用户修改拒绝
- **WHEN** user_b 发 PUT `/workflows/:id` 试图更新 user_a 的 workflow
- **THEN** 系统 MUST 返 403;不允许写入 + 不允许更新 version

### Requirement: 索引性能
5 张表的索引 MUST 支持以下 query pattern 全部 < 100ms(本地 PG,1k workflow / 100k node_event):latest version 查询 / workflow_run 历史查询 / node_event 时间线查询 / approval 待审批查询。

#### Scenario: latest version 查询 < 100ms
- **WHEN** `SELECT * FROM workflow_definition WHERE id=? ORDER BY version DESC LIMIT 1`
- **THEN** 系统 MUST < 100ms(索引 `(id, version DESC)` 命中)

#### Scenario: node_event 时间线查询 < 200ms
- **WHEN** `SELECT * FROM node_event WHERE run_id=? ORDER BY started_at`(单 run 100 节点)
- **THEN** 系统 MUST < 200ms(索引 `(run_id, started_at)` 命中)

#### Scenario: approval 待审批查询 < 100ms
- **WHEN** `SELECT * FROM approval WHERE approver_user_id=? AND status='pending' ORDER BY created_at`(单用户 50 待审批)
- **THEN** 系统 MUST < 100ms(索引 `(approver_user_id, status, created_at)` 命中)

### Requirement: 数据保留策略
audit_log 类(workflow_run / node_event)MUST 保留 ≥ 90 天(MVP);workflow_definition / approval 永久保留(只要 `archived=false`)。后台 cron(apscheduler)每周扫一次,删除 90 天前 `status IN ('completed','failed','cancelled')` 的 workflow_run + 关联 node_event。

#### Scenario: 90 天后清理
- **WHEN** cron 扫到 workflow_run.status=completed 且 ended_at < now() - 90 days
- **THEN** 系统 MUST 删 workflow_run + 关联 node_event(CASCADE 触发);保留 workflow_definition 不动;保留 audit_log(独立 780GB MinIO 存储估算,eng-review Perf #2)

#### Scenario: 永久保留字段
- **WHEN** 清理 cron 跑
- **THEN** 系统 MUST NOT 删 `workflow_definition` / `approval` 表(永久保留);只删 `workflow_run` / `node_event`

