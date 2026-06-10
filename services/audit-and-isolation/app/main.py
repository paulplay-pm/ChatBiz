"""FastAPI app + lifespan for the audit-and-isolation service.

Lifespan (locked by the plan in
``openspec-changes-audit-isolation/plan.md`` Task 12.1):

* **Startup** — log the environment, load the routing table into
  Redis + the in-memory fallback, start the audit outbox worker.
  The order matters: the routing table is needed by the chat
  endpoint, so it must be ready before the first request lands;
  the outbox is independent of routing, but starting it before
  yield keeps the early-error path uniform.
* **Shutdown** — stop the outbox (drains the in-memory queue),
  dispose the SQLAlchemy engine. Redis is left to the OS to
  close (the connection pool cleans up on process exit).

The three routers are mounted as:

* ``/v1/chat/completions`` — the proxy endpoint.
* ``/v1/models`` — the OpenAI-shaped model list.
* ``/healthz`` + ``/readyz`` — Kubernetes probes (no prefix).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.api.models import router as models_router
from app.audit.writer import get_outbox
from app.config import get_settings
from app.database import dispose_engine
from app.routing.table import load_routing_into_cache

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(f"audit-and-isolation starting in {settings.environment}")
    # 启动时加载路由表
    try:
        count = await load_routing_into_cache()
        logger.info(f"loaded {count} routing entries")
    except Exception as e:
        # DB 不可达时启动也要继续(空路由表 → 全部 400)
        logger.warning(f"routing table load failed: {e}")
    # 启动 audit outbox
    await get_outbox().start()
    try:
        yield
    finally:
        # 关闭
        await get_outbox().stop()
        await dispose_engine()


app = FastAPI(title="chatbiz-audit-and-isolation", version="0.1.0", lifespan=lifespan)
app.include_router(chat_router, prefix="/v1")
app.include_router(health_router)
app.include_router(models_router, prefix="/v1")


__all__ = ["app", "lifespan"]
