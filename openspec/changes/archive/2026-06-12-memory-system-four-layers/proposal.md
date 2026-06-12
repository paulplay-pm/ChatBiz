## Why

eng-review 2026-06-10 锁定的 12 个工程决策中,Arch #3 明确"§4.2 列出 4 层记忆架构,但 §4.3 没有详细设计"。eng-review 报告里**已预留 §4.3.X 段**作为本 spec 的目标位置。仓库 `docs/architecture.md` 现状:§4.3.3 已有 4 层记忆的**简要图**(L1/L2/L3/L4 各 1 段),但**call sites / 写入策略 / 读取策略 / 容量预估 / Memory Middleware 集成点全部空白**。本次 change 补 §4.3.X 段(eng-review #3 锁定的设计文档),**不**实现 4 层记忆的 service / API / schema(实现分散在 L2/L3/L4 多个 spec,跨 team 推进,本 spec 不抢)。

## What Changes

**文档段补全**(eng-review Arch #3 锁定)
- From:`docs/architecture.md` §4.3.3 之后没有 §4.3.X 段(eng-review 报告预留段空白)
- To:在 §4.3.3 之后新增 §4.3.X 段(约 200-300 行),覆盖 4 层记忆的详细设计:每层的存储 / 生命周期 / call site / 写入策略 / 读取策略 / 容量预估 + Memory Middleware
- Reason:eng-review Arch #3 锁定"补 §4.3.X 详细设计"
- Impact:`docs/architecture.md` 增量 1 段;**CLAUDE.md** 同步 surface `[FUTURE-IMPLEMENTATION]`

**交叉引用**
- §4.3.X 引用 §4.3.3(简要图)
- §4.3.X 引用 §4.3.Y(PII 规则集,L4 文档上传前 PII 扫描)
- §4.3.X 引用 §4.4 技术栈选型(Milvus / pgvector / Redis / PG)

**CLAUDE.md surface**
- 在 §4.3 之后、`## 已锁定的工程决策` 之前,加 `[FUTURE-IMPLEMENTATION] docs/architecture.md §4.3.X 4 层记忆详细设计即将在 memory-system-four-layers apply 阶段补全`

## Capabilities

### New Capabilities

- `memory-system-design`:`docs/architecture.md` §4.3.X 段落存在,内容覆盖 4 层记忆(L1 working / L2 short-term Redis / L3 long-term PG+pgvector / L4 semantic Milvus)+ Memory Middleware 5 大要点(call sites / 写入策略 / 读取策略 / 容量预估 / 与 Agent/Workflow runtime 集成点),引用 §4.3.3(简要图)与 §4.3.Y(PII 规则集)

### Modified Capabilities

无。本 spec 是**纯文档增量**,不修改既有 spec 的 REQUIREMENTS。

## Impact

- **新增文档段**:`docs/architecture.md` §4.3.X(预计 200-300 行)
- **CLAUDE.md**:加 1 行 `[FUTURE-IMPLEMENTATION]` 标记
- **目录条目**:`docs/architecture.md` 目录中加 `- [4.3.X 4 层记忆详细设计]` 条目
- **不影响代码**:不创建 service / API / schema;不写新 Python 文件
- **下游 spec 引用**:T2 Node Contract / T7 Workflow+Chatflow / T11 4 错误边界 / (新) L2 / (新) L3 / (新) L4 / (新) Memory Middleware 都会引用 §4.3.X
- **[FUTURE-IMPLEMENTATION]** 4 层记忆的实际实现(L2 Redis client / L3 pgvector 表 / L4 Milvus collection / Middleware service)由后续 4 个独立 spec 实施,本 spec 不抢

## Non-goals

- **不**实现 4 层记忆的 service / API / schema
- **不**创建 `services/memory/` 目录
- **不**实现 Memory Middleware 代码
- **不**修改 §4.3.3(已有 4 层图)
- **不**修改 §4.3.Y(PII 规则集,刚由 gateway-egress-enforcement-p0 spec 补)
- **不**修改 §4.4 技术栈选型
- **不**动 12 个 eng-review 决策中的任何其他 11 项
