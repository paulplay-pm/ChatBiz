# Retrospective: four-error-boundaries

**Cycle:** 2026-06-12(单 session,约 1.5 hour)
**Outcome:** 8/8 task 完成 + 1 capability × 3 requirement 全部实现 + 287 tests

---

## What went well

### 1. 补差模式再次奏效
跟 T1 gateway spec 同模式:**4 边界 80% 已散落实现**,本 spec 只补 §4.3.Z 段 + 1 个新 `WorkflowCycleError` 类 + 5 tests。**30 行代码 + 150 行文档**就完成了 3 个 requirement。

### 2. 既有 `chatbiz_error_handler` 自动覆盖新错误类
**D8 decision 原本要求"加新 middleware handler"**,但实际 `WorkflowCycleError(error_class="user")` 走既有 handler 自动获 HTTP 422 + 统一响应体。**d8 决策在 apply 阶段被 D8 revised**——这是 TDD 的胜利(还没写代码前先看既有代码)。

### 3. Eng-review 决策 vs 现状对比一次到位
brainstorm.md 详细列了 4 边界 × 现有实现的 class / file / HTTP status 映射。**spec 起草时就已经知道要补什么 vs 留什么**。

### 4. 文档 spec 跟 T3 同模式
跟 T3 memory-system-four-layers 一样走"纯文档增量 + 1 capability spec"模式,流程跑熟,模板复用。

### 5. 5 个新测试一次过
test_workflow_cycle_error_class / message_contains_edges / preserves_edges_attr / defensive_copy / empty_edges 5 个测试,**第 6 个 (nested-list) 期望错,我修成同类型 list 测试通过**。TDD 实战。

---

## What went wrong

### 1. 文档目录条目 edit 失败 2 次
docs/architecture.md 顶层目录是 2-level 缩进(line 28-32),我 edit 时按 4-level 缩进匹配,失败。**回头看 `sed -n` 才知道**。浪费 1 turn。

**教训:** 任何 Edit 操作前**先 `Read` 看实际行内容 + 缩进**,不要凭记忆。

### 2. def 防御性 copy 测试期望过严
我测了 `src = [["a", "b"]]` 嵌套 list mutations,期望 `e.cycle_edges` 不变。但 `list(edges)` 只做浅 copy,内部嵌套 list 是 mutable。**类型也不匹配**(`list[list[str]]` vs `list[tuple[str, str]]`)。改测同类型 list append,1 轮修过。

**教训:** 防御性 copy 测试**只测**"外层 list append 元素"和"同类型元素 mutation",**不测**"嵌套结构 + 跨类型"。

### 3. `chatbiz_error_handler` 现状 `user → 422` 跟 spec 写 `Boundary #3 → 400` 不一致
eng-review 没明确 Boundary #3 应该是 400 还是 422。**现状是 422**(由 `error_class == "user"` 决定),spec 文档 段也写 422。**我 spec 写时跟现状对齐,没改既有 handler**。

**教训:** 补差 spec 永远以**现状代码**为准,不重新设计;如果 eng-review 没明确,沿用既有实现。

### 4. 覆盖率 baseline 没 100%(98.85%)
fix-workflow-engine-100pct-coverage commit `e6453ae` 加了 4 个 test_workflows filter test,但仍缺 11 行。**这不在 T11 spec 范围**。我**没**补那 11 行(避免抢其他 spec 的活)。

**教训:** 增量 spec 严格守"只动自己的范围",不动其他 spec 的遗留问题。

---

## Decisions that aged well

1. **D4 独立类**(`WorkflowCycleError` 不继承 `UserError`)—— 语义清晰,error code 独立
2. **D6 422 Unprocessable Entity** —— 跟既有 `chatbiz_error_handler` 行为一致,无需改 middleware
3. **D7 既有错误类不动** —— 不抢实现,跟 T1/T3 补差模式一致
4. **D9 状态标注体系** `[EXISTING]` / `[NEW]` —— 跟 §4.3.Y / §4.3.X 风格一致

---

## Decisions that aged poorly

1. **D8 决策最初写"加新 middleware handler"** —— apply 阶段发现 D8 错了,revised 为"既有 handler 自动覆盖"。应该在 brainstorm 阶段就 check 既有 code 行为,不要凭直觉写决策
2. **无自动化 grep test 验证 §4.3.Z 段** —— T3 一样,文档 spec 不写 grep test 验证。**后续应加 `tests/test_architecture_md_errors.py`** 跟 T3 一样

---

## Surprises

1. **`chatbiz_error_handler` 已是 base class handler** —— 4 边界类只要继承 `ChatBizError` + 设 `error_class` 字段,自动获对应 HTTP 状态 + 统一响应体
2. **`WorkflowCycleError` 加 5 个测试 0 修改既有测试** —— 既有 9 个子类测试全部不动,新增 5 个独立测试,干净分离
3. **CLAUDE.md 累积到 3 个 `[FUTURE-IMPLEMENTATION]` 标记** —— 长期累积,需要定期清理或合并

---

## Process changes for next change

1. **brainstorm 阶段必 check 既有代码行为** —— D8 决策错就是因为没 check middleware 行为。Edit 之前先 Read 既有实现
2. **文档 spec 主动加 grep test** —— `tests/test_architecture_md_<spec>.py`,在 `tests/` 根目录
3. **Edit 之前先 Read** —— 不要凭记忆匹配字符串,实际行内容 + 缩进必须看
4. **测试防御性 copy 时只测同类型 + 外层 list mutation** —— 不测嵌套结构跨类型

---

## Numbers

| Metric | Value |
|---|---|
| Wall clock | ~1.5 hour |
| Spec 起草 + apply + 收尾 | 1 user turn 启动 → 9 个 artifact 闭环 |
| Commits | 3(代码 + 文档 + 自动) |
| 新增 Python 行 | ~30 |
| 新增文档行 | ~150(§4.3.Z)+ 1(CLAUDE.md)+ 1(目录条目) |
| 测试 | **+5** (282 → 287) |
| Spec requirements | **3 / 3 ✓** |
| Tasks | **8 / 8 ✓** |

---

## What I would do differently

1. **D8 决策在 brainstorm 阶段就 check 既有 code** —— 而不是 apply 阶段 revise
2. **主动加 grep test**(`tests/test_architecture_md_errors.py`)—— 跟 T3 一样
3. **Edit 之前先 `Read`** —— 不要凭记忆

---

## Risks for archive + PR

- **`chatbiz_error_handler` 现状 `user → 422` 跟 eng-review 表述的 `Boundary #3 → 400` 不严格对齐** —— 文档表面这个 deviation
- **`services/error_handling/` 统一 package 留 V1.0+** —— 标 `[FUTURE-IMPLEMENTATION]`
- **CLAUDE.md 累积 3 个 `[FUTURE-IMPLEMENTATION]` 标记** —— 长期累积

**Risk mitigation:** PR 描述引用 verify.md,让 reviewer 知道 Boundary #1 是 `[NEW]` 其他 3 边界是 `[EXISTING]`。
