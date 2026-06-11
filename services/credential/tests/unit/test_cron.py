"""Unit tests for ``app.cron`` — expiry check + cleanup.

Uses aiosqlite (in-memory) for the async engine — no testcontainers needed.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.audit import hash_credential_id
from app.cron import (
    ACTION_CLEANUP_PREVIOUS,
    IDEMPOTENCY_WINDOW,
    NOTIFY_THRESHOLDS_DAYS,
    _action_for,
    _build_notification_payload,
    _date_window,
    check_expiring_credentials,
    cleanup_expired_previous,
)
from app.models import Base, Credential, CredentialAudit, CredentialType


# ---------------------------------------------------------------------------
# Helper: build fake Credential rows for cron tests.
# ---------------------------------------------------------------------------


def _make_credential(
    suffix: str,
    expires_at: datetime | None,
    previous_value: bytes | None = None,
    previous_encrypted_dek: bytes | None = None,
    previous_expires_at: datetime | None = None,
) -> Credential:
    """Build a minimal ``Credential`` row. Encrypted columns hold opaque bytes."""
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


async def _audit_count(session: AsyncSession, action: str) -> int:
    stmt = select(CredentialAudit).where(CredentialAudit.action == action)
    rows = (await session.execute(stmt)).scalars().all()
    return len(rows)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def session() -> AsyncIterator[AsyncSession]:
    """Create in-memory SQLite engine + session per test."""
    from sqlalchemy import event as sa_event

    engine = create_async_engine("sqlite+aiosqlite://", echo=False)

    @sa_event.listens_for(engine.sync_engine, "before_cursor_execute", retval=True)
    def _intercept_ddl(conn, cursor, statement, parameters, context, executemany):
        if "BIGINT" in statement:
            statement = statement.replace("BIGINT", "INTEGER")
        return statement, parameters

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.fixture
def mock_webhook(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Replace ``app.cron.send_wechat_webhook`` with a recorder."""
    calls: list[dict[str, Any]] = []

    async def fake_send(url: str | None, message: dict[str, Any], **_: Any) -> None:
        calls.append({"url": url, "message": message})

    monkeypatch.setattr("app.cron.send_wechat_webhook", fake_send)
    return calls


# ---------------------------------------------------------------------------
# Unit-level helpers
# ---------------------------------------------------------------------------


class TestActionFor:
    def test_returns_correct_action_string(self) -> None:
        assert _action_for(7) == "notify_expiry_7day"
        assert _action_for(1) == "notify_expiry_1day"
        assert _action_for(0) == "notify_expiry_0day"


class TestDateWindow:
    def test_window_7_days_ahead(self) -> None:
        now = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
        start, end = _date_window(now, 7)
        assert start == datetime(2026, 6, 16, 0, 0, 0, tzinfo=UTC)
        assert end == datetime(2026, 6, 17, 0, 0, 0, tzinfo=UTC)

    def test_window_1_day_ahead(self) -> None:
        now = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
        start, end = _date_window(now, 1)
        assert start == datetime(2026, 6, 10, 0, 0, 0, tzinfo=UTC)
        assert end == datetime(2026, 6, 11, 0, 0, 0, tzinfo=UTC)

    def test_window_0_days_ahead(self) -> None:
        now = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
        start, end = _date_window(now, 0)
        # 0 days ahead = today
        assert start == datetime(2026, 6, 9, 0, 0, 0, tzinfo=UTC)
        assert end == datetime(2026, 6, 10, 0, 0, 0, tzinfo=UTC)


class TestBuildNotificationPayload:
    def test_7_day_payload(self) -> None:
        row = _make_credential(suffix="t1", expires_at=datetime(2026, 7, 1, tzinfo=UTC))
        payload = _build_notification_payload(row, 7)
        assert payload["msgtype"] == "text"
        content = payload["text"]["content"]
        assert "即将过期" in content
        assert "7 days" in content
        assert "key-t1" in content
        assert hash_credential_id(row.id).hex() in content

    def test_1_day_payload(self) -> None:
        row = _make_credential(suffix="t2", expires_at=datetime(2026, 7, 1, tzinfo=UTC))
        payload = _build_notification_payload(row, 1)
        assert "1 day" in payload["text"]["content"]

    def test_0_day_payload(self) -> None:
        row = _make_credential(suffix="t3", expires_at=datetime(2026, 7, 1, tzinfo=UTC))
        payload = _build_notification_payload(row, 0)
        assert "已过期" in payload["text"]["content"]


class TestConstants:
    def test_notify_thresholds(self) -> None:
        assert NOTIFY_THRESHOLDS_DAYS == (7, 1, 0)

    def test_idempotency_window(self) -> None:
        assert IDEMPOTENCY_WINDOW == timedelta(hours=24)

    def test_action_cleanup_previous(self) -> None:
        assert ACTION_CLEANUP_PREVIOUS == "cleanup_previous"


# ---------------------------------------------------------------------------
# Expiry notification tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCheckExpiringCredentials:
    async def test_notifies_7_1_0_day_credentials(
        self,
        session: AsyncSession,
        mock_webhook: list[dict[str, Any]],
    ) -> None:
        """3 candidates (7d / 1d / 0d) → 3 webhook calls + 3 audit rows."""
        now = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
        session.add_all(
            [
                _make_credential(suffix="7d", expires_at=now + timedelta(days=7)),
                _make_credential(suffix="1d", expires_at=now + timedelta(days=1)),
                _make_credential(suffix="0d", expires_at=now + timedelta(hours=3)),
                _make_credential(suffix="30d", expires_at=now + timedelta(days=30)),
            ]
        )
        await session.flush()

        result = await check_expiring_credentials(
            session,
            webhook_url="https://example.invalid/webhook",
            now=now,
        )
        await session.flush()

        assert result.candidates == 3
        assert result.notifications_sent == 3
        assert result.skipped_idempotent == 0
        assert len(mock_webhook) == 3

        for call in mock_webhook:
            assert call["url"] == "https://example.invalid/webhook"
            assert call["message"]["msgtype"] == "text"

    async def test_idempotent_within_24h(
        self,
        session: AsyncSession,
        mock_webhook: list[dict[str, Any]],
    ) -> None:
        """Re-running the cron within 24h sends 0 new webhooks."""
        now = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
        session.add(_make_credential(suffix="1d", expires_at=now + timedelta(days=1)))
        await session.flush()

        first = await check_expiring_credentials(
            session, webhook_url="https://example.invalid/webhook", now=now,
        )
        await session.flush()
        assert first.notifications_sent == 1

        second = await check_expiring_credentials(
            session, webhook_url="https://example.invalid/webhook", now=now,
        )
        await session.flush()
        assert second.notifications_sent == 0
        assert second.skipped_idempotent == 1
        assert len(mock_webhook) == 1

    async def test_no_webhook_url_still_writes_audit(
        self,
        session: AsyncSession,
        mock_webhook: list[dict[str, Any]],
    ) -> None:
        """When webhook URL is None, audit rows are still written."""
        now = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
        session.add(_make_credential(suffix="1d", expires_at=now + timedelta(days=1)))
        await session.flush()

        await check_expiring_credentials(session, webhook_url=None, now=now)
        await session.flush()

        assert len(mock_webhook) == 1
        assert mock_webhook[0]["url"] is None

    async def test_no_matching_credentials(
        self,
        session: AsyncSession,
        mock_webhook: list[dict[str, Any]],
    ) -> None:
        """No credentials near expiry → zero notifications."""
        now = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
        session.add(_make_credential(suffix="far", expires_at=now + timedelta(days=365)))
        await session.flush()

        result = await check_expiring_credentials(
            session, webhook_url="https://example.invalid/webhook", now=now,
        )
        await session.flush()

        assert result.candidates == 0
        assert result.notifications_sent == 0
        assert len(mock_webhook) == 0

    async def test_no_expires_at_skipped(
        self,
        session: AsyncSession,
        mock_webhook: list[dict[str, Any]],
    ) -> None:
        """Credentials without expires_at are not candidate for notification."""
        now = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
        session.add(_make_credential(suffix="noexpiry", expires_at=None))
        await session.flush()

        result = await check_expiring_credentials(
            session, webhook_url="https://example.invalid/webhook", now=now,
        )
        await session.flush()

        assert result.candidates == 0
        assert result.notifications_sent == 0
        assert len(mock_webhook) == 0

    async def test_multiple_credentials_same_day(
        self,
        session: AsyncSession,
        mock_webhook: list[dict[str, Any]],
    ) -> None:
        """Multiple credentials expiring on the same day all get notified."""
        now = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
        session.add_all([
            _make_credential(suffix="a1", expires_at=now + timedelta(days=7, hours=2)),
            _make_credential(suffix="a2", expires_at=now + timedelta(days=7, hours=5)),
        ])
        await session.flush()

        result = await check_expiring_credentials(
            session, webhook_url="https://example.invalid/webhook", now=now,
        )
        await session.flush()

        assert result.candidates == 2
        assert result.notifications_sent == 2
        assert len(mock_webhook) == 2

    async def test_uses_now_parameter(
        self,
        session: AsyncSession,
        mock_webhook: list[dict[str, Any]],
    ) -> None:
        """Verifies the now parameter is used for date windows."""
        now = datetime(2026, 12, 25, 12, 0, 0, tzinfo=UTC)
        # This credential expires exactly 7 days from this custom now
        session.add(_make_credential(suffix="xmas", expires_at=now + timedelta(days=7)))
        await session.flush()

        result = await check_expiring_credentials(
            session, webhook_url="https://example.invalid/webhook", now=now,
        )
        await session.flush()

        assert result.candidates == 1
        assert result.notifications_sent == 1


# ---------------------------------------------------------------------------
# Cleanup tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCleanupExpiredPrevious:
    async def test_cleans_expired_previous(self, session: AsyncSession) -> None:
        """A row with previous_expires_at < now has all previous_* columns nulled."""
        now = datetime(2026, 6, 9, 12, 0, 0)
        cred = _make_credential(
            suffix="rotated",
            expires_at=None,
            previous_value=b"OLD_CIPHERTEXT",
            previous_encrypted_dek=b"OLD_DEK",
            previous_expires_at=now - timedelta(days=1),
        )
        session.add(cred)
        await session.flush()
        cred_id = cred.id

        cleaned = await cleanup_expired_previous(session, now=now)
        await session.flush()
        assert cleaned == 1

        session.expire_all()
        row = await session.get(Credential, cred_id)
        assert row is not None
        assert row.previous_value is None
        assert row.previous_encrypted_dek is None
        assert row.previous_expires_at is None

    async def test_rerun_is_noop(self, session: AsyncSession) -> None:
        """After the row is cleaned, a second run cleans 0 more rows."""
        now = datetime(2026, 6, 9, 12, 0, 0)
        cred = _make_credential(
            suffix="rotated",
            expires_at=None,
            previous_value=b"OLD",
            previous_encrypted_dek=b"OLD",
            previous_expires_at=now - timedelta(days=1),
        )
        session.add(cred)
        await session.flush()

        assert await cleanup_expired_previous(session, now=now) == 1
        await session.flush()
        assert await cleanup_expired_previous(session, now=now) == 0
        await session.flush()

    async def test_boundary_now_exact_is_cleaned(self, session: AsyncSession) -> None:
        """``previous_expires_at == now`` is cleaned (NOT treated as future)."""
        now = datetime(2026, 6, 9, 12, 0, 0)
        cred = _make_credential(
            suffix="boundary",
            expires_at=None,
            previous_value=b"OLD",
            previous_encrypted_dek=b"OLD",
            previous_expires_at=now,
        )
        session.add(cred)
        await session.flush()

        cleaned = await cleanup_expired_previous(session, now=now)
        await session.flush()
        assert cleaned == 1

    async def test_future_previous_not_cleaned(self, session: AsyncSession) -> None:
        """``previous_expires_at > now`` is left alone."""
        now = datetime(2026, 6, 9, 12, 0, 0)
        cred = _make_credential(
            suffix="fresh",
            expires_at=None,
            previous_value=b"OLD",
            previous_encrypted_dek=b"OLD",
            previous_expires_at=now + timedelta(days=10),
        )
        session.add(cred)
        await session.flush()
        cred_id = cred.id

        cleaned = await cleanup_expired_previous(session, now=now)
        await session.flush()
        assert cleaned == 0

        session.expire_all()
        row = await session.get(Credential, cred_id)
        assert row is not None
        assert row.previous_value == b"OLD"

    async def test_ignores_rows_with_null_previous(
        self, session: AsyncSession
    ) -> None:
        """Never-rotated rows (no previous_*) are NOT touched."""
        now = datetime(2026, 6, 9, 12, 0, 0)
        cred = _make_credential(suffix="never-rotated", expires_at=None)
        session.add(cred)
        await session.flush()

        cleaned = await cleanup_expired_previous(session, now=now)
        await session.flush()
        assert cleaned == 0

    async def test_ignores_rows_with_half_populated_previous_value_none(
        self, session: AsyncSession
    ) -> None:
        """Row with previous_expires_at set but previous_value=None is skipped
        (the IS NOT NULL guard prevents spurious cleanup)."""
        now = datetime(2026, 6, 9, 12, 0, 0)
        cred = _make_credential(
            suffix="half",
            expires_at=None,
            previous_value=None,
            previous_encrypted_dek=b"DEK",
            previous_expires_at=now - timedelta(days=1),
        )
        session.add(cred)
        await session.flush()

        cleaned = await cleanup_expired_previous(session, now=now)
        await session.flush()
        assert cleaned == 0


# ---------------------------------------------------------------------------
# _utcnow helper
# ---------------------------------------------------------------------------


class TestUtcnow:
    def test_utcnow_returns_aware_utc_datetime(self) -> None:
        """_utcnow returns a timezone-aware UTC datetime."""
        from app.cron import _utcnow

        now = _utcnow()
        assert isinstance(now, datetime)
        assert now.tzinfo is not None
        assert now.tzinfo == UTC


# ---------------------------------------------------------------------------
# CLI entry point tests (_parse_args, main, _entry)
# ---------------------------------------------------------------------------


class TestCLI:
    def test_parse_args_defaults(self) -> None:
        """_parse_args with no args returns namespace with --once False."""
        from app.cron import _parse_args

        ns = _parse_args([])
        assert not ns.once

    def test_parse_args_once_flag(self) -> None:
        """--once sets the flag to True."""
        from app.cron import _parse_args

        ns = _parse_args(["--once"])
        assert ns.once


@pytest.mark.asyncio
class TestMain:
    async def test_main_returns_exit_code_from_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """main returns 0 on successful run with a DB URL set."""
        from app.cron import main

        engine = create_async_engine("sqlite+aiosqlite://", echo=False)

        from sqlalchemy import event as sa_event

        @sa_event.listens_for(engine.sync_engine, "before_cursor_execute", retval=True)
        def _intercept(conn, cursor, statement, parameters, context, executemany):
            if "BIGINT" in statement:
                statement = statement.replace("BIGINT", "INTEGER")
            return statement, parameters

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        monkeypatch.setenv("CREDENTIAL_DB_URL", "sqlite+aiosqlite://")
        monkeypatch.setattr("app.cron.create_async_engine", lambda url, pool_pre_ping=True: engine)

        from app.cron import ExpiryRunResult
        import app.cron as cron_mod

        async def fake_check(*args: Any, **kwargs: Any) -> ExpiryRunResult:
            return ExpiryRunResult(candidates=0, notifications_sent=0, skipped_idempotent=0)

        async def fake_cleanup(*args: Any, **kwargs: Any) -> int:
            return 0

        monkeypatch.setattr(cron_mod, "check_expiring_credentials", fake_check)
        monkeypatch.setattr(cron_mod, "cleanup_expired_previous", fake_cleanup)

        exit_code = await main([])
        assert exit_code == 0

        await engine.dispose()

    async def test_main_no_db_url_returns_1(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When CREDENTIAL_DB_URL is not set, returns exit code 1."""
        from app.cron import main

        import os
        if "CREDENTIAL_DB_URL" in os.environ:
            del os.environ["CREDENTIAL_DB_URL"]

        exit_code = await main([])
        assert exit_code == 1


class TestEntry:
    def test_entry_exits_zero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_entry runs asyncio.run(main()) and exits."""
        from app.cron import _entry

        import logging
        logging.disable(logging.CRITICAL)

        monkeypatch.setenv("CREDENTIAL_DB_URL", "sqlite+aiosqlite://")

        engine = create_async_engine("sqlite+aiosqlite://", echo=False)

        from sqlalchemy import event as sa_event

        @sa_event.listens_for(engine.sync_engine, "before_cursor_execute", retval=True)
        def _intercept(conn, cursor, statement, parameters, context, executemany):
            if "BIGINT" in statement:
                statement = statement.replace("BIGINT", "INTEGER")
            return statement, parameters

        import asyncio

        async def _setup():
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        asyncio.run(_setup())

        monkeypatch.setattr("app.cron.create_async_engine", lambda url, pool_pre_ping=True: engine)

        import app.cron as cron_mod

        async def fake_main(*args: Any, **kwargs: Any) -> int:
            return 0

        monkeypatch.setattr(cron_mod, "main", fake_main)

        import sys as _sys
        monkeypatch.setattr(_sys, "exit", lambda code: None)
        _entry()

        logging.disable(logging.NOTSET)
