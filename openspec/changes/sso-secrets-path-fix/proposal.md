# sso-secrets-path-fix — Proposal

## Why

`services/sso/app/lifespan.py:60-61` 设 `private_path = Path(os.getenv("JWT_PRIVATE_KEY_PATH", "secrets/jwt_private.pem"))`,默认相对路径在容器内 resolve 为 `/app/secrets/jwt_private.pem` (因为 sso-cmd-path-fix 改 WORKDIR → `/app`)。`jwt_utils.py:91` 调 `private_path.parent.mkdir(parents=True, exist_ok=True)`,但 sso 容器以非 root user `chatbiz-sso` 运行,Dockerfile:43。`/app` 目录 owner 是 root,非 root user 无 write permission。

后果: `sso-1` 容器从 sso-cmd-path-fix 修后是 `Up (unhealthy)`,uvicorn lifespan 跑 RSA key generation 时 `PermissionError: [Errno 13] Permission denied: 'secrets'`,FastAPI startup fail → healthcheck 端点 `/healthz` 起不来,`chatbiz-web` 3-gate `depends_on: sso: service_healthy` 永远卡。

**这是 sso-real-impl (archive 2026-06-14) 当时没 surface 的 followup**。

## What Changes

- **修改** `services/sso/app/lifespan.py:60-61`: 默认 `JWT_PRIVATE_KEY_PATH` 从 `"secrets/jwt_private.pem"` → `"~/.sso/secrets/jwt_private.pem"`,默认 `JWT_PUBLIC_KEY_PATH` 同样改。`~` 在 Path constructor 中 expand 为 `$HOME` (`/home/chatbiz-sso` 由 `useradd --create-home` 创),always writable for the non-root user
- **不** 改 `services/sso/Dockerfile` (HOME 已是 `/home/chatbiz-sso`,非 root user 拥有 `$HOME`,无 need 再 mkdir / chown)
- **不** 改 `infrastructure/docker-compose*.yml` (无 env var 改动,默认值升级即生效)
- **不** 改 `services/sso/.env.example` (默认值的更新对所有调用者一致;现有引用 `secrets/jwt_private.pem` 的 `.env` 用户可保留覆盖)
- **不** 改 `services/sso/app/jwt_utils.py` (函数实现正确,只改 lifespan.py 传入的 default path)

## Capabilities

### New Capabilities

无。这是 sso Python source 1 个默认值升级,不是新 capability。

### Modified Capabilities

- `sso-real-impl` (existing capability, archive 2026-06-14): **前端范围** = N/A (无前端变更);**后端范围** = 1 file (lifespan.py) 2 line edits;**是否豁免前端** = 是 — 纯 Python 源 path fix,跟前端 0 关系。

## Impact

- **新开发者 onboarding**: 跑 `docker compose -f ... -f ... up -d` 后 `chatbiz-sso-1` 从 `Up (unhealthy)` 升到 `(healthy)`,`chatbiz-web` 3-gate `depends_on: sso: service_healthy` 通过,Web SSO 端到端可用
- **CI**: 不动 `.github/workflows/ci-cov.yml` (sso cov 矩阵已含,本 change 0 cov 变化)
- **生产部署**: 0 影响 (生产 K8s 通常显式设 `JWT_PRIVATE_KEY_PATH` env var 到 secret-mounted path,默认值不被使用)
- **被消费的下游**: 4 个 `chatbiz-web` 3-gate 内的依赖 (sso 起来后) 都可工作;V1 (dev compose curl http://localhost:5173/api/auth/sso/jwks.json) 可从 502 升到 200

## Non-goals

1. **不** 改 Dockerfile (useradd --create-home 已设 $HOME,非 root user 拥有 $HOME,无 need mkdir)
2. **不** 改 .env.example (默认值升级,显式覆盖仍 work)
3. **不** 改 jwt_utils.py (函数实现正确,只改 lifespan.py 传入的 default)
4. **不** 改 .github/workflows/ci-cov.yml
5. **不** 改 docker-compose*.yml
6. **不** 写新 capability
7. **不** 加 unit test (本 change 改默认值,跟原 sso-real-impl 的 100% cov 兼容)
