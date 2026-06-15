# gateway-scanner-coverage-matrix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `services/gateway-scanner/` 服务拉进跟 `services/audit-and-isolation/` 对齐的 cov 矩阵：改 `pyproject.toml` 加 `--cov=gateway_scanner --cov-fail-under=100`，补 test 让 `scanner.py` (65% → 100%) 和 `__main__.py` (0% → 100%) 达到 100% line coverage。关闭 `gateway-egress-enforcement-p0/retrospective.md §6.4` 第 2 条。

**Architecture:** 1 个 commit 包含 (1) 1 行 `pyproject.toml` config + (2) ~5-10 个新 test 函数（scanner.py ~3-5 + `__main__.py` ~3-5 CliRunner 测试）。0 行 `gateway_scanner/` 下 .py 改动。本 plan 是 tasks.md 的 micro-step 展开（每步 2-5 分钟）。

**Tech Stack:** pytest 8.x + pytest-cov 6.x + click 8.1（prod dep，含 `click.testing.CliRunner`）；conda env `chatbiz`（CLAUDE.md `conda-chatbiz-env` memory 强制）；git。

**参考 artifacts**:
- `openspec/changes/gateway-scanner-coverage-matrix/brainstorm.md` — 决议链
- `openspec/changes/gateway-scanner-coverage-matrix/proposal.md` — Why/What/Capabilities
- `openspec/changes/gateway-scanner-coverage-matrix/design.md` — Context/Goals/Decisions
- `openspec/changes/gateway-scanner-coverage-matrix/specs/gateway-scanner-coverage-100pct/spec.md` — 5 Requirements / 18 Scenarios
- `openspec/changes/gateway-scanner-coverage-matrix/tasks.md` — 7 个高阶 task
- `openspec/changes/coverage-improvement/{brainstorm,plan,retrospective}.md` — 模板参考

**产物路径说明**：本 plan 写在 `openspec/changes/gateway-scanner-coverage-matrix/plan.md` 而**非** writing-plans skill 默认的 `docs/superpowers/plans/`，因为 openspec schema 强制 plan.md 必须落在 change 目录下。

---

## Task 1: Verify baseline state (encoding prep)

**Files:**
- Verify (no modify): `services/gateway-scanner/gateway_scanner/scanner.py`
- Verify (no modify): `services/gateway-scanner/gateway_scanner/__main__.py`
- Verify (no modify): `services/gateway-scanner/pyproject.toml`

- [ ] **Step 1.1: 跑 baseline pytest 摸底**

```bash
cd /Users/paulwang/work/ChatBiz/services/gateway-scanner
conda activate chatbiz
pytest tests/ --cov=gateway_scanner --cov-report=term-missing --no-header 2>&1 | tail -20
```
Expected: `40 passed` + cov 表显示 `gateway_scanner/scanner.py ... 65%` + `gateway_scanner/__main__.py ... 0%`。
Failure: 任何 FAILED → 基线已坏，**停止**。

- [ ] **Step 1.2: 验证 pyproject.toml 当前 addopts 缺 cov flag**

```bash
grep -A 3 "tool.pytest.ini_options" /Users/paulwang/work/ChatBiz/services/gateway-scanner/pyproject.toml
```
Expected: 显示 `addopts = "-v"`（无 `--cov` / `--cov-fail-under`）。

- [ ] **Step 1.3: 验证 working tree 干净**

```bash
cd /Users/paulwang/work/ChatBiz
git status --porcelain services/gateway-scanner/
```
Expected: 空输出（除 `openspec/changes/gateway-scanner-coverage-matrix/` 仍 untracked，本 Task 不动）。

---

## Task 2: pyproject.toml config 变更

**Files:**
- Modify: `services/gateway-scanner/pyproject.toml` 第 `[tool.pytest.ini_options].addopts` 字段

- [ ] **Step 2.1: 改 addopts 字段**

打开 `services/gateway-scanner/pyproject.toml`,找到 `addopts = "-v"` 那一行,改成：

```toml
addopts = "-v --cov=gateway_scanner --cov-fail-under=100"
```

(与 `services/audit-and-isolation/pyproject.toml` 的
`addopts = "-v --cov=app --cov-report=term-missing --cov-fail-under=100"`
对齐;`--cov-report` 省略是因为 pytest-cov 默认输出 term-missing,本
change 不需要改报告格式。)

- [ ] **Step 2.2: 验证 config 语法正确**

```bash
cd /Users/paulwang/work/ChatBiz/services/gateway-scanner
conda activate chatbiz
pytest tests/ --no-cov 2>&1 | tail -3
```
Expected: `40 passed`（--no-cov 跳过 cov 收集，验证 config 语法没破）。
Failure: 任何错误 → pyproject.toml 改坏,`git restore services/gateway-scanner/pyproject.toml` 回滚。

- [ ] **Step 2.3: 验证 cov flag 触发报告**

```bash
pytest tests/ --no-header 2>&1 | grep -E "gateway_scanner/(scanner|__main__)\.py" | head -5
```
Expected: 输出含 `gateway_scanner/scanner.py ... 65%` + `gateway_scanner/__main__.py ... 0%`（即 cov 报告行被触发）。
Failure: 输出空 → `--cov=gateway_scanner` 没生效,回滚 2.1 检查语法。

---

## Task 3: 跑 cov 拿 missing lines (paired with Task 4-5 补 test)

**Files:** 无 modify,只跑 cov。

- [ ] **Step 3.1: 跑 cov 看 scanner.py + __main__.py 具体 missing lines**

```bash
cd /Users/paulwang/work/ChatBiz/services/gateway-scanner
pytest tests/ --cov=gateway_scanner --cov-report=term-missing --no-header 2>&1 | tail -10
```
Expected: cov 表显示 `Missing` 列含 `33, 52, 71-94, 102-105, 109-112, 122-125, 137, 175, 197, 211-213`（scanner.py）+ `14-99`（`__main__.py`）。
**注意**：具体 missing lines 可能在 apply 阶段跟 brainstorming 时略有差异（apply 阶段前已有 baseline 跑过 cov,evidence 已就位）。

- [ ] **Step 3.2: surface 给用户决策：test file 拆分**

问用户：
- 选项 A：1 个新 test file `tests/test_coverage_followup.py` 含所有新 test
- 选项 B：2 个新 test file `tests/test_scanner_cov.py` + `tests/test_main_cov.py`

推荐 A（跟 `coverage-improvement` 同 pattern,1 个文件好 git history）。
**预计时间**：1 分钟用户决策。

---

## Task 4: 补 scanner.py 100% coverage (paired with Task 5)

**Files:**
- Create: `services/gateway-scanner/tests/test_scanner_coverage.py`（若 Task 3.2 选 A,可并入 `test_coverage_followup.py`）
- 复用: 现有 5 个 test file（test_smoke / test_allowlist / test_blocklist / test_ast_scanner / test_workflow）

- [ ] **Step 4.1: 写 test 走 scanner.py line 33（`__str__` method）**

```python
def test_violation_str_returns_file_line_package() -> None:
    from gateway_scanner.scanner import Violation
    v = Violation(file=Path("a/b.py"), line=42, package="openai")
    assert str(v) == "a/b.py:42:openai"
```

- [ ] **Step 4.2: 跑 test 验证 PASS**

```bash
cd /Users/paulwang/work/ChatBiz/services/gateway-scanner
pytest tests/test_scanner_coverage.py::test_violation_str_returns_file_line_package -v --no-cov 2>&1 | tail -3
```
Expected: `1 passed in 0.01s`。

- [ ] **Step 4.3-4.7: 写剩余 ~4 个 test 走 scanner.py 其他 missing lines**

参考 spec.md Scenario:
- `ScannerConfig.target` property + blocklist / allowlist default frozenset
- `load_config` 解析 YAML blocklist + allowlist
- `scan_path` 在 blocklist package 出现时返回 Violation
- `scan_path` 在 allowlisted file 中不报 violation

每个 test 写完**立即**跑 `pytest tests/<file>::<test_name> -v --no-cov`
验证 PASS，再进下一个（TDD micro-cycle）。

- [ ] **Step 4.8: 跑 cov 验证 scanner.py 100%**

```bash
pytest tests/ --cov=gateway_scanner --cov-report=term-missing --no-header 2>&1 | grep -E "scanner\.py|__main__\.py"
```
Expected: `gateway_scanner/scanner.py ... 100%`。
Failure: < 100% → 4.3-4.7 漏写某个分支,补 test 回到对应 Step。

---

## Task 5: 补 `__main__.py` 100% coverage (CliRunner)

**Files:**
- 同 Task 4 的 test file（依 Task 3.2 决策）

- [ ] **Step 5.1: 写 test 走 `cli` exit code 0（0 violation）**

```python
def test_cli_exits_0_when_no_violations(tmp_path: Path) -> None:
    from click.testing import CliRunner
    from gateway_scanner.__main__ import cli

    runner = CliRunner()
    result = runner.invoke(cli, [str(tmp_path)])
    assert result.exit_code == 0
```

- [ ] **Step 5.2: 跑 test 验证 PASS**

```bash
pytest tests/<file>::test_cli_exits_0_when_no_violations -v --no-cov 2>&1 | tail -3
```
Expected: `1 passed`。

- [ ] **Step 5.3-5.7: 写剩余 ~4 个 test 走 `__main__.py` 其他分支**

参考 spec.md Scenario:
- exit code 1（≥1 violation）+ 含 openai 的 fixture
- exit code 2（path 不存在）
- 接受 `--config` / `--blocklist` / `--allowlist` 选项
- 默认从 `./gateway_scanner.yaml` 读 config
- 缺省 config 文件时使用空规则

每个 test 写完**立即**跑验证 PASS，再进下一个。

- [ ] **Step 5.8: 跑 cov 验证 `__main__.py` 100%**

```bash
pytest tests/ --cov=gateway_scanner --cov-report=term-missing --no-header 2>&1 | grep -E "scanner\.py|__main__\.py"
```
Expected: `gateway_scanner/scanner.py ... 100%` + `gateway_scanner/__main__.py ... 100%`。
Failure: < 100% → 5.3-5.7 漏写某个分支,补 test 回到对应 Step。

---

## Task 6: 验证 production diff = 0（仅 pyproject.toml 改）

**Files:** 全 `services/gateway-scanner/gateway_scanner/` 目录。

- [ ] **Step 6.1: git diff working tree vs HEAD on prod code**

```bash
cd /Users/paulwang/work/ChatBiz
git diff --stat services/gateway-scanner/gateway_scanner/
```
Expected: **空输出**。
Failure: 非空 → 意外改了 prod code,**停止**。**不**进 commit,先 revert。

- [ ] **Step 6.2: 跑完整 cov 验证 100% + exit code 0**

```bash
cd /Users/paulwang/work/ChatBiz/services/gateway-scanner
pytest tests/ --cov=gateway_scanner --cov-fail-under=100 2>&1 | tail -3
echo "exit=$?"
```
Expected: `2 modules, 100% covered` 类消息 + `exit=0`。
Failure: `exit!=0` → coverage < 100%,回 Task 4 / 5 补 test。

---

## Task 7: git add + commit

**Files:**
- Add: `services/gateway-scanner/pyproject.toml`（1 行改）
- Add: `services/gateway-scanner/tests/<new_file>.py`（~5-10 个 test）

- [ ] **Step 7.1: git add**

```bash
cd /Users/paulwang/work/ChatBiz
git add services/gateway-scanner/pyproject.toml services/gateway-scanner/tests/
git status --short services/gateway-scanner/
```
Expected: `M  services/gateway-scanner/pyproject.toml` + `?? services/gateway-scanner/tests/<new>.py`（A 状态） 或 `M`（既有 test 改）。

- [ ] **Step 7.2: git commit with full message**

```bash
cd /Users/paulwang/work/ChatBiz
git commit -m "test(gateway-scanner): close retrospective §6.4 row 2 — 100% line cov + cov matrix

* pyproject.toml: addopts 加 '--cov=gateway_scanner --cov-fail-under=100'
  （与 audit-and-isolation 对齐 cov 矩阵）
* scanner.py: 65% → 100%（具体 test list 见 verify.md §1）
* __main__.py: 0% → 100%（CliRunner 6 个 Scenario 覆盖）

Openspec: openspec/changes/gateway-scanner-coverage-matrix/
Source trigger: gateway-egress-enforcement-p0/retrospective.md §6.4
Verification: openspec/changes/gateway-scanner-coverage-matrix/verify.md

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 7.3: verify commit**

```bash
git log -1 --stat
```
Expected: commit hash + `pyproject.toml` + `tests/<new>.py` change,无 `gateway_scanner/` 下 .py 改动。
Failure: 含 `gateway_scanner/` 下 .py → 立即 `git reset HEAD~1` + Task 6 排查。

---

## Task 8: 写 verify.md (apply 阶段证据固化)

**Files:**
- Create: `openspec/changes/gateway-scanner-coverage-matrix/verify.md`

- [ ] **Step 8.1: 收集 Task 1 / 2 / 4 / 5 / 6 / 7 的实际 command output**

把以下 stdout 完整复制到 verify.md:
- Task 1.1: baseline cov 数字（scanner.py 65% / `__main__.py` 0%）
- Task 4.8: scanner.py 100% 截图
- Task 5.8: `__main__.py` 100% 截图
- Task 6.1: `git diff` 输出（空）
- Task 7.3: `git log -1 --stat`

- [ ] **Step 8.2: 写 verify.md（5-section 模板）**

模板（参考 `coverage-improvement/verify.md`）：

```markdown
# Verify: gateway-scanner-coverage-matrix

**Date**: <apply 日期>
**Change**: openspec/changes/gateway-scanner-coverage-matrix/
**Trigger**: gateway-egress-enforcement-p0/retrospective.md §6.4 row 2
**Commit**: <Task 7.3 的 commit hash>

## §1. pytest baseline
\```
<paste Task 1.1>
\```

## §2. pyproject.toml config
\```
<paste Task 2.3>
\```

## §3. scanner.py 100% cov
\```
<paste Task 4.8>
\```

## §4. __main__.py 100% cov
\```
<paste Task 5.8>
\```

## §5. production diff = 0
\```
<paste Task 6.1>
\```

## §6. commit evidence
\```
<paste Task 7.3>
\```

## §7. summary
- 2 target modules 100% line coverage
- pyproject.toml 1 line addopts changed
- 0 production code modified
- 1 commit on main
```

---

## Task 9: 写 retrospective.md (apply 阶段收尾)

**Files:**
- Create: `openspec/changes/gateway-scanner-coverage-matrix/retrospective.md`

- [ ] **Step 9.1: 写 5-section retrospective**

模板（参考 `coverage-improvement/retrospective.md`）：

```markdown
# Retrospective: gateway-scanner-coverage-matrix

**Date range**: <开始> → <结束>
**Trigger**: gateway-egress-enforcement-p0/retrospective.md §6.4 row 2

## 1. What was built
- 1 commit, 1 line pyproject.toml + ~5-10 test
- 2 modules 100% line coverage
- 0 production code modified

## 2. What went well
- (填：cli 测用 CliRunner 零新 dep)
- (填：跟 coverage-improvement 同 pattern 复用)

## 3. What didn't go well
- (填：scanner.py 38 missing 是哪些具体分支,需要 apply 跑 cov 后才知道)
- (填：跟 coverage-improvement 共有的 "claim vs reality" 漂移)

## 4. What's left for V1.0+
- NG1 nested 空目录 services/gateway-scanner/services/gateway-scanner/tests/ — 留 scaffold-cleanup
- NG2 CI workflow 改造 — 留 ci-coverage-all-services
- (任何 apply 阶段发现的新 followup)

## 5. Process reflections
- (填：跟 coverage-improvement 的 "1.5:1 流程/编码 比" 对比)
- (填：是否真的需要 design doc 落地 vs openspec design.md)
```

---

## Task 10: openspec archive + git push

**Files:** 全 `openspec/changes/gateway-scanner-coverage-matrix/` 目录被 move 到 `openspec/changes/archive/2026-06-15-gateway-scanner-coverage-matrix/`。

- [ ] **Step 10.1: 改 tasks.md 标记全部 [x]**

```bash
sed -i '' 's/^- \[ \]/- [x]/g' /Users/paulwang/work/ChatBiz/openspec/changes/gateway-scanner-coverage-matrix/tasks.md
```

- [ ] **Step 10.2: openspec archive**

```bash
cd /Users/paulwang/work/ChatBiz
yes y | openspec archive gateway-scanner-coverage-matrix 2>&1 | tail -10
```

- [ ] **Step 10.3: 验证 archive 落地**

```bash
ls openspec/changes/archive/ | grep gateway-scanner-coverage-matrix
openspec list 2>&1 | grep -c "gateway-scanner-coverage-matrix"
```
Expected: `2026-06-15-gateway-scanner-coverage-matrix` + grep count = 0（已 archive,不在 active）。

- [ ] **Step 10.4: git add + commit openspec archive + 新 spec**

```bash
cd /Users/paulwang/work/ChatBiz
git add openspec/changes/archive/2026-06-15-gateway-scanner-coverage-matrix/
git add openspec/specs/gateway-scanner-coverage-100pct/
git commit -m "chore(openspec): archive gateway-scanner-coverage-matrix

* 8 artifacts archived
* new capability spec delta applied
* closes retrospective §6.4 row 2

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 10.5: git push origin main**

```bash
git push origin main 2>&1 | tail -5
```
Expected: `<old_hash>..<new_hash> main -> main`。

---

## Self-Review(plan 自查)

**1. Spec coverage**:
- `### Requirement: gateway_scanner.scanner 模块 100% 单元测试覆盖` → Task 4
- `### Requirement: gateway_scanner.__main__ 模块 100% 单元测试覆盖` → Task 5
- `### Requirement: pyproject.toml coverage matrix 配置` → Task 2
- `### Requirement: 既有 5 个 test file 40 PASS 不被破坏` → Task 1.1 / 2.2
- `### Requirement: 既有生产代码契约不变` → Task 6.1
- 全部 5 Requirement 有对应 Task。✓

**2. Placeholder scan**:
- 无 `TBD` / `TODO` / `implement later`
- 所有 `git commit -m` 给完整 message
- 所有 pytest 命令给完整路径
- 所有 expected output 明确（不是 "should work"）

**3. Type consistency**:
- `gateway_scanner/scanner.py` / `__main__.py` 命名一致
- `CliRunner` 命名一致
- `coverage-improvement` / `gateway-scanner-coverage-matrix` 引用链一致
- 无 type / 命名漂移

## Execution Handoff

Plan 已落地。Apply 启动：直接顺序跑 Task 1-10，跟 `coverage-improvement` apply 阶段同 pattern。
