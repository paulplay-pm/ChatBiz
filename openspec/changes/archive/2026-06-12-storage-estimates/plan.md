# 5 Storage Estimates 实施计划(纯文档 spec)

> **For agentic workers:** Use superpowers:brainstorming-style planning,
> this is a documentation-only spec. No code is written; verify is grep-based.

**Goal:** 在 `docs/architecture.md` §4.5 部署架构后新增 §4.6 段(eng-review
Perf #2 锁定的 5 存储量预估),集中 5 数字 + 计算依据 + 与既有 §4.3 段引用一致
+ 漂移监控 `[FUTURE-IMPLEMENTATION]` 标注。

**Architecture:** 纯文档增量。5 数字(780GB/3mo / 500MB / 100GB / 500MB / 10TB/year)
**不**实现监控脚本(`services/operations/storage_monitor.py` 留 V1.0+)。
本 spec 是 eng-review Perf #2 锁定的设计文档对应。

**Tech Stack:** 不引入新 stack。引用 §4.4 锁定的 PostgreSQL / Redis / MinIO / Milvus。

---

## 总体执行顺序

| 阶段 | 任务组 | 阻塞关系 | 并行机会 |
|---|---|---|---|
| Phase A | 1.1 / 1.2 调研 | 无 | 可并行 |
| Phase B | 2.1 / 2.2 §4.6 段 | 依赖 Phase A | 串行 |
| Phase C | 3.1 CLAUDE.md surface | 依赖 2.1 | 串行 |
| Phase D | 4.1 / 4.2 verify 测试 | 依赖 2.1 / 3.1 | 串行 |
| Phase E | 5.1 / 5.2 收尾 | 依赖 4.2 | 串行 |

**关键路径:** 1.1 → 2.1 → 3.1 → 4.1 → 5.1 → 5.2
**无并行窗口**(纯文档 spec)

---

## 关键 commit 节点

| Commit # | Task | 触发条件 |
|---|---|---|
| C1 | 2.1 + 2.2 | §4.6 段 + 目录条目 |
| C2 | 3.1 | CLAUDE.md surface |
| C3 | 4.1 + 4.2 | verify 测试通过 |
| C4 | 5.1 + 5.2 | verify.md + retrospective.md + archive |

---

## Task 2.1 §4.6 段撰写(样板)

**Files:**
- Modify: `docs/architecture.md` §4.5 部署架构后,五、参考资料前
- Modify: `docs/architecture.md` 顶层目录 §4 段下

**Steps:**

- [ ] **Step 2.1.1:** 找 §4.5 段末位置(line 1186 附近,`└──...` 结束位置)
- [ ] **Step 2.1.2:** 在 `---` 分隔符前,加 `### 4.6 存储量预估(eng-review Perf #2 锁定)` 标题
- [ ] **Step 2.1.3:** 写引子(eng-review Perf #2 锁定 + 5 数字集中 + 计算依据)
- [ ] **Step 2.1.4:** 写 5 数字总览表
- [ ] **Step 2.1.5:** 写计算依据段(每数字 ~5 行)
- [ ] **Step 2.1.6:** 写与既有 §4.3 段引用段
- [ ] **Step 2.1.7:** 写漂移监控段(`[FUTURE-IMPLEMENTATION]` 标注)
- [ ] **Step 2.1.8:** 写 eng-review 决策引用 + 下游 spec 引用
- [ ] **Step 2.1.9:** 在顶层目录 §4 段下加 `- [4.6 存储量预估(eng-review Perf #2 锁定)]` 链接
- [ ] **Step 2.1.10:** 验证文档总长度仍 < 1500 行
- [ ] **Step 2.1.11:** Commit: `docs(architecture): add §4.6 5 storage estimates (eng-review Perf #2)`

---

## Task 3.1 CLAUDE.md surface(样板)

**Files:**
- Modify: `CLAUDE.md`

**Steps:**

- [ ] **Step 3.1.1:** 找 `CLAUDE.md` 中 `## 已锁定的工程决策` 之前位置
- [ ] **Step 3.1.2:** 加 1 行 `[FUTURE-IMPLEMENTATION] docs/architecture.md §4.6 5 存储量预估(eng-review Perf #2 锁定)即将在 storage-estimates apply 阶段补全,引用 §4.3.X L4 100GB + §4.3.Y PII mask 节省 + §4.5 部署架构;漂移监控 V1.0+`
- [ ] **Step 3.1.3:** 验证 `CLAUDE.md` 总长度 < 320 行
- [ ] **Step 3.1.4:** Commit: `docs: CLAUDE.md surface for §4.6 5 storage estimates`

---

## Task 4.1 verify 测试(样板)

**Files:**
- Create: `tests/test_architecture_md_storage.py`(仓库根 tests/ 下)

**Steps:**

- [ ] **Step 4.1.1:** 写 test 用 grep 验证 `docs/architecture.md` 含:
  - `### 4.6 存储量预估` 段标题
  - 5 数字:`780GB` / `500MB` / `100GB` / `10TB/year`
  - 5 关键词:`audit` / `workflow` / `Milvus` / `canvas` / `MinIO`
  - 3 交叉引用:`§4.3.X` / `§4.3.Y` / `§4.5`
  - `Perf #2` eng-review 决策引用
  - `[FUTURE-IMPLEMENTATION]` 漂移监控标注
- [ ] **Step 4.1.2:** 跑 `python -m pytest tests/test_architecture_md_storage.py -v` 验证通过
- [ ] **Step 4.1.3:** Commit: `test: verify §4.6 5 storage estimates section exists with required content`

---

## Task 5.1 / 5.2 收尾

- [ ] 5.1 写 `verify.md`:列 §4.6 段验证结果 + 5 数字 + 3 交叉引用 + Perf #2 引用 + [FUTURE-IMPLEMENTATION] 标注 + 4 commit 列表
- [ ] 5.2 写 `retrospective.md`:本 spec 是纯文档 spec 反思(eng-review 数字 vs 实际实施) + 与 §4.3 段引用一致性 + V1.0+ 漂移监控 spec 衔接建议

---

## 验证矩阵

| Task | 验证 |
|---|---|
| 2.1 §4.6 段 | test_architecture_md_storage.py grep 验证 |
| 3.1 CLAUDE.md surface | grep `[FUTURE-IMPLEMENTATION] docs/architecture.md §4.6` |
| 4.1 verify test | pytest 通过 |
| 5.1 verify.md | `openspec status` isComplete: true |
| 5.2 retrospective.md | 列出 4 commit + V1.0+ 漂移监控 spec 衔接建议 |

---

## 风险与回退(对应 design.md Risks)

| 风险 | 触发条件 | 回退方案 |
|---|---|---|
| R1 5 数字漂移 | 后续 spec 实施时发现数字不对 | 在 §4.6 加"数字基于估算,实际由 storage_monitor V1.0+ 校准"注释 |
| R2 §4.3.X 100GB 漂移 | 后续 4 层记忆 spec 实施时改数字 | 同步修订 §4.6 |
| R3 gateway spec 780GB 漂移 | archive_audit.py 改 90 天 | 同步修订 §4.6 |
| R4 漂移监控未实施 | 实际容量超 780GB 不告警 | 标 `[FUTURE-IMPLEMENTATION]`,V1.0+ 必做 |

---

## 收尾判定标准

- [ ] `docs/architecture.md` §4.6 段存在 + 含 5 数字 + 3 交叉引用 + Perf #2 引用 + [FUTURE-IMPLEMENTATION] 标注
- [ ] `CLAUDE.md` 含 `[FUTURE-IMPLEMENTATION] docs/architecture.md §4.6 ...` 标记
- [ ] `pytest tests/test_architecture_md_storage.py` 通过
- [ ] `openspec status --change storage-estimates` 输出 `isComplete: true`
- [ ] `verify.md` + `retrospective.md` 已写
- [ ] 4 个 commit 都在 main 上
