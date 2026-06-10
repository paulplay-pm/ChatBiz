"""90-day cleanup: delete terminal workflow_run + node_event older than 90 days."""
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import delete
from app.database import SessionLocal
from app.models.workflow import WorkflowRun

log = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def cleanup_old_runs():
    """Delete workflow_run rows + cascade-delete node_event + approval where status is terminal
    AND ended_at < 90 days ago. Keeps workflow_definition + audit_log untouched."""
    async with SessionLocal() as session:
        cutoff = datetime.utcnow() - timedelta(days=90)
        stmt = delete(WorkflowRun).where(
            WorkflowRun.status.in_(("completed", "failed", "cancelled")),
            WorkflowRun.ended_at < cutoff,
        )
        result = await session.execute(stmt)
        await session.commit()
        count = result.rowcount or 0
        if count:
            log.info(f"cleanup: deleted {count} workflow_run rows older than 90 days")


def start_cron():
    scheduler.add_job(cleanup_old_runs, "cron", day_of_week="sun", hour=3, minute=0, id="cleanup_90d", replace_existing=True)
    scheduler.start()
    log.info("cleanup cron started (weekly Sun 3:00 AM)")


def stop_cron():
    if scheduler.running:
        scheduler.shutdown()
