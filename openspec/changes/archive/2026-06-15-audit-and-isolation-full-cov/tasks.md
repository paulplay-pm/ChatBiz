## 1. 验证现状（working tree baseline）

- [x] 1.1 验证 audit-and-isolation 4 module 摸底:
  `cd services/audit-and-isolation && conda run -n chatbiz pytest
  tests/ --cov=app --cov-report=term-missing --no-header 2>&1 | grep
  "^app/api/audit_archive.py\|^app/api/chat.py\|^app/api/traces.py\|^app/perf/contracts.py"`。
  **预计时间**: 1 分钟。

## 2. 补 test 达 100%

- [x] 2.1 写 `tests/unit/test_full_cov_followup.py` 含 4-5 个新 test 走 4 module
  missing lines。**预计时间**: 15-25 分钟。

- [x] 2.2 跑 cov verify 100%:
  `cd services/audit-and-isolation && conda run -n chatbiz pytest
  tests/ --cov=app --cov-report=term-missing --no-header 2>&1 | grep
  "^app/api/audit_archive.py\|^app/api/chat.py\|^app/api/traces.py\|^app/perf/contracts.py"`。
  **预期**: 4 module 均 100%。
  **预计时间**: 1 分钟。

## 3. 验证 prod diff = 0

- [x] 3.1 `git diff --stat services/audit-and-isolation/app/` 输出**为空**。
  **预计时间**: 1 分钟。

## 4. Git 跟踪

- [x] 4.1 `git add services/audit-and-isolation/tests/unit/test_full_cov_followup.py`。
- [x] 4.2 单 commit 提交。
- [x] 4.3 `git log -1 --stat` 验证。

## 5. Openspec archive

- [x] 5.1 写 verify.md。
- [x] 5.2 写 retrospective.md。
- [x] 5.3 sed tasks.md 全勾 [x]。
- [x] 5.4 `yes y | openspec archive audit-and-isolation-full-cov`。
- [x] 5.5 git add archive + commit + push。
