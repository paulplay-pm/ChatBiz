# 4 Layer Memory System 实施计划(纯文档 spec)

> **For agentic workers:** Use superpowers:brainstorming-style planning,
> this is a documentation-only spec. No code is written; verify is grep-based.

**Goal:** 在 `docs/architecture.md` §4.3.3 之后新增 §4.3.X 段(eng-review
Arch #3 锁定的详细设计段),覆盖 4 层记忆(L1 working / L2 short-term Redis
/ L3 long-term PG+pgvector / L4 semantic Milvus)+ Memory Middleware 的
5 大要点(call sites / 写入策略 / 读取策略 / 容量预估 / 与 Agent/Workflow
runtime 集成点)。

**Architecture:** 纯文档增量。L1 working 已在 LangGraph state 实现
([EXISTING]);L2 short-term 短期记忆 spec 待实施([FUTURE-IMPLEMENTATION]);
L3 long-term 长期记忆 spec 待实施;L4 semantic 知识库 spec 待实施;
Memory Middleware 待实施。本 spec 标注每层状态,引用 §4.3.3 简要图 +
§4.3.Y PII 规则集 + §4.4 技术栈。

**Tech Stack:** 不引入新 stack。引用 §4.4 锁定的 Milvus / pgvector /
Redis 7+ / PostgreSQL 16+ / LangGraph。

---

## 总体执行顺序

| 阶段 | 任务组 | 阻塞关系 | 并行机会 |
|---|---|---|---|
| Phase A | 1.1 / 1.2 文档调研 | 无 | 可并行 |
| Phase B | 2.1 §4.3.X 段撰写 | 依赖 1.1 / 1.2 | 串行 |
| Phase C | 3.1 / 3.2 CLAUDE.md surface | 依赖 2.1 | 串行 |
| Phase D | 4.1 / 4.2 verify 测试 | 依赖 2.1 / 3.1 | 串行 |
| Phase E | 5.1 / 5.2 verify.md + retrospective.md | 依赖 4.2 | 串行 |

**关键路径:** 1.1 → 2.1 → 3.1 → 4.1 → 5.1 → 5.2
**无并行窗口**(纯文档 spec,单人串行最快)

---

## 关键 commit 节点

| Commit # | Task | 触发条件 |
|---|---|---|
| C1 | 2.1 + 2.2 | §4.3.X 段 + 目录条目 |
| C2 | 3.1 + 3.2 | CLAUDE.md surface |
| C3 | 4.1 + 4.2 | verify 测试通过 |
| C4 | 5.1 + 5.2 | verify.md + retrospective.md |

---

## Task 2.1 §4.3.X 段撰写(样板,分 section 写)

**Files:**
- Modify: `docs/architecture.md` §4.3.3 之后新增 §4.3.X 段
- Modify: `docs/architecture.md` 目录条目加 §4.3.X 链接

**Steps:**

- [ ] **Step 2.1.1:** 在 §4.3.3 简要图末尾(`└──...` 结束位置)后,`#### 4.3.4 工具与扩展系统` 之前,加 `#### 4.3.X 4 层记忆系统详细设计(eng-review Arch #3 锁定)`
- [ ] **Step 2.1.2:** 写引子段:eng-review Arch #3 锁定 / 本段是 §4.3.3 简要图的详细设计补充 / 不动 §4.3.3
- [ ] **Step 2.1.3:** 写 L1 工作记忆段(5 大要点 + [EXISTING] 状态)
- [ ] **Step 2.1.4:** 写 L2 短期记忆段([FUTURE-IMPLEMENTATION] 状态 + 容量 30MB)
- [ ] **Step 2.1.5:** 写 L3 长期记忆段([FUTURE-IMPLEMENTATION] 状态 + 容量 100MB + pgvector)
- [ ] **Step 2.1.6:** 写 L4 语义记忆段([FUTURE-IMPLEMENTATION] 状态 + 容量 100GB + 引用 §4.3.Y PII)
- [ ] **Step 2.1.7:** 写 Memory Middleware 段
- [ ] **Step 2.1.8:** 写 call sites 与 Agent/Workflow runtime 集成段(每层状态标注)
- [ ] **Step 2.1.9:** 写交叉引用段(§4.3.3 / §4.3.Y / §4.4)
- [ ] **Step 2.1.10:** 写 eng-review 决策引用段(Arch #3 / Perf #2 #3)
- [ ] **Step 2.1.11:** 写下游 spec 引用段(T2 / T7 / T11 / T12 / 4 个新 spec)
- [ ] **Step 2.1.12:** 在 `docs/architecture.md` 目录条目加 `- [4.3.X 4 层记忆系统详细设计](#43x-4-层记忆系统详细设计eng-review-arch-3-锁定)`
- [ ] **Step 2.1.13:** Commit: `docs(architecture): add §4.3.X 4-layer memory system detailed design`

---

## Task 3.1 CLAUDE.md surface 同步(样板)

**Files:**
- Modify: `CLAUDE.md`

**Steps:**

- [ ] **Step 3.1.1:** 找 `CLAUDE.md` 中 §4.3 描述段后、`## 已锁定的工程决策` 之前的位置
- [ ] **Step 3.1.2:** 在该位置加 1 行 `[FUTURE-IMPLEMENTATION] docs/architecture.md §4.3.X 4 层记忆详细设计即将在 memory-system-four-layers apply 阶段补全,引用 §4.3.3 简要图 + §4.3.Y PII 规则集 + §4.4 技术栈`
- [ ] **Step 3.1.3:** 验证 `CLAUDE.md` 总长度 < 300 行
- [ ] **Step 3.1.4:** Commit: `docs: CLAUDE.md surface for §4.3.X 4-layer memory system`

---

## Task 4.1 verify 测试(样板)

**Files:**
- Create: `tests/test_architecture_md_memory.py`(仓库根 tests/ 下,与 gateway spec 的 test_architecture_md.py 并列)

**Steps:**

- [ ] **Step 4.1.1:** 写 test 用 grep 验证 `docs/architecture.md` 含以下所有关键词:
  - `### 4.3.X 4 层记忆` (段标题)
  - `L1` / `L2` / `L3` / `L4` (4 层)
  - `Middleware` 或 `Memory Middleware`
  - `call site` / `写入策略` / `读取策略` / `容量` (5 大要点)
  - `§4.3.3` / `§4.3.Y` / `§4.4` (交叉引用)
  - `Arch #3` / `Perf #2` (eng-review 决策)
  - `[EXISTING]` 或 `[FUTURE-IMPLEMENTATION]` (状态标注)
- [ ] **Step 4.1.2:** 跑 `python -m pytest tests/test_architecture_md_memory.py -v` 验证通过
- [ ] **Step 4.1.3:** Commit: `test: verify §4.3.X 4-layer memory section exists with required content`

---

## Task 5.1 / 5.2 收尾

- [ ] 5.1 写 `verify.md`:列 §4.3.X 段验证结果 + 5 大要点覆盖 + 交叉引用 OK + CLAUDE.md surface OK + 4 个 commit 列表
- [ ] 5.2 写 `retrospective.md`:本 spec 是纯文档 spec 的反思 + 与 §4.3.3 关系 + 下游 spec 引用是否清晰 + 后续 L2/L3/L4/Middleware 4 个 spec 衔接建议

---

## 验证矩阵

| Task | 验证 |
|---|---|
| 2.1 §4.3.X 段 | test_architecture_md_memory.py grep 验证 |
| 3.1 CLAUDE.md surface | grep `[FUTURE-IMPLEMENTATION] docs/architecture.md §4.3.X` |
| 4.1 verify test | pytest 通过 |
| 5.1 verify.md | `openspec status` isComplete: true |
| 5.2 retrospective.md | 列出 4 commit + 后续 spec 衔接建议 |

---

## 风险与回退(对应 design.md Risks)

| 风险 | 触发条件 | 回退方案 |
|---|---|---|
| R1 容量数字漂移 | 后续 spec 实施时发现数字不对 | 在 §4.3.X 加 "数字基于估算,实际由 T12 校准" 注释 |
| R2 [FUTURE-IMPLEMENTATION] 状态变化 | 后续 spec 实施完成 | 后续 spec apply 阶段改 §4.3.X 状态标注 |
| R3 与 §4.3.3 重复 | 写得太详细覆盖简要图 | 删重复内容,只引用 §4.3.3 |
| R4 与下游 spec 脱节 | L2/L3/L4 spec 实施时发现 §4.3.X 设计需改 | 后续 spec 实施时回头 surface 修订 |

---

## 收尾判定标准

- [ ] `docs/architecture.md` §4.3.X 段存在 + 含 5 大要点
- [ ] `CLAUDE.md` 含 `[FUTURE-IMPLEMENTATION] docs/architecture.md §4.3.X ...` 标记
- [ ] `pytest tests/test_architecture_md_memory.py` 通过
- [ ] `openspec status --change memory-system-four-layers` 输出 `isComplete: true`
- [ ] `verify.md` + `retrospective.md` 已写
- [ ] 4 个 commit 都在 `feat/gateway-egress-p0` 或新 branch 上
