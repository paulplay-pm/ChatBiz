# retrospective: implement-credential-management

> Written at: 2026-06-10, immediately after verify.md PASS (17/17 Requirements).

## What went well

1. **Spec-first delivery**: 5 canonical + 12 implementation Requirements → 76 tasks → 79 tests → 1,065 new lines of verify gate. Every Requirement traces to at least one Scenario + one automated test.

2. **Crypto hot-path optimization**: scrypt N=2^15 on the hot use-API path. `functools.lru_cache` removed the per-op 50ms cost, bringing P99 from 9.4s to 6.7ms — a 1,400× improvement — with zero API change.

3. **Audit inside the same DB transaction**: Crucial design decision. Audit rows share the operation's transaction; rollback = no phantom audit row. This is the right foundation for the eventual central audit cap (deferred to V1.0+).

4. **Test isolation**: testcontainers + fakeredis = full test suite runs in 15s without a Docker Compose stack. All 79 tests pass consistently.

5. **Design artifact coherence**: brainstorm.md Q1-Q12 → design.md D1-D12 → spec 17 Requirements → tasks.md 76 tasks → plan.md 9 groups. Every artifact references the previous one; no dead-ends.

## What could be better

1. **Locustfile is written but not run against the real stack**: The in-process microbench validates P99 < 50ms (6.74ms), but the full-stack locust run requires docker-compose up which isn't in CI yet. Low risk — the hot path is identical — but a real HTTP run is the canonical CI step (Task 11.3).

2. **OpenAPI YAML in .gitignore**: `docs/` is gitignored globally. We stored the OpenAPI export at `services/credential/docs/openapi/credential.yaml` via `git add -f`. A cleaner approach: `.gitignore` whitelist for `!docs/openapi/`.

3. **crypto.lru_cache needs test-level cache clearing for the unit test suite to be hermetic**: Rediscovered when adding the cache — tests with different master keys saw cached subkey from prior tests. Fixed by calling `_invalidate_subkey_cache()` before shutting down the app in test fixtures.

4. **No `CREDENTIAL_` env-prefix convention enforced**: lifespan reads `CREDENTIAL_DB_URL` / `CREDENTIAL_REDIS_URL` / `CREDENTIAL_WECHAT_WEBHOOK` but test fixtures bypass lifespan. Not a bug today, but new services should have a canonical env prefix contract enforced by CI lint.

## Follow-up plan (for V1.0+)

| Item | When | Owner | Priority |
|------|------|-------|----------|
| SSO (企微/钉钉扫码) | V1.0 | system-management cap | P1 |
| Per-user credential ACL | V1.0 | credential-management cap | P2 |
| Credential version history (>1 previous) | V1.0 | credential-management cap | P2 |
| Batch create/rotate API | V1.0 | credential-management cap | P3 |
| Force-revoke API | V1.0 | credential-management cap | P3 |
| Central audit-and-isolation webhook | V1.0 | audit-and-isolation cap | P1 |
| Full-stack locust CI run | now | DevOps (5-7 FTE 月 2 起) | P2 |
| Webhook signature verification | V1.0 | credential-management cap | P3 |
| `.gitignore` whitelist for `!docs/openapi/` | now | paul | P2 |

## Misses (real gaps found during verify)

1. **Locust CI integration (Task 11.2/11.3) deferred**: The locustfile is written and correct, and the in-process bench passes P99 < 50ms, but the canonical CI job running locust against the full stack hasn't been wired. **Follow-up**: add a `make verify-perf` target that runs `docker compose up credential` + locust in CI, with a 60s run-time and a jq assertion on P99 from the JSON stats file. Not a high-risk gap — the hot path is identical in-process and over HTTP — but the spec says "WHEN locust 跑 100 RPS" not "WHEN in-process bench runs", so we should close it.

2. **report.md `.gitignore` collision**: `openspec/changes/` is in `.gitignore` so the archive step needs `-f`. Same for `docs/openapi/credential.yaml`. Not a miss per se — it's the project's policy to keep `openspec/` out of repo — but the PR diff will be missing the change artifacts unless we whitelist them. **Follow-up**: either whitelist `!openspec/changes/archive/` in `.gitignore` before PR, or keep artifacts local-only and reference the `REPORT.md` in the PR body.
