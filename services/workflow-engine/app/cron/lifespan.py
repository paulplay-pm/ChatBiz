"""FastAPI lifespan handler: startup/shutdown for cron jobs."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.cron.approval_timeout import start_cron as start_timeout, stop_cron as stop_timeout
from app.cron.cleanup import start_cron as start_cleanup, stop_cron as stop_cleanup
from app.nodes.registry import bind_execute_fns
import logging
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    bind_execute_fns()
    log.info("Node Contract execute_fns bound")
    start_timeout()
    start_cleanup()
    log.info("workflow-engine started")
    yield
    # Shutdown
    stop_timeout()
    stop_cleanup()
    log.info("workflow-engine stopped")
