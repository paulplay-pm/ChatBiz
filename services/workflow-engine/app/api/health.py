import httpx
from fastapi import APIRouter
from app.config import get_settings
from app.database import engine
from app.redis_client import get_redis

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz():
    return {"status": "ok"}


@router.get("/readyz")
async def readyz():
    """Check that PostgreSQL + Redis + audit-and-isolation + credential are all reachable."""
    s = get_settings()
    checks = {}

    # Postgres
    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"down: {e}"

    # Redis
    try:
        r = get_redis()
        await r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"down: {e}"

    # Audit isolation
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(f"{s.audit_isolation_url}/healthz")
            checks["audit_isolation"] = "ok" if r.status_code == 200 else f"down: HTTP {r.status_code}"
    except Exception as e:
        checks["audit_isolation"] = f"down: {e}"

    # Credential
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(f"{s.credential_service_url}/healthz")
            checks["credential"] = "ok" if r.status_code == 200 else f"down: HTTP {r.status_code}"
    except Exception as e:
        checks["credential"] = f"down: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    return {"status": "ready" if all_ok else "not_ready", "checks": checks}
