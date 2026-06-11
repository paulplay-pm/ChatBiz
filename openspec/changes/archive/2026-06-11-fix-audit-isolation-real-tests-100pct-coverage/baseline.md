# Baseline: audit-and-isolation real tests coverage

## Scope

This file persists the Task 1 baseline calibration requested by code quality review for later `verify.md` and `retrospective.md` use.

This note covers **only** `plan.md` Task 1: baseline coverage collection and test cwd calibration. It does **not** complete `tasks.md` 1.2 or 1.3; the missing-line-driven test skeletons and their pytest collection check are follow-up implementation tasks.

## Files read and checked

- `/Users/paulwang/work/ChatBiz/.claude/worktrees/fix-audit-isolation-coverage/services/audit-and-isolation/pyproject.toml`
  - confirmed pytest configuration is service-local: `testpaths = ["tests"]`.
  - confirmed default pytest addopts already include `-v --cov=app --cov-report=term-missing --cov-fail-under=100`, so the baseline command explicitly uses `--cov-fail-under=0` to observe current gaps without failing.
  - confirmed `asyncio_mode = "auto"`.
- `/Users/paulwang/work/ChatBiz/.claude/worktrees/fix-audit-isolation-coverage/services/audit-and-isolation/tests/unit/test_api_chat.py`
  - confirmed existing chat endpoint tests are unittest-style around a module-level `TestClient(app)`.
  - confirmed existing structure patches imported/runtime boundaries for auth, routing, LLM, credential, redactor, and reverser behavior rather than using real external services.
  - confirmed this file currently covers request-validation surface only; deeper chat missing lines are planned follow-up work, not part of this baseline note.

## Commands and exit codes

### Service cwd baseline command

- cwd before command: `/Users/paulwang/work/ChatBiz/.claude/worktrees/fix-audit-isolation-coverage`
- command recorded from `plan.md` Task 1:

```bash
cd services/audit-and-isolation
PYTHONPATH=. python3 -m pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=0
```

- actual service cwd after `cd`: `/Users/paulwang/work/ChatBiz/.claude/worktrees/fix-audit-isolation-coverage/services/audit-and-isolation`
- exit code: `0`
- result: `127 passed, 3 warnings`
- total coverage: `80%`

### Root cwd calibration command

- cwd: `/Users/paulwang/work/ChatBiz/.claude/worktrees/fix-audit-isolation-coverage`
- command recorded from `plan.md` Task 1:

```bash
cd repo root
PYTHONPATH=$(pwd)/services/audit-and-isolation python3 -m pytest tests/ -v
```

- exit code: `4`
- error: `file or directory not found: tests/`
- result: expected failure because `tests/` is service-local under `services/audit-and-isolation/tests`, not repository-root local. Follow-up test/coverage commands must run from `services/audit-and-isolation` unless the command explicitly points pytest at the service test directory.

## Coverage summary

- total tests: `127 passed`
- total coverage: `80%`
- statements: `714`
- missing statements: `140`

## Full coverage table

```text
Name                        Stmts   Miss  Cover   Missing
---------------------------------------------------------
app/__init__.py                 0      0   100%
app/alerts.py                  15      0   100%
app/api/__init__.py             2      0   100%
app/api/chat.py                89     13    85%   102-103, 119-120, 129, 143, 166-173
app/api/health.py              41     25    39%   55, 67-103
app/api/models.py              33     12    64%   58-79
app/audit/__init__.py           0      0   100%
app/audit/hash.py               7      0   100%
app/audit/writer.py            54      2    96%   60-61
app/auth.py                    22      0   100%
app/config.py                  22      0   100%
app/credential_client.py       37      1    97%   100
app/database.py                28     14    50%   59-64, 76-81, 94-97, 103-106
app/errors.py                  14      0   100%
app/llm/__init__.py             0      0   100%
app/llm/client.py              31      5    84%   47-53, 94
app/llm/streaming.py           17     17     0%   30-72
app/main.py                    31     12    61%   43-59
app/metrics.py                  8      0   100%
app/models/__init__.py          3      0   100%
app/models/audit.py            34      0   100%
app/models/common.py           15      0   100%
app/models/llm.py              28     28     0%   19-79
app/pii/__init__.py             0      0   100%
app/pii/detector.py            26      0   100%
app/pii/redactor.py            32      2    94%   97-100
app/pii/reverser.py            25      3    88%   58-60
app/pii/rules.py               37      3    92%   118, 121-122
app/redis_client.py            11      3    73%   47-53
app/routing/__init__.py         0      0   100%
app/routing/dispatcher.py      13      0   100%
app/routing/table.py           39      0   100%
---------------------------------------------------------
TOTAL                         714    140    80%
```

## Warnings observed

- `app/pii/rules.py`: `SyntaxWarning: invalid escape sequence '\d'`
  - observed path: `/Users/paulwang/work/ChatBiz/.claude/worktrees/fix-audit-isolation-coverage/services/audit-and-isolation/app/pii/rules.py`
  - warning context: docstring text references a regex example like ``\d{16,19}``.
- `app/audit/writer.py`: `RuntimeWarning` related to `AsyncMock`.
  - observed path: `/Users/paulwang/work/ChatBiz/.claude/worktrees/fix-audit-isolation-coverage/services/audit-and-isolation/app/audit/writer.py:102`
  - warning context: `s.add(rec)` received an `AsyncMock` in existing tests and produced `coroutine 'AsyncMockMixin._execute_mock_call' was never awaited`.

## Ignored test artifacts

The following local files/directories are ignored test artifacts produced by baseline execution or coverage inspection, not tracked product-code changes:

- `.coverage`
- `.pytest_cache`
- `__pycache__`
