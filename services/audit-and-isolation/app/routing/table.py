"""In-memory + Redis routing table cache.

The routing table maps ``model_name`` to an upstream provider
(``qwen-max`` -> ``https://dashscope.aliyuncs.com``, etc.). It is
loaded from PostgreSQL at startup and cached both:

* In Redis (``routing:model:<model_name>``, TTL
  ``routing_table_ttl_seconds``) so any pod can serve a hot
  request without a DB round-trip.
* In this process's ``_inmemory`` dict, as the Redis-down fallback
  (the gateway must continue serving if Redis is briefly
  unavailable — failing the request would propagate the cache
  outage into the LLM call path).

The startup load reads ``ModelRouting`` rows where
``enabled == true`` and filters at the SQL level (not the Python
level) so a routing table of 10 000 rows with 1 % enabled doesn't
load 9 900 disabled rows into Python.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import select

from app import redis_client
from app.config import get_settings
from app.database import get_session
from app.models.audit import ModelRouting

logger = logging.getLogger(__name__)

# 内存 fallback(启动时载入,Redis 挂时用)
_inmemory: dict[str, dict] = {}


async def load_routing_into_cache() -> int:
    """Read enabled routing rows from PG, populate Redis + in-memory cache.

    Returns the count of rows loaded (used for the startup log
    line and the ``routing_table_loaded_total`` metric). On a Redis
    failure the function still completes (with a warning) so the
    in-memory cache is always available, even if Redis is down.
    """
    global _inmemory
    async with get_session() as s:
        result = await s.execute(
            select(ModelRouting).where(ModelRouting.enabled == True)
        )
        rows = result.scalars().all()
    settings = get_settings()
    r = redis_client.get_redis()
    _inmemory = {}
    try:
        pipe = r.pipeline()
        for row in rows:
            entry = {
                "model_kind": row.model_kind,
                "upstream_base_url": row.upstream_base_url,
                "upstream_path": row.upstream_path,
                "timeout_ms": row.timeout_ms,
            }
            _inmemory[row.model_name] = entry
            pipe.set(
                f"routing:model:{row.model_name}",
                json.dumps(entry),
                ex=settings.routing_table_ttl_seconds,
            )
        await pipe.execute()
    except Exception as e:
        logger.warning(f"Redis routing cache write failed (will use in-memory only): {e}")
    return len(_inmemory)


async def get_routing(model_name: str) -> dict | None:
    """Resolve a model name to its routing entry, or ``None`` if unknown.

    Resolution order:

    1. Redis (``routing:model:<name>``). The hot path — avoids any
       DB or in-process dict access. If the key is missing or the
       Redis call fails, fall through to step 2.
    2. The in-process ``_inmemory`` dict (populated at startup).
       Used when Redis is down OR when the model isn't in the
       Redis cache (e.g. a hot-loaded model between cache writes).
    3. Return ``None`` — the dispatcher raises ``RoutingError`` and
       the gateway returns 400 to the caller.
    """
    try:
        r = redis_client.get_redis()
        raw = await r.get(f"routing:model:{model_name}")
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.warning(f"Redis routing read failed, using in-memory: {e}")
    return _inmemory.get(model_name)


def reset_inmemory_for_tests() -> None:
    """Drop the in-memory routing cache. Test-only helper."""
    global _inmemory
    _inmemory = {}


__all__ = ["get_routing", "load_routing_into_cache", "reset_inmemory_for_tests"]
