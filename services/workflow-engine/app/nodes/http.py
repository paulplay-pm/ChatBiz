"""HTTP request node — generic outbound HTTP call with retry + Jinja2 templating.

Used for any node that needs to call an external REST API (CRM, ERP, custom
internal service, webhook). The URL, headers, and body are all Jinja2-templated
against the workflow inputs, so a single node config can be reused across
runs by binding different input variables.

Retry uses exponential backoff (``1s, 2s, 4s, ...``) up to ``retry_count``
additional attempts. We retry on *any* exception (transport or HTTP) — for
the MVP we don't distinguish 4xx (don't retry) from 5xx (do retry) because
the canvas frontend doesn't expose per-status-class retry config yet. Phase
5 will add a ``retry_on`` field for ``["5xx", "timeout"]`` granularity.
"""
from __future__ import annotations

import asyncio
from typing import Any, Literal

import httpx
from pydantic import Field

from app.graph.jinja import render_jinja
from app.nodes.contracts.base import BaseConfig, BaseNode
from app.nodes.registry import register


class HTTPConfig(BaseConfig):
    """Configuration for the HTTP request node."""

    method: Literal["GET", "POST", "PUT", "DELETE"]
    url: str = Field(..., description="Jinja2 URL 模板,渲染后作为请求 URL")
    headers: dict[str, str] = Field(default_factory=dict, description="HTTP headers,值支持 Jinja2")
    body: Any | None = Field(
        None,
        description="可选 body (dict 序列化为 JSON,str 作为 raw body,Jinja2 模板会被渲染)",
    )
    timeout_ms: int = Field(5000, ge=100, le=60000)
    retry_count: int = Field(1, ge=0, le=5, description="失败重试次数(0 = 不重试)")


@register("http", version="1.0.0")
class HTTPNode(BaseNode):
    """Node contract for the HTTP request node."""

    config: HTTPConfig


async def http_execute(config: HTTPConfig, inputs: dict) -> dict:
    """Render URL + body, issue the request with retries, return parsed response.

    The response body is JSON-decoded if the content-type starts with
    ``application/json``; otherwise returned as the raw text. This matches the
    behaviour of ``httpx.Response.json()`` / ``.text`` so callers can rely on
    the same field naming.
    """
    url = render_jinja(config.url, inputs)
    body = render_jinja(config.body, inputs) if config.body is not None else None
    last_exc: Exception | None = None
    timeout_s = config.timeout_ms / 1000
    for attempt in range(config.retry_count + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as c:
                # Templated headers (Jinja2 in values)
                rendered_headers = {k: render_jinja(v, inputs) for k, v in config.headers.items()}
                r = await c.request(
                    config.method,
                    url,
                    headers=rendered_headers,
                    json=body if isinstance(body, (dict, list)) else None,
                    content=body if isinstance(body, str) else None,
                )
                r.raise_for_status()
                ct = r.headers.get("content-type", "")
                return {
                    "status": r.status_code,
                    "headers": dict(r.headers),
                    "body": r.json() if ct.startswith("application/json") else r.text,
                }
        except Exception as e:
            last_exc = e
            if attempt < config.retry_count:
                await asyncio.sleep(1 * (2 ** attempt))
    # All retries exhausted — re-raise the last exception. The runner maps
    # ``httpx.HTTPStatusError`` to ``WorkflowRuntimeError`` (boundary #2).
    assert last_exc is not None
    raise last_exc


__all__ = ["HTTPConfig", "HTTPNode", "http_execute"]
