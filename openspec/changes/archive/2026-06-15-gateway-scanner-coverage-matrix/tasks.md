## 1. 验证现状（working tree baseline）

- [x] 1.1 验证 `services/gateway-scanner/` 处于基线状态：
  5 个 test file / 40 PASS，`scanner.py` 65% / `__main__.py` 0% /
  TOTAL 50%。**预期**：
  `cd services/gateway-scanner && conda activate chatbiz &&
  pytest tests/ --cov=gateway_scanner --cov-report=term-missing --no-header`
  输出 `40 passed in ~0.3s` + cov 表显示上述百分比。**owner**：
  apply 阶段开始时由 orchestrator 复核。**预计时间**：3 分钟。

- [x] 1.2 验证 `pyproject.toml` 当前 `addopts = "-v"` 缺
  `--cov=gateway_scanner` 与 `--cov-fail-under=100`。
  **预期**：`grep -A 3 "tool.pytest.ini_options" services/gateway-scanner/pyproject.toml`
  显示 `addopts = "-v"` 单行。**预计时间**：1 分钟。

## 2. pyproject.toml 配置变更（pyproject 是 prod 文件）

- [x] 2.1 改 `services/gateway-scanner/pyproject.toml`：
  `addopts = "-v"` → `addopts = "-v --cov=gateway_scanner --cov-fail-under=100"`。
  **owner**：apply 阶段 orchestrator 直接 Edit。**预计时间**：1 分钟。

- [x] 2.2 验证 `pytest tests/` 在改后能跑（baseline 40 PASS 不被
  `--cov` 触发 0 退出码问题影响）：
  `cd services/gateway-scanner && pytest tests/ --no-cov` 应仍 40 PASS。
  **预计时间**：2 分钟。
  **若失败**：config 语法错，回滚 2.1。

## 3. 单元测试验证 baseline（编码后验证 task 4-5 的新 test）

- [x] 3.1 跑 cov 拿 scanner.py / `__main__.py` 具体 missing lines：
  `cd services/gateway-scanner && pytest tests/
  --cov=gateway_scanner --cov-report=term-missing --no-header`。
  **预期**：cov 报告含 2 个 module 的 missing 行号。
  这步**必**在 task 4-5 之前——给补 test 提供 evidence。
  **预计时间**：2 分钟。

- [x] 3.2 surface 给用户决策：missing lines 数量 / 拆分建议
  （是 1 个 test file 还是 2 个）。
  **owner**：orchestrator 通过 AskUserQuestion 给用户 1 个 binary 选择。
  **预计时间**：3 分钟。

## 4. 补 test 达 100%（systematic-debugging Phase 4 用户决策杠杆）

- [x] 4.1 补 `scanner.py` 100% coverage：基于 Task 3.1 missing lines
  写 ~3-5 个 test。文件位置依 Task 3.2 决策。**owner**：orchestrator
  通过 Edit 加 test。**预计时间**：15 分钟。
  配对：每个 test 跑后立即 `pytest tests/<file>::test_name -v --no-cov`
  验证 PASS（避免批量写完才测）。

- [x] 4.2 补 `__main__.py` 100% coverage：用 `click.testing.CliRunner`
  写 ~3-5 个 test，覆盖 6 个 Scenario。文件位置依 Task 3.2 决策
  （新 `test_main.py` 或并入 `test_smoke.py`）。
  **预计时间**：15 分钟。

- [x] 4.3 跑完整 cov 验证：
  `pytest tests/ --cov=gateway_scanner --cov-fail-under=100`。
  **预期**：2 个 module 100%，exit code 0。
  **预计时间**：2 分钟。
  **若失败**（cov < 100%）：回到 4.1 / 4.2 补 test。

- [x] 4.4 验证既有 5 个 test file / 40 PASS 仍过：
  `pytest tests/ --no-cov` 应仍 40 PASS + 新 test 总数。
  **预计时间**：2 分钟。

## 5. 单元测试验证（生产 diff 仅 pyproject.toml）

- [x] 5.1 验证 `gateway_scanner/scanner.py` 与 `__main__.py` diff 为零：
  `cd /Users/paulwang/work/ChatBiz && git diff --stat
  services/gateway-scanner/gateway_scanner/` 输出必须**为空**。
  **预计时间**：1 分钟。
  **若非空**：意外改生产代码，立即回滚。

## 6. Git 跟踪

- [x] 6.1 `git add services/gateway-scanner/pyproject.toml
  services/gateway-scanner/tests/` 跟踪所有变更。
  **预计时间**：1 分钟。

- [x] 6.2 单 commit 提交：
  ```
  git commit -m "test(gateway-scanner): close retrospective §6.4 row 2 — 100% line cov + cov matrix

  * pyproject.toml: addopts 加 '--cov=gateway_scanner
    --cov-fail-under=100'（与 audit-and-isolation 对齐）
  * scanner.py: 65% → 100%（具体 test list 见 verify.md §1）
  * __main__.py: 0% → 100%（CliRunner 6 个 Scenario 覆盖）

  Openspec: openspec/changes/gateway-scanner-coverage-matrix/
  Source trigger: gateway-egress-enforcement-p0/retrospective.md §6.4
  Verification: openspec/changes/gateway-scanner-coverage-matrix/verify.md

  Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```
  **预计时间**：2 分钟。

- [x] 6.3 `git log -1 --stat` 确认 commit 含 `pyproject.toml` +
  tests/ 变更，0 个 `gateway_scanner/` 下 .py 文件。**预计时间**：1 分钟。

## 7. Openspec archive（apply 收尾）

- [x] 7.1 写 `verify.md`：列出 3.1 / 3.2 / 4.3 / 5.1 / 6.3 的实际
  command + output（含 cov 100% 截图 + production diff 为零）。
  **owner**：apply 阶段 orchestrator。**预计时间**：15 分钟。

- [x] 7.2 写 `retrospective.md`（5-section 模板，参考
  `coverage-improvement/retrospective.md` 结构）：
  What was built / What went well / What didn't go well /
  What's left for V1.0+（强调 NG1 nested 空目录 + NG2 CI
  workflow 仍未 close）/ Process reflections。
  **预计时间**：20 分钟。

- [x] 7.3 改 tasks.md 把所有 `- [ ]` 改成 `- [x]`。
  **预计时间**：1 分钟。

- [x] 7.4 `openspec archive gateway-scanner-coverage-matrix`（含
  必要 interactive confirm 提示）。**预计时间**：2 分钟。

- [x] 7.5 git add + commit 跟踪 openspec archive 目录 + 新 spec：
  ```
  git add openspec/changes/archive/2026-06-15-gateway-scanner-coverage-matrix/
  openspec/specs/gateway-scanner-coverage-100pct/
  git commit -m "chore(openspec): archive gateway-scanner-coverage-matrix

  * 8 artifacts: brainstorm / proposal / design / specs / tasks / plan /
    verify / retrospective + .openspec.yaml
  * new capability spec delta applied at
    openspec/specs/gateway-scanner-coverage-100pct/spec.md
  * closes retrospective §6.4 row 2: gateway-scanner 2 target
    modules now at 100% line coverage (scanner / __main__)
  * cov matrix config now in pyproject.toml (matches audit-and-isolation)

  Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```
  **预计时间**：2 分钟。

- [x] 7.6 `git push origin main`。**预计时间**：1 分钟。
