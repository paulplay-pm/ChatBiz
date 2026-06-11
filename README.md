# ChatBiz Agent Platform

<p align="center">
  <img src="assets/logo.png" alt="ChatBiz Logo" width="240" />
</p>

> **企业级 AI Agent 智能体平台** — 让企业中的每一位员工都能轻松构建和部署 AI 智能体,实现业务流程的智能化升级。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status: MVP](https://img.shields.io/badge/Status-MVP-blueviolet)](#roadmap)
[![Coverage: workflow-engine 100%](https://img.shields.io/badge/Coverage-100%25-brightgreen)](#quality)

---

## 目录

- [项目概述](#项目概述)
- [功能介绍](#功能介绍)
- [架构介绍](#架构介绍)
  - [整体架构](#整体架构)
  - [核心设计决策](#核心设计决策)
  - [服务清单](#服务清单)
  - [技术栈](#技术栈)
- [运行环境搭建](#运行环境搭建)
  - [前置依赖](#前置依赖)
  - [本地开发(单服务)](#本地开发单服务)
  - [本地开发(全栈 docker-compose)](#本地开发全栈-docker-compose)
  - [生产环境(K8s)](#生产环境k8s)
- [研发环境搭建](#研发环境搭建)
  - [代码规范](#代码规范)
  - [测试与覆盖率](#测试与覆盖率)
  - [OpenSpec 变更工作流](#openspec-变更工作流)
  - [CI / 验证脚本](#ci--验证脚本)
- [Docker 运行方案](#docker-运行方案)
  - [镜像构建](#镜像构建)
  - [Compose 编排](#compose-编排)
  - [健康检查与日志](#健康检查与日志)
- [文档与参考](#文档与参考)
- [Roadmap](#roadmap)
- [License](#license)

---

## 项目概述

**ChatBiz Agent Platform** 是一款面向企业的可视化 AI Agent 编排平台。它汲取 DeerFlow(Lead/Sub-Agent)、Dify(可视化画布)、n8n(低代码)、LangGraph(图计算运行时)等主流平台的优点,采用**混合编排模式**(可视化拖拽 + 代码化)与**6 层企业级架构**,让业务人员与开发者都能高效构建和部署智能体应用。

### 核心价值主张

| 价值 | 说明 |
|------|------|
| **低门槛编排** | 可视化拖拽 + 代码化编排,兼顾业务人员与 AI 开发者 |
| **企业级安全** | 数据隔离网关(egress 强制点)、AES-256-GCM 凭证加密、审计日志、Docker 沙箱执行 |
| **灵活扩展** | MCP 标准化协议 + 自定义节点,14 类节点覆盖常见业务场景 |
| **全链路可观测** | Node Event 审计、SSE 实时事件流、4 层记忆(工作 / 短期 / 长期 / 语义) |
| **跨服务 trace-id 关联** | 所有 LLM 调用透传 `X-Trace-Id`,审计日志可关联 |

### 目标用户与典型场景

- **业务人员** — 用可视化画布搭智能客服、文档问答,无需编程
- **AI 开发者** — 用代码化编排 + 自定义节点调优模型与流程
- **平台管理员** — 用户/权限/资源/审计配置
- **企业开发者** — API 集成、插件开发、二次开发

**典型场景**:智能客服(paul 财务月报)、数据分析助手(月度报告自动生成)、合同审核(RAG + LLM + 人工审批)。

---

## 功能介绍

### 6 大核心模块

| 模块 | 关键能力 |
|------|---------|
| **工作流** | 14 类节点(start / end / variable_assign / condition / llm / knowledge / agent / http / code / approval / loop / iterate / subflow / extract),可视化画布 → JSON → LangGraph 编译执行 |
| **Agent** | Lead Agent / Sub Agent 委派,工具调用(MCP + 自定义),四层记忆,断点续传 |
| **知识库** | 文档上传 → 向量化(Milvus) → RAG 检索 → LLM 增强回答 |
| **插件** | MCP server 协议 (filesystem / fetch / postgres) + 自定义节点注册 |
| **模型** | 多 LLM 适配(OpenAI / Claude / DeepSeek / Qwen / ERNIE),模型路由,PII 脱敏 |
| **系统** | 用户/权限/审计/通知(企微/邮件/站内信)/监控 |

### 14 类工作流节点(eng-review 锁定)

| 节点 | 作用 | 关键依赖 |
|------|------|---------|
| `start` / `end` | 流程入口 / 出口 | — |
| `variable_assign` | 变量赋值(Jinja2 模板) | jinja2 |
| `condition` | 条件分支 | jinja2 |
| `llm` | LLM 调用(经 audit-and-isolation 网关) | langchain-openai |
| `knowledge` | 知识库 RAG 检索 | knowledge-base |
| `agent` | 委派 agent-runtime 执行 | agent-runtime |
| `http` | 通用 HTTP 请求(含重试 + Jinja2) | httpx |
| `code` | 用户代码执行(Docker 沙箱) | docker SDK |
| `approval` | 人工审批(企微/邮件/站内信) | — |
| `loop` | 循环节点 | — |
| `iterate` | 数组迭代 | — |
| `subflow` | 子工作流调用 | — |
| `extract` | LLM 结构化抽取 | llm |

### 关键业务能力

- ✅ **数据隔离网关** — 所有 LLM 调用经 audit-and-isolation,egress 强制点,2 实例 HA + PII 脱敏
- ✅ **凭证加密保险柜** — AES-256-GCM 双层密钥包装,审计零明文
- ✅ **人工审批中断续接** — LangGraph PostgreSQL Checkpointer,审批 24h 超时自动标 fail
- ✅ **工作流版本化** — `PUT /workflows/:id` 创新版本,旧版本保留用于回滚
- ✅ **SSE 实时事件流** — Node Event 增量推送,前端 EventSource 实时显示执行进度

---

## 架构介绍

### 整体架构

ChatBiz 采用 **6 层企业级架构**,详情见 [`docs/architecture.md`](docs/architecture.md) §4.1:

```
┌─────────────────────────────────────────────────────────────────────┐
│ ① 接入层 (Access Layer)                                            │
│   Web App (React) | Mobile (Flutter) | 钉钉 | 企业微信 | 飞书        │
├─────────────────────────────────────────────────────────────────────┤
│ ② 网关层 (Gateway Layer)                                            │
│   API Gateway (Kong/Nginx) | Auth Center (OAuth/SSO)               │
│   Rate Limit & Quota | Audit Log                                    │
├─────────────────────────────────────────────────────────────────────┤
│ ③ 编排引擎层 (Orchestration Engine)                                 │
│   ┌──────────────────────────────────────────────────────────┐    │
│   │ ChatBiz Workflow Engine (本仓库 workflow-engine)            │    │
│   │  14 类节点 / 可视化画布 → JSON → LangGraph 编译执行         │    │
│   └──────────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────────┤
│ ④ Agent 运行时层 (Agent Runtime)                                    │
│   Agent Core (LangGraph) | Memory Manager (4 层)                   │
│   Tool Registry (MCP+自定义) | RAG Engine | Checkpoint              │
│   Sandbox (Docker) | Middleware Chain | Skill Loader               │
├─────────────────────────────────────────────────────────────────────┤
│ ⑤ 模型与集成层 (Model & Integration)                                │
│   OpenAI / Claude / DeepSeek / 文心 / 通义                          │
│   向量 DB (Milvus/Weaviate) | 企业 API | MySQL/PG | MinIO | ES     │
├─────────────────────────────────────────────────────────────────────┤
│ ⑥ 基础设施层 (Infrastructure)                                       │
│   K8s | PostgreSQL 16 | Redis 7 | Kafka | MinIO                    │
│   Prometheus | Grafana | ELK | Jaeger                              │
└─────────────────────────────────────────────────────────────────────┘
```

### 数据隔离网关(eng-review Arch #1 — P0)

```
调用方 (workflow-engine / agent-runtime)
        ↓ OpenAI-compatible API
chatbiz-audit-and-isolation :8080
  ├─ 鉴权 (service token, 调 credential service)
  ├─ PII Detector (6 类正则) → Redactor → Redis map (TTL 30min)
  ├─ Routing (按 X-Model-Kind 决定 PII 跳过)
  ├─ Upstream Caller (httpx async)
  └─ Audit Writer (outbox 异步落 PG,metadata-only)
        ↓
上游 LLM (public: Qwen/DeepSeek | private: 内部 vLLM)
```

### 核心设计决策(eng-review 2026-06-10,12 finding 全部 approved)

| # | 决策 | 理由 |
|---|------|------|
| 1 | **数据隔离网关 = egress 强制点** | 单点可控,PII 集中处理,2 实例 HA |
| 2 | **14 节点共享 Node Contract (Pydantic)** | 一份 dataclass 生成画布 UI / StateGraph 节点 / I/O schema / 验证器 4 份产品 |
| 3 | **四层记忆** | 工作 / 短期 Redis / 长期 PG / 语义 Milvus,覆盖复杂场景 |
| 4 | **Workflow + Chatflow 同 StateGraph** | Chatflow 是 Workflow 的 loop-back 变体,代码统一 |
| 5 | **MVP 包含 MCP 集成** | filesystem / fetch / postgres 三个核心 server |
| 6 | **人工审批 + PostgreSQL Checkpointer** | LangGraph interrupt_before + 24h 超时 |
| 7 | **代码生成 Node Contract** | 1 份 Pydantic schema → 4 份产品 |
| 8 | **状态双层**(PG source-of-truth + Redis 实时) | 状态双写,失败可恢复 |
| 9 | **错误处理 4 边界** | canvas / runtime / user / security |
| 10 | **3 层测试 + LLM eval** | pytest 单元 + 集成 + Playwright E2E + 50 paul 财务月报 eval |
| 11 | **4 critical path 100% 覆盖** | paul 财务月报 / PII 拦截 / 人工审批 / 插件降级 |
| 12 | **5 个存储量预估** | audit 780GB/3mo / state 500MB / Milvus 100GB / canvas 500MB / MinIO 10TB/year |

### 服务清单(本仓库 `services/`)

| 服务 | 端口 | 状态 | 说明 |
|------|------|------|------|
| **workflow-engine** | 8001 | ✅ MVP | 工作流编译/执行引擎,14 节点,LangGraph 运行时 |
| **audit-and-isolation** | 8080 | ✅ MVP | LLM 网关,PII 脱敏 + 审计 |
| **credential** | 8000 | ✅ MVP | 凭证保险柜,AES-256-GCM 双层密钥 |
| credential-migrate | — | ✅ | Alembic 一次性升级容器 |
| credential-cron | — | ✅ | 凭证清理 / 告警 定时任务 |
| workflow-engine-migrate | — | ✅ | 工作流引擎迁移容器 |
| **postgres** | 5432 | ✅ 共享 | 共享主数据库 |
| **redis** | 6379 | ✅ 共享 | 共享缓存/短期记忆 |

🚧 规划中(见 [Roadmap](#roadmap)):`agent-runtime` / `knowledge-base` / `canvas-*` 前端 / `api-gateway`。

### 技术栈

| 层级 | 选型 | 说明 |
|------|------|------|
| **后端框架** | Python 3.12 + FastAPI 0.115 | 高性能异步,OpenAPI 自动生成 |
| **Agent 运行时** | LangGraph 0.2 + LangChain 0.3 | 图计算 + 原生 Checkpoint 持久化 |
| **工作流引擎** | 自研(基于 LangGraph 编译) | 14 类 Node Contract,画布 JSON → StateGraph |
| **数据库** | PostgreSQL 16 + asyncpg + SQLAlchemy 2.0 | 主存储 + JSONB |
| **缓存** | Redis 7 + fakeredis(test) | 短期记忆 / 画布实时状态 / 任务队列 |
| **向量数据库** | Milvus(规划) | RAG 检索(1B chunks 预估) |
| **对象存储** | MinIO(规划) | 知识库文档 / 附件 |
| **Pydantic** | 2.9 | Node Contract 单一数据源 |
| **JWT** | PyJWT 2.8 | 内部 IAM token(签名 MVP 暂不验) |
| **MCP** | (规划) | filesystem / fetch / postgres 三个核心 server |
| **前端** | React 18 + TypeScript 5 + Ant Design(规划) | 画布:React Flow / AntV X6 |
| **容器编排** | Docker Compose(dev) → K8s(prod) | Helm chart(规划) |
| **监控** | Prometheus + Grafana(规划) | 指标 + 链路追踪 |

完整设计见 [`docs/architecture.md`](docs/architecture.md) §4.4。

---

## 运行环境搭建

### 前置依赖

| 工具 | 版本 | 用途 |
|------|------|------|
| **Python** | 3.12+ | 后端运行时 |
| **Node.js** | 20+ (规划,前端开发时) | 前端构建 |
| **Docker** | 24+ | 容器化运行 |
| **Docker Compose** | v2 (plugin) | 本地全栈编排 |
| **Git** | 2.30+ | 源码管理 |
| **Conda / uv** | 任意一种 | Python 依赖管理(本仓库用 conda) |
| **psql** | 16 | (可选) 直连数据库排查 |

### 本地开发(单服务)

适合只跑一个服务(workflow-engine / audit-and-isolation / credential),不需要完整依赖。

#### 1. 克隆代码

```bash
git clone https://github.com/your-org/ChatBiz.git
cd ChatBiz
```

#### 2. 启动共享基础设施(只需一次)

```bash
# 启动 postgres + redis(其他服务共享)
cd infrastructure
docker compose up -d postgres redis
cd ..
```

> `postgres` 容器首次启动时会自动执行 `infrastructure/postgres/init/01-credential-schema.sql` 初始化 `credential` 数据库。其他业务库(`workflow_engine` / `audit`)由对应服务的 Alembic 迁移创建。

#### 3. 启动单个服务

以 `workflow-engine` 为例:

```bash
cd services/workflow-engine
conda create -n chatbiz python=3.12 -y
conda activate chatbiz
pip install -e ".[dev]"

cp .env.example .env
# 编辑 .env 至少确认:
#   DATABASE_URL=postgresql+asyncpg://chatbiz:chatbiz@localhost:5432/workflow_engine
#   REDIS_URL=redis://localhost:6379/0
#   AUDIT_ISOLATION_URL=http://localhost:8080
#   CREDENTIAL_SERVICE_URL=http://localhost:8000
#   WORKFLOW_ENGINE_SERVICE_TOKEN=dev-token

# 跑迁移(创建表)
alembic upgrade head

# 启动(开发模式:reload)
uvicorn app.main:app --reload --port 8001
```

健康检查:

```bash
curl http://localhost:8001/healthz
# {"status":"ok"}

curl http://localhost:8001/readyz
# {"status":"ready", "checks": {...}}
```

#### 4. 类似地启动其他服务

```bash
# 终端 2
cd services/audit-and-isolation
conda activate chatbiz
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8080

# 终端 3
cd services/credential
conda activate chatbiz
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 本地开发(全栈 docker-compose)

适合联调、跑 e2e / Playwright 测试,或一个 `docker compose up` 跑起来。

```bash
# 在仓库根
cd infrastructure
docker compose up -d

# 查看日志
docker compose logs -f workflow-engine
docker compose logs -f audit-and-isolation

# 进入容器调试
docker compose exec workflow-engine bash
docker compose exec postgres psql -U chatbiz -d workflow_engine

# 停止
docker compose down              # 保留数据卷
docker compose down -v           # 清理数据卷
```

启动后端点:

| 服务 | URL |
|------|-----|
| workflow-engine | http://localhost:8001 |
| workflow-engine OpenAPI | http://localhost:8001/docs |
| audit-and-isolation | http://localhost:8080 |
| credential | http://localhost:8000 |
| postgres | localhost:5432 (user=chatbiz / pwd=chatbiz) |
| redis | localhost:6379 |

### 生产环境(K8s)

🚧 规划中,本仓库目前不提供 Helm chart。

参考部署架构(`docs/architecture.md` §4.5):

- **Ingress**: Nginx Controller,统一入口
- **核心服务副本数**:Workflow Engine × 3 / Agent Runtime × 3 / Tool Executor × 3 / RAG × 2 / Model Proxy × 2
- **PostgreSQL**: 外部托管(RDS / Aurora / 自管 PG Operator)
- **Redis**: Sentinel / Cluster
- **对象存储**: S3 兼容(MinIO 集群)
- **监控**: Prometheus + Grafana + Jaeger

---

## 研发环境搭建

### 代码规范

- **后端**: Python 3.12,async/await 风格,SQLAlchemy 2.0 async ORM,FastAPI dependency injection
- **Pydantic v2** 用于所有 DTO / 配置 / Node Contract
- **Commit message**: `<type>(<scope>): <subject>`(`feat` / `fix` / `refactor` / `test` / `docs` / `chore`)
- **PR 流程**: branch → OpenSpec change → tests → verify.py → review → merge
- **OpenSpec 规范**: 中文需求 (`SHALL` / `MUST`),每 Requirement 至少一个 `#### Scenario:` (`WHEN` / `THEN`)

### 测试与覆盖率

每个服务都有 `tests/` 目录,标准结构:

```
tests/
├── unit/           # 单元测试(纯函数 + mock httpx)
├── e2e/            # 端到端(需 docker-compose up)
├── security/       # 安全相关(跨用户、凭据检查)
├── conftest.py     # 共享 fixture(aiosqlite + fakeredis + respx)
└── fixtures/       # 静态 fixture(paul 财务月报等)
```

#### 跑测试

```bash
cd services/<service-name>
conda activate chatbiz

# 单元 + 覆盖率(eng-review 锁定 100%)
python -m pytest tests/ --cov=app --cov-fail-under=100

# 仅单元(快)
python -m pytest tests/unit/ -v

# 单个测试
python -m pytest tests/unit/test_api_workflows.py::test_get_workflow_cross_user_403 -v

# E2E(需先 docker compose up)
python -m pytest tests/e2e/ -v
```

#### 测试栈

- `pytest` + `pytest-asyncio` (asyncio_mode = "auto")
- `pytest-cov` (覆盖率)
- `aiosqlite` (in-memory 替代 Postgres)
- `fakeredis` (替代 Redis)
- `respx` (mock httpx,无需真实 HTTP)
- `freezegun` (时间冻结,用于 cron 测试)
- `asgi-lifespan` (FastAPI lifespan 测试)

#### 当前覆盖率

| 服务 | 单元覆盖率 | 状态 |
|------|-----------|------|
| workflow-engine | **100%** (260 tests) | ✅ |
| audit-and-isolation | 0% (新) | ⏳ |
| credential | 0% (新) | ⏳ |

详细见各服务 `tests/` + `verify.py`。

### OpenSpec 变更工作流

所有功能/修复都走 OpenSpec change 工作流,默认 schema `superpowers-bridge`:

```bash
# 1. 列出活跃 changes
openspec list

# 2. 创建一个新 change
openspec new change add-foo

# 3. 写 artifacts(brainstorm → proposal → design → specs → tasks)
# 编辑 openspec/changes/add-foo/{proposal,design,plan,tasks,specs/*/spec}.md

# 4. 验证
openspec status --change add-foo

# 5. 实施
openspec apply-change add-foo
# (执行 tasks.md 中的 1-1, 1-2, ...)

# 6. 验证 + 归档
python verify.py
openspec archive -y add-foo
```

完整规范见 [`openspec/config.yaml`](openspec/config.yaml) + [`CLAUDE.md`](CLAUDE.md)。

### CI / 验证脚本

每个服务根目录有 `verify.py`,作为 CI gate:

```bash
cd services/<service-name>
python verify.py
# ✅ verify PASSED (all gates) 或 ❌ FAILED
```

`verify.py` 默认检查:

- `openspec/specs/<spec>/spec.md` 存在 + ≥ 5 scenarios + ≥ 8 requirements
- 14 节点契约全部存在 + `bind_execute_fns` 已绑定
- 4 个 ORM 模型 + 4 个 Alembic 迁移
- 7 个 API routers 全部挂载
- paul 财务月报 fixture 7 节点

---

## Docker 运行方案

### 镜像构建

每个服务都有多阶段 `Dockerfile`,参考 `services/workflow-engine/Dockerfile`:

```dockerfile
# syntax=docker/dockerfile:1.7
# builder: 装依赖到 /root/.local
FROM python:3.12-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
RUN pip install --user --no-cache-dir .

# runtime: 仅 slim + 非 root + 源码
FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin wf
COPY --from=builder /root/.local /home/wf/.local
COPY --chown=wf:wf . /app
USER wf
EXPOSE 8001
HEALTHCHECK CMD ["python", "-c", "import urllib.request,sys; \
    sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8001/healthz', timeout=2).status == 200 else sys.exit(1)"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

#### 单独构建

```bash
cd services/workflow-engine
docker build -t chatbiz/workflow-engine:dev .

# 跑(需要 DATABASE_URL 等环境变量)
docker run --rm -p 8001:8001 \
  -e DATABASE_URL=postgresql+asyncpg://chatbiz:chatbiz@host.docker.internal:5432/workflow_engine \
  -e REDIS_URL=redis://host.docker.internal:6379/0 \
  -e AUDIT_ISOLATION_URL=http://host.docker.internal:8080 \
  chatbiz/workflow-engine:dev
```

### Compose 编排

完整编排见 [`infrastructure/docker-compose.yml`](infrastructure/docker-compose.yml),250 行。包含:

| 服务组 | 服务 |
|--------|------|
| **共享基础设施** | `postgres` (port 5432), `redis` (port 6379) |
| **业务服务** | `workflow-engine` (8001), `audit-and-isolation` (8080), `credential` (8000) |
| **迁移容器** | `workflow-engine-migrate`, `credential-migrate`(一次性 alembic upgrade head) |
| **定时任务** | `credential-cron`(凭证清理 / 告警) |
| **数据卷** | `postgres-data`, `redis-data` |

#### 启动全栈

```bash
cd infrastructure

# 默认启动
docker compose up -d

# 看健康状态
docker compose ps

# 单独看 workflow-engine 日志
docker compose logs -f workflow-engine

# 触发一次性迁移
docker compose run --rm workflow-engine-migrate
# 或 alembic upgrade head(在容器内)

# 停止 + 清理
docker compose down            # 保留卷
docker compose down -v         # 删卷
```

#### 关键 env

`docker-compose.yml` 用 `${VAR:-default}` 让 `AUDIT_WEBHOOK_URL` / `WECOM_WEBHOOK_URL` / `LOG_LEVEL` / `ENVIRONMENT` 走 `.env` 或环境:

```bash
# infrastructure/.env (可选)
AUDIT_WEBHOOK_URL=https://hooks.example.com/audit
WECOM_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...
LOG_LEVEL=info
ENVIRONMENT=local
```

### 健康检查与日志

每个容器配 `HEALTHCHECK`:

```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U chatbiz -d credential"]
  interval: 5s
  timeout: 3s
  retries: 10
```

`workflow-engine` / `audit-and-isolation` / `credential` 容器有 `HEALTHCHECK` 通过 `/healthz` 探测。

#### 查日志

```bash
# 单个服务
docker compose logs -f workflow-engine

# 所有
docker compose logs -f

# 按时间
docker compose logs --since 10m workflow-engine

# 导出
docker compose logs workflow-engine > workflow-engine.log
```

---

## 文档与参考

| 文档 | 说明 |
|------|------|
| [`docs/architecture.md`](docs/architecture.md) | 70 KB 技术架构(对比 7 个 AI Agent 平台 + 6 层企业级设计 + 12 个 eng-review finding) |
| [`docs/prd.md`](docs/prd.md) | 166 KB 产品需求文档 v1.5(8 章节 / 6 模块 / 4 用户 / 3 场景 / 4 阶段里程碑) |
| [`docs/prototype.html`](docs/prototype.html) | 4562 行 HTML 产品原型 |
| [`CLAUDE.md`](CLAUDE.md) | Claude Code 工作约定(必读) |
| [`openspec/specs/`](openspec/specs/) | 已落地的所有 spec(workflow-engine / canvas-* / credential 等) |
| [`openspec/changes/`](openspec/changes/) | 进行中的 change + 归档目录 |
| `services/<svc>/README.md` | 每个服务的开发/部署指南 |

---

## Roadmap

| 阶段 | 周期 | 目标 | 状态 |
|------|------|------|------|
| **M0** (Month 0) | — | 设计冻结 + 12 个 eng-review finding 锁定 | ✅ |
| **MVP** (Month 1-3) | 3 月 | 数据隔离网关 + 自研画布 + paul 财务月报 workflow + 基础审计 | 🚧 进行中 |
| **V1.0** (Month 4-6) | 3 月 | 完整数据隔离 + 基础画布 + 4 节点 + 12 类节点全类型 | ⏳ |
| **V1.5** (Month 7-9) | 3 月 | 完整 14 类节点 + RAG + MCP + 人工审批 + 监控 | ⏳ |
| **V2.0** (Month 10-12) | 3 月 | 团队共享 + 模板广场 + 收藏 + 多租户 + Helm chart | ⏳ |

详细 PRD 见 [`docs/prd.md`](docs/prd.md) §8。

---

## License

[MIT](LICENSE)
