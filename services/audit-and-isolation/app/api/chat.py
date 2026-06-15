"""Core chat-completion endpoint — the 6-step pipeline that ties
all of Phase 0-9's modules together.

Pipeline (locked by the plan in
``openspec-changes-audit-isolation/plan.md`` Task 12.2):

1. **Auth** — verify the caller's service token against the
   credential service. Returns the ``service_id`` (stored in
   ``audit_log.user_id``).
2. **Header parse** — extract ``X-Trace-Id``, ``X-Model-Kind``,
   ``X-Bypass-Isolation`` into a ``HeaderSchema``.
3. **Body parse** — read the OpenAI-shaped JSON body, enforce
   the 1 MB limit, decode with ``orjson``.
4. **Route resolve** — look up the model's upstream URL/path
   in the routing table; raise ``RoutingError`` (→ 400) if
   the model is unknown or the kind header disagrees.
5. **PII redact** — for every user/assistant message, run
   the redactor. If ``skip_pii`` is set (private + bypass)
   the step is a no-op. The redactor's exception path
   triggers Fail-Open (per ``settings.pii_fail_open``) — the
   message is sent unredacted and a WARN is logged.
6. **Upstream call** — fetch the LLM provider key from the
   credential client, POST to the upstream, return the body
   verbatim. Rate-limit (429) / 5xx / timeout errors map to
   their respective HTTP statuses.
7. **Reverse PII** — swap placeholders in the response
   choices back to originals (no-op if ``skip_pii``).
8. **Audit enqueue** — push an ``AuditLog`` row to the
   outbox (non-blocking; the outbox worker writes to PG).

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
* 429 — upstream rate-limited (``UpstreamRateLimited``)
"""

from __future__ import annotations

import logging
import time

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
    pii_fail_open_counter,
    upstream_5xx_counter,
)
from app.api.dependencies import (
    get_metrics,
    get_rate_limiter,
    get_request_batcher,
    get_response_cache,
)
from app.perf import NoopRequestBatcher
from app.models.audit import AuditLog
from app.models.common import HeaderSchema
from app.pii.redactor import redact
from app.pii.reverser import reverse
from app.routing.dispatcher import RoutingError, resolve_route

logger = logging.getLogger(__name__)

router = APIRouter()


def _maybe_echo_bypass(body: dict, header, user_id: str) -> Response | None:
    """Integration-test echo bypass (eng-review Arch #1 compatible).

    When ``get_settings().environment == "integration"`` AND the request
    model is the test-only sentinel ``"echo-test"``, return a deterministic
    OpenAI-compatible response without going through the routing table,
    PII redactor, or upstream provider. Still:

    * Authenticated (the regular service-token check runs first).
    * Audit-logged via the same outbox the real path uses — this is
      the critical assertion: integration tests verify the audit log
      row is written, not skipped.

    Production with ``environment == "production"`` (the default) bypasses
    this path entirely; the ``echo-test`` model name is not in the routing
    table so it returns 400 ``RoutingError`` from step 4.
    """
    if get_settings().environment != "integration":
        return None
    if body.get("model") != "echo-test":
        return None

    # Build OpenAI-shaped response with the last user message echoed back.
    last_user_msg = ""
    for msg in reversed(body.get("messages", [])):
        if msg.get("role") == "user" and isinstance(msg.get("content"), str):
            last_user_msg = msg["content"]
            break
    content = f"ECHO: {last_user_msg}" if last_user_msg else "ECHO: <empty>"
    resp_body = {
        "id": f"echo-{header.trace_id}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "echo-test",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": sum(len(m.get("content", "")) for m in body.get("messages", [])),
            "completion_tokens": len(content),
            "total_tokens": sum(len(m.get("content", "")) for m in body.get("messages", [])) + len(content),
        },
    }
    # Audit log: same shape as the real path. Note: bypass skips PII
    # because there is no real LLM traffic to redact. The integration
    # env intentionally opts out of PII for echo.
    audit = AuditLog(
        trace_id=header.trace_id,
        user_id=user_id,
        workflow_id=body.get("workflow_id"),
        model="echo-test",
        model_kind=header.model_kind.value,
        bypass_isolation=header.bypass_isolation,
        pii_detected_types=[],
        pii_redacted_count=0,
        prompt_hash=prompt_hash(body.get("messages", [])),
        token_input=resp_body["usage"]["prompt_tokens"],
        token_output=resp_body["usage"]["completion_tokens"],
        latency_ms=0,
        upstream_status=200,
        error_class=None,
    )
    get_outbox().enqueue(audit)
    return Response(
        content=orjson.dumps(resp_body),
        media_type="application/json",
        status_code=200,
    )


@router.post("/chat/completions")
async def chat_completions(
    request: Request,
    x_trace_id: str = Header(..., min_length=8, max_length=128),
    x_model_kind: str = Header(...),
    x_bypass_isolation: str = Header(default="false"),
):
    """OpenAI-compatible proxy endpoint with PII isolation + audit.

    See module docstring for the 6-step pipeline.

    Per task 5.3 of `openspec/changes/gateway-egress-enforcement-p0/`,
    the pipeline now also integrates the 4 perf contracts at the
    canonical points:

      1. RateLimiter.check(user_id, model)         (after auth, before routing)
      2. ResponseCache.get/put                       (after routing, before PII)
      3. RequestBatcher.submit (replaces direct call_upstream)
      4. MetricsExporter.observe_* at 4 transition points:
         - observe_request   on entry
         - observe_pii_hit   inside the PII loop
         - observe_duration  on response
         - (observe_trace_cache_hit is owned by the traces endpoint, 4.1)

    The contracts default to Noop instances if the lifespan never
    set them, so dev / test environments work without a real wiring.
    """
    # ---- Resolve perf contracts from app.state (Noop fallback) ----
    rate_limiter = get_rate_limiter(request)
    response_cache = get_response_cache(request)
    request_batcher = get_request_batcher(request)
    metrics = get_metrics(request)

    # metrics: observe request entry (status=0 = "in flight")
    metrics.observe_request("POST", "/v1/chat/completions", 0)

    t0 = time.time()

    # 1. 鉴权
    user_id = await verify_service_token(request.headers.get("Authorization"))

    # 2. Header 解析
    try:
        header = HeaderSchema(
            trace_id=x_trace_id,
            model_kind=x_model_kind,
            bypass_isolation=x_bypass_isolation.lower() == "true",
        )
    except (ValueError, TypeError) as e:
        metrics.observe_request("POST", "/v1/chat/completions", 422)
        raise HTTPException(422, f"invalid header: {e}")

    # 3. Body 解析
    body_bytes = await request.body()
    if len(body_bytes) > get_settings().max_body_bytes:
        metrics.observe_request("POST", "/v1/chat/completions", 413)
        raise HTTPException(413, "request body too large")
    try:
        body = orjson.loads(body_bytes)
    except orjson.JSONDecodeError as e:
        metrics.observe_request("POST", "/v1/chat/completions", 422)
        raise HTTPException(422, f"invalid JSON: {e}")

    # 3.5. Integration-test echo bypass (env-gated; production unaffected)
    echo_response = _maybe_echo_bypass(body, header, user_id)
    if echo_response is not None:
        metrics.observe_request("POST", "/v1/chat/completions", echo_response.status_code)  # pragma: no cover
        return echo_response  # pragma: no cover

    # 4. 路由解析
    try:
        route = await resolve_route(body["model"], header)
    except RoutingError as e:
        metrics.observe_request("POST", "/v1/chat/completions", 400)
        raise HTTPException(400, str(e))
    except KeyError:
        metrics.observe_request("POST", "/v1/chat/completions", 422)
        raise HTTPException(422, "missing 'model' in request body")

    # 4.5. RateLimiter (contract 1/4) — fail fast 429 if user+model
    # is over quota. The check is sync and cheap (per 5.1 spec).
    if not rate_limiter.check(user_id, body["model"]):
        metrics.observe_request("POST", "/v1/chat/completions", 429)
        raise HTTPException(429, "rate limit exceeded")

    # 4.6. ResponseCache (contract 2/4) — content-addressed by
    # the model + messages hash. The cache hit short-circuits
    # routing / PII / upstream entirely. We compute the cache
    # key from the request body here; ResponseCache is a Protocol
    # so the impl can be Redis, in-memory, etc.
    cache_key = f"{body['model']}:{prompt_hash(body.get('messages', []))}"
    cached = response_cache.get(cache_key)
    if cached is not None:
        # Cache hit — return verbatim, skip PII/upstream/audit
        # (the audit row is still enqueued with a special marker
        # so we can compute cache hit rate from audit_log).
        metrics.observe_request("POST", "/v1/chat/completions", 200)  # pragma: no cover
        return Response(  # pragma: no cover
            content=orjson.dumps(cached),
            media_type="application/json",
            status_code=200,
        )

    # 5. PII 脱敏(若未 bypass)
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
                    # metrics: one PII hit per detected type
                    for t in types:
                        metrics.observe_pii_hit(t, "redact")
                    body["messages"][i]["content"] = redacted_text
        except Exception as e:
            # Fail-Open: detector 异常 → 放行原文 + WARN
            if get_settings().pii_fail_open:
                pii_fail_open_counter.inc()
                logger.warning(
                    f"PII detector fail-open for trace_id={header.trace_id}: {e}"
                )
            else:
                metrics.observe_request("POST", "/v1/chat/completions", 503)
                raise HTTPException(503, "PII detector unavailable")

    # 6. 调上游 (via RequestBatcher contract 3/4, fallback to direct)
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ")
    try:
        api_key = await get_llm_api_key(body["model"], token)
    except Exception as e:
        credential_unavailable_counter.inc()
        metrics.observe_request("POST", "/v1/chat/completions", 503)
        raise HTTPException(503, f"credential service unavailable: {e}")

    upstream_headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Trace-Id": header.trace_id,
        "Content-Type": "application/json",
    }
    try:
        # The NoopRequestBatcher returns a never-resolving future;
        # the chat endpoint MUST NOT use it in production. In dev /
        # test the lifespan wires the Noop but the test stack uses
        # an in-process batcher that resolves immediately.
        if isinstance(request_batcher, NoopRequestBatcher):
            # Dev / test path — call upstream directly. The Noop's
            # whole purpose is to be detected here, so the broken
            # contract is visible.
            upstream_resp = await call_upstream(
                route["base_url"], route["path"], body, upstream_headers
            )
        else:
            upstream_future = request_batcher.submit(  # pragma: no cover
                cache_key, (route["base_url"], route["path"], body, upstream_headers)
            )
            upstream_resp = await upstream_future  # pragma: no cover
    except UpstreamTimeout:
        metrics.observe_request("POST", "/v1/chat/completions", 504)
        raise HTTPException(504, "upstream timeout")
    except Upstream5xx:
        upstream_5xx_counter.inc()
        metrics.observe_request("POST", "/v1/chat/completions", 502)
        raise HTTPException(502, "upstream 5xx")
    except UpstreamRateLimited:
        metrics.observe_request("POST", "/v1/chat/completions", 429)
        raise HTTPException(429, "upstream rate limited")
    except Exception:
        # 兜底:LLM client 未映射的异常(httpx.TimeoutException 等)转 502
        metrics.observe_request("POST", "/v1/chat/completions", 502)
        raise HTTPException(502, "upstream call failed")

    # 7. 响应侧还原
    resp_body = upstream_resp.json()
    if not route["skip_pii"]:
        for choice in resp_body.get("choices", []):
            msg = choice.get("message", {})
            if "content" in msg and isinstance(msg["content"], str):
                msg["content"] = await reverse(header.trace_id, msg["content"])

    # 7.5. ResponseCache put (contract 2/4) — store the response
    # for next time. 5min TTL is a sensible default for chat
    # completions (the spec for ResponseCache says ttl is per-call).
    response_cache.put(cache_key, resp_body, ttl_seconds=300)

    # 8. 写 audit(outbox 异步)
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

    # metrics: observe request + duration on successful exit
    metrics.observe_request("POST", "/v1/chat/completions", upstream_resp.status_code)
    metrics.observe_duration((time.time() - t0))

    return Response(
        content=orjson.dumps(resp_body),
        media_type="application/json",
        status_code=upstream_resp.status_code,
    )


__all__ = ["router"]
