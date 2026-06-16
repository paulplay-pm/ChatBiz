# sso-healthz-route-fix — Tasks

## 1. main.py + routers/sso.py 改 + 验证

- [ ] 1.1 改 `services/sso/app/main.py`: 在 `app.include_router(sso_router.router)` 之前加 `@app.get("/healthz")` 装饰器 + healthz handler (用 `async with request.app.state.db_sessionmaker() as session:`)
- [ ] 1.2 改 `services/sso/app/routers/sso.py`: 删 `# --- /healthz ---` 整段 (含 `@router.get("/healthz")` 装饰器 + `async def healthz` 函数)
- [ ] 1.3 验证 V1: `grep '@app.get("/healthz")' services/sso/app/main.py` 输出 ≥ 1 行
- [ ] 1.4 验证 V2: `grep "async with" services/sso/app/main.py | grep session.execute` 输出 ≥ 1 行
- [ ] 1.5 验证 V3: `grep -c "healthz" services/sso/app/routers/sso.py` 输出 `0`
- [ ] 1.6 验证 V4: `git diff --stat services/sso/app/` 显示 2 files changed
- [ ] 1.7 commit: `git add services/sso/app/ && git commit -m "fix(sso): move /healthz to main.py (no APIRouter prefix) + use async_sessionmaker as context manager"`

## 2. 重建 sso image + 端到端 docker compose 验证

- [ ] 2.1 跑 `docker build -t chatbiz/sso:dev -f services/sso/Dockerfile services/sso` 重建 sso image
- [ ] 2.2 验证 V-build: build exit 0, `docker images chatbiz/sso:dev` 显示新 image
- [ ] 2.3 跑 `docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose-dev.yml up -d` 跑 30s
- [ ] 2.4 验证 V5: `docker ps --filter name=chatbiz-sso-1 --format "{{.Status}}"` 输出 `(healthy)`
- [ ] 2.5 验证 V6: `docker exec chatbiz-sso-1 python -c "urllib.urlopen('http://127.0.0.1:8007/healthz').status"` 输出 `200`
- [ ] 2.6 验证 V7: `docker ps --filter name=chatbiz-web --format "{{.Status}}"` 输出 `(healthy)`
- [ ] 2.7 验证 V8: `curl -fsS http://localhost:5173/api/auth/sso/jwks.json | head -c 200` 输出 JSON `{"keys":`

## 3. openspec archive + commit + push + retro

- [ ] 3.1 `openspec archive sso-healthz-route-fix --yes` (1 commit)
- [ ] 3.2 merge to main + push origin main + 写 retrospective
- [ ] 3.3 删 worktree + branch
