# ChatBiz Infrastructure

本地开发、集成测试与生产环境的 Docker Compose 编排指南。所有命令假设在仓库根目录或 `infrastructure/` 下执行。

## 文件清单

| 文件 | 用途 |
|---|---|
| `docker-compose.yml` | **生产/基础编排**：postgres + redis + 7 个服务容器(credential / audit-and-isolation / mcp / workflow-engine + 各自的 migrate/cron 容器) |
| `docker-compose-dev.yml` | **开发环境 overlay**：bind-mount 源码 + `uvicorn --reload`，与 prod compose 联用 |
| `docker-compose-test.yml` | **集成测试编排**：完全独立，容器名/网络/volume 均隔离，避免影响开发/生产环境 |
| `Makefile` | **测试基础设施入口**：仅 `make test-integration <up|down|test|logs>`，不是构建工具 |
| `postgres/init/` | 生产/开发环境 postgres 首次启动的初始化 SQL |
| `postgres-init-test/` | 测试环境 postgres 初始化 SQL(内容相同，独立目录便于 CI 挂载) |
| `web/Dockerfile` | 统一 Web 前端 nginx 容器(构建方式见下方各环境说明) |

---

## 服务总览与端口分配

| 服务 | 容器内端口 | 主机端口 | 镜像方式 | Dockerfile |
|---|---:|---:|---|---|
| postgres | 5432 | 5432 | 官方 `postgres:16-alpine` | — |
| redis | 6379 | 6379 | 官方 `redis:7-alpine` | — |
| credential | 8000 | 8005 | 多阶段构建 | `services/credential/Dockerfile` |
| audit-and-isolation | 8080 | 8080 | 多阶段构建 | `services/audit-and-isolation/Dockerfile` |
| mcp | 8080 | 8004 | 多阶段构建 | `services/mcp/Dockerfile` |
| workflow-engine | 8001 | 8001 | 多阶段构建 | `services/workflow-engine/Dockerfile` |
| web(nginx) | 80 | 5173 | nginx:1.27-alpine + 本地 build 产物 | `web/Dockerfile` |

每个后端服务的 Dockerfile 都是**多阶段构建**：

```
AS builder  → 装 Python 依赖到 /root/.local
AS runtime  → 仅复制 site-packages + 源码
              USER 切换到非 root
              HEALTHCHECK + CMD ["uvicorn", "app.main:app", ...]
```

---

## 🟢 生产环境部署

**适用场景**：正式部署、预发布验证、给非开发者演示。

**工作流程**：

```bash
cd /Users/paulwang/work/ChatBiz/infrastructure

# 1. 构建前端 dist(必须在主机上先执行)
cd ../web/canvas && pnpm exec vite build && cd ../admin && pnpm exec vite build

# 2. 构建所有后端服务镜像
cd ../infrastructure
docker compose -f docker-compose.yml build

# 3. 构建 Web 前端镜像(从 web/Dockerfile)
docker build -t chatbiz-web:latest -f ../web/Dockerfile ../web

# 4. 启动全栈(后台)
docker compose -f docker-compose.yml up -d
docker run -d --rm --name chatbiz-web --network chatbiz-net -p 5173:80 chatbiz-web:latest

# 5. 验证健康检查(等待 30s 让服务就绪)
docker compose -f docker-compose.yml ps
curl http://localhost:8005/healthz   # credential
curl http://localhost:8080/healthz   # audit-and-isolation
curl http://localhost:8004/healthz   # MCP
curl http://localhost:8001/healthz   # workflow-engine
curl http://localhost:5173/healthz   # Web 前端

# 6. 打开浏览器
open http://localhost:5173/canvas/   # 画布前端
open http://localhost:5173/admin/    # 管理后台

# 7. 一次性数据库迁移(如未在启动时自动完成)
docker compose -f docker-compose.yml run --rm credential-migrate
docker compose -f docker-compose.yml run --rm audit-and-isolation-migrate
docker compose -f docker-compose.yml run --rm workflow-engine-migrate

# 8. 停止
docker stop chatbiz-web
docker compose -f docker-compose.yml down       # 保留数据卷
docker compose -f docker-compose.yml down -v    # 同时清理数据卷
```

> **注意**：`docker-compose.yml` 目前未包含 `web` 服务定义。Web 前端通过 `web/Dockerfile` 独立构建，手动 `docker run` 挂进同一 network。后续 Web 容器可编入 compose。

**生产部署特点**：

- **不使用** `docker-compose-dev.yml`
- 镜像里装好的代码就是部署时跑的代码(build 一次，部署多次)
- 改代码 → `docker compose -f docker-compose.yml build <svc>` + `up -d --force-recreate <svc>`
- 改依赖(`pyproject.toml`)→ `docker compose -f docker-compose.yml build --no-cache <svc>`
- 改 env / ports / healthcheck → `docker compose -f docker-compose.yml up -d --force-recreate`
- 数据持久化：`postgres-data` / `redis-data` named volumes
- 镜像发布推荐 tag：`chatbiz/<svc>:<semver>`(如 `chatbiz/credential:1.2.3`)，推到镜像仓库后由 K8s / Swarm 滚动升级

**K8s 部署参考**：

```bash
# 本机构建 → 推送到镜像仓库
docker tag <built> chatbiz/credential:1.2.3
docker push chatbiz/credential:1.2.3

# K8s 端
kubectl set image deployment/credential credential=chatbiz/credential:1.2.3
kubectl rollout status deployment/credential
```

完整 K8s manifest(Helm chart / Kustomize)尚未纳入仓库，仅 Compose 编排在 V1.0 阶段使用。

---

## 🟡 开发环境部署

**适用场景**：日常写代码、改一行看一行效果、debug 后端逻辑。

### 核心原理

开发环境通过**两个 compose 文件叠加**实现源码实时热加载：

```bash
docker compose -f docker-compose.yml -f docker-compose-dev.yml <命令>
#                        ^^^^^^^^              ^^^^^^^^^^^^^^^
#              基础服务定义（端口/env/依赖）        overlay（覆盖 command + volumes + image）
```

- `docker-compose.yml` 提供完整的服务拓扑(port / env / depends_on / healthcheck)
- `docker-compose-dev.yml` 覆盖每条服务的 `command`(加 `--reload`)、`volumes`(bind-mount 源码)、`image`(打 `:dev` tag 与生产隔离)

### 工作流程

```bash
cd /Users/paulwang/work/ChatBiz/infrastructure

# 1. 构建前端 dist
cd ../web/canvas && pnpm exec vite build && cd ../admin && pnpm exec vite build && cd ../../infrastructure

# 2. 一次性构建 dev 镜像(依赖在 builder 阶段装好，后续 reload 不改这里)
docker compose -f docker-compose.yml -f docker-compose-dev.yml build

# 3. 启动开发栈(后台)
docker compose -f docker-compose.yml -f docker-compose-dev.yml up -d

# 4. 启动 Web 前端容器
cd .. && docker build -t chatbiz-web:dev -f web/Dockerfile web
docker run -d --rm --name chatbiz-web --network chatbiz-net -p 5173:80 chatbiz-web:dev

# 5. 验证 reload 工作
docker compose -f docker-compose.yml -f docker-compose-dev.yml logs -f credential
# 在另一个终端修改 services/credential/app/main.py → 日志出现 "Detected change..." + "Restarting..."

# 6. 跑测试(在主机上，不进容器)
cd ../services/credential
PYTHONPATH=. python3 -m pytest tests/ -v --cov=app --cov-fail-under=100

# 7. 停止
cd ../infrastructure
docker compose -f docker-compose.yml -f docker-compose-dev.yml down
docker stop chatbiz-web
```

### 开发部署特点

| 项 | 行为 |
|---|---|
| 源码 | bind-mount `../services/<svc>` 到容器内 `/app`，编辑主机文件立即可见 |
| site-packages | 镜像 baked in(**不**挂载 host venv，避免平台差异) |
| 热加载 | `uvicorn --reload --reload-dir=/app/app` 监听 app 目录变更自动重启 worker |
| `__pycache__` | named volume `pycache-<svc>` 挂到 `/app/__pycache__`，字节码缓存跨容器重启保留 |
| 改 .py 文件 | **0.5s 自动 reload**，无需重建 |
| 改 `pyproject.toml` 新增依赖 | `docker compose -f docker-compose.yml -f docker-compose-dev.yml build <svc>` + `up -d --force-recreate <svc>` |
| 改 Dockerfile / 系统包 | `docker compose -f docker-compose.yml -f docker-compose-dev.yml build --no-cache <svc>` |

### 单独启动某个服务

```bash
# 只起 credential(不依赖其他时)
docker compose -f docker-compose.yml -f docker-compose-dev.yml up -d credential

# 实时看某个服务日志
docker compose -f docker-compose.yml -f docker-compose-dev.yml logs -f audit-and-isolation

# 进容器手动 debug
docker compose -f docker-compose.yml -f docker-compose-dev.yml exec credential bash
```

### workflow-engine 注意事项

`workflow-engine` 在 dev overlay 中**没有**重写服务定义。原因是 prod compose 的 `security_opt: [no-new-privileges:true]` 与 overlay 的 `security_opt` 跨文件 list merge 会因"items at 0 and 1 are equal"报错。

要使用 `--reload` 模式，临时用 `run` 覆盖启动：

```bash
docker compose \
    -f docker-compose.yml \
    -f docker-compose-dev.yml \
    run --rm -p 8001:8001 workflow-engine \
    uvicorn app.main:app \
    --host=0.0.0.0 --port=8001 \
    --reload --reload-dir=/app/app
```

prod `workflow-engine` 的 `volumes`(含 Docker socket)仍生效，源码 bind-mount 也自动生效。

---

## 🔵 集成测试环境部署

**适用场景**：CI 流水线、PR 验证、本地跑 E2E(Playwright)测试。

### 设计原则

- **完全隔离**：`docker-compose-test.yml` 使用独立的 project name(`chatbiz-test`)、network(`chatbiz-test-net`)、容器名(`chatbiz-test-*`前缀)、数据卷(`chatbiz-test-*`)。
- **不影响开发/生产环境**：两个 compose stack 可以同时运行(前提是端口 5173 不冲突)。
- **一次性、短生命周期**：所有服务 `restart: "no"`，healthcheck 设置更密集的 retries + `start_period`。
- **端口最小暴露**：仅 web 容器的 `5173:80` 暴露到主机，避免与开发环境端口冲突。

### 前置要求

- 主机上安装了 `pnpm`(用于构建前端 dist)
- Docker Desktop 或 Docker Engine 正在运行

### 工作流程

```bash
cd /Users/paulwang/work/ChatBiz

# 1. 启动测试栈(自动构建前端 dist + 等待所有服务 healthy)
make test-integration up

# 2. 跑集成测试
make test-integration test

# 3. 看日志(调试失败时)
make test-integration logs

# 4. 清理(删除容器 + 数据卷)
make test-integration down
```

`make test-integration up` 等价于手动执行：

```bash
# 1. 本地构建前端(dist 产物)
cd web/canvas && pnpm exec vite build
cd web/admin && pnpm exec vite build

# 2. 启动测试栈
cd /Users/paulwang/work/ChatBiz
docker compose -p chatbiz-test -f infrastructure/docker-compose-test.yml up --wait --quiet-pull
```

`make test-integration down` 等价于：

```bash
docker compose -p chatbiz-test -f infrastructure/docker-compose-test.yml down --volumes
```

> ⚠️ `make test-integration up` 会检测 `chatbiz` 生产 compose 是否在运行；如果生产栈占用端口，会报错并提示先 `docker compose -p chatbiz down`。

### 测试环境的 Web 前端

与生产/开发环境不同，测试环境**不**通过 `web/Dockerfile` 构建。而是：

1. 主机上 `vite build` 产出 `web/canvas/dist/` 和 `web/admin/dist/`
2. 测试 compose 直接用 `nginx:1.27-alpine` 镜像 + volume mount 把 dist 挂进 `/usr/share/nginx/html/`

这样避免了"在 Docker 里构建前端"的复杂性，测试启动更快。

### 服务依赖拓扑(测试环境)

```
postgres ─┬─ credential-migrate ─► credential ─► audit-and-isolation-migrate ─► audit-and-isolation ─► mcp
          ├─ workflow-engine-migrate ─► workflow-engine ──────────────────────────────────────────────► web
          └─ (audit_isolation / workflow_engine 数据库通过 init SQL 创建)
redis ──── credential, audit-and-isolation, workflow-engine
```

---

## 🔄 三环境关键差异表

| 项 | 🟢 生产 | 🟡 开发 | 🔵 集成测试 |
|---|---|---|---|
| **Compose 文件** | `docker-compose.yml` | `docker-compose.yml` + `docker-compose-dev.yml` | `docker-compose-test.yml` |
| **Project name** | `chatbiz` | `chatbiz` | `chatbiz-test` |
| **Network** | `chatbiz-net` | `chatbiz-net` | `chatbiz-test-net` |
| **容器名前缀** | `chatbiz-` | `chatbiz-` | `chatbiz-test-` |
| **Volume 前缀** | `chatbiz-` | `chatbiz-` + `chatbiz-pycache-*` | `chatbiz-test-` |
| **启动命令** | `uvicorn app.main:app --port=...` | `uvicorn ... --reload --reload-dir=/app/app` | `uvicorn app.main:app --port=...` |
| **镜像 tag** | 默认(`<context>`) | `chatbiz/<svc>:dev` | 默认(`<context>`) |
| **源码** | 镜像 COPY | bind-mount `../services/<svc>` 到 `/app` | 镜像 COPY |
| **热加载** | ❌ | ✅ `--reload` | ❌ |
| **`__pycache__`** | 容器 ephemeral | named volume `pycache-<svc>` | 容器 ephemeral |
| **改 .py 文件** | `build` + `up --force-recreate` | 0.5s 自动 reload | `build` + `up --force-recreate` |
| **改 `pyproject.toml`** | `build --no-cache` | `build --no-cache` | `build --no-cache` |
| **restart 策略** | `unless-stopped` | `unless-stopped` | `"no"`(一次性) |
| **Web 前端提供方式** | `web/Dockerfile` build → nginx 容器 | 同生产 | host `vite build` → volume mount `dist/` |
| **主机端口暴露** | 5432 / 6379 / 8005 / 8080 / 8004 / 8001 / 5173 | 同生产 | **仅 5173** |
| **数据持久化** | ✅ named volumes | ✅ named volumes | ❌ `down --volumes` 后丢失 |
| **Healthcheck retries/interval** | 3 retries / 30s interval | 同生产 | 10 retries / 5s interval(更激进) |
| **入口命令** | `docker compose -f docker-compose.yml up -d` | `docker compose -f docker-compose.yml -f docker-compose-dev.yml up -d` | `make test-integration up` |
| **清理命令** | `docker compose -f docker-compose.yml down [-v]` | `docker compose -f docker-compose.yml -f docker-compose-dev.yml down` | `make test-integration down` |

---

## 🧰 常用命令速查

### 查看状态

```bash
# 查看所有运行容器
docker compose -f docker-compose.yml -f docker-compose-dev.yml ps

# 查看测试栈容器
docker compose -p chatbiz-test -f infrastructure/docker-compose-test.yml ps

# 看具体服务最近 100 行日志
docker compose -f docker-compose.yml -f docker-compose-dev.yml logs --tail=100 -f audit-and-isolation

# 看测试栈所有日志
make test-integration logs
```

### 重建与清理

```bash
# 完全重建开发环境(清缓存)
docker compose -f docker-compose.yml -f docker-compose-dev.yml down -v
docker compose -f docker-compose.yml -f docker-compose-dev.yml build --no-cache
docker compose -f docker-compose.yml -f docker-compose-dev.yml up -d

# 重建单个服务
docker compose -f docker-compose.yml -f docker-compose-dev.yml build credential
docker compose -f docker-compose.yml -f docker-compose-dev.yml up -d --force-recreate credential

# 清理测试环境
make test-integration down
```

### 数据库

```bash
# 进入 postgres 容器手动 sql
docker compose -f docker-compose.yml -f docker-compose-dev.yml exec postgres psql -U chatbiz -d credential
docker compose -f docker-compose.yml -f docker-compose-dev.yml exec postgres psql -U chatbiz -d audit_isolation
docker compose -f docker-compose.yml -f docker-compose-dev.yml exec postgres psql -U chatbiz -d workflow_engine

# 手动跑迁移
docker compose -f docker-compose.yml -f docker-compose-dev.yml run --rm credential-migrate
docker compose -f docker-compose.yml -f docker-compose-dev.yml run --rm audit-and-isolation-migrate
docker compose -f docker-compose.yml -f docker-compose-dev.yml run --rm workflow-engine-migrate
```

### 容器内调试

```bash
# 进容器 bash
docker compose -f docker-compose.yml -f docker-compose-dev.yml exec credential bash

# 进测试栈容器
docker compose -p chatbiz-test -f infrastructure/docker-compose-test.yml exec credential bash
```

### 前端重建

```bash
# 开发/生产环境：重新 build dist + 重建 web 镜像
cd web/canvas && pnpm exec vite build && cd ../admin && pnpm exec vite build
cd ../infrastructure
docker build -t chatbiz-web:dev -f ../web/Dockerfile ../web
docker stop chatbiz-web && docker rm chatbiz-web
docker run -d --name chatbiz-web --network chatbiz-net -p 5173:80 chatbiz-web:dev
```

---

## 🔗 相关文档

- `docker-compose.yml` — 生产/基础编排(service 定义 + 端口 + env + healthcheck)
- `docker-compose-dev.yml` — 开发 overlay(command/volumes/image 覆盖)
- `docker-compose-test.yml` — 集成测试编排(完全独立)
- `Makefile` — 测试基础设施入口
- `../web/Dockerfile` — 统一 Web 前端 nginx 镜像
- `../services/<svc>/README.md` — 各服务自带 README
- `../docs/architecture.md` — 全局架构
- `../CLAUDE.md` — 全局工作约定
