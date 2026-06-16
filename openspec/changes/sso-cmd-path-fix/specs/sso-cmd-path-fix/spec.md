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

### Requirement: chatbiz-sso-1 容器 Up (healthy)
The system MUST result in the `chatbiz-sso-1` dev container reporting `(healthy)` after `docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose-dev.yml up -d` is run and at least 30 seconds elapse. This proves that the Dockerfile's `WORKDIR /app` + `COPY ... /app` change resolves the uvicorn `app.main:app` import correctly and the sso FastAPI service starts.

#### Scenario: chatbiz-sso-1 (healthy)
- **WHEN** a developer runs `docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose-dev.yml up -d` and waits 30 seconds, then runs `docker ps --filter name=chatbiz-sso-1 --format "{{.Status}}"`
- **THEN** the output MUST be `(healthy)` (no longer `Exited (2)` as before the change)

#### Scenario: sso-1 healthcheck 端点返回 200
- **WHEN** the same developer runs `docker exec chatbiz-sso-1 python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8007/healthz').status)"`
- **THEN** the output MUST be `200` and the command MUST exit 0

#### Scenario: cascade 修复 — mcp + workflow-engine 都 Up (healthy)
- **WHEN** the same developer runs `docker ps --filter name=chatbiz-mcp --filter name=chatbiz-workflow-engine --format "{{.Names}}: {{.Status}}"`
- **THEN** the output MUST list 2 lines, each ending with `(healthy)` (proving the 3-gate `depends_on: sso: service_healthy` chain that dev compose extends onto `chatbiz-web` is now satisfied for all 3 gates)
