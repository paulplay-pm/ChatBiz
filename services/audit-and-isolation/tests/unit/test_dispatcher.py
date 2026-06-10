"""Unit tests for the routing dispatcher.

The dispatcher is a pure-ish function ``resolve_route(model, header)``
that depends on ``get_routing`` — we monkey-patch the routing table
module to return canned entries rather than touching Redis or
PostgreSQL. The 5 cases the plan calls out are:

* public + no bypass → skip_pii=False
* public + bypass → skip_pii=False (bypass ignored on public)
* private + bypass → skip_pii=True
* private + no bypass → skip_pii=False
* model_kind mismatch → RoutingError
"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from app.models.common import HeaderSchema, ModelKind
from app.routing.dispatcher import RoutingError, resolve_route


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _entry(model_kind: str) -> dict:
    return {
        "model_kind": model_kind,
        "upstream_base_url": "https://example.com",
        "upstream_path": "/v1/chat/completions",
        "timeout_ms": 30000,
    }


class TestDispatcher(unittest.TestCase):
    """Matrix of (model_kind, bypass) → skip_pii, plus the kind-mismatch error."""

    def test_public_no_bypass_redacts(self):
        header = HeaderSchema(trace_id="t-12345678", model_kind=ModelKind.PUBLIC, bypass_isolation=False)
        with patch("app.routing.dispatcher.get_routing", return_value=_entry("public")):
            route = _run(resolve_route("qwen-max", header))
        self.assertFalse(route["skip_pii"])

    def test_public_with_bypass_still_redacts(self):
        # public + bypass_isolation=true → skip_pii stays False
        # (bypass only applies to private models)
        header = HeaderSchema(trace_id="t-12345678", model_kind=ModelKind.PUBLIC, bypass_isolation=True)
        with patch("app.routing.dispatcher.get_routing", return_value=_entry("public")):
            route = _run(resolve_route("qwen-max", header))
        self.assertFalse(route["skip_pii"])

    def test_private_with_bypass_skips_pii(self):
        header = HeaderSchema(trace_id="t-12345678", model_kind=ModelKind.PRIVATE, bypass_isolation=True)
        with patch("app.routing.dispatcher.get_routing", return_value=_entry("private")):
            route = _run(resolve_route("internal-vllm-qwen", header))
        self.assertTrue(route["skip_pii"])

    def test_private_without_bypass_redacts(self):
        header = HeaderSchema(trace_id="t-12345678", model_kind=ModelKind.PRIVATE, bypass_isolation=False)
        with patch("app.routing.dispatcher.get_routing", return_value=_entry("private")):
            route = _run(resolve_route("internal-vllm-qwen", header))
        self.assertFalse(route["skip_pii"])

    def test_kind_mismatch_raises(self):
        # routing table says public, header says private → error
        header = HeaderSchema(trace_id="t-12345678", model_kind=ModelKind.PRIVATE, bypass_isolation=False)
        with patch("app.routing.dispatcher.get_routing", return_value=_entry("public")):
            with self.assertRaises(RoutingError):
                _run(resolve_route("qwen-max", header))

    def test_unknown_model_raises(self):
        header = HeaderSchema(trace_id="t-12345678", model_kind=ModelKind.PUBLIC, bypass_isolation=False)
        with patch("app.routing.dispatcher.get_routing", return_value=None):
            with self.assertRaises(RoutingError):
                _run(resolve_route("no-such-model", header))

    def test_route_passes_through_upstream_fields(self):
        # Sanity check: base_url / path / timeout_ms come from the
        # routing table entry verbatim.
        header = HeaderSchema(trace_id="t-12345678", model_kind=ModelKind.PUBLIC, bypass_isolation=False)
        entry = {
            "model_kind": "public",
            "upstream_base_url": "https://dashscope.aliyuncs.com",
            "upstream_path": "/v1/chat/completions",
            "timeout_ms": 12345,
        }
        with patch("app.routing.dispatcher.get_routing", return_value=entry):
            route = _run(resolve_route("qwen-max", header))
        self.assertEqual(route["base_url"], "https://dashscope.aliyuncs.com")
        self.assertEqual(route["path"], "/v1/chat/completions")
        self.assertEqual(route["timeout_ms"], 12345)


if __name__ == "__main__":
    unittest.main()
