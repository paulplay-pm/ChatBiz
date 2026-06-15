# coverage-improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 working tree 中 2 个 untracked 测试文件 formalize 进 openspec 审计链，关闭 `gateway-egress-enforcement-p0/retrospective.md §6.4` 第 1 条的 `coverage-improvement` followup（audit-and-isolation 项目 3 个目标模块 100% 单元覆盖）。

**Architecture:** 纯测试 followup，0 行生产代码修改。2 个 untracked 文件已经写完且 12 passed / 1 skipped 跑过，本 plan 的工作仅是：(1) verify working tree 状态无回退、(2) `pytest-cov` 验证 3 个目标模块 100%、(3) `git add` + 1 个 commit + openspec archive。

**Tech Stack:** pytest 8.x + pytest-asyncio + pytest-cov（`services/audit-and-isolation/` dev 依赖已锁）；conda env `chatbiz`（CLAUDE.md `conda-chatbiz-env` memory 强制）；git。

**参考 artifacts**:
- `openspec/changes/coverage-improvement/brainstorm.md` — 决议链
- `openspec/changes/coverage-improvement/proposal.md` — Why/What/Capabilities
- `openspec/changes/coverage-improvement/design.md` — Context/Goals/Decisions
- `openspec/changes/coverage-improvement/specs/audit-isolation-coverage-100pct/spec.md` — 6 Requirements / 14 Scenarios
- `openspec/changes/coverage-improvement/tasks.md` — 11 个高阶 task（本 plan 是其 micro-step 展开）
- `openspec/changes/archive/2026-06-15-gateway-egress-enforcement-p0/retrospective.md §6.4` — 触发源

**产物路径说明**：本 plan 写在 `openspec/changes/coverage-improvement/plan.md` 而**非** writing-plans skill 默认的 `docs/superpowers/plans/`，因为 openspec schema 强制 plan.md 必须落在 change 目录下。CLAUDE.md 强制所有 change 走 `openspec/` schemas。

---

## Task 1: Verify working tree state (encoding prep)

**Files:**
- Verify (no modify): `services/audit-and-isolation/tests/unit/test_coverage_gaps_v1_followup.py`
- Verify (no modify): `services/audit-and-isolation/tests/unit/test_routing_table_coverage.py`

- [ ] **Step 1.1: 确认 working tree 起点**

```bash
cd /Users/paulwang/work/ChatBiz
git status --porcelain services/audit-and-isolation/tests/unit/
```
Expected output:
```
?? services/audit-and-isolation/tests/unit/test_coverage_gaps_v1_followup.py
?? services/audit-and-isolation/tests/unit/test_routing_table_coverage.py
```
Failure: 若任一文件已是 tracked (`A ` / `M `) → 本 change apply 已被前会话完成，**停止**并报告 user。

- [ ] **Step 1.2: 确认 `await_archive_old_audit_logs` 已删除**

```bash
grep -c "await_archive_old_audit_logs" \
  services/audit-and-isolation/tests/unit/test_coverage_gaps_v1_followup.py
```
Expected: `0`
Failure: 非 0 → 未删除干净，**停止**并修（这意味着 session 中断导致前一次删除没保存）。

- [ ] **Step 1.3: 确认 stub test 改为 pytest.skip**

```bash
grep -c "pytest.skip" \
  services/audit-and-isolation/tests/unit/test_coverage_gaps_v1_followup.py
```
Expected: `>= 1`（实际 1）

- [ ] **Step 1.4: 确认 stub docstring 引用 sibling `# pragma: no cover` 约定**

```bash
grep -c "pragma: no cover" \
  services/audit-and-isolation/tests/unit/test_coverage_gaps_v1_followup.py
```
Expected: `>= 1`（实际 1，引用 `retry_with_redis:121`）

- [ ] **Step 1.5: 确认 `test_routing_table_coverage.py` 含 7 个 test**

```bash
grep -c "def test_" \
  services/audit-and-isolation/tests/unit/test_routing_table_coverage.py
```
Expected: `7`（注意：是 `def test_` 而**非** `^def test_`，因为该文件的 test 在
`async def` 形式，pytest 仍能 collect 到，但行首 `^` 会 miss）
Failure: < 7 → 缺失 test，重写或恢复该 test 函数。
更稳的验证：`pytest --collect-only -q tests/unit/test_routing_table_coverage.py`
应报 `7 tests collected`。

- [ ] **Step 1.6: Commit this verification (optional)**

本 Task 仅 verify，不修代码，无 commit。直接进 Task 2。

---

## Task 2: pytest 单元测试 12 passed / 1 skipped (paired verification of Task 1)

**Files:**
- Run-only: `services/audit-and-isolation/tests/unit/test_coverage_gaps_v1_followup.py`
- Run-only: `services/audit-and-isolation/tests/unit/test_routing_table_coverage.py`

- [ ] **Step 2.1: 激活 conda 环境**

```bash
conda activate chatbiz
```
Expected: prompt 前缀从 `(base)` 变为 `(chatbiz)`。**不**激活将导致 `from app.jobs.archive_audit import ...` 失败（memory `conda-chatbiz-env` 强制）。

- [ ] **Step 2.2: 跑目标测试文件（无 cov）**

```bash
cd /Users/paulwang/work/ChatBiz/services/audit-and-isolation
pytest tests/unit/test_coverage_gaps_v1_followup.py \
       tests/unit/test_routing_table_coverage.py \
       -v --no-cov 2>&1 | tail -20
```
Expected: `12 passed, 1 skipped in 0.13s`（实际 0.13-0.32s，取决于机器）。
Failure: 任何 `FAILED` 或 `ERROR` → 立即停止，**不**进 commit，**不**进 archive。回到 Task 1 排查。

- [ ] **Step 2.3: 确认 skip 的 test 是预期的那个**

```bash
pytest tests/unit/test_coverage_gaps_v1_followup.py \
       tests/unit/test_routing_table_coverage.py \
       -v --no-cov 2>&1 | grep SKIPPED
```
Expected: 输出含 `test_retry_with_idempotency_raises_unreachable_no_result`。
Failure: SKIP 的不是预期 test → 检查是不是 step 2.2 输出 read 错了。

- [ ] **Step 2.4: 收集 exit code**

```bash
pytest tests/unit/test_coverage_gaps_v1_followup.py \
       tests/unit/test_routing_table_coverage.py \
       --no-cov > /tmp/cov_imp_step2_4.log 2>&1
echo "exit=$?"
```
Expected: `exit=0`（pytest 默认 PASS 集合包含 SKIP 时仍返回 0）。
Failure: `exit!=0` → 立即停止，task 2 失败，**不**进 commit。

---

## Task 3: pytest-cov 验证 3 个目标模块 100%

**Files:** 复用 Task 2 的 2 个 test file；本 Task 只跑 --cov。

- [ ] **Step 3.1: 跑 archive_audit 模块 cov**

```bash
cd /Users/paulwang/work/ChatBiz/services/audit-and-isolation
pytest tests/unit/test_coverage_gaps_v1_followup.py \
       --cov=app.jobs.archive_audit \
       --cov-report=term-missing --no-header 2>&1 | tail -10
```
Expected: `app/jobs/archive_audit.py ... 100%`
Failure: 任何 < 100% → Task 1.1 / Task 1.2 验证有漏，检查 stub test 的 assert 边界条件。

- [ ] **Step 3.2: 跑 client.compute_idempotency_key 模块 cov**

```bash
pytest tests/unit/test_coverage_gaps_v1_followup.py \
       --cov=app.llm.client \
       --cov-report=term-missing --no-header 2>&1 | tail -10
```
Expected: `app/llm/client.py ... TOTAL < 100%`（因 wrapper body 240-304 不在本 change scope），**但** `compute_idempotency_key` 函数相关的行号（188-193）必须被覆盖。`--cov-report=term-missing` 会列出 missing lines。
Acceptance: missing lines 中**不**含 188-193。允许 missing lines = 240-304（wrapper body）+ 121（`retry_with_redis` 标 `# pragma: no cover`）。
Failure: 188-193 出现在 missing lines → `test_compute_idempotency_key_handles_non_dict_non_str_body` 或 `test_compute_idempotency_key_handles_none_body` 没跑覆盖到位。

- [ ] **Step 3.3: 跑 routing.table 模块 cov**

```bash
pytest tests/unit/test_routing_table_coverage.py \
       --cov=app.routing.table \
       --cov-report=term-missing --no-header 2>&1 | tail -10
```
Expected: `app/routing/table.py ... 100%`
Failure: < 100% → 检查 7 个 test 是否覆盖到 `load_routing` Redis pipeline 失败 + `get_routing` garbage data fallback 路径。

---

## Task 4: 生产代码 diff 为零验证 (non-regression check)

**Files:** 全 `services/audit-and-isolation/app/` 目录。

- [ ] **Step 4.1: git diff working tree vs HEAD on app/**

```bash
cd /Users/paulwang/work/ChatBiz
git diff --stat services/audit-and-isolation/app/
```
Expected: **空输出**（HEAD 与 working tree 在 `app/` 下无差异）。
Failure: 非空 → 意外改了生产代码，**停止**。**不**进 commit，必须先 revert app/ 下的 accidental edit。

- [ ] **Step 4.2: git diff staged vs HEAD on app/**

```bash
git diff --cached --stat services/audit-and-isolation/app/
```
Expected: **空输出**。
Failure: 非空 → 之前 `git add` 时误加了 app/ 文件，**停止**并 `git restore --staged`。

---

## Task 5: git add 2 个 test file (formalize 进仓库)

**Files:**
- Add: `services/audit-and-isolation/tests/unit/test_coverage_gaps_v1_followup.py`
- Add: `services/audit-and-isolation/tests/unit/test_routing_table_coverage.py`

- [ ] **Step 5.1: git add**

```bash
cd /Users/paulwang/work/ChatBiz
git add \
  services/audit-and-isolation/tests/unit/test_coverage_gaps_v1_followup.py \
  services/audit-and-isolation/tests/unit/test_routing_table_coverage.py
```

- [ ] **Step 5.2: git status verify staged**

```bash
git status --short services/audit-and-isolation/tests/unit/
```
Expected:
```
A  services/audit-and-isolation/tests/unit/test_coverage_gaps_v1_followup.py
A  services/audit-and-isolation/tests/unit/test_routing_table_coverage.py
```
Failure: 任一文件状态不是 `A` → add 失败，重做 Step 5.1。

- [ ] **Step 5.3: git diff --cached 确认仅 test files**

```bash
git diff --cached --stat
```
Expected: 2 个文件，`+` 行数 = 7,558 (test_coverage_gaps_v1_followup.py, 190 行) + 8,924 bytes (test_routing_table_coverage.py, 估算 ~250 行)。0 个 app/ 文件。

---

## Task 6: git commit (single commit, 完整 message)

**Files:** 复用 Task 5 的 staged 状态。

- [ ] **Step 6.1: git commit with full message**

```bash
cd /Users/paulwang/work/ChatBiz
git commit -m "test(audit-isolation): close retrospective §6.4 row 1 — coverage 83% → 100% on 3 modules

* archive_audit: duration_seconds property + row-count-mismatch
  warning path (190 行测试, 5 PASS + 1 SKIP for defensive
  client.py:304)
* llm/client.compute_idempotency_key: non-dict/non-str/None
  body fallback (lines 188-193)
* routing/table: load_routing + get_routing full path
  (in-memory + Redis pipeline + Redis-down fallback + garbage
  data fallback + unknown-model returns None) — 7 PASS

Openspec: openspec/changes/coverage-improvement/
Source trigger: gateway-egress-enforcement-p0/retrospective.md §6.4
Verification: 12 passed, 1 skipped; 3 target modules 100% line cov

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 6.2: verify commit**

```bash
git log -1 --stat
```
Expected: commit hash + 2 个 file change，diff stat 行数 = 2 行（test file 1 + test file 2），无 app/ 下任何文件。
Failure: diff stat 含 app/ 文件 → 立即 `git reset HEAD~1` 并回到 Task 4.1 排查。

- [ ] **Step 6.3: verify working tree clean**

```bash
git status --short services/audit-and-isolation/
```
Expected: 空输出（除 `openspec/changes/coverage-improvement/` 仍 untracked，因本 Task 5 没 add openspec change —— openspec 走 archive 流程，不是 git commit）。

---

## Task 7: 写 verify.md (apply 阶段证据固化)

**Files:**
- Create: `openspec/changes/coverage-improvement/verify.md`

- [ ] **Step 7.1: 收集 Task 2 / 3 / 4 的实际 command output**

把以下 3 段 stdout 完整复制到 verify.md:
- Task 2.2: `12 passed, 1 skipped` pytest output
- Task 3.1 / 3.2 / 3.3: 3 个 cov report（重点：100% 行号 + missing lines 不含 188-193 / 290-295 / 94）
- Task 4.1: `git diff --stat services/audit-and-isolation/app/` = 空

- [ ] **Step 7.2: 写 verify.md（参考 gateway-egress-enforcement-p0/verify.md 结构）**

模板：
```markdown
# Verify: coverage-improvement

**Date**: <实际 apply 日期>
**Change**: openspec/changes/coverage-improvement/
**Trigger**: gateway-egress-enforcement-p0/retrospective.md §6.4 row 1

## §1. pytest 12 passed / 1 skipped

\```
<paste Task 2.2 output>
\```

## §2. pytest-cov 3 target modules 100%

### §2.1 archive_audit
\```
<paste Task 3.1 output>
\```

### §2.2 client.compute_idempotency_key
\```
<paste Task 3.2 output>
\```

### §2.3 routing.table
\```
<paste Task 3.3 output>
\```

## §3. production diff = 0
\```
<paste Task 4.1 output — 空>
\```

## §4. commit evidence
\```
<paste Task 6.2 output>
\```

## §5. summary
- 3 个目标模块达到 100% line coverage
- 1 个 defensive unreachable 分支显式 skip
- 0 行生产代码修改
- 1 个 commit 落地
```

---

## Task 8: 写 retrospective.md (apply 阶段收尾)

**Files:**
- Create: `openspec/changes/coverage-improvement/retrospective.md`

- [ ] **Step 8.1: 写 5-section retrospective**

模板（参考 `gateway-egress-enforcement-p0/retrospective.md`）：
```markdown
# Retrospective: coverage-improvement

**Date range**: <开始> → <结束>
**Trigger**: gateway-egress-enforcement-p0/retrospective.md §6.4 row 1

## 1. What was built
- 1 commit，2 个 test file
- 3 个模块达到 100% line coverage
- 1 个 defensive 分支显式 skip

## 2. What went well
- (填：2 untracked 文件 → formalize 的成本低)
- (填：open Q 一次性问完)

## 3. What didn't go well
- (填：stub test 改成 skip 的取舍)
- (填：retrospective §6.4 第 2 条仍未 close)

## 4. What's left for V1.0+
- gateway-scanner 测试矩阵改造（retrospective §6.4 row 2）
- (任何 apply 阶段发现的新 followup)

## 5. Process reflections
- (填：spec-driven 流程对 trivial test followup 是否 over-engineered)
```

---

## Task 9: openspec archive (change 收尾)

**Files:** 全 `openspec/changes/coverage-improvement/` 目录被 move 到 `openspec/changes/archive/2026-06-15-coverage-improvement/`。

- [ ] **Step 9.1: openspec archive**

```bash
cd /Users/paulwang/work/ChatBiz
openspec archive coverage-improvement
```
Expected: CLI 打印 "Archived change 'coverage-improvement' to openspec/changes/archive/2026-06-15-coverage-improvement/"

- [ ] **Step 9.2: 验证 archive 落地**

```bash
ls openspec/changes/archive/ | grep coverage-improvement
```
Expected: `2026-06-15-coverage-improvement`

- [ ] **Step 9.3: 验证 active change list 移除本 change**

```bash
openspec list 2>&1 | grep -c "coverage-improvement"
```
Expected: `0`（已 archive，不在 active list）
Failure: `>= 1` → archive 失败，回到 Step 9.1。

---

## Self-Review(plan 自查)

**1. Spec coverage**:
- `### Requirement: archive_audit 模块 100% 单元测试覆盖` → Task 3.1
- `### Requirement: llm/client.compute_idempotency_key 100% 单元测试覆盖` → Task 3.2
- `### Requirement: routing/table 模块 100% 单元测试覆盖` → Task 3.3
- `### Requirement: 测试套件位置与命名规范` → Task 1.1 / 1.2 / 1.5
- `### Requirement: pytest 收集与运行产物可预期` → Task 2.2 / 2.3
- `### Requirement: 既有生产代码契约不变` → Task 4.1 / 4.2 / 6.2
- 全部 6 个 Requirement 有对应 Task。✓

**2. Placeholder scan**:
- 无 `TBD` / `TODO` / `implement later`
- 无 "Similar to Task N" 引用
- 所有 `git commit -m` 给完整 message
- 所有 pytest 命令给完整路径
- 所有 expected output 明确（不是 "should work"）

**3. Type consistency**:
- `test_retry_with_idempotency_raises_unreachable_no_result` — 在 brainstorm / design / tasks / plan 一致
- `await_archive_old_audit_logs` — 一致
- `client.py:304` — 一致
- `retry_with_redis:121` — 一致
- `gateway-egress-enforcement-p0/retrospective.md §6.4` — 一致
- 无 type / 命名漂移

## Execution Handoff

Plan 已落地。两种执行方式：

1. **Subagent-Driven (推荐)**:用 `superpowers:subagent-driven-development`,每个 Task 一个 fresh subagent,task 间 review。本 change Task 数 9 个,subagent cost 较高但 review 粒度细。
2. **Inline Execution**:用 `superpowers:executing-plans`,本 session 顺序执行,batch + checkpoint。

按 apply 阶段默认 flow,选 **2. Inline Execution**(本 change 是 trivial test followup,不需要 subagent 隔离)。orchestrator 直接顺序跑 Task 1-9。

实际 apply 启动命令:`/opsx:apply` 或对 Claude 说 "implement coverage-improvement"。
