"""Unit tests for GET /v1/models response construction.

The endpoint behavior is exercised directly while replacing the database
session with a fake SQLAlchemy result. The response assertions verify the
OpenAI-shaped public contract and that upstream routing internals are not
leaked to callers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.api import models


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


class _SessionContext:
    def __init__(self, rows):
        self.rows = rows
        self.statements = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, statement):
        self.statements.append(statement)
        return _Result(self.rows)


def _row(model_name, model_kind, updated_at):
    return SimpleNamespace(
        model_name=model_name,
        model_kind=model_kind,
        updated_at=updated_at,
        upstream_base_url="https://internal-upstream.example.com",
        upstream_path="/private/path",
        timeout_ms=12345,
        enabled=True,
    )


@pytest.mark.asyncio
async def test_list_models_filters_enabled_rows_in_sql_statement_and_formats_timezone_aware_updated_at():
    updated_at = datetime(2026, 6, 11, 12, 30, 0, tzinfo=timezone.utc)
    session = _SessionContext([_row("qwen-max", "public", updated_at)])

    with patch.object(models, "get_session", return_value=session):
        response = await models.list_models()

    assert response.object == "list"
    assert response.data[0].id == "qwen-max"
    assert response.data[0].object == "model"
    assert response.data[0].created == int(updated_at.timestamp())
    assert response.data[0].owned_by == "public"
    assert "enabled IS true" in str(session.statements[0])


@pytest.mark.asyncio
async def test_list_models_uses_timezone_aware_now_when_updated_at_is_none():
    fixed_now = datetime(2026, 6, 11, 8, 0, 0, tzinfo=timezone.utc)
    session = _SessionContext([_row("internal-qwen", "private", None)])

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            assert tz is timezone.utc
            return fixed_now

    with (
        patch.object(models, "get_session", return_value=session),
        patch.object(models, "datetime", _FixedDateTime),
    ):
        response = await models.list_models()

    assert response.data[0].created == int(fixed_now.timestamp())
    assert response.data[0].owned_by == "private"


@pytest.mark.asyncio
async def test_list_models_treats_naive_updated_at_as_utc():
    naive_updated_at = datetime(2026, 6, 11, 9, 15, 30)
    session = _SessionContext([_row("qwen-plus", "public", naive_updated_at)])

    with patch.object(models, "get_session", return_value=session):
        response = await models.list_models()

    assert response.data[0].created == int(
        naive_updated_at.replace(tzinfo=timezone.utc).timestamp()
    )


@pytest.mark.asyncio
async def test_list_models_returns_empty_openai_shaped_list_when_no_enabled_rows_exist():
    session = _SessionContext([])

    with patch.object(models, "get_session", return_value=session):
        response = await models.list_models()

    assert response.object == "list"
    assert response.data == []


@pytest.mark.asyncio
async def test_list_models_response_fields_do_not_leak_upstream_routing_internals():
    session = _SessionContext([
        _row("qwen-max", "public", datetime(2026, 6, 11, tzinfo=timezone.utc))
    ])

    with patch.object(models, "get_session", return_value=session):
        response = await models.list_models()

    body = response.model_dump()
    model_payload = body["data"][0]
    assert set(model_payload) == {"id", "object", "created", "owned_by"}
    assert "upstream_base_url" not in model_payload
    assert "upstream_path" not in model_payload
    assert "timeout_ms" not in model_payload
    assert "https://internal-upstream.example.com" not in repr(body)
