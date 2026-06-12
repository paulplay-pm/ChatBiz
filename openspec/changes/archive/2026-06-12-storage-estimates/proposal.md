## Why

eng-review 2026-06-10 锁定的 12 个工程决策中,Perf #2 明确"5 个存储量预估"(audit log 780GB/3mo / workflow state 500MB / Milvus 100GB / canvas JSON 500MB / MinIO docs 10TB/year)。eng-review 报告里**没有**预留段名(不像 Arch #3 预留 §4.3.X)。仓库现状:5 数字**散落**(L4 100GB 在 §4.3.X / audit 780GB 在 gateway spec + jobs/archive_audit.py / 其他 3 个没显式)。本次 change 在 §4.5 部署架构后新增 §4.6 段,集中 5 数字 + 计算依据 + 漂移监控,**不**实施 `services/operations/storage_monitor.py`(留 V1.0+)。

## What Changes

**新增 design doc 段**
- From:`docs/architecture.md` 没有 §4.6 段,5 数字散落
- To:在 §4.5 部署架构后,新增 `### 4.6 存储量预估(eng-review Perf #2 锁定)` 段(约 70-100 行),含 5 数字总览表 + 计算依据 + 与 §4.3 段引用 + 漂移监控(`[FUTURE-IMPLEMENTATION]`)
- Reason:eng-review Perf #2 锁定
- Impact:`docs/architecture.md` 增量 1 段;`CLAUDE.md` 同步 surface `[FUTURE-IMPLEMENTATION]`

**顶层目录条目**
- 在 `docs/architecture.md` §4 段下加 `- [4.6 存储量预估]` 链接

**L4 100GB 数字与 §4.3.X 引用一致**
- §4.6 显式引用 §4.3.X L4 100GB(避免漂移)
- §4.6 显式引用 §4.3.Y PII mask 节省存储
- §4.6 显式引用 §4.5 部署架构(本段是 §4.5 存储量细节)

## Capabilities

### New Capabilities

- `storage-estimates`:`docs/architecture.md` §4.6 段存在 + 含 5 数字总览 + 计算依据 + 引用 §4.3.X / §4.3.Y / §4.5 + 漂移监控 `[FUTURE-IMPLEMENTATION]` 标注

### Modified Capabilities

无。本 spec 是**纯文档增量**,不修改既有 spec 的 REQUIREMENTS。

## Impact

- **新增文档段**:`docs/architecture.md` §4.6(预计 70-100 行)
- **CLAUDE.md**:加 1 行 `[FUTURE-IMPLEMENTATION]` 标记
- **目录条目**:`docs/architecture.md` §4 下加 `- [4.6 存储量预估(eng-review Perf #2 锁定)]` 链接
- **不影响代码**:不创建 service / API / schema;不写新 Python 文件
- **下游 spec 引用**:T1 数据隔离网关(audit 90 天 MinIO 路径与本段 780GB 一致)/ T3 4 层记忆(§4.3.X L4 100GB 数字一致)/(新) 漂移监控 spec
- **[FUTURE-IMPLEMENTATION]** `services/operations/storage_monitor.py` 漂移监控脚本 + K8s CronJob 留 V1.0+ spec 实施

## Non-goals

- **不**实施 `services/operations/storage_monitor.py`
- **不**实施 Grafana 漂移监控 dashboard
- **不**修改 §4.5 部署架构(已有)
- **不**修改 §4.3.X / §4.3.Y / §4.3.Z(已有)
- **不**修改 §4.4 技术栈选型
- **不**动 12 个 eng-review 决策中的任何其他 11 项
