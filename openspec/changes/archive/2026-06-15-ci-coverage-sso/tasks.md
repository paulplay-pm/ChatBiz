## 1. 验证现状（working tree baseline）

- [x] 1.1 验证 sso 摸底: `cd services/sso && conda run -n chatbiz pytest tests/
  --collect-only 2>&1 | tail -5`。
  **预计时间**: 2 分钟。

- [x] 1.2 验证 pyproject 当前无 `--cov-fail-under`: `grep "addopts\|pythonpath"
  services/sso/pyproject.toml`。
  **预计时间**: 1 分钟。

## 2. 修 4 import errors

- [x] 2.1 加 `pythonpath = ["."]` 到 pyproject。**预计时间**: 1 分钟。

- [x] 2.2 跑 pytest verify 4 errors 修复: `cd services/sso && conda run -n
  chatbiz pytest tests/ --collect-only 2>&1 | tail -5`。
  **预计时间**: 2 分钟。

- [x] 2.3 跑真实 pytest: `cd services/sso && conda run -n chatbiz pytest
  tests/ 2>&1 | tail -3`。**预计时间**: 2 分钟。

## 3. 摸 cov 起点

- [x] 3.1 `cd services/sso && conda run -n chatbiz pytest tests/ --cov=app
  --cov-report=term-missing --no-header 2>&1 | tail -20`。
  **预计时间**: 2 分钟。

## 4. 补 test 达 100%

- [x] 4.1 摸 15 prod file 起点 + 决定 test 拆分。**预计时间**: 3 分钟。
- [x] 4.2 补 test 达 100%。**预计时间**: 30-45 分钟。
- [x] 4.3 跑 cov 验证 100% + fail-under exit 0。**预计时间**: 2 分钟。

## 5. 加 3 flag

- [x] 5.1 pyproject addopts 列表加 3 flag。**预计时间**: 1 分钟。

## 6. 验证 prod diff = 0

- [x] 6.1 `git diff --stat services/sso/app/` 输出**为空**。**预计时间**: 1 分钟。

## 7. Git 跟踪

- [x] 7.1 `git add services/sso/pyproject.toml services/sso/tests/`。
- [x] 7.2 单 commit 提交。
- [x] 7.3 `git log -1 --stat` 验证。

## 8. Openspec archive

- [x] 8.1 写 verify.md。
- [x] 8.2 写 retrospective.md。
- [x] 8.3 sed tasks.md 全勾 [x]。
- [x] 8.4 `yes y | openspec archive ci-coverage-sso`。
- [x] 8.5 git add archive + commit + push。
