<!--
Delta spec for `sso-cmd-path-fix` capability.
This is a NEW capability (no existing spec in openspec/specs/sso-cmd-path-fix/).
Followup to sso-real-impl (2026-06-14).
-->

## ADDED Requirements

### Requirement: sso 容器源码装到 /app/app 路径
The system MUST install the sso service source code at the path `/app/app/` inside the runtime container image, so that the `uvicorn app.main:app` command (which resolves `app.main` relative to the container's `WORKDIR`) can locate the FastAPI `app` package. Specifically, `services/sso/Dockerfile` MUST set `WORKDIR /app` (not `/home/sso`) and MUST `COPY` the source tree to `/app` (not `/home/sso`). The Dockerfile's CMD MUST remain `uvicorn app.main:app --host 0.0.0.0 --port 8007` so it resolves `app.main` against the new WORKDIR.

#### Scenario: Dockerfile WORKDIR 改到 /app
- **WHEN** a developer runs `grep -E "^WORKDIR" services/sso/Dockerfile` after the change
- **THEN** the output MUST contain `WORKDIR /app` (and MUST NOT contain `WORKDIR /home/sso`)

#### Scenario: Dockerfile COPY 目标改到 /app
- **WHEN** the same developer runs `grep -E "^COPY.*\.$" services/sso/Dockerfile` after the change
- **THEN** the output MUST contain a line matching `COPY --chown=chatbiz-sso:chatbiz-sso . /app` (and MUST NOT contain any `COPY ... /home/sso` line)

#### Scenario: 容器内 /app/app/main.py 存在
- **WHEN** the same developer runs `docker run --rm chatbiz/sso:dev ls /app/app/main.py` after rebuilding the image
- **THEN** the output MUST print the full path `/app/app/main.py` (exit 0), proving the source is installed at the expected location

### Requirement: chatbiz-sso-1 容器 uvicorn 能 import app.main
The system MUST result in the `chatbiz-sso-1` dev container's uvicorn process successfully importing `app.main` and starting the FastAPI app, after `docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose-dev.yml up -d` is run. Specifically, `chatbiz-sso-1` MUST be in state `Up` (not `Exited (2)`), proving that the Dockerfile's `WORKDIR /app` + `COPY ... /app` change resolves the uvicorn `app.main:app` import correctly. The container MAY still be marked `(unhealthy)` if downstream code (e.g. `app/lifespan.py`'s RSA key generation) fails at a later stage — that is tracked as a separate pre-existing bug (`sso-real-impl` followup), out of this change's scope.

#### Scenario: chatbiz-sso-1 Up (no longer Exited 2)
- **WHEN** a developer runs `docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose-dev.yml up -d` and waits 30 seconds, then runs `docker ps -a --filter name=chatbiz-sso-1 --format "{{.Names}}: {{.Status}}"`
- **THEN** the output MUST contain `Up` in the status field (not `Exited (2)` as before the change). The status MAY also include `(unhealthy)` due to a downstream lifespan error — that is acceptable for this requirement

#### Scenario: cascade 修复 — mcp + workflow-engine 都 Up (healthy)
- **WHEN** the same developer runs `docker ps --filter name=chatbiz-mcp --filter name=chatbiz-workflow-engine --format "{{.Names}}: {{.Status}}"`
- **THEN** the output MUST list 2 lines, each ending with `(healthy)` (proving the 3-gate `depends_on: sso: service_healthy` chain that dev compose extends onto `chatbiz-web` is now satisfied — note: the `sso: service_healthy` gate may fail if sso-1 is unhealthy, but the mcp and workflow-engine containers' own healthchecks (postgres + redis + own health) may still pass independently)
- **OR** if sso-1 is unhealthy, the output MAY show mcp / workflow-engine in `Waiting` or `(unhealthy)` state due to the cascade — that is acceptable for this change since the WORKDIR fix unblocks the uvicorn import (the primary goal); the downstream `app/lifespan.py` `secrets/` permission error is tracked separately
