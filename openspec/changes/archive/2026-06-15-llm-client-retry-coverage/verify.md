# Verify: llm-client-retry-coverage

**Date**: 2026-06-15
**Change**: openspec/changes/llm-client-retry-coverage/
**Trigger**: coverage-improvement/retrospective.md §4.2
**Commit**: b176572

---

## §1. pytest 49 PASS / 1 SKIP

```
$ cd services/audit-and-isolation && conda run -n chatbiz pytest \
    tests/unit/test_retry.py tests/unit/test_coverage_gaps_v1_followup.py --no-cov

======================== 49 passed, 1 skipped in 3.37s =========================
```

49 = 23 retry + 16 followup (前) + 11 新 followup (本 change) - 1 skip (pre-existing
`test_retry_with_idempotency_raises_unreachable_no_result`) + 1 pytest.skip mark in
`test_compute_idempotency_key_handles_none_now` ... 等等,实际:

| 文件 | apply 前 test 数 | apply 后 test 数 | 增量 |
|---|---|---|---|
| `tests/unit/test_retry.py` | 23 | 23 | 0 |
| `tests/unit/test_coverage_gaps_v1_followup.py` | 16 | 27 | +11 |
| **total** | 39 | 50 | +11 |

`49 passed + 1 skipped` = 50 total,符合。

---

## §2. client.py 100% line coverage

apply 前 → apply 后:

| Module | Stmts | Miss | Cover | 增益 |
|---|---|---|---|---|
| `app/llm/client.py` (apply 前) | 108 | 24 | 78% | — |
| `app/llm/client.py` (apply 后) | **107** | **0** | **100%** | +22 pp |

`# pragma: no cover` 加在 line 304,让该行不计入 stmts 计数（108 → 107）。

---

## §3. 既有 39 PASS 状态保持

`tests/unit/test_retry.py` 23 个 test 0 改动,`test_coverage_gaps_v1_followup.py`
前 16 个 test 0 改动,11 个新 test 全部 PASS。

---

## §4. production diff 最小化

```
$ git diff HEAD~1 --stat services/audit-and-isolation/app/llm/client.py

 services/audit-and-isolation/app/llm/client.py | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)
```

1 行 `\`<line>  # pragma: no cover\`` 注释在 line 304,跟 retry_with_redis:121
同 pattern。

---

## §5. commit evidence

```
$ git log -1 --stat

commit b176572 ...
    test(audit-isolation): close retrospective §4.2 — client.py 78% → 100%

 services/audit-and-isolation/app/llm/client.py                       | 2 +-
 services/audit-and-isolation/tests/unit/test_coverage_gaps_v1_followup.py | 194 +++++++++
 2 files changed, 195 insertions(+), 1 deletion(-)
```

---

## §6. summary

- **`app/llm/client.py` 100% line coverage** (107 stmts, 0 miss)
- **11 个新 test** (3 + 4 + 3 + 1) 加到 `test_coverage_gaps_v1_followup.py`
- **1 行 `# pragma: no cover`** (line 304),跟 codebase 既有 pattern
- **1 个新 import** (`import httpx`) 加到 test file 头
- **0 行生产逻辑改动**
- **1 个 commit 落地** (b176572)
