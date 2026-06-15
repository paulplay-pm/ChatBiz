## 1. 验证现状（working tree baseline）

- [x] 1.1 验证 `app/llm/client.py` 当前 cov 78% (24 miss)：
  `cd services/audit-and-isolation && conda run -n chatbiz pytest
  tests/unit/test_coverage_gaps_v1_followup.py tests/unit/test_retry.py
  --cov=app.llm.client --cov-report=term-missing --no-header`。
  **预期**：45 passed,client.py 显示 `24 miss, 78%`,missing
  `74-80, 104-120, 214-215, 304, 334`。**预计时间**：2 分钟。

- [x] 1.2 验证 `client.py` line 304 / 121 已是 `# pragma: no cover`。
  **预计时间**：1 分钟。

## 2. 补 test 达 100%（systematic-debugging Phase 4）

- [x] 2.1 补 `get_client()` lazy init (line 74-80) 3 个 test，
  加到 `tests/unit/test_coverage_gaps_v1_followup.py`。
  参考 spec Scenario 1-3。每个 test 写完立即跑验证 PASS。**预计时间**：15 分钟。

- [x] 2.2 补 `retry_with_redis` 2-iter loop (line 104-120) 4 个 test。
  参考 spec Scenario 4-7。每个 test 写完立即跑验证 PASS。**预计时间**：20 分钟。

- [x] 2.3 补 `_is_ha_failover` JSON parse 错误路径 (line 214-215) 3 个 test。
  参考 spec Scenario 8-10。**预计时间**：10 分钟。

- [x] 2.4 补 `reset_client_for_tests` (line 334) 1 个 test。
  参考 spec Scenario 11。**预计时间**：5 分钟。

- [x] 2.5 跑完整 cov 验证 100%：
  `pytest tests/unit/test_coverage_gaps_v1_followup.py
  tests/unit/test_retry.py --cov=app.llm.client --cov-fail-under=100`。
  **预期**：client.py 100%,exit code 0。**预计时间**：2 分钟。
  **若失败**：回到 2.1-2.4 补 test。

## 3. 验证 production diff = 0

- [x] 3.1 验证 `app/llm/client.py` diff 为零：
  `cd /Users/paulwang/work/ChatBiz && git diff --stat
  services/audit-and-isolation/app/llm/client.py` 输出**为空**。
  **预计时间**：1 分钟。
  **若非空**：意外改 prod code,立即回滚。

## 4. Git 跟踪

- [x] 4.1 `git add services/audit-and-isolation/tests/unit/test_coverage_gaps_v1_followup.py`。
  **预计时间**：1 分钟。

- [x] 4.2 单 commit 提交：
  ```
  git commit -m "test(audit-isolation): close retrospective §4.2 — client.py 78% → 100%

  * get_client lazy init: 3 test (line 74-80)
  * retry_with_redis 2-iter loop: 4 test (line 104-120)
  * _is_ha_failover JSON parse error: 3 test (line 214-215)
  * reset_client_for_tests: 1 test (line 334)
  * 0 行 production code 改动 (line 304/121 已是 # pragma: no cover)

  Openspec: openspec/changes/llm-client-retry-coverage/
  Source trigger: coverage-improvement/retrospective.md §4.2
  Verification: openspec/changes/llm-client-retry-coverage/verify.md

  Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```
  **预计时间**：2 分钟。

- [x] 4.3 `git log -1 --stat` 确认 commit 仅 test file 改动,0 个
  `app/llm/client.py` 改动。**预计时间**：1 分钟。

## 5. Openspec archive（apply 收尾）

- [x] 5.1 写 `verify.md`：列出 1.1 / 2.5 / 3.1 / 4.3 实际 command +
  output。**预计时间**：15 分钟。

- [x] 5.2 写 `retrospective.md`（5-section 模板）。**预计时间**：20 分钟。

- [x] 5.3 改 tasks.md 把所有 `- [ ]` 改成 `- [x]`。**预计时间**：1 分钟。

- [x] 5.4 `yes y | openspec archive llm-client-retry-coverage`。
  **预计时间**：2 分钟。

- [x] 5.5 git add + commit 跟踪 openspec archive + 新 spec + push。
  **预计时间**：2 分钟。
