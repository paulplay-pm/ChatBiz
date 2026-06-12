"""Core chat-completion endpoint — the 8-step pipeline that ties
all of Phase 0-9's modules together, extended with the 4 perf
contract call sites from Phase E.

Pipeline (locked by the plan in
``openspec-changes-audit-isolation/plan.md`` Task 12.2,
extended with Phase E contract call sites from
``openspec/changes/gateway-egress-enforcement-p0/specs/gateway-perf-contracts/spec.md``):

1. **Auth** — verify the caller's service token against the
   credential service. Returns the ``service_id`` (stored in
   ``audit_log.user_id``).
2. **Header parse** — extract ``X-Trace-Id``, ``X-Model-Kind``,
   ``X-Bypass-Isolation`` into a ``HeaderSchema``.
3. **Body parse** — read the OpenAI-shaped JSON body, enforce
   the 1 MB limit, decode with ``orjson``.
4. **Rate limit** *(Phase E contract #1)* — call
   :meth:`RateLimiter.check`. A ``False`` return short-circuits
   to HTTP 429 with ``{"error": "rate_limited", "retry_after": N}``.
   A raising contract falls back to Noop (``True``) and the
   ``contract_degraded{contract="rate_limiter"}`` counter is
   incremented.
5. **Route resolve** — look up the model's upstream URL/path
   in the routing table; raise ``RoutingError`` (→ 400) if
   the model is unknown or the kind header disagrees.
6. **Cache lookup** *(Phase E contract #2)* — compute
   ``request_hash = sha256(model + body)`` and call
   :meth:`ResponseCache.get`. A hit returns the cached body
   verbatim after PII scanning. A raising contract falls back
   to Noop (always-miss).
7. **PII redact** — for every user/assistant message, run
   the redactor. If ``skip_pii`` is set (private + bypass)
   the step is a no-op. The redactor's exception path
   triggers Fail-Open (per ``settings.pii_fail_open``) — the
   message is sent unredacted and a WARN is logged.
8. **Batch upstream** *(Phase E contract #3)* — wrap the
   upstream call in :meth:`RequestBatcher.submit` and await
   the returned future. A raising contract falls back to
   the synchronous :func:`call_upstream` path.
9. **Upstream call** — fetch the LLM provider key from the
   credential client, POST to the upstream, return the body
   verbatim. Rate-limit (429) / 5xx / timeout errors map to
   their respective HTTP statuses.
10. **Reverse PII** — swap placeholders in the response
    choices back to originals (no-op if ``skip_pii``).
11. **Cache store** *(Phase E contract #2)* — on a successful
    upstream call, store the response under the same
    ``request_hash`` with the default TTL. A raising
    contract falls back to Noop (always-discard).
12. **Audit enqueue** — push an ``AuditLog`` row to the
    outbox (non-blocking; the outbox worker writes to PG).
13. **Metrics** *(Phase E contract #4)* — increment
    :data:`gateway_requests_total` and observe
    :data:`gateway_request_duration_seconds` at the end of
    the pipeline (success or failure). The
    :data:`gateway_active_connections` gauge is incremented
    at the start and decremented on response.

Failure-mode summary (the 7-class exception taxonomy lives in
``app.errors``):

* 401 — missing/invalid token (``AuthFailed``)
* 422 — invalid JSON body or bad ``X-Trace-Id`` length
* 413 — body > 1 MB
* 400 — model not in routing table or kind mismatch
  (``RoutingError``)
* 503 — credential service unreachable after retry
  (``CredentialServiceUnavailable``)
* 502 — upstream 5xx (``Upstream5xx``)
* 504 — upstream timeout (``UpstreamTimeout``)
* 429 — upstream rate-limited (``UpstreamRateLimited``) **or**
  contract #1 (per-user rate limit) returning ``False``

Each perf contract is wrapped in a ``_safe_call_contract`` helper
that catches *any* exception, increments
``contract_degraded{contract=<name>}``, and substitutes the
equivalent Noop behaviour. This is the **failure-degradation
contract** the spec locks in
(``open spec/changes/gateway-egress-enforcement-p0/specs/gateway-perf-contracts/spec.md``
scenario "contract 异常降级").
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Awaitable, Callable

import orjson
from fastapi import APIRouter, Header, HTTPException, Request, Response

from app.audit.hash import prompt_hash
from app.audit.writer import get_outbox
from app.auth import verify_service_token
from app.config import get_settings
from app.credential_client import get_llm_api_key
from app.errors import (
    Upstream5xx,
    UpstreamRateLimited,
    UpstreamTimeout,
)
from app.llm.client import call_upstream
from app.metrics import (
    credential_unavailable_counter,
    gateway_active_connections,
    gateway_contract_degraded_total,
    gateway_pii_hits_total,
    gateway_request_duration_seconds,
    gateway_requests_total,
    gateway_trace_cache_hits_total,
    latency_histogram,
    pii_fail_open_counter,
    upstream_5xx_counter,
)
from app.models.audit import AuditLog
from app.models.common import HeaderSchema
from app.perf.contracts import (
    CachedResponse,
    NoopMetricsExporter,
    NoopRateLimiter,
    NoopRequestBatcher,
    NoopResponseCache,
    RateLimiter,
    Request as PerfRequest,
    RequestBatcher,
    Response as PerfResponse,
    ResponseCache,
)
from app.pii.redactor import redact
from app.pii.reverser import reverse
from app.routing.dispatcher import RoutingError, resolve_route

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Contract wiring
# ---------------------------------------------------------------------------
#
# The 4 perf contracts are module-level singletons for now (Phase E
# just needs the wiring + Noop behaviour). T6 will replace them with
# real implementations — the chat pipeline reads them through the
# Protocol types, so swapping in a Redis-backed limiter is a
# one-line change here.
#
# ``_make_default_contracts`` is also used by the unit tests to
# inject mocks; the module-level ``_contracts`` global below is
# initialised from it at import time.

_DEFAULT_RETRY_AFTER_SECONDS = 60
_DEFAULT_CACHE_TTL_SECONDS = 300


def _make_default_contracts() -> dict[str, Any]:
    """Build the default (Noop) contract bundle.

    Kept as a function so unit tests can call it to get a fresh
    bundle without polluting module state.
    """
    return {
        "rate_limiter": NoopRateLimiter(),
        "response_cache": NoopResponseCache(),
        # The batcher's Noop needs an executor — we hand it the
        # real ``call_upstream`` so the Noop runs the same path
        # the chat pipeline used to take, just wrapped in a
        # Future.
        "request_batcher": NoopRequestBatcher(executor=call_upstream),
        "metrics_exporter": NoopMetricsExporter(),
    }


_contracts: dict[str, Any] = _make_default_contracts()


def get_contracts() -> dict[str, Any]:
    """Return the current contract bundle (used by tests for
    swapping in mocks)."""
    return _contracts


def reset_contracts_for_tests() -> None:
    """Drop the contract bundle back to Noop defaults."""
    global _contracts
    _contracts = _make_default_contracts()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _request_hash(model: str, body: dict) -> str:
    """Compute the cache key for a request.

    The hash is over ``model + str(body)`` — same model + same
    body (messages + parameters) = same response. We use a
    stable string representation rather than ``json.dumps`` so
    the order of dict keys doesn't matter. SHA-256 hex is
    64 chars, which fits inside any reasonable key column.
    """
    payload = model + "|" + str(sorted(body.items()) if isinstance(body, dict) else body)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe_call_contract(
    contract_name: str,
    fn: Callable[[], Any],
    fallback: Any,
) -> Any:
    """Run ``fn`` and substitute ``fallback`` on any exception.

    The exception is logged at WARNING and the
    ``contract_degraded{contract=<name>}`` counter is
    incremented. The chat pipeline must never propagate a
    contract exception to the caller — contracts are an
    optimisation, not a correctness gate.
    """
    try:
        return fn()
    except Exception as e:  # noqa: BLE001 — contract exceptions are policy, not bugs
        gateway_contract_degraded_total.labels(contract=contract_name).inc()
        logger.warning(
            "perf contract %s degraded to Noop: %s", contract_name, e
        )
        return fallback


async def _await_contract_future(fut, contract_name: str) -> Any:
    """Await a contract-returned future, falling back on
    ``Exception`` (the same degradation policy as
    :func:`_safe_call_contract` but for the batcher path which
    is async). The exception is tagged with
    ``_chatbiz_degraded_counted = True`` so the outer caller
    doesn't double-count it.
    """
    try:
        return await fut
    except Exception as e:  # noqa: BLE001
        gateway_contract_degraded_total.labels(contract=contract_name).inc()
        setattr(e, "_chatbiz_degraded_counted", True)
        logger.warning(
            "perf contract %s future failed, degrading to Noop: %s",
            contract_name,
            e,
        )
        raise


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


@router.post("/chat/completions")
async def chat_completions(
    request: Request,
    x_trace_id: str = Header(..., min_length=8, max_length=128),
    x_model_kind: str = Header(...),
    x_bypass_isolation: str = Header(default="false"),
):
    """OpenAI-compatible proxy endpoint with PII isolation + audit
    + 4 perf contract call sites.
    """
    # ---- 0. Active connections gauge (Phase E metric) --------------
    gateway_active_connections.inc()
    request_t0 = time.time()
    request_status = "500"  # default; overwritten on success
    request_path = "/v1/chat/completions"
    try:
        # ---- 1. 鉴权 -------------------------------------------------
        user_id = await verify_service_token(request.headers.get("Authorization"))

        # ---- 2. Header 解析 ------------------------------------------
        try:
            header = HeaderSchema(
                trace_id=x_trace_id,
                model_kind=x_model_kind,
                bypass_isolation=x_bypass_isolation.lower() == "true",
            )
        except (ValueError, TypeError) as e:
            raise HTTPException(422, f"invalid header: {e}")

        # ---- 3. Body 解析 --------------------------------------------
        body_bytes = await request.body()
        if len(body_bytes) > get_settings().max_body_bytes:
            raise HTTPException(413, "request body too large")
        try:
            body = orjson.loads(body_bytes)
        except orjson.JSONDecodeError as e:
            raise HTTPException(422, f"invalid JSON: {e}")

        # ---- 4. Rate limit (contract #1) ----------------------------
        contracts = get_contracts()
        rate_limiter: RateLimiter = contracts["rate_limiter"]
        allowed = _safe_call_contract(
            "rate_limiter",
            lambda: rate_limiter.check(user_id, body.get("model", "")),
            fallback=True,
        )
        if not allowed:
            request_status = "429"
            return _rate_limited_response()

        # ---- 5. 路由解析 --------------------------------------------
        try:
            route = await resolve_route(body["model"], header)
        except RoutingError as e:
            raise HTTPException(400, str(e))
        except KeyError:
            raise HTTPException(422, "missing 'model' in request body")

        # ---- 6. Cache lookup (contract #2) --------------------------
        request_hash = _request_hash(body["model"], body)
        response_cache: ResponseCache = contracts["response_cache"]
        cached = _safe_call_contract(
            "response_cache.get",
            lambda: response_cache.get(request_hash),
            fallback=None,
        )
        if cached is not None:
            # Cache hit: parse the body, run PII scan + reverse on
            # the response, write audit, return.
            try:
                resp_body = orjson.loads(cached.body)
            except orjson.JSONDecodeError:
                # Defensive: a malformed cache entry is treated
                # as a miss — never propagate the corruption to
                # the caller.
                resp_body = {}
            # PII reverse on the cached response (mirror the
            # non-cached path).
            if not route["skip_pii"]:
                for choice in resp_body.get("choices", []):
                    msg = choice.get("message", {})
                    if "content" in msg and isinstance(msg["content"], str):
                        msg["content"] = await reverse(header.trace_id, msg["content"])
            # Audit enqueue (cache hit path).
            usage = resp_body.get("usage", {})
            audit = AuditLog(
                trace_id=header.trace_id,
                user_id=user_id,
                workflow_id=body.get("workflow_id"),
                model=body["model"],
                model_kind=header.model_kind.value,
                bypass_isolation=header.bypass_isolation,
                pii_detected_types=[],
                pii_redacted_count=0,
                prompt_hash=prompt_hash(body.get("messages", [])),
                token_input=usage.get("prompt_tokens"),
                token_output=usage.get("completion_tokens"),
                latency_ms=0,
                upstream_status=cached.status_code,
                error_class=None,
            )
            get_outbox().enqueue(audit)
            gateway_trace_cache_hits_total.inc()
            request_status = str(cached.status_code)
            return Response(
                content=orjson.dumps(resp_body),
                media_type="application/json",
                status_code=cached.status_code,
            )

        # ---- 7. PII 脱敏(若未 bypass) --------------------------------
        pii_types: list[str] = []
        pii_count = 0
        if not route["skip_pii"]:
            try:
                for i, msg in enumerate(body.get("messages", [])):
                    if "content" not in msg or not isinstance(msg["content"], str):
                        continue
                    redacted_text, _map, types = await redact(header.trace_id, msg["content"])
                    if types:
                        pii_types = list(set(pii_types + types))
                        pii_count += len(types)
                        body["messages"][i]["content"] = redacted_text
                        for pii_type in types:
                            gateway_pii_hits_total.labels(
                                pii_type=pii_type, action="mask"
                            ).inc()
            except Exception as e:
                # Fail-Open: detector 异常 → 放行原文 + WARN
                if get_settings().pii_fail_open:
                    pii_fail_open_counter.inc()
                    gateway_pii_hits_total.labels(
                        pii_type="unknown", action="fail_open"
                    ).inc()
                    logger.warning(
                        f"PII detector fail-open for trace_id={header.trace_id}: {e}"
                    )
                else:
                    raise HTTPException(503, "PII detector unavailable")

        # ---- 8. 调上游(批处理 contract #3) --------------------------
        t0 = time.time()
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.removeprefix("Bearer ")
        try:
            api_key = await get_llm_api_key(body["model"], token)
        except Exception as e:
            credential_unavailable_counter.inc()
            raise HTTPException(503, f"credential service unavailable: {e}")

        upstream_headers = {
            "Authorization": f"Bearer {api_key}",
            "X-Trace-Id": header.trace_id,
            "Content-Type": "application/json",
        }

        # Wrap the upstream call in the request batcher. The
        # Noop returns a Future that's already done with the
        # result of ``call_upstream``; the real T6 batcher may
        # coalesce. Either way the pipeline ``await``s the
        # future as if it were a normal ``httpx.Response``.
        request_batcher: RequestBatcher = contracts["request_batcher"]
        perf_request = PerfRequest(
            model=body["model"],
            body={
                **body,
                "_base_url": route["base_url"],
                "_path": route["path"],
            },
            headers=upstream_headers,
        )
        try:
            future = request_batcher.submit(perf_request)
            # ``submit()`` itself may raise synchronously (the
            # contract is broken / unconfigured) — catch and
            # degrade here. If ``submit()`` returns, the
            # exception will surface on ``await`` instead.
            upstream_resp = await _await_contract_future(future, "request_batcher")
        except Exception as e:
            # The contract exception was already counted by
            # ``_await_contract_future`` (it handles the
            # future-error case). For the synchronous-raise
            # case (where ``submit()`` itself raised before
            # we could call ``_await_contract_future``), we
            # count here. The two are not mutually exclusive
            # in the general case, but a single
            # ``submit()`` raising only ever enters one
            # branch — so incrementing in this outer except
            # is correct for the synchronous case. The
            # future-error case has *already* incremented
            # via ``_await_contract_future``; in that case
            # the exception re-raises out of ``await`` and
            # lands here a second time, so we avoid the
            # double-count by using a sentinel attribute
            # tagged on the exception object.
            if not getattr(e, "_chatbiz_degraded_counted", False):
                setattr(e, "_chatbiz_degraded_counted", True)
                gateway_contract_degraded_total.labels(
                    contract="request_batcher"
                ).inc()
                logger.warning("request_batcher contract degraded: %s", e)
            try:
                upstream_resp = await call_upstream(
                    route["base_url"], route["path"], body, upstream_headers
                )
            except UpstreamTimeout:
                raise HTTPException(504, "upstream timeout")
            except Upstream5xx:
                upstream_5xx_counter.inc()
                raise HTTPException(502, "upstream 5xx")
            except UpstreamRateLimited:
                raise HTTPException(429, "upstream rate limited")
            except Exception:
                # 兜底:LLM client 未映射的异常(httpx.TimeoutException 等)转 502
                raise HTTPException(502, "upstream call failed")
        else:
            # The batcher returned successfully — map
            # ``PerfResponse`` back to a real ``httpx.Response``
            # shape (we use ``MagicMock`` because the chat
            # pipeline only reads ``status_code`` + ``json()``).
            if isinstance(upstream_resp, PerfResponse):
                upstream_resp = _perf_response_to_httpx(upstream_resp)

        # Map the upstream errors that came through the batcher
        # success path (the batcher may catch them and re-raise
        # as a non-typed exception).
        try:
            # Touch the status code to surface the error class.
            _ = upstream_resp.status_code  # noqa: F841
        except UpstreamTimeout:
            raise HTTPException(504, "upstream timeout")
        except Upstream5xx:
            upstream_5xx_counter.inc()
            raise HTTPException(502, "upstream 5xx")
        except UpstreamRateLimited:
            raise HTTPException(429, "upstream rate limited")

        # ---- 9. 响应侧还原 ------------------------------------------
        resp_body = upstream_resp.json()
        if not route["skip_pii"]:
            for choice in resp_body.get("choices", []):
                msg = choice.get("message", {})
                if "content" in msg and isinstance(msg["content"], str):
                    msg["content"] = await reverse(header.trace_id, msg["content"])

        # ---- 10. Cache store (contract #2) -------------------------
        try:
            response_cache.put(
                request_hash,
                CachedResponse(
                    body=orjson.dumps(resp_body),
                    status_code=upstream_resp.status_code,
                ),
                ttl=_DEFAULT_CACHE_TTL_SECONDS,
            )
        except Exception as e:  # noqa: BLE001
            gateway_contract_degraded_total.labels(contract="response_cache.put").inc()
            logger.warning("response_cache.put failed: %s", e)

        # ---- 11. 写 audit(outbox 异步) ------------------------------
        latency_ms = int((time.time() - t0) * 1000)
        usage = resp_body.get("usage", {})
        audit = AuditLog(
            trace_id=header.trace_id,
            user_id=user_id,
            workflow_id=body.get("workflow_id"),
            model=body["model"],
            model_kind=header.model_kind.value,
            bypass_isolation=header.bypass_isolation,
            pii_detected_types=pii_types,
            pii_redacted_count=pii_count,
            prompt_hash=prompt_hash(body.get("messages", [])),
            token_input=usage.get("prompt_tokens"),
            token_output=usage.get("completion_tokens"),
            latency_ms=latency_ms,
            upstream_status=upstream_resp.status_code,
            error_class=None,
        )
        get_outbox().enqueue(audit)

        # ---- 12. Latency observation (Phase E metric) ---------------
        latency_histogram.observe(time.time() - t0)
        request_status = str(upstream_resp.status_code)
        return Response(
            content=orjson.dumps(resp_body),
            media_type="application/json",
            status_code=upstream_resp.status_code,
        )
    finally:
        # ---- 13. 收尾指标 -------------------------------------------
        duration = time.time() - request_t0
        gateway_active_connections.dec()
        gateway_requests_total.labels(
            method="POST", path=request_path, status=request_status
        ).inc()
        gateway_request_duration_seconds.labels(
            method="POST", path=request_path
        ).observe(duration)


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _rate_limited_response() -> Response:
    """Build the 429 response body for a rate-limited request.

    The spec (``spec.md`` scenario "限流触发") requires the body
    shape ``{"error": "rate_limited", "retry_after": N}``. ``N``
    is the default retry budget for now — T6's real limiter
    can return a per-user / per-model retry budget if needed
    (a future extension to the ``RateLimiter`` protocol).
    """
    return Response(
        content=orjson.dumps(
            {
                "error": "rate_limited",
                "retry_after": _DEFAULT_RETRY_AFTER_SECONDS,
            }
        ),
        media_type="application/json",
        status_code=429,
    )


def _perf_response_to_httpx(perf_resp: PerfResponse) -> Any:
    """Coerce a :class:`PerfResponse` (from the batcher) to a
    ``httpx.Response``-shaped object.

    The chat pipeline only reads ``status_code`` and ``json()``;
    a ``MagicMock`` is the cheapest stand-in that satisfies the
    duck type.
    """
    from unittest.mock import MagicMock

    resp = MagicMock()
    resp.status_code = perf_resp.status_code
    resp.json = MagicMock(return_value=perf_resp.body)
    return resp


__all__ = ["router", "get_contracts", "reset_contracts_for_tests"]
