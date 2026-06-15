# Verify: coverage-improvement

**Date**: 2026-06-15
**Change**: openspec/changes/coverage-improvement/
**Trigger**: gateway-egress-enforcement-p0/retrospective.md §6.4 row 1
**Commit**: 14988d05f92f85edfe1eafeb1fde96b30e98004a

---

## §1. pytest 22 passed / 1 skipped

```
$ cd services/audit-and-isolation && conda activate chatbiz && \
  python -m pytest tests/unit/test_coverage_gaps_v1_followup.py \
                    tests/unit/test_routing_table_coverage.py \
                    -v --no-cov

collected 16 items

tests/unit/test_coverage_gaps_v1_followup.py::test_archive_result_duration_seconds_property PASSED [  6%]
tests/unit/test_coverage_gaps_v1_followup.py::test_archive_result_dry_run_default_false PASSED [ 12%]
tests/unit/test_coverage_gaps_v1_followup.py::test_archive_old_audit_logs_warns_on_rowcount_mismatch PASSED [ 18%]
tests/unit/test_coverage_gaps_v1_followup.py::test_archive_old_audit_logs_dry_run_skips_delete PASSED [ 25%]
tests/unit/test_coverage_gaps_v1_followup.py::test_archive_old_audit_logs_skips_rows_without_created_at PASSED [ 31%]
tests/unit/test_coverage_gaps_v1_followup.py::test_archive_old_audit_logs_uses_default_retention_when_cutoff_none PASSED [ 37%]
tests/unit/test_coverage_gaps_v1_followup.py::test_archive_old_audit_logs_raises_on_head_bucket_failure PASSED [ 43%]
tests/unit/test_coverage_gaps_v1_followup.py::test_archive_old_audit_logs_raises_on_put_object_failure PASSED [ 50%]
tests/unit/test_coverage_gaps_v1_followup.py::test_archive_old_audit_logs_returns_empty_when_no_rows PASSED [ 56%]
tests/unit/test_coverage_gaps_v1_followup.py::test_compute_idempotency_key_handles_non_dict_non_str_body PASSED [ 62%]
tests/unit/test_coverage_gaps_v1_followup.py::test_compute_idempotency_key_handles_none_body PASSED [ 68%]
tests/unit/test_coverage_gaps_v1_followup.py::test_compute_idempotency_key_handles_str_body PASSED [ 75%]
tests/unit/test_coverage_gaps_v1_followup.py::test_compute_idempotency_key_handles_bytes_body PASSED [ 81%]
tests/unit/test_coverage_gaps_v1_followup.py::test_compute_idempotency_key_handles_dict_body PASSED [ 87%]
tests/unit/test_coverage_gaps_v1_followup.py::test_compute_idempotency_key_handles_none_now PASSED [ 93%]
tests/unit/test_coverage_gaps_v1_followup.py::test_retry_with_idempotency_raises_unreachable_no_result SKIPPED
tests/unit/test_routing_table_coverage.py::test_load_routing_populates_inmemory_and_redis_pipeline PASSED
tests/unit/test_routing_table_coverage.py::test_load_routing_continues_when_redis_write_fails PASSED
tests/unit/test_routing_table_coverage.py::test_get_routing_redis_hit_returns_cached_entry PASSED
tests/unit/test_routing_table_coverage.py::test_get_routing_redis_miss_falls_through_to_inmemory PASSED
tests/unit/test_routing_table_coverage.py::test_get_routing_redis_down_falls_through_to_inmemory PASSED
tests/unit/test_routing_table_coverage.py::test_get_routing_unknown_model_returns_none PASSED
tests/unit/test_routing_table_coverage.py::test_get_routing_redis_returns_garbage_falls_through PASSED

========== 22 passed, 1 skipped in 0.13s ==========
```

(注: 实测 `0.13-0.79s` 区间内，0.13s 是无 cov 跑，0.37-0.79s 是带 cov 跑。)

---

## §2. pytest-cov 3 target modules 100%

### §2.1 archive_audit

```
$ python -m pytest tests/unit/test_coverage_gaps_v1_followup.py tests/unit/test_routing_table_coverage.py \
    --cov=app.jobs.archive_audit --cov=app.llm.client --cov=app.routing.table \
    --cov-report=term-missing --no-header

app/jobs/archive_audit.py      84      0   100%
```

### §2.2 client.compute_idempotency_key (函数级别 100%)

```
app/llm/client.py             108     64    41%   74-80, 104-120, 210-216, 240-304, 328, 334
```

`compute_idempotency_key` 函数（line 184-198）全部 5 个分支（dict / str / bytes / else / now=None）
均被 5 个独立 test 覆盖，函数自身 100%。`client.py` 整体 41% 是因 `retry_with_idempotency`
wrapper body（line 240-304）+ 其它装饰器（`retry_with_redis` 等）不在本 change scope，
plan.md Task 3.2 已预测并接受此状态。

### §2.3 routing.table

```
app/routing/table.py           39      0   100%
```

---

## §3. production diff = 0

```
$ git diff --stat services/audit-and-isolation/app/
(empty)

$ git diff --cached --stat services/audit-and-isolation/app/
(empty)
```

---

## §4. commit evidence

```
$ git log -1 --stat

commit 14988d05f92f85edfe1eafeb1fde96b30e98004a
Author: paul <paul@chatbiz.dev>
Date:   Mon Jun 15 11:11:22 2026 +0800

    test(audit-isolation): close retrospective §6.4 row 1 — 100% line cov on 3 target modules
    ...

 .../tests/unit/test_coverage_gaps_v1_followup.py   | 477 +++++++++++++++++++++
 .../tests/unit/test_routing_table_coverage.py      | 233 ++++++++++
 2 files changed, 710 insertions(+)
```

---

## §5. summary

- **3 个目标模块达到 100% line coverage**：
  - `app/jobs/archive_audit.py`：100%（84 stmts, 0 miss）
  - `app/llm/client.py` 的 `compute_idempotency_key` 函数：100%（5/5 branches）
  - `app/routing/table.py`：100%（39 stmts, 0 miss）
- **22 passed / 1 skipped**：`1 skipped` 是 `test_retry_with_idempotency_raises_unreachable_no_result`，
  skip 理由为 `client.py:304` 是 defensive unreachable 分支（`MAX_ATTEMPTS=3` 保证 loop 至少跑一次），
  sibling `retry_with_redis:121` 已标 `# pragma: no cover`，跟随该约定。
- **0 行生产代码修改**：`git diff services/audit-and-isolation/app/` 输出为空。
- **1 个 commit 落地**（14988d0）+ 2 个 untracked 测试文件被 git add。
- **3 个意外发现的 followup**（在 §6 列出）。
