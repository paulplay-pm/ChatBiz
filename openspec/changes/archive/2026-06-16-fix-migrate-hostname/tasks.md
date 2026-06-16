# fix-migrate-hostname — Tasks

## 1. base compose sed 替换 + 验证

- [ ] 1.1 跑 `sed -i '' 's|@postgres:5432|@chatbiz-postgres:5432|g' infrastructure/docker-compose.yml`
- [ ] 1.2 验证 V1:`grep -c "postgres:5432" infrastructure/docker-compose.yml` 输出 `0`
- [ ] 1.3 验证 V2:`grep -c "chatbiz-postgres:5432" infrastructure/docker-compose.yml` 输出 `9`
- [ ] 1.4 验证 V3:`git diff --stat` 显示 `1 file changed, 9 insertions(+), 9 deletions(-)`
- [ ] 1.5 commit:`git add infrastructure/docker-compose.yml && git commit -m "fix(infrastructure): rename postgres:5432 → chatbiz-postgres:5432 in *-migrate env vars (fix-compose followup)"`

## 2. 端到端 docker compose 验证

- [ ] 2.1 跑 `docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose-dev.yml up -d` 后等 60s
- [ ] 2.2 验证 V4:`docker ps -a --filter name=chatbiz-credential-migrate --filter name=chatbiz-audit-isolation-migrate --filter name=chatbiz-workflow-engine-migrate --filter name=chatbiz-sso-migrate --format "{{.Names}}: {{.Status}}"` 输出 4 行,每行 `Exited (0)`
- [ ] 2.3 验证 V4.5:`docker logs chatbiz-credential-migrate --tail 5` 不含 `ConnectionError` 或 `connection_lost()`,含 alembic success marker

## 3. openspec archive + commit + push + retro

- [ ] 3.1 `openspec archive fix-migrate-hostname --yes` (1 commit)
- [ ] 3.2 merge to main + push origin main + 写 retrospective
- [ ] 3.3 删 worktree + branch
