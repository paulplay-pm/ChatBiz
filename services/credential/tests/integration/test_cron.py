"""Integration tests for ``app.cron`` against a real Postgres.

Covers:

* §凭证过期提醒 (`Requirement: 凭证过期提醒`):
  - 7 / 1 / 0 day before expiry each fire exactly one webhook;
  - rows outside the 3 windows (e.g. 30 days away) do NOT fire;
  - re-running the cron within 24h does NOT double-notify
    (idempotency anchored on the audit log).

* §凭证轮换双值窗口期 (`Requirement: 凭证轮换双值窗口期` →
  `Scenario: cron job 清理过期旧值`):
  - rows with ``previous_expires_at <= now`` have their previous_*
    columns cleared and one ``cleanup_previous`` audit row written;
  - re-run is a no-op;
  - boundary ``previous_expires_at == now`` IS cleaned (not future-only).

The fixture spins up a Postgres testcontainer and builds the schema via
``Base.metadata.create_all`` — mirroring the pattern used in
``tests/integration/test_services.py``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app import crypto
from app.audit import hash_credential_id
from app.cron import (
    ACTION_CLEANUP_PREVIOUS,
    NOTIFY_THRESHOLDS_DAYS,
    check_expiring_credentials,
    cleanup_expired_previous,
)
from app.models import Base, Credential, CredentialAudit, CredentialType

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pg_url() -> Iterator[str]:
    """Spin up a Postgres testcontainer and yield the asyncpg DSN."""
    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url()
        if url.startswith("postgresql+psycopg2://"):
            url = "postgresql+asyncpg://" + url[len("postgresql+psycopg2://") :]
        elif url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://") :]
        yield url


@pytest_asyncio.fixture(scope="function")
async def session(pg_url: str) -> AsyncIterator[AsyncSession]:
    """Fresh schema per test — drop + create."""
    engine = create_async_engine(pg_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.fixture(scope="session")
def master_key() -> bytes:
    return crypto.generate_master_key()


@pytest.fixture
def mock_webhook(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Replace ``app.notifications.send_wechat_webhook`` and record every call.

    Note: ``app.cron`` imports ``send_wechat_webhook`` by name at module
    load time, so we patch the symbol on ``app.cron``, not on
    ``app.notifications``.
    """
    calls: list[dict[str, Any]] = []

    async def fake_send(url: str | None, message: dict[str, Any], **_: Any) -> None:
        calls.append({"url": url, "message": message})

    monkeypatch.setattr("app.cron.send_wechat_webhook", fake_send)
    return calls


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_credential(
    *,
    suffix: str,
    expires_at: datetime | None,
    previous_expires_at: datetime | None = None,
    previous_value: bytes | None = None,
    previous_encrypted_dek: bytes | None = None,
) -> Credential:
    """Build a minimal ``Credential`` row for cron tests.

    The encrypted columns hold opaque bytes — the cron does NOT decrypt,
    so we skip the full envelope-encryption dance the service layer
    performs (covered in ``test_services.py``).
    """
    return Credential(
        id=f"cred_test_{suffix}",
        name=f"key-{suffix}",
        type=CredentialType.API_KEY,
        encrypted_value=b"\x00" * 32,
        encrypted_dek=b"\x00" * 32,
        previous_value=previous_value,
        previous_encrypted_dek=previous_encrypted_dek,
        previous_expires_at=previous_expires_at,
        workspace_id="finance",
        expires_at=expires_at,
    )


async def _audit_rows(
    session: AsyncSession, action: str
) -> list[CredentialAudit]:
    """All audit rows with the given ``action``."""
    stmt = select(CredentialAudit).where(CredentialAudit.action == action)
    return list((await session.execute(stmt)).scalars().all())


# ---------------------------------------------------------------------------
# Expiry-notification tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestCheckExpiringCredentials:
    async def test_notifies_7_1_0_day_credentials(
        self,
        session: AsyncSession,
        mock_webhook: list[dict[str, Any]],
    ) -> None:
        """3 candidates (7d / 1d / 0d) → 3 webhook calls + 3 audit rows.

        The 30-day-away credential must NOT trigger a notification.
        """
        # Fix ``now`` so the date-window arithmetic is deterministic.
        # Use the noon mark to avoid any near-midnight edge interaction.
        now = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
        session.add_all(
            [
                _make_credential(suffix="7d", expires_at=now + timedelta(days=7)),
                _make_credential(suffix="1d", expires_at=now + timedelta(days=1)),
                _make_credential(suffix="0d", expires_at=now + timedelta(hours=3)),
                _make_credential(suffix="30d", expires_at=now + timedelta(days=30)),
            ]
        )
        await session.commit()

        result = await check_expiring_credentials(
            session,
            webhook_url="https://example.invalid/webhook",
            now=now,
        )
        await session.commit()

        assert result.candidates == 3
        assert result.notifications_sent == 3
        assert result.skipped_idempotent == 0
        assert len(mock_webhook) == 3

        # Each call carries a 企微-shaped payload with a content body.
        for call in mock_webhook:
            assert call["url"] == "https://example.invalid/webhook"
            assert call["message"]["msgtype"] == "text"
            assert "content" in call["message"]["text"]

        # One audit row per threshold; action strings match the spec.
        sent_actions: list[str] = []
        for days in NOTIFY_THRESHOLDS_DAYS:
            for row in await _audit_rows(session, f"notify_expiry_{days}day"):
                sent_actions.append(row.action)
        assert sorted(sent_actions) == [
            "notify_expiry_0day",
            "notify_expiry_1day",
            "notify_expiry_7day",
        ]

    async def test_idempotent_within_24h(
        self,
        session: AsyncSession,
        mock_webhook: list[dict[str, Any]],
    ) -> None:
        """Re-running the cron within 24h sends 0 new webhooks."""
        now = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
        session.add(_make_credential(suffix="1d", expires_at=now + timedelta(days=1)))
        await session.commit()

        # First run: 1 webhook.
        first = await check_expiring_credentials(
            session, webhook_url="https://example.invalid/webhook", now=now,
        )
        await session.commit()
        assert first.notifications_sent == 1
        assert len(mock_webhook) == 1

        # Second run, same ``now`` (within idempotency window): 0 new webhooks.
        second = await check_expiring_credentials(
            session, webhook_url="https://example.invalid/webhook", now=now,
        )
        await session.commit()
        assert second.notifications_sent == 0
        assert second.skipped_idempotent == 1
        assert len(mock_webhook) == 1  # unchanged

    async def test_notifies_again_after_24h(
        self,
        session: AsyncSession,
        mock_webhook: list[dict[str, Any]],
    ) -> None:
        """After the 24h idempotency window passes, the next run fires again.

        We construct a 1-day-out credential, run the cron at T, then run
        it again at T + 25h with the credential's ``expires_at`` shifted
        forward 25h so it lands on the 0-day window — exercising both
        the window-shift AND the idempotency expiry. (We can't keep the
        same credential at "1 day away" 25h later, because by then the
        real-time distance would be < 1 day.)
        """
        now = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
        cred = _make_credential(suffix="rolling", expires_at=now + timedelta(days=1))
        session.add(cred)
        await session.commit()

        await check_expiring_credentials(
            session, webhook_url="https://example.invalid/webhook", now=now,
        )
        await session.commit()
        assert len(mock_webhook) == 1

        # 25h later: idempotency for 1-day audit has aged out.
        # Shift expires_at so the credential lands on the 0-day window
        # for the new ``now``.
        later = now + timedelta(hours=25)
        cred.expires_at = later + timedelta(hours=2)
        await session.commit()
        await check_expiring_credentials(
            session, webhook_url="https://example.invalid/webhook", now=later,
        )
        await session.commit()

        assert len(mock_webhook) == 2

    async def test_no_webhook_url_still_writes_audit(
        self,
        session: AsyncSession,
        mock_webhook: list[dict[str, Any]],
    ) -> None:
        """When webhook URL is empty, audit rows are still written.

        The transport is a no-op for empty URLs (see notifications.py);
        the cron still records the attempt so the idempotency anchor
        is laid down and the alert isn't endlessly retried.
        """
        now = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
        session.add(_make_credential(suffix="1d", expires_at=now + timedelta(days=1)))
        await session.commit()

        await check_expiring_credentials(session, webhook_url=None, now=now)
        await session.commit()

        # Webhook recorder saw a call (with url=None) — the transport
        # itself is the gate, not the cron.
        assert len(mock_webhook) == 1
        assert mock_webhook[0]["url"] is None
        assert len(await _audit_rows(session, "notify_expiry_1day")) == 1


# ---------------------------------------------------------------------------
# Cleanup tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestCleanupExpiredPrevious:
    async def test_cleans_expired_previous(
        self, session: AsyncSession
    ) -> None:
        """A row with previous_expires_at < now has all previous_* columns nulled."""
        now = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
        cred = _make_credential(
            suffix="rotated",
            expires_at=None,
            previous_value=b"OLD_CIPHERTEXT_PLACEHOLDER",
            previous_encrypted_dek=b"OLD_DEK_PLACEHOLDER",
            previous_expires_at=now - timedelta(days=1),
        )
        session.add(cred)
        await session.commit()
        cred_id = cred.id  # capture before expire_all()

        cleaned = await cleanup_expired_previous(session, now=now)
        await session.commit()
        assert cleaned == 1

        session.expire_all()
        row = await session.get(Credential, cred_id)
        assert row is not None
        assert row.previous_value is None
        assert row.previous_encrypted_dek is None
        assert row.previous_expires_at is None

        # Audit row written with action / cap / purpose per spec.
        rows = await _audit_rows(session, ACTION_CLEANUP_PREVIOUS)
        assert len(rows) == 1
        audit = rows[0]
        assert audit.cap == "cron"
        assert audit.purpose == "30-day window expired"
        assert audit.user_id == "cron"
        assert audit.success is True
        assert audit.credential_id_hash == hash_credential_id(cred_id)

    async def test_rerun_is_noop(
        self, session: AsyncSession
    ) -> None:
        """After the row is cleaned, a second run cleans 0 more rows."""
        now = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
        cred = _make_credential(
            suffix="rotated",
            expires_at=None,
            previous_value=b"OLD",
            previous_encrypted_dek=b"OLD",
            previous_expires_at=now - timedelta(days=1),
        )
        session.add(cred)
        await session.commit()

        assert await cleanup_expired_previous(session, now=now) == 1
        await session.commit()

        assert await cleanup_expired_previous(session, now=now) == 0
        await session.commit()
        # Exactly one cleanup audit row total — the second run produced none.
        assert len(await _audit_rows(session, ACTION_CLEANUP_PREVIOUS)) == 1

    async def test_boundary_now_exact_is_cleaned(
        self, session: AsyncSession
    ) -> None:
        """``previous_expires_at == now`` is cleaned (NOT treated as future)."""
        now = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
        cred = _make_credential(
            suffix="boundary",
            expires_at=None,
            previous_value=b"OLD",
            previous_encrypted_dek=b"OLD",
            previous_expires_at=now,  # exactly now
        )
        session.add(cred)
        await session.commit()

        cleaned = await cleanup_expired_previous(session, now=now)
        await session.commit()
        assert cleaned == 1

    async def test_future_previous_not_cleaned(
        self, session: AsyncSession
    ) -> None:
        """``previous_expires_at > now`` is left alone (within the 30-day window)."""
        now = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
        cred = _make_credential(
            suffix="fresh",
            expires_at=None,
            previous_value=b"OLD",
            previous_encrypted_dek=b"OLD",
            previous_expires_at=now + timedelta(days=10),
        )
        session.add(cred)
        await session.commit()
        cred_id = cred.id

        cleaned = await cleanup_expired_previous(session, now=now)
        await session.commit()
        assert cleaned == 0

        session.expire_all()
        row = await session.get(Credential, cred_id)
        assert row is not None
        assert row.previous_value == b"OLD"
        assert row.previous_encrypted_dek == b"OLD"
        assert row.previous_expires_at == now + timedelta(days=10)

    async def test_ignores_rows_with_null_previous(
        self, session: AsyncSession
    ) -> None:
        """Never-rotated rows (no previous_*) are NOT touched."""
        now = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
        cred = _make_credential(suffix="never-rotated", expires_at=None)
        session.add(cred)
        await session.commit()

        cleaned = await cleanup_expired_previous(session, now=now)
        await session.commit()
        assert cleaned == 0
        assert len(await _audit_rows(session, ACTION_CLEANUP_PREVIOUS)) == 0
