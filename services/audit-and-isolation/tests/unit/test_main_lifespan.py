"""Unit tests for FastAPI lifespan startup/shutdown behavior.

The lifespan runs real control flow but replaces external startup and
shutdown boundaries: routing preload, audit outbox, and engine disposal.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from starlette.routing import Route

from app import main


class _Outbox:
    def __init__(self):
        self.start = AsyncMock()
        self.stop = AsyncMock()


@pytest.mark.asyncio
async def test_lifespan_loads_routing_starts_outbox_then_stops_outbox_and_disposes_engine_on_shutdown():
    outbox = _Outbox()
    load_routing = AsyncMock(return_value=2)
    dispose_engine = AsyncMock()
    events: list[str] = []

    async def _load_routing():
        events.append("load")
        return await load_routing()

    async def _start():
        events.append("start")

    async def _stop():
        events.append("stop")

    async def _dispose():
        events.append("dispose")

    outbox.start.side_effect = _start
    outbox.stop.side_effect = _stop
    dispose_engine.side_effect = _dispose

    with (
        patch.object(main, "get_settings", return_value=SimpleNamespace(environment="test")),
        patch.object(main, "load_routing_into_cache", new=_load_routing),
        patch.object(main, "get_outbox", return_value=outbox),
        patch.object(main, "dispose_engine", new=dispose_engine),
    ):
        async with main.lifespan(FastAPI()):
            events.append("inside")

    load_routing.assert_awaited_once_with()
    outbox.start.assert_awaited_once_with()
    outbox.stop.assert_awaited_once_with()
    dispose_engine.assert_awaited_once_with()
    assert events == ["load", "start", "inside", "stop", "dispose"]


@pytest.mark.asyncio
async def test_lifespan_continues_when_routing_load_fails_and_still_runs_shutdown(caplog):
    outbox = _Outbox()
    dispose_engine = AsyncMock()
    routing_error = RuntimeError("database unavailable")

    with (
        caplog.at_level(logging.WARNING, logger="app.main"),
        patch.object(main, "get_settings", return_value=SimpleNamespace(environment="test")),
        patch.object(main, "load_routing_into_cache", new=AsyncMock(side_effect=routing_error)),
        patch.object(main, "get_outbox", return_value=outbox),
        patch.object(main, "dispose_engine", new=dispose_engine),
    ):
        async with main.lifespan(FastAPI()):
            pass

    outbox.start.assert_awaited_once_with()
    outbox.stop.assert_awaited_once_with()
    dispose_engine.assert_awaited_once_with()
    assert "routing table load failed: database unavailable" in caplog.messages


def test_app_registers_expected_routers_and_metadata():
    route_paths = {route.path for route in main.app.routes if isinstance(route, Route)}

    assert main.app.title == "chatbiz-audit-and-isolation"
    assert main.app.version == "0.1.0"
    assert "/healthz" in route_paths
    assert "/readyz" in route_paths
    assert "/v1/models" in route_paths
    assert "/v1/chat/completions" in route_paths
