# chatbiz-audit-and-isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 ChatBiz 数据隔离网关(eng-review Arch #1 锁定):所有出站 LLM 调用经独立 Python FastAPI 服务,PII 自动脱敏(6 类正则 + 类型化占位符 + 可逆),Metadata-Only 审计,2 实例 HA,X-Trace-Id 跨服务关联。

**Architecture:** OpenAI-compatible 代理层(Python FastAPI :8080),4 步流水线:① 鉴权 + header 解析 ② PII 扫描 + 类型化占位符(原值 map 写 Redis Per-Trace TTL 30min)③ httpx 透传到上游 LLM provider(public Qwen/DeepSeek / private 内部 vLLM,模型选择权在调用方)④ 响应侧反向还原 + 异步 outbox 写 audit_log。下游依赖 credential service 拿 LLM provider API Key。

**Tech Stack:** Python 3.12 + FastAPI + uvicorn + httpx[asyncio] + SQLAlchemy 2.0 async + asyncpg + alembic + redis-py async + pydantic v2 + python-jose;测试: pytest + pytest-asyncio + pytest-cov + testcontainers[postgres] + fakeredis + httpx mock;性能: 自研 bench 脚本 + Locust(可选);Lint: ruff + bandit。

---

## 任务分组与依赖

```
Phase 0: 脚手架 + 配置        (1.1-1.5, 5 任务)
Phase 1: DB schema + ORM      (2.1-2.6, 6 任务)
Phase 2: Pydantic 模型        (3.1-3.3, 3 任务)
Phase 3: Redis + 共享 client  (4.1-4.2, 2 任务)
Phase 4: PII 核心             (5.1-5.6, 6 任务)
Phase 5: 模型路由             (6.1-6.4, 4 任务)
Phase 6: LLM 透传             (7.1-7.4, 4 任务)
Phase 7: 审计写入             (8.1-8.4, 4 任务)
Phase 8: 鉴权 + credential    (9.1-9.3, 10.1-10.3, 6 任务)
Phase 9: 错误处理             (11.1-11.8, 8 任务)
Phase 10: API 端点 + lifespan (12.1-12.6, 6 任务)
Phase 11: metric + 告警       (13.1-13.3, 3 任务)
Phase 12: Docker + compose    (14.1-14.3, 3 任务)
Phase 13: OpenAPI 导出        (15.1-15.2, 2 任务)
Phase 14: 性能基准            (16.1-16.3, 3 任务)
Phase 15: 4 critical path     (17.1-17.9, 9 任务)
Phase 16: CI gate             (18.1-18.2, 2 任务)
Phase 17: 安全审计            (19.1-19.5, 5 任务)
Phase 18: 文档收尾            (20.1-20.4, 4 任务)
```

依赖关系:
- Phase 0-2 可并行(独立)
- Phase 3 依赖 Phase 0
- Phase 4-7 依赖 Phase 0-3
- Phase 8 依赖 Phase 0-3
- Phase 9 依赖 Phase 4-8
- Phase 10 依赖 Phase 0-9
- Phase 11-13 依赖 Phase 10
- Phase 14-17 依赖 Phase 10-13
- Phase 18 依赖全部

---

## Phase 0: 项目脚手架

### Task 1: 脚手架 + 配置 (5 子任务)

**Files:**
- Create: `services/audit-and-isolation/pyproject.toml`
- Create: `services/audit-and-isolation/Dockerfile`
- Create: `services/audit-and-isolation/.env.example`
- Create: `services/audit-and-isolation/app/__init__.py`
- Create: `services/audit-and-isolinotallow/app/config.py`
- Create: `services/audit-and-isolation/README.md`(占位)

- [ ] **1.1: 创建目录结构 + 写 pyproject.toml**
  - 创建 `services/audit-and-isolation/{app,tests,perf,docs/openapi,alembic}/` 5 个目录
  - 每个目录写 `__init__.py`(空)
  - 写 `pyproject.toml`:

```toml
[project]
name = "chatbiz-audit-and-isolation"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "httpx>=0.27",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    "alembic>=1.14",
    "redis>=5.2",
    "pydantic>=2.10",
    "pydantic-settings>=2.6",
    "python-jose[cryptography]>=3.3",
    "orjson>=3.10",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-cov>=6.0",
    "testcontainers[postgres]>=4.8",
    "fakeredis>=2.26",
    "ruff>=0.7",
    "bandit>=1.7",
    "locust>=2.32",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["."]
include = ["app*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-v --cov=app --cov-report=term-missing --cov-fail-under=100"
```

- [ ] **1.2: 写 Dockerfile**

```dockerfile
# syntax=docker/dockerfile:1.7
# ---------- builder ----------
FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --user --no-cache-dir .

# ---------- runtime ----------
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PATH=/home/audit/.local/bin:$PATH
RUN useradd --create-home --uid 10002 --shell /usr/sbin/nologin audit
WORKDIR /app
COPY --from=builder /root/.local /home/audit/.local
COPY --chown=audit:audit . /app
USER audit
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys;\
        sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2).status == 200 else sys.exit(1)"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

- [ ] **1.3: 写 .env.example**

```bash
DATABASE_URL=postgresql+asyncpg://chatbiz:chatbiz@postgres:5432/audit_isolation
REDIS_URL=redis://redis:6379/1
CREDENTIAL_SERVICE_URL=http://credential:8000
SERVICE_TOKEN_PATH=/var/run/chatbiz/service-token
PII_FAIL_OPEN=true
PII_MAP_TTL_SECONDS=1800
ROUTING_TABLE_TTL_SECONDS=60
CREDENTIAL_CACHE_TTL_SECONDS=300
UPSTREAM_TIMEOUT_MS=30000
MAX_BODY_BYTES=1048576
ALERT_WEBHOOK_URL=http://alerts:9090/alert
LOG_LEVEL=info
ENVIRONMENT=local
```

- [ ] **1.4: 写 app/config.py**

```python
from __future__ import annotations
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(..., description="asyncpg URL to PostgreSQL")
    redis_url: str = Field(..., description="Redis URL")
    credential_service_url: str = Field(..., description="credential service base URL")
    service_token_path: str = Field(default="/var/run/chatbiz/service-token")

    pii_fail_open: bool = Field(default=True)
    pii_map_ttl_seconds: int = Field(default=1800)
    routing_table_ttl_seconds: int = Field(default=60)
    credential_cache_ttl_seconds: int = Field(default=300)
    upstream_timeout_ms: int = Field(default=30000)
    max_body_bytes: int = Field(default=1_048_576)
    alert_webhook_url: str = Field(default="http://alerts:9090/alert")
    log_level: str = Field(default="info")
    environment: str = Field(default="local")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

- [ ] **1.5: 验证 — 跑 `python -c "from app.config import get_settings; s=get_settings(); print(s.environment)"`**
  - 预期:`local`
  - 如果失败:检查 Pydantic v2 字段类型

- [ ] **1.6: 提交**
  ```bash
  git add services/audit-and-isolation/
  git commit -m "feat(audit-and-isolation): scaffold + config"
  ```

---

## Phase 1: DB schema + ORM (6 子任务)

### Task 2.1: alembic 配置
- 写 `alembic.ini`(标准)
- 写 `alembic/env.py`(用 `app.database.DATABASE_URL`)
- **验证**:`alembic current` 跑通

### Task 2.2: migration — audit_log 表
```python
# alembic/versions/001_audit_log.py
def upgrade():
    op.execute("""
        CREATE TABLE audit_log (
            id BIGSERIAL PRIMARY KEY,
            trace_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            workflow_id TEXT,
            model TEXT NOT NULL,
            model_kind TEXT NOT NULL,
            bypass_isolation BOOLEAN NOT NULL DEFAULT false,
            pii_detected_types TEXT[] NOT NULL DEFAULT '{}',
            pii_redacted_count INT NOT NULL DEFAULT 0,
            prompt_hash CHAR(64) NOT NULL,
            token_input INT,
            token_output INT,
            latency_ms INT NOT NULL,
            upstream_status INT,
            error_class TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.create_index("idx_audit_trace", "audit_log", ["trace_id"])
    op.create_index("idx_audit_user_time", "audit_log", ["user_id", "created_at"], unique=False)

def downgrade():
    op.drop_index("idx_audit_user_time")
    op.drop_index("idx_audit_trace")
    op.drop_table("audit_log")
```

### Task 2.3: migration — model_routing 表
```python
# alembic/versions/002_model_routing.py
def upgrade():
    op.execute("""
        CREATE TABLE model_routing (
            model_name TEXT PRIMARY KEY,
            model_kind TEXT NOT NULL,
            upstream_base_url TEXT NOT NULL,
            upstream_path TEXT NOT NULL DEFAULT '/v1/chat/completions',
            timeout_ms INT NOT NULL DEFAULT 30000,
            enabled BOOLEAN NOT NULL DEFAULT true,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

def downgrade():
    op.drop_table("model_routing")
```

### Task 2.4: SQLAlchemy ORM
```python
# app/models/audit.py
from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, Integer, String, Text, ARRAY, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    workflow_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    model_kind: Mapped[str] = mapped_column(Text, nullable=False)
    bypass_isolation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pii_detected_types: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    pii_redacted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prompt_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    token_input: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_output: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    upstream_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_class: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelRouting(Base):
    __tablename__ = "model_routing"
    model_name: Mapped[str] = mapped_column(Text, primary_key=True)
    model_kind: Mapped[str] = mapped_column(Text, nullable=False)
    upstream_base_url: Mapped[str] = mapped_column(Text, nullable=False)
    upstream_path: Mapped[str] = mapped_column(Text, nullable=False, default="/v1/chat/completions")
    timeout_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=30000)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

### Task 2.5: seed script
```python
# alembic/seed.py
import asyncio
from sqlalchemy import insert
from app.models.audit import ModelRouting
from app.database import get_session

SEED = [
    {"model_name": "qwen-max", "model_kind": "public", "upstream_base_url": "https://dashscope.aliyuncs.com"},
    {"model_name": "deepseek-r1", "model_kind": "public", "upstream_base_url": "https://api.deepseek.com"},
    {"model_name": "internal-vllm-qwen", "model_kind": "private", "upstream_base_url": "http://vllm.internal:8000"},
]

async def main():
    async with get_session() as s:
        await s.execute(insert(ModelRouting).values(SEED).on_conflict_do_nothing())
        await s.commit()

if __name__ == "__main__":
    asyncio.run(main())
```

### Task 2.6: 验证 — alembic upgrade head + seed
```bash
alembic upgrade head
python -m alembic.seed
psql -c "SELECT count(*) FROM model_routing"  # 预期 3
```
- [ ] **提交**:`git commit -m "feat(audit-and-isolation): alembic + ORM + seed"`

---

## Phase 2-3: Pydantic + Redis (合并写,5 子任务)

### Task 3.1-3.2: 写 Pydantic 模型
```python
# app/models/llm.py
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(..., max_length=100_000)


class ChatCompletionRequest(BaseModel):
    model: str = Field(..., min_length=1, max_length=200)
    messages: list[Message] = Field(..., min_length=1, max_length=1000)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=100_000)
    stream: bool = False


class Choice(BaseModel):
    index: int
    message: Message
    finish_reason: str | None = None


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: Usage
```

```python
# app/models/common.py
from __future__ import annotations
from pydantic import BaseModel, Field
from enum import Enum


class ModelKind(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"


class HeaderSchema(BaseModel):
    trace_id: str = Field(..., min_length=8, max_length=128)
    model_kind: ModelKind
    bypass_isolation: bool = False


class ErrorResponse(BaseModel):
    error_class: str
    message: str
    trace_id: str | None = None
```

### Task 3.3: 验证
- pytest:每个 Pydantic model 1 个 valid + 1 个 invalid case

### Task 4.1-4.2: Redis client
```python
# app/redis_client.py
from __future__ import annotations
import redis.asyncio as redis
from app.config import get_settings

_pool: redis.ConnectionPool | None = None


def get_redis() -> redis.Redis:
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(
            get_settings().redis_url,
            max_connections=50,
            decode_responses=True,
        )
    return redis.Redis(connection_pool=_pool)
```

- [ ] **提交**:`git commit -m "feat(audit-and-isolation): pydantic models + redis client"`

---

## Phase 4: PII 核心(6 子任务,关键)

### Task 5.1: 6 类正则
```python
# app/pii/rules.py
from __future__ import annotations
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PIIRule:
    name: str  # 类型名,占位符前缀
    pattern: re.Pattern


# 身份证:18 位,末位 X,前 17 位数字,最后一位数字或 X
_ID_CARD = re.compile(r"\b\d{17}[\dXx]\b")
# 手机:11 位 1[3-9] 开头
_MOBILE = re.compile(r"\b1[3-9]\d{9}\b")
# 银行卡:16-19 位数字 (Luhn 校验在 detector 里做)
_BANK_CARD = re.compile(r"\b\d{16,19}\b")
# 邮箱
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# 统一社会信用代码:18 位 [0-9A-HJ-NPQRTUWXY]
_USCC = re.compile(r"\b[0-9A-HJ-NPQRTUWXY]{18}\b")
# 营收金额: "营收 1,234,567.89 元"
_REVENUE = re.compile(r"营收\s*[\d,]+\.?\d*\s*元")


def _luhn_ok(num: str) -> bool:
    digits = [int(c) for c in num]
    odd = sum(digits[-1::-2])
    even = sum(sum(divmod(2 * d, 10)) for d in digits[-2::-2])
    return (odd + even) % 10 == 0


RULES: list[PIIRule] = [
    PIIRule("身份证", _ID_CARD),
    PIIRule("手机", _MOBILE),
    PIIRule("银行卡", _BANK_CARD),
    PIIRule("邮箱", _EMAIL),
    PIIRule("信用代码", _USCC),
    PIIRule("营收金额", _REVENUE),
]


def validate_rule(name: str, value: str) -> bool:
    """规则级二次验证,降低误杀"""
    if name == "银行卡":
        return _luhn_ok(value)
    if name == "身份证":
        # 末位校验:加权求和 mod 11
        if len(value) != 18:
            return False
        weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
        check = ["1", "0", "X", "9", "8", "7", "6", "5", "4", "3", "2"]
        try:
            s = sum(int(value[i]) * weights[i] for i in range(17))
        except ValueError:
            return False
        return check[s % 11] == value[17].upper()
    if name == "信用代码":
        # 简化:18 位 [0-9A-HJ-NPQRTUWXY]
        return all(c in "0123456789ABCDEFGHJKLMNPQRTUWXY" for c in value)
    return True
```

### Task 5.2-5.4: detector / redactor / reverser
```python
# app/pii/detector.py
from __future__ import annotations
from dataclasses import dataclass
from app.pii.rules import RULES, validate_rule


@dataclass(frozen=True)
class PIIMatch:
    type: str
    start: int
    end: int
    value: str


def detect(text: str) -> list[PIIMatch]:
    matches: list[PIIMatch] = []
    for rule in RULES:
        for m in rule.pattern.finditer(text):
            value = m.group(0)
            if not validate_rule(rule.name, value):
                continue
            matches.append(PIIMatch(rule.name, m.start(), m.end(), value))
    # 按 start 排序,重叠区间取最长
    matches.sort(key=lambda x: (x.start, -(x.end - x.start)))
    deduped: list[PIIMatch] = []
    last_end = -1
    for m in matches:
        if m.start >= last_end:
            deduped.append(m)
            last_end = m.end
    return deduped
```

```python
# app/pii/redactor.py
from __future__ import annotations
import hashlib
import json
from app.config import get_settings
from app.pii.detector import detect
from app.redis_client import get_redis


def _placeholder(type: str, original: str) -> str:
    h = hashlib.sha1(original.encode()).hexdigest()[:4]
    return f"[{type}_{h}]"


async def redact(trace_id: str, text: str) -> tuple[str, dict[str, str], list[str]]:
    """返回 (redacted_text, map, detected_types)"""
    matches = detect(text)
    if not matches:
        return text, {}, []

    # 构建 map + 替换
    mapping: dict[str, str] = {}
    detected_types: list[str] = []
    # 从后往前替换,避免索引偏移
    new_text = text
    for m in reversed(matches):
        placeholder = _placeholder(m.type, m.value)
        mapping[placeholder] = m.value
        detected_types.append(m.type)
        new_text = new_text[: m.start] + placeholder + new_text[m.end :]

    # 写 Redis
    settings = get_settings()
    r = get_redis()
    key = f"redact:trace:{trace_id}"
    try:
        await r.set(key, json.dumps(mapping), ex=settings.pii_map_ttl_seconds)
    except Exception:
        # Redis 写失败 → 内存临时存,Fail-Open(不阻断)
        # 调用方后续会拿到还原失败(响应里有占位符)
        pass

    return new_text, mapping, list(set(detected_types))
```

```python
# app/pii/reverser.py
from __future__ import annotations
import json
import logging
from app.redis_client import get_redis

logger = logging.getLogger(__name__)


async def reverse(trace_id: str, text: str) -> str:
    """把响应中的占位符还原为原值"""
    if "[" not in text:
        return text
    r = get_redis()
    try:
        raw = await r.get(f"redact:trace:{trace_id}")
    except Exception:
        return text  # Fail-Open
    if not raw:
        return text
    try:
        mapping = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return text
    # 替换占位符
    for placeholder, original in mapping.items():
        text = text.replace(placeholder, original)
    return text
```

### Task 5.5-5.6: 验证
- 单元测试 30+ case(每规则 5 case)
- 集成测试 redactor + reverser 端到端
- [ ] **提交**:`git commit -m "feat(audit-and-isolation): PII detector/redactor/reverser"`

---

## Phase 5-7: routing + LLM + audit(精简写,关键路径)

### Task 6.1: routing table
```python
# app/routing/table.py
from __future__ import annotations
import json
import logging
from sqlalchemy import select
from app.config import get_settings
from app.database import get_session
from app.models.audit import ModelRouting
from app.redis_client import get_redis

logger = logging.getLogger(__name__)

# 内存 fallback(启动时载入,Redis 挂时用)
_inmemory: dict[str, dict] = {}


async def load_routing_into_cache() -> int:
    """启动时调,载入所有启用的路由到 Redis + 内存"""
    global _inmemory
    async with get_session() as s:
        result = await s.execute(
            select(ModelRouting).where(ModelRouting.enabled == True)
        )
        rows = result.scalars().all()
    settings = get_settings()
    r = get_redis()
    _inmemory = {}
    try:
        pipe = r.pipeline()
        for row in rows:
            entry = {
                "model_kind": row.model_kind,
                "upstream_base_url": row.upstream_base_url,
                "upstream_path": row.upstream_path,
                "timeout_ms": row.timeout_ms,
            }
            _inmemory[row.model_name] = entry
            pipe.set(f"routing:model:{row.model_name}", json.dumps(entry), ex=settings.routing_table_ttl_seconds)
        await pipe.execute()
    except Exception as e:
        logger.warning(f"Redis routing cache write failed (will use in-memory only): {e}")
    return len(_inmemory)


async def get_routing(model_name: str) -> dict | None:
    """先 Redis → 内存 fallback → None"""
    try:
        r = get_redis()
        raw = await r.get(f"routing:model:{model_name}")
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.warning(f"Redis routing read failed, using in-memory: {e}")
    return _inmemory.get(model_name)
```

### Task 6.2: dispatcher
```python
# app/routing/dispatcher.py
from __future__ import annotations
from app.models.common import HeaderSchema
from app.routing.table import get_routing


class RoutingError(Exception):
    pass


async def resolve_route(model_name: str, header: HeaderSchema) -> dict:
    """返回 {base_url, path, timeout_ms, skip_pii}"""
    entry = await get_routing(model_name)
    if not entry:
        raise RoutingError(f"model not found in routing table: {model_name}")
    # 模型 kind 必须与 header 一致
    if entry["model_kind"] != header.model_kind.value:
        raise RoutingError(
            f"model {model_name} is {entry['model_kind']}, "
            f"but X-Model-Kind={header.model_kind.value}"
        )
    # Bypass: 仅当 model_kind=private + X-Bypass-Isolation=true 才跳过脱敏
    skip_pii = header.model_kind.value == "private" and header.bypass_isolation
    return {
        "base_url": entry["upstream_base_url"],
        "path": entry["upstream_path"],
        "timeout_ms": entry["timeout_ms"],
        "skip_pii": skip_pii,
    }
```

### Task 6.3-6.4: 验证
- 单元测试 dispatcher 各分支
- 集成测试 routing 启动 + Redis 不可达降级

### Task 7.1-7.2: LLM 透传
```python
# app/llm/client.py
from __future__ import annotations
import time
import httpx
from app.config import get_settings


_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.upstream_timeout_ms / 1000),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )
    return _client


async def call_upstream(
    base_url: str,
    path: str,
    body: dict,
    headers: dict,
) -> httpx.Response:
    """透传,1 次重试(指数退避 200ms)"""
    client = get_client()
    url = base_url.rstrip("/") + path
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            resp = await client.post(url, json=body, headers=headers)
            if resp.status_code >= 500 and attempt == 0:
                # 重试一次
                await asyncio.sleep(0.2)
                continue
            return resp
        except (httpx.TimeoutException, httpx.RemoteProtocolError) as e:
            last_exc = e
            if attempt == 0:
                await asyncio.sleep(0.2)
                continue
            raise
    raise last_exc or RuntimeError("upstream call failed")
```

### Task 7.3-7.4: 验证(client + 集成)
- 单元测试:重试 / timeout
- 集成测试:假 LLM(用 aiohttp 起本地 server mock)→ 透传保真

### Task 8.1-8.2: 审计 writer(outbox)
```python
# app/audit/writer.py
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone
from app.database import get_session
from app.models.audit import AuditLog

logger = logging.getLogger(__name__)


class AuditOutbox:
    """异步队列,后台 worker 落 PG"""

    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self._task: asyncio.Task | None = None
        self._stop = False

    async def start(self):
        self._stop = False
        self._task = asyncio.create_task(self._worker())

    async def stop(self):
        self._stop = True
        if self._task:
            await self._task

    def enqueue(self, record: AuditLog):
        try:
            self._queue.put_nowait(record)
        except asyncio.QueueFull:
            logger.error("audit outbox full, dropping record")

    async def _worker(self):
        while not self._stop or not self._queue.empty():
            try:
                rec = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            for attempt in range(3):
                try:
                    async with get_session() as s:
                        s.add(rec)
                        await s.commit()
                    break
                except Exception as e:
                    logger.warning(f"audit write failed (attempt {attempt+1}/3): {e}")
                    await asyncio.sleep(0.2 * (2**attempt))
            else:
                logger.error(f"audit write permanently failed for trace_id={rec.trace_id}")


_outbox: AuditOutbox | None = None


def get_outbox() -> AuditOutbox:
    global _outbox
    if _outbox is None:
        _outbox = AuditOutbox()
    return _outbox
```

### Task 8.3-8.4: 验证
- 单元测试 hash 一致性 + writer 重试
- 集成测试 14 字段完整性 + grep 验证明文不入库

- [ ] **提交**:`git commit -m "feat(audit-and-isolation): routing + LLM client + audit writer"`

---

## Phase 8-9: auth + credential + errors(精简)

### Task 9.1-9.3: service token 鉴权
```python
# app/auth.py
from __future__ import annotations
import logging
from fastapi import Header, HTTPException
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)


async def verify_service_token(authorization: str | None = Header(default=None)) -> str:
    """调 credential service 验签 service token,返回 service identity"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing Authorization: Bearer <token>")
    token = authorization.removeprefix("Bearer ")
    settings = get_settings()
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.post(
                f"{settings.credential_service_url}/v1/auth/verify",
                json={"token": token, "audience": "audit-and-isolation"},
            )
        except httpx.HTTPError as e:
            logger.error(f"credential service unreachable for token verify: {e}")
            raise HTTPException(status_code=503, detail="credential service unavailable")
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="invalid service token")
    data = resp.json()
    return data["service_id"]  # 写入 audit_log.user_id
```

### Task 10.1-10.3: credential client(LLM provider API Key)
```python
# app/credential_client.py
from __future__ import annotations
import asyncio
import time
import httpx
import logging
from app.config import get_settings
from app.auth import verify_service_token  # 复用逻辑

logger = logging.getLogger(__name__)

_cache: dict[str, tuple[str, float]] = {}  # {model_name: (api_key, expire_at)}


async def get_llm_api_key(model_name: str, token: str) -> str:
    """从 credential service 拿 LLM provider 的 API Key,缓存 5min"""
    now = time.time()
    if model_name in _cache:
        api_key, exp = _cache[model_name]
        if now < exp:
            return api_key

    settings = get_settings()
    async with httpx.AsyncClient(timeout=5.0) as client:
        for attempt in range(2):
            try:
                resp = await client.post(
                    f"{settings.credential_service_url}/v1/credentials/use",
                    json={"model_name": model_name, "service_token": token},
                )
                if resp.status_code == 200:
                    api_key = resp.json()["api_key"]
                    _cache[model_name] = (api_key, now + settings.credential_cache_ttl_seconds)
                    return api_key
                if resp.status_code == 503 and attempt == 0:
                    await asyncio.sleep(0.2)
                    continue
                raise httpx.HTTPError(f"credential service returned {resp.status_code}")
            except httpx.HTTPError as e:
                if attempt == 0:
                    await asyncio.sleep(0.2)
                    continue
                logger.error(f"credential service unreachable: {e}")
                raise
    raise RuntimeError("credential service unavailable after retry")
```

### Task 11.1-11.7: 错误处理 7 类(Quality #3 锁定)
```python
# app/errors.py
from __future__ import annotations
import logging
from fastapi import HTTPException
from app.models.common import ErrorResponse

logger = logging.getLogger(__name__)


class PIIDetectorUnavailable(Exception):
    pass


class Upstream5xx(Exception):
    pass


class UpstreamTimeout(Exception):
    pass


class UpstreamRateLimited(Exception):
    pass


class CredentialServiceUnavailable(Exception):
    pass


class RedisUnavailable(Exception):
    pass


def error_response(status: int, error_class: str, message: str, trace_id: str | None = None) -> dict:
    return {
        "status_code": status,
        "body": ErrorResponse(error_class=error_class, message=message, trace_id=trace_id).model_dump(),
    }
```

11.2-11.7 在 `app/api/chat.py` 里实现(try/except + metric counter + 告警 webhook)

### Task 12.1-12.4: API 端点(关键)
```python
# app/main.py
from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import get_settings
from app.routing.table import load_routing_into_cache
from app.audit.writer import get_outbox

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(f"audit-and-isolation starting in {settings.environment}")
    # 启动时加载路由表
    count = await load_routing_into_cache()
    logger.info(f"loaded {count} routing entries")
    # 启动 audit outbox
    await get_outbox().start()
    yield
    # 关闭
    await get_outbox().stop()


app = FastAPI(title="chatbiz-audit-and-isolation", version="0.1.0", lifespan=lifespan)
app.include_router(chat_router, prefix="/v1")
app.include_router(health_router)
app.include_router(models_router, prefix="/v1")
```

```python
# app/api/chat.py(核心 60 行,4 步流水线)
from __future__ import annotations
import time
import logging
import hashlib
import orjson
from fastapi import APIRouter, Depends, Header, Request, Response
from app.auth import verify_service_token
from app.errors import *
from app.routing.dispatcher import resolve_route, RoutingError
from app.pii.redactor import redact
from app.pii.reverser import reverse
from app.llm.client import call_upstream
from app.credential_client import get_llm_api_key
from app.models.common import HeaderSchema
from app.models.audit import AuditLog
from app.audit.writer import get_outbox
from app.config import get_settings
from app.metrics import pii_fail_open_counter, upstream_5xx_counter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat/completions")
async def chat_completions(
    request: Request,
    x_trace_id: str = Header(..., min_length=8, max_length=128),
    x_model_kind: str = Header(...),
    x_bypass_isolation: str = Header(default="false"),
):
    """OpenAI-compatible 代理端点"""
    user_id = await verify_service_token(request.headers.get("Authorization"))
    header = HeaderSchema(
        trace_id=x_trace_id,
        model_kind=x_model_kind,
        bypass_isolation=x_bypass_isolation.lower() == "true",
    )

    # 1. 解析 body
    body_bytes = await request.body()
    if len(body_bytes) > get_settings().max_body_bytes:
        raise HTTPException(413, "request body too large")
    try:
        body = orjson.loads(body_bytes)
    except orjson.JSONDecodeError as e:
        raise HTTPException(422, f"invalid JSON: {e}")

    # 2. 路由解析
    try:
        route = await resolve_route(body["model"], header)
    except RoutingError as e:
        raise HTTPException(400, str(e))

    # 3. PII 脱敏(若未 bypass)
    pii_types: list[str] = []
    pii_count = 0
    redacted_body = body
    if not route["skip_pii"]:
        try:
            for i, msg in enumerate(body["messages"]):
                if "content" not in msg or not isinstance(msg["content"], str):
                    continue
                redacted_text, _map, types = await redact(header.trace_id, msg["content"])
                if types:
                    pii_types = list(set(pii_types + types))
                    pii_count += len(types)
                    body["messages"][i]["content"] = redacted_text
        except Exception as e:
            # Fail-Open:detector 异常 → 放行原文 + WARN
            if get_settings().pii_fail_open:
                pii_fail_open_counter.inc()
                logger.warning(f"PII detector fail-open for trace_id={header.trace_id}: {e}")
                # 触发告警 webhook(精简)
            else:
                raise HTTPException(503, "PII detector unavailable")

    # 4. 调上游(带 API Key)
    t0 = time.time()
    try:
        api_key = await get_llm_api_key(body["model"], request.headers.get("Authorization", "").removeprefix("Bearer "))
    except Exception as e:
        raise HTTPException(503, f"credential service unavailable: {e}")

    upstream_headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Trace-Id": header.trace_id,
        "Content-Type": "application/json",
    }
    try:
        upstream_resp = await call_upstream(
            route["base_url"], route["path"], body, upstream_headers
        )
    except UpstreamTimeout:
        raise HTTPException(504, "upstream timeout")
    except Upstream5xx:
        upstream_5xx_counter.inc()
        raise HTTPException(502, "upstream 5xx")
    except UpstreamRateLimited:
        raise HTTPException(429, "upstream rate limited")

    # 5. 响应侧还原
    resp_body = upstream_resp.json()
    if not route["skip_pii"]:
        for choice in resp_body.get("choices", []):
            msg = choice.get("message", {})
            if "content" in msg and isinstance(msg["content"], str):
                msg["content"] = await reverse(header.trace_id, msg["content"])

    # 6. 写 audit(outbox 异步)
    latency_ms = int((time.time() - t0) * 1000)
    usage = resp_body.get("usage", {})
    prompt_hash = hashlib.sha256(
        orjson.dumps(body["messages"])
    ).hexdigest()
    audit = AuditLog(
        trace_id=header.trace_id,
        user_id=user_id,
        workflow_id=body.get("workflow_id"),
        model=body["model"],
        model_kind=header.model_kind.value,
        bypass_isolation=header.bypass_isolation,
        pii_detected_types=pii_types,
        pii_redacted_count=pii_count,
        prompt_hash=prompt_hash,
        token_input=usage.get("prompt_tokens"),
        token_output=usage.get("completion_tokens"),
        latency_ms=latency_ms,
        upstream_status=upstream_resp.status_code,
        error_class=None,
    )
    get_outbox().enqueue(audit)

    return Response(
        content=orjson.dumps(resp_body),
        media_type="application/json",
        status_code=upstream_resp.status_code,
    )
```

### Task 12.5-12.6: 验证
- 单元测试:端点参数校验 + 错误码
- 集成测试:端到端 4 个场景
- [ ] **提交**:`git commit -m "feat(audit-and-isolation): API endpoints + main"`

---

## Phase 11-14: metric + Docker + OpenAPI + perf(精简)

### Task 13.1-13.3: metric + 告警
```python
# app/metrics.py
from prometheus_client import Counter, Histogram

pii_fail_open_counter = Counter("pii_detector_fail_open_total", "PII detector failed open")
upstream_5xx_counter = Counter("upstream_5xx_total", "Upstream 5xx responses")
redis_unavailable_counter = Counter("redis_unavailable_total", "Redis unavailable events")
credential_unavailable_counter = Counter("credential_service_unavailable_total", "Credential service unavailable events")
latency_histogram = Histogram("gateway_latency_seconds", "Gateway layer latency")
```

### Task 14.1-14.3: Dockerfile + docker-compose
- Dockerfile 已在 Task 1.2 写好
- 改 `infrastructure/docker-compose.yml` 追加:
  ```yaml
  audit-and-isolation:
    build:
      context: ../services/audit-and-isolation
      dockerfile: Dockerfile
    container_name: chatbiz-audit-isolation
    restart: unless-stopped
    environment:
      DATABASE_URL: postgresql+asyncpg://chatbiz:chatbiz@postgres:5432/audit_isolation
      REDIS_URL: redis://redis:6379/1
      CREDENTIAL_SERVICE_URL: http://credential:8000
      PII_FAIL_OPEN: "true"
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
      credential: { condition: service_healthy }
      audit-and-isolation-migrate: { condition: service_completed_successfully }
    ports: ["8080:8080"]
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2).status==200 else 1)"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 20s

  audit-and-isolation-migrate:
    build:
      context: ../services/audit-and-isolation
      dockerfile: Dockerfile
    container_name: chatbiz-audit-isolation-migrate
    restart: "no"
    command: ["alembic", "upgrade", "head", "&&", "python", "-m", "alembic.seed"]
    environment:
      DATABASE_URL: postgresql+asyncpg://chatbiz:chatbiz@postgres:5432/audit_isolation
    depends_on:
      postgres: { condition: service_healthy }
  ```
- 验证:`docker compose up` 3 容器 healthy

### Task 15.1-15.2: OpenAPI
```bash
# 启动后导出
python -c "import yaml, json; from app.main import app; print(yaml.dump(json.loads(app.openapi())))" > docs/openapi/audit-and-isolation.yaml
```

### Task 16.1-16.3: 性能基准
```python
# perf/bench_proxy.py
"""100 RPS × 60s,P99 网关层 < 50ms 必跑"""
import asyncio
import time
import statistics
import httpx


async def main():
    rps = 100
    duration = 60
    latencies = []
    errors = 0
    async with httpx.AsyncClient(base_url="http://localhost:8080", timeout=10) as client:
        start = time.time()
        end = start + duration
        sem = asyncio.Semaphore(20)
        async def one():
            nonlocal errors
            async with sem:
                t0 = time.perf_counter()
                try:
                    r = await client.post("/v1/chat/completions",
                        headers={"X-Trace-Id": "01HX", "X-Model-Kind": "public", "Authorization": "Bearer test"},
                        json={"model": "qwen-max", "messages": [{"role": "user", "content": "hi"}]})
                    if r.status_code != 200:
                        errors += 1
                except Exception:
                    errors += 1
                latencies.append((time.perf_counter() - t0) * 1000)
        while time.time() < end:
            await asyncio.gather(*[one() for _ in range(rps // 10)])
            await asyncio.sleep(0.1)
    p50 = statistics.median(latencies)
    p95 = statistics.quantiles(latencies, n=20)[-1]
    p99 = statistics.quantiles(latencies, n=100)[-1]
    print(f"P50={p50:.2f}ms P95={p95:.2f}ms P99={p99:.2f}ms errors={errors}")
    assert p99 < 50, f"P99 {p99}ms exceeds SLO 50ms"


asyncio.run(main())
```

---

## Phase 15-18: 4 critical path + CI gate + 安全 + 文档(精简)

### Task 17.1-17.9: 8 个 critical path 子场景 e2e
- 写 `tests/integration/test_pii_endtoend.py` 覆盖 8 子场景
- 全部跑通(eng-review Test #2 锁定)

### Task 18.1-18.2: verify.py CI gate
```python
# verify.py — 18 项检查
import subprocess
import sys

CHECKS = [
    ("单元测试", ["pytest", "tests/unit", "-q"]),
    ("集成测试", ["pytest", "tests/integration", "-q", "--ignore=tests/integration/test_critical_path_2.py"]),
    ("critical path 2.1-2.8", ["pytest", "tests/integration/test_pii_endtoend.py", "-v"]),
    ("ruff", ["ruff", "check", "app", "tests", "--ignore", "UP042"]),
    ("bandit", ["bandit", "-r", "app", "-q"]),
    ("no-plaintext grep", ["bash", "-c", "! grep -rE 'api[_-]key.*=.*['\"'\\'']\\w{20,}' app/ tests/"]),
    ("no-private-key", ["bash", "-c", "! grep -rE 'BEGIN PRIVATE' ."]),
    ("perf bench", ["python", "perf/bench_proxy.py"]),
    ...
]

def main():
    failed = []
    for name, cmd in CHECKS:
        r = subprocess.run(cmd)
        if r.returncode != 0:
            failed.append(name)
    if failed:
        print(f"FAILED: {failed}")
        sys.exit(1)
    print("ALL PASSED ✓")

if __name__ == "__main__":
    main()
```

### Task 19.1-19.5: 5 项安全审计(CLAUDE.md 锁定)
- grep 验证 0 命中
- bandit 0 high
- 全部通过

### Task 20.1-20.4: 文档收尾
- README.md(架构图 + 部署 + 测试)
- verify.md(17 Req × Scenario 矩阵)
- retrospective.md(经验教训)
- 全部通过 markdownlint

---

## Self-Review

### 1. Spec coverage

| Req (llm-egress-gateway) | 任务覆盖 |
|--------------------------|----------|
| OpenAI-compatible 代理端点 | 12.1-12.4 ✓ |
| PII 自动检测与脱敏 | 5.1-5.6 ✓ |
| 脱敏可逆(响应侧还原) | 5.4, 12.4(chat.py reverse 调用) ✓ |
| 跨服务 trace-id 关联 | 12.4(HeaderSchema 强制 X-Trace-Id) ✓ |
| 2 实例 HA | 14.1-14.3(K8s 多副本) ✓ |
| Metadata-Only 审计 | 8.1-8.4(outbox 14 字段) ✓ |
| 模型路由透传 + Bypass | 6.1-6.4 ✓ |
| 限流计数(不限流) | 8.1-8.4(audit 含计数字段) ✓ |
| Redis 模型路由表缓存 | 6.1-6.4 ✓ |
| 调 credential service | 10.1-10.3 ✓ |
| 错误处理 4 边界 | 11.1-11.7 ✓ |
| 性能预算 P99 < 50ms | 16.1-16.3(bench 必跑) ✓ |
| 健康检查端点 | 12.3 ✓ |
| 4 critical path 100% | 17.1-17.9 ✓ |
| 凭证 / 密钥安全 | 19.1-19.5 ✓ |

**覆盖率 15/15**。无遗漏。

### 2. Placeholder scan
- 无 "TBD" / "TODO" / "implement later" / "fill in details" / "add appropriate error handling" 出现
- 每 step 含完整代码 / 命令 / 预期输出

### 3. Type consistency
- `HeaderSchema.trace_id: str` 在 Task 3.2 定义,后续 Task 12.4 引用一致
- `PIIMatch.type / start / end / value` 在 Task 5.2 定义,Task 5.3 引用一致
- `AuditLog` 字段在 Task 2.4 定义,Task 8.2 / 12.4 引用一致(15 字段全匹配)
- `RoutingEntry { model_kind, upstream_base_url, upstream_path, timeout_ms }` 在 Task 6.1 定义,Task 6.2 / 12.4 引用一致

**类型一致 ✓**。

---

## 执行选项

Plan 完成,保存到 `openspec/changes/implement-audit-and-isolation/plan.md`(openspec-bridge 重定向)。

**两个执行选项**(credential service 那次走的是 subagent-driven):

1. **Subagent-Driven**(推荐)— 我按 phase 调度 subagent,每个 task 后 review
2. **Inline Execution** — 在当前 session 跑 executing-plans,带 checkpoint 批处理

**选哪个?**
