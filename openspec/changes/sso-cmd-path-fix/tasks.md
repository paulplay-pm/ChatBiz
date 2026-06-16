# sso-cmd-path-fix — Tasks

## 1. Dockerfile 2 行修改 + 验证

- [ ] 1.1 改 `services/sso/Dockerfile` line 36: `WORKDIR /home/sso` → `WORKDIR /app`
- [ ] 1.2 改 `services/sso/Dockerfile` line 41: `COPY --chown=chatbiz-sso:chatbiz-sso . /home/sso` → `COPY --chown=chatbiz-sso:chatbiz-sso . /app`
- [ ] 1.3 验证 V1:`git diff services/sso/Dockerfile` 显示 2 行 +,2 行 -
- [ ] 1.4 验证 V1.5:`grep -E "^WORKDIR" services/sso/Dockerfile` 输出含 `WORKDIR /app`,不含 `/home/sso`
- [ ] 1.5 验证 V1.6:`grep -E "^COPY.*\.$" services/sso/Dockerfile` 输出含 `/app`
- [ ] 1.6 commit:`git add services/sso/Dockerfile && git commit -m "fix(sso): align WORKDIR + COPY target to /app so uvicorn can find app/main.py"`

## 2. 重建 sso image + 端到端 docker compose 验证

- [ ] 2.1 跑 `docker build -t chatbiz/sso:dev -f services/sso/Dockerfile services/sso` 重建 sso image
- [ ] 2.2 验证 V2: build exit 0,`docker images chatbiz/sso:dev` 显示新 image
- [ ] 2.3 跑 `docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose-dev.yml up -d` 跑 30s
- [ ] 2.4 验证 V3:`docker ps --filter name=chatbiz-sso-1 --format "{{.Status}}"` 输出 `(healthy)`
- [ ] 2.5 验证 V4:`docker ps --filter name=chatbiz-mcp --filter name=chatbiz-workflow-engine --format "{{.Names}}: {{.Status}}"` 输出 2 行 `(healthy)`
- [ ] 2.6 验证 V5:`docker exec chatbiz-sso-1 python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8007/healthz').status)"` 输出 `200`

## 3. openspec archive + commit + push + retro

- [ ] 3.1 `openspec archive sso-cmd-path-fix --yes` (1 commit)
- [ ] 3.2 merge to main + push origin main + 写 retrospective
- [ ] 3.3 删 worktree + branch
