# ChatBiz Infrastructure

本地与生产环境的 Docker Compose 编排。所有命令假设在 `infrastructure/`
目录下执行。

## 文件清单

| 文件 | 用途 |
|---|---|
| `docker-compose.yml` | 生产/通用编排：postgres + redis + 3 个业务服务（credential / audit-and-isolation / workflow-engine）+ 各服务的 migrate/cron 容器 |
| `docker-compose-dev.yml` | 开发环境 overlay：bind-mount 源码 + `uvicorn --reload` |
| `docker-compose-dev.README.md` | dev overlay 的详细使用文档与 workflow-engine 注意事项 |
| `postgres/init/` | postgres 首次启动的初始化 SQL（业务库 + 索引） |

## 服务总览

| 服务 | 端口 | 镜像 tag（生产） | 镜像 tag（开发） | 镜像 Dockerfile |
|---|---:|---|---|---|
| postgres | 5432 | postgres:16-alpine | （同） | 官方 |
| redis | 6379 | redis:7-alpine | （同） | 官方 |
| credential | 8000 | `<context>` | `chatbiz/credential:dev` | `services/credential/Dockerfile` |
| audit-and-isolation | 8080 | `<context>` | `chatbiz/audit-and-isolation:dev` | `services/audit-and-isolation/Dockerfile` |
| workflow-engine | 8001 | `<context>` | `chatbiz/workflow-engine:dev` | `services/workflow-engine/Dockerfile` |
| credential-migrate / -cron | — | 同上 | — | 同上 |
| audit-and-isolation-migrate | — | 同上 | — | 同上 |
| workflow-engine-migrate | — | 同上 | — | 同上 |

每个服务的 Dockerfile 都是 **多阶段构建**：

```
AS builder  → 装依赖到 /root/.local
AS runtime  → 仅复制 site-packages + 源码
              USER 切换到非 root
              HEALTHCHECK + CMD ["uvicorn", "app.main:app", ...]
```

---

## 🟢 生产环境部署

```bash
cd infrastructure

# 1. 一次性构建镜像
docker compose -f docker-compose.yml build

# 2. 启动全栈（后台）
docker compose -f docker-compose.yml up -d

# 3. 验证
docker compose ps
curl http://localhost:8000/healthz   # credential
curl http://localhost:8080/healthz   # audit-and-isolation
curl http://localhost:8001/healthz   # workflow-engine

# 4. 一次性数据库迁移（如未自动跑）
docker compose run --rm credential-migrate
docker compose run --rm audit-and-isolation-migrate
docker compose run --rm workflow-engine-migrate

# 5. 停止
docker compose down                  # 保留数据卷
docker compose down -v               # 同时清理数据卷
```

### 生产部署特点

- **不使用** `docker-compose-dev.yml`
- 镜像里装好的代码就是部署时跑的代码（build 一次，部署多次）
- 改代码 → `docker compose build <svc>` + `up -d --force-recreate <svc>`
- 改依赖（`pyproject.toml`） → `docker compose build --no-cache <svc>`
- 改 env / ports / healthcheck → `docker compose up -d --force-recreate`
- 数据持久化：`postgres-data` / `redis-data` named volume
- 镜像发布推荐 tag：`chatbiz/<svc>:<semver>`（如 `chatbiz/credential:1.2.3`），推到镜像仓库后由 K8s / Swarm 滚动升级

### K8s 部署参考

```bash
# 本机构建 → 推送到镜像仓库
docker tag <built> chatbiz/credential:1.2.3
docker push chatbiz/credential:1.2.3

# K8s 端
kubectl set image deployment/credential credential=chatbiz/credential:1.2.3
kubectl rollout status deployment/credential
```

完整 K8s manifest（Helm chart / Kustomize）尚未纳入仓库，仅 Compose
编排在 V1.0 阶段使用。

---

## 🟡 开发环境部署

```bash
cd infrastructure

# 1. 一次性构建 dev 镜像（依赖在 builder 阶段装好）
docker compose -f docker-compose.yml -f docker-compose-dev.yml build

# 2. 启动开发栈
docker compose -f docker-compose.yml -f docker-compose-dev.yml up -d

# 3. 验证 reload 工作
docker compose -f docker-compose.yml -f docker-compose-dev.yml logs -f credential
# 在另一个终端修改 services/credential/app/main.py → 日志出现 "Detected change..." + "Restarting..."

# 4. 跑测试（在主机上，不进容器）
cd ../services/credential
PYTHONPATH=. python3 -m pytest tests/ -v --cov=app --cov-fail-under=100

# 5. 停止
docker compose -f docker-compose.yml -f docker-compose-dev.yml down
```

### 开发部署特点

- **同时加载两个 compose 文件**：prod 提供服务定义，dev 覆盖 `command` + `volumes` + `image`
- 源码 `bind-mount` 到 `/app`，编辑主机文件立即可见
- `uvicorn --reload --reload-dir=/app/app` 监听 app 目录下的变更自动重启 worker
- `pycache-<svc>` named volume 挂到 `/app/__pycache__`，让字节码缓存跨容器重启保留
- 改 `pyproject.toml` 新增依赖 → `docker compose -f docker-compose.yml -f docker-compose-dev.yml build <svc>` + `up -d --force-recreate <svc>`
- 改 `Dockerfile` / 系统包 → `docker compose -f docker-compose.yml -f docker-compose-dev.yml build --no-cache <svc>`

### 单独启动某个服务

```bash
# 只起 credential（不依赖其他服务时）
docker compose -f docker-compose.yml -f docker-compose-dev.yml up -d credential

# 实时看某个服务日志
docker compose -f docker-compose.yml -f docker-compose-dev.yml logs -f audit-and-isolation

# 进容器手动 debug
docker compose -f docker-compose.yml -f docker-compose-dev.yml exec credential bash
```

### workflow-engine 注意事项

`workflow-engine` 在 dev overlay 中**没有**重写服务定义（prod 含
`security_opt: [no-new-privileges:true]`，跨文件 list merge 会因
"items at 0 and 1 are equal" 报错）。

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

prod `workflow-engine` 的 `volumes` 仍然存在，所以源码 bind-mount 自动
生效。详见 `docker-compose-dev.README.md`。

---

## 🔄 关键差异表

| 项 | 生产 (`docker-compose.yml`) | 开发 (`+docker-compose-dev.yml`) |
|---|---|---|
| 启动命令 | `uvicorn app.main:app --port=...` | `uvicorn ... --reload --reload-dir=/app/app` |
| 镜像 tag | 默认（`<context>`） | `chatbiz/<svc>:dev`（与生产隔离） |
| 源码 | 镜像 COPY | bind-mount `../services/<svc>` 到 `/app` |
| site-packages | 镜像 baked in | 镜像 baked in（**不**挂载 host venv） |
| `__pycache__` | 容器 ephemeral | named volume `pycache-<svc>` |
| 改 .py 文件 | `build` + `up --force-recreate` | 0.5s 自动 reload |
| 改 `pyproject.toml` | `build --no-cache` | `build --no-cache` |
| 持久化 volume | `postgres-data` `redis-data` | 同 + `pycache-*` |
| 端口 | 8000 / 8080 / 8001 | 同 |

---

## 🧰 常用命令速查

```bash
# 查看所有运行容器
docker compose -f docker-compose.yml -f docker-compose-dev.yml ps

# 看具体服务最近 100 行日志
docker compose -f docker-compose.yml -f docker-compose-dev.yml logs --tail=100 -f audit-and-isolation

# 跑单服务一次性命令（如 alembic 手动迁移、调试脚本）
docker compose -f docker-compose.yml -f docker-compose-dev.yml run --rm credential alembic upgrade head

# 完全重建（清缓存）
docker compose -f docker-compose.yml -f docker-compose-dev.yml down -v
docker compose -f docker-compose.yml -f docker-compose-dev.yml build --no-cache
docker compose -f docker-compose.yml -f docker-compose-dev.yml up -d

# 进入 postgres 容器手动 sql
docker compose -f docker-compose.yml -f docker-compose-dev.yml exec postgres psql -U chatbiz -d credential
docker compose -f docker-compose.yml -f docker-compose-dev.yml exec postgres psql -U chatbiz -d audit_isolation
docker compose -f docker-compose.yml -f docker-compose-dev.yml exec postgres psql -U chatbiz -d workflow_engine
```

## 🔗 相关文档

- [`docker-compose-dev.README.md`](docker-compose-dev.README.md) — dev overlay 详细文档
- `../services/<svc>/README.md` — 各服务自带 README
- `../docs/architecture.md` — 全局架构
- `../CLAUDE.md` — 全局工作约定
