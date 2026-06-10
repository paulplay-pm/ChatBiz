"""Routing dispatcher — resolve a model name + request header to an upstream.

The dispatcher is the bridge between the HTTP layer's parsed
``HeaderSchema`` (carrying the caller's intended model kind and
``X-Bypass-Isolation`` flag) and the routing table's
model-to-upstream mapping. It returns a single ``dict`` with the
upstream's base URL / path / timeout, plus a derived ``skip_pii``
flag that the redactor reads to decide whether to actually rewrite
the body.

``skip_pii`` policy (eng-review #1 lock-in):

* ``public`` model + ``X-Bypass-Isolation: true`` → still redact.
  The bypass flag only applies to the *private* data plane; using
  a public LLM with PII in the body is a data-leak regardless of
  any header the caller sends.
* ``private`` model + ``X-Bypass-Isolation: true`` → skip PII.
  The caller is explicitly opting into a private upstream that
  already meets the data-isolation bar; redacting would be
  destructive (placeholder→original can't round-trip through
  in-pod storage that already has the plaintext).
* ``private`` model without bypass → still redact. Defense in
  depth: a private model can still be logged by the upstream
  provider, and the redactor's metadata-only audit is more
  trustworthy if the audit log is the *only* place the PII
  redaction map lives.
"""

from __future__ import annotations

from app.models.common import HeaderSchema
from app.routing.table import get_routing


class RoutingError(Exception):
    """Raised when a request cannot be routed to an upstream.

    The gateway maps this to a 400 response — the caller's
    ``X-Model-Kind`` header is wrong, or the model name is
    not in the routing table (typo, model decommissioned,
    etc.)."""


async def resolve_route(model_name: str, header: HeaderSchema) -> dict:
    """Return ``{base_url, path, timeout_ms, skip_pii}`` for the request.

    Raises :class:`RoutingError` on any of:

    * model not found in routing table
    * caller's ``X-Model-Kind`` header disagrees with the table's
      ``model_kind`` (e.g. trying to send a public request to a
      private vLLM pod)
    """
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


__all__ = ["RoutingError", "resolve_route"]
