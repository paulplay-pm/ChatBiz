<!--
Delta spec for `web-frontend-containerization` capability.
This is a NEW capability (no existing spec in openspec/specs/web-frontend-containerization/),
so only ADDED Requirements apply.
-->

## ADDED Requirements

### Requirement: chatbiz-web 服务容器在 base compose 注册
The system MUST register the `chatbiz-web` service in `infrastructure/docker-compose.yml` as a first-class service, with `service key: chatbiz-web` (matching the `chatbiz-` prefix convention required by `CLAUDE.md` and the `openspec/config.yaml` apply-rule), explicit `container_name: chatbiz-web`, an `image: chatbiz/web:dev` field, a `build:` block pointing at `web/Dockerfile`, a `ports` mapping of `5173:80`, and a `healthcheck` matching the nginx `/health` endpoint. The service key MUST NOT be the legacy short form `web`; the change MUST be lint-clean under `tools/check-compose-naming.sh` without falling into the baseline suppression list.

#### Scenario: base compose 列出 chatbiz-web service
- **WHEN** a developer runs `docker compose -f infrastructure/docker-compose.yml config --services` on main
- **THEN** the output MUST include the line `chatbiz-web` (full `chatbiz-` prefixed service key, satisfying the project's mandatory service-key naming convention)

#### Scenario: base compose 段格式自洽
- **WHEN** the same developer runs `bash tools/check-compose-naming.sh` after the change
- **THEN** the script MUST exit 0 and report `OK: 0 error(s), 0 warning(s)`, with `chatbiz-web` satisfying rule 1 (`chatbiz-` prefix on service key) and rule 2 (explicit `container_name`) without falling into the baseline suppression list

### Requirement: web/Dockerfile 重写为多阶段 (builder + runtime)
The system MUST rebuild `web/Dockerfile` as a two-stage Docker image. The `builder` stage MUST use `node:20-alpine` as its base, run `pnpm install --frozen-lockfile`, and execute `pnpm build` for each of the three sub-applications (`portal`, `canvas`, `admin`) with the appropriate `VITE_APP_BASE` argument. The `runtime` stage MUST use `nginx:1.27-alpine`, copy the `dist/` directories for the three sub-applications and the `nginx.conf` file from the builder stage, expose port 80, define a `HEALTHCHECK` against `http://127.0.0.1:80/health`, and run `nginx -g "daemon off;"` as its `CMD`.

#### Scenario: Dockerfile 头 25 行可读出多阶段结构
- **WHEN** a developer runs `head -25 web/Dockerfile`
- **THEN** the output MUST contain `FROM node:20-alpine AS builder` and `FROM nginx:1.27-alpine AS runtime`

#### Scenario: builder 阶段复制 dist 到 runtime 阶段
- **WHEN** a developer runs `grep -E "COPY .*dist|COPY nginx.conf" web/Dockerfile`
- **THEN** the output MUST contain at least one `COPY --from=builder` line copying either `dist/` directories or `nginx.conf` into the `runtime` stage

### Requirement: dev compose chatbiz-web 段用 extends 拉 base 重定义
The system MUST rewrite the `chatbiz-web` service in `infrastructure/docker-compose-dev.yml` to use `extends:` referencing the base compose `chatbiz-web` service. The dev override MUST re-declare `container_name: chatbiz-web` (so dev-namespace lint visibility holds), `image: chatbiz/web:dev`, and bind-mount `../web:/app` for live source reload. The existing `web-node-modules: { name: chatbiz-web-node-modules }` named volume MUST be preserved in the top-level `volumes:` block.

#### Scenario: dev compose 段用 extends 拉 base
- **WHEN** a developer runs `grep -A 6 "^  chatbiz-web:" infrastructure/docker-compose-dev.yml`
- **THEN** the output MUST include `extends:` with `file: docker-compose.yml` and `service: chatbiz-web`

#### Scenario: dev compose 段显式 container_name
- **WHEN** the same developer runs `bash tools/check-compose-naming.sh` after the change
- **THEN** the dev compose `chatbiz-web` service MUST be lint-visible as `container_name: chatbiz-web` and MUST NOT trigger the baseline warning path

### Requirement: chatbiz-web 服务 depends_on nginx upstream 健康起来后才 ready
The system MUST declare the `chatbiz-web` service with `depends_on:` on `workflow-engine` and `mcp` (the base compose service keys; `mcp` resolves to container `chatbiz-mcp` at runtime via its `container_name: chatbiz-mcp` directive), each with `condition: service_healthy`. The dev compose overlay MUST additionally depend on `chatbiz-sso` (because `chatbiz-sso` is a dev-only service that does not exist in the base compose). The combined set of upstream services — base (`workflow-engine`, `mcp`) + dev overlay (`chatbiz-sso`) — MUST total exactly three services matching the `proxy_pass` directives declared in `web/nginx.conf` (lines 50-81), and MUST NOT include `audit-and-isolation` or `credential` (which are not proxied through nginx).

#### Scenario: base compose 段 depends_on 含 2 个 upstream 且全 service_healthy
- **WHEN** a developer runs `docker compose -f infrastructure/docker-compose.yml config chatbiz-web` and inspects the rendered `depends_on` block
- **THEN** the rendered output MUST list exactly two services — `workflow-engine` and `mcp` — each with `condition: service_healthy`

#### Scenario: dev overlay chatbiz-web 段含 3 个 upstream 且全 service_healthy
- **WHEN** the same developer runs `docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose-dev.yml config chatbiz-web` (with the dev overlay in scope) and inspects the rendered `depends_on` block
- **THEN** the rendered output MUST list exactly three services — `chatbiz-sso`, `workflow-engine`, `mcp` — each with `condition: service_healthy`

#### Scenario: chatbiz-web 段不依赖 audit-and-isolation / credential
- **WHEN** the same developer inspects the rendered `depends_on` block in either base or dev overlay
- **THEN** the output MUST NOT include `audit-and-isolation` or `credential` (or any non-proxied backend)

### Requirement: chatbiz-web 容器单端口 5173 + nginx upstream 代理可工作
The system MUST expose `chatbiz-web` on host port 5173 mapping to container port 80, and the nginx configuration in `web/nginx.conf` MUST remain unchanged after this change. After `docker compose -f docker-compose.yml -f docker-compose-dev.yml up -d chatbiz-web`, a `curl http://localhost:5173/health` MUST return HTTP 200 with body `OK\n`, and `curl http://localhost:5173/api/auth/sso/jwks.json` MUST return HTTP 200 with a JSON body (proving the `chatbiz-sso` upstream proxy works through nginx).

#### Scenario: nginx /health 端点
- **WHEN** a developer runs `curl -fsS http://localhost:5173/health` after starting the stack
- **THEN** the command MUST exit 0 and the body MUST equal `OK\n` (matching the existing nginx `location /health` block)

#### Scenario: nginx upstream proxy (sso)
- **WHEN** the same developer runs `curl -fsS http://localhost:5173/api/auth/sso/jwks.json` after `chatbiz-sso` is healthy
- **THEN** the command MUST exit 0 with a JSON response body, proving nginx correctly proxies `/api/auth/sso/` to `http://chatbiz-sso:8007`

#### Scenario: nginx upstream proxy (workflow)
- **WHEN** the same developer runs `curl -fsS http://localhost:5173/workflows/healthz` after `workflow-engine` is healthy
- **THEN** the command MUST exit 0 with HTTP 200, proving nginx correctly proxies `/workflows` to `http://workflow-engine:8001`
