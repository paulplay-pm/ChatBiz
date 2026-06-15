# ci-coverage-all-services Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 创建一个 orchestrator change scaffold,产出 6 个 sub-change 目录 (`ci-coverage-{audit-isolation,gateway-scanner,workflow-engine,sso,mcp,credential}`) + 各自 6 artifact 模板。本 change 自己 0 行 prod 改动,6 sub-change 各自走 apply chain 在 1-2 周内 followup。

**Architecture:** 一次性 `openspec new change` × 6 + 模板填空 × 36 artifact。Orchestrator change 性质:不直接改 prod,只 scaffold 6 sub-change。`openspec new change <name>` CLI 自动生成 `.openspec.yaml` scaffold。模板复用 3 个前 coverage change 的 6 artifact 结构。

**Tech Stack:** openspec CLI + 3 个前 coverage change 的 6 artifact 模板 (markdown)。git。

**参考 artifacts**:
- `openspec/changes/ci-coverage-all-services/{brainstorm,proposal,design}.md` — 已写
- `openspec/changes/ci-coverage-all-services/specs/ci-coverage-all-services-orchestrator/spec.md` — 4 Requirements
- `openspec/changes/ci-coverage-all-services/tasks.md` — 5 个高阶 task
- `openspec/changes/coverage-improvement/`, `gateway-scanner-coverage-matrix/`, `llm-client-retry-coverage/` — 6 artifact 模板来源

**产物路径**:本 plan 落在 openspec 强制路径 `openspec/changes/ci-coverage-all-services/plan.md`。

---

## Task 1: Verify 6 service baseline (encoding prep)

**Files:** Verify-only。

- [ ] **Step 1.1: 跑 6 service pytest 摸底**
```bash
cd /Users/paulwang/work/ChatBiz
for svc in audit-and-isolation gateway-scanner workflow-engine credential sso mcp; do
  echo "===== $svc ====="
  cd "services/$svc" && conda run -n chatbiz pytest tests/ --collect-only -q 2>&1 | grep "tests collected" | head -1 && cd ../..
done 2>&1 | tail -10
```
Expected: 6 service test count 跟 tasks.md 1.1 一致 (384 / 68 / 287 / 4+15err / 8 / 183)。

- [ ] **Step 1.2: 跑 6 service pyproject cov config check**
```bash
for svc in audit-and-isolation gateway-scanner workflow-engine credential sso mcp; do
  echo "===== $svc ====="
  grep -A 1 "addopts" "services/$svc/pyproject.toml" 2>/dev/null | head -3
done 2>&1
```
Expected: 0/6 含 `--cov-fail-under`。

---

## Task 2: 创建 6 sub-change scaffold (1 minute per)

**Files:** 新增 6 个 `openspec/changes/ci-coverage-*/.openspec.yaml` + 空目录。

- [ ] **Step 2.1: openspec new change × 6**
```bash
cd /Users/paulwang/work/ChatBiz
for name in audit-isolation gateway-scanner workflow-engine sso mcp credential; do
  openspec new change "ci-coverage-$name" 2>&1 | tail -1
done
```
Expected: 6 个 "Created change 'ci-coverage-XXX' at openspec/changes/ci-coverage-XXX/" 行。

- [ ] **Step 2.2: 验证 6 sub-change 创建**
```bash
ls openspec/changes/ci-coverage-*/
```
Expected: 6 个目录,每个含 `.openspec.yaml`。

---

## Task 3: 写 6 sub-change 的 6 artifact (3.1 - 3.6)

每个 sub-change 模板填空复用前 3 个 coverage change 结构。

### 3.1 `ci-coverage-gateway-scanner` (trivial, ~10 min apply)
- [ ] **Step 3.1.1-3.1.6**: 写 6 artifact(模板填空, 见 `coverage-improvement/tasks.md` 同结构)

### 3.2 `ci-coverage-audit-isolation` (大, ~2 hours apply)
- [ ] **Step 3.2.1-3.2.6**: 写 6 artifact,含 41 module 摸底(3 个已 100% module + client.py 之外)

### 3.3 `ci-coverage-workflow-engine` (中, ~1.5 hours apply)
- [ ] **Step 3.3.1-3.3.6**: 写 6 artifact,含 63 prod file 摸底

### 3.4 `ci-coverage-mcp` (小, ~30 min apply)
- [ ] **Step 3.4.1-3.4.6**: 写 6 artifact,含 13 prod file 摸底

### 3.5 `ci-coverage-sso` (小, ~30 min apply)
- [ ] **Step 3.5.1-3.5.6**: 写 6 artifact,含 17 prod file 摸底

### 3.6 `ci-coverage-credential` (最大, ~2 hours apply)
- [ ] **Step 3.6.1**: 跑 `pytest services/credential/tests/` 拿 15 errors 完整 traceback
- [ ] **Step 3.6.2**: surface 15 errors 给用户决策(setup 错 / env var 缺 / db fixture 缺)
- [ ] **Step 3.6.3-3.6.8**: 写 6 artifact, plan.md 第一步显式列"修 15 errors"

---

## Task 4: 验证 prod diff = 0 (本 orchestrator change)

```bash
cd /Users/paulwang/work/ChatBiz
git diff --stat services/
```
Expected: **空输出**。

- [ ] **Step 4.1**: 跑 prod diff 验证
- [ ] **Step 4.2**: `git status --short` 确认仅 openspec/changes/ci-coverage-*/ 新增

---

## Task 5: git add + commit (本 orchestrator change)

- [ ] **Step 5.1: git add 7 个目录**
```bash
git add openspec/changes/ci-coverage-*/(本 orchestrator change 也在内, 因 .openspec.yaml scaffold 包含本 change 目录)
```

- [ ] **Step 5.2: git commit with full message** (见 tasks.md 5.2)

- [ ] **Step 5.3: 验证 commit 仅 openspec/ 改动**

---

## Task 6: 写 verify.md + retrospective.md

- [ ] **Step 6.1**: 收集 6 service pytest 摸底 + prod diff + commit 数据
- [ ] **Step 6.2**: 写 verify.md(5-section 模板)
- [ ] **Step 6.3**: 写 retrospective.md(5-section 模板, 强调 NG1 NG2 NG3 仍未 close, 6 sub-change followup chain 启动)

---

## Task 7: openspec archive (本 orchestrator change apply 收尾)

- [ ] **Step 7.1**: sed tasks.md 全勾 [x]
- [ ] **Step 7.2**: `yes y | openspec archive ci-coverage-all-services`
- [ ] **Step 7.3**: 验证 archive 落地 + 6 sub-change 在 active list
- [ ] **Step 7.4**: git add archive + commit + push

---

## Self-Review

**1. Spec coverage**:
- 6 sub-change scaffold 创建 → Task 2
- 每个 sub-change 6 artifact 齐 → Task 3
- 命名一致 → Task 2.2 验证
- 各自独立 apply → 6 sub-change 互不依赖
- 6 sub-change 加同 1 套 pyconfig pattern → 各 sub-change apply
- 0 行 prod 改动 → Task 4

4 个 Requirement 全部有对应 Task。✓

**2. Placeholder scan**: 无 TBD / TODO / "should work"

**3. Type consistency**: `ci-coverage-{svc}` 命名一致
