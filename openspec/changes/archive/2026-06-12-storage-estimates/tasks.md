# Tasks: storage-estimates

## 1. 文档调研与素材准备(20min,2 个 task)

- [ ] 1.1 读 `docs/architecture.md` §4.5 部署架构 + §4.3.X 4 层记忆 + §4.3.Y PII 规则集,确认 5 数字的引用源
- [ ] 1.2 读 eng-review #12(Perf #2)锁定决策,确认 5 数字 + 计算依据假设

## 2. §4.6 段撰写(1h,1 个 task)

- [ ] 2.1 写 `docs/architecture.md` §4.6 段(目标 70-100 行),内容结构:
  - **引子**:eng-review Perf #2 锁定;5 数字集中 + 计算依据
  - **5 数字总览表**:# / 存储 / 容量 / 位置 / 保留 / eng-review 编号
  - **计算依据**(eng-review 报告里只给数字,本 spec 显式给计算):
    1. audit log 780GB/3mo:14 字段 × 2KB × 50K events/day × 90 天 = ~9GB PG;冷数据 + 历史累计 + 索引副本 ≈ 780GB/3mo(PG 50GB + MinIO 720GB)
    2. workflow state 500MB PG:1000 workflow × 5 versions × 100KB = 500MB(不含 LangGraph checkpoint)
    3. Milvus 100GB:1B chunks × 1KB + IVF/HNSW 索引(约等于原始向量 30%);与 §4.3.X L4 数字一致
    4. canvas JSON 500MB PG+Redis:1000 canvas × 50 versions × 10KB + Redis 实时副本(不含画布图片)
    5. MinIO docs 10TB/year:企业日均 30GB 文档 × 365 = 10.95TB(含 3 副本 erasure coding)
  - **与既有 §4.3 段引用**:§4.3.X L4 100GB / §4.3.Y PII mask 节省 / §4.5 部署架构
  - **漂移监控**:`[FUTURE-IMPLEMENTATION]` 标 + 阈值 30% + 复用 `alerts.py::send_wecom()` + K8s CronJob 每日 02:00 UTC
  - **eng-review 决策引用**:Perf #2
  - **下游 spec 引用**:T1 / T3 /(新) 漂移监控 /(新) Grafana dashboard
- [ ] 2.2 在 `docs/architecture.md` 顶层目录 §4 段下加 `- [4.6 存储量预估(eng-review Perf #2 锁定)]` 链接

## 3. CLAUDE.md surface 同步(10min,1 个 task)

- [ ] 3.1 在 `CLAUDE.md` `## 已锁定的工程决策` 段之前,加 1 行 `[FUTURE-IMPLEMENTATION] docs/architecture.md §4.6 5 存储量预估(eng-review Perf #2 锁定)即将在 storage-estimates apply 阶段补全,引用 §4.3.X L4 100GB + §4.3.Y PII mask 节省 + §4.5 部署架构;漂移监控 V1.0+`

## 4. verify 验证(15min,1 个 task)

- [ ] 4.1 写 `tests/test_architecture_md_storage.py`(仓库根 tests/ 下,跟 T3 模板一致),用 grep 验证:
  - `### 4.6 存储量预估` (段标题)
  - `780GB` / `500MB` / `100GB` / `10TB/year` 5 数字
  - `audit` / `workflow` / `Milvus` / `canvas` / `MinIO` 5 关键词
  - `§4.3.X` / `§4.3.Y` / `§4.5` 3 个交叉引用
  - `Perf #2` eng-review 决策引用
  - `[FUTURE-IMPLEMENTATION]` 漂移监控标注
- [ ] 4.2 跑 `python -m pytest tests/test_architecture_md_storage.py -v` 验证通过

## 5. 收尾(15min,2 个 task)

- [ ] 5.1 写 `verify.md`:列 §4.6 段验证结果 + 5 数字 + 3 交叉引用 + Perf #2 引用 + [FUTURE-IMPLEMENTATION] 标注
- [ ] 5.2 写 `retrospective.md`:本 spec 是纯文档 spec 反思(eng-review 数字 vs 实际实施) + 与 §4.3 段引用一致性 + V1.0+ 漂移监控 spec 衔接建议

---

**总计 6 个 task**:2 调研 + 1 文档 + 1 CLAUDE.md + 1 verify + 1 收尾。每个 task ≤ 1h,无编码任务(全文档)。

**配对验证**:
- task 2.1 ↔ task 4.1(test 验证)
- task 3.1 ↔ task 4.1(同一 test 验证)
- task 5.1 ↔ task 4.1(spec 完成判定)

无孤儿。任务粒度全部 ≤ 1h(总预估 ~2.5h)。
