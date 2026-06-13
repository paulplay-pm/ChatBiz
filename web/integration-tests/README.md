# Web Integration Test Suite

> Status: **partial** — code is written and unit-tested; full `make test-integration test` end-to-end is blocked on pre-existing production bugs in the docker stack (see [Known Issues](#known-issues) below).

## What this is

Adds a real-backend integration test infrastructure on top of the existing mock-only E2E specs:

- `infrastructure/docker-compose-test.yml` — independent test stack (`--project-name chatbiz-test`) covering web + 4 services + pg/redis.
- `infrastructure/postgres-init-test/` — test-specific Postgres init scripts that work around a pre-existing Postgres 16 incompatibility in the production init script.
- `Makefile` — single entrypoint with `up` / `down` / `test` / `logs` subcommands.
- `services/audit-and-isolation/app/api/chat.py` — LLM echo bypass for integration tests. Gated by `ENVIRONMENT=integration` AND `model=echo-test`; still writes audit log; production path unchanged.
- `services/audit-and-isolation/tests/unit/test_chat_echo.py` — 7 unit tests covering the bypass.
- `web/nginx.conf` — added `location /healthz { proxy_pass http://chatbiz-mcp:8080; }`.
- `web/admin/src/api/health.ts` — `useHealth` now defaults to relative path; falls back to direct `localhost:8004` only when `VITE_ADMIN_HEALTH_DIRECT=1`.
- `web/canvas/vitest.integration.config.ts` + `tests/integration/{global-setup,api-client.spec}.ts` — Vitest config + integration spec (4 cases).
- `web/canvas/playwright.integration.config.ts` + `e2e/integration/paul-monthly-report.spec.ts` — Playwright config + critical-path-1 spec (3 cases).
- `web/admin/playwright.integration.config.ts` + `e2e/integration/admin-health.spec.ts` — admin health E2E (3 cases).

## How to run

```bash
# 1. From the repo root, build the frontends (so the nginx container has dist/ to mount)
make test-integration up
# (or: bash scripts/test-integration.sh up)

# 2. Once 'make test-integration up' exits 0, the stack is healthy.
#    Verify:
curl http://localhost:5173/healthz         # → 200 + mcp's health body
curl http://localhost:5173/canvas/         # → 200 + canvas SPA HTML
curl http://localhost:5173/admin/          # → 200 + admin SPA HTML

# 3. Run integration tests
cd web/canvas && pnpm test:integration
cd web/canvas && pnpm e2e:integration
cd web/admin  && pnpm e2e:integration

# 4. Stop
make test-integration down
```

## Critical path status (eng-review Test #2)

| # | Critical path                          | Status               | Where covered                                                    |
|---|----------------------------------------|----------------------|------------------------------------------------------------------|
| ① | paul 财务月报 end-to-end               | partial (~30%)       | `web/canvas/e2e/integration/paul-monthly-report.spec.ts` (3 cases: SPA load, 401 security boundary, nginx→workflow-engine proxy smoke). Full path blocked on the test stack lacking `/api/auth/login` (see Known Issues). |
| ② | 网关 PII 拦截 e2e                      | spec hook only (Non-goal) | `web-e2e-orchestration/spec.md` § "Extension points"           |
| ③ | 人工审批中断续接 e2e                   | spec hook only (Non-goal) | same                                                           |
| ④ | 插件加载降级 e2e                       | spec hook only (Non-goal) | same                                                           |

## Known Issues (blocks full E2E)

The test stack was designed to mirror production, but **production `infrastructure/docker-compose.yml` has latent bugs that block clean startup**. These are pre-existing — not introduced by this change — but they prevent `make test-integration up` from succeeding on a clean machine. Each needs a follow-up change (separate from this one) to fix in production:

1. **Postgres 16 rejects `CREATE DATABASE` inside a function/DO block.**
   `infrastructure/postgres/init/02-create-databases.sql` uses `DO $$ ... EXECUTE 'CREATE DATABASE ...'; ... END $$;`, which Postgres 16 disallows.
   - **Workaround in this change**: `infrastructure/postgres-init-test/02-create-databases.sql` uses psql `\gexec` instead.
   - **Production fix needed**: rewrite the production init script the same way (separate change).

2. **`*-migrate` containers don't set `PYTHONPATH`.**
   The Dockerfiles install deps to `~/.local/lib/python3.12/site-packages/`, but `alembic upgrade head` is invoked without `PYTHONPATH` pointing there. The dev compose (`docker-compose-dev.yml`) sets it explicitly; production compose does not. This means the migrate container fails with `ModuleNotFoundError: No module named 'alembic'`.
   - **Workaround in this change**: `docker-compose-test.yml` sets `PYTHONPATH` on each `*-migrate` service.
   - **Production fix needed**: add `PYTHONPATH` to the migrate services in `infrastructure/docker-compose.yml`.

3. **credential service requires a master encryption key in PG.**
   On first start, `app/crypto.py:load_master_key` aborts with `MasterKeyNotFoundError: no active master key in encryption_keys`. The dev compose seeds this via a Python heredoc after `alembic upgrade head`; production compose does not.
   - **Workaround in this change**: not applied (out of scope to seed in test compose too). Test stack currently fails to start without manual seeding.
   - **Production fix needed**: add the same heredoc to production compose's `credential-migrate` container command, or refactor credential startup to auto-seed on first start (preferred — see [feature/credential-bootstrap]).

4. **Port 8000 conflict on this machine.**
   `Trae IDE` (process 7703) holds `0.0.0.0:8000`. Production compose maps `8000:8000` for the credential service.
   - **Workaround in this change**: `docker-compose-test.yml` does NOT expose service ports to the host — only nginx's 5173. All client → service traffic goes through nginx.
   - **General note**: this works for our test spec, but a developer running a test alongside a dev compose on the same machine will still hit conflicts on `5173` (nginx) and `5432/6379/8001` if dev compose is up. `make test-integration up` checks for `chatbiz` (dev project) and aborts.

5. **Login in the test stack: no `/api/auth/login` endpoint.**
   `web/canvas/vite-plugin-dev-iam.ts` provides a dev-only mock at `/api/auth/login` — but only when running under `vite dev`. The test stack serves the pre-built canvas SPA without vite, so login calls return 404.
   - **Workaround in this change**: Paul E2E spec does NOT exercise the login flow. It tests SPA load + 401 security boundary + nginx → workflow-engine proxy.
   - **Follow-up change needed**: either (a) add a test-iam service in test compose that handles `/api/auth/login`, or (b) refactor canvas to use the real credential service for login. Option (a) is the lower-risk path.

6. **canvas `pnpm build` runs `tsc --noEmit` which has pre-existing type errors.**
   `e2e/canvas-connection.spec.ts`, `e2e/canvas-edge-deletion.spec.ts`, `src/main.tsx`, plus several `tests/*.test.tsx` files have errors unrelated to this change.
   - **Workaround in this change**: `Makefile` `test-integration up` calls `pnpm exec vite build` directly (skipping tsc). The dist is mounted into the nginx container.
   - **General note**: the production Dockerfile also runs `tsc --noEmit && vite build` and would currently fail. This is a separate cleanup.

## What's actually verified today

- `services/audit-and-isolation/tests/unit/test_chat_echo.py` — **7 tests pass** (verified in this session).
- All existing audit-and-isolation unit tests still pass (170 of 170).
- `web/nginx.conf`, `web/admin/src/api/health.ts` — TypeScript-clean.
- `web/canvas/{vitest,playwright}.integration.config.ts` + spec files — TypeScript-clean.
- `web/admin/playwright.integration.config.ts` + spec file — TypeScript-clean.

The end-to-end `make test-integration test` requires the production compose bugs to be fixed first; this is documented in the verify.md and tracked in the retrospective as follow-up work.
