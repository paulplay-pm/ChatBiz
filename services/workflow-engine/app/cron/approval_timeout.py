"""Approval timeout cron: every 5 min, mark pending approvals > 24h as timeout."""
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from app.database import SessionLocal
from app.models.workflow import Approval, WorkflowRun

log = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def check_approval_timeout():
    """Mark approvals older than 24h as timeout. Uses FOR UPDATE SKIP LOCKED for multi-instance safety."""
    async with SessionLocal() as session:
        cutoff = datetime.utcnow() - timedelta(hours=24)
        # SQLite (tests) doesn't support SKIP LOCKED; we use a try/except fallback
        try:
            stmt = (
                select(Approval)
                .where(Approval.status == "pending", Approval.created_at < cutoff)
                .with_for_update(skip_locked=True)
            )
            result = await session.execute(stmt)
        except Exception:  # pragma: no cover (SQLite test path goes straight to fallback)
            # Fallback for SQLite test env
            stmt = select(Approval).where(Approval.status == "pending", Approval.created_at < cutoff)
            result = await session.execute(stmt)
        expired = result.scalars().all()
        count = 0
        for ap in expired:
            ap.status = "timeout"
            ap.responded_at = datetime.utcnow()
            run = await session.get(WorkflowRun, ap.run_id)
            if run and run.status not in ("completed", "failed", "cancelled"):
                run.status = "failed"
                run.error_class = "user"
                run.error_message = "approval timeout: 24h exceeded"
                run.ended_at = datetime.utcnow()
            count += 1
        await session.commit()
        if count:
            log.info(f"approval timeout: marked {count} as timeout")


def start_cron():
    scheduler.add_job(check_approval_timeout, "cron", minute="*/5", id="approval_timeout", replace_existing=True)
    scheduler.start()
    log.info("approval timeout cron started (every 5 min)")


def stop_cron():
    if scheduler.running:
        scheduler.shutdown()
