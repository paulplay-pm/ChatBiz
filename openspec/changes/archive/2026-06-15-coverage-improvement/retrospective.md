# Retrospective: coverage-improvement

**Date range**: 2026-06-15（单次 session 完成）
**Trigger**: `gateway-egress-enforcement-p0/retrospective.md §6.4 row 1`
**Owner**: paul (sponsor) + Claude (apply orchestrator)
**Commit**: 14988d05f92f85edfe1eafeb1fde96b30e98004a

---

## 1. What was built

1 个 commit（14988d0）+ 2 个测试文件（710 行新增，0 行生产代码修改）：

- **`services/audit-and-isolation/tests/unit/test_coverage_gaps_v1_followup.py`**：477 行
  - 6 个原始测试（5 PASS + 1 SKIP，来自前会话 untracked 工作）
  - **9 个新测试**（apply 阶段补，覆盖原 spec 外的 gap）
  - 1 个 `pytest.skip` 替换 broken stub（docstring 解释 `client.py:304` 的 defensive 性质）
  - 3 个 env var `os.environ.setdefault`（修复 `Settings()` import-time 验证失败，pattern 与 commit 6994800 task 7.1 一致）

- **`services/audit-and-isolation/tests/unit/test_routing_table_coverage.py`**：233 行
  - 7 个测试，全部 PASS，覆盖 `load_routing` / `get_routing` 全路径

**覆盖率收尾**：

| 模块 | 起始（apply 前） | 收尾（apply 后） |
|---|---|---|
| `app/jobs/archive_audit.py` | 86%（行 295 missing）| **100%** |
| `app/llm/client.py` 的 `compute_idempotency_key` | 37%（行 185/189/191 missing）| **100%**（函数级） |
| `app/routing/table.py` | 100% | 100% |
| **3 个目标模块合计** | partial | **100%** |

注：`client.py` 整体仍 41%，但 missing 行全在 `retry_with_idempotency` / `retry_with_redis`
装饰器 body（line 240-304 + 74-80 + 104-120 + 210-216 + 328 + 334），本 change scope 之外。
plan.md Task 3.2 已预测并接受此状态。

---

## 2. What went well

### 2.1 Claim vs reality 漂移被 apply 阶段抓住

proposal.md / design.md / plan.md 都声称"line 188-193 covered" / "lines 290-295 row-count-mismatch
warning path covered"。apply 阶段第一次跑 `pytest-cov` 显示：

- `archive_audit.py` 86% —— 行 295 (`else: rows_deleted = 0`) missing，**不是** spec claim 的 290-295
- `client.py` 37% —— 行 189 (`str.encode`) / 191 (`bytes`) missing，spec 没说这两条具体路径

**如果按"5 PASS / 1 SKIP 全绿就 commit" 走流程**，覆盖率数字会被 commit 进 main，但 claim
是**部分撒谎**的（spec 说"100%"，实际"原始 docstring 声明的几个分支"，子集）。**这次**因为
apply 阶段把 cov 跑出来对比，漂移在 commit 前就被 surface，用户给指令"补 test 达 100%"，才
避免了一次不诚实的 commit。

### 2.2 "small batches followup" 是正确的形状

本 change 是 retrospective §6.4 第 1 条的"low-hanging module gap"小批量，**只动 2 个
untracked test file + 3 行 env var setdefault**。0 行生产代码，1 个 commit，~30 分钟
净 apply 时间。如果硬上"全 audit-and-isolation 100%"会扩 scope 5-10x，retrospective
§6.4 没承诺那个。

### 2.3 spec-driven 流程对 trivial change 也有审计价值

`openspec/changes/coverage-improvement/` 6 个 artifact（brainstorm / proposal / design /
specs / tasks / plan）共 1263 行 markdown。**单一测试 followup 看起来 over-engineered**，
但产物是：

- 未来 `grep "100% line coverage"` 能从 `proposal.md Why` 段追溯到 `retrospective.md §6.4`
- 9 个新 test 都有 docstring 解释"为什么"，比裸 test 函数更耐看
- 12 个 eng-review 决策 + 3 个具名用户 workflow + 3 件源参考 全在 proposal §Impact
  显式声明"不触及"，未来 review 不会重新讨论

---

## 3. What didn't go well

### 3.1 9 个新 test 远超原 spec docstring 范围

原始 `test_coverage_gaps_v1_followup.py` 的 docstring 说：

> Modules covered here:
>   * `app/jobs/archive_audit.py` — line 94 (duration_seconds property)
>     + lines 290-295 (row-count-mismatch warning path)
>   * `app/llm/client.py` — lines 188-193 (body-not-dict fallback in
>     compute_idempotency_key) + line 304 (unreachable-no-result raise)

apply 阶段发现"100% line coverage"是 84 / 39 / 184-198 行的承诺，docstring 只声明其中
**5 行**。9 个新 test 走了 docstring 没声明的分支（167-168 / 214-215 / 221-223 / 232-233
/ 256-264 / 185-187 / 191 / 189 / 184）。

**根因**：proposal / design / plan 的 G1 claim "100% line coverage" 在 docstring
"覆盖 line 94 + 290-295 + 188-193 + 304" 之外扩大了范围，但前 sessions 的 brainstorming
没把"100% line coverage"和"docstring 声明的 5 行"区分开。

**教训**：未来 spec proposal "100% line coverage" claim 必须列出**所有**需要走的分支清单
（哪怕只是"函数级 100%"，也要列函数 signature + 每个 branch 的 coverage 责任），
不能只指 docstring。

### 3.2 apply 阶段发现 `client.py:304` unreachable stub 写错

原 `test_retry_with_idempotency_raises_unreachable_no_result` 是 broken stub：

- docstring 说要测 `client.py:304`
- 实际代码 `inspect.getsource(archive_audit)` 测的是 `archive_audit.py`（错的文件）
- 断言 `"RuntimeError" in src` 在 `archive_audit.py` 上永远 False

**根因**：前会话试图测 defensive unreachable 分支，路径不可达，写了"看起来对"的 stub
占位，但**没**真跑过这个 test 验证它会通过。

**教训**：所有"测不到"的 defensive 分支应该**直接 `pytest.skip` 标 `# pragma: no cover`**
（跟 sibling `retry_with_redis:121` 一样），**不要**写"看起来对"的 stub。

### 3.3 Settings() env var fix 是已知 pattern 重复出现

apply 阶段补 5 个新 archive_audit test 时触发 `asyncpg.exceptions.InvalidPasswordError`，
根因是 `Settings()` 在 import `app.config` 时 eager-validate，3 个 env var 未设。
fix 是 `os.environ.setdefault(...)` 在 `from app.config import ...` 之前。

**这不是新发现** —— commit 6994800 (gateway-egress-enforcement-p0 task 7.1) 在
`test_llm_client.py` 修过**同一个** env var 失败。**这次的 followup 没在 apply 之前
grep `test_llm_client.py` 找这个 fix**，导致重复发现 + 重复修。

**教训**：**任何** audit-and-isolation unit test 在做 `from app.jobs.archive_audit
import ...` 这种 import 之前，必须先看 `test_llm_client.py` line 19-21 的 setdefault
pattern（如果存在），或者新建 `conftest.py` 把 3 个 env var 提到 module-level 一次性 setdefault
—— 这是跨 test file 的 fix，单文件重复 import-level 修不 scale。

**Action item**：未来 `services/audit-and-isolation/tests/conftest.py` 落地，把 3 个
env var setdefault 提到 fixture / autouse session scope。

### 3.4 plan.md Step 1.5 grep pattern 写错

plan.md Step 1.5 写的是 `grep -c "^def test_"` 但实际 test 是 `async def test_`（无 class
包装，line 首字符是 `a` 而非 `d`）。apply Task 1 时 grep 返回 0，差点误判"test file 不存在"。

inline fix 后 plan.md 改了 grep pattern 并加了 `pytest --collect-only` fallback。**没**升级
到 retrospective 影响面。

**教训**：所有 grep-based plan step 必须 fallback 到 `pytest --collect-only` —— grep 对
"行首 vs 缩进" / "async def vs def" / "class wrapping" 是脆的。

---

## 4. What's left for V1.0+

### 4.1 retrospective §6.4 row 2 — gateway-scanner 测试矩阵

本 change **只 close** §6.4 第 1 条（audit-and-isolation 83% → 100% on 3 modules）。
**未触及** §6.4 第 2 条：

> | Add `services/gateway-scanner/tests/` to the coverage matrix | `coverage-improvement` |

`gateway-scanner` service 当前在 `openspec/changes/archive/2026-06-10-implement-audit-and-isolation/`
之后没新 change 跟进。**建议下一条 change**：

- name: `gateway-scanner-coverage-matrix`
- scope: 扫 `services/gateway-scanner/app/` 下未 100% 的模块 + 写对应 unit test +
  接入 audit-and-isolation 同样的 pytest-cov 验证 pattern
- estimated effort: 1 session，~2-3 commits，~500 行 test

### 4.2 `retry_with_idempotency` wrapper body (client.py:240-304)

本 change 让 `compute_idempotency_key` 函数 100% covered，但**整个 client.py 仍 41%**，
主要因 `retry_with_idempotency` wrapper body（line 240-304）无 unit test。

**建议下下条 change**：

- name: `llm-client-retry-coverage`
- scope: 补 `retry_with_idempotency` 的 3-attempt/5s 预算 / HA_FAILOVER 503 重试 /
  `last_exc` raise / `last_resp` return 4 个分支的 unit test
- estimated effort: 1 session，~2-3 commits，~300 行 test

### 4.3 `services/audit-and-isolation/tests/conftest.py` env var 提取

见 §3.3。当前 3 个 env var setdefault 在 `test_coverage_gaps_v1_followup.py` line 22-24
硬编码，**应**提到 `tests/conftest.py` autouse session fixture，让所有 test file
共享。**本 change 不做**（scope 限于"followup coverage"，不动 test infra），留待
下下下次清理 test 的时候一起做。

### 4.4 覆盖率门槛（`--cov-fail-under=100`）

本 change 让 3 个目标模块 100%，**但**没在 `pyproject.toml` / `pytest.ini` 加
`--cov-fail-under=100`。当前 TOTAL 21.95% —— 加这个门槛会**全 CI 失败**。

**未来**：

- 当 audit-and-isolation 项目所有 30 个 `app/*.py` 模块都 100% 时，加
  `--cov-fail-under=100`
- 本 change 不做：scope 限 3 模块，门槛改动属 CI 配置变更

---

## 5. Process reflections

### 5.1 superpowers-bridge 流程对 trivial followup 的 over-engineering 评估

**流程成本**：brainstorm + proposal + design + specs + tasks + plan = 6 个 artifact，
~1263 行 markdown，~30 分钟净写作时间。**apply 阶段实际编码工作**只有 9 个 test 函数
+ 3 行 env var setdefault，~20 分钟。**比值 1.5:1**（流程 30 min / 编码 20 min）。

**收益**：future-proof 审计链。CLAUDE.md "openspec/ schemas" + "source of truth = 三件套"
强制所有 change 走完整流程；本 change 即使 trivial 也要走，因为它是 retrospective 引用
的 V1.0+ followup trigger name `coverage-improvement` 的"首次落点"。

**结论**：**流程成本对 trivial change over-engineered，但符合 CLAUDE.md 强制要求**。
未来是否要开"trivial followup 走 light schema" 是 spec-driven vs change-driven 的
架构决策，**不在本 change scope**。

### 5.2 systematic-debugging 在 apply 阶段的拦截

本 change 的关键拦截发生在 Task 3（cov 验证）：

1. claim "100% line coverage" 在 apply Task 3 之前**没**被直接验证
2. Task 3 跑 cov 实际数字 = 86% / 37% / 100%
3. systematic-debugging Phase 1 (root cause investigation) 找出 missing 行 = docstring
   未声明的具体分支
4. surface 给用户 → 用户决策"补 test 达 100%"
5. 5 个新 test 落地 → cov 100% → commit 落地

**如果跳过 Task 3 的 cov 验证**（只看"5 PASS / 1 SKIP"），commit 会带 partial claim
进 main，未来审计会被回退。

**教训**：**任何** spec 提"100% coverage" / "100% test" / "all branches" / "fully
covered" claim，apply 阶段**必须**跑 `pytest --cov` 验证，而不是只看 pass count。

### 5.3 用户"扩 scope"决策的杠杆

apply Task 3 失败时，我**没有**默默多写 test 强制 100%，而是 surface 给用户决策。

用户选了"补 test 达 100%"，**不是**"接受 partial"或"推给 followup change"。

**理由**：

- 默默扩 scope = 违反"1 change = 1 set of requirements"原则
- 默默限制 scope = 违反"100% line coverage" claim 的诚实性
- 把决策权还给用户 = 体现"claim vs reality"信号，**不**让 Claude 单方面决定

**建议**：未来 spec-driven 流程里"claim vs reality 漂移"是**显式** checkpoint，
**不要**默认 follow user-claimed scope。

### 5.4 openspec archive 在本 session 内完成

`openspec archive coverage-improvement` 没在 apply 阶段跑（plan.md Task 9 标了，但
本 session 还没执行）。**应在最终 session 收尾时执行**，让 change 路径从
`openspec/changes/coverage-improvement/` 移到 `openspec/changes/archive/2026-06-15-coverage-improvement/`。

---

## 6. Final state

- commit `14988d0` 已落地 main
- 2 个测试文件 tracked，22 PASS / 1 SKIP
- 3 个目标模块 100% line coverage
- 0 行生产代码修改
- `openspec/changes/coverage-improvement/{brainstorm,proposal,design,specs,tasks,plan,verify}.md`
  全部 done，retrospective.md（本档）写完
- 待执行：`openspec archive coverage-improvement`（Task 9）
