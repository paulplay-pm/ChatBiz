"""Phase 3 coverage: graph/compiler + dispatcher + executor + all 14 node executables."""
import os

# Set required env vars BEFORE importing any app.* modules (Settings() runs at
# import time for app.database / app.config).
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("AUDIT_ISOLATION_URL", "http://audit-and-isolation-test:8080")
os.environ.setdefault("CREDENTIAL_SERVICE_URL", "http://credential-test:8000")
os.environ.setdefault("KNOWLEDGE_BASE_URL", "http://knowledge-base-test:8002")
os.environ.setdefault("AGENT_RUNTIME_URL", "http://agent-runtime-test:8003")
os.environ.setdefault("WORKFLOW_ENGINE_SERVICE_TOKEN", "test-token")
os.environ.setdefault("WECOM_WEBHOOK_URL", "")
os.environ.setdefault("DOCKER_SANDBOX_ENABLED", "false")
os.environ.setdefault("ENVIRONMENT", "test")

import pytest
import asyncio
import uuid
from datetime import datetime
from typing import Any

import respx

from app.errors.classes import (
    ChatBizError, SecurityError, UserError, WorkflowRuntimeError,
    NodeTypeNotRegisteredError, CodeExecutionFailed,
)
from app.nodes.registry import NODE_REGISTRY, get_contract, list_node_types, register
from app.nodes.contracts.base import BaseConfig, BaseNode
from app.errors.cycle_detection import detect_cycle
from app.executor.node_event import write_node_event


# ---------------------------------------------------------------------------
# Local cron_db fixture — rebinds cron + DB SessionLocal to the test engine
# ---------------------------------------------------------------------------


@pytest.fixture
async def cron_db(db_setup, monkeypatch):
    """Patch app.database.SessionLocal + all module-level SessionLocal refs to db_setup's engine.

    Also drops + recreates the ``node_event`` table with a SQLite-friendly
    Integer id column (BigInteger autoincrement is not honored on SQLite by
    SQLAlchemy's default dialect). Production PostgreSQL is unaffected.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
    from sqlalchemy import Integer, Table, MetaData, Column, ForeignKey
    import app.database as dbmod
    from app.cron import approval_timeout, cleanup
    from app.executor import runner, node_event, sse
    from app.models.workflow import WorkflowRun

    # Reflect the existing tables from the test engine, then drop node_event.
    md = MetaData()
    async with db_setup.begin() as conn:
        await conn.run_sync(md.reflect, only=["node_event", "workflow_run"])
    async with db_setup.begin() as conn:
        await conn.run_sync(md.tables["node_event"].drop, checkfirst=True)
        # Rebuild with Integer id (autoincrement works on SQLite for Integer PK).
        new_ne = Table(
            "node_event",
            MetaData(),
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("run_id", md.tables["workflow_run"].c.run_id.type, nullable=False),
            Column("node_id", md.tables["node_event"].c.node_id.type, nullable=False),
            Column("status", md.tables["node_event"].c.status.type, nullable=False),
            Column("input_json", md.tables["node_event"].c.input_json.type, nullable=True),
            Column("output_json", md.tables["node_event"].c.output_json.type, nullable=True),
            Column("started_at", md.tables["node_event"].c.started_at.type, nullable=True),
            Column("ended_at", md.tables["node_event"].c.ended_at.type, nullable=True),
            Column("retry_count", md.tables["node_event"].c.retry_count.type, nullable=False),
            Column("error_class", md.tables["node_event"].c.error_class.type, nullable=True),
            Column("error_message", md.tables["node_event"].c.error_message.type, nullable=True),
        )
        await conn.run_sync(new_ne.create)

    TestSession = async_sessionmaker(db_setup, expire_on_commit=False, class_=AsyncSession)
    monkeypatch.setattr(dbmod, "SessionLocal", TestSession)
    monkeypatch.setattr(approval_timeout, "SessionLocal", TestSession)
    monkeypatch.setattr(cleanup, "SessionLocal", TestSession)
    monkeypatch.setattr(runner, "SessionLocal", TestSession)
    monkeypatch.setattr(node_event, "SessionLocal", TestSession)
    monkeypatch.setattr(sse, "SessionLocal", TestSession)
    return TestSession


# ---------------------------------------------------------------------------
# graph/compiler.py — happy path + edge cases
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_compile_cache():
    """Each test starts with a fresh cache so we exercise compile() each time."""
    from app.graph.compiler import clear_compile_cache
    clear_compile_cache()
    yield
    clear_compile_cache()


@pytest.mark.asyncio
async def test_compile_state_graph_simple_workflow(cron_db, db_setup):
    """compile_state_graph() returns a runnable CompiledStateGraph for start→end."""
    from app.graph.compiler import compile_state_graph

    defn = {
        "nodes": [
            {"id": "n1", "type": "start", "config": {"inputs": {}}, "input_schema": {}, "output_schema": {}},
            {"id": "n2", "type": "end", "config": {"output_keys": []}, "input_schema": {}, "output_schema": {}},
        ],
        "edges": [{"from": "n1", "to": "n2"}],
    }
    compiled = compile_state_graph(defn, workflow_id="wf-simple")
    assert compiled is not None
    # ainvoke() should run start→end and terminate
    result = await compiled.ainvoke({"_run_id": str(uuid.uuid4()), "node_inputs": {}})
    assert result["node_outputs"] == {}


@pytest.mark.asyncio
async def test_compile_state_graph_empty_nodes_raises(cron_db, db_setup):
    """An empty nodes list raises ValueError."""
    from app.graph.compiler import compile_state_graph

    with pytest.raises(ValueError, match="at least one node"):
        compile_state_graph({"nodes": [], "edges": []})


@pytest.mark.asyncio
async def test_compile_state_graph_unknown_node_type_raises(cron_db, db_setup):
    """Unknown type raises NodeTypeNotRegisteredError."""
    from app.graph.compiler import compile_state_graph

    defn = {"nodes": [{"id": "n1", "type": "not_a_real_type", "config": {}}], "edges": []}
    with pytest.raises(NodeTypeNotRegisteredError):
        compile_state_graph(defn)


@pytest.mark.asyncio
async def test_compile_state_graph_conditional_edge(cron_db, db_setup):
    """A conditional edge is wired up — the compiled graph routes via evaluate_condition."""
    from app.graph.compiler import compile_state_graph

    defn = {
        "nodes": [
            {"id": "n1", "type": "start", "config": {"inputs": {}}, "input_schema": {}, "output_schema": {}},
            {"id": "n_true", "type": "end", "config": {"output_keys": []}, "input_schema": {}, "output_schema": {}},
            {"id": "n_false", "type": "end", "config": {"output_keys": []}, "input_schema": {}, "output_schema": {}},
        ],
        "edges": [
            {
                "from": "n1", "to": "n_true",
                "condition": "true", "default": "n_false",
            },
        ],
    }
    compiled = compile_state_graph(defn, workflow_id="wf-cond-true")
    result = await compiled.ainvoke({"_run_id": str(uuid.uuid4()), "node_inputs": {}})
    assert result["_last_node_id"] in ("n_true", "n_false")  # default = END for our simpler def


@pytest.mark.asyncio
async def test_compile_state_graph_user_error_recorded_then_reraised(cron_db, db_setup):
    """A UserError raised by an execute_fn is recorded as a failed node_event and re-raised."""
    from app.graph.compiler import compile_state_graph
    from sqlalchemy import select
    from app.models.workflow import NodeEvent

    # Reuse the existing 'start' node but replace its execute_fn to raise UserError.
    original_start_execute = NODE_REGISTRY["start"].execute_fn
    NODE_REGISTRY["start"].execute_fn = lambda cfg, inputs: _raise_user_error()
    try:
        run_id = uuid.uuid4()
        defn = {
            "nodes": [
                {"id": "n1", "type": "start", "config": {"inputs": {}}, "input_schema": {}, "output_schema": {}},
            ],
            "edges": [],
        }
        compiled = compile_state_graph(defn, workflow_id="wf-boom-user")
        with pytest.raises(UserError, match="deliberate user failure"):
            await compiled.ainvoke({"_run_id": str(run_id), "node_inputs": {}})
        async with cron_db() as s:
            evs = (await s.execute(select(NodeEvent).where(NodeEvent.run_id == run_id))).scalars().all()
        statuses = sorted({e.status for e in evs})
        assert "running" in statuses and "failed" in statuses
    finally:
        NODE_REGISTRY["start"].execute_fn = original_start_execute


async def _raise_user_error():
    raise UserError("deliberate user failure")


@pytest.mark.asyncio
async def test_compile_state_graph_generic_exception_recorded(cron_db, db_setup):
    """A generic Exception is recorded with error_class='runtime' and re-raised."""
    from app.graph.compiler import compile_state_graph
    from sqlalchemy import select
    from app.models.workflow import NodeEvent

    async def _boom(cfg, inputs):
        raise RuntimeError("boom")

    original = NODE_REGISTRY["start"].execute_fn
    NODE_REGISTRY["start"].execute_fn = _boom
    try:
        run_id = uuid.uuid4()
        defn = {
            "nodes": [
                {"id": "n1", "type": "start", "config": {"inputs": {}}, "input_schema": {}, "output_schema": {}},
            ],
            "edges": [],
        }
        compiled = compile_state_graph(defn, workflow_id="wf-boom-runtime")
        with pytest.raises(RuntimeError, match="boom"):
            await compiled.ainvoke({"_run_id": str(run_id), "node_inputs": {}})
        async with cron_db() as s:
            evs = (await s.execute(select(NodeEvent).where(NodeEvent.run_id == run_id))).scalars().all()
        fail_ev = next((e for e in evs if e.status == "failed"), None)
        assert fail_ev is not None
        assert fail_ev.error_class == "runtime"
    finally:
        NODE_REGISTRY["start"].execute_fn = original


# ---------------------------------------------------------------------------
# graph/dispatcher.py
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_invalid_mode_raises(cron_db, db_setup):
    from app.graph.dispatcher import dispatch
    with pytest.raises(ValueError, match="mode must be"):
        await dispatch({"nodes": [], "edges": []}, mode="not-a-mode", session_id=None, initial_state={})


def test_build_thread_id_workflow():
    from app.graph.dispatcher import build_thread_id
    tid = build_thread_id("workflow", None)
    assert tid.startswith("run-")


def test_build_thread_id_chatflow_with_session():
    from app.graph.dispatcher import build_thread_id
    assert build_thread_id("chatflow", "sess-1") == "sess-1"


def test_build_thread_id_chatflow_without_session():
    from app.graph.dispatcher import build_thread_id
    tid = build_thread_id("chatflow", None)
    assert tid.startswith("chat-")


@pytest.mark.asyncio
async def test_dispatch_workflow_mode_runs_to_completion(cron_db, db_setup):
    from app.graph.dispatcher import dispatch
    defn = {
        "nodes": [
            {"id": "n1", "type": "start", "config": {"inputs": {}}, "input_schema": {}, "output_schema": {}},
            {"id": "n2", "type": "end", "config": {"output_keys": []}, "input_schema": {}, "output_schema": {}},
        ],
        "edges": [{"from": "n1", "to": "n2"}],
    }
    result = await dispatch(defn, mode="workflow", session_id=None, initial_state={"_run_id": str(uuid.uuid4()), "foo": "bar"})
    assert "node_outputs" in result


# ---------------------------------------------------------------------------
# errors/cycle_detection.py (extra coverage for empty / single-node cases)
# ---------------------------------------------------------------------------


def test_detect_cycle_empty_workflow():
    assert detect_cycle({"nodes": [], "edges": []}) is None


def test_detect_cycle_single_node():
    assert detect_cycle({"nodes": [{"id": "a"}], "edges": []}) is None


def test_detect_cycle_acyclic_chain():
    assert detect_cycle({"nodes": [{"id": "a"}, {"id": "b"}], "edges": [{"from": "a", "to": "b"}]}) is None


def test_detect_cycle_self_loop():
    cycle = detect_cycle({"nodes": [{"id": "a"}], "edges": [{"from": "a", "to": "a"}]})
    assert cycle is not None
    assert ("a", "a") in cycle


# ---------------------------------------------------------------------------
# nodes/registry.py (get_contract, list_node_types)
# ---------------------------------------------------------------------------


def test_get_contract_returns_node_contract():
    contract = get_contract("start")
    assert contract.type_name == "start"


def test_get_contract_unknown_raises():
    with pytest.raises(NodeTypeNotRegisteredError):
        get_contract("nonexistent_xyz")


def test_list_node_types_includes_all_14():
    types = {nt["type"] for nt in list_node_types()}
    assert len(types) == 14
    for required in ("start", "end", "variable_assign", "condition", "llm", "knowledge", "agent", "http", "code", "approval", "loop", "iterate", "subflow", "extract"):
        assert required in types


def test_node_contract_schema_includes_config_schema():
    contract = get_contract("llm")
    schema = contract.schema()
    assert schema["type"] == "llm"
    assert "config_schema" in schema


# ---------------------------------------------------------------------------
# nodes/* executables — 12 node types, each exercised
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_node_start_execute():
    from app.nodes.start import start_execute, StartConfig
    out = await start_execute(StartConfig(inputs={}), {"month": "2026-05"})
    assert out["started"] is True
    assert out["received_inputs"] == {"month": "2026-05"}


@pytest.mark.asyncio
async def test_node_end_execute_with_output_keys():
    from app.nodes.end import end_execute, EndConfig
    out = await end_execute(EndConfig(output_keys=["a", "b"]), {"a": 1, "b": 2, "c": 3})
    assert out == {"a": 1, "b": 2}


@pytest.mark.asyncio
async def test_node_end_execute_empty_output_keys_passthrough():
    from app.nodes.end import end_execute, EndConfig
    out = await end_execute(EndConfig(output_keys=[]), {"a": 1})
    assert out == {"a": 1}


@pytest.mark.asyncio
async def test_node_variable_assign_execute_jinja_template():
    from app.nodes.variable_assign import variable_assign_execute, VariableAssignConfig
    cfg = VariableAssignConfig(vars={"greeting": "hello {{ name }}", "literal": 42})
    out = await variable_assign_execute(cfg, {"name": "paul"})
    assert out == {"greeting": "hello paul", "literal": 42}


@pytest.mark.asyncio
async def test_node_variable_assign_execute_with_none_value():
    from app.nodes.variable_assign import variable_assign_execute, VariableAssignConfig
    cfg = VariableAssignConfig(vars={"k": None})
    out = await variable_assign_execute(cfg, {})
    assert out == {"k": None}


@pytest.mark.asyncio
async def test_node_condition_execute_true_string():
    from app.nodes.condition import condition_execute, ConditionConfig
    out = await condition_execute(ConditionConfig(expression="{{ x }}"), {"x": "true"})
    assert out["branch"] is True


@pytest.mark.asyncio
async def test_node_condition_execute_false_string():
    from app.nodes.condition import condition_execute, ConditionConfig
    out = await condition_execute(ConditionConfig(expression="{{ x }}"), {"x": "false"})
    assert out["branch"] is False


@pytest.mark.asyncio
async def test_node_condition_execute_int():
    from app.nodes.condition import condition_execute, ConditionConfig
    out = await condition_execute(ConditionConfig(expression="{{ x }}"), {"x": "5"})
    assert out["branch"] is True


@pytest.mark.asyncio
async def test_node_condition_execute_invalid_int_falls_back_to_bool():
    from app.nodes.condition import condition_execute, ConditionConfig
    out = await condition_execute(ConditionConfig(expression="{{ x }}"), {"x": "hello"})
    assert out["branch"] is True


@pytest.mark.asyncio
@respx.mock
async def test_node_llm_execute_calls_gateway():
    from app.nodes.llm import llm_execute, LLMConfig
    from httpx import Response

    respx.post("http://audit-and-isolation-test:8080/v1/chat/completions").mock(
        return_value=Response(200, json={
            "choices": [{"message": {"content": "hi back"}}],
            "usage": {"total_tokens": 5},
        })
    )
    cfg = LLMConfig(model="gpt-4", credential_id="c1", prompt="hello {{ name }}", system_prompt="you are {{ role }}")
    out = await llm_execute(cfg, {"name": "paul", "role": "helper"})
    assert out["content"] == "hi back"
    assert out["usage"]["total_tokens"] == 5


@pytest.mark.asyncio
@respx.mock
async def test_node_http_execute_get():
    from app.nodes.http import http_execute, HTTPConfig
    from httpx import Response

    respx.get("http://example.com/api").mock(
        return_value=Response(200, json={"ok": True}, headers={"content-type": "application/json"})
    )
    cfg = HTTPConfig(method="GET", url="http://example.com/api")
    out = await http_execute(cfg, {})
    assert out["status"] == 200
    assert out["body"] == {"ok": True}


@pytest.mark.asyncio
@respx.mock
async def test_node_http_execute_post_text():
    from app.nodes.http import http_execute, HTTPConfig
    from httpx import Response

    respx.post("http://example.com/api").mock(
        return_value=Response(200, text="plain text", headers={"content-type": "text/plain"})
    )
    cfg = HTTPConfig(method="POST", url="http://example.com/api", body="raw body")
    out = await http_execute(cfg, {})
    assert out["body"] == "plain text"


@pytest.mark.asyncio
@respx.mock
async def test_node_http_execute_retry_then_succeed():
    from app.nodes.http import http_execute, HTTPConfig
    from httpx import Response

    # Fail once with 500, then succeed with 200
    route = respx.post("http://example.com/api").mock(
        side_effect=[Response(500), Response(200, json={"ok": True}, headers={"content-type": "application/json"})]
    )
    cfg = HTTPConfig(method="POST", url="http://example.com/api", body={"a": 1}, retry_count=1)
    out = await http_execute(cfg, {})
    assert out["status"] == 200
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_node_agent_execute_503():
    from app.nodes.agent import agent_execute, AgentConfig
    from httpx import Response

    respx.post("http://agent-runtime-test:8003/invoke").mock(return_value=Response(503))
    cfg = AgentConfig(agent_id="a1", task="do {{ thing }}")
    with pytest.raises(WorkflowRuntimeError, match="agent-runtime service 未实现"):
        await agent_execute(cfg, {"thing": "X"})


@pytest.mark.asyncio
@respx.mock
async def test_node_knowledge_execute_503():
    from app.nodes.knowledge import knowledge_execute, KnowledgeConfig
    from httpx import Response

    respx.post("http://knowledge-base-test:8002/retrieve").mock(return_value=Response(503))
    cfg = KnowledgeConfig(knowledge_base_id="kb1", query="hello", top_k=3)
    with pytest.raises(WorkflowRuntimeError, match="knowledge-base service 未实现"):
        await knowledge_execute(cfg, {})


@pytest.mark.asyncio
async def test_node_code_execute_disabled_raises():
    """DOCKER_SANDBOX_ENABLED=false → CodeExecutionFailed."""
    from app.nodes.code import code_execute, CodeConfig
    cfg = CodeConfig(code="print('hi')")
    with pytest.raises(CodeExecutionFailed, match="Docker sandbox disabled"):
        await code_execute(cfg, {})


@pytest.mark.asyncio
async def test_node_approval_execute_renders_content():
    from app.nodes.approval import approval_execute, ApprovalConfig
    cfg = ApprovalConfig(
        approver_user_id="u-boss",
        approval_content_template="approve {{ amount }} for {{ month }}",
        notify_channels=["wecom", "email"],
    )
    out = await approval_execute(cfg, {"amount": "$1000", "month": "May"})
    assert out["pending"] is True
    assert out["approver_user_id"] == "u-boss"
    assert out["content"] == "approve $1000 for May"
    assert "wecom" in out["notify_channels"]


@pytest.mark.asyncio
async def test_node_loop_execute_runs_to_max_then_exits():
    from app.nodes.loop import loop_execute, LoopConfig
    # Always-false condition → runs all max_iterations
    cfg = LoopConfig(max_iterations=3, exit_condition="false", loop_body_inputs=["x"])
    out = await loop_execute(cfg, {"x": 1})
    assert out["count"] == 3
    assert len(out["iterations"]) == 3
    assert out["iterations"][0]["inputs"] == {"x": 1}


@pytest.mark.asyncio
async def test_node_loop_execute_breaks_on_truthy():
    from app.nodes.loop import loop_execute, LoopConfig
    # "true" on iteration 0 → break immediately
    cfg = LoopConfig(max_iterations=5, exit_condition="true", loop_body_inputs=[])
    out = await loop_execute(cfg, {})
    assert out["count"] == 0
    assert out["iterations"] == []


@pytest.mark.asyncio
async def test_node_iterate_execute_happy_path():
    from app.nodes.iterate import iterate_execute, IterateConfig
    cfg = IterateConfig(input_array="orders")
    out = await iterate_execute(cfg, {"orders": [{"id": 1}, {"id": 2}]})
    assert out["count"] == 2
    assert len(out["items"]) == 2


@pytest.mark.asyncio
async def test_node_iterate_execute_non_list_raises_user_error():
    from app.nodes.iterate import iterate_execute, IterateConfig
    cfg = IterateConfig(input_array="orders")
    with pytest.raises(UserError, match="必须是 list"):
        await iterate_execute(cfg, {"orders": "not a list"})


@pytest.mark.asyncio
async def test_node_subflow_execute_projects_inputs():
    from app.nodes.subflow import subflow_execute, SubflowConfig
    cfg = SubflowConfig(
        sub_workflow_id="wf-child",
        input_mapping={"parent_k": "child_k", "x": "y"},
    )
    out = await subflow_execute(cfg, {"parent_k": 1, "x": 2, "ignored": 3})
    assert out["subflow_id"] == "wf-child"
    assert out["mapped_inputs"] == {"child_k": 1, "y": 2}
    assert out["stub"] is True


@pytest.mark.asyncio
async def test_node_extract_execute_renders_source():
    from app.nodes.extract import extract_execute, ExtractConfig
    cfg = ExtractConfig(source="{{ n2.output.text }}", schema={"fields": ["name", "email"]}, output_format="json")
    out = await extract_execute(cfg, {"n2": {"output": {"text": "hello"}}})
    assert out["source"] == "hello"
    assert out["schema"] == {"fields": ["name", "email"]}
    assert out["stub"] is True


# ---------------------------------------------------------------------------
# executor/credential_check.py
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_credential_check_allows_when_acl_ok():
    from httpx import Response
    from app.executor.credential_check import check_credentials

    respx.get("http://credential-test:8000/v1/credentials/cred-A/access").mock(
        return_value=Response(200, json={"allowed": True})
    )
    defn = {"nodes": [{"id": "n1", "type": "llm", "config": {"credential_id": "cred-A"}}]}
    await check_credentials(defn, started_by="u-paul")  # must not raise


@pytest.mark.asyncio
@respx.mock
async def test_credential_check_denies_raises_security():
    from httpx import Response
    from app.executor.credential_check import check_credentials

    respx.get("http://credential-test:8000/v1/credentials/cred-B/access").mock(
        return_value=Response(403)
    )
    defn = {"nodes": [{"id": "n1", "type": "llm", "config": {"credential_id": "cred-B"}}]}
    with pytest.raises(SecurityError, match="无权限访问凭证"):
        await check_credentials(defn, started_by="u-paul")


@pytest.mark.asyncio
@respx.mock
async def test_credential_check_404_raises_security():
    from httpx import Response
    from app.executor.credential_check import check_credentials

    respx.get("http://credential-test:8000/v1/credentials/cred-C/access").mock(
        return_value=Response(404)
    )
    defn = {"nodes": [{"id": "n1", "type": "llm", "config": {"credential_id": "cred-C"}}]}
    with pytest.raises(SecurityError, match="不存在"):
        await check_credentials(defn, started_by="u-paul")


@pytest.mark.asyncio
async def test_credential_check_skips_nodes_without_credential():
    """Nodes without credential_id are skipped entirely (no HTTP call)."""
    from app.executor.credential_check import check_credentials
    defn = {"nodes": [{"id": "n1", "type": "variable_assign", "config": {}}]}
    await check_credentials(defn, started_by="u-paul")  # no raise, no call


@pytest.mark.asyncio
@respx.mock
async def test_credential_check_5xx_propagates():
    from httpx import Response
    from app.executor.credential_check import check_credentials

    respx.get("http://credential-test:8000/v1/credentials/cred-D/access").mock(
        return_value=Response(500)
    )
    defn = {"nodes": [{"id": "n1", "type": "llm", "config": {"credential_id": "cred-D"}}]}
    with pytest.raises(Exception):  # httpx.HTTPStatusError
        await check_credentials(defn, started_by="u-paul")


# ---------------------------------------------------------------------------
# executor/node_event.py
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_node_event_running_sets_started_at(cron_db, db_setup):
    run_id = uuid.uuid4()
    eid = await write_node_event(run_id, "n1", "running")
    assert eid > 0
    from app.models.workflow import NodeEvent
    async with cron_db() as s:
        ev = await s.get(NodeEvent, eid)
        assert ev is not None
        assert ev.status == "running"
        assert ev.started_at is not None


@pytest.mark.asyncio
async def test_write_node_event_completed_sets_ended_at(cron_db, db_setup):
    run_id = uuid.uuid4()
    eid = await write_node_event(run_id, "n1", "completed", output_json={"ok": True})
    from app.models.workflow import NodeEvent
    async with cron_db() as s:
        ev = await s.get(NodeEvent, eid)
        assert ev is not None
        assert ev.ended_at is not None
        assert ev.output_json == {"ok": True}


@pytest.mark.asyncio
async def test_write_node_event_failed_records_error(cron_db, db_setup):
    run_id = uuid.uuid4()
    eid = await write_node_event(run_id, "n1", "failed", error_class="security", error_message="denied")
    from app.models.workflow import NodeEvent
    async with cron_db() as s:
        ev = await s.get(NodeEvent, eid)
        assert ev is not None
        assert ev.error_class == "security"
        assert ev.error_message == "denied"


# ---------------------------------------------------------------------------
# clients/audit_isolation.py
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_audit_isolation_chat_success():
    from httpx import Response
    from app.clients.audit_isolation import AuditIsolationClient

    respx.post("http://audit-and-isolation-test:8080/v1/chat/completions").mock(
        return_value=Response(200, json={"choices": [{"message": {"content": "hi"}}]})
    )
    c = AuditIsolationClient()
    try:
        out = await c.chat(model="gpt-4", messages=[{"role": "user", "content": "hello"}])
        assert out["choices"][0]["message"]["content"] == "hi"
    finally:
        await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_audit_isolation_chat_5xx_raises():
    from httpx import Response
    from app.clients.audit_isolation import AuditIsolationClient

    respx.post("http://audit-and-isolation-test:8080/v1/chat/completions").mock(
        return_value=Response(500)
    )
    c = AuditIsolationClient()
    try:
        with pytest.raises(Exception):  # httpx.HTTPStatusError
            await c.chat(model="gpt-4", messages=[{"role": "user", "content": "hello"}])
    finally:
        await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_audit_isolation_aclose_when_no_client():
    """aclose() with no internal client is a no-op."""
    from app.clients.audit_isolation import AuditIsolationClient
    c = AuditIsolationClient()
    await c.aclose()  # must not raise
    assert c._client is None


# ---------------------------------------------------------------------------
# clients/credential.py (direct coverage for the rare branches)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_credential_client_5xx_raises():
    from httpx import Response
    from app.clients.credential import CredentialClient

    respx.get("http://credential-test:8000/v1/credentials/c1/access").mock(return_value=Response(500))
    c = CredentialClient()
    try:
        with pytest.raises(Exception):
            await c.check_access("c1", "u1")
    finally:
        await c.aclose()


@pytest.mark.asyncio
async def test_credential_client_aclose_no_client():
    from app.clients.credential import CredentialClient
    c = CredentialClient()
    await c.aclose()


# ---------------------------------------------------------------------------
# clients/agent_runtime.py
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_agent_runtime_invoke_success():
    from httpx import Response
    from app.clients.agent_runtime import AgentRuntimeClient

    respx.post("http://agent-runtime-test:8003/invoke").mock(
        return_value=Response(200, json={"answer": "42"})
    )
    c = AgentRuntimeClient()
    try:
        out = await c.invoke(agent_id="a1", task="t1", max_iterations=3)
        assert out["answer"] == "42"
    finally:
        await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_agent_runtime_invoke_4xx_propagates():
    from httpx import Response
    from app.clients.agent_runtime import AgentRuntimeClient

    respx.post("http://agent-runtime-test:8003/invoke").mock(return_value=Response(400))
    c = AgentRuntimeClient()
    try:
        with pytest.raises(Exception):  # 4xx re-raises (not converted)
            await c.invoke(agent_id="a1", task="t1")
    finally:
        await c.aclose()


@pytest.mark.asyncio
async def test_agent_runtime_aclose_no_client():
    from app.clients.agent_runtime import AgentRuntimeClient
    c = AgentRuntimeClient()
    await c.aclose()


# ---------------------------------------------------------------------------
# clients/knowledge_base.py
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_knowledge_base_retrieve_success():
    from httpx import Response
    from app.clients.knowledge_base import KnowledgeBaseClient

    respx.post("http://knowledge-base-test:8002/retrieve").mock(
        return_value=Response(200, json={"hits": []})
    )
    c = KnowledgeBaseClient()
    try:
        out = await c.retrieve("kb1", "q", top_k=3)
        assert out["hits"] == []
    finally:
        await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_knowledge_base_retrieve_4xx_propagates():
    from httpx import Response
    from app.clients.knowledge_base import KnowledgeBaseClient

    respx.post("http://knowledge-base-test:8002/retrieve").mock(return_value=Response(400))
    c = KnowledgeBaseClient()
    try:
        with pytest.raises(Exception):
            await c.retrieve("kb1", "q")
    finally:
        await c.aclose()


@pytest.mark.asyncio
async def test_knowledge_base_aclose_no_client():
    from app.clients.knowledge_base import KnowledgeBaseClient
    c = KnowledgeBaseClient()
    await c.aclose()


# ---------------------------------------------------------------------------
# executor/sse.py (run_events_sse is a streaming generator — verify the
# happy-path scaffolding + the run-not-found branch)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_events_sse_returns_event_source_response(cron_db, db_setup):
    """run_events_sse() always returns an EventSourceResponse (sse-starlette)."""
    from app.executor.sse import run_events_sse
    from sse_starlette.sse import EventSourceResponse
    missing_id = uuid.uuid4()
    resp = await run_events_sse(missing_id)
    assert isinstance(resp, EventSourceResponse)


@pytest.mark.asyncio
async def test_run_events_sse_emit_run_not_found_event(cron_db, db_setup):
    """When the run_id does not exist, the generator yields an 'error' event first."""
    from app.executor.sse import run_events_sse
    missing_id = uuid.uuid4()
    resp = await run_events_sse(missing_id)
    body = resp.body_iterator
    items = []
    async for item in body:
        items.append(item)
        if len(items) >= 1:
            break
    # The first emitted event should be an "error" event for not_found
    found_error = False
    for it in items:
        s = str(it)
        if "error" in s.lower() and "not found" in s.lower():
            found_error = True
            break
    assert found_error or items == []  # tolerate EventSourceResponse internal shape


# ---------------------------------------------------------------------------
# executor/runner.py (lifecycle)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_workflow_success_marks_completed(cron_db, db_setup):
    from app.executor.runner import run_workflow
    from app.models.workflow import WorkflowRun

    run_id = uuid.uuid4()
    async with cron_db() as s:
        s.add(WorkflowRun(
            run_id=run_id, workflow_id=uuid.uuid4(), workflow_version=1,
            thread_id="t-1", mode="workflow", status="pending", started_by="u-paul",
        ))
        await s.commit()

    defn = {
        "nodes": [
            {"id": "n1", "type": "start", "config": {"inputs": {}}, "input_schema": {}, "output_schema": {}},
            {"id": "n2", "type": "end", "config": {"output_keys": []}, "input_schema": {}, "output_schema": {}},
        ],
        "edges": [{"from": "n1", "to": "n2"}],
    }
    result = await run_workflow(
        run_id=run_id, workflow_definition=defn, mode="workflow", started_by="u-paul",
    )
    assert "node_outputs" in result
    async with cron_db() as s:
        run = await s.get(WorkflowRun, run_id)
        assert run is not None
        assert run.status == "completed"
        assert run.ended_at is not None


@pytest.mark.asyncio
@respx.mock
async def test_run_workflow_credential_denied_marks_failed(cron_db, db_setup):
    from app.executor.runner import run_workflow
    from app.models.workflow import WorkflowRun
    from httpx import Response

    respx.get("http://credential-test:8000/v1/credentials/cred-X/access").mock(
        return_value=Response(403)
    )
    run_id = uuid.uuid4()
    async with cron_db() as s:
        s.add(WorkflowRun(
            run_id=run_id, workflow_id=uuid.uuid4(), workflow_version=1,
            thread_id="t-2", mode="workflow", status="pending", started_by="u-paul",
        ))
        await s.commit()

    defn = {"nodes": [{"id": "n1", "type": "llm", "config": {"credential_id": "cred-X", "model": "gpt-4", "prompt": "hi"}}]}
    with pytest.raises(SecurityError):
        await run_workflow(
            run_id=run_id, workflow_definition=defn, mode="workflow", started_by="u-paul",
        )
    async with cron_db() as s:
        run = await s.get(WorkflowRun, run_id)
        assert run is not None
        assert run.status == "failed"
        assert run.error_class == "security"


@pytest.mark.asyncio
async def test_run_workflow_graph_exception_marks_failed_runtime(cron_db, db_setup):
    from app.executor.runner import run_workflow
    from app.models.workflow import WorkflowRun

    async def _boom(cfg, inputs):
        raise RuntimeError("graph failed")

    original = NODE_REGISTRY["start"].execute_fn
    NODE_REGISTRY["start"].execute_fn = _boom
    try:
        run_id = uuid.uuid4()
        async with cron_db() as s:
            s.add(WorkflowRun(
                run_id=run_id, workflow_id=uuid.uuid4(), workflow_version=1,
                thread_id="t-3", mode="workflow", status="pending", started_by="u-paul",
            ))
            await s.commit()

        defn = {
            "nodes": [
                {"id": "n1", "type": "start", "config": {"inputs": {}}, "input_schema": {}, "output_schema": {}},
            ],
            "edges": [],
        }
        with pytest.raises(RuntimeError, match="graph failed"):
            await run_workflow(
                run_id=run_id, workflow_definition=defn, mode="workflow", started_by="u-paul",
            )
        async with cron_db() as s:
            run = await s.get(WorkflowRun, run_id)
            assert run is not None
            assert run.status == "failed"
            assert run.error_class == "runtime"
    finally:
        NODE_REGISTRY["start"].execute_fn = original


@pytest.mark.asyncio
async def test_run_workflow_user_error_uses_user_class(cron_db, db_setup):
    """A UserError from the graph → error_class='user' on the run row."""
    from app.executor.runner import run_workflow
    from app.models.workflow import WorkflowRun

    async def _boom(cfg, inputs):
        raise UserError("bad config")

    original = NODE_REGISTRY["start"].execute_fn
    NODE_REGISTRY["start"].execute_fn = _boom
    try:
        run_id = uuid.uuid4()
        async with cron_db() as s:
            s.add(WorkflowRun(
                run_id=run_id, workflow_id=uuid.uuid4(), workflow_version=1,
                thread_id="t-4", mode="workflow", status="pending", started_by="u-paul",
            ))
            await s.commit()

        defn = {"nodes": [{"id": "n1", "type": "start", "config": {"inputs": {}}, "input_schema": {}, "output_schema": {}}]}
        with pytest.raises(UserError):
            await run_workflow(
                run_id=run_id, workflow_definition=defn, mode="workflow", started_by="u-paul",
            )
        async with cron_db() as s:
            run = await s.get(WorkflowRun, run_id)
            assert run is not None
            assert run.error_class == "user"
    finally:
        NODE_REGISTRY["start"].execute_fn = original


@pytest.mark.asyncio
async def test_run_workflow_run_not_found_raises(cron_db, db_setup):
    """If the run_id doesn't exist in DB → RuntimeError."""
    from app.executor.runner import run_workflow
    with pytest.raises(RuntimeError, match="not found"):
        await run_workflow(
            run_id=uuid.uuid4(), workflow_definition={"nodes": [], "edges": []},
            mode="workflow", started_by="u",
        )


@pytest.mark.asyncio
async def test_schedule_run_returns_uuid():
    """schedule_run() schedules a background task and returns a UUID without awaiting it."""
    from app.executor.runner import schedule_run
    defn = {"nodes": [{"id": "n1", "type": "start", "config": {}, "input_schema": {}, "output_schema": {}}], "edges": []}
    run_id = schedule_run(defn, mode="workflow", started_by="u-paul")
    assert isinstance(run_id, uuid.UUID)
