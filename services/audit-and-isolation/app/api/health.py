"""Liveness + readiness probes.

* ``GET /healthz`` — liveness. Always 200 (as long as the process
  is up and the event loop is responsive). Used by Kubernetes
  ``livenessProbe`` — if this stops responding, the pod is
  restarted.
* ``GET /readyz`` — readiness. Returns 200 only when the
  gateway can actually serve a request:

  - PostgreSQL is reachable (one ``SELECT 1`` via the cached
    session factory).
  - Redis is reachable (``PING``).
  - The credential service responded to a ``/v1/auth/verify``
    with a 401 (any HTTP response is enough — what we care
    about is TCP + handler reachability, not auth).
  - The in-memory routing table is non-empty.

  Used by Kubernetes ``readinessProbe`` — the pod is removed
  from the Service load-balancer pool when ``/readyz`` returns
  non-200, so traffic drains before the pod is restarted.

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
from fastapi import APIRouter, Response
from sqlalchemy import text

from app import redis_client
from app.config import get_settings
from app.database import get_session
from app.routing.table import _inmemory

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict:
    """Liveness probe — always 200 if the process is alive.

    The body is a tiny ``{"status": "ok"}`` so a debug client
    can curl the endpoint and see a parseable response.
    """
    return {"status": "ok"}


@router.get("/readyz")
async def readyz() -> Response:
    """Readiness probe — 200 only when every dependency is reachable.

    Each check is wrapped in its own try/except so a single
    failing dependency produces a useful ``checks`` body
    rather than a 500. The HTTP status is 200 only when *all*
    checks pass.
    """
    checks: dict[str, str] = {}

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
