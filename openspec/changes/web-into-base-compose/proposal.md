# web-into-base-compose — Proposal

## Why

`chatbiz-web` 是 `web/` 目录下**所有前端功能** (portal / canvas / admin) 的统一入口容器,每个前端 SPA 通过 `web/nginx.conf` 里的 `proxy_pass` 跟 `services/` 下对应后端 (chatbiz-sso / workflow-engine / chatbiz-mcp) 对接。当前**只在** `infrastructure/docker-compose-dev.yml:174-184` 定义,跟 base compose 的 5 个 Python service 段格式不一致(无 `extends:` 拉 base、service key 是 `web` 而不是 `chatbiz-web`、没有 `image` 字段)。

`openspec/config.yaml` apply-rule 第 1 条明文要求"**服务容器在 `docker-compose.yml` 注册;格式与 credential/audit-and-isolation/workflow-engine/mcp 保持一致**"。`chatbiz-web` 是服务容器,目前未在 base 注册 — 违反 apply-rule。

不改会发生:base compose 命令 (`docker compose -f docker-compose.yml up -d`) 起不到 web;base compose + dev compose 拼起来时 web 段缺 `image: chatbiz/web:dev` 不能跟其它 service dev 工作流对齐 (`chatbiz/credential:dev` / `chatbiz/audit-and-isolation:dev` 模式);新开发者 onboarding 时学不到 web 段是 base 段(以为 dev-only,误删)。

上游三件源:本 change 不触 `docs/architecture.md` (无新增架构层)、不触 `docs/prd.md` (无产品需求变更),只触 `docker-compose*.yml` + `web/Dockerfile` —— **不**与 12 个 eng-review 决策任一条冲突。

## What Changes

- **修改** `web/Dockerfile`:从 1 阶段 `nginx:1.27-alpine AS runtime` 改为 2 阶段 (`node:20-alpine AS builder` + `nginx:1.27-alpine AS runtime`)。builder 阶段在容器内 `pnpm install` + 跑 3 个 `vite build` (portal / canvas / admin);runtime 阶段只拷 `dist/` + `nginx.conf`,沿用现有 `HEALTHCHECK` + `EXPOSE 80`。
- **修改** `infrastructure/docker-compose.yml`:在 `mcp` 段后、`workflow-engine` 段前新增 `chatbiz-web:` 段,跟其它 service 段同格式 (`container_name: chatbiz-web` + 显式 `build` 段 + `image: chatbiz/web:dev` + `ports: ["5173:80"]` + `depends_on` 含 3 个 nginx upstream `condition: service_healthy` + `healthcheck`)。`chatbiz-web` service key 满足 `openspec/config.yaml` apply-rule + `CLAUDE.md` 强制约定 "新加 service 必须 `chatbiz-` 前缀"。
- **修改** `infrastructure/docker-compose-dev.yml`:把 `chatbiz-web` 段改为 `extends:` 拉 base `chatbiz-web` 段,重定义 `image: chatbiz/web:dev` + 显式 `container_name: chatbiz-web` (dev namespace 独立 lint 可见) + bind mount `../web:/app` + `web-node-modules` 命名 volume (沿用现有第 257-258 行)。
- **不** 改 `web/nginx.conf` 内部路径或代理规则 (现有 6 个 `proxy_pass` 段保持不变)。
- **不** 改 `web/` 目录下 5 个子应用 (`portal` / `canvas` / `admin` / `ui` / `integration-tests`) 的源代码或构建脚本。
- **不** 改 `services/<x>/pyproject.toml` 任何字段(本 change 不动 Python 后端)。
- **不** 写 K8s / Helm / 生产部署(prod 由后续 change 负责)。
- **不** 改 `tools/check-compose-naming.sh` baseline 列表 (12 个不动,避免误抑制)。新 `chatbiz-web` 段必须直接满足规则 1 (`chatbiz-` 前缀) + 规则 2 (显式 `container_name`)。

## Capabilities

### New Capabilities

无。chatbiz-web 容器化是**已有**容器化模式的迁移,不是新 capability。

### Modified Capabilities

- `web-frontend-containerization` (从 dev-only 单段迁到 base 段 + dev extends 重定义):**前端范围** = 容器化位置/格式变更,前端源代码不变;**后端范围** = 0 (本 change 不动任何后端 service);**是否豁免前端** = 否(原 `web/portal/canvas/admin` 3 个 SPA 的源代码不动,只是打包方式从"预 build 拷 dist"变成"容器内 pnpm build")。

## Impact

- **新开发者 onboarding**:1 步 `docker compose -f docker-compose.yml -f docker-compose-dev.yml up -d` 即可起整个 stack(含 web);现状要 2 步(起 dev compose + 手起 web 镜像)。
- **CI**:本 change 不动 `.github/workflows/ci-cov.yml` (ci-cov 是 Python 后端 cov gate,跟 web 无关);不引新 workflow。
- **生产部署**:本 change 不写 K8s/Helm。生产期仍按现状:K8s 单独管理 `chatbiz-web` deployment,镜像 tag 由 CI 推到 registry。base compose 段新增的 `web` 段给 `docker compose` 单机开发用,prod 入口仍由 K8s 控。
- **测试影响**:无 Python 单元 / 集成测试改动。`web/` 子应用 e2e (Playwright) 仍按现状跑(`docker compose -f docker-compose.yml -f docker-compose-dev.yml up` 起全 stack 后 Playwright 跑 `web/portal|canvas|admin`)。
- **被消费的下游**:3 个 nginx upstream `chatbiz-sso` / `workflow-engine` / `chatbiz-mcp` 必须 `healthcheck: service_healthy` 起来后 web 才能 ready(原现状只 `depends_on: workflow-engine`,改后 3 service 全 health gate)。这影响:启动顺序强、首次 `up` 时间可能 +5-10s(等 healthcheck pass)。

## Non-goals

1. **不**改 nginx.conf 的 6 个 `proxy_pass` 段
2. **不**改 `web/portal|canvas|admin` 任何源代码
3. **不**写 K8s / Helm / 生产部署脚本
4. **不**改 `tools/check-compose-naming.sh` 的 baseline 12 service 列表
5. **不**改 `services/<x>/pyproject.toml` 任何字段
6. **不**改 `.github/workflows/ci-cov.yml` matrix (跟 web 无关)
7. **不**改 `CLAUDE.md` 端口表(5173 已在"web 统一入口端口, 不进后端 service 端口表"段)
8. **不**写 web e2e 测试(playwright 已有,本 change 不动)
