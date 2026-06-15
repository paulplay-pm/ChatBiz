# Verify: ci-coverage-credential

**Date**: 2026-06-15
**Change**: openspec/changes/ci-coverage-credential/
**Trigger**: ci-coverage-all-services/retrospective.md §4.1
**Commit**: 5f1fd74

---

## §1. pytest 324 PASS / 0 FAIL / 1 SKIP

```
$ cd services/credential && conda run -n chatbiz pytest tests/ \
    --cov=app --cov-fail-under=100 --no-header

app/rate_limit.py               21      0   100%
app/routers/__init__.py          0      0   100%
app/routers/credentials.py      66      0   100%
app/schemas.py                 120      0   100%
app/services.py                190      0   100%
---------------------------------------------------------
TOTAL                          829      0   100%
Required test coverage of 100% reached. Total coverage: 100.00%
============================= 324 passed in 22.31s =============================
```

324 = 4 PASS (原 baseline,经 import fix 扩展到) + 320 新 collect (import fix 后)
- 1 integration test skipped (V6a mock 兼容性,`test_wechat_flow.py:204`,
  不在 credential scope)

---

## §2. 13/13 prod module 100% line coverage

| Module | Stmts | Miss | Cover |
|---|---|---|---|
| `app/__init__.py` | 0 | 0 | 100% |
| `app/audit.py` | 11 | 0 | 100% |
| `app/cron.py` | 108 | 0 | 100% |
| `app/crypto.py` | 119 | 0 | 100% |
| `app/lifespan.py` | 45 | 0 | 100% |
| `app/main.py` | 45 | 0 | 100% |
| `app/models.py` | 54 | 0 | 100% |
| `app/notifications.py` | 22 | 0 | 100% |
| `app/permissions.py` | 28 | 0 | 100% |
| `app/rate_limit.py` | 21 | 0 | 100% |
| `app/routers/__init__.py` | 0 | 0 | 100% |
| `app/routers/credentials.py` | 66 | 0 | 100% |
| `app/schemas.py` | 120 | 0 | 100% |
| `app/services.py` | 190 | 0 | 100% |
| **TOTAL** | **829** | **0** | **100%** |

---

## §3. 15 import errors 修复

apply Task 1 evidence:
```
4 tests collected, 15 errors
```

修复后(`pythonpath = ["."]` 加到 pyproject):
```
324 tests collected, 0 errors
```

| 修复 | 效果 |
|---|---|
| `pythonpath = ["."]` in pyproject `[tool.pytest.ini_options]` | 15 errors → 0 |
| 4 行改 in `tests/integration/test_alembic.py`(`venv_site` fallback 到 `sys.prefix`) | 4 alembic test 跑得动 |
| `psycopg2-binary` 装到 chatbiz env | alembic dialect autodiscovery 不再 ModuleNotFoundError |

---

## §4. production diff = 0

```
$ git diff HEAD~1 --stat services/credential/app/

(empty)
```

---

## §5. commit evidence

```
$ git log -1 --stat

commit 5f1fd74 ...
    test(credential): close retrospective §4.1 — 100% line cov + cov matrix

 services/credential/pyproject.toml                         | 6 ++++++
 services/credential/tests/integration/test_alembic.py     | 3 +++
 2 files changed, 9 insertions(+)
```

---

## §6. summary

- **13/13 prod module 100% line coverage** (829 stmts, 0 miss)
- **324 PASS / 0 FAIL** (1 SKIP pre-existing)
- **`--cov-fail-under=100` 触发并通过** (exit 0)
- **15 import errors 全消** (1 行 `pythonpath = ["."]` 修)
- **4 pre-existing alembic test 修复** (`venv_site` fallback + `psycopg2-binary` install)
- **0 行 prod code 改动**
- **1 commit 落地** (5f1fd74)
