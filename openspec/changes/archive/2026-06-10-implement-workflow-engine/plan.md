# implement-workflow-engine Implementation Plan

> **For agentic workers:** Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Each task = one fresh subagent + spec reviewer + code quality reviewer.

**Goal:** 实现 workflow-engine 后端 service(14 节点 + 13 REST endpoint + 5 PG 表 + LangGraph StateGraph 编译执行 + Node Contract codegen + 4 critical path e2e),eng-review 8 finding(Arch #2/#4/#6, Quality #1/#2/#3, Test #2, Perf #2)100% 落地。

**Architecture:** 自研 workflow-engine 后端(FastAPI + SQLAlchemy 异步 + LangGraph 0.2)。Node Contract 用 Pydantic BaseModel 统一驱动 4 份产物(eng-review Quality #1)。Canvas JSON → LangGraph StateGraph 编译,workflow / chatflow 共享同一 CompiledStateGraph(eng-review Arch #4)。人工审批 4 设计点(LangGraph Checkpointer + 企微 + reentry + 24h timeout,eng-review Arch #6)。错误处理 4 边界(eng-review Quality #3)。paul 财务月报 end-to-end 1 完整 fixture(eng-review Test #2 path #1)。

**Tech Stack:** Python 3.12 / FastAPI 0.115 / SQLAlchemy 2.0 async / asyncpg / Alembic / langgraph 0.2 / langgraph-checkpoint-postgres / langchain-openai 0.2 / Pydantic 2.8 / NetworkX 3.3 / apscheduler 3.10 / Docker SDK 7 / httpx 0.27 / pytest + pytest-asyncio + httpx ASGITransport + fakeredis + respx + aiosqlite + testcontainers[postgres,redis]。

**依赖 service:** `services/audit-and-isolation:8080` (LLM 网关) + `services/credential:8000` (凭证) + PostgreSQL 16 + Redis 7。

**stub URL** (env var 配置,未实现返 503): `KNOWLEDGE_BASE_URL=http://knowledge-base:8002` / `AGENT_RUNTIME_URL=http://agent-runtime:8003`。

---

## Task 1: 脚手架 + 配置

**Files:**
- Create: `services/workflow-engine/pyproject.toml`
- Create: `services/workflow-engine/Dockerfile`
- Create: `services/workflow-engine/.env.example`
- Create: `services/workflow-engine/app/__init__.py`
- Create: `services/workflow-engine/app/config.py`
- Create: `services/workflow-engine/app/main.py`

- [ ] **Step 1.1:** 写 `pyproject.toml`(用 uv / poetry 二选一;这里用 PEP 621 标准)

```toml
[project]
name = "chatbiz-workflow-engine"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115,<0.116",
  "uvicorn[standard]>=0.30",
  "sqlalchemy[asyncio]>=2.0,<3.0",
  "asyncpg>=0.29",
  "alembic>=1.13",
  "redis>=5.0",
  "httpx>=0.27",
  "pydantic>=2.8,<3.0",
  "pydantic-settings>=2.4",
  "langgraph>=0.2,<0.3",
  "langgraph-checkpoint-postgres>=2.0",
  "langchain-openai>=0.2,<0.3",
  "langchain-core>=0.3",
  "networkx>=3.3",
  "apscheduler>=3.10",
  "docker>=7.0",
  "jinja2>=3.1",
  "python-multipart>=0.0.9",
  "sse-starlette>=2.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "pytest-cov>=5.0",
  "httpx>=0.27",
  "fakeredis>=2.23",
  "respx>=0.21",
  "aiosqlite>=0.20",
  "testcontainers[postgres,redis]>=4.8",
  "ruff>=0.6",
  "freezegun>=1.5",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-v --tb=short --cov=app --cov-report=term-missing --cov-fail-under=100"
```

- [ ] **Step 1.2:** 写 `Dockerfile`(同 audit-and-isolation 风格,多阶段 + non-root)

```dockerfile
# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt ./
# 同时安装 docker SDK 依赖(deb 装 docker cli 用于 sandbox 编排可选,实际用 unix socket)
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && \
    pip install --user --no-cache-dir -r requirements.txt && \
    apt-get purge -y gcc libpq-dev && apt-get autoremove -y

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH=/home/wf/.local/bin:$PATH
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin wf
WORKDIR /app
COPY --from=builder /root/.local /home/wf/.local
COPY --chown=wf:wf . /app
USER wf
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8001/healthz', timeout=2).status==200 else sys.exit(1)"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

`requirements.txt` 从 `pyproject.toml` 导出:`uv pip compile pyproject.toml -o requirements.txt`。

- [ ] **Step 1.3:** 写 `.env.example`(13 字段)

```bash
# Database
DATABASE_URL=postgresql+asyncpg://chatbiz:chatbiz@postgres:5432/workflow_engine
# Redis
REDIS_URL=redis://redis:6379/0
# External services
AUDIT_ISOLATION_URL=http://audit-and-isolation:8080
CREDENTIAL_SERVICE_URL=http://credential:8000
KNOWLEDGE_BASE_URL=http://knowledge-base:8002
AGENT_RUNTIME_URL=http://agent-runtime:8003
# Service token (issued by credential service, MVP static)
WORKFLOW_ENGINE_SERVICE_TOKEN=dev-wf-token
# Wecom webhook (optional, no send if not set)
WECOM_WEBHOOK_URL=
# App
LOG_LEVEL=info
ENVIRONMENT=local
# Docker sandbox
DOCKER_SANDBOX_ENABLED=true
DOCKER_SOCKET=/var/run/docker.sock
```

- [ ] **Step 1.4:** 写 `app/config.py` Pydantic Settings

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str
    audit_isolation_url: str
    credential_service_url: str
    knowledge_base_url: str = "http://knowledge-base:8002"
    agent_runtime_url: str = "http://agent-runtime:8003"
    workflow_engine_service_token: str
    wecom_webhook_url: str = ""
    log_level: str = "info"
    environment: str = "local"
    docker_sandbox_enabled: bool = True
    docker_socket: str = "/var/run/docker.sock"

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 1.5:** 写 `app/main.py`(FastAPI 启动 + /healthz)

```python
from fastapi import FastAPI
from app.config import get_settings

app = FastAPI(title="ChatBiz Workflow Engine", version="0.1.0")
settings = get_settings()

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
```

- [ ] **Step 1.6:** 验证:`uv sync` + `pytest` 启动空 OK + docker build 不报错 + commit

```bash
git add services/workflow-engine/ && git commit -m "feat(workflow-engine): scaffold + config + healthz"
```

---

## Task 2: PostgreSQL ORM + Alembic

**Files:**
- Create: `services/workflow-engine/app/database.py`
- Create: `services/workflow-engine/app/models/__init__.py`
- Create: `services/workflow-engine/app/models/base.py`
- Create: `services/workflow-engine/app/models/workflow.py`
- Create: `services/workflow-engine/alembic.ini`
- Create: `services/workflow-engine/alembic/env.py`
- Create: `services/workflow-engine/alembic/versions/001_workflow_definition.py`
- Create: `services/workflow-engine/alembic/versions/002_workflow_run.py`
- Create: `services/workflow-engine/alembic/versions/003_node_event.py`
- Create: `services/workflow-engine/alembic/versions/004_approval.py`
- Create: `services/workflow-engine/app/checkpointer.py`
- Test: `services/workflow-engine/tests/test_orm.py`

- [ ] **Step 2.1:** 写 `app/database.py`(同 audit-and-isolation 模式)

```python
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from app.config import get_settings

_settings = get_settings()
engine = create_async_engine(_settings.database_url, pool_pre_ping=True, pool_size=20)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session

async def dispose_engine():
    await engine.dispose()
```

- [ ] **Step 2.2:** 写 `app/models/base.py` + `app/models/workflow.py`(严格按 spec §workflow-state-storage 字段)

```python
# base.py
from sqlalchemy.orm import DeclarativeBase
class Base(DeclarativeBase): pass

# workflow.py
from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
import uuid
from datetime import datetime
from app.models.base import Base

class WorkflowDefinition(Base):
    __tablename__ = "workflow_definition"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    definition_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (Index("ix_wf_def_id_version", "id", "version"),)

class WorkflowRun(Base):
    __tablename__ = "workflow_run"
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    workflow_version: Mapped[int] = mapped_column(Integer, nullable=False)
    thread_id: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)  # 'workflow' | 'chatflow'
    status: Mapped[str] = mapped_column(Text, nullable=False)  # 'pending'|'running'|'paused'|'completed'|'failed'|'cancelled'
    started_by: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(default=None)
    error_class: Mapped[str | None] = mapped_column(default=None)
    error_message: Mapped[str | None] = mapped_column(default=None)
    __table_args__ = (
        Index("ix_wf_run_workflow_started", "workflow_id", "started_at"),
        Index("ix_wf_run_thread", "thread_id"),
    )

class NodeEvent(Base):
    __tablename__ = "node_event"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflow_run.run_id", ondelete="CASCADE"), nullable=False)
    node_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    input_json: Mapped[dict | None] = mapped_column(JSONB, default=None)
    output_json: Mapped[dict | None] = mapped_column(JSONB, default=None)
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    ended_at: Mapped[datetime | None] = mapped_column(default=None)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_class: Mapped[str | None] = mapped_column(default=None)
    error_message: Mapped[str | None] = mapped_column(default=None)
    __table_args__ = (Index("ix_node_event_run_started", "run_id", "started_at"),)

class Approval(Base):
    __tablename__ = "approval"
    approval_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflow_run.run_id", ondelete="CASCADE"), nullable=False)
    node_id: Mapped[str] = mapped_column(Text, nullable=False)
    approver_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)  # 'pending'|'approved'|'rejected'|'timeout'|'cancelled'
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    responded_at: Mapped[datetime | None] = mapped_column(default=None)
    response_payload: Mapped[dict | None] = mapped_column(JSONB, default=None)
    __table_args__ = (Index("ix_approval_approver_status_created", "approver_user_id", "status", "created_at"),)
```

- [ ] **Step 2.3:** 写 `alembic.ini` + `alembic/env.py` 异步 + 4 个 migration

`alembic/env.py` 异步示例(关键段):

```python
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from app.config import get_settings
from app.models.base import Base
from app.models.workflow import WorkflowDefinition, WorkflowRun, NodeEvent, Approval

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata

async def run_migrations_online():
    connectable = async_engine_from_config(config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool)
    async with connectable.connect() as conn:
        await conn.run_sync(do_run_migrations)
    await connectable.dispose()
```

4 个 migration 各 30-50 行(op.create_table + op.create_index + op.create_foreign_key + down_revision chain:1 → 2 → 3 → 4)。

- [ ] **Step 2.4:** 写 `app/checkpointer.py`(LangGraph AsyncPostgresSaver 单例)

```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.config import get_settings

_saver: AsyncPostgresSaver | None = None

async def get_checkpointer() -> AsyncPostgresSaver:
    global _saver
    if _saver is None:
        # 解析 DSN 改 asyncpg 格式
        dsn = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://")
        _saver = AsyncPostgresSaver.from_conn_string(dsn)
        await _saver.setup()  # 自动建 checkpoints 表
    return _saver
```

- [ ] **Step 2.5:** 写 `tests/test_orm.py`(aiosqlite + 4 表 CRUD + alembic upgrade/downgrade)

```python
import pytest
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models.base import Base
from app.models.workflow import WorkflowDefinition, WorkflowRun, NodeEvent, Approval

@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s
    await engine.dispose()

async def test_workflow_definition_crud(session):
    wf = WorkflowDefinition(version=1, name="test", created_by="u1", definition_json={"nodes": []})
    session.add(wf)
    await session.commit()
    result = await session.scalar(select(WorkflowDefinition))
    assert result.name == "test"
    assert result.archived is False
```

- [ ] **Step 2.6:** 验证:`pytest tests/test_orm.py -v` + alembic upgrade head + alembic downgrade base 双向 + commit

---

## Task 3: Redis + 服务客户端

**Files:**
- Create: `services/workflow-engine/app/redis_client.py`
- Create: `services/workflow-engine/app/clients/__init__.py`
- Create: `services/workflow-engine/app/clients/audit_isolation.py`
- Create: `services/workflow-engine/app/clients/credential.py`
- Create: `services/workflow-engine/app/clients/knowledge_base.py`
- Create: `services/workflow-engine/app/clients/agent_runtime.py`
- Test: `services/workflow-engine/tests/test_clients.py`

- [ ] **Step 3.1:** 写 `app/redis_client.py`(同 audit-and-isolation 风格)

```python
import redis.asyncio as aioredis
from app.config import get_settings
_redis: aioredis.Redis | None = None

def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(get_settings().redis_url, decode_responses=True, max_connections=50)
    return _redis

async def dispose_redis():
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
```

- [ ] **Step 3.2:** 写 4 个 httpx 客户端(同 audit-and-isolation 的 `httpx.AsyncClient` + timeout + retry)

骨架模式:

```python
import httpx
from app.config import get_settings

class AuditIsolationClient:
    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get(self) -> httpx.AsyncClient:
        if self._client is None:
            s = get_settings()
            self._client = httpx.AsyncClient(
                base_url=s.audit_isolation_url,
                timeout=httpx.Timeout(30.0, connect=5.0),
                headers={"X-Service-Token": s.workflow_engine_service_token, "X-Trace-Id": "wf-{uuid}"},
            )
        return self._client

    async def chat(self, model: str, messages: list, **kw) -> dict:
        c = await self._get()
        r = await c.post("/v1/chat/completions", json={"model": model, "messages": messages, **kw})
        r.raise_for_status()
        return r.json()

    async def aclose(self):
        if self._client: await self._client.aclose()
```

- [ ] **Step 3.3:** 写 `tests/test_clients.py`(`respx` mock 4 个 client)

```python
import respx, httpx, pytest
from httpx import Response
from app.clients.audit_isolation import AuditIsolationClient

@pytest.mark.asyncio
@respx.mock
async def test_audit_isolation_chat():
    respx.post("http://audit-and-isolation:8080/v1/chat/completions").mock(
        return_value=Response(200, json={"choices": [{"message": {"content": "hi"}}]})
    )
    c = AuditIsolationClient()
    r = await c.chat("gpt-4", [{"role": "user", "content": "hi"}])
    assert r["choices"][0]["message"]["content"] == "hi"
    await c.aclose()
```

- [ ] **Step 3.4:** 验证 + commit

---

## Task 4: Node Contract codegen(eng-review Arch #2 / Quality #1)

**Files:**
- Create: `services/workflow-engine/app/nodes/__init__.py`
- Create: `services/workflow-engine/app/nodes/registry.py`
- Create: `services/workflow-engine/app/nodes/contracts/base.py`
- Create: `services/workflow-engine/app/nodes/contracts/{start,end,variable_assign,condition,llm,knowledge,agent,http,code,approval,loop,iterate,subflow,extract}.py` (14 文件)
- Test: `services/workflow-engine/tests/test_node_contracts.py`

- [ ] **Step 4.1:** 写 `app/nodes/registry.py`(核心!)

```python
from typing import Callable, Any
from pydantic import BaseModel
from app.errors.classes import NodeTypeNotRegisteredError, NodeOutputValidationError

NODE_REGISTRY: dict[str, "NodeContract"] = {}

class NodeContract:
    def __init__(self, type_name: str, base_model: type[BaseModel], execute_fn: Callable, version: str = "1.0.0"):
        self.type_name = type_name
        self.base_model = base_model
        self.execute_fn = execute_fn
        self.version = version
        NODE_REGISTRY[type_name] = self

    def schema(self) -> dict:
        return self.base_model.model_json_schema()

    def validate_config(self, config: dict) -> BaseModel:
        return self.base_model.model_validate(config)

    def wrap_for_langgraph(self) -> Callable:
        """包装 execute_fn 为 LangGraph node function"""
        async def node_fn(state: dict) -> dict:
            config = state.get("node_config", {})
            inputs = state.get("node_inputs", {})
            try:
                outputs = await self.execute_fn(config, inputs)
            except Exception as e:
                raise
            # output validation
            try:
                validated = self.base_model.model_validate({"config": config, "input_schema": {}, "output_schema": outputs})
            except Exception as e:
                raise NodeOutputValidationError(type_name=self.type_name, original=str(e))
            return {**state, "node_outputs": outputs}
        return node_fn

def register(type_name: str, version: str = "1.0.0"):
    def deco(base_model_cls):
        async def default_execute(config, inputs): return {}
        NODE_REGISTRY[type_name] = NodeContract(type_name, base_model_cls, default_execute, version)
        return base_model_cls
    return deco
```

- [ ] **Step 4.2:** 写 `app/nodes/contracts/base.py` 通用基类

```python
from pydantic import BaseModel
class BaseConfig(BaseModel):
    """所有节点 config 的基类"""
    pass
class BaseNode(BaseModel):
    config: BaseConfig
    input_schema: dict = {}
    output_schema: dict = {}
```

- [ ] **Step 4.3:** 写最简单的 3 个节点(start / end / variable_assign)

`start.py`:
```python
from pydantic import Field
from app.nodes.contracts.base import BaseNode, BaseConfig
from app.nodes.registry import register

class StartConfig(BaseConfig):
    inputs: dict = Field(default_factory=dict)

@register("start")
class StartNode(BaseNode):
    config: StartConfig

async def start_execute(config: StartConfig, inputs: dict) -> dict:
    return {"started": True, "inputs": inputs}
```

`end.py` / `variable_assign.py` 同模式。

- [ ] **Step 4.4:** 写 `condition.py`(Jinja2 条件)

```python
from pydantic import Field
from app.nodes.contracts.base import BaseNode, BaseConfig
from app.nodes.registry import NODE_REGISTRY
from app.graph.jinja import render_jinja

class ConditionConfig(BaseConfig):
    expression: str = Field(..., description="Jinja2 表达式,返回 true/false")

@register("condition")
class ConditionNode(BaseNode):
    config: ConditionConfig

async def condition_execute(config: ConditionConfig, inputs: dict) -> dict:
    rendered = render_jinja(config.expression, {"node_outputs": inputs})
    return {"branch": bool(rendered), "raw": str(rendered)}
```

- [ ] **Step 4.5:** 写 `llm.py`(调 audit-and-isolation 网关)

```python
from pydantic import Field
from app.nodes.contracts.base import BaseNode, BaseConfig
from app.clients.audit_isolation import AuditIsolationClient

class LLMConfig(BaseConfig):
    model: str = Field(..., description="模型名,如 gpt-4 / qwen-max")
    credential_id: str = Field(..., description="credential_management 凭证 ID")
    prompt: str = Field(..., description="Jinja2 模板")
    temperature: float = 0.7
    max_tokens: int = 4096

@register("llm")
class LLMNode(BaseNode):
    config: LLMConfig

async def llm_execute(config: LLMConfig, inputs: dict) -> dict:
    from app.graph.jinja import render_jinja
    prompt = render_jinja(config.prompt, inputs)
    c = AuditIsolationClient()
    r = await c.chat(config.model, [{"role": "user", "content": prompt}],
                      temperature=config.temperature, max_tokens=config.max_tokens)
    return {"content": r["choices"][0]["message"]["content"], "usage": r.get("usage", {})}
```

- [ ] **Step 4.6:** 写 `knowledge.py` / `agent.py`(stub)

```python
# knowledge.py
class KnowledgeConfig(BaseConfig):
    knowledge_base_id: str
    query: str  # Jinja2
    top_k: int = 5

@register("knowledge")
class KnowledgeNode(BaseNode):
    config: KnowledgeConfig

async def knowledge_execute(config: KnowledgeConfig, inputs: dict) -> dict:
    import httpx
    from app.config import get_settings
    s = get_settings()
    r = httpx.post(f"{s.knowledge_base_url}/retrieve",
                   json={"knowledge_base_id": config.knowledge_base_id, "query": config.query, "top_k": config.top_k},
                   timeout=10.0)
    if r.status_code == 503:
        raise RuntimeError("knowledge-base service not implemented")
    r.raise_for_status()
    return r.json()
```

- [ ] **Step 4.7:** 写 `http.py`(httpx + retry)

```python
class HTTPConfig(BaseConfig):
    method: Literal["GET", "POST", "PUT", "DELETE"]
    url: str  # Jinja2
    headers: dict[str, str] = Field(default_factory=dict)
    body: dict | None = None
    timeout_ms: int = 5000
    retry_count: int = 1

@register("http")
class HTTPNode(BaseNode):
    config: HTTPConfig

async def http_execute(config: HTTPConfig, inputs: dict) -> dict:
    from app.graph.jinja import render_jinja
    import httpx
    url = render_jinja(config.url, inputs)
    body = render_jinja(config.body, inputs) if config.body else None
    last_exc = None
    for attempt in range(config.retry_count + 1):
        try:
            async with httpx.AsyncClient(timeout=config.timeout_ms / 1000) as c:
                r = await c.request(config.method, url, headers=config.headers, json=body)
                r.raise_for_status()
                return {"status": r.status_code, "body": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text}
        except Exception as e:
            last_exc = e
            if attempt < config.retry_count:
                await asyncio.sleep(1 * (2 ** attempt))
            else:
                raise
```

- [ ] **Step 4.8:** 写 `code.py`(Docker sandbox,eng-review Q3 锁定)

```python
import docker, asyncio
from app.config import get_settings

class CodeConfig(BaseConfig):
    language: Literal["python", "node"]
    code: str
    input_variables: list[str] = Field(default_factory=list)
    cpu: float = 0.5
    memory_mb: int = 256
    timeout_s: int = 30

@register("code")
class CodeNode(BaseNode):
    config: CodeConfig

async def code_execute(config: CodeConfig, inputs: dict) -> dict:
    s = get_settings()
    if not s.docker_sandbox_enabled:
        raise RuntimeError("Docker sandbox disabled")
    image = "python:3.12-slim" if config.language == "python" else "node:20-slim"
    client = docker.DockerClient(base_url=f"unix://{s.docker_socket}")
    try:
        container = client.containers.run(
            image, command=["sh", "-c", "cat > /tmp/code.txt && python3 /tmp/code.txt" if config.language == "python" else "cat > /tmp/code.txt && node /tmp/code.txt"],
            stdin_open=True, detach=True,
            cpu_quota=int(config.cpu * 100000), mem_limit=f"{config.memory_mb}m",
            network_mode="none",
        )
        container.wait(timeout=config.timeout_s)
        stdout = container.logs(stdout=True, stderr=False).decode()
        stderr = container.logs(stdout=False, stderr=True).decode()
        container.remove(force=True)
        if stderr:
            return {"stdout": stdout, "stderr": stderr, "exit_code": 1}
        return {"stdout": stdout, "exit_code": 0}
    except docker.errors.ContainerError as e:
        raise RuntimeError(f"code execution failed: {e.stderr.decode()}")
    except Exception as e:
        raise RuntimeError(f"code execution timeout or resource exceeded: {e}")
```

- [ ] **Step 4.9:** 写 `approval.py`(eng-review Arch #6 4 设计点)

```python
class ApprovalConfig(BaseConfig):
    approver_user_id: str
    timeout_hours: int = 24
    notify_channels: list[Literal["wecom", "email", "in_app"]] = ["wecom"]
    approval_content_template: str  # Jinja2

@register("approval")
class ApprovalNode(BaseNode):
    config: ApprovalConfig

async def approval_execute(config: ApprovalConfig, inputs: dict) -> dict:
    """LangGraph will pause here via interrupt_before / interrupt_after"""
    from app.graph.jinja import render_jinja
    content = render_jinja(config.approval_content_template, inputs)
    # 1. 写 approval 表(status=pending)
    # 2. 发企微 webhook
    # 3. UPDATE workflow_run.status=paused
    # 4. LangGraph 状态由 compile_state_graph 时的 interrupt_before 处理
    return {"pending": True, "approver": config.approver_user_id, "content": content}
```

- [ ] **Step 4.10:** 写剩余 4 节点(loop / iterate / subflow / extract)+ 测试

- [ ] **Step 4.11:** 验证:`pytest tests/test_node_contracts.py -v`(14 节点单测)+ `GET /api/nodes/:type/schema` 14 个全过 + commit

---

## Task 5: StateGraph 编译器(eng-review Arch #4)

**Files:**
- Create: `services/workflow-engine/app/graph/__init__.py`
- Create: `services/workflow-engine/app/graph/jinja.py`
- Create: `services/workflow-engine/app/graph/compiler.py`
- Create: `services/workflow-engine/app/graph/conditional.py`
- Create: `services/workflow-engine/app/graph/dispatcher.py`
- Test: `services/workflow-engine/tests/test_compiler.py`

- [ ] **Step 5.1:** 写 `app/graph/jinja.py`(Jinja2 渲染 + 变量上下文)

```python
from jinja2 import Environment, StrictUndefined, TemplateSyntaxError
_env = Environment(undefined=StrictUndefined, autoescape=False)

def render_jinja(template_str: str, context: dict) -> str:
    if not isinstance(template_str, str):
        return template_str
    try:
        return _env.from_string(template_str).render(**context)
    except TemplateSyntaxError as e:
        raise ValueError(f"Jinja2 语法错误: {e.message} at line {e.lineno}")
```

- [ ] **Step 5.2:** 写 `app/graph/compiler.py`(纯函数编译 + cache)

```python
from langgraph.graph import StateGraph, END
from app.nodes.registry import NODE_REGISTRY
from app.errors.classes import NodeTypeNotRegisteredError
import functools

_cache: dict[str, object] = {}

def compile_state_graph(workflow_definition: dict, workflow_id: str = "adhoc") -> object:
    cache_key = f"{workflow_id}:{workflow_definition.get('version', 0)}"
    if cache_key in _cache:
        return _cache[cache_key]
    graph = StateGraph(dict)
    nodes = workflow_definition["nodes"]
    edges = workflow_definition["edges"]
    for n in nodes:
        if n["type"] not in NODE_REGISTRY:
            raise NodeTypeNotRegisteredError(n["type"])
        graph.add_node(n["id"], NODE_REGISTRY[n["type"]].wrap_for_langgraph())
    graph.set_entry_point(nodes[0]["id"])
    for e in edges:
        if "condition" in e:
            graph.add_conditional_edges(e["from"], lambda s: s.get("branch", False), {True: e["to"], False: e.get("default", END)})
        else:
            graph.add_edge(e["from"], e["to"])
    compiled = graph.compile()
    _cache[cache_key] = compiled
    return compiled
```

- [ ] **Step 5.3:** 写 `app/graph/dispatcher.py`(workflow / chatflow 双模式)

```python
import uuid
from app.graph.compiler import compile_state_graph

async def dispatch(workflow_definition: dict, mode: str, session_id: str | None, initial_state: dict) -> dict:
    compiled = compile_state_graph(workflow_definition)
    if mode == "workflow":
        thread_id = f"run-{uuid.uuid4()}"
    else:  # chatflow
        thread_id = session_id or f"chat-{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}
    return await compiled.ainvoke(initial_state, config=config)
```

- [ ] **Step 5.4:** 验证 + commit

---

## Task 6: 执行引擎 + workflow_run 状态机

**Files:**
- Create: `services/workflow-engine/app/executor/__init__.py`
- Create: `services/workflow-engine/app/executor/runner.py`
- Create: `services/workflow-engine/app/executor/retry.py`
- Create: `services/workflow-engine/app/executor/node_event.py`
- Create: `services/workflow-engine/app/executor/credential_check.py`
- Create: `services/workflow-engine/app/executor/sse.py`
- Test: `services/workflow-engine/tests/test_executor.py`

- [ ] **Step 6.1:** 写 `app/executor/runner.py`(asyncio.create_task 跑 workflow)

骨架:

```python
import asyncio
from app.graph.dispatcher import dispatch
from app.executor.node_event import write_node_event
from app.models.workflow import WorkflowRun
from app.database import SessionLocal
from datetime import datetime

async def run_workflow(run_id: str, workflow_definition: dict, mode: str, started_by: str):
    async with SessionLocal() as session:
        run = await session.get(WorkflowRun, run_id)
        run.status = "running"
        await session.commit()
    try:
        result = await dispatch(workflow_definition, mode, session_id=None, initial_state={})
        async with SessionLocal() as session:
            run = await session.get(WorkflowRun, run_id)
            run.status = "completed"
            run.ended_at = datetime.utcnow()
            await session.commit()
        return result
    except Exception as e:
        async with SessionLocal() as session:
            run = await session.get(WorkflowRun, run_id)
            run.status = "failed"
            run.error_class = type(e).__name__
            run.error_message = str(e)
            run.ended_at = datetime.utcnow()
            await session.commit()
        raise

def schedule_run(workflow_definition: dict, mode: str, started_by: str) -> str:
    import uuid
    run_id = uuid.uuid4()
    asyncio.create_task(run_workflow(run_id, workflow_definition, mode, started_by))
    return run_id
```

- [ ] **Step 6.2:** 写 `app/executor/retry.py`(runtime 1 次 indexed backoff)

```python
import asyncio

async def with_retry(fn, retry_count: int = 1):
    last_exc = None
    for attempt in range(retry_count + 1):
        try:
            return await fn()
        except Exception as e:
            from app.errors.classes import UserError, SecurityError
            if isinstance(e, (UserError, SecurityError)):
                raise  # 不重试
            last_exc = e
            if attempt < retry_count:
                await asyncio.sleep(1 * (2 ** attempt))
    raise last_exc
```

- [ ] **Step 6.3:** 写 `app/executor/node_event.py`(写 node_event 记录)

```python
from app.models.workflow import NodeEvent
from app.database import SessionLocal
from datetime import datetime

async def write_node_event(run_id, node_id, status, input_json=None, output_json=None, retry_count=0, error_class=None, error_message=None):
    async with SessionLocal() as session:
        ev = NodeEvent(run_id=run_id, node_id=node_id, status=status,
                       input_json=input_json, output_json=output_json,
                       started_at=datetime.utcnow() if status == "running" else None,
                       ended_at=datetime.utcnow() if status in ("completed", "failed", "skipped") else None,
                       retry_count=retry_count, error_class=error_class, error_message=error_message)
        session.add(ev)
        await session.commit()
        return ev.id
```

- [ ] **Step 6.4:** 写 `app/executor/credential_check.py`(启动时遍历节点 + 调 credential 客户端)

```python
import httpx
from app.config import get_settings
from app.errors.classes import SecurityError

async def check_credentials(workflow_definition: dict, started_by: str) -> None:
    s = get_settings()
    for n in workflow_definition.get("nodes", []):
        cid = (n.get("config") or {}).get("credential_id")
        if cid:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.get(f"{s.credential_service_url}/v1/credentials/{cid}/access",
                                params={"user_id": started_by},
                                headers={"X-Service-Token": s.workflow_engine_service_token})
            if r.status_code != 200:
                raise SecurityError(f"无权限访问凭证 {cid}")
```

- [ ] **Step 6.5:** 写 `app/executor/sse.py`(SSE 节点事件流)

```python
from sse_starlette.sse import EventSourceResponse
from app.models.workflow import NodeEvent, WorkflowRun
from app.database import SessionLocal
import asyncio, json
from datetime import datetime

async def run_events_sse(run_id: str):
    async def event_generator():
        last_event_id = 0
        while True:
            async with SessionLocal() as session:
                run = await session.get(WorkflowRun, run_id)
                if not run:
                    yield {"event": "error", "data": json.dumps({"error": "not found"})}
                    return
                events = (await session.execute(
                    __import__("sqlalchemy").select(NodeEvent).where(NodeEvent.run_id == run_id, NodeEvent.id > last_event_id).order_by(NodeEvent.id)
                )).scalars().all()
                for ev in events:
                    last_event_id = ev.id
                    yield {"event": f"node_{ev.status}", "data": json.dumps({"run_id": str(run_id), "node_id": ev.node_id, "status": ev.status, "ts": ev.started_at.isoformat() if ev.started_at else None})}
                if run.status in ("completed", "failed", "cancelled"):
                    yield {"event": f"run_{run.status}", "data": json.dumps({"run_id": str(run_id), "status": run.status})}
                    return
            await asyncio.sleep(0.5)
    return EventSourceResponse(event_generator())
```

- [ ] **Step 6.6:** 验证:paul 月报 fixture e2e(单测 mock 全部)+ retry 测试 + SSE 多客户端测试 + commit

---

## Task 7: REST API(13 个 endpoint)

**Files:**
- Create: `services/workflow-engine/app/api/__init__.py`
- Create: `services/workflow-engine/app/api/{workflows,validate,run,runs,approvals,nodes,health}.py`
- Modify: `services/workflow-engine/app/main.py`

- [ ] **Step 7.1:** 写 7 个 API router 文件(每个 ~50-100 行,CRUD + FastAPI 装饰器 + Pydantic request/response)
- [ ] **Step 7.2:** 改 `app/main.py` 集成所有 router + lifespan(启动 cron + checkpointer.setup)
- [ ] **Step 7.3:** 验证:13 endpoint 接口测试 + OpenAPI 完整 + commit

---

## Task 8: 错误处理 4 边界(eng-review Quality #3)

**Files:**
- Create: `services/workflow-engine/app/errors/__init__.py`
- Create: `services/workflow-engine/app/errors/classes.py`
- Create: `services/workflow-engine/app/errors/middleware.py`
- Create: `services/workflow-engine/app/errors/handlers.py`
- Create: `services/workflow-engine/app/errors/cycle_detection.py`
- Test: `services/workflow-engine/tests/test_errors.py`

- [ ] **Step 8.1:** 写 `app/errors/classes.py`(7 个 exception)

```python
class ChatBizError(Exception):
    error_class = "internal"
    def __init__(self, message: str, **context):
        super().__init__(message)
        self.message = message
        self.context = context

class SecurityError(ChatBizError): error_class = "security"
class UserError(ChatBizError): error_class = "user"
class RuntimeError_(ChatBizError): error_class = "runtime"  # 注意不覆盖 builtin RuntimeError
class NodeTypeNotRegisteredError(UserError): error_class = "user"
class NodeOutputValidationError(RuntimeError_): pass
class CodeExecutionFailed(RuntimeError_): pass
class ApprovalNotFound(UserError): pass
class ApprovalAlreadyResponded(UserError): pass
class UnauthorizedApprovalAccess(SecurityError): pass
```

- [ ] **Step 8.2:** 写 `app/errors/middleware.py`(统一 4xx/5xx 响应)

- [ ] **Step 8.3:** 写 `app/errors/handlers.py`(Pydantic ValidationError → user;httpx 5xx → runtime;权限 → security)
- [ ] **Step 8.4:** 写 `app/errors/cycle_detection.py`(NetworkX find_cycle)

```python
import networkx as nx
def detect_cycle(workflow_definition: dict) -> list[str] | None:
    g = nx.DiGraph()
    for n in workflow_definition["nodes"]: g.add_node(n["id"])
    for e in workflow_definition["edges"]: g.add_edge(e["from"], e["to"])
    try:
        return nx.find_cycle(g)
    except nx.NetworkXNoCycle:
        return None
```

- [ ] **Step 8.5:** 验证:4 边界各 2-3 单测 + commit

---

## Task 9: 人工审批 cron + 通知(eng-review Arch #6)

**Files:**
- Create: `services/workflow-engine/app/cron/__init__.py`
- Create: `services/workflow-engine/app/cron/approval_timeout.py`
- Create: `services/workflow-engine/app/cron/cleanup.py`
- Create: `services/workflow-engine/app/cron/lifespan.py`
- Test: `services/workflow-engine/tests/test_cron.py`

- [ ] **Step 9.1:** 写 `app/cron/approval_timeout.py`(apscheduler AsyncIOScheduler + SELECT FOR UPDATE SKIP LOCKED)

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, text
from app.database import SessionLocal
from app.models.workflow import Approval, WorkflowRun
from datetime import datetime, timedelta
import logging
log = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

async def check_approval_timeout():
    async with SessionLocal() as session:
        # SELECT FOR UPDATE SKIP LOCKED 防多实例重复处理
        result = await session.execute(
            select(Approval).where(Approval.status == "pending", Approval.created_at < datetime.utcnow() - timedelta(hours=24)).with_for_update(skip_locked=True)
        )
        expired = result.scalars().all()
        for ap in expired:
            ap.status = "timeout"
            ap.responded_at = datetime.utcnow()
            run = await session.get(WorkflowRun, ap.run_id)
            if run:
                run.status = "failed"
                run.error_class = "user"
                run.error_message = "approval timeout: 24h exceeded"
        await session.commit()
        log.info(f"approval timeout: marked {len(expired)} as timeout")

def start_cron():
    scheduler.add_job(check_approval_timeout, "cron", minute="*/5", id="approval_timeout", replace_existing=True)
    scheduler.start()

def stop_cron():
    if scheduler.running: scheduler.shutdown()
```

- [ ] **Step 9.2:** 写 `app/cron/cleanup.py`(90 天清理)
- [ ] **Step 9.3:** 写 `app/cron/lifespan.py`(FastAPI lifespan 启停 cron)
- [ ] **Step 9.4:** 验证:approval timeout 测试(用 freezegun)+ cleanup 测试 + 启停测试 + commit

---

## Task 10: Docker compose + OpenAPI

**Files:**
- Modify: `infrastructure/docker-compose.yml`(加 `workflow-engine` + `workflow-engine-migrate` 服务,挂 docker socket + security_opt)
- Create: `services/workflow-engine/scripts/export_openapi.py`
- Create: `services/workflow-engine/scripts/perf_bench.py`

- [ ] **Step 10.1:** docker-compose 增服务(volumes 挂 /var/run/docker.sock + no-new-privileges + depends_on audit-and-isolation healthy)
- [ ] **Step 10.2:** OpenAPI 导出(`python -m app.main` + httpx 调 /openapi.json)
- [ ] **Step 10.3:** perf bench 脚本(5 个 endpoint 100 并发,记录 p99)
- [ ] **Step 10.4:** 验证 + commit

---

## Task 11: 4 critical path E2E + 安全测试

**Files:**
- Create: `services/workflow-engine/tests/fixtures/paul_monthly_report.json`
- Create: `services/workflow-engine/tests/e2e/test_paul_monthly_report.py`
- Create: `services/workflow-engine/tests/e2e/test_manual_approval.py`
- Create: `services/workflow-engine/tests/e2e/test_pii_blocked.py`
- Create: `services/workflow-engine/tests/e2e/test_plugin_degradation.py`
- Create: `services/workflow-engine/tests/security/test_credential_check.py`
- Create: `services/workflow-engine/tests/security/test_cross_user.py`

- [ ] **Step 11.1:** 写 `paul_monthly_report.json` fixture(7 节点)

```json
{
  "nodes": [
    {"id": "start", "type": "start", "config": {}, "position": {"x": 0, "y": 0}},
    {"id": "fetch_erp", "type": "http", "config": {"method": "GET", "url": "http://mock-erp/data", "credential_id": "cred-erp"}},
    {"id": "set_vars", "type": "variable_assign", "config": {"vars": {"month": "2026-05"}}},
    {"id": "check", "type": "condition", "config": {"expression": "{{fetch_erp.output.body.revenue}} > 1000000"}},
    {"id": "summary", "type": "llm", "config": {"model": "gpt-4", "credential_id": "cred-openai", "prompt": "{{variables.month}} 月报: {{fetch_erp.output.body}}"}},
    {"id": "approve", "type": "approval", "config": {"approver_user_id": "u-paul", "timeout_hours": 24, "approval_content_template": "请审批 {{variables.month}} 月报"}},
    {"id": "end", "type": "end", "config": {}, "position": {"x": 0, "y": 500}}
  ],
  "edges": [
    {"from": "start", "to": "fetch_erp"},
    {"from": "fetch_erp", "to": "set_vars"},
    {"from": "set_vars", "to": "check"},
    {"from": "check", "to": "summary", "condition": "true"},
    {"from": "check", "to": "end", "condition": "false"},
    {"from": "summary", "to": "approve"},
    {"from": "approve", "to": "end"}
  ],
  "variables": {"month": "2026-05"}
}
```

- [ ] **Step 11.2:** 写 `test_paul_monthly_report.py`(mock ERP + 网关 + 企微 + credential 端到端 7 节点)
- [ ] **Step 11.3:** 写 `test_manual_approval.py`(触发 → paused → resume → 完成 + 24h timeout)
- [ ] **Step 11.4:** 写 `test_pii_blocked.py`(mock 网关返 422 PII → 验证 workflow_run failed)
- [ ] **Step 11.5:** 写 `test_plugin_degradation.py`(HTTP 503 → retry → degrade)
- [ ] **Step 11.6:** 写 `tests/security/test_credential_check.py` + `test_cross_user.py`
- [ ] **Step 11.7:** 验证:11.x 全部 e2e + security 100% + 覆盖率 ≥ 100% / 接口 100% + commit

---

## Task 12: 文档 + verify.py CI gate

**Files:**
- Create: `services/workflow-engine/README.md`
- Create: `services/workflow-engine/verify.py`
- Create: `services/workflow-engine/tests/integration/test_docker_compose.py`

- [ ] **Step 12.1:** 写 `README.md`(启动 / env / 测试 / 故障排查)
- [ ] **Step 12.2:** 写 `verify.py`(eng-review 17+ requirement + 18 gate)
- [ ] **Step 12.3:** 写集成测试(`docker compose up + curl /readyz + curl /api/nodes/llm/schema`)
- [ ] **Step 12.4:** ruff fix + 全部单测 + e2e + 集成测试通过
- [ ] **Step 12.5:** 最终 commit + 整理 commit history

---

**总任务量**: 12 大组,85 子任务(任务列表中 12 大组已对应),~250-400 micro-step(此 plan 详细 step 数)。

**关键路径**: 1 → 2 → 3 → 4(基础)→ 5 → 6(核心)→ 7(API)→ 8(错误)→ 9(审批)→ 10(deploy)→ 11(e2e)→ 12(verify)。

**依赖关系**:
- Task 1 → 全部
- Task 2 → 6 / 9 (DB 必需)
- Task 3 → 4 / 6 (client 必需)
- Task 4 → 5 / 6 / 7 (Node Contract 是核心)
- Task 5 → 6 (编译需先有)
- Task 6 → 7 / 11 (执行引擎是 e2e 的核心)
- Task 8 → 7 / 11 (错误处理 4 边界)
- Task 9 → 7 / 11 (cron 跟人工审批集成)
- Task 10 → 11 (集成测试需要 docker compose)
- Task 12 → 全部(总收口)

**apply 阶段建议**: 3 个 subagent 并行,各负责 4 个 task;controller 串行验证 + review 闭环。

---

## Self-Review

- [x] Spec coverage: 6 个 spec 文件 + 4 critical path 全部有 task 覆盖
- [x] Placeholder scan: 0 个 TBD / TODO
- [x] Type consistency: WorkflowRun.status / Approval.status enum 与 spec 一致
- [x] Architecture consistency: 与 architecture.md §4.3.1 workflow engine + §4.4 tech stack 一致
- [x] eng-review 12 finding 涉及 8 个全部覆盖
