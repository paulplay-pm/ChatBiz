# storage-estimates Specification

## Purpose
TBD - created by archiving change storage-estimates. Update Purpose after archive.
## Requirements
### Requirement: docs/architecture.md MUST 新增 §4.6 段(eng-review Perf #2 锁定)

`docs/architecture.md` 必须在 §4.5 部署架构后、参考资料(## 五、参考资料)前,新增 `### 4.6 存储量预估(eng-review Perf #2 锁定)` 段。段内 MUST 含 5 数字总览表(audit log 780GB/3mo / workflow state 500MB / Milvus 100GB / canvas JSON 500MB / MinIO docs 10TB/year)+ 数字位置 + 保留期 + eng-review Perf #2 引用 + 每数字计算依据 + 与既有 §4.3 段引用一致。

#### Scenario: 段标题存在
- **WHEN** 读 `docs/architecture.md`
- **THEN** 文档 MUST 含 `### 4.6 存储量预估(eng-review Perf #2 锁定)` 标题

#### Scenario: 5 数字全列
- **WHEN** 读 §4.6 段
- **THEN** 段内 MUST 出现 5 数字(780GB/3mo / 500MB / 100GB / 500MB / 10TB/year)+ 各自存储(audit log / workflow state / Milvus / canvas JSON / MinIO docs)

#### Scenario: 计算依据
- **WHEN** 读 §4.6 段
- **THEN** 段内 MUST 出现每数字的计算依据(行数 / 大小 / 副本 / 索引估算)

#### Scenario: eng-review 决策引用
- **WHEN** 读 §4.6 段
- **THEN** 段内 MUST 出现 `Perf #2` 引用

### Requirement: §4.6 MUST 引用既有 §4.3 段(避免数字漂移)

§4.6 段 MUST 显式引用 `§4.3.X 4 层记忆系统详细设计`(L4 100GB 数字一致)+ `§4.3.Y PII 规则集`(解释 audit 780GB 是 mask 后数字)+ `§4.5 部署架构`(本段是 §4.5 存储量细节)。

#### Scenario: 引用 §4.3.X
- **WHEN** 读 §4.6 段
- **THEN** 段内 MUST 出现 `§4.3.X` 引用,说明 L4 100GB 数字一致

#### Scenario: 引用 §4.3.Y
- **WHEN** 读 §4.6 段
- **THEN** 段内 MUST 出现 `§4.3.Y` 引用,说明 audit 780GB 是 PII mask 后数字

#### Scenario: 引用 §4.5
- **WHEN** 读 §4.6 段
- **THEN** 段内 MUST 出现 `§4.5` 引用,说明本段是 §4.5 存储量细节

### Requirement: 漂移监控 MUST 标 `[FUTURE-IMPLEMENTATION]`,V1.0+ 留 spec

§4.6 段 MUST 标注漂移监控(`services/operations/storage_monitor.py` + K8s CronJob + 阈值 30% + 复用 `alerts.py::send_wecom()`) 为 `[FUTURE-IMPLEMENTATION]`,V1.0+ 留 spec 实施。**不**在当前 spec 实施。

#### Scenario: 漂移监控标注
- **WHEN** 读 §4.6 段
- **THEN** 段内 MUST 出现 `[FUTURE-IMPLEMENTATION]` 标记,**不**出现 storage_monitor.py 实际代码

#### Scenario: V1.0+ 留 spec 引用
- **WHEN** 读 §4.6 段
- **THEN** 段内 MUST 出现下游 spec 引用清单,含"漂移监控 spec 留 V1.0+"

[FUTURE-IMPLEMENTATION] 本 spec 处于 pre-build 文档增量阶段,`docs/architecture.md` §4.6 段在 apply 阶段补全,引用 §4.3.X / §4.3.Y / §4.5。`services/operations/storage_monitor.py` 漂移监控脚本 + K8s CronJob 留 V1.0+ 独立 spec 实施。

