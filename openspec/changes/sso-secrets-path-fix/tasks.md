# sso-secrets-path-fix — Tasks

## 1. lifespan.py 改 2 行 + 验证

- [ ] 1.1 改 `services/sso/app/lifespan.py:60`: `Path(os.getenv("JWT_PRIVATE_KEY_PATH", "secrets/jwt_private.pem"))` → `Path(os.getenv("JWT_PRIVATE_KEY_PATH", "~/.sso/secrets/jwt_private.pem")).expanduser()`
- [ ] 1.2 改 `services/sso/app/lifespan.py:61`: `Path(os.getenv("JWT_PUBLIC_KEY_PATH", "secrets/jwt_public.pem"))` → `Path(os.getenv("JWT_PUBLIC_KEY_PATH", "~/.sso/secrets/jwt_public.pem")).expanduser()`
- [ ] 1.3 验证 V1:`git diff services/sso/app/lifespan.py` 显示 4 lines diff (2 insertions, 2 deletions)
- [ ] 1.4 验证 V2:`grep "JWT_PRIVATE_KEY_PATH" services/sso/app/lifespan.py` 输出含 `~/.sso/secrets/jwt_private.pem`
- [ ] 1.5 验证 V3:`grep -E "expanduser" services/sso/app/lifespan.py` 输出至少 1 行
- [ ] 1.6 commit:`git add services/sso/app/lifespan.py && git commit -m "fix(sso): use ~/.sso/secrets/ default for JWT key paths so non-root user can write"`

## 2. 重建 sso image + 端到端 docker compose 验证

- [ ] 2.1 跑 `docker build -t chatbiz/sso:dev -f services/sso/Dockerfile services/sso` 重建 sso image
- [ ] 2.2 验证 V-build: build exit 0,`docker images chatbiz/sso:dev` 显示新 image
- [ ] 2.3 跑 `docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose-dev.yml up -d` 跑 30s
- [ ] 2.4 验证 V4:`docker ps --filter name=chatbiz-sso-1 --format "{{.Status}}"` 输出 `(healthy)`
- [ ] 2.5 验证 V5:`docker exec chatbiz-sso-1 python -c "urllib.urlopen('http://127.0.0.1:8007/healthz').status"` 输出 `200`
- [ ] 2.6 验证 V6:`docker ps --filter name=chatbiz-web --format "{{.Status}}"` 输出 `(healthy)` (3-gate 解锁)
- [ ] 2.7 验证 V-end-to-end:`curl -fsS http://localhost:5173/api/auth/sso/jwks.json` 输出 JSON 200
- [ ] 2.8 验证 V3-files:`docker exec chatbiz-sso-1 ls /home/chatbiz-sso/.sso/secrets/jwt_private.pem` 输出完整 path

## 3. openspec archive + commit + push + retro

- [ ] 3.1 `openspec archive sso-secrets-path-fix --yes` (1 commit)
- [ ] 3.2 merge to main + push origin main + 写 retrospective
- [ ] 3.3 删 worktree + branch
