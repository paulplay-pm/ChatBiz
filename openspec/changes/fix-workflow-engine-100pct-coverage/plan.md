# fix-workflow-engine-100pct-coverage Implementation Plan

**Goal:** 通过补单元测试,让 `python -m pytest tests/ --cov-fail-under=100` 真实运行并通过。

**Architecture:** 在 `services/workflow-engine/tests/unit/` 添加 30+ 测试文件,覆盖所有未达 100% 模块。沿用现有 aiosqlite + respx + freezegun 模式。

**Tech Stack:** Python 3.12 / pytest / pytest-asyncio / pytest-cov / respx / aiosqlite / freezegun(已有)。

---

## Phase 1 关键骨架(纯函数 + httpx mock)

`tests/unit/test_errors_classes.py`:

```python
from app.errors.classes import (
    ChatBizError, SecurityError, UserError, WorkflowRuntimeError,
    NodeTypeNotRegisteredError, NodeOutputValidationError,
    CodeExecutionFailed, ApprovalNotFound, ApprovalAlreadyResponded,
    UnauthorizedApprovalAccess,
)

def test_chatbiz_error_default_class():
    e = ChatBizError("oops")
    assert e.error_class == "internal"
    assert e.message == "oops"
    assert e.context == {}

def test_subclass_error_classes():
    assert SecurityError("x").error_class == "security"
    assert UserError("x").error_class == "user"
    assert WorkflowRuntimeError("x").error_class == "runtime"
    assert NodeTypeNotRegisteredError("x").error_class == "user"
    assert NodeOutputValidationError("x").error_class == "runtime"
    assert CodeExecutionFailed("x").error_class == "runtime"
    assert ApprovalNotFound("x").error_class == "user"
    assert ApprovalAlreadyResponded("x").error_class == "user"
    assert UnauthorizedApprovalAccess("x").error_class == "security"
    assert str(NodeTypeNotRegisteredError("foo")) == "foo"
```

`tests/unit/test_executor_retry.py`:

```python
import pytest
from app.errors.classes import UserError, SecurityError
from app.executor.retry import with_retry

@pytest.mark.asyncio
async def test_with_retry_success():
    async def fn(): return 42
    assert await with_retry(fn) == 42

@pytest.mark.asyncio
async def test_with_retry_runtime_retries():
    calls = []
    async def fn():
        calls.append(1)
        if len(calls) < 2:
            raise RuntimeError("transient")
        return "ok"
    assert await with_retry(fn, retry_count=1) == "ok"
    assert len(calls) == 2

@pytest.mark.asyncio
async def test_with_retry_user_error_no_retry():
    calls = []
    async def fn():
        calls.append(1)
        raise UserError("bad input")
    with pytest.raises(UserError):
        await with_retry(fn, retry_count=3)
    assert len(calls) == 1

@pytest.mark.asyncio
async def test_with_retry_security_error_no_retry():
    calls = []
    async def fn():
        calls.append(1)
        raise SecurityError("denied")
    with pytest.raises(SecurityError):
        await with_retry(fn, retry_count=3)
    assert len(calls) == 1

@pytest.mark.asyncio
async def test_with_retry_eventually_raises():
    async def fn():
        raise RuntimeError("always fails")
    with pytest.raises(RuntimeError):
        await with_retry(fn, retry_count=2)
```

`tests/unit/test_graph_conditional.py`:

```python
from app.graph.conditional import evaluate_condition

def test_evaluate_true_strings():
    for v in ("true", "True", "1", "yes"):
        assert evaluate_condition(v, {}) is True

def test_evaluate_false_strings():
    for v in ("false", "False", "0", "no", ""):
        assert evaluate_condition(v, {}) is False

def test_evaluate_int():
    assert evaluate_condition("1", {}) is True
    assert evaluate_condition("0", {}) is False
    assert evaluate_condition("42", {}) is True

def test_evaluate_non_zero_string():
    assert evaluate_condition("hello", {}) is True
    assert evaluate_condition("falseish", {}) is True
```

`tests/unit/test_clients_*.py` 用 respx mock:

```python
# tests/unit/test_clients_credential.py
import pytest, respx
from httpx import Response
from app.clients.credential import CredentialClient
from app.errors.classes import SecurityError

@pytest.mark.asyncio
@respx.mock
async def test_check_access_true():
    respx.get("http://test/v1/credentials/c1/access").mock(return_value=Response(200, json={"allowed": True}))
    c = CredentialClient()
    assert await c.check_access("c1", "u1") is True
    await c.aclose()

@pytest.mark.asyncio
@respx.mock
async def test_check_access_false():
    respx.get("http://test/v1/credentials/c1/access").mock(return_value=403)
    c = CredentialClient()
    assert await c.check_access("c1", "u1") is False
    await c.aclose()

@pytest.mark.asyncio
@respx.mock
async def test_check_access_404_raises_security():
    respx.get("http://test/v1/credentials/c1/access").mock(return_value=404)
    c = CredentialClient()
    with pytest.raises(SecurityError):
        await c.check_access("c1", "u1")
    await c.aclose()
```

(注: 需设 env var,测试在 conftest 的 `setup_env` 里设。)

---

## Phase 2 关键骨架(API + cron)

`tests/unit/test_api_workflows.py` 用 `client` fixture from conftest,按 7 个 endpoint 测一遍。每个 test 用 `X-User-Id: test-user` 头。

`tests/unit/test_cron_approval_timeout.py` 用 `freezegun.freeze_time` 模拟 24h 前后:

```python
import pytest
from datetime import datetime, timedelta, timezone
from freezegun import freeze_time
from app.cron.approval_timeout import check_approval_timeout
from app.models.workflow import Approval, WorkflowRun
from app.database import SessionLocal

@pytest.mark.asyncio
async def test_approval_timeout_marks_expired(db_setup):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestSession = async_sessionmaker(db_setup, expire_on_commit=False)
    async with TestSession() as s:
        run = WorkflowRun(run_id=uuid.uuid4(), workflow_id=uuid.uuid4(), workflow_version=1, thread_id="t", mode="workflow", status="paused", started_by="u-paul")
        s.add(run)
        await s.commit()
        # pending, created 25h ago
        ap = Approval(run_id=run.run_id, node_id="n", approver_user_id="u-paul", status="pending", created_at=datetime.now(timezone.utc) - timedelta(hours=25))
        s.add(ap)
        await s.commit()
    await check_approval_timeout()
    async with TestSession() as s:
        ap2 = await s.get(Approval, ap.approval_id)
        assert ap2.status == "timeout"
```

---

## Phase 3 关键骨架(graph/compiler + nodes + executor)

`tests/unit/test_graph_compiler.py` 用 monkeypatch 简化:

```python
import pytest
from app.graph.compiler import compile_state_graph, _make_node_fn, detect_cycle_path
from app.nodes.registry import NODE_REGISTRY
from app.graph.drag_loop import detect_cycle

def test_compile_sequential_workflow():
    definition = {
        "nodes": [
            {"id": "n1", "type": "start", "config": {}},
            {"id": "n2", "type": "end", "config": {}},
        ],
        "edges": [{"from": "n1", "to": "n2"}],
    }
    compiled = compile_state_graph(definition)
    assert compiled is not None
```

`tests/unit/test_nodes_*.py` 每个节点 1 个测试,验证 execute 行为(用 respx 模拟外部依赖,比如 LLM/credential/HTTP)。

---

## 验证命令

```bash
cd /Users/paulwang/work/ChatBiz/services/workflow-engine
conda run -n chatbiz python -m pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=100
```

期望:
- 全部测试通过(40+ tests)
- 覆盖率 ≥ 100%
- 退出码 0
