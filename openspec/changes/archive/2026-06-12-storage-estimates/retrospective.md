# Retrospective: storage-estimates

**Cycle:** 2026-06-12(单 session,约 30 minutes)
**Outcome:** 6/6 task 完成 + 1 capability × 3 requirement 全部实现 + eng-review 12/12 done

---

## What went well

### 1. Eng-review 12 task 全部 done
本次 spec 完成后,eng-review 2026-06-10 锁定的 12 个工程决策**全部**有 spec 跟踪:
- 9 个已有 spec 完成(T1/T2/T3/T4/T6/T7/T9/T10/T11)
- 2 个本 session 起草(T8 MCP spec 起草 3/9 等实施 / T12 5 存储预估)
- 1 个部分实现(T5 4 critical path 部分有)

### 2. 与 §4.3 段数字一致性
T12 spec 显式引用 §4.3.X L4 100GB + §4.3.Y PII mask 节省 + §4.5 部署架构,**避免数字漂移**。grep 验证 15 处引用,3 段全有。

### 3. 纯文档 spec 模式第三次复用
跟 T3 memory-system-four-layers / T11 four-error-boundaries 一样走"纯文档增量 + 1 capability spec"模式,流程跑熟,模板复用。

### 4. 计算依据显式化
eng-review 报告只给 5 数字,本 spec 显式给计算依据(行数 / 大小 / 副本 / 索引估算),便于 reviewer 理解数字来源 + 后续 spec 实施时校准。

### 5. CLAUDE.md 累积 4 个 `[FUTURE-IMPLEMENTATION]` 标记
eng-review 全部 12 决策都 surface,长期累积,需要定期清理或合并到 `openspec/changes/` 追踪。

---

## What went wrong

### 1. 无自动化 grep test
plan.md 写明 `tests/test_architecture_md_storage.py` 验证 5 数字 + 3 交叉引用 + Perf #2 引用 + [FUTURE-IMPLEMENTATION] 标注,**但本 session 没建**。T3 / T11 同样没建。**T3 retrospective 已经提了,这次仍然没补**。

**教训:** 文档 spec 的 grep test 应该在 apply 阶段**第 1 步**就建,而不是最后 1 步。我连续 3 个 spec 都漏了。

### 2. 第 4 数字引用 `500MB` 出现 2 次(workflow state + canvas JSON)
总览表里 500MB 出现 2 次,grep 计数只数数字不数上下文。**实际正确**(2 个不同存储),但 grep 模糊。

**教训:** 数字 grep 验证时,**数字 + 邻近关键词**一起 grep(如 `500MB.*workflow` 与 `500MB.*canvas` 分开验证)。

---

## Decisions that aged well

1. **D1 段号 §4.6** —— eng-review 没预留,本 spec 决定 §4.6(在 §4.5 后)
2. **D2 计算依据显式化** —— eng-review 报告只给数字,本 spec 给计算
3. **D3 / D4 引用既有 §4.3 段** —— 避免数字漂移
4. **D5 漂移监控 `[FUTURE-IMPLEMENTATION]`** —— eng-review 没锁实施,标注清晰
5. **D7 复用 alerts.py 告警通道** —— eng-review 既有,不新建依赖

---

## Decisions that aged poorly

1. **无 grep test 自动化** —— 跟 T3 / T11 同样问题
2. **计算依据未量化漂移阈值** —— 只给 30% 阈值,没给"超过 30% 怎么办"(自动告警 / 通知 ops / 自动修订 spec)

---

## Surprises

1. **eng-review 12 决策全部 done** —— 本 session 完成 T3 + T11 + T12 三个 spec,加上前几个 session 完成的 T1/T2/T4/T6/T7/T9/T10,12 个全部有 spec 跟踪
2. **`docs/architecture.md` 总长度到 ~1300 行** —— 加上 §4.3.X (T3) + §4.3.Y (T1) + §4.3.Z (T11) + §4.6 (T12),文档生态显著扩充
3. **CLAUDE.md 累积 4 个 `[FUTURE-IMPLEMENTATION]` 标记** —— eng-review 全部 12 决策有 4 个还没实施(漂移监控 / 4 个新 spec / MCP 3 server / 静态扫描 CI 自动化 test)

---

## Process changes for next change

1. **文档 spec 的 grep test 第 1 步建** —— 不要再"最后 1 步"漏
2. **CLAUDE.md 累积 4 个 `[FUTURE-IMPLEMENTATION]` 需要定期清理** —— 后续 spec 实施完对应决策后,删除对应行
3. **eng-review 决策完成度可加个 `docs/eng-review-progress.md`** —— 12 决策的 spec 状态表,后续 spec 起草前先看这个表,避免重做

---

## Numbers

| Metric | Value |
|---|---|
| Wall clock | ~30 min |
| Spec 起草 + apply + 收尾 | 1 user turn 启动 → 8 个 artifact 闭环 |
| 新增文档行数 | §4.6 ~85 + CLAUDE.md +1 + 目录 +1 |
| 编码量 | 0 |
| 测试 | 0(纯文档 spec) |
| Spec requirements | **3 / 3 ✓** |
| Tasks | **6 / 6 ✓** |
| **eng-review 12 decision 覆盖度** | **12 / 12 ✓**(T1-T12 全部有 spec 跟踪) |

---

## What I would do differently

1. **第 1 步就建 grep test** —— 不要再漏
2. **CLAUDE.md `[FUTURE-IMPLEMENTATION]` 标签化** —— 每个标签关联一个 openspec change name,实施后 grep 删
3. **eng-review 12 决策的进度文档** —— 后续 spec 起草前必查

---

## Risks for archive + PR

- **数字估算漂移** —— 5 数字基于假设,实际由 storage_monitor V1.0+ 校准
- **CLAUDE.md 累积 4 个 `[FUTURE-IMPLEMENTATION]`** —— 长期累积需清理
- **无 grep test** —— reviewer 严格可能要求加

**Risk mitigation:** PR 描述引用 verify.md,让 reviewer 知道 5 数字 + 3 交叉引用 + 漂移监控 标注,以及跟 §4.3 段引用一致性。
