# audit-and-isolation 100% 覆盖率 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `services/audit-and-isolation` 的 `app` 包在真实测试下达到 100% pytest-cov 覆盖，并把该覆盖率门禁纳入 `verify.py`。

**Architecture:** 本计划采用缺口驱动的 TDD：先为未覆盖模块写失败/覆盖缺口测试，再用最小实现或最小 pragma 处理不可达防御行。测试只 mock 外部边界（PG/Redis/credential/upstream LLM），不重写网关架构、不改变 PII/路由/API 语义。

**Tech Stack:** Python 3.12/3.13、FastAPI、pytest、pytest-cov、pytest-asyncio、unittest、AsyncMock、respx、fakeredis、SQLAlchemy async、httpx。

---

## File Structure

**新增测试文件：**

- `services/audit-and-isolation/tests/unit/test_api_health.py` — 覆盖 `app/api/health.py` 的 liveness/readiness 成功和失败分支。
- `services/audit-and-isolation/tests/unit/test_api_models.py` — 覆盖 `app/api/models.py` 的 enabled-only、timestamp fallback/UTC 分支。
- `services/audit-and-isolation/tests/unit/test_main_lifespan.py` — 覆盖 FastAPI lifespan startup/shutdown 与 routing load fail-open。
- `services/audit-and-isolation/tests/unit/test_database.py` — 覆盖 lazy engine/session、get_session 成功/异常、dispose。
- `services/audit-and-isolation/tests/unit/test_redis_client.py` — 覆盖 Redis pool lazy init/reuse/reset。
- `services/audit-and-isolation/tests/unit/test_llm_streaming.py` — 覆盖 streaming reverse helpers。
- `services/audit-and-isolation/tests/unit/test_models_llm.py` — 覆盖 OpenAI-shaped Pydantic models。
- `services/audit-and-isolation/tests/unit/test_pii_edges.py` — 覆盖 redactor/reverser/rules 的剩余边缘分支。

**扩展现有测试文件：**

- `services/audit-and-isolation/tests/unit/test_api_chat.py` — chat pipeline 错误/skip/audit 分支。
- `services/audit-and-isolation/tests/unit/test_audit_writer.py` — AuditOutbox lifecycle 分支与 AsyncMock warning 修复。
- `services/audit-and-isolation/tests/unit/test_llm_client.py` — streaming 请求分支与不可达兜底处理验证。
- `services/audit-and-isolation/tests/unit/test_credential_client.py` — 不可达兜底处理验证。

**可能修改产品代码：**

- `services/audit-and-isolation/app/credential_client.py` — loop 后不可达兜底重构或 `# pragma: no cover`。
- `services/audit-and-isolation/app/llm/client.py` — streaming path 覆盖、loop 后不可达兜底重构或 `# pragma: no cover`。
- `services/audit-and-isolation/app/audit/writer.py` — 如测试暴露 `s.add()` AsyncMock warning，可改测试 fake session 或最小修复测试，不优先改产品。
- `services/audit-and-isolation/verify.py` — 增加 pytest-cov 100% gate。

**OpenSpec 完成文件：**

- `openspec/changes/fix-audit-isolation-real-tests-100pct-coverage/verify.md`
- `openspec/changes/fix-audit-isolation-real-tests-100pct-coverage/retrospective.md`

---

## Task 1: Baseline 与执行目录校准

**Files:**
- Read: `services/audit-and-isolation/pyproject.toml`
- Read: `services/audit-and-isolation/tests/unit/test_api_chat.py`
- No code changes expected

- [ ] **Step 1: 进入服务目录运行 baseline**

```bash
cd /Users/paulwang/work/ChatBiz/services/audit-and-isolation
PYTHONPATH=. python3 -m pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=0
```

Expected: `127 passed` 左右，TOTAL 约 `80%`，missing lines 与 baseline 一致或更少。

- [ ] **Step 2: 保存当前 missing lines 到工作笔记**

把输出中的 coverage table 复制到本任务记录，重点跟踪：

```text
app/api/chat.py
app/api/health.py
app/api/models.py
app/audit/writer.py
app/credential_client.py
app/database.py
app/llm/client.py
app/llm/streaming.py
app/main.py
app/models/llm.py
app/pii/redactor.py
app/pii/reverser.py
app/pii/rules.py
app/redis_client.py
```

- [ ] **Step 3: 确认从仓库根运行会失败，不把根目录作为测试 cwd**

```bash
cd /Users/paulwang/work/ChatBiz
PYTHONPATH=$(pwd)/services/audit-and-isolation python3 -m pytest tests/ -v
```

Expected: fails with `file or directory not found: tests/`。记录：后续命令必须从 `services/audit-and-isolation` 执行。

---

## Task 2: 覆盖 `app/api/health.py`

**Files:**
- Create: `services/audit-and-isolation/tests/unit/test_api_health.py`
- Test target: `services/audit-and-isolation/app/api/health.py`

- [ ] **Step 1: 写 healthz 测试**

Create `tests/unit/test_api_health.py` with:

```python
"""Unit tests for app.api.health."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_healthz_returns_ok():
    from app.api.health import healthz

    assert await healthz() == {"status": "ok"}
```

- [ ] **Step 2: 运行单测确认通过**

```bash
cd /Users/paulwang/work/ChatBiz/services/audit-and-isolation
PYTHONPATH=. python3 -m pytest tests/unit/test_api_health.py -v --cov=app.api.health --cov-report=term-missing --cov-fail-under=0
```

Expected: PASS；health.py 仍有 readyz missing lines。

- [ ] **Step 3: 添加 readyz fake dependencies**

Append to `test_api_health.py`:

```python
class _FakeSession:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.executed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, stmt):
        self.executed = True
        if self.fail:
            raise RuntimeError("pg down")
        return object()


class _SessionFactory:
    def __init__(self, fail: bool = False):
        self.fail = fail

    def __call__(self):
        return _FakeSession(fail=self.fail)


class _FakeRedis:
    def __init__(self, fail: bool = False):
        self.fail = fail

    async def ping(self):
        if self.fail:
            raise RuntimeError("redis down")
        return True


class _FakeAsyncClient:
    def __init__(self, *args, fail: bool = False, **kwargs):
        self.fail = fail

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        if self.fail:
            raise RuntimeError("credential down")
        return object()


def _response_text(response) -> str:
    return bytes(response.body).decode("utf-8")
```

- [ ] **Step 4: 添加 readyz all-ok 测试**

Append:

```python
@pytest.mark.asyncio
async def test_readyz_all_ok(monkeypatch):
    import app.api.health as health

    monkeypatch.setattr(health, "get_session", _SessionFactory())
    monkeypatch.setattr(health.redis_client, "get_redis", lambda: _FakeRedis())
    monkeypatch.setattr(health.httpx, "AsyncClient", _FakeAsyncClient)
    monkeypatch.setitem(health._inmemory, "qwen-max", {"model": "qwen-max"})

    response = await health.readyz()

    assert response.status_code == 200
    body = _response_text(response)
    assert '"postgres": "ok"' in body
    assert '"redis": "ok"' in body
    assert '"credential_service": "ok"' in body
    assert '"routing_table": "ok"' in body
```

- [ ] **Step 5: 添加各依赖失败测试**

Append:

```python
@pytest.mark.asyncio
async def test_readyz_pg_fail(monkeypatch):
    import app.api.health as health

    monkeypatch.setattr(health, "get_session", _SessionFactory(fail=True))
    monkeypatch.setattr(health.redis_client, "get_redis", lambda: _FakeRedis())
    monkeypatch.setattr(health.httpx, "AsyncClient", _FakeAsyncClient)
    monkeypatch.setitem(health._inmemory, "qwen-max", {"model": "qwen-max"})

    response = await health.readyz()

    assert response.status_code == 503
    assert '"postgres": "fail: pg down"' in _response_text(response)


@pytest.mark.asyncio
async def test_readyz_redis_fail(monkeypatch):
    import app.api.health as health

    monkeypatch.setattr(health, "get_session", _SessionFactory())
    monkeypatch.setattr(health.redis_client, "get_redis", lambda: _FakeRedis(fail=True))
    monkeypatch.setattr(health.httpx, "AsyncClient", _FakeAsyncClient)
    monkeypatch.setitem(health._inmemory, "qwen-max", {"model": "qwen-max"})

    response = await health.readyz()

    assert response.status_code == 503
    assert '"redis": "fail: redis down"' in _response_text(response)


@pytest.mark.asyncio
async def test_readyz_credential_fail(monkeypatch):
    import app.api.health as health

    class FailingClient(_FakeAsyncClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, fail=True, **kwargs)

    monkeypatch.setattr(health, "get_session", _SessionFactory())
    monkeypatch.setattr(health.redis_client, "get_redis", lambda: _FakeRedis())
    monkeypatch.setattr(health.httpx, "AsyncClient", FailingClient)
    monkeypatch.setitem(health._inmemory, "qwen-max", {"model": "qwen-max"})

    response = await health.readyz()

    assert response.status_code == 503
    assert '"credential_service": "fail: credential down"' in _response_text(response)


@pytest.mark.asyncio
async def test_readyz_empty_routing_table(monkeypatch):
    import app.api.health as health

    monkeypatch.setattr(health, "get_session", _SessionFactory())
    monkeypatch.setattr(health.redis_client, "get_redis", lambda: _FakeRedis())
    monkeypatch.setattr(health.httpx, "AsyncClient", _FakeAsyncClient)
    health._inmemory.clear()

    response = await health.readyz()

    assert response.status_code == 503
    assert '"routing_table": "empty"' in _response_text(response)
```

- [ ] **Step 6: 验证 health.py 100%**

```bash
cd /Users/paulwang/work/ChatBiz/services/audit-and-isolation
PYTHONPATH=. python3 -m pytest tests/unit/test_api_health.py -v --cov=app.api.health --cov-report=term-missing --cov-fail-under=100
```

Expected: PASS, `app/api/health.py 100%`.

---

## Task 3: 覆盖 `app/api/models.py`

**Files:**
- Create: `services/audit-and-isolation/tests/unit/test_api_models.py`
- Test target: `services/audit-and-isolation/app/api/models.py`

- [ ] **Step 1: 写 fake result/session**

Create `tests/unit/test_api_models.py`:

```python
"""Unit tests for app.api.models."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest


@dataclass
class _RouteRow:
    model_name: str
    model_kind: str
    updated_at: datetime | None


class _Scalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _Scalars(self._rows)


class _FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.statement = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, statement):
        self.statement = statement
        return _Result(self.rows)


class _SessionFactory:
    def __init__(self, rows):
        self.session = _FakeSession(rows)

    def __call__(self):
        return self.session
```

- [ ] **Step 2: 写 timezone-aware 测试**

Append:

```python
@pytest.mark.asyncio
async def test_list_models_timezone_aware(monkeypatch):
    import app.api.models as models

    updated = datetime(2026, 6, 11, 12, 0, 0, tzinfo=timezone.utc)
    factory = _SessionFactory([_RouteRow("qwen-max", "public", updated)])
    monkeypatch.setattr(models, "get_session", factory)

    response = await models.list_models()

    assert response.object == "list"
    assert len(response.data) == 1
    assert response.data[0].id == "qwen-max"
    assert response.data[0].owned_by == "public"
    assert response.data[0].created == int(updated.timestamp())
    assert "enabled" in str(factory.session.statement)
```

- [ ] **Step 3: 写 updated_at None fallback 测试**

Append:

```python
@pytest.mark.asyncio
async def test_list_models_updated_at_none_uses_now(monkeypatch):
    import app.api.models as models

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 6, 11, 8, 30, 0, tzinfo=tz)

    factory = _SessionFactory([_RouteRow("internal-vllm", "private", None)])
    monkeypatch.setattr(models, "get_session", factory)
    monkeypatch.setattr(models, "datetime", _FixedDateTime)

    response = await models.list_models()

    assert response.data[0].id == "internal-vllm"
    assert response.data[0].owned_by == "private"
    assert response.data[0].created == int(_FixedDateTime.now(timezone.utc).timestamp())
```

- [ ] **Step 4: 写 naive datetime UTC 测试**

Append:

```python
@pytest.mark.asyncio
async def test_list_models_naive_datetime_assumes_utc(monkeypatch):
    import app.api.models as models

    naive = datetime(2026, 6, 11, 9, 0, 0)
    factory = _SessionFactory([_RouteRow("deepseek-chat", "public", naive)])
    monkeypatch.setattr(models, "get_session", factory)

    response = await models.list_models()

    expected = naive.replace(tzinfo=timezone.utc)
    assert response.data[0].created == int(expected.timestamp())
```

- [ ] **Step 5: 写 empty list 测试**

Append:

```python
@pytest.mark.asyncio
async def test_list_models_empty(monkeypatch):
    import app.api.models as models

    monkeypatch.setattr(models, "get_session", _SessionFactory([]))

    response = await models.list_models()

    assert response.object == "list"
    assert response.data == []
```

- [ ] **Step 6: 验证 models.py 100%**

```bash
cd /Users/paulwang/work/ChatBiz/services/audit-and-isolation
PYTHONPATH=. python3 -m pytest tests/unit/test_api_models.py -v --cov=app.api.models --cov-report=term-missing --cov-fail-under=100
```

Expected: PASS, `app/api/models.py 100%`.

---

## Task 4: 覆盖 `app/main.py` lifespan

**Files:**
- Create: `services/audit-and-isolation/tests/unit/test_main_lifespan.py`
- Test target: `services/audit-and-isolation/app/main.py`

- [ ] **Step 1: 写 fake outbox**

Create `tests/unit/test_main_lifespan.py`:

```python
"""Unit tests for FastAPI lifespan."""
from __future__ import annotations

import pytest


class _FakeOutbox:
    def __init__(self):
        self.started = False
        self.stopped = False

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True
```

- [ ] **Step 2: 写 startup/shutdown 成功测试**

Append:

```python
@pytest.mark.asyncio
async def test_lifespan_loads_routing_starts_outbox_and_disposes(monkeypatch):
    import app.main as main

    calls = []
    outbox = _FakeOutbox()

    async def fake_load():
        calls.append("load")
        return 2

    async def fake_dispose():
        calls.append("dispose")

    monkeypatch.setattr(main, "load_routing_into_cache", fake_load)
    monkeypatch.setattr(main, "get_outbox", lambda: outbox)
    monkeypatch.setattr(main, "dispose_engine", fake_dispose)

    async with main.lifespan(main.app):
        assert outbox.started is True
        assert calls == ["load"]

    assert outbox.stopped is True
    assert calls == ["load", "dispose"]
```

- [ ] **Step 3: 写 routing load 失败仍启动测试**

Append:

```python
@pytest.mark.asyncio
async def test_lifespan_continues_when_routing_load_fails(monkeypatch):
    import app.main as main

    calls = []
    outbox = _FakeOutbox()

    async def fake_load():
        calls.append("load")
        raise RuntimeError("db down")

    async def fake_dispose():
        calls.append("dispose")

    monkeypatch.setattr(main, "load_routing_into_cache", fake_load)
    monkeypatch.setattr(main, "get_outbox", lambda: outbox)
    monkeypatch.setattr(main, "dispose_engine", fake_dispose)

    async with main.lifespan(main.app):
        assert outbox.started is True
        assert calls == ["load"]

    assert outbox.stopped is True
    assert calls == ["load", "dispose"]
```

- [ ] **Step 4: 验证 main.py 100%**

```bash
cd /Users/paulwang/work/ChatBiz/services/audit-and-isolation
PYTHONPATH=. python3 -m pytest tests/unit/test_main_lifespan.py -v --cov=app.main --cov-report=term-missing --cov-fail-under=100
```

Expected: PASS, `app/main.py 100%`.

---

## Task 5: 覆盖 `app/database.py`

**Files:**
- Create: `services/audit-and-isolation/tests/unit/test_database.py`
- Test target: `services/audit-and-isolation/app/database.py`

- [ ] **Step 1: 读取 database.py 确认变量名**

Open `app/database.py` and confirm module globals. Expected names likely include `_engine`, `_SessionLocal`, `get_session`, `dispose_engine`.

- [ ] **Step 2: 写测试 reset fixture**

Create `tests/unit/test_database.py`:

```python
"""Unit tests for app.database lazy engine/session helpers."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def reset_database_module(monkeypatch):
    import app.database as db

    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(db, "_SessionLocal", None)
    yield
    db._engine = None
    db._SessionLocal = None
```

If actual names differ, adjust fixture to exact names from `app/database.py`.

- [ ] **Step 3: 写 fake engine/session factory**

Append:

```python
class _FakeEngine:
    def __init__(self):
        self.disposed = False

    async def dispose(self):
        self.disposed = True


class _FakeSession:
    def __init__(self, fail_enter: bool = False):
        self.fail_enter = fail_enter
        self.closed = False

    async def __aenter__(self):
        if self.fail_enter:
            raise RuntimeError("session enter failed")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.closed = True
        return False


class _FakeSessionFactory:
    def __init__(self, fail_enter: bool = False):
        self.fail_enter = fail_enter
        self.sessions = []

    def __call__(self):
        session = _FakeSession(fail_enter=self.fail_enter)
        self.sessions.append(session)
        return session
```

- [ ] **Step 4: 写 lazy engine/session 测试**

Append after adapting exact function names:

```python
def test_get_engine_lazy_and_cached(monkeypatch):
    import app.database as db

    created = []

    def fake_create_async_engine(url, **kwargs):
        engine = _FakeEngine()
        created.append((url, kwargs, engine))
        return engine

    monkeypatch.setattr(db, "create_async_engine", fake_create_async_engine)

    e1 = db._get_engine()
    e2 = db._get_engine()

    assert e1 is e2
    assert len(created) == 1


def test_get_session_factory_lazy_and_cached(monkeypatch):
    import app.database as db

    fake_engine = _FakeEngine()
    monkeypatch.setattr(db, "_get_engine", lambda: fake_engine)

    factories = []

    def fake_async_sessionmaker(engine, **kwargs):
        factories.append((engine, kwargs))
        return _FakeSessionFactory()

    monkeypatch.setattr(db, "async_sessionmaker", fake_async_sessionmaker)

    f1 = db._get_session_factory()
    f2 = db._get_session_factory()

    assert f1 is f2
    assert factories[0][0] is fake_engine
    assert len(factories) == 1
```

- [ ] **Step 5: 写 get_session 成功/异常与 dispose 测试**

Append:

```python
@pytest.mark.asyncio
async def test_get_session_yields_session_and_closes(monkeypatch):
    import app.database as db

    factory = _FakeSessionFactory()
    monkeypatch.setattr(db, "_get_session_factory", lambda: factory)

    async with db.get_session() as session:
        assert session is factory.sessions[0]

    assert factory.sessions[0].closed is True


@pytest.mark.asyncio
async def test_get_session_propagates_enter_exception(monkeypatch):
    import app.database as db

    factory = _FakeSessionFactory(fail_enter=True)
    monkeypatch.setattr(db, "_get_session_factory", lambda: factory)

    with pytest.raises(RuntimeError, match="session enter failed"):
        async with db.get_session():
            pass


@pytest.mark.asyncio
async def test_dispose_engine_when_uninitialized():
    import app.database as db

    await db.dispose_engine()

    assert db._engine is None
    assert db._SessionLocal is None


@pytest.mark.asyncio
async def test_dispose_engine_disposes_and_resets(monkeypatch):
    import app.database as db

    engine = _FakeEngine()
    db._engine = engine
    db._SessionLocal = object()

    await db.dispose_engine()

    assert engine.disposed is True
    assert db._engine is None
    assert db._SessionLocal is None
```

- [ ] **Step 6: 验证 database.py 100%**

```bash
cd /Users/paulwang/work/ChatBiz/services/audit-and-isolation
PYTHONPATH=. python3 -m pytest tests/unit/test_database.py -v --cov=app.database --cov-report=term-missing --cov-fail-under=100
```

Expected: PASS, `app/database.py 100%`。If names differ, update tests to match actual module names, not production code.

---

## Task 6: 覆盖 `app/redis_client.py`

**Files:**
- Create: `services/audit-and-isolation/tests/unit/test_redis_client.py`
- Test target: `services/audit-and-isolation/app/redis_client.py`

- [ ] **Step 1: 写 fake Redis/Pool 测试**

Create `tests/unit/test_redis_client.py`:

```python
"""Unit tests for app.redis_client."""
from __future__ import annotations


class _FakePool:
    def __init__(self, url):
        self.url = url


class _FakeRedis:
    def __init__(self, connection_pool):
        self.connection_pool = connection_pool
```

- [ ] **Step 2: 写 lazy pool/reuse 测试**

Append:

```python
def test_get_redis_lazy_initializes_and_reuses_pool(monkeypatch):
    import app.redis_client as rc

    created_urls = []

    def fake_from_url(url, **kwargs):
        created_urls.append((url, kwargs))
        return _FakePool(url)

    monkeypatch.setattr(rc, "_pool", None)
    monkeypatch.setattr(rc.redis.ConnectionPool, "from_url", fake_from_url)
    monkeypatch.setattr(rc.redis, "Redis", _FakeRedis)

    r1 = rc.get_redis()
    r2 = rc.get_redis()

    assert r1.connection_pool is r2.connection_pool
    assert len(created_urls) == 1
```

- [ ] **Step 3: 写 reset 测试**

Append:

```python
def test_reset_pool_for_tests_sets_pool_none(monkeypatch):
    import app.redis_client as rc

    monkeypatch.setattr(rc, "_pool", _FakePool("redis://example"))

    rc.reset_pool_for_tests()

    assert rc._pool is None
```

- [ ] **Step 4: 验证 redis_client.py 100%**

```bash
cd /Users/paulwang/work/ChatBiz/services/audit-and-isolation
PYTHONPATH=. python3 -m pytest tests/unit/test_redis_client.py -v --cov=app.redis_client --cov-report=term-missing --cov-fail-under=100
```

Expected: PASS, `app/redis_client.py 100%`.

---

## Task 7: 覆盖 `app/models/llm.py`

**Files:**
- Create: `services/audit-and-isolation/tests/unit/test_models_llm.py`
- Test target: `services/audit-and-isolation/app/models/llm.py`

- [ ] **Step 1: 写 schema happy-path 测试**

Create `tests/unit/test_models_llm.py`:

```python
"""Unit tests for OpenAI-shaped LLM models."""
from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_chat_completion_request_defaults():
    from app.models.llm import ChatCompletionRequest, Message

    req = ChatCompletionRequest(
        model="qwen-max",
        messages=[Message(role="user", content="hello")],
    )

    assert req.model == "qwen-max"
    assert req.messages[0].role == "user"
    assert req.temperature == 0.7
    assert req.stream is False
```

- [ ] **Step 2: 写 request validation 测试**

Append:

```python
def test_message_role_validation():
    from app.models.llm import Message

    with pytest.raises(ValidationError):
        Message(role="system-admin", content="bad")


def test_request_requires_messages():
    from app.models.llm import ChatCompletionRequest

    with pytest.raises(ValidationError):
        ChatCompletionRequest(model="qwen-max", messages=[])
```

If actual model allows system role or empty messages, adapt expected assertions to actual Pydantic constraints; do not change product code just for this step.

- [ ] **Step 3: 写 response/usage defaults 测试**

Append:

```python
def test_chat_completion_response_defaults():
    from app.models.llm import ChatCompletionResponse, Choice, Message, Usage

    usage = Usage(prompt_tokens=3, completion_tokens=4, total_tokens=7)
    response = ChatCompletionResponse(
        id="chatcmpl-1",
        created=1718080000,
        model="qwen-max",
        choices=[Choice(index=0, message=Message(role="assistant", content="ok"), finish_reason="stop")],
        usage=usage,
    )

    assert response.object == "chat.completion"
    assert response.choices[0].index == 0
    assert response.choices[0].message.content == "ok"
    assert response.usage.total_tokens == 7
```

- [ ] **Step 4: 覆盖 optional usage / finish_reason 分支**

Append:

```python
def test_choice_and_usage_optional_fields():
    from app.models.llm import Choice, Message, Usage

    choice = Choice(index=1, message=Message(role="assistant", content="partial"))
    usage = Usage()

    assert choice.finish_reason is None
    assert usage.prompt_tokens is None
    assert usage.completion_tokens is None
    assert usage.total_tokens is None
```

- [ ] **Step 5: 验证 models/llm.py 100%**

```bash
cd /Users/paulwang/work/ChatBiz/services/audit-and-isolation
PYTHONPATH=. python3 -m pytest tests/unit/test_models_llm.py -v --cov=app.models.llm --cov-report=term-missing --cov-fail-under=100
```

Expected: PASS。If constraints differ, inspect `app/models/llm.py` and update tests to assert actual schema behavior.

---

## Task 8: 覆盖 `app/llm/streaming.py`

**Files:**
- Create: `services/audit-and-isolation/tests/unit/test_llm_streaming.py`
- Test target: `services/audit-and-isolation/app/llm/streaming.py`

- [ ] **Step 1: 写 async iterator helper**

Create `tests/unit/test_llm_streaming.py`:

```python
"""Unit tests for LLM streaming helpers."""
from __future__ import annotations

import pytest


async def _aiter(items):
    for item in items:
        yield item
```

- [ ] **Step 2: 写 reverse_stream 测试**

Append:

```python
@pytest.mark.asyncio
async def test_reverse_stream_reverses_non_empty_chunks(monkeypatch):
    import app.llm.streaming as streaming

    calls = []

    async def fake_reverse(trace_id, text):
        calls.append((trace_id, text))
        return text.replace("[身份证_a1b2]", "110101199001011234")

    monkeypatch.setattr(streaming, "reverse", fake_reverse)

    chunks = ["客户 ", "[身份证_a1b2]", ""]
    result = [chunk async for chunk in streaming.reverse_stream("trace-1234", _aiter(chunks))]

    assert result == ["客户 ", "110101199001011234", ""]
    assert calls == [("trace-1234", "客户 "), ("trace-1234", "[身份证_a1b2]")]
```

- [ ] **Step 3: 写 buffer_and_reverse 测试**

Append:

```python
@pytest.mark.asyncio
async def test_buffer_and_reverse_joins_chunks_once(monkeypatch):
    import app.llm.streaming as streaming

    calls = []

    async def fake_reverse(trace_id, text):
        calls.append((trace_id, text))
        return text.replace("[手机_b3c4]", "13800138000")

    monkeypatch.setattr(streaming, "reverse", fake_reverse)

    result = await streaming.buffer_and_reverse("trace-5678", _aiter(["手机 ", "[手机_b3c4]"]))

    assert result == "手机 13800138000"
    assert calls == [("trace-5678", "手机 [手机_b3c4]")]
```

- [ ] **Step 4: 写 empty stream 测试**

Append:

```python
@pytest.mark.asyncio
async def test_buffer_and_reverse_empty_stream(monkeypatch):
    import app.llm.streaming as streaming

    calls = []

    async def fake_reverse(trace_id, text):
        calls.append((trace_id, text))
        return text

    monkeypatch.setattr(streaming, "reverse", fake_reverse)

    result = await streaming.buffer_and_reverse("trace-empty", _aiter([]))

    assert result == ""
    assert calls == [("trace-empty", "")]
```

- [ ] **Step 5: 验证 streaming.py 100%**

```bash
cd /Users/paulwang/work/ChatBiz/services/audit-and-isolation
PYTHONPATH=. python3 -m pytest tests/unit/test_llm_streaming.py -v --cov=app.llm.streaming --cov-report=term-missing --cov-fail-under=100
```

Expected: PASS, `app/llm/streaming.py 100%`.

---

## Task 9: 扩展 `AuditOutbox` lifecycle 覆盖

**Files:**
- Modify: `services/audit-and-isolation/tests/unit/test_audit_writer.py`
- Test target: `services/audit-and-isolation/app/audit/writer.py`

- [ ] **Step 1: 修复现有 AsyncMock warning 的测试 fake**

Open `tests/unit/test_audit_writer.py`。If it uses `AsyncMock` for session where `s.add(rec)` becomes async, replace that fake session with a sync `add()` method:

```python
class FakeSession:
    def __init__(self, fail_times=0):
        self.fail_times = fail_times
        self.added = []
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def add(self, rec):
        self.added.append(rec)

    async def commit(self):
        self.commits += 1
        if self.commits <= self.fail_times:
            raise RuntimeError("db transient")
```

Expected: existing audit writer tests still pass without `RuntimeWarning: coroutine ... was never awaited`.

- [ ] **Step 2: 添加 start 幂等测试**

Append to `test_audit_writer.py`:

```python
@pytest.mark.asyncio
async def test_outbox_start_is_idempotent(monkeypatch):
    from app.audit.writer import AuditOutbox

    created = []

    class _FakeTask:
        def done(self):
            return False

    def fake_create_task(coro):
        coro.close()
        task = _FakeTask()
        created.append(task)
        return task

    monkeypatch.setattr("asyncio.create_task", fake_create_task)
    outbox = AuditOutbox()

    await outbox.start()
    await outbox.start()

    assert len(created) == 1
```

- [ ] **Step 3: 添加 task done 后 restart 测试**

Append:

```python
@pytest.mark.asyncio
async def test_outbox_start_restarts_done_task(monkeypatch):
    from app.audit.writer import AuditOutbox

    created = []

    class _DoneTask:
        def done(self):
            return True

    def fake_create_task(coro):
        coro.close()
        task = _DoneTask()
        created.append(task)
        return task

    monkeypatch.setattr("asyncio.create_task", fake_create_task)
    outbox = AuditOutbox()

    await outbox.start()
    await outbox.start()

    assert len(created) == 2
```

- [ ] **Step 4: 添加 stop timeout 测试**

Append:

```python
@pytest.mark.asyncio
async def test_outbox_stop_handles_timeout(monkeypatch):
    from app.audit.writer import AuditOutbox

    class _Task:
        def done(self):
            return False

    async def fake_wait_for(task, timeout):
        raise TimeoutError()

    monkeypatch.setattr("asyncio.wait_for", fake_wait_for)
    outbox = AuditOutbox()
    outbox._task = _Task()

    await outbox.stop()

    assert outbox._task is None
```

- [ ] **Step 5: 添加 worker timeout continue 测试**

Append:

```python
@pytest.mark.asyncio
async def test_worker_timeout_continue_then_stop(monkeypatch):
    from app.audit.writer import AuditOutbox

    calls = {"count": 0}

    async def fake_wait_for(awaitable, timeout):
        awaitable.close()
        calls["count"] += 1
        if calls["count"] == 1:
            raise TimeoutError()
        outbox._stop = True
        raise TimeoutError()

    monkeypatch.setattr("asyncio.wait_for", fake_wait_for)
    outbox = AuditOutbox()
    outbox._stop = False

    await outbox._worker()

    assert calls["count"] == 2
```

If coroutine close is invalid for current awaitable, replace with `awaitable.cancel()` only if it is a Task. The goal is to avoid un-awaited coroutine warnings.

- [ ] **Step 6: 添加 singleton reset 测试**

Append:

```python
def test_get_outbox_singleton_and_reset():
    import app.audit.writer as writer

    writer.reset_outbox_for_tests()
    o1 = writer.get_outbox()
    o2 = writer.get_outbox()
    assert o1 is o2

    writer.reset_outbox_for_tests()
    o3 = writer.get_outbox()
    assert o3 is not o1
```

- [ ] **Step 7: 验证 audit writer 100% 且无 RuntimeWarning**

```bash
cd /Users/paulwang/work/ChatBiz/services/audit-and-isolation
PYTHONPATH=. python3 -m pytest tests/unit/test_audit_writer.py -v --cov=app.audit.writer --cov-report=term-missing --cov-fail-under=100
```

Expected: PASS, `app/audit/writer.py 100%`，无 `RuntimeWarning: coroutine ... was never awaited`。

---

## Task 10: PII redactor/reverser/rules 边界覆盖

**Files:**
- Create: `services/audit-and-isolation/tests/unit/test_pii_edges.py`
- Test targets: `app/pii/redactor.py`, `app/pii/reverser.py`, `app/pii/rules.py`

- [ ] **Step 1: 写 fake Redis**

Create `tests/unit/test_pii_edges.py`:

```python
"""Edge tests for PII redactor/reverser/rules."""
from __future__ import annotations

import pytest


class _FailingRedis:
    async def get(self, key):
        raise RuntimeError("redis get down")

    async def set(self, key, value, ex=None):
        raise RuntimeError("redis set down")


class _RawRedis:
    def __init__(self, raw):
        self.raw = raw

    async def get(self, key):
        return self.raw

    async def set(self, key, value, ex=None):
        self.raw = value
        return True
```

- [ ] **Step 2: 覆盖 redactor Redis set 失败 fail-open**

Append:

```python
@pytest.mark.asyncio
async def test_redact_returns_redacted_text_when_redis_set_fails(monkeypatch):
    import app.pii.redactor as redactor

    monkeypatch.setattr(redactor.redis_client, "get_redis", lambda: _FailingRedis())

    text, mapping, types = await redactor.redact("trace-edge", "客户 110101199001011234")

    assert "110101199001011234" not in text
    assert mapping
    assert "id_card" in types
```

- [ ] **Step 3: 覆盖 reverser invalid JSON**

Append:

```python
@pytest.mark.asyncio
async def test_reverse_invalid_json_map_returns_original(monkeypatch):
    import app.pii.reverser as reverser

    monkeypatch.setattr(reverser.redis_client, "get_redis", lambda: _RawRedis("not-json"))

    text = await reverser.reverse("trace-bad-json", "客户 [身份证_a1b2]")

    assert text == "客户 [身份证_a1b2]"
```

- [ ] **Step 4: 覆盖 reverser multiple placeholders**

Append:

```python
@pytest.mark.asyncio
async def test_reverse_replaces_multiple_placeholders(monkeypatch):
    import orjson
    import app.pii.reverser as reverser

    raw = orjson.dumps({"[身份证_a1b2]": "110101199001011234", "[手机_b3c4]": "13800138000"})
    monkeypatch.setattr(reverser.redis_client, "get_redis", lambda: _RawRedis(raw))

    text = await reverser.reverse("trace-many", "客户 [身份证_a1b2] 手机 [手机_b3c4]")

    assert text == "客户 110101199001011234 手机 13800138000"
```

- [ ] **Step 5: 覆盖 rules helper 剩余边界**

Append after inspecting exact helper names in `app/pii/rules.py`. If helper functions are named `_luhn_ok` and `_valid_uscc_chars`, use:

```python
def test_luhn_empty_and_non_digit_negative():
    import app.pii.rules as rules

    assert rules._luhn_ok("") is False
    assert rules._luhn_ok("abcd") is False


def test_uscc_invalid_length_or_chars_negative():
    import app.pii.rules as rules

    assert rules._uscc_ok("123") is False
    assert rules._uscc_ok("9I1234567890123456") is False
```

If actual helper names differ, adapt to the exact private helper names. Do not change product code solely for helper names.

- [ ] **Step 6: 验证 PII 相关模块覆盖**

```bash
cd /Users/paulwang/work/ChatBiz/services/audit-and-isolation
PYTHONPATH=. python3 -m pytest tests/unit/test_pii_edges.py tests/integration/test_pii_redact_reverse.py tests/unit/test_pii_rules.py -v --cov=app.pii.redactor --cov=app.pii.reverser --cov=app.pii.rules --cov-report=term-missing --cov-fail-under=100
```

Expected: PASS。If helper tests fail due actual names, inspect `app/pii/rules.py` and update only tests.

---

## Task 11: chat pipeline 错误与 skip 分支覆盖

**Files:**
- Modify: `services/audit-and-isolation/tests/unit/test_api_chat.py`
- Test target: `services/audit-and-isolation/app/api/chat.py`

- [ ] **Step 1: 添加 endpoint helper（patch imported bindings）**

Append to `test_api_chat.py` or add near existing helpers:

```python
class _FakeUpstreamResponse:
    status_code = 200

    def __init__(self, body=None):
        self._body = body or {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2},
        }

    def json(self):
        return self._body


class _CaptureOutbox:
    def __init__(self):
        self.records = []

    def enqueue(self, record):
        self.records.append(record)


def _valid_headers():
    return {
        "Authorization": "Bearer svc-token",
        "X-Trace-Id": "trace-chat-1234",
        "X-Model-Kind": "public",
    }


def _valid_body():
    return {"model": "qwen-max", "messages": [{"role": "user", "content": "hello"}]}
```

- [ ] **Step 2: 添加 missing model 测试**

```python
def test_missing_model_returns_422(client, monkeypatch):
    import app.api.chat as chat

    async def fake_verify(auth):
        return "svc-audit"

    monkeypatch.setattr(chat, "verify_service_token", fake_verify)

    response = client.post("/v1/chat/completions", headers=_valid_headers(), json={"messages": []})

    assert response.status_code == 422
    assert "missing 'model'" in response.text
```

- [ ] **Step 3: 添加 invalid header 测试**

```python
def test_invalid_model_kind_returns_422(client, monkeypatch):
    import app.api.chat as chat

    async def fake_verify(auth):
        return "svc-audit"

    headers = _valid_headers()
    headers["X-Model-Kind"] = "external"
    monkeypatch.setattr(chat, "verify_service_token", fake_verify)

    response = client.post("/v1/chat/completions", headers=headers, json=_valid_body())

    assert response.status_code == 422
    assert "invalid header" in response.text
```

- [ ] **Step 4: 添加 PII skip message content 分支测试**

```python
def test_messages_without_string_content_are_skipped(client, monkeypatch):
    import app.api.chat as chat

    calls = {"redact": 0}
    outbox = _CaptureOutbox()

    async def fake_verify(auth):
        return "svc-audit"

    async def fake_route(model, header):
        return {"base_url": "https://llm.example", "path": "/chat", "skip_pii": False}

    async def fake_redact(trace_id, text):
        calls["redact"] += 1
        return text, {}, []

    async def fake_key(model, token):
        return "fake-key"

    async def fake_upstream(base_url, path, body, headers):
        assert body["messages"][0] == {"role": "user"}
        assert body["messages"][1]["content"] == {"not": "string"}
        assert body["messages"][2]["content"] == "hello"
        return _FakeUpstreamResponse()

    monkeypatch.setattr(chat, "verify_service_token", fake_verify)
    monkeypatch.setattr(chat, "resolve_route", fake_route)
    monkeypatch.setattr(chat, "redact", fake_redact)
    monkeypatch.setattr(chat, "get_llm_api_key", fake_key)
    monkeypatch.setattr(chat, "call_upstream", fake_upstream)
    monkeypatch.setattr(chat, "get_outbox", lambda: outbox)

    body = {"model": "qwen-max", "messages": [{"role": "user"}, {"role": "user", "content": {"not": "string"}}, {"role": "user", "content": "hello"}]}
    response = client.post("/v1/chat/completions", headers=_valid_headers(), json=body)

    assert response.status_code == 200
    assert calls["redact"] == 1
```

- [ ] **Step 5: 添加 PII fail-closed 测试**

```python
def test_pii_fail_closed_returns_503(client, monkeypatch):
    import app.api.chat as chat

    async def fake_verify(auth):
        return "svc-audit"

    async def fake_route(model, header):
        return {"base_url": "https://llm.example", "path": "/chat", "skip_pii": False}

    async def fake_redact(trace_id, text):
        raise RuntimeError("detector down")

    settings = chat.get_settings()
    monkeypatch.setattr(settings, "pii_fail_open", False)
    monkeypatch.setattr(chat, "verify_service_token", fake_verify)
    monkeypatch.setattr(chat, "resolve_route", fake_route)
    monkeypatch.setattr(chat, "redact", fake_redact)

    response = client.post("/v1/chat/completions", headers=_valid_headers(), json=_valid_body())

    assert response.status_code == 503
    assert "PII detector unavailable" in response.text
```

If settings is frozen, monkeypatch `chat.get_settings` to return a simple object with `max_body_bytes` and `pii_fail_open=False`.

- [ ] **Step 6: 添加 upstream exception mapping 测试**

```python
@pytest.mark.parametrize(
    ("exc", "expected_status", "expected_text"),
    [
        ("Upstream5xx", 502, "upstream 5xx"),
        ("UpstreamRateLimited", 429, "upstream rate limited"),
        ("generic", 502, "upstream call failed"),
    ],
)
def test_upstream_errors_map_to_http(client, monkeypatch, exc, expected_status, expected_text):
    import app.api.chat as chat
    from app.errors import Upstream5xx, UpstreamRateLimited

    async def fake_verify(auth):
        return "svc-audit"

    async def fake_route(model, header):
        return {"base_url": "https://llm.example", "path": "/chat", "skip_pii": True}

    async def fake_key(model, token):
        return "fake-key"

    async def fake_upstream(base_url, path, body, headers):
        if exc == "Upstream5xx":
            raise Upstream5xx("bad gateway")
        if exc == "UpstreamRateLimited":
            raise UpstreamRateLimited("quota")
        raise RuntimeError("boom")

    monkeypatch.setattr(chat, "verify_service_token", fake_verify)
    monkeypatch.setattr(chat, "resolve_route", fake_route)
    monkeypatch.setattr(chat, "get_llm_api_key", fake_key)
    monkeypatch.setattr(chat, "call_upstream", fake_upstream)

    response = client.post("/v1/chat/completions", headers=_valid_headers(), json=_valid_body())

    assert response.status_code == expected_status
    assert expected_text in response.text
```

- [ ] **Step 7: 添加 response reverse skip/audit usage missing 测试**

```python
def test_response_reverse_skips_missing_or_non_string_content_and_audit_usage_missing(client, monkeypatch):
    import app.api.chat as chat

    outbox = _CaptureOutbox()
    reverse_calls = []

    async def fake_verify(auth):
        return "svc-audit"

    async def fake_route(model, header):
        return {"base_url": "https://llm.example", "path": "/chat", "skip_pii": False}

    async def fake_redact(trace_id, text):
        return text, {}, []

    async def fake_key(model, token):
        return "fake-key"

    async def fake_upstream(base_url, path, body, headers):
        return _FakeUpstreamResponse({"choices": [{}, {"message": {"content": 123}}, {"message": {"content": "ok"}}]})

    async def fake_reverse(trace_id, text):
        reverse_calls.append((trace_id, text))
        return "reversed"

    monkeypatch.setattr(chat, "verify_service_token", fake_verify)
    monkeypatch.setattr(chat, "resolve_route", fake_route)
    monkeypatch.setattr(chat, "redact", fake_redact)
    monkeypatch.setattr(chat, "get_llm_api_key", fake_key)
    monkeypatch.setattr(chat, "call_upstream", fake_upstream)
    monkeypatch.setattr(chat, "reverse", fake_reverse)
    monkeypatch.setattr(chat, "get_outbox", lambda: outbox)

    body = _valid_body() | {"workflow_id": "wf-123"}
    response = client.post("/v1/chat/completions", headers=_valid_headers(), json=body)

    assert response.status_code == 200
    assert response.json()["choices"][2]["message"]["content"] == "reversed"
    assert reverse_calls == [("trace-chat-1234", "ok")]
    assert outbox.records[0].workflow_id == "wf-123"
    assert outbox.records[0].token_input is None
    assert outbox.records[0].token_output is None
```

- [ ] **Step 8: 验证 chat.py 100%**

```bash
cd /Users/paulwang/work/ChatBiz/services/audit-and-isolation
PYTHONPATH=. python3 -m pytest tests/unit/test_api_chat.py tests/integration/test_e2e_4_scenarios.py tests/integration/test_pii_subscenario_2_*.py -v --cov=app.api.chat --cov-report=term-missing --cov-fail-under=100
```

Expected: PASS, `app/api/chat.py 100%`.

---

## Task 12: LLM client 与 credential client 不可达分支处理

**Files:**
- Modify: `services/audit-and-isolation/app/credential_client.py`
- Modify: `services/audit-and-isolation/app/llm/client.py`
- Modify: `services/audit-and-isolation/tests/unit/test_credential_client.py`
- Modify: `services/audit-and-isolation/tests/unit/test_llm_client.py`

- [ ] **Step 1: 验证当前 missing 行**

```bash
cd /Users/paulwang/work/ChatBiz/services/audit-and-isolation
PYTHONPATH=. python3 -m pytest tests/unit/test_credential_client.py tests/unit/test_llm_client.py -v --cov=app.credential_client --cov=app.llm.client --cov-report=term-missing --cov-fail-under=0
```

Expected: likely missing `credential_client.py:100` and `llm/client.py:47-53,94`.

- [ ] **Step 2: 覆盖 `call_upstream(..., stream=True)` 分支**

Inspect `app/llm/client.py`. If `call_upstream` accepts `stream` and sets body/header for streaming, add to `test_llm_client.py`:

```python
@pytest.mark.asyncio
async def test_call_upstream_stream_true_passes_stream_flag(respx_mock):
    from app.llm.client import call_upstream

    route = respx_mock.post("https://llm.example/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )

    response = await call_upstream(
        "https://llm.example",
        "/v1/chat/completions",
        {"model": "qwen-max", "stream": True},
        {"Authorization": "Bearer fake", "X-Trace-Id": "trace-stream"},
    )

    assert response.status_code == 200
    assert route.called
```

Adapt to existing respx style in `test_llm_client.py`.

- [ ] **Step 3: 处理 credential_client 不可达兜底**

Open `app/credential_client.py`. If final line after retry loop is unreachable, change it to:

```python
    raise RuntimeError("credential service unavailable after retry")  # pragma: no cover - defensive fallback; loop always returns or raises
```

Only do this after confirming normal paths already cover retry behavior.

- [ ] **Step 4: 处理 llm/client 不可达兜底**

Open `app/llm/client.py`. If final line after retry loop is unreachable, change it to:

```python
    raise last_exc or RuntimeError("upstream call failed")  # pragma: no cover - defensive fallback; retry loop always returns or raises
```

If line length violates ruff, split with local variable:

```python
    fallback = last_exc or RuntimeError("upstream call failed")  # pragma: no cover - defensive fallback
    raise fallback
```

- [ ] **Step 5: 验证 llm/credential modules coverage**

```bash
cd /Users/paulwang/work/ChatBiz/services/audit-and-isolation
PYTHONPATH=. python3 -m pytest tests/unit/test_credential_client.py tests/unit/test_llm_client.py -v --cov=app.credential_client --cov=app.llm.client --cov-report=term-missing --cov-fail-under=100
```

Expected: PASS. Record any pragma in `verify.md` later.

---

## Task 13: 全量 coverage 反查并补最后缺口

**Files:**
- Modify tests or app files identified by coverage only

- [ ] **Step 1: 运行全量 coverage**

```bash
cd /Users/paulwang/work/ChatBiz/services/audit-and-isolation
PYTHONPATH=. python3 -m pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=100
```

Expected: may still FAIL if there are residual missing lines.

- [ ] **Step 2: 对每个 residual missing line 分类**

For each missing line:

```text
A. Public behavior not tested → add/extend test.
B. External boundary error path → fake/mock boundary and assert behavior.
C. True defensive unreachable fallback → pragma with comment and verify.md entry.
D. Dead code contradicted by spec → remove only if safe and covered by tests.
```

- [ ] **Step 3: 补一轮最小测试或 pragma**

Add tests in the nearest focused file. Example:

```python
# If remaining missing line is a branch in app/api/chat.py,
# add the test to tests/unit/test_api_chat.py rather than creating a broad catch-all file.
```

- [ ] **Step 4: 重复全量 coverage 直到 100%**

```bash
cd /Users/paulwang/work/ChatBiz/services/audit-and-isolation
PYTHONPATH=. python3 -m pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=100
```

Expected final: all tests pass, `TOTAL ... 100%`.

---

## Task 14: 更新 `verify.py` coverage gate

**Files:**
- Modify: `services/audit-and-isolation/verify.py`

- [ ] **Step 1: 在 CHECKS 顶部加入 pytest-cov gate**

Modify `CHECKS` so first check is:

```python
    ("Pytest coverage gate (app 100%)", lambda: run(
        "Pytest coverage",
        [
            "python3", "-m", "pytest", "tests/", "-v",
            "--cov=app", "--cov-report=term-missing", "--cov-fail-under=100",
        ],
    )),
```

Keep existing unit/integration/critical-path checks unless runtime becomes too slow. Do not delete security checks.

- [ ] **Step 2: Update verify header count dynamically if needed**

If verify prints `18 checks`, update text to avoid hard-coded mismatch:

```python
print(f"chatbiz-audit-and-isolation verify gate ({len(CHECKS)} checks)")
```

- [ ] **Step 3: Run verify**

```bash
cd /Users/paulwang/work/ChatBiz/services/audit-and-isolation
python3 verify.py
```

Expected: PASS, output says all checks passed. If slow but correct, keep it.

---

## Task 15: 安全与 critical path final checks

**Files:**
- No code changes expected unless failures reveal regressions

- [ ] **Step 1: Run PII critical path 2.1-2.8**

```bash
cd /Users/paulwang/work/ChatBiz/services/audit-and-isolation
PYTHONPATH=. python3 -m pytest \
  tests/integration/test_pii_subscenario_2_1.py \
  tests/integration/test_pii_subscenario_2_2.py \
  tests/integration/test_pii_subscenario_2_3.py \
  tests/integration/test_pii_subscenario_2_4.py \
  tests/integration/test_pii_subscenario_2_5.py \
  tests/integration/test_pii_subscenario_2_6.py \
  tests/integration/test_pii_subscenario_2_7.py \
  tests/integration/test_pii_subscenario_2_8.py \
  -v
```

Expected: 8 scenario files pass.

- [ ] **Step 2: Run security grep checks**

```bash
cd /Users/paulwang/work/ChatBiz/services/audit-and-isolation
! grep -rEn 'api[_-]key[ ]*=[ ]["'"'][A-Za-z0-9_\-]{16,}' app/ tests/ 2>/dev/null | grep -v __pycache__ | grep -v credential_client.py
! grep -rE 'BEGIN PRIVATE' --exclude='verify.py' . 2>/dev/null
```

Expected: both commands exit 0 with no matches.

- [ ] **Step 3: Run ruff**

```bash
cd /Users/paulwang/work/ChatBiz/services/audit-and-isolation
ruff check app tests --ignore UP042
```

Expected: PASS. If ruff reports line length/import order in new tests, fix the tests.

---

## Task 16: 写 verify.md 与 retrospective.md

**Files:**
- Create: `openspec/changes/fix-audit-isolation-real-tests-100pct-coverage/verify.md`
- Create: `openspec/changes/fix-audit-isolation-real-tests-100pct-coverage/retrospective.md`

- [ ] **Step 1: 写 verify.md**

Create `verify.md`:

```markdown
# Verify — fix-audit-isolation-real-tests-100pct-coverage

## Summary

- Service: `services/audit-and-isolation`
- Result: PASSED / FAILED
- Final coverage: 100% app coverage
- Total tests: <fill from pytest output>

## Commands

| Command | Exit | Result |
|---|---:|---|
| `PYTHONPATH=. python3 -m pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=100` | 0 | PASS |
| `python3 verify.py` | 0 | PASS |
| `PYTHONPATH=. python3 -m pytest tests/integration/test_pii_subscenario_2_*.py -v` | 0 | PASS |
| `ruff check app tests --ignore UP042` | 0 | PASS |

## Coverage

Paste final coverage table here.

## Product code changes

- `<file>` — <reason>, <test proving it>, external behavior changed? yes/no

## Pragmas

- `<file>:<line>` — <why unreachable>, <why not artificial test>

## Security checks

- API key grep: PASS
- Private key grep: PASS
- metadata-only audit tests: PASS
```

Fill exact numbers from final command output.

- [ ] **Step 2: 写 retrospective.md**

Create `retrospective.md`:

```markdown
# Retrospective — fix-audit-isolation-real-tests-100pct-coverage

## What went well

- <specific>

## Gotchas

- <specific gotcha, e.g. pytest cwd, AsyncMock sync add warning>

## Decisions confirmed

- Real tests first; only defensive unreachable fallbacks get pragma.

## Follow-ups

- <optional future work, e.g. compose-based HA smoke, README /v1/completions drift>
```

- [ ] **Step 3: Validate OpenSpec status**

```bash
cd /Users/paulwang/work/ChatBiz
openspec status --change fix-audit-isolation-real-tests-100pct-coverage
```

Expected: verify/retrospective may be pending until implementation, but plan/apply artifacts should be complete.

---

## Task 17: Final git review checkpoint

**Files:**
- Review all changed files

- [ ] **Step 1: Show changed files**

```bash
cd /Users/paulwang/work/ChatBiz
git status --short
```

Expected: OpenSpec change files, audit service tests, possibly app/verify.py modifications.

- [ ] **Step 2: Inspect diff for accidental secrets or unrelated changes**

```bash
cd /Users/paulwang/work/ChatBiz
git diff -- services/audit-and-isolation openspec/changes/fix-audit-isolation-real-tests-100pct-coverage
```

Expected: no real credentials, no unrelated services changed.

- [ ] **Step 3: Commit only when explicitly asked**

Do not commit unless the user asks. If committing, use:

```bash
git add openspec/changes/fix-audit-isolation-real-tests-100pct-coverage services/audit-and-isolation

git commit -m "test(audit-isolation): reach 100pct coverage" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

- Spec coverage: plan covers audit coverage gate, verify.py gate, PII critical path 2.1-2.8, health/readiness/models/lifespan/database/redis/streaming/schema/chat/audit/PII/LLM client gaps, security checks, verify/retrospective.
- Placeholder scan: no TBD/TODO placeholders; exact files and commands are listed. Some snippets require adapting private helper names after reading actual files, explicitly constrained to tests only.
- Type consistency: all test helpers use local fake classes; imported binding patching is directed at `app.api.chat` to match product imports.
