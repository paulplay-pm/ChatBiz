"""Liveness + readiness probes.

* ``GET /healthz`` — liveness. **200 normally, 503 when draining.**
  Per task 2.1 of `openspec/changes/gateway-egress-enforcement-p0/`:
  when K8s preStop fires (SIGTERM → FastAPI lifespan __aexit__), the
  service flips ``app.state.draining = True`` BEFORE stopping the
  outbox or disposing the engine. The NGINX stream L4 LB (task 2.3)
  checks /healthz on each upstream; once it sees 503 it stops sending
  new traffic, and the 30s `preStop sleep` gives in-flight requests
  time to finish.

  Yes, returning 503 on a liveness probe violates the usual Kubernetes
  convention ("liveness = process is alive, period"). The deviation
  is deliberate: audit-and-isolation is the egress enforcement point
  (eng-review decision #1). A pod that says "I'm alive" while refusing
  to drain correctly would leak in-flight LLM calls outside the
  audit-and-isolation policy. During normal operation, /healthz is
  never 503 — only the K8s preStop window. After
  `terminationGracePeriodSeconds` the pod is deleted regardless of
  /healthz, so the "503 → restart" behavior is bounded to the drain
  window.

* ``GET /readyz`` — readiness. Returns 200 only when the
  gateway can actually serve a request:

  - PostgreSQL is reachable (one ``SELECT 1`` via the cached
    session factory).
  - Redis is reachable (``PING``).
  - The credential service responded to a ``/v1/auth/verify``
    with a 401 (any HTTP response is enough — what we care
    about is TCP + handler reachability, not auth).
  - The in-memory routing table is non-empty.
  - ``app.state.draining`` is False (short-circuits before any I/O).

  Used by Kubernetes ``readinessProbe`` — the pod is removed
  from the Service load-balancer pool when ``/readyz`` returns
  non-200, so traffic drains before the pod is restarted. /readyz
  503 during preStop also makes the NGINX L4 LB (task 2.3) drain
  the upstream, providing redundant drain signaling alongside
  /healthz.

The 200/503 split keeps the liveness path tiny (no I/O) and
makes the readiness path the single source of truth for "can
this pod serve a request right now". We deliberately do *not*
treat individual dependency failures as fatal for the
liveness probe — a transient PG hiccup should not cause
pod restarts.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Request, Response
from sqlalchemy import text

from app import redis_client
from app.config import get_settings
from app.database import get_session
from app.routing.table import _inmemory

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/healthz")
async def healthz(request: Request) -> Response:
    """Liveness probe — 200 normally, 503 when draining.

    See module docstring for why /healthz (not just /readyz) returns 503
    during the preStop drain window.
    """
    if getattr(request.app.state, "draining", False):
        return Response(
            content='{"status":"draining"}',
            media_type="application/json",
            status_code=503,
        )
    return Response(
        content='{"status":"ok"}',
        media_type="application/json",
        status_code=200,
    )


@router.get("/readyz")
async def readyz(request: Request) -> Response:
    """Readiness probe — 200 only when every dependency is reachable
    AND the service is not draining.

    Each check is wrapped in its own try/except so a single
    failing dependency produces a useful ``checks`` body
    rather than a 500. The HTTP status is 200 only when *all*
    checks pass AND ``app.state.draining`` is False.
    """
    checks: dict[str, str] = {}

    # preStop drain flag — short-circuit before any I/O. This is the
    # standard K8s readiness semantics ("pod is not ready during drain"),
    # not a deviation. /readyz 503 also makes the NGINX L4 LB (task 2.3)
    # drain the upstream, providing redundant drain signaling alongside
    # /healthz (which is the deviation).
    if getattr(request.app.state, "draining", False):
        return Response(
            content='{"status":"draining"}',
            media_type="application/json",
            status_code=503,
        )

    # PostgreSQL
    try:
        async with get_session() as s:
            await s.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"fail: {e}"

    # Redis
    try:
        r = redis_client.get_redis()
        await r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"fail: {e}"

    # Credential service
    try:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=2.0) as client:
            # 故意发无效 token:401 = 服务可达但鉴权失败(我们要的就是这个)
            await client.post(
                f"{settings.credential_service_url}/v1/auth/verify",
                json={"token": "", "audience": "audit-and-isolation"},
            )
        checks["credential_service"] = "ok"
    except Exception as e:
        checks["credential_service"] = f"fail: {e}"

    # 路由表
    checks["routing_table"] = "ok" if _inmemory else "empty"

    ok = all(v == "ok" for v in checks.values())
    status = 200 if ok else 503
    return Response(
        content=str(checks).replace("'", '"'),
        media_type="application/json",
        status_code=status,
    )


__all__ = ["router"]
