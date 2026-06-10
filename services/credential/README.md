# credential-management service

FastAPI service that owns the ChatBiz **encrypted credential vault**.

The service implements the requirements in
`openspec/specs/credential-management/spec.md` (5 canonical Requirements) plus
the 12 ADDED Requirements in
`openspec/changes/implement-credential-management/specs/credential-management/spec.md`.

## Architecture (one-paragraph)

A single FastAPI process backed by PostgreSQL. Credentials are stored as
`ciphertext || nonce || tag` produced by **AES-256-GCM** with a per-credential
**data-encryption key (DEK)**, and each DEK is itself wrapped by a
**master key** persisted in the `encryption_keys` table. Other caps obtain
plaintext via the `POST /api/v1/credentials/{id}/use` API; the service never
returns plaintext in list / detail responses. Every access is recorded in
`credential_audit` (hash of the credential id, no plaintext).

## Layout

```
services/credential/
├── app/                  # FastAPI app (routers, services, models) — Tasks 3-5
│   ├── routers/
│   ├── services/
│   └── cron.py
├── alembic/              # DB migrations — Task 2
│   ├── env.py
│   └── versions/
├── tests/                # unit / integration / e2e
│   ├── integration/
│   └── e2e/
├── locust/               # performance / load tests
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
├── Makefile
└── .pre-commit-config.yaml
```

## Local development

```bash
# 1. Bring up the full stack (postgres, redis, credential, alembic migrate, cron)
make dev

# 2. Or run the service against your own Postgres:
make install
export DATABASE_URL=postgresql+asyncpg://chatbiz:chatbiz@localhost:5432/credential
make migrate
make run
```

## Useful targets

| Command                | Purpose                                                |
|------------------------|--------------------------------------------------------|
| `make dev`             | `docker compose up` the full local stack               |
| `make test`            | Run pytest (unit + integration via testcontainers)     |
| `make migrate`         | Apply Alembic migrations to HEAD                       |
| `make run`             | Run uvicorn locally (no docker)                        |
| `make lint`            | `ruff check` + `ruff format --check` + `mypy`          |
| `make fmt`             | Auto-format with ruff                                  |
| `make sec`             | `bandit` security scan                                 |
| `make precommit`       | Run all pre-commit hooks                               |

## Status

- [x] **Task 1** — Service skeleton, Dockerfile, Makefile, docker-compose (this commit)
- [ ] **Task 2** — Database schema + Alembic migrations
- [ ] **Task 3** — Crypto module (envelope encryption)
- [ ] **Task 4** — Credential CRUD endpoints
- [ ] **Task 5** — `use` API (for other caps)
- [ ] **Task 6** — Cron: previous-value cleanup + expiring-soon alerts
- [ ] **Task 7** — Audit pipeline (writes to `audit-and-isolation`)
- [ ] **Task 8** — Tests (unit + integration + e2e + locust)
- [ ] **Task 9** — Observability + final verification
