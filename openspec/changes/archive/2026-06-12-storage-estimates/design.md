# Design:5 存储量预估 §4.6 段(eng-review Perf #2)

## Context

eng-review 2026-06-10 锁定的 12 个工程决策中,Perf #2 明确"5 个存储量预估"(audit log 780GB/3mo / workflow state 500MB / Milvus 100GB / canvas JSON 500MB / MinIO docs 10TB/year)。eng-review 报告**没有**预留段名。本 spec 在 §4.5 部署架构后新增 §4.6 段集中 5 数字,**不**实施漂移监控(eng-review 没锁实施)。

仓库 0 行新代码(纯文档 spec)。L4 100GB 数字已**在** `§4.3.X` 段(本 session T3 spec 补);audit 780GB 已**在** `gateway-egress-enforcement-p0` spec + `services/audit-and-isolation/jobs/archive_audit.py`;本段是**集中 + 引用**已有数字,补充其他 3 个散落数字。

## Goals

- **G1:** §4.6 段存在,5 数字 + 计算依据 + 与 §4.3 段引用一致
- **G2:** 漂移监控标注 `[FUTURE-IMPLEMENTATION]`,V1.0+ 留 spec
- **G3:** CLAUDE.md 同步 surface `[FUTURE-IMPLEMENTATION]`
- **G4:** 顶层目录条目加 §4.6 链接

## Decisions

| ID | 决策 | 出处 |
|---|---|---|
| D1 | 段号 = §4.6(在 §4.5 部署架构后) | eng-review Perf #2 没预留段号,本 spec 决定 |
| D2 | 5 数字 + 计算依据列在 §4.6 段总览表 | eng-review 报告只给数字,本 spec 显式给计算依据 |
| D3 | L4 100GB 数字与 §4.3.X 一致,显式引用 | 避免漂移 |
| D4 | audit 780GB 数字与 gateway spec 一致,引用 §4.3.Y PII mask 节省 | 与 gateway spec 数字同源 |
| D5 | 漂移监控 `[FUTURE-IMPLEMENTATION]`,V1.0+ 留 spec | eng-review 没锁实施 |
| D6 | 漂移阈值 30%(MVP 保守值) | V1.0+ 可调 |
| D7 | 漂移告警复用 `audit-and-isolation/app/alerts.py::send_wecom()` | eng-review 既有通道,不新建 |
| D8 | 漂移监控走 K8s CronJob,每日 02:00 UTC | 沿用 audit 归档任务模式 |

## 与 source of truth 的对应关系

- `docs/architecture.md` §4.3.X L4 100GB —— **本段引用**(避免数字漂移)
- `docs/architecture.md` §4.3.Y PII mask —— **本段引用**(解释 audit 780GB 是 mask 后数字)
- `docs/architecture.md` §4.5 部署架构 —— **本段前置**
- eng-review Perf #2 锁定数字 —— **本段是设计文档对应**
- `services/audit-and-isolation/jobs/archive_audit.py` 90 天 MinIO 路径 —— **本段数字来源**

## Risks

- **R1:** 5 数字基于假设,实际漂移 —— 缓解:D6 漂移监控 + 漂移确认后 commit 修订本段
- **R2:** §4.3.X L4 100GB 与本段 Milvus 100GB 漂移 —— 缓解:本段显式引用 §4.3.X
- **R3:** gateway-egress-enforcement-p0 spec 的 audit 780GB 与本段漂移 —— 缓解:本段引用 gateway spec + archive_audit.py
- **R4:** 漂移监控未实施,实际容量超 780GB 不会被自动告警 —— 缓解:标 `[FUTURE-IMPLEMENTATION]`,V1.0+ 必做

## 跨 spec 依赖图

```
T12 (本 spec) ─┬─→ T1 数据隔离网关 引用 audit 780GB
               ├─→ T3 4 层记忆 引用 L4 100GB
               ├─→ (新) storage_monitor spec 留 V1.0+
               └─→ (新) Grafana 漂移 dashboard 留 V1.0+
```

## Migration

不适用。本 spec 是文档增量,不动现有代码。

## Open Questions(交给 apply 阶段)

- **OQ1:** 漂移监控 5 数字告警是单 store 还是聚合?决定:单 store
- **OQ2:** workflow state 500MB 是否含 LangGraph checkpoint?决定:不含
- **OQ3:** canvas JSON 500MB 是否含 Redis 实时副本?决定:含(PG + Redis 双层)
