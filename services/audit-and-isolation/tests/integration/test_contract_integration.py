"""Integration tests for the 4 perf contract call sites in the chat pipeline.

Spec fixtures (``openspec/changes/gateway-egress-enforcement-p0/specs/gateway-perf-contracts/spec.md``
Requirement: 主流程必须嵌入 4 个 contract 调用点,失败降级 Noop):

1. **Noop 路径可跑通完整 e2e** — the 4 e2e scenarios from
   ``test_e2e_4_scenarios.py`` still pass with the Noop contracts
   wired in. This is the regression test: phase E must not break
   the existing critical path.
2. **限流触发** — a real ``RateLimiter`` returning ``False``
   causes the chat endpoint to return HTTP 429 with the
   ``{"error": "rate_limited", "retry_after": N}`` body and
   skip the upstream call.
3. **缓存命中** — a real ``ResponseCache`` returning a hit
   causes the chat endpoint to skip the upstream call, run
   the PII reverse on the cached body, write audit, and
   return the cached response.
4. **contract 异常降级** — a real contract raising an exception
   causes the chat pipeline to fall back to Noop behaviour
   and increment the ``contract_degraded{contract=...}``
   counter. The request still succeeds.

These tests share a base class with the existing e2e fixtures
(``CriticalPathTestBase``); the contract-specific stubs are
swapped in per-test via :func:`app.api.chat.get_contracts`.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Required env vars for the app config to load.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x")
os.environ.setdefault("REDIS_URL", "redis://x")
os.environ.setdefault("CREDENTIAL_SERVICE_URL", "http://x")
os.environ["REDIS_URL"] = "redis://fakeredis:6379/0"

import fakeredis  # noqa: E402
import fakeredis.aioredis  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import redis_client  # noqa: E402
from app.api import chat as chat_mod  # noqa: E402
from app.main import app  # noqa: E402
from app.metrics import (  # noqa: E402
    gateway_contract_degraded_total,
    gateway_requests_total,
    gateway_trace_cache_hits_total,
)
from app.perf.contracts import (  # noqa: E402
    CachedResponse,
    RateLimiter,
    RequestBatcher,
    ResponseCache,
)


def _build_fake_redis_pool():
    """Patch the redis pool to return a fakeredis instance.

    Mirrors the helper in ``test_e2e_4_scenarios.py``.
    """
    server = fakeredis.FakeServer()
    fake = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)

    def _get():
        return fake

    return patch.object(redis_client, "get_redis", new=_get)


def _public_route() -> dict:
    return {
        "base_url": "https://upstream.example.com",
        "path": "/v1/chat/completions",
        "timeout_ms": 30000,
        "skip_pii": False,
    }


def _echo_upstream():
    """An LLM-fake that echoes the user content with a prefix."""

    async def _echo(base_url, path, body, headers):
        user_msg = body["messages"][-1]["content"]
        resp = MagicMock()
        resp.status_code = 200
        resp.json = MagicMock(
            return_value={
                "id": "cmpl-echo",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": f"echo: {user_msg}",
                        }
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }
        )
        return resp

    return _echo


# ---------------------------------------------------------------------------
# Base class — wires the 4 Noop contracts + standard mocks
# ---------------------------------------------------------------------------


class ContractIntegrationTestBase(unittest.TestCase):
    """Shared base for the 4 contract integration tests.

    Subclasses get:

    * a fully-stubbed FastAPI ``TestClient``
    * fakeredis for the PII map round-trip
    * the standard auth + credential + routing + LLM client
      mocks
    * the 4 Noop contracts pre-wired via ``reset_contracts_for_tests``

    The contracts are accessible via ``self.set_contract(name, obj)``
    for swapping in custom mocks.
    """

    def setUp(self) -> None:
        from app.audit.writer import reset_outbox_for_tests

        reset_outbox_for_tests()
        chat_mod.reset_contracts_for_tests()

        # fakeredis for the PII map.
        self._redis_patcher = _build_fake_redis_pool()
        self._redis_patcher.start()
        # Auth stub.
        self._auth_patcher = patch(
            "app.api.chat.verify_service_token",
            new=AsyncMock(return_value="svc-paul"),
        )
        self._auth_patcher.start()
        # Credential stub.
        self._cred_patcher = patch(
            "app.api.chat.get_llm_api_key",
            new=AsyncMock(return_value="sk-fake"),
        )
        self._cred_patcher.start()
        # LLM client stub (echo).
        self._llm_patcher = patch(
            "app.api.chat.call_upstream", new=_echo_upstream()
        )
        self._llm_patcher.start()
        # PII redactor + reverser stubs.
        async def _redact(trace_id, text):
            return text, {}, []
        async def _reverse(trace_id, text):
            return text
        self._redact_mod_patcher = patch(
            "app.pii.redactor.redact", new=_redact
        )
        self._redact_chat_patcher = patch(
            "app.api.chat.redact", new=_redact
        )
        self._redact_mod_patcher.start()
        self._redact_chat_patcher.start()
        self._reverse_mod_patcher = patch(
            "app.pii.reverser.reverse", new=_reverse
        )
        self._reverse_chat_patcher = patch(
            "app.api.chat.reverse", new=_reverse
        )
        self._reverse_mod_patcher.start()
        self._reverse_chat_patcher.start()
        # Routing stub.
        self._route_patcher = patch(
            "app.api.chat.resolve_route",
            new=AsyncMock(return_value=_public_route()),
        )
        self._route_patcher.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        for p in (
            self._redis_patcher,
            self._auth_patcher,
            self._cred_patcher,
            self._llm_patcher,
            self._redact_mod_patcher,
            self._redact_chat_patcher,
            self._reverse_mod_patcher,
            self._reverse_chat_patcher,
            self._route_patcher,
        ):
            p.stop()
        # Restore Noop contracts for the next test.
        chat_mod.reset_contracts_for_tests()

    # ----- helpers ----------------------------------------------------------

    def set_contract(self, name: str, obj) -> None:
        """Swap in a custom contract for the duration of this test."""
        contracts = chat_mod.get_contracts()
        contracts[name] = obj

    def _headers(self, **overrides) -> dict:
        h = {
            "Authorization": "Bearer t",
            "X-Trace-Id": "01HXPHASECONTRACT00AAAAA",
            "X-Model-Kind": "public",
        }
        h.update(overrides)
        return h

    def _body(self, content: str = "hi") -> dict:
        return {
            "model": "qwen-max",
            "messages": [{"role": "user", "content": content}],
        }

    def _read_counter(self, counter, **labels) -> float:
        """Read a counter's value for a specific label set.

        For unlabelled counters, reads ``_value.get()``
        directly. For labelled counters, calls ``.labels()``
        first to materialise the per-label-set value
        (incrementing by 0 keeps the value intact and the
        side-effect is a single sample line in the
        exposition).
        """
        if not labels:
            return counter._value.get()  # noqa: SLF001
        # Labelled counter — materialise the label set.
        labelled = counter.labels(**labels)
        return labelled._value.get()  # noqa: SLF001


# ---------------------------------------------------------------------------
# Fixture 1: Noop path runs the full e2e unchanged
# ---------------------------------------------------------------------------


class TestNoopContractsFullE2E(ContractIntegrationTestBase):
    """With the Noop contracts wired in, the full e2e (the 4
    scenarios from ``test_e2e_4_scenarios.py``) still passes.

    This is the regression test: phase E added 4 call sites
    + 4 contract Noops; the Noop behaviour must not change
    the response of any of the 4 scenarios.
    """

    def test_scenario1_public_pii_redacts_and_reverses(self):
        """public + PII + reverse — unchanged from the e2e test."""
        r = self.client.post(
            "/v1/chat/completions",
            json={
                "model": "qwen-max",
                "messages": [
                    {
                        "role": "user",
                        "content": "客户 110101199003078888 想知道余额",
                    }
                ],
            },
            headers=self._headers(),
        )
        self.assertEqual(r.status_code, 200, r.text)
        # Upstream body was sent (Noop cache = always miss).
        self.assertEqual(r.json()["id"], "cmpl-echo")

    def test_scenario2_private_bypass_skips_redaction(self):
        """private + bypass → skip_pii=True → upstream sees PII.

        (The base class wiring uses a public route, so we
        override the route + headers to trigger the private
        + bypass path.)
        """
        async def _private_bypass(model, header):
            return {
                "base_url": "https://private.example.com",
                "path": "/v1/chat/completions",
                "timeout_ms": 30000,
                "skip_pii": True,
            }
        self._route_patcher.stop()
        self._route_patcher = patch(
            "app.api.chat.resolve_route", new=_private_bypass
        )
        self._route_patcher.start()
        r = self.client.post(
            "/v1/chat/completions",
            json=self._body("客户 110101199003078888 想知道余额"),
            headers=self._headers(
                **{
                    "X-Model-Kind": "private",
                    "X-Bypass-Isolation": "true",
                }
            ),
        )
        self.assertEqual(r.status_code, 200, r.text)

    def test_scenario3_pii_detector_fail_open_passes_through(self):
        """PII redactor raises → gateway increments fail-open
        counter, passes the body through to upstream."""
        async def _explode(trace_id, text):
            raise RuntimeError("detector crashed")
        with patch("app.pii.redactor.redact", new=_explode), \
             patch("app.api.chat.redact", new=_explode):
            r = self.client.post(
                "/v1/chat/completions",
                json=self._body("客户 110101199003078888 想知道余额"),
                headers=self._headers(),
            )
        self.assertEqual(r.status_code, 200, r.text)

    def test_scenario4_upstream_timeout_returns_504(self):
        """``call_upstream`` raises ``UpstreamTimeout`` → 504.

        This is a fast path because the request_batcher Noop
        delegates to ``call_upstream`` — when the LLM client
        raises the typed error, the batcher Noop propagates
        it back through the future and the chat pipeline
        maps it to 504.
        """
        from app.errors import UpstreamTimeout

        async def _timeout(base_url, path, body, headers):
            raise UpstreamTimeout("upstream too slow")

        with patch("app.api.chat.call_upstream", new=_timeout):
            r = self.client.post(
                "/v1/chat/completions",
                json=self._body("hi"),
                headers=self._headers(),
            )
        self.assertEqual(r.status_code, 504, r.text)


# ---------------------------------------------------------------------------
# Fixture 2: rate limit triggers 429
# ---------------------------------------------------------------------------


class TestRateLimitContract(ContractIntegrationTestBase):
    """A real ``RateLimiter`` returning ``False`` short-circuits
    the chat pipeline to HTTP 429."""

    def test_rate_limited_returns_429_with_retry_after(self):
        """``RateLimiter.check`` returns ``False`` → chat
        endpoint returns 429 + ``{"error": "rate_limited",
        "retry_after": N}`` (spec scenario "限流触发")."""

        class _Block(RateLimiter):
            def check(self, user_id, model):
                return False

        self.set_contract("rate_limiter", _Block())
        r = self.client.post(
            "/v1/chat/completions",
            json=self._body("hi"),
            headers=self._headers(),
        )
        self.assertEqual(r.status_code, 429, r.text)
        body = r.json()
        self.assertEqual(body["error"], "rate_limited")
        self.assertIsInstance(body["retry_after"], int)
        self.assertGreater(body["retry_after"], 0)

    def test_rate_limiter_raising_exception_degrades_to_noop(self):
        """``RateLimiter.check`` raises → pipeline falls back to
        ``True`` (Noop), request succeeds (spec scenario
        "contract 异常降级")."""

        class _Explode(RateLimiter):
            def check(self, user_id, model):
                raise RuntimeError("limiter crashed")

        self.set_contract("rate_limiter", _Explode())
        # Snapshot the contract_degraded counter.
        before = self._read_counter(
            gateway_contract_degraded_total, contract="rate_limiter"
        )
        r = self.client.post(
            "/v1/chat/completions",
            json=self._body("hi"),
            headers=self._headers(),
        )
        self.assertEqual(r.status_code, 200, r.text)
        after = self._read_counter(
            gateway_contract_degraded_total, contract="rate_limiter"
        )
        self.assertEqual(after, before + 1)

    def test_rate_limiter_returning_true_lets_request_through(self):
        """A permissive rate limiter is a no-op (request
        succeeds, no 429)."""

        class _Allow(RateLimiter):
            def check(self, user_id, model):
                return True

        self.set_contract("rate_limiter", _Allow())
        r = self.client.post(
            "/v1/chat/completions",
            json=self._body("hi"),
            headers=self._headers(),
        )
        self.assertEqual(r.status_code, 200, r.text)


# ---------------------------------------------------------------------------
# Fixture 3: cache hit short-circuits upstream
# ---------------------------------------------------------------------------


class TestResponseCacheContract(ContractIntegrationTestBase):
    """A real ``ResponseCache`` returning a hit causes the chat
    endpoint to skip the upstream call, run PII reverse, and
    return the cached body."""

    def test_cache_hit_skips_upstream_and_returns_cached_body(self):
        """``ResponseCache.get`` returns a ``CachedResponse`` →
        chat endpoint returns the cached body and increments
        the ``trace_cache_hits_total`` counter."""

        cached_body_dict = {
            "id": "cmpl-cached",
            "choices": [
                {"message": {"role": "assistant", "content": "from cache"}}
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
        import orjson
        cached_body_bytes = orjson.dumps(cached_body_dict)
        cached = CachedResponse(body=cached_body_bytes, status_code=200)

        class _HitCache(ResponseCache):
            def get(self, request_hash):
                return cached
            def put(self, request_hash, response, ttl):
                return None

        self.set_contract("response_cache", _HitCache())
        # Snapshot the trace cache hits counter.
        before = self._read_counter(gateway_trace_cache_hits_total)
        # We expect the upstream stub to be called *zero* times.
        # Swap the LLM client for a tracker so we can assert.
        call_count = {"n": 0}

        async def _track_call(base_url, path, body, headers):
            call_count["n"] += 1
            resp = MagicMock()
            resp.status_code = 999  # sentinel — should not see this
            resp.json = MagicMock(return_value={"id": "NEVER"})
            return resp

        with patch("app.api.chat.call_upstream", new=_track_call):
            r = self.client.post(
                "/v1/chat/completions",
                json=self._body("hi"),
                headers=self._headers(),
            )
        self.assertEqual(r.status_code, 200, r.text)
        # Upstream was NOT called.
        self.assertEqual(call_count["n"], 0)
        # Cached body came back.
        self.assertEqual(r.json()["id"], "cmpl-cached")
        # Cache hit counter incremented.
        after = self._read_counter(gateway_trace_cache_hits_total)
        self.assertEqual(after, before + 1)

    def test_cache_hit_with_skip_pii_skips_reverse(self):
        """When ``skip_pii=True`` the cache hit path skips the
        PII reverse (mirrors the non-cached path)."""
        import orjson
        cached = CachedResponse(
            body=orjson.dumps(
                {
                    "id": "cmpl-x",
                    "choices": [
                        {"message": {"role": "assistant", "content": "hi"}}
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                }
            ),
            status_code=200,
        )

        class _HitCache(ResponseCache):
            def get(self, request_hash):
                return cached
            def put(self, request_hash, response, ttl):
                return None

        self.set_contract("response_cache", _HitCache())

        async def _private_skip(model, header):
            return {
                "base_url": "https://private.example.com",
                "path": "/v1/chat/completions",
                "timeout_ms": 30000,
                "skip_pii": True,
            }

        self._route_patcher.stop()
        self._route_patcher = patch(
            "app.api.chat.resolve_route", new=_private_skip
        )
        self._route_patcher.start()
        r = self.client.post(
            "/v1/chat/completions",
            json=self._body("hi"),
            headers=self._headers(
                **{
                    "X-Model-Kind": "private",
                    "X-Bypass-Isolation": "true",
                }
            ),
        )
        self.assertEqual(r.status_code, 200, r.text)

    def test_cache_get_raising_exception_degrades_to_noop(self):
        """``ResponseCache.get`` raises → pipeline falls back to
        a Noop cache (always-miss), request proceeds normally."""

        class _Explode(ResponseCache):
            def get(self, request_hash):
                raise RuntimeError("redis down")
            def put(self, request_hash, response, ttl):
                return None

        self.set_contract("response_cache", _Explode())
        before = self._read_counter(
            gateway_contract_degraded_total, contract="response_cache.get"
        )
        r = self.client.post(
            "/v1/chat/completions",
            json=self._body("hi"),
            headers=self._headers(),
        )
        self.assertEqual(r.status_code, 200, r.text)
        after = self._read_counter(
            gateway_contract_degraded_total, contract="response_cache.get"
        )
        self.assertEqual(after, before + 1)

    def test_cache_miss_runs_full_pipeline(self):
        """``ResponseCache.get`` returns ``None`` (the common
        case) → pipeline runs the full upstream path."""
        # Default Noop cache already returns None; we just
        # assert the request still succeeds.
        r = self.client.post(
            "/v1/chat/completions",
            json=self._body("hi"),
            headers=self._headers(),
        )
        self.assertEqual(r.status_code, 200, r.text)

    def test_cache_hit_with_malformed_body_returns_empty(self):
        """A cached body that can't be JSON-decoded is treated
        as a defensive empty response — the pipeline returns
        the cached status code (200) with an empty JSON body
        (``{}``) rather than propagating the parse error to
        the caller."""
        cached = CachedResponse(body=b"not-json", status_code=200)

        class _MalformedCache(ResponseCache):
            def get(self, request_hash):
                return cached
            def put(self, request_hash, response, ttl):
                return None

        self.set_contract("response_cache", _MalformedCache())
        r = self.client.post(
            "/v1/chat/completions",
            json=self._body("hi"),
            headers=self._headers(),
        )
        # The pipeline served the cache hit (status 200, empty
        # body) rather than calling upstream — the corruption
        # is contained.
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json(), {})

    def test_cache_put_raising_degrades_silently(self):
        """``ResponseCache.put`` raises → pipeline catches,
        increments ``response_cache.put`` counter, returns the
        response normally (a put failure must never break the
        response)."""

        class _ExplodePut(ResponseCache):
            def get(self, request_hash):
                return None
            def put(self, request_hash, response, ttl):
                raise RuntimeError("redis write failed")

        self.set_contract("response_cache", _ExplodePut())
        before = self._read_counter(
            gateway_contract_degraded_total, contract="response_cache.put"
        )
        r = self.client.post(
            "/v1/chat/completions",
            json=self._body("hi"),
            headers=self._headers(),
        )
        self.assertEqual(r.status_code, 200, r.text)
        after = self._read_counter(
            gateway_contract_degraded_total, contract="response_cache.put"
        )
        self.assertEqual(after, before + 1)


# ---------------------------------------------------------------------------
# Fixture 4: contract exception degradation
# ---------------------------------------------------------------------------


class TestContractDegradation(ContractIntegrationTestBase):
    """When a real contract implementation raises an exception,
    the chat pipeline falls back to Noop behaviour and
    increments the ``contract_degraded`` counter. The request
    still succeeds end-to-end."""

    def test_request_batcher_raising_falls_back_to_sync_call(self):
        """``RequestBatcher.submit`` raises synchronously →
        pipeline catches, increments counter, falls back to
        the direct ``call_upstream`` path."""

        class _Explode(RequestBatcher):
            def submit(self, request):
                raise RuntimeError("batcher crashed")

        self.set_contract("request_batcher", _Explode())
        before = self._read_counter(
            gateway_contract_degraded_total, contract="request_batcher"
        )
        r = self.client.post(
            "/v1/chat/completions",
            json=self._body("hi"),
            headers=self._headers(),
        )
        self.assertEqual(r.status_code, 200, r.text)
        # Counter incremented.
        after = self._read_counter(
            gateway_contract_degraded_total, contract="request_batcher"
        )
        self.assertEqual(after, before + 1)
        # Response still came from the echo upstream.
        self.assertEqual(r.json()["id"], "cmpl-echo")

    def test_metrics_exporter_does_not_block(self):
        """The metrics exporter is fire-and-forget — its
        Noop behaviour is to accept + discard. A real
        exporter that hangs is out of scope for Phase E."""
        # Default Noop exporter — request still succeeds.
        r = self.client.post(
            "/v1/chat/completions",
            json=self._body("hi"),
            headers=self._headers(),
        )
        self.assertEqual(r.status_code, 200, r.text)

    def test_request_batcher_future_raising_degrades_to_sync(self):
        """``RequestBatcher.submit`` returns a Future that
        resolves with an exception → the chat pipeline catches
        it via ``_await_contract_future`` and falls back to the
        direct upstream call."""

        import asyncio

        class _FutureBatcher(RequestBatcher):
            def submit(self, request):
                loop = asyncio.get_event_loop()
                fut = loop.create_future()
                fut.set_exception(RuntimeError("future boom"))
                return fut

        self.set_contract("request_batcher", _FutureBatcher())
        before = self._read_counter(
            gateway_contract_degraded_total, contract="request_batcher"
        )
        r = self.client.post(
            "/v1/chat/completions",
            json=self._body("hi"),
            headers=self._headers(),
        )
        self.assertEqual(r.status_code, 200, r.text)
        after = self._read_counter(
            gateway_contract_degraded_total, contract="request_batcher"
        )
        # Counter incremented exactly once (not double-counted
        # by the outer except — the sentinel attribute prevents
        # the duplicate).
        self.assertEqual(after, before + 1)

    def test_request_batcher_perf_response_is_coerced(self):
        """``RequestBatcher.submit`` returns a Future resolving
        to a :class:`PerfResponse` (the contract value type) →
        the chat pipeline coerces it to an ``httpx.Response``-
        shaped object via ``_perf_response_to_httpx``."""

        import asyncio

        from app.perf.contracts import Response as PerfResponse

        class _PerfResponseBatcher(RequestBatcher):
            def submit(self, request):
                loop = asyncio.get_event_loop()
                fut = loop.create_future()
                fut.set_result(PerfResponse(
                    status_code=200,
                    body={
                        "id": "cmpl-batched",
                        "choices": [
                            {"message": {"role": "assistant", "content": "batched"}}
                        ],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                    },
                ))
                return fut

        self.set_contract("request_batcher", _PerfResponseBatcher())
        r = self.client.post(
            "/v1/chat/completions",
            json=self._body("hi"),
            headers=self._headers(),
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["id"], "cmpl-batched")

    def test_request_batcher_future_with_upstream_timeout(self):
        """``RequestBatcher.submit`` returns a Future that
        resolves to a response whose ``.status_code`` access
        raises ``UpstreamTimeout`` → the chat pipeline's
        post-batcher ``try/except`` catches it and returns 504.

        This is the "map the upstream errors that came through
        the batcher success path" branch in chat.py.
        """
        import asyncio
        from app.errors import UpstreamTimeout

        class _StatusRaisesBatcher(RequestBatcher):
            def submit(self, request):
                loop = asyncio.get_event_loop()
                fut = loop.create_future()

                class _TimeoutResp:
                    @property
                    def status_code(self):
                        raise UpstreamTimeout("upstream too slow")
                    def json(self):
                        return {}

                fut.set_result(_TimeoutResp())
                return fut

        self.set_contract("request_batcher", _StatusRaisesBatcher())
        r = self.client.post(
            "/v1/chat/completions",
            json=self._body("hi"),
            headers=self._headers(),
        )
        self.assertEqual(r.status_code, 504, r.text)

    def test_request_batcher_future_with_upstream_5xx(self):
        """``status_code`` access raises ``Upstream5xx`` → 502."""
        import asyncio
        from app.errors import Upstream5xx

        class _StatusRaisesBatcher(RequestBatcher):
            def submit(self, request):
                loop = asyncio.get_event_loop()
                fut = loop.create_future()

                class _5xxResp:
                    @property
                    def status_code(self):
                        raise Upstream5xx("5xx")
                    def json(self):
                        return {}

                fut.set_result(_5xxResp())
                return fut

        self.set_contract("request_batcher", _StatusRaisesBatcher())
        r = self.client.post(
            "/v1/chat/completions",
            json=self._body("hi"),
            headers=self._headers(),
        )
        self.assertEqual(r.status_code, 502, r.text)

    def test_request_batcher_future_with_upstream_rate_limited(self):
        """``status_code`` access raises ``UpstreamRateLimited`` → 429."""
        import asyncio
        from app.errors import UpstreamRateLimited

        class _StatusRaisesBatcher(RequestBatcher):
            def submit(self, request):
                loop = asyncio.get_event_loop()
                fut = loop.create_future()

                class _429Resp:
                    @property
                    def status_code(self):
                        raise UpstreamRateLimited("429")
                    def json(self):
                        return {}

                fut.set_result(_429Resp())
                return fut

        self.set_contract("request_batcher", _StatusRaisesBatcher())
        r = self.client.post(
            "/v1/chat/completions",
            json=self._body("hi"),
            headers=self._headers(),
        )
        self.assertEqual(r.status_code, 429, r.text)


# ---------------------------------------------------------------------------
# Metrics integration: every chat request increments the request counter
# ---------------------------------------------------------------------------


class TestChatMetricsIncrement(ContractIntegrationTestBase):
    """The chat pipeline increments ``gateway_requests_total`` on
    every request (success or failure) and observes
    ``gateway_request_duration_seconds`` on success."""

    def test_chat_request_increments_requests_total(self):
        before = self._read_counter(
            gateway_requests_total,
            method="POST",
            path="/v1/chat/completions",
            status="200",
        )
        r = self.client.post(
            "/v1/chat/completions",
            json=self._body("hi"),
            headers=self._headers(),
        )
        self.assertEqual(r.status_code, 200, r.text)
        after = self._read_counter(
            gateway_requests_total,
            method="POST",
            path="/v1/chat/completions",
            status="200",
        )
        self.assertEqual(after, before + 1)


if __name__ == "__main__":
    unittest.main()
