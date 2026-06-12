"""fetch MCP server — stdio JSON-RPC service with 3 tools.

Tools
-----

* ``fetch_url(url)``        — GET any URL, return ``{status, body, headers}``.
* ``fetch_html(url)``       — GET + BeautifulSoup, extract main text.
* ``fetch_json(url)``       — GET + ``orjson`` decode, return ``dict``.

Security
--------

Every tool call passes the URL through ``McpSecurityPolicy.check_url``,
which enforces the ``MCP_FETCH_ALLOWED_DOMAINS`` allowlist and rejects
hosts that resolve to private / loopback / link-local IPs (SSRF
defense). Response bodies larger than ``MCP_FETCH_MAX_BYTES``
(default 1 MiB) raise ``McpResponseTooLargeError``. ``fetch_json``
raises ``McpParseError`` on a non-JSON payload.

Audit
-----

After each tool call the server best-effort writes an audit record
through ``app.router.audit_call``. A failed audit write MUST NOT
propagate to the tool response (per eng-review #1).
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx
import orjson
from bs4 import BeautifulSoup
from mcp.server import Server

from app.audit import make_audit_call
from app.security import (
    McpParseError,
    McpResponseTooLargeError,
    McpSecurityError,
    McpSecurityPolicy,
)

TOOL_NAMES = ("fetch_url", "fetch_html", "fetch_json")


def _run_coro(coro):
    """Run an async helper from the router's sync HANDLER adapter."""
    return __import__("asyncio").run(coro)


def HANDLER(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Synchronous adapter used by ``app.router.McpRouter``."""
    # The central router advertises names with the fetch_ prefix; the
    # standalone server uses bare tool names.
    if tool_name.startswith("fetch_") and tool_name not in TOOL_NAMES:
        tool_name = tool_name.removeprefix("fetch_")
        tool_name = f"fetch_{tool_name}"
    url = args.get("url", "")
    if tool_name == "fetch_url":
        return _run_coro(fetch_url(url))
    if tool_name == "fetch_html":
        return {"text": _run_coro(fetch_html(url))}
    if tool_name == "fetch_json":
        return _run_coro(fetch_json(url))
    raise ValueError(f"unknown fetch tool: {tool_name}")


__all__ = [
    "TOOL_NAMES",
    "HANDLER",
    "build_server",
    "fetch_url",
    "fetch_html",
    "fetch_json",
]


# ---------------------------------------------------------------------------
# Module-level config
# ---------------------------------------------------------------------------


def _build_policy() -> McpSecurityPolicy:
    """Build the security policy from environment variables.

    Split out as a free function so tests can monkeypatch it without
    touching module globals directly (improves branch coverage).
    """
    return McpSecurityPolicy.from_env()


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


async def fetch_url(url: str, *, policy: McpSecurityPolicy | None = None) -> dict:
    """GET ``url`` and return ``{"status", "body", "headers"}``.

    Raises:
        McpSecurityError: allowlist / SSRF violation.
        McpResponseTooLargeError: response body exceeds the byte cap.
    """
    pol = policy if policy is not None else _build_policy()
    pol.check_url(url)
    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        resp = await client.get(url)
        body_bytes = await _read_capped(resp, pol.max_response_bytes)
    return {
        "status": resp.status_code,
        "body": body_bytes.decode("utf-8", errors="replace"),
        "headers": dict(resp.headers),
    }


async def fetch_html(url: str, *, policy: McpSecurityPolicy | None = None) -> str:
    """GET ``url`` and return the extracted main text.

    Raises:
        McpSecurityError: allowlist / SSRF violation.
        McpResponseTooLargeError: response body exceeds the byte cap.
    """
    pol = policy if policy is not None else _build_policy()
    pol.check_url(url)
    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        resp = await client.get(url)
        body_bytes = await _read_capped(resp, pol.max_response_bytes)
    soup = BeautifulSoup(body_bytes, "html.parser")
    # ``get_text`` joins all block-level text nodes; the separator
    # keeps paragraph boundaries visible.
    return soup.get_text(separator="\n", strip=True)


async def fetch_json(url: str, *, policy: McpSecurityPolicy | None = None) -> dict:
    """GET ``url`` and return the parsed JSON document.

    Raises:
        McpSecurityError: allowlist / SSRF violation.
        McpResponseTooLargeError: response body exceeds the byte cap.
        McpParseError: response body is not valid JSON.
    """
    pol = policy if policy is not None else _build_policy()
    pol.check_url(url)
    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        resp = await client.get(url)
        body_bytes = await _read_capped(resp, pol.max_response_bytes)
    try:
        loaded = orjson.loads(body_bytes)
    except orjson.JSONDecodeError as exc:
        raise McpParseError(f"response is not valid JSON: {exc}") from exc
    if not isinstance(loaded, dict):
        raise McpParseError(
            f"expected JSON object at top level, got {type(loaded).__name__}"
        )
    return loaded


async def _read_capped(resp: httpx.Response, cap: int) -> bytes:
    """Read the response body in chunks; raise if it exceeds ``cap`` bytes."""
    chunks: list[bytes] = []
    total = 0
    async for chunk in resp.aiter_bytes():
        total += len(chunk)
        if total > cap:
            raise McpResponseTooLargeError(
                f"response exceeds {cap} byte limit"
            )
        chunks.append(chunk)
    return b"".join(chunks)


# ---------------------------------------------------------------------------
# MCP server wiring
# ---------------------------------------------------------------------------


def _serialize(value: Any) -> str:
    """Serialize a tool return value into a JSON string for MCP transport."""
    return json.dumps(value, ensure_ascii=False, default=str)


def build_server(
    *,
    policy: McpSecurityPolicy | None = None,
    audit_url: str | None = None,
    user_id: str = "mcp-fetch",
    trace_id: str = "trace-fetch-00000000",
) -> Server:
    """Construct the MCP ``Server`` instance exposing the 3 tools.

    Args:
        policy: Security policy to inject. Defaults to env-driven policy.
        audit_url: Override the audit-and-isolation egress URL (tests).
        user_id: Caller identity written to the audit record.
        trace_id: Trace identifier written to the audit record.
    """
    pol = policy if policy is not None else _build_policy()
    server = Server("chatbiz-mcp-fetch")

    @server.list_tools()
    async def _list_tools():
        return [
            {
                "name": "fetch_url",
                "description": "GET a URL and return {status, body, headers}.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
            },
            {
                "name": "fetch_html",
                "description": "GET a URL and extract main text via BeautifulSoup.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
            },
            {
                "name": "fetch_json",
                "description": "GET a URL and parse the response as JSON.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
            },
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict):
        url = arguments.get("url", "")
        t0 = time.time()
        status_code = 200
        try:
            if name == "fetch_url":
                result = await fetch_url(url, policy=pol)
            elif name == "fetch_html":
                result = await fetch_html(url, policy=pol)
                # fetch_html returns str — wrap to keep one return shape.
                result = {"text": result}
            elif name == "fetch_json":
                result = await fetch_json(url, policy=pol)
            else:
                raise McpParseError(f"unknown tool: {name}")
            payload = _serialize(result)
        except McpSecurityError as exc:
            status_code = 403
            payload = _serialize(
                {"error_class": "security", "error_message": str(exc)}
            )
        except McpResponseTooLargeError as exc:
            status_code = 413
            payload = _serialize(
                {"error_class": "runtime", "error_message": str(exc)}
            )
        except McpParseError as exc:
            status_code = 422
            payload = _serialize(
                {"error_class": "runtime", "error_message": str(exc)}
            )
        latency_ms = int((time.time() - t0) * 1000)

        # Best-effort audit write — MUST NOT block the tool response.
        await make_audit_call(
            tool_name=name,
            user_id=user_id,
            trace_id=trace_id,
            payload={"url": url},
            status_code=status_code,
            latency_ms=latency_ms,
            audit_url=audit_url,
        )()

        return [{"type": "text", "text": payload}]

    return server