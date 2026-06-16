# web-into-base-compose — Design

## Context

`chatbiz-web` 容器 (`web/` 目录的统一 SPA 运行时) 当前**只在** `infrastructure/docker-compose-dev.yml:174-184` 定义 (`service: web` 短名),跟 base compose 的 5 个 Python service 段格式不一致 (无 `extends:` 拉 base、service key 是 `web` 而不是 `chatbiz-` 前缀、没有 `image` 字段)。`openspec/config.yaml` apply-rule 第 1 条明文要求"服务容器在 `docker-compose.yml` 注册;格式与 credential/audit-and-isolation/workflow-engine/mcp 保持一致"。`chatbiz-web` 是服务容器,目前未在 base 注册 — 违反 apply-rule。

`web/Dockerfile` 现状是 1 阶段 (`nginx:1.27-alpine AS runtime`),要求 `portal/canvas/admin` 3 个子应用**先**在 host 跑 `vite build` 把 dist 产物拷进 nginx 镜像,跟其它 service 的多阶段 Dockerfile pattern 不一致 (`services/sso/Dockerfile` / `services/credential/Dockerfile` 都是 builder 阶段装 deps + runtime 阶段只拷产物)。

`web/nginx.conf:50-81` 的 6 个 `proxy_pass` 强依赖 `chatbiz-sso` / `workflow-engine` / `chatbiz-mcp` 内部 DNS 名 — 这是本 change 决定 `depends_on` 选哪些 service 的权威来源。

上游三件源:本 change 不触 `docs/architecture.md` / `docs/prd.md` / 设计 doc(无新增架构层、无产品需求变更、无 eng-review 决策冲突)。

## Goals / Non-Goals

**Goals** (3 条):
1. `chatbiz-web` 段在 `infrastructure/docker-compose.yml` (base) 注册,跟 `credential` / `audit-and-isolation` / `mcp` / `workflow-engine` / `sso` 同格式 (`service key: chatbiz-web` + `container_name: chatbiz-web` + 显式 `build` / `image` / `ports` / `depends_on` / `healthcheck`)。`chatbiz-` 前缀 service key 满足 `CLAUDE.md` 强制约定 "新加 service 必须 chatbiz- 前缀" (与 `chatbiz-postgres` / `chatbiz-redis` 一致)
2. `web/Dockerfile` 重写为 2 阶段:builder 阶段在容器内 `pnpm install` + 3 个 `vite build`;runtime 阶段只拷 `dist` + `nginx.conf`,跟 `services/sso/Dockerfile` / `services/credential/Dockerfile` 的多阶段 pattern 一致
3. dev compose 改为 `extends:` 拉 base `chatbiz-web` 段,重定义 `image: chatbiz/web:dev` + bind mount + (可选) reload 模式,跟现有 5 个 service 的 dev 模式对齐 (与 `chatbiz-mcp` / `chatbiz-postgres` / `chatbiz-redis` 的 fix-compose v6a alias 模式一致)

**Non-Goals** (3 条,显式 YAGNI):
1. **不**改 `web/nginx.conf` 内部路径或代理规则 — 现有 6 个 `proxy_pass` 段保持不变
2. **不**改 `web/` 目录下 5 个子应用 (`portal` / `canvas` / `admin` / `ui` / `integration-tests`) 的源代码或构建脚本
3. **不**写 K8s / Helm / 生产部署 — 跟 V2 阶段 scope 一致, prod 由后续 change 负责

## Decisions

### D1: chatbiz-web 段位置 = base + dev extends 重定义

**Context**: chatbiz-web 容器现在只在 dev compose 定义 (`service: web` 短名,违反 `chatbiz-` 前缀约定),base compose 段没注册。openspec apply-rule 第 1 条要求"服务容器在 docker-compose.yml 注册"。

**选项**:
- **A (已选)**: base 新增 `chatbiz-web:` 段,dev 改为 `extends:` 拉 base 重定义 (image: chatbiz/web:dev + bind mount + reload)
- B: 只在 dev,不动 base — 拒绝理由:违反 openspec apply-rule
- C: base 加空壳段(只占位),dev fills in — 拒绝理由:跟其它 5 service 命名 pattern 不一致,且 dev extends 拉空壳段没用

**结论**: 选 A。`chatbiz-web:` 段在 base 跟其它 service 同列,dev 拉 base 重定义。Service key 强制 `chatbiz-` 前缀,跟 `CLAUDE.md` "新加 service 禁止进 baseline,必须直接满足规则 1+2+3" 锁定;`chatbiz-web` 不进 12 baseline 列表(不误抑制)。

### D2: Dockerfile 改为 2 阶段 (builder + runtime)

**Context**: 现有 `web/Dockerfile` 1 阶段,要求 host 先 `vite build` 把 dist 拷进镜像。跟其它 service 多阶段 pattern 不一致 (`services/sso/Dockerfile` 是 builder + runtime 2 阶段)。

**选项**:
- **A (已选)**: 2 阶段 — stage 1 `node:20-alpine AS builder` 装 pnpm + 跑 3 个 `vite build` (用 VITE_APP_BASE 环境变量); stage 2 `nginx:1.27-alpine AS runtime` 只拷 `dist/` + `nginx.conf` + 设 `HEALTHCHECK` + `EXPOSE 80`
- B: 保留预 build 模式(现状) — 拒绝理由:跟其它 service 多阶段 pattern 不一致,新开发者要记 2 步
- C: 单阶段 with `npm ci` 在 runtime — 拒绝理由:runtime 镜像含 node + pnpm,膨胀 5x

**结论**: 选 A。builder 用 `node:20-alpine` 跟 web/`portal|canvas|admin/package.json` 里的 `engines.node` 约束对齐;runtime 沿用现有 `nginx:1.27-alpine` + `HEALTHCHECK` (现有 `wget -qO- http://127.0.0.1:80/health`)+ `EXPOSE 80` + `CMD ["nginx", "-g", "daemon off;"]`,0 业务行为变化。

### D3: depends_on 只 nginx upstream 代理过的 3 service

**Context**: `web/nginx.conf:50-81` 强耦合 `chatbiz-sso` (5 个 /api/auth/sso/ 端点) / `workflow-engine` (4 个 /api/nodes + /workflows + /runs + /approvals) / `chatbiz-mcp` (1 个 /healthz proxy)。dev compose 现状是 `web` 段 `depends_on: workflow-engine`(无 health,无 sso / mcp)。web 起来时如果 sso/mcp 没 ready → nginx proxy 502。

**选项**:
- **A (已选)**: `depends_on` 3 个 upstream (`chatbiz-sso` + `workflow-engine` + `chatbiz-mcp`),全 `condition: service_healthy`。web 自身保留 healthcheck (现有 nginx `/health` 端点)
- B: 只 depends_on workflow-engine (现状) — 拒绝理由:`/api/auth/sso/` proxy 启动时 sso 没 ready → 502
- C: depends_on 全部 6 service — 拒绝理由:启动慢且不必要 (`audit-and-isolation` / `credential` / `agent-runtime` 不进 nginx proxy)

**结论**: 选 A。引用 `web/nginx.conf:50-81` 作为权威来源 (强耦合 DNS 名)。`mcp` 在 dev compose 里 service key 是 `chatbiz-mcp`,跟 `docker-compose-dev.yml:179` 一致。

### D4: docker-compose lint 工具不动 baseline 12 service 列表

**Context**: `tools/check-compose-naming.sh` 有 12 个 baseline application service (credential / credential-cron / credential-migrate / audit-and-isolation / audit-and-isolation-migrate / workflow-engine / workflow-engine-migrate / sso / sso-migrate / web + dev compose 内的 `chatbiz-postgres` / `chatbiz-redis` alias extends 段),在 fix-compose 期间**未**触动,记入 baseline 抑制错误。

**选项**:
- **A (已选)**: 本 change 不动 baseline 列表。`chatbiz-web` 段显式 `chatbiz-` 前缀 + 显式 `container_name: chatbiz-web`,lint 直接 PASS,不依赖 baseline
- B: 把 `chatbiz-web` 加进 baseline 列表 — 拒绝理由:web 已 `chatbiz-` 前缀,不需要 baseline 抑制;误加反而让后续扫清时(`compose-naming-migration-full` change)误抑制

**结论**: 选 A。

## Risks / Trade-offs

- **Risk 1 (高)**: 多阶段 Dockerfile 镜像层大。builder 阶段含 `node_modules` (~250MB) + 3 个 `dist/` (~10-30MB each)。镜像总大小约 800MB,跟 Python multi-stage 同级 (`services/sso` image 约 600MB)
  - **Mitigation**: 复用 `web/Dockerfile` 现有 `.dockerignore` (如无,本 change 不补,YAGNI);builder 阶段用 `pnpm install --frozen-lockfile` 装 deps,确保 `pnpm-lock.yaml` 锁定版本可复现;builder 阶段和 runtime 阶段共用 `node:20-alpine` 的 `/usr/local/lib/node_modules` 路径常量 (简单 hard-code,不引 ARG)
- **Risk 2 (中)**: dev compose `web` 段从 dev-only 改为 extends 拉 base 是 breaking change, 其它 dev compose 命令 (`docker compose -f dev.yml up web` 不带 base) 会缺依赖
  - **Mitigation**: openspec `tasks.md` 明确: 任何 dev compose 命令必须 `-f docker-compose.yml -f docker-compose-dev.yml` 双 file;现有 5 个 service 段已是这个 pattern, 跟它对齐
- **Risk 3 (中)**: 启动顺序强变。3 个 nginx upstream 必须 health 才能 web ready → 首次 `up` 时间 +5-10s(等 healthcheck pass,interval 30s,timeout 5s,start_period 20s)
  - **Mitigation**: 把 web 段 `depends_on` 3 upstream 全 `condition: service_healthy` 写在 base 段,dev extends 拉过来不重定义,顺序行为唯一
- **Risk 4 (低)**: `web/portal|canvas|admin` 3 个子应用有 VITE_APP_BASE 环境变量,builder 阶段必须在 build 时把环境变量设进去。容器内 `pnpm build` 时需要 `ENV VITE_APP_BASE=/portal/` 之类
  - **Mitigation**: Dockerfile builder 段显式设 `ARG VITE_APP_BASE` 段,每个子应用 build 传不同 VITE_APP_BASE 值;dev compose (后续扩展) 如需 hot-reload 模式要传 host 路径,本 change 不做

## Migration Plan

按顺序,每步产出可观察:

| # | Step | 产物 |
|---|---|---|
| 1 | 重写 `web/Dockerfile` 为 2 阶段 (builder + runtime) | 新 50-60 行 Dockerfile, 跟其它 service 同 pattern |
| 2 | `docker-compose.yml` 新增 `chatbiz-web:` 段,放 `mcp` 段后 `workflow-engine` 段前 | base compose 自包含 chatbiz-web 段 |
| 3 | `docker-compose-dev.yml` 把 `chatbiz-web` 段改为 `extends:` 拉 base, 重定义 `image: chatbiz/web:dev` + bind mount `../web:/app` + `web-node-modules` 命名 volume | dev compose 用 extends 模式 |
| 4 | `tools/check-compose-naming.sh` 跑 → 必须 PASS (web 已 `chatbiz-` 前缀 + 显式 `container_name`) | exit 0 |
| 5 | `docker compose -f docker-compose.yml config --services` → 列表含 `web` | 列输出 |
| 6 | `docker compose -f docker-compose.yml -f docker-compose-dev.yml build web` → exit 0, 镜像 `chatbiz/web:dev` 存在 | `docker images` 显示 `chatbiz/web:dev` |
| 7 | `docker compose -f docker-compose.yml -f docker-compose-dev.yml up -d web` + 等 30s | `docker ps --filter name=chatbiz-web` 显示 `(healthy)` |
| 8 | 浏览器 `curl http://localhost:5173/health` → 200 | HTTP body `OK` |
| 9 | `curl http://localhost:5173/api/auth/sso/jwks.json` → 200 (sso 起来 + nginx proxy 工作) | JSON body |
| 10 | `curl http://localhost:5173/workflows/healthz` → 200 (workflow-engine 起来 + nginx proxy 工作) | 200 body |
| 11 | openspec `tasks.md` / `specs/` / `plan.md` 写完 + archive + commit + push | 2 commits on main |

**Rollback**: 任一 verification 失败 → `git revert` 已 push 的 commits; base compose 段整段删除 / dev compose 段恢复成 extends-less 版本(老版本)即可。

## Verification (详见 specs/requirements + tasks.md)

| # | 验证项 | 命令 | 期望 |
|---|---|---|---|
| V1 | `web/Dockerfile` 多阶段 | `head -25 web/Dockerfile` | 看到 `FROM node:20-alpine AS builder` + `FROM nginx:1.27-alpine AS runtime` |
| V2 | base compose `chatbiz-web` 段在 | `docker compose -f docker-compose.yml config --services \| grep chatbiz-web` | 输出 `chatbiz-web` |
| V3 | base compose `chatbiz-web` 段格式 | `docker compose -f docker-compose.yml config \| grep -A 20 "chatbiz-web:"` | 看到 `container_name: chatbiz-web` + `build:` + `depends_on:` (3 个 upstream) |
| V4 | dev compose `chatbiz-web` 段用 extends | `grep -A 5 "chatbiz-web:" docker-compose-dev.yml` | 看到 `extends: { file: docker-compose.yml, service: chatbiz-web }` |
| V5 | 命名 lint PASS | `bash tools/check-compose-naming.sh` | exit 0, `OK: 0 error(s), 0 warning(s)` (chatbiz-web 满足规则,baseline 不动) |
| V6 | 容器能 build | `docker compose -f docker-compose.yml -f docker-compose-dev.yml build chatbiz-web` | exit 0, 镜像 `chatbiz/web:dev` 存在 |
| V7 | 容器能起 + healthy | `docker compose -f docker-compose.yml -f docker-compose-dev.yml up -d chatbiz-web` + 等 30s | `docker ps --filter name=chatbiz-web` 显示 `(healthy)` |
| V8 | nginx `/health` 端点 | `curl -fsS http://localhost:5173/health` | exit 0, body `OK` |
| V9 | nginx upstream proxy 工作 (sso) | `curl -fsS http://localhost:5173/api/auth/sso/jwks.json` | exit 0, JSON 响应 (需要 sso 也起) |
| V10 | nginx upstream proxy 工作 (workflow) | `curl -fsS http://localhost:5173/workflows/healthz` | exit 0, 200 (需要 workflow-engine 也起) |

## Open Questions

- (低) 5 个子应用 (`portal` / `canvas` / `admin` / `ui` / `integration-tests`) 是不是都要 build 进 web 镜像? 当前 Dockerfile 只 build 3 个 (`portal` / `canvas` / `admin`)。`ui/` 和 `integration-tests/` 是不是 V1 阶段遗留?
  - **默认采用**: 本 change 沿用现有 Dockerfile 第 15-17 行的 3 个子应用清单 (`COPY portal/dist` + `COPY canvas/dist` + `COPY admin/dist`),不动 `ui/` / `integration-tests/`。如果这 2 个是死代码, 后续开一个 `web-cleanup` change
- (低) `web/node_modules` 是 dev compose bind mount 还是 named volume?
  - **默认采用**: 沿用现有 `volumes:` 段 `web-node-modules: { name: chatbiz-web-node-modules }` 模式, 不动
- (低) dev compose 段 web 段当前无 `healthcheck` 显式重写,是否需要 dev mode disable healthcheck 跟其它 service 一致 (`healthcheck: { disable: true }`)?
  - **默认采用**: dev mode 不动 healthcheck,沿用 base 段配置 (健康检查是好事, dev mode 不需要禁用)
