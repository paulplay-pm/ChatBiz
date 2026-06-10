"""Cron jobs for the credential-management service.

Two jobs run on a daily cadence (host cron / Kubernetes CronJob):

* :func:`check_expiring_credentials` — scan ``credentials`` for rows
  whose ``expires_at`` is 7 / 1 / 0 days away and POST a 企微 webhook
  for each. Per spec §凭证过期提醒 (`Requirement: 凭证过期提醒`):
  "系统 MUST 在凭证过期前 7 天 / 1 天 / 当天 各触发 1 次企微 webhook
  通知管理员".

* :func:`cleanup_expired_previous` — scan ``credentials`` for rows
  whose ``previous_expires_at < now()`` and physically clear the
  ``previous_value`` / ``previous_encrypted_dek`` / ``previous_expires_at``
  columns. Per spec §凭证轮换双值窗口期 (`Requirement: 凭证轮换双值窗口期`):
  "旧值 ``previous_expires_at`` < 当前时间的行由 cron job 物理清空".

Idempotency
-----------
``check_expiring_credentials`` MUST NOT double-notify within a 24h window.
The check is performed against the ``credential_audit`` table: if a row
with ``action = 'notify_expiry_Nday'`` exists for the same credential
within the last 24h, the notification is skipped. This lets the cron
re-run safely (e.g. host cron fires twice or a CronJob retries) without
spamming the on-call channel.

Entry point
-----------
``python -m app.cron`` runs both jobs once and exits. There is no daemon
loop — the cadence is owned by the scheduler (host cron, k8s CronJob,
docker-compose ``credential-cron`` service). The ``--once`` flag is
accepted for clarity but is the default behaviour anyway.

Configuration
-------------
* ``CREDENTIAL_DB_URL``       — asyncpg DSN (required).
* ``CREDENTIAL_WECHAT_WEBHOOK`` — webhook URL (optional; absent → log only).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.audit import hash_credential_id, write_audit
from app.models import Credential, CredentialAudit
from app.notifications import send_wechat_webhook

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Days-before-expiry thresholds that trigger a notification. The tuple
#: is iterated in this order; each entry yields an ``action`` string
#: ``notify_expiry_<N>day`` that is both audited and used as the
#: idempotency key. Order does not affect behaviour — kept descending
#: only for log readability.
NOTIFY_THRESHOLDS_DAYS: Final[tuple[int, ...]] = (7, 1, 0)

#: Idempotency window. If a ``notify_expiry_<N>day`` audit row exists
#: within this window for a given credential, the notification is
#: skipped on the current run. 24h matches the cron cadence: at most
#: one notification per threshold per day per credential.
IDEMPOTENCY_WINDOW: Final[timedelta] = timedelta(hours=24)

#: Audit action prefix used for expiry notifications. The full action
#: string is ``notify_expiry_7day`` / ``notify_expiry_1day`` / ``notify_expiry_0day``.
_NOTIFY_ACTION_PREFIX: Final[str] = "notify_expiry_"

#: Audit action for the cleanup job. One row per cleaned credential.
ACTION_CLEANUP_PREVIOUS: Final[str] = "cleanup_previous"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ExpiryRunResult:
    """Counts returned by :func:`check_expiring_credentials`."""

    candidates: int
    notifications_sent: int
    skipped_idempotent: int


def _action_for(days: int) -> str:
    """Return the audit ``action`` string for a given threshold (e.g. ``notify_expiry_7day``)."""
    return f"{_NOTIFY_ACTION_PREFIX}{days}day"


def _utcnow() -> datetime:
    """Timezone-aware UTC ``datetime.now`` — kept explicit for testability."""
    return datetime.now(UTC)


def _date_window(now: datetime, days_ahead: int) -> tuple[datetime, datetime]:
    """Return [start, end) covering the UTC calendar day ``days_ahead`` from ``now``.

    Spec uses 24h tolerance ("within 24h tolerance window"); we
    implement that as "expires on the same calendar UTC day as
    ``now + days_ahead``" because date equality is robust to small
    clock drift and reads cleanly in the SQL.
    """
    target_day = (now + timedelta(days=days_ahead)).date()
    start = datetime(target_day.year, target_day.month, target_day.day, tzinfo=UTC)
    end = start + timedelta(days=1)
    return start, end


async def check_expiring_credentials(
    session: AsyncSession,
    webhook_url: str | None,
    now: datetime | None = None,
) -> ExpiryRunResult:
    """Send expiry notifications for credentials hitting 7 / 1 / 0 day marks.

    For each threshold (in ``NOTIFY_THRESHOLDS_DAYS``):

    1. Find ``Credential`` rows with ``expires_at`` falling on the UTC
       calendar day ``now + N days``.
    2. For each row, check ``credential_audit`` for an existing
       ``notify_expiry_<N>day`` row within the last 24h; skip if present.
    3. Otherwise POST the 企微 webhook and write a
       ``notify_expiry_<N>day`` audit row (success=True regardless of
       webhook outcome — the audit captures *the attempt*, not the
       delivery; webhook failures are logged by
       :func:`app.notifications.send_wechat_webhook`).

    The audit row is the idempotency anchor — writing it under any
    branch (sent or skipped) would break re-tries; we write only when
    a notification is actually attempted in this run.

    Returns an :class:`ExpiryRunResult` with counts for the run log.
    """
    current = now if now is not None else _utcnow()
    total_candidates = 0
    total_sent = 0
    total_skipped = 0

    for days in NOTIFY_THRESHOLDS_DAYS:
        start, end = _date_window(current, days)
        stmt = select(Credential).where(
            and_(
                Credential.expires_at.is_not(None),
                Credential.expires_at >= start,
                Credential.expires_at < end,
            )
        )
        rows = (await session.execute(stmt)).scalars().all()
        total_candidates += len(rows)

        action = _action_for(days)
        for row in rows:
            if await _has_recent_notify(session, row.id, action, current):
                total_skipped += 1
                continue
            await _send_and_audit(session, row, days, action, webhook_url)
            total_sent += 1

    await session.flush()
    logger.info(
        "[cron] expiry-check: %d candidates, %d notifications sent, %d skipped (idempotent)",
        total_candidates,
        total_sent,
        total_skipped,
    )
    return ExpiryRunResult(
        candidates=total_candidates,
        notifications_sent=total_sent,
        skipped_idempotent=total_skipped,
    )


async def cleanup_expired_previous(
    session: AsyncSession,
    now: datetime | None = None,
) -> int:
    """Physically clear ``previous_*`` columns past the 30-day window.

    Selects rows where ``previous_expires_at <= now`` (the boundary is
    inclusive: a credential whose previous-value expires *exactly now*
    is cleaned, per the Task 6 edge-case requirement: "previous_expires_at
    = now exactly → cleaned (NOT future-only)") and:

    * sets ``previous_value`` / ``previous_encrypted_dek`` /
      ``previous_expires_at`` to NULL;
    * writes one ``cleanup_previous`` audit row per cleaned credential.

    Returns the number of rows cleaned (= the number of audit rows
    written).
    """
    current = now if now is not None else _utcnow()
    stmt = select(Credential.id).where(
        and_(
            Credential.previous_expires_at.is_not(None),
            Credential.previous_expires_at <= current,
            # ``previous_value IS NOT NULL`` — sanity guard: in normal
            # operation the three columns are populated together, but
            # we keep the guard so a half-populated row never trips a
            # spurious cleanup (the UPDATE would be a no-op but the
            # audit row would still fire).
            Credential.previous_value.is_not(None),
        )
    )
    # Materialise the ids up front. We then issue per-credential UPDATE
    # + audit-insert pairs. The two-step pattern avoids interleaving an
    # active SELECT cursor with the per-row writes (which on asyncpg
    # tripped a ``MissingGreenlet`` when we iterated the SELECT result
    # lazily while issuing writes inside the loop body).
    ids: list[str] = list((await session.execute(stmt)).scalars().all())
    cleaned = 0
    for cred_id in ids:
        # Bulk UPDATE keyed by id; using session.execute(update(...))
        # avoids the per-row attribute mutation + flush ping-pong and
        # keeps the SQL trivial to read in pg logs.
        await session.execute(
            update(Credential)
            .where(Credential.id == cred_id)
            .values(
                previous_value=None,
                previous_encrypted_dek=None,
                previous_expires_at=None,
            )
        )
        await write_audit(
            session,
            user_id="cron",
            credential_id=cred_id,
            action=ACTION_CLEANUP_PREVIOUS,
            success=True,
            cap="cron",
            purpose="30-day window expired",
        )
        cleaned += 1

    await session.flush()
    logger.info("[cron] cleanup: %d previous-value rows cleared", cleaned)
    return cleaned


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _has_recent_notify(
    session: AsyncSession,
    credential_id: str,
    action: str,
    now: datetime,
) -> bool:
    """True if a ``CredentialAudit`` row exists for (cred, action) within 24h.

    Idempotency anchor for :func:`check_expiring_credentials`.
    """
    cutoff = now - IDEMPOTENCY_WINDOW
    cred_hash = hash_credential_id(credential_id)
    stmt = (
        select(CredentialAudit.id)
        .where(
            and_(
                CredentialAudit.credential_id_hash == cred_hash,
                CredentialAudit.action == action,
                CredentialAudit.timestamp >= cutoff,
            )
        )
        .limit(1)
    )
    return (await session.execute(stmt)).first() is not None


async def _send_and_audit(
    session: AsyncSession,
    row: Credential,
    days: int,
    action: str,
    webhook_url: str | None,
) -> None:
    """POST the 企微 webhook + write the audit row.

    Webhook failures are swallowed by ``send_wechat_webhook`` itself
    (best-effort transport, logs a warning); the audit row is written
    regardless so the next run's idempotency check sees the attempt.
    """
    message = _build_notification_payload(row, days)
    await send_wechat_webhook(webhook_url, message)
    await write_audit(
        session,
        user_id="cron",
        credential_id=row.id,
        action=action,
        success=True,
        cap="cron",
        purpose=f"expiry-reminder-{days}day",
    )


def _build_notification_payload(row: Credential, days: int) -> dict[str, object]:
    """Build the 企微 webhook payload for an expiring credential.

    Spec §凭证过期前 7 天提醒 requires: "推送提醒消息(含凭证名称、ID
    hash、过期时间、续期操作指引)". We do NOT include the plaintext
    credential id — only its 8-byte hash, matching the audit log.
    """
    if days == 0:
        headline = "凭证已过期"
    elif days == 1:
        headline = "凭证即将过期 (1 day)"
    else:
        headline = f"凭证即将过期 ({days} days)"

    id_hash_hex = hash_credential_id(row.id).hex()
    expires_at_display = row.expires_at.isoformat() if row.expires_at is not None else "unknown"
    content = (
        f"{headline}\n"
        f"名称: {row.name}\n"
        f"ID hash: {id_hash_hex}\n"
        f"过期时间: {expires_at_display}\n"
        f"操作: 请通过管理后台 /credentials 页面执行轮换。"
    )
    return {
        "msgtype": "text",
        "text": {"content": content},
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """CLI arg parser. ``--once`` is accepted for clarity and is the default."""
    parser = argparse.ArgumentParser(
        prog="app.cron",
        description="ChatBiz credential-management cron jobs (expiry + cleanup).",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run both jobs once and exit (this is the default behaviour).",
    )
    return parser.parse_args(argv)


async def main(argv: list[str] | None = None) -> int:
    """Open DB session, run both jobs sequentially, log results, exit.

    Returns the suggested process exit code (0 on success). Webhook
    transport failures do NOT cause a non-zero exit — they are logged
    and the cron will re-try on the next tick.
    """
    _parse_args(argv if argv is not None else sys.argv[1:])

    db_url = os.environ.get("CREDENTIAL_DB_URL")
    if not db_url:
        logger.critical("CREDENTIAL_DB_URL is not set; cannot run cron")
        return 1
    webhook_url = os.environ.get("CREDENTIAL_WECHAT_WEBHOOK") or None

    engine = create_async_engine(db_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session, session.begin():
            expiry_result = await check_expiring_credentials(session, webhook_url)
            cleanup_count = await cleanup_expired_previous(session)
    finally:
        await engine.dispose()

    logger.info(
        "[cron] %d credentials expiring soon, %d notifications sent, %d cleanup rows",
        expiry_result.candidates,
        expiry_result.notifications_sent,
        cleanup_count,
    )
    return 0


def _entry() -> None:
    """Synchronous shim used by ``python -m app.cron``."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    sys.exit(asyncio.run(main()))


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in real ops
    _entry()


__all__ = [
    "ACTION_CLEANUP_PREVIOUS",
    "ExpiryRunResult",
    "IDEMPOTENCY_WINDOW",
    "NOTIFY_THRESHOLDS_DAYS",
    "check_expiring_credentials",
    "cleanup_expired_previous",
    "main",
]
