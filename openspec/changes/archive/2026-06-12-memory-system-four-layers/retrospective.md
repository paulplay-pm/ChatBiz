# Retrospective: memory-system-four-layers

**Cycle:** 2026-06-12(单 session,约 1 hour)
**Outcome:** 7/7 task 完成 + 1 capability × 3 requirement 全部实现 + 文档 spec 全闭环

---

## What went well

### 1. 纯文档 spec 模式
本次 spec 是**纯文档增量**,不写代码、不写测试。**这是 superpowers-bridge schema 第一次跑纯文档 spec**,证明 schema 不强制要求代码产物。

### 2. 5 大要点 + 交叉引用 + 下游 spec 引用结构清晰
spec 内容按 eng-review Arch #3 锁定的"4 层 + Middleware 5 大要点(call sites / 写入 / 读取 / 容量 / 集成)"组织,清晰映射到 3 个 requirement。

### 3. 状态标注 `[EXISTING]` / `[FUTURE-IMPLEMENTATION]`
每层都标状态,后续 spec 实施时只需把 `[FUTURE-IMPLEMENTATION]` 改成 `[EXISTING]`,无需重写段。

### 4. 与 gateway-egress-enforcement-p0 spec 的 §4.3.Y 协同
§4.3.X 显式引用 §4.3.Y(L4 文档 PII 扫描),证明 2 个 spec 不冲突,而是互补。

### 5. 容量预估数字与 eng-review Perf #2 #3 对齐
L4 100GB / 1B chunks 与 eng-review 锁定数字一致,避免漂移。

---

## What went wrong

### 1. 顶层目录条目修正
仓库原顶层目录没展开 §4.3.1-§4.3.x 子项(只有 §4.3 总条目)。我之前给 gateway spec 加 §4.3.Y 时**没在顶层目录补**,这次给 §4.3.X 加时**才发现**需要展开 7 个子项。

**教训:** 任何新增 §4.3.x 段都要**同步顶层目录**。把"§4.3.x 目录展开"作为 spec 验收标准之一。

### 2. brainstorm 阶段问题表简化
brainstorm.md 列了 5 个 Q1-Q5,但**所有决策都是 eng-review 锁定的默认值**,没有真正需要 user 拍板的开放问题。**brainstorm 阶段对纯文档 spec 来说是冗余的**(设计已经 100% 来自 eng-review)。

**教训:** superpowers-bridge schema 的 brainstorm 阶段对纯文档 spec 可以**用一句话过场** —— "本 spec 设计 100% 来自 eng-review Arch #3 锁定,无开放决策需 user 拍板"。

### 3. 与 §4.3.3 简要图重复风险
§4.3.3 已有 4 层图(L1/L2/L3/L4 各 1 段),§4.3.X 详细设计时**很容易重复写 4 层定义**。我在 D7 决策明确"§4.3.X 引用 §4.3.3,不复制图",实际写时也确实没重复。

**教训:** 文档 spec 必须先看相邻段(§4.3.3)再写,避免重复。

---

## Decisions that aged well

1. **5 大要点结构** —— 写起来快,reviewer 读起来清
2. **状态标注体系** `[EXISTING]` / `[FUTURE-IMPLEMENTATION]` —— 给后续 spec 留好钩子
3. **引用 §4.3.3 / §4.3.Y / §4.4** —— 文档生态正确,避免重复 + 防止漂移
4. **下游 spec 引用清单** —— 后续 L2/L3/L4/Middleware spec 知道本段是 design doc

---

## Decisions that aged poorly

1. **无自动化 test** —— 文档 spec 没法用 pytest 验,只能 grep + 手动 review。如果 reviewer 严格,可能要求加 `tests/test_architecture_md_memory.py`(类似 gateway spec 的 test_architecture_md.py)。**应该主动加,而不是 reviewer 提**
2. **下游 spec name 占位**(`<l2-spec>` 等)—— 实施时需替换,容易忘

---

## Surprises

1. **superpowers-bridge schema 不强制要求代码产物** —— 之前我以为必须写代码 + 测试,实际上纯文档 spec 也能完整跑通
2. **eng-review Arch #3 已有"§4.3.X"占位命名** —— 我用 §4.3.X 与 eng-review 报告里预留的命名完全一致,无需重新编号
3. **CLAUDE.md 已累积 2 个 `[FUTURE-IMPLEMENTATION]` 标记** —— 长期累积,可能需要定期清理;但当前 2 个都还没实施,合理

---

## Process changes for next change

1. **任何新增 §4.3.x 段都要同步顶层目录** —— 把"目录展开"加入 spec 验收清单
2. **纯文档 spec 应主动加 grep test** —— 类似 `test_architecture_md_memory.py`,在 `tests/` 根目录,提供 pytest 自动化验证
3. **brainstorm 阶段对纯文档 spec 可简化** —— 1-2 句过场,避免冗长
4. **下游 spec name 占位用 `openspec/changes/<real-name>/`** —— 实施时易替换,避免 `<placeholder>` 漂移

---

## Numbers

| Metric | Value |
|---|---|
| Wall clock | ~1 hour(单 session) |
| Spec 起草 + review + apply | 1 user turn 启动 → 9 个 sub-step 完成 |
| 新增文档行数 | §4.3.X ~140 行 + CLAUDE.md +2 行 + 目录 +7 行 |
| 编码量 | 0 |
| 测试 | 0(纯文档 spec) |
| Spec requirements | **3 / 3 ✓** |
| Tasks | **7 / 7 ✓** |

---

## What I would do differently

1. **主动加 `tests/test_architecture_md_memory.py`** —— 不等 reviewer 要求
2. **brainstorm 阶段写 1 段过场而不是完整 Q1-Q5** —— 节省 ~10 turn
3. **顶层目录展开作为 spec 第一步** —— 不放在最后才想起

---

## Risks for archive + PR

- **无代码,无测试** —— reviewer 可能要求加 grep test
- **下游 4 个新 spec 占位** —— 实施时需替换,可能忘
- **CLAUDE.md 双 `[FUTURE-IMPLEMENTATION]` 累积** —— 后续清理

**Risk mitigation:** PR 描述引用 verify.md,让 reviewer 知道本 spec 是纯文档 + 引用 4 个新 spec 后续实施。
