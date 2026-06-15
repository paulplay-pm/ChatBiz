## 1. 验证现状（working tree baseline）

- [x] 1.1 验证 credential 摸底数据:
  `cd services/credential && conda run -n chatbiz pytest tests/
  --collect-only 2>&1 | tail -5`。
  **预期**: `4 tests collected, 15 errors`。
  **预计时间**: 2 分钟。

- [x] 1.2 验证 pyproject 当前无 `--cov-fail-under`:
  `grep "addopts\|pythonpath" services/credential/pyproject.toml`。
  **预计时间**: 1 分钟。

## 2. 修 15 import errors (系统根因)

- [x] 2.1 改 `services/credential/pyproject.toml` 加 `pythonpath = ["."]`。
  **预计时间**: 1 分钟。

- [x] 2.2 跑 pytest verify 15 errors 修复:
  `cd services/credential && conda run -n chatbiz pytest tests/
  --collect-only 2>&1 | tail -5`。
  **预期**: 收集到全部 15+ test,0 errors。
  **预计时间**: 2 分钟。

- [x] 2.3 跑真实 pytest 看 PASS/FAIL 数:
  `cd services/credential && conda run -n chatbiz pytest tests/ 2>&1 | tail -3`。
  **owner**: surface 真实 PASS/FAIL 数给用户决策。
  **预计时间**: 2 分钟。

## 3. 单元测试验证 baseline (paired with Task 4-5 补 test)

- [x] 3.1 跑 cov 拿 13 prod file missing lines:
  `cd services/credential && conda run -n chatbiz pytest tests/
  --cov=app --cov-report=term-missing --no-header 2>&1 | tail -20`。
  **预计时间**: 2 分钟。

## 4. 补 test 达 100% (systematic-debugging Phase 4)

- [x] 4.1 摸 13 prod file 起点 + 决定 test 拆分。
  **owner**: orchestrator 通过 AskUserQuestion 给用户 1 个 binary 选择。
  **预计时间**: 3 分钟。

- [x] 4.2 补 test 达 100%,文件位置依 4.1 决策。
  **预计时间**: 30-45 分钟(具体看 missing lines 数)。

- [x] 4.3 跑 cov 验证 100%:
  `cd services/credential && conda run -n chatbiz pytest tests/
  --cov=app --cov-fail-under=100 --no-header 2>&1 | tail -10`。
  **预期**: 13 file 100%,exit 0。
  **预计时间**: 2 分钟。

## 5. 加 pyproject cov config (3 flag + pythonpath)

- [x] 5.1 改 `services/credential/pyproject.toml`:
  addopts 列表加 `--cov=app` + `--cov-report=term-missing` +
  `--cov-fail-under=100`。
  **预计时间**: 1 分钟。

- [x] 5.2 跑 pytest verify fail-under trigger:
  `cd services/credential && conda run -n chatbiz pytest tests/
  --no-cov 2>&1 | tail -3`。
  **预计时间**: 1 分钟。

## 6. 验证 production diff = 0

- [x] 6.1 `git diff --stat services/credential/app/` 输出**为空**。
  **预计时间**: 1 分钟。

## 7. Git 跟踪

- [x] 7.1 `git add services/credential/pyproject.toml
  services/credential/tests/`。
  **预计时间**: 1 分钟。

- [x] 7.2 单 commit 提交。
  **预计时间**: 2 分钟。

- [x] 7.3 `git log -1 --stat` 确认 commit 仅 test + config 改动。
  **预计时间**: 1 分钟。

## 8. Openspec archive

- [x] 8.1 写 `verify.md`。
  **预计时间**: 10 分钟。

- [x] 8.2 写 `retrospective.md`(5-section 模板)。
  **预计时间**: 15 分钟。

- [x] 8.3 sed tasks.md 全勾 [x]。

- [x] 8.4 `yes y | openspec archive ci-coverage-credential`。

- [x] 8.5 git add archive + commit + push。
