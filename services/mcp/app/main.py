"""ChatBiz MCP — HTTP/SSE entrypoint.

This module exposes the unified MCP router (filesystem + fetch + postgres)
over Server-Sent Events so that other ChatBiz services can reach it via
HTTP instead of stdio.  It keeps ``app.router`` untouched so the stdio
entrypoint (``python -m app.router``) remains available for tests and
local subprocess spawning.

Routes
------

* ``GET /sse``          — establish an SSE session, receive ``endpoint`` event
* ``POST /messages``    — post JSON-RPC messages to a session
* ``GET /healthz``      — liveness probe

Environment
-----------

* ``MCP_HOST``          — bind host (default ``0.0.0.0``)
* ``MCP_PORT``          — bind port (default ``8080``)
* ``MCP_SSE_PATH``      — SSE endpoint path (default ``/sse``)
* ``MCP_MESSAGE_PATH``  — POST message endpoint path (default ``/messages``)
* ``MCP_AUDIT_BASE_URL``— audit-and-isolation base URL
* ``LOG_LEVEL``         — Python logging level
* ``ENVIRONMENT``       — ``local`` enables Starlette debug mode
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.types import Receive, Scope, Send

from mcp.server.sse import SseServerTransport

from app.router import make_server

logger = logging.getLogger(__name__)

DEFAULT_SSE_PATH = "/sse"
DEFAULT_MESSAGE_PATH = "/messages"

SSE_PATH = os.environ.get("MCP_SSE_PATH", DEFAULT_SSE_PATH)
MESSAGE_PATH = os.environ.get("MCP_MESSAGE_PATH", DEFAULT_MESSAGE_PATH)

# The endpoint advertised to clients in the SSE ``endpoint`` event.
# It must be a relative or absolute URL that the client will POST to.
# A relative path keeps the transport independent of the external host/port.
sse_transport = SseServerTransport(MESSAGE_PATH)


@asynccontextmanager
async def lifespan(app: Starlette):
    """Build the MCP server once and stash it on the app state."""
    logger.info("initializing MCP server")
    app.state.mcp_server = make_server()
    yield
    logger.info("shutting down MCP server")


class HealthzEndpoint:
    """``GET /healthz`` — liveness probe."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = PlainTextResponse("ok")
        await response(scope, receive, send)


class SseEndpoint:
    """``GET /sse`` — establish a server-sent events session."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        app: Starlette = scope["app"]
        server = app.state.mcp_server
        async with sse_transport.connect_sse(scope, receive, send) as (
            read_stream,
            write_stream,
        ):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )


class MessagesEndpoint:
    """``POST /messages`` — client JSON-RPC messages for an existing session."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await sse_transport.handle_post_message(scope, receive, send)


routes = [
    Route("/healthz", HealthzEndpoint()),
    Route(SSE_PATH, SseEndpoint()),
    Route(MESSAGE_PATH, MessagesEndpoint(), methods=["POST"]),
]

app = Starlette(
    debug=os.environ.get("ENVIRONMENT", "local") == "local",
    routes=routes,
    lifespan=lifespan,
)


def main() -> None:
    """CLI entrypoint used by ``python -m app.main`` and the Dockerfile."""
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "8080"))
    log_level = (os.environ.get("LOG_LEVEL") or "info").lower()
    logging.basicConfig(
        level=log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_level=log_level,
        access_log=True,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
