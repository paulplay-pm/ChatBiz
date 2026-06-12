<!--
Raw capture of superpowers:brainstorming output for change `storage-estimates`.
设计来源:eng-review 2026-06-10 锁定的 Perf #2(locked-in,不再重新讨论)。
eng-review 原始 finding(逐字引用):
> Perf #2 (P1, 7/10) — Only audit log storage estimated.
> Resolution: 5 个存储量预估. (1) audit log 780GB/3mo MinIO cold; (2) workflow
> state 500MB PostgreSQL; (3) Milvus vectors 100GB (1B chunks × 1KB); (4) canvas
> JSON 500MB PostgreSQL+Redis; (5) MinIO docs 10TB/year distributed.
-->

# Brainstorm:5 存储量预估 §4.6 段(eng-review Perf #2)

## 背景(来自 eng-review 报告)

eng-review 2026-06-10 锁定的 12 个工程决策中,Perf #2 明确"5 个存储量预估"。
eng-review 报告里**没有**预留 §4.X 段名(不像 Arch #3 预留 §4.3.X)。

仓库现状盘点(2026-06-12):
- `docs/architecture.md` §4.5 部署架构段已存在,**无**5 数字集中段
- L4 Milvus 100GB 数字**已**在 `§4.3.X`(本 session T3 spec 补)
- audit log 780GB/3mo **已**在 `gateway-egress-enforcement-p0` spec 设计里
  (`design.md` D8 + `services/audit-and-isolation/jobs/archive_audit.py`)
- workflow state 500MB / canvas JSON 500MB / MinIO 文档 10TB/year **散落**于
  README + spec,未集中

本次 change **不**重复 L4 100GB 与 audit 780GB 已写过的数字,**统一集中**5
数字 + 计算依据 + 漂移监控。

## 决策链(已知,eng-review 锁定,本段不需 user 确认)

### Q1:范围边界

- **选项 A** 纯 §4.6 段补全 + 5 数字集中 + 计算依据 + 漂移监控,**不**实现
  `services/operations/storage_monitor.py` 漂移监控
- B:同时实现漂移监控脚本
- C:只列数字不写计算依据

**选 A**。eng-review Perf #2 锁定"5 数字",不锁"实现监控脚本"。监控脚本
留 V1.0+ 单独 spec 实施。

### Q2:段号

- eng-review 报告里**没**预留段号。本 spec 决定:`§4.6`(在 §4.5 部署架构后)
- 理由:本段是部署架构的存储量细节,跟 §4.5 紧邻

### Q3:与 §4.3 段引用

- §4.3.X L4 100GB 数字 → 本段 Milvus 100GB 引用(避免漂移)
- §4.3.Y PII mask 节省存储 → 本段 audit 780GB 注释"mask 后数字"
- §4.5 部署架构 → 本段引用(本段是 §4.5 的存储量细节)

### Q4:漂移监控

- 阈值:30%(MVP 保守值)
- 通道:复用 `audit-and-isolation/app/alerts.py::send_wecom()`(eng-review 既有)
- 频率:每日 02:00 UTC(与 audit 归档任务同窗口)
- 实施:`services/operations/storage_monitor.py` 留 V1.0+

### Q5:spec capability 列表

- 1 个新 capability `storage-estimates` 锁定 §4.6 段存在 + 5 数字 + 计算依据 + 漂移监控

## 5 数字(eng-review Perf #2 锁定)

1. **audit log 780GB/3mo MinIO cold**:
   - metadata-only 14 字段 × 2KB/event × 50K events/day × 90 天 = ~9GB PG
   - 冷数据 + 历史累计 + 索引副本 ≈ 780GB/3mo(PG 50GB + MinIO 720GB)
2. **workflow state 500MB PostgreSQL**:
   - 1000 workflow × 5 versions × 100KB/workflow JSON = 500MB
   - 不含 LangGraph checkpoint(checkpoint 单存 `workflow_state` 表)
3. **Milvus 100GB**:
   - 1B chunks × 1KB/chunk + IVF/HNSW 索引(约等于原始向量 30%)
   - 与 §4.3.X L4 数字一致
4. **canvas JSON 500MB PostgreSQL+Redis**:
   - 1000 canvas × 50 versions × 10KB/canvas JSON + Redis 实时副本
   - 不含画布图片 / 资产(那些走 MinIO 文档)
5. **MinIO docs 10TB/year distributed**:
   - 企业日均 30GB 文档上传 × 365 = 10.95TB
   - 含 3 副本 erasure coding

## 设计取捨

| 取捨点 | 选 A | 选 B | 我们选 | 理由 |
|---|---|---|---|---|
| 漂移监控 | 阈值 30% | 阈值 50% | 30% | MVP 保守,V1.0+ 调 |
| 告警通道 | 复用 `alerts.py` | 新建 Slack webhook | 复用 | eng-review 锁定 + 减少新依赖 |
| 监控频率 | 每日 02:00 UTC | 实时 | 每日 | 与 audit 归档同窗口,简单 |
| 实施位置 | `services/operations/` | K8s CronJob | K8s CronJob | 沿用 audit 归档模式 |

## 被拒方案

1. **实施 `services/operations/storage_monitor.py`** —— eng-review 锁定"5 数字",不锁"实现监控"。留 V1.0+ 单独 spec
2. **数字全部漂移到 V1.0 修订** —— MVP 阶段数字保守即可
3. **5 数字单独建 spec** —— 1 个 capability 已够,eng-review 1 个 finding 锁 1 段

## 触发 wedge 场景

- **paul 财务月报**:audit 90 天内数据 + 1 年历史财务文档 → 占 audit 30% + 文档 50%
- **leo 数据查询**:workflow state 1000 × 5 = 500MB 长期
- **anny 文档审核**:上传文档到 MinIO 占 10TB/year 主体,Milvus 占 100GB

## 跨 spec 依赖

| 后续 spec | 怎么依赖本 spec |
|---|---|
| T3 4 层记忆 | §4.3.X L4 100GB 数字与本段 Milvus 100GB 引用一致 |
| T1 数据隔离网关 | audit 90 天 MinIO 路径与本段"audit log 780GB/3mo"一致 |
| (新) 漂移监控 spec | 继承本段 §4.6 漂移监控段 + 引用 K8s CronJob 模式 |

## Open Questions(交给 apply 阶段)

- **OQ1:** 漂移监控的 5 数字告警是单 store 还是聚合?决定:单 store(便于定位)
- **OQ2:** 是否加 chart 可视化(Grafana 模板)决定:留 V1.0+
- **OQ3:** workflow state 500MB 是否含 LangGraph checkpoint?决定:不含(checkpoint 单存 `workflow_state` 表,与 workflow definition JSON 分开)
