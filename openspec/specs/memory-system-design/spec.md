# memory-system-design Specification

## Purpose
TBD - created by archiving change memory-system-four-layers. Update Purpose after archive.
## Requirements
### Requirement: docs/architecture.md MUST 新增 §4.3.X 段(eng-review Arch #3 锁定)

`docs/architecture.md` 必须在 §4.3.3(4 层记忆简要图)之后、§4.3.4(工具与扩展系统)之前,新增 `#### 4.3.X 4 层记忆系统详细设计(eng-review Arch #3 锁定)` 段。段内 MUST 覆盖 4 层(L1 working / L2 short-term Redis / L3 long-term PG+pgvector / L4 semantic Milvus)+ Memory Middleware 的 5 大要点:每层 MUST 含 call sites / 写入策略 / 读取策略 / 容量预估 + Memory Middleware 的 read/write API 与溢出淘汰。

#### Scenario: 段标题存在
- **WHEN** 读 `docs/architecture.md`
- **THEN** 文档 MUST 含 `#### 4.3.X 4 层记忆系统详细设计(eng-review Arch #3 锁定)` 标题

#### Scenario: 4 层全列
- **WHEN** 读 §4.3.X 段
- **THEN** 段内 MUST 出现 L1 / L2 / L3 / L4 全部 4 层,且每层 MUST 含 call site / 写入策略 / 读取策略 / 容量预估 4 要素

#### Scenario: Memory Middleware 段存在
- **WHEN** 读 §4.3.X 段
- **THEN** 段内 MUST 出现 Memory Middleware 描述,含 `read(query)` / `write(memory)` 2 个 API 与溢出淘汰策略

### Requirement: §4.3.X MUST 标注每层实现状态 + 交叉引用既有段

§4.3.X 段 MUST 标注每层是 `[EXISTING]`(已实现)或 `[FUTURE-IMPLEMENTATION]`(待实施),且 MUST 交叉引用 `§4.3.3`(简要图)、`§4.3.Y`(PII 规则集)、`§4.4`(技术栈)以及 eng-review 决策 Arch #3 / Perf #2 #3。

#### Scenario: 状态标注
- **WHEN** 读 §4.3.X 段
- **THEN** 段内 MUST 出现 `[EXISTING]` 与 `[FUTURE-IMPLEMENTATION]` 至少各 1 次

#### Scenario: 交叉引用
- **WHEN** 读 §4.3.X 段
- **THEN** 段内 MUST 出现 `§4.3.3` / `§4.3.Y` / `§4.4` 全部 3 个引用

#### Scenario: eng-review 决策引用
- **WHEN** 读 §4.3.X 段
- **THEN** 段内 MUST 出现 `Arch #3` 与 `Perf #2` 引用

### Requirement: §4.3.X MUST 列下游 spec 引用清单

§4.3.X 段 MUST 列出引用本段的下游 spec:已知 task(T2 Node Contract / T7 Workflow+Chatflow / T11 4 错误边界 / T12 5 存储预估)+ 4 个新 spec(L2 short-term / L3 long-term / L4 semantic / Memory Middleware)。

#### Scenario: 下游 spec 清单存在
- **WHEN** 读 §4.3.X 段
- **THEN** 段内 MUST 出现 T2 / T7 / T11 / T12 引用

#### Scenario: 4 个新 spec 引用
- **WHEN** 读 §4.3.X 段
- **THEN** 段内 MUST 出现 L2 / L3 / L4 / Middleware 4 个新 spec 名称引用

#### Scenario: 容量数字与 eng-review Perf #2 #3 对齐
- **WHEN** 读 §4.3.X 段
- **THEN** L4 容量预估 MUST 与 eng-review Perf #2 #3 锁定的 100GB / 1B chunks 一致

[FUTURE-IMPLEMENTATION] 本 spec 处于 pre-build 文档增量阶段,`docs/architecture.md` §4.3.X 段在 apply 阶段补全,引用 §4.3.3 简要图 + §4.3.Y PII 规则集 + §4.4 技术栈。4 层记忆的实际实现(L1 LangGraph state 已在,无需新 spec;L2 Redis client / L3 pgvector / L4 Milvus / Middleware)由后续 4 个独立 spec 实施。

