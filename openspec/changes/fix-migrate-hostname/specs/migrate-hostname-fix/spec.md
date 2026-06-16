<!--
Delta spec for `migrate-hostname-fix` capability.
This is a NEW capability (no existing spec in openspec/specs/migrate-hostname-fix/).
Followup to fix-compose-postgres-naming (8c0df0b, 2026-06-14).
-->

## ADDED Requirements

### Requirement: base compose *-migrate 服务引用 chatbiz-postgres hostname
The system MUST update every `postgres:5432` hostname reference inside `infrastructure/docker-compose.yml` to `chatbiz-postgres:5432`, so that all `*-migrate` one-shot Alembic upgrade containers (and any other internal service env vars that depend on the postgres service key) can resolve the database host via Docker Compose's internal DNS. The number of post-update `postgres:5432` occurrences in `infrastructure/docker-compose.yml` MUST be exactly zero, and the number of `chatbiz-postgres:5432` occurrences MUST be exactly nine (the original count of `postgres:5432` references before this change).

#### Scenario: 替换后 0 处 postgres:5432
- **WHEN** a developer runs `grep -c "@postgres:5432" infrastructure/docker-compose.yml` after the change (using the leading `@` anchor to avoid matching the longer `chatbiz-postgres:5432` substring)
- **THEN** the output MUST be `0`

#### Scenario: 替换后 9 处 chatbiz-postgres:5432
- **WHEN** the same developer runs `grep -c "@chatbiz-postgres:5432" infrastructure/docker-compose.yml` after the change
- **THEN** the output MUST be `9`

#### Scenario: 不动 test / dev / e2e-ha compose
- **WHEN** the same developer runs `grep -c "@postgres:5432" infrastructure/docker-compose-test.yml` and `grep -c "@chatbiz-e2e-ha-postgres:5432" infrastructure/docker-compose-e2e-ha.yml`
- **THEN** the outputs MUST be unchanged from before this change (test compose keeps its `@postgres:5432` references per the `CLAUDE.md` "test compose by design 隔离网络 + 独立命名空间" exemption; e2e-ha compose keeps its `@chatbiz-e2e-ha-postgres:5432` references which are an independent naming)
- **AND WHEN** the same developer runs `grep -c "@postgres:5432" infrastructure/docker-compose-dev.yml`
- **THEN** the output MUST be `0` (dev compose was already correct in this respect, no change)

### Requirement: 4 个 *-migrate container 全部 Exited (0) 跑通
The system MUST result in all four one-shot Alembic upgrade containers — `chatbiz-credential-migrate`, `chatbiz-audit-isolation-migrate`, `chatbiz-workflow-engine-migrate`, and `chatbiz-sso-migrate` — reporting `Exited (0)` after running `docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose-dev.yml up -d` for at least 60 seconds, proving that the new `chatbiz-postgres:5432` hostname resolves correctly via Docker Compose's internal DNS and the asyncpg connection no longer fails at SSL upgrade.

#### Scenario: 4 个 migrate container Exited (0)
- **WHEN** a developer runs `docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose-dev.yml up -d` and waits at least 60 seconds, then runs `docker ps -a --filter name=chatbiz-credential-migrate --filter name=chatbiz-audit-isolation-migrate --filter name=chatbiz-workflow-engine-migrate --filter name=chatbiz-sso-migrate --format "{{.Names}}: {{.Status}}"`
- **THEN** the output MUST list exactly 4 lines, each ending with `Exited (0)` (the normal "completed successfully" state for a `restart: "no"` one-shot container)

#### Scenario: chatbiz-postgres healthcheck 在 migrate 之前就 pass
- **WHEN** the same developer inspects the migrate container logs with `docker logs chatbiz-credential-migrate --tail 5`
- **THEN** the last line MUST NOT contain `ConnectionError` or `connection_lost()` (the previous failure mode)
- **AND** the log MUST contain an alembic-related success marker such as `Running upgrade` or `alembic.ini` indicating the migration script reached its upgrade stage
