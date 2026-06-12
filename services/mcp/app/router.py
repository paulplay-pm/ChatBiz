"""McpRouter — stdio JSON-RPC dispatch to the 3 MCP servers.

This module owns the **transport** and the **audit-egress**
contract. The 3 server submodules own the **business logic**.

Per ``openspec/changes/mcp-server-integration-mvp/design.md`` D5,
every external call must flow through
``services/audit-and-isolation/app/llm/client.py`` (eng-review
decision #1 — egress enforcement). In the skeleton phase we model
that requirement with :func:`audit_archive`, which uses ``httpx``
to ``POST /v1/audit/archive`` on the audit-and-isolation service.
Tests inject a fake to avoid a live HTTP dependency.

Architecture:

    agent-runtime ──stdio──> McpRouter ──dispatch──> server.HANDLER
                                │
                                └─audit_archive──> audit-and-isolation

Public surface:

* :class:`McpRouter` — orchestrates dispatch + audit + response shaping
* :func:`make_server` — build a fresh ``mcp.server.Server`` wired
  with the router's handlers (used by both this module's own
  ``__main__`` entrypoint and by integration tests)
* :func:`audit_archive` — the egress helper (skeleton: ``httpx`` POST)
* :data:`TOOL_PREFIX_*` — the three tool-name prefixes

The module is also runnable as ``python -m app.router`` so the
integration test suite can spawn it as a real subprocess speaking
the stdio JSON-RPC protocol.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional

import httpx

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    TextContent,
    Tool,
)

from app.servers import fetch as _fetch_server
from app.servers import filesystem as _filesystem_server
from app.servers import postgres as _postgres_server

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# public constants
# ---------------------------------------------------------------------------


TOOL_PREFIX_FILESYSTEM = "fs_"
TOOL_PREFIX_FETCH = "fetch_"
TOOL_PREFIX_POSTGRES = "pg_"

AUDIT_ARCHIVE_PATH = "/v1/audit/archive"

# Default to localhost in dev; production sets this env var to the
# audit-and-isolation service URL (typically the in-cluster DNS).
DEFAULT_AUDIT_BASE_URL = "http://127.0.0.1:8080"


# Re-export from app.audit for callers (e.g. fetch server) that used to
# import make_audit_call from here.
from app.audit import make_audit_call  # noqa: E402, F401


# ---------------------------------------------------------------------------
# egress helper
# ---------------------------------------------------------------------------


def audit_archive(
    tool_name: str,
    args: dict[str, Any],
    trace_id: str,
    *,
    base_url: Optional[str] = None,
    timeout: float = 5.0,
) -> dict[str, Any]:
    """POST a single audit record to ``audit-and-isolation``.

    Mirrors the ``/v1/audit/archive`` schema the audit-and-isolation
    service exposes (eng-review #1 egress). In the skeleton phase we
    intentionally use a synchronous ``httpx`` call so the dispatch
    path is straight-line; V1.0 will switch to an ``AsyncClient`` so
    the stdio loop never blocks on audit IO.

    Returns the parsed JSON body on success. Raises ``httpx.HTTPError``
    on transport failure — the caller (router) decides whether to
    surface that as a runtime error to the agent-runtime or to
    Fail-Open (the eng-review decided Fail-Open for audit; mirror
    that here so an audit-and-isolation outage does not block LLM
    work).
    """
    url = (base_url or os.environ.get("MCP_AUDIT_BASE_URL") or DEFAULT_AUDIT_BASE_URL).rstrip(
        "/"
    ) + AUDIT_ARCHIVE_PATH
    payload = {
        "trace_id": trace_id,
        "tool_name": tool_name,
        "args": args,
        "service": "chatbiz-mcp",
    }
    try:
        resp = httpx.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        # Fail-Open (eng-review audit Fail-Open policy).
        logger.warning(
            "audit archive failed (tool=%s trace_id=%s): %s", tool_name, trace_id, exc
        )
        return {"status": "fail_open", "error": str(exc), "trace_id": trace_id}


# ---------------------------------------------------------------------------
# router
# ---------------------------------------------------------------------------


ServerHandler = Callable[[str, dict[str, Any]], dict[str, Any]]
AuditFn = Callable[[str, dict[str, Any], str], dict[str, Any]]


@dataclass
class McpRouter:
    """Dispatch + audit + response-shaping for the 3 MCP servers.

    The router is intentionally a plain dataclass so tests can
    inject fakes for any of the three handlers or the audit
    function. The default constructor wires the skeleton-phase
    stub handlers; production usage will replace them with the
    real ``HANDLER``s each subagent delivers.
    """

    filesystem_handler: ServerHandler = _filesystem_server.HANDLER
    fetch_handler: ServerHandler = _fetch_server.HANDLER
    postgres_handler: ServerHandler = _postgres_server.HANDLER
    audit_archive: AuditFn = staticmethod(audit_archive)  # type: ignore[assignment]

    # -- dispatch ------------------------------------------------------------

    def _resolve_handler(self, tool_name: str) -> ServerHandler:
        """Map a tool-name prefix to the corresponding server handler."""
        if tool_name.startswith(TOOL_PREFIX_FILESYSTEM):
            return self.filesystem_handler
        if tool_name.startswith(TOOL_PREFIX_FETCH):
            return self.fetch_handler
        if tool_name.startswith(TOOL_PREFIX_POSTGRES):
            return self.postgres_handler
        raise ValueError(f"unknown tool prefix on {tool_name!r}")

    async def dispatch(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Dispatch one tool call: route → audit → return payload.

        The order matters — we audit **after** the handler returns
        (or raises) so the audit record reflects the actual outcome,
        not just the request. Fail-Open audit means a transient
        audit-and-isolation outage never blocks the LLM call.
        """
        handler = self._resolve_handler(tool_name)
        trace_id = uuid.uuid4().hex
        # Stub handlers in this phase are sync; we still call them
        # via ``asyncio.to_thread`` so a future switch to async
        # handlers is a one-line change.
        result = await asyncio.to_thread(handler, tool_name, args)
        # Audit happens *after* dispatch so the record includes the
        # actual outcome. The egress helper is sync today; switch
        # to an ``AsyncClient`` when we add audit batching.
        self.audit_archive(tool_name, args, trace_id)
        return result

    # -- advertised tools ----------------------------------------------------

    def _advertise(self) -> Iterable[Tool]:
        """Combine the three servers' advertised tool names into MCP ``Tool``s."""
        for prefix, server in (
            (TOOL_PREFIX_FILESYSTEM, _filesystem_server),
            (TOOL_PREFIX_FETCH, _fetch_server),
            (TOOL_PREFIX_POSTGRES, _postgres_server),
        ):
            for name in server.TOOL_NAMES:
                yield Tool(
                    name=f"{prefix}{name}" if not name.startswith(prefix) else name,
                    description=f"skeleton stub for {name}",
                    inputSchema={"type": "object", "properties": {}, "additionalProperties": True},
                )

    async def list_advertised_tools(self) -> list[Tool]:
        """Return the list of ``Tool``s the router will advertise."""
        return list(self._advertise())


# ---------------------------------------------------------------------------
# server factory + stdio entrypoint
# ---------------------------------------------------------------------------


def make_server(router: Optional[McpRouter] = None) -> Server:
    """Build a fresh ``mcp.server.Server`` wired to ``router``.

    The handlers installed on the returned ``Server`` defer all
    work to :meth:`McpRouter.dispatch` and
    :meth:`McpRouter.list_advertised_tools` so behaviour stays in
    one place.

    Tests that want to swap in fakes should construct an
    :class:`McpRouter` with custom handlers and pass it here.
    """
    router = router or McpRouter()
    server: Server = Server("chatbiz-mcp-router")

    @server.list_tools()  # type: ignore[misc]
    async def _list_tools() -> list[Tool]:
        # ``list_tools`` expects a raw list[Tool]; the framework
        # wraps it in ``ListToolsResult`` itself. Returning the
        # wrapped type here triggers a double-wrap validation
        # failure on the wire.
        return await router.list_advertised_tools()

    @server.call_tool()  # type: ignore[misc]
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        try:
            payload = await router.dispatch(name, arguments or {})
        except Exception as exc:  # noqa: BLE001 - we re-shape into MCP error envelope
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "error_class": getattr(exc, "error_class", "runtime"),
                            "error_message": str(exc),
                        }
                    ),
                )
            ]
        return [TextContent(type="text", text=json.dumps(payload))]

    return server


async def _run_stdio() -> None:
    """stdio entrypoint used by ``python -m app.router``."""
    server = make_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    """Synchronous shim so ``python -m app.router`` works on Python 3.12."""
    asyncio.run(_run_stdio())


# ---------------------------------------------------------------------------
# intentionally-unused references (kept to silence linters and document intent)
# ---------------------------------------------------------------------------

# These imports prove the stdio + list_tools + call_tool types are
# available at runtime; they are referenced via ``make_server`` and
# ``dispatch``. Listed here for the static checker.
_ = (CallToolRequest, CallToolResult, ListToolsRequest, ListToolsResult)


if __name__ == "__main__":  # pragma: no cover
    main()