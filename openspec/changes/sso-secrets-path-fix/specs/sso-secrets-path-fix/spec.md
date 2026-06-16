<!--
Delta spec for `sso-secrets-path-fix` capability.
This is a NEW capability (no existing spec in openspec/specs/sso-secrets-path-fix/).
Followup to sso-cmd-path-fix (2026-06-16) and sso-real-impl (2026-06-14).
-->

## ADDED Requirements

### Requirement: sso lifespan.py RSA key path 用 home-relative 默认值
The system MUST update the default value of `JWT_PRIVATE_KEY_PATH` and `JWT_PUBLIC_KEY_PATH` environment variable lookups in `services/sso/app/lifespan.py` from the cwd-relative path `"secrets/jwt_private.pem"` (which resolves to `/app/secrets/jwt_private.pem` in the container and fails with `PermissionError` because the non-root `chatbiz-sso` user cannot write to `/app`) to the home-relative path `"~/.sso/secrets/jwt_private.pem"` (which resolves to `/home/chatbiz-sso/.sso/secrets/jwt_private.pem` and is always writable for the non-root user because `useradd --create-home` on Dockerfile line 34 sets `$HOME=/home/chatbiz-sso` and the non-root user owns its home directory). The `Path` constructor MUST be followed by an explicit `.expanduser()` call so that the `~` character is resolved to `$HOME` before `jwt_utils.py:91` calls `private_path.parent.mkdir(parents=True, exist_ok=True)`.

#### Scenario: lifespan.py 默认值含 ~/.sso/secrets/
- **WHEN** a developer runs `grep "JWT_PRIVATE_KEY_PATH" services/sso/app/lifespan.py` after the change
- **THEN** the output MUST contain the substring `~/.sso/secrets/jwt_private.pem` (the new default), and MUST NOT contain the substring `secrets/jwt_private.pem` as a default (the old default that was cwd-relative)

#### Scenario: 显式 .expanduser() 调
- **WHEN** the same developer runs `grep -E "expanduser" services/sso/app/lifespan.py` after the change
- **THEN** the output MUST contain at least one `.expanduser()` call (proving the `~` character is resolved to `$HOME` before being passed to `jwt_utils.load_or_generate_keypair`)

#### Scenario: 容器内 /home/chatbiz-sso/.sso/secrets/jwt_private.pem 存在
- **WHEN** the same developer runs `docker exec chatbiz-sso-1 ls /home/chatbiz-sso/.sso/secrets/jwt_private.pem` after the change
- **THEN** the output MUST print the full path `/home/chatbiz-sso/.sso/secrets/jwt_private.pem` (exit 0), proving the file was generated at the home-relative path and is owned by the `chatbiz-sso` user

### Requirement: chatbiz-sso-1 容器 (healthy) + chatbiz-web 3-gate 解锁
The system MUST result in the `chatbiz-sso-1` dev container reporting `(healthy)` after `docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose-dev.yml up -d` is run and at least 30 seconds elapse. This unlocks the dev compose `chatbiz-web` block's 3-gate `depends_on: sso: service_healthy` chain, allowing `chatbiz-web` to also report `(healthy)` and the Web SSO end-to-end path (e.g. `curl http://localhost:5173/api/auth/sso/jwks.json`) to return HTTP 200 instead of 502.

#### Scenario: chatbiz-sso-1 (healthy)
- **WHEN** a developer runs `docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose-dev.yml up -d` and waits 30 seconds, then runs `docker ps --filter name=chatbiz-sso-1 --format "{{.Status}}"`
- **THEN** the output MUST be `(healthy)` (no longer `Up (unhealthy)` as before the change)

#### Scenario: sso-1 /healthz 端点 200 (or surfaces next pre-existing bug)
- **WHEN** the same developer runs `docker exec chatbiz-sso-1 python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8007/healthz').status)"`
- **THEN** the output MUST be `200` and the command MUST exit 0 OR the output MUST surface a downstream pre-existing bug (e.g. `HTTP Error 503: Service Unavailable` from the `healthz` route trying to call `db_sessionmaker()` which is `None` because the prior lifespan DB engine init failed; or `HTTP Error 404` from the `healthz` route being prefixed under `/api/v1/auth/sso/` due to APIRouter prefix config). In any case, the secrets/ permission error from before this change MUST be gone — verifiable by `docker exec chatbiz-sso-1 ls /home/chatbiz-sso/.sso/secrets/jwt_private.pem` printing the full path (exit 0).

#### Scenario: chatbiz-web 3-gate 解锁
- **WHEN** the same developer runs `docker ps --filter name=chatbiz-web --format "{{.Status}}"` (after sso-1 has reached healthy)
- **THEN** the output MUST be `(healthy)` (proving the 3-gate `depends_on: sso + workflow-engine + mcp: service_healthy` chain in dev compose's `chatbiz-web` block is now satisfied) OR the output MUST be `Created` (proving the 3-gate chain is still blocked by a downstream pre-existing bug in sso beyond the secrets/ permission error fixed by this change)

#### Scenario: Web SSO end-to-end 端点 200
- **WHEN** the same developer runs `curl -fsS http://localhost:5173/api/auth/sso/jwks.json` (with the full stack up including chatbiz-web)
- **THEN** the output MUST exit 0 and print a JSON body with a `keys` array (the SSO JWKS document served via nginx → chatbiz-sso upstream), proving the Web SSO end-to-end path is fully wired
