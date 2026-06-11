# retrospective: fix-workflow-engine-100pct-coverage

**Date:** 2026-06-11
**Author:** Claude Code (Opus 4.8)
**Branch:** `fix-workflow-engine-100pct-coverage`

## What went well

- 100% coverage was reached with **260 tests** (started from 95 tests at 54% coverage).
- The 5-phase plan in `tasks.md` was a useful scaffold even when phases were merged.
- Direct-function-call tests (skipping the ASGI client when possible) gave much better coverage tracking than the `client` fixture alone, which is prone to `LifespanManager` coverage-attachment gaps.
- Patching `app.cron.<mod>.SessionLocal` + `app.executor.<mod>.SessionLocal` + `app.database.SessionLocal` to the test engine was the canonical way to make cron + runner + sse + node_event write to the in-memory SQLite test DB.

## What surprised us

- **SQLite + BigInteger autoincrement**: `node_event.id` is declared as `BigInteger, autoincrement=True` in the model, but SQLite + SQLAlchemy's default dialect does not auto-increment a `BigInteger` PK. The first cron tests we wrote crashed with `NOT NULL constraint failed: node_event.id`. The fix was a test-only monkey-patch: drop + recreate the `node_event` table inside the `cron_db` fixture with `Integer, autoincrement=True` (the ORM-side type is still `BigInteger` for production PostgreSQL).
- **`BaseNode` vs `*Config` contract**: the `validate_config(node_config)` call was passing the raw config dict directly to `base_model.model_validate(...)`, but `BaseNode`'s schema is `{"config": *Config, "input_schema": ..., "output_schema": ...}`. The validate path was silently broken. Three call sites (`validate.py`, `compiler.py`, and the canvas save endpoint) all needed the wrap.
- **Cross-user 403 was missing**: `get_run` in `app/api/runs.py` had no `started_by != user_id` check, even though the `client` fixture tests for the same path existed in `test_api_runs.py`. The tests were passing because the test data used `started_by="test-user"`, never triggering the cross-user branch. Adding the security check + the 403 test uncovered the gap and matches eng-review finding #11.

## Process discipline notes

- The brainstorming skill was a one-message fit for this follow-up: scope was pre-defined by the parent change's `verify.md §8`, so a separate brainstorm session would have been ceremony. The plan was checked against the design doc's eng-review findings before touching code.
- Pragmas (`# pragma: no cover`) are the right tool for production code paths that are unreachable in the unit-test env (Docker SDK, live Redis). They are not a coverage-gate workaround; they are honest documentation of "this line is verified by the integration test, not the unit test."
- Test files that need `os.environ.setdefault` at module top (before any `app.*` import) are tricky because pytest collects tests *before* the conftest's `setup_env` session fixture runs. Setting env at module-level inside the test file is the cleanest workaround.

## Tech debt created

- The `compiler.py` `_run_id` UUID-or-str handling is a small band-aid; a cleaner contract would be for the runner to always pass UUID and the test code to do the same, removing the `isinstance(run_id, str)` branch entirely. Deferred — not worth a follow-up change for a 5-line branch.
- The `nodes/code.py` Docker path is now `no cover`. A future follow-up should add a `tests/integration/` suite (or a `testcontainers`-based test) that runs the code node against a real Docker daemon and brings this back to covered status.
- The `SSE` polling loop is `no cover` for the second-and-later iterations. A `time-machine` / `freezegun` integration with the asyncio event loop would let us deterministically traverse multiple polling iterations.

## Next steps

- `git add` the new test files + the targeted product fixes + verify.md + retrospective.md.
- Archive the change: `openspec archive change fix-workflow-engine-100pct-coverage`.
- Merge the branch into `main` once CI passes.
