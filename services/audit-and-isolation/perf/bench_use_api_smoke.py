"""In-process 500-op use-API smoke for the chat endpoint.

Bypasses HTTP entirely: imports the FastAPI app and drives
``POST /v1/chat/completions`` via ``TestClient`` (which uses
``httpx`` under the hood) without binding a port. 500 ops
is enough to surface hot-path allocation / GC issues; the
p99 latency is the SLO gate.

We patch the auth, routing, credential, and LLM-upstream
boundaries so the test runs offline (no PG / Redis /
credential service / upstream LLM needed). The smoke is
about *the gateway's own latency*, not the upstream's.

Run::

    python perf/bench_use_api_smoke.py

The script exits non-zero if the 500 ops don't all complete
within the budget, OR if the p99 latency breaches the SLO.
"""

from __future__ import annotations

import os
import statistics
import time
from unittest.mock import AsyncMock, MagicMock, patch

# Env-var defaults so ``Settings`` validates.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x")
os.environ.setdefault("REDIS_URL", "redis://x")
os.environ.setdefault("CREDENTIAL_SERVICE_URL", "http://x")

import fakeredis.aioredis  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app import redis_client  # noqa: E402
from app.main import app  # noqa: E402


N_OPS = 500
SLO_P99_MS = 50.0


def _build_client() -> TestClient:
    """Build a TestClient with every external boundary stubbed.

    Returns a context-manager-free client (the ``with`` block is
    used below for lifespan setup)."""

    # fakeredis for the PII map round-trip.
    redis_client.reset_pool_for_tests()
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    redis_client.get_redis = lambda: fake

    # Auth → fixed service_id.
    app.dependency_overrides_clear()
    # We patch at the call site, not via FastAPI dependency, because
    # ``verify_service_token`` is called as a function (not a
    # ``Depends()``) in the chat handler.

    return TestClient(app)


def main() -> int:
    client = _build_client()
    latencies: list[float] = []
    errors = 0
    with patch(
        "app.api.chat.verify_service_token", new=AsyncMock(return_value="svc-bench")
    ), patch(
        "app.routing.dispatcher.get_routing",
        new=AsyncMock(
            return_value={
                "model_kind": "public",
                "upstream_base_url": "https://upstream.example.com",
                "upstream_path": "/v1/chat/completions",
                "timeout_ms": 30000,
            }
        ),
    ), patch(
        "app.api.chat.get_llm_api_key", new=AsyncMock(return_value="sk-bench")
    ), patch(
        "app.api.chat.call_upstream", new=AsyncMock(
            return_value=_fake_upstream_response()
        )
    ):
        for i in range(N_OPS):
            t0 = time.perf_counter()
            try:
                r = client.post(
                    "/v1/chat/completions",
                    headers={
                        "X-Trace-Id": f"01HX{'A' * 12}{i:04d}",
                        "X-Model-Kind": "public",
                        "Authorization": "Bearer bench",
                    },
                    json={
                        "model": "qwen-max",
                        "messages": [{"role": "user", "content": "hi"}],
                    },
                )
                if r.status_code != 200:
                    errors += 1
            except Exception:
                errors += 1
            latencies.append((time.perf_counter() - t0) * 1000)
    if errors:
        print(f"FAIL: {errors}/{N_OPS} requests errored")
        return 1
    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = statistics.quantiles(latencies, n=20)[-1]
    p99 = statistics.quantiles(latencies, n=100)[-1]
    print(
        f"ops={N_OPS} P50={p50:.2f}ms P95={p95:.2f}ms P99={p99:.2f}ms"
    )
    if p99 >= SLO_P99_MS:
        print(f"FAIL: P99 {p99:.2f}ms exceeds SLO {SLO_P99_MS}ms")
        return 1
    print(f"PASS: P99 {p99:.2f}ms < SLO {SLO_P99_MS}ms")
    return 0


def _fake_upstream_response() -> MagicMock:
    """Build a fake httpx response with the OpenAI shape."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json = MagicMock(
        return_value={
            "id": "cmpl-bench",
            "choices": [
                {"message": {"role": "assistant", "content": "ok"}},
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
    )
    return resp


if __name__ == "__main__":
    raise SystemExit(main())
