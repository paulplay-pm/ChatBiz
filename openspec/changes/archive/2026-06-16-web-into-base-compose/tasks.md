# web-into-base-compose — Tasks

## 1. Dockerfile 多阶段重写

- [ ] 1.1 重写 `web/Dockerfile`:第 1 阶段 `FROM node:20-alpine AS builder`,装 pnpm + `pnpm install --frozen-lockfile`,跑 3 个 `pnpm build` (portal 用 `VITE_APP_BASE=/portal/`、canvas 用 `VITE_APP_BASE=/canvas/`、admin 用 `VITE_APP_BASE=/admin/`)
- [ ] 1.2 重写 `web/Dockerfile`:第 2 阶段 `FROM nginx:1.27-alpine AS runtime`,`COPY --from=builder` 3 个 dist + `nginx.conf`,`EXPOSE 80`,沿用现有 `HEALTHCHECK` + `CMD ["nginx", "-g", "daemon off;"]`
- [ ] 1.3 验证 V1:`head -25 web/Dockerfile` 输出含 `FROM node:20-alpine AS builder` + `FROM nginx:1.27-alpine AS runtime`

## 2. base compose 新增 chatbiz-web 段

- [ ] 2.1 在 `infrastructure/docker-compose.yml` `mcp` 段后、`workflow-engine` 段前新增 `chatbiz-web:` 段,内容含 `build: { context: ../web, dockerfile: Dockerfile }` + `image: chatbiz/web:dev` + `container_name: chatbiz-web` + `restart: unless-stopped` + `ports: ["5173:80"]` (service key 强制 `chatbiz-` 前缀,满足 `CLAUDE.md` 强制约定)
- [ ] 2.2 在新 `chatbiz-web:` 段加 `depends_on: chatbiz-sso + workflow-engine + chatbiz-mcp` 全 `condition: service_healthy`,`chatbiz-mcp` 走 v6a alias 命名跟 dev compose 段一致
- [ ] 2.3 在新 `chatbiz-web:` 段加 `healthcheck: { test: ["CMD", "wget", "-qO-", "http://127.0.0.1:80/health"], interval: 30s, timeout: 5s, retries: 3, start_period: 5s }`
- [ ] 2.4 验证 V2:`docker compose -f infrastructure/docker-compose.yml config --services | grep chatbiz-web` 输出 `chatbiz-web`
- [ ] 2.5 验证 V3:`docker compose -f infrastructure/docker-compose.yml config | grep -A 20 "^  chatbiz-web:"` 看到 `container_name: chatbiz-web` + `build:` + `depends_on:`

## 3. dev compose 改 chatbiz-web 段为 extends 重定义

- [ ] 3.1 在 `infrastructure/docker-compose-dev.yml` 替换 `chatbiz-web:` 段为 `extends: { file: docker-compose.yml, service: chatbiz-web }` + 显式 `container_name: chatbiz-web` (dev namespace lint 可见) + `image: chatbiz/web:dev` + bind mount `../web:/app` + `web-node-modules` 命名 volume
- [ ] 3.2 保留 dev compose 顶层 `volumes:` 段 `web-node-modules: { name: chatbiz-web-node-modules }` (第 257-258 行不动)
- [ ] 3.3 验证 V4:`grep -A 6 "^  chatbiz-web:" infrastructure/docker-compose-dev.yml` 看到 `extends:` + `file: docker-compose.yml` + `service: chatbiz-web`

## 4. lint + 端到端验证

- [ ] 4.1 验证 V5:`bash tools/check-compose-naming.sh` exit 0 + `OK: 0 error(s), 0 warning(s)`,chatbiz-web 不触发 baseline warning
- [ ] 4.2 验证 V6:`docker compose -f docker-compose.yml -f docker-compose-dev.yml build chatbiz-web` exit 0,`docker images | grep chatbiz/web` 显示 `chatbiz/web:dev`
- [ ] 4.3 验证 V7:`docker compose -f docker-compose.yml -f docker-compose-dev.yml up -d chatbiz-web` + 等 30s,`docker ps --filter name=chatbiz-web` 显示 `(healthy)`
- [ ] 4.4 验证 V8:`curl -fsS http://localhost:5173/health` exit 0 + body `OK\n`
- [ ] 4.5 验证 V9:`curl -fsS http://localhost:5173/api/auth/sso/jwks.json` exit 0 + JSON body (sso 起来后)
- [ ] 4.6 验证 V10:`curl -fsS http://localhost:5173/workflows/healthz` exit 0 + 200 (workflow-engine 起来后)

## 5. openspec archive + commit + push

- [ ] 5.1 `openspec archive --change web-into-base-compose --yes` (按 superpowers-bridge 8 阶段,apply 阶段由 archive 一次性 commit)
- [ ] 5.2 `git log --oneline -3` 看到 `feat(infrastructure): chatbiz-web-into-base-compose` + `chore(openspec): archive chatbiz-web-into-base-compose` 2 个新 commit
- [ ] 5.3 `git push origin worktree-web-into-base-compose` 推到 remote
- [ ] 5.4 写 `openspec/changes/archive/2026-06-16-chatbiz-web-into-base-compose/retrospective.md` (按已有 5 followups 模式)
- [ ] 5.5 删 worktree:`git worktree remove /Users/paulwang/work/ChatBiz/.worktrees/web-into-base-compose` + `git branch -d worktree-web-into-base-compose`
