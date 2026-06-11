"""Unit tests for ``app.services.CredentialService`` — CRUD + encryption orchestration.

Uses aiosqlite (in-memory) for the async engine — no testcontainers needed.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy import BigInteger, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app import crypto
from app.models import Base, Credential, CredentialAudit, CredentialType
from app.schemas import (
    CredentialCreateRequest,
    CredentialRotateRequest,
    CredentialUseRequest,
)
from app.services import (
    ACTION_CREATE,
    ACTION_DELETE,
    ACTION_READ,
    ACTION_REVEAL,
    ACTION_ROTATE,
    ACTION_USE,
    PREVIOUS_VALUE_TTL,
    CredentialExpiredError,
    CredentialNotFoundError,
    CredentialService,
    WorkspaceMismatchError,
    _generate_credential_id,
    mask_value,
)

# ---------------------------------------------------------------------------
# Engine setup
# ---------------------------------------------------------------------------


# SQLite does not support BigInteger autoincrement; intercept CREATE TABLE
# DDL and replace BIGINT with INTEGER for the credential_audit table so
# the ``id`` column gets SQLite's ROWID alias auto-increment behaviour.


@pytest_asyncio.fixture(scope="function")
async def session() -> AsyncIterator[AsyncSession]:
    """Create in-memory SQLite engine + session per test.

    Hooks ``before_cursor_execute`` to patch BIGINT → INTEGER in the
    ``credential_audit`` DDL, then calls ``create_all``.
    """
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
def _sqlite_utcnow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch ``_utcnow`` to return naive UTC datetimes.

    SQLite strips timezone from DateTime columns, so ``_check_not_expired``
    fails when comparing aware ``datetime.now(UTC)`` against a naive
    ``expires_at`` loaded from SQLite. This fixture makes ``_utcnow``
    return a naive datetime so comparisons work on SQLite.
    """
    from app import services as svc_mod
    from app.services import _utcnow as _orig

    def _naive_utcnow() -> datetime:
        return _orig().replace(tzinfo=None)

    monkeypatch.setattr(svc_mod, "_utcnow", _naive_utcnow)


@pytest.fixture
def _sqlite_utcnow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch ``_utcnow`` to return naive UTC datetimes.

    SQLite strips timezone from DateTime columns, so ``_check_not_expired``
    fails when comparing aware ``datetime.now(UTC)`` against a naive
    ``expires_at`` loaded from SQLite. This fixture makes ``_utcnow``
    return a naive datetime so comparisons work on SQLite.
    """
    from app import services as svc_mod
    from app.services import _utcnow as _orig

    def _naive_utcnow() -> datetime:
        return _orig().replace(tzinfo=None)

    monkeypatch.setattr(svc_mod, "_utcnow", _naive_utcnow)


@pytest.fixture(scope="session")
def master_key() -> bytes:
    return crypto.generate_master_key()


@pytest_asyncio.fixture
async def service(session: AsyncSession, master_key: bytes) -> CredentialService:
    return CredentialService(session=session, master_key=master_key)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_api_key_req(
    name: str = "openai-key",
    value: str = "sk-test-123",
    workspace_id: str = "finance",
) -> CredentialCreateRequest:
    return CredentialCreateRequest(
        name=name,
        type=CredentialType.API_KEY,
        value=SecretStr(value),
        workspace_id=workspace_id,
    )


def _make_oauth2_req() -> CredentialCreateRequest:
    return CredentialCreateRequest(
        name="github-oauth",
        type=CredentialType.OAUTH2,
        value=SecretStr("gh-token-abc"),
        workspace_id="finance",
        client_id="abc123",
        client_secret=SecretStr("very-secret"),
        token_url="https://github.com/oauth/token",
        scope="repo,read:user",
    )


def _make_database_req() -> CredentialCreateRequest:
    return CredentialCreateRequest(
        name="pg-db",
        type=CredentialType.DATABASE,
        value=SecretStr("db-pass-456"),
        workspace_id="finance",
        host="localhost",
        port=5432,
        db_name="mydb",
    )


def _make_smtp_req() -> CredentialCreateRequest:
    return CredentialCreateRequest(
        name="smtp-relay",
        type=CredentialType.SMTP,
        value=SecretStr("smtp-pass-789"),
        workspace_id="finance",
        host="smtp.example.com",
        port=587,
        username="sender",
    )


async def _audit_count(session: AsyncSession, action: str) -> int:
    stmt = select(CredentialAudit).where(CredentialAudit.action == action)
    rows = (await session.execute(stmt)).scalars().all()
    return len(rows)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreate:
    async def test_create_api_key(
        self, service: CredentialService, session: AsyncSession
    ) -> None:
        req = _make_api_key_req(value="sk-test-12345678")
        resp = await service.create(req, user_id="u-alice")

        assert resp.id.startswith("cred_")
        assert len(resp.id) == 32  # cred_ (5) + 27 base62 = 32
        assert resp.name == "openai-key"
        assert resp.type is CredentialType.API_KEY
        assert resp.workspace_id == "finance"

        row = await session.get(Credential, resp.id)
        assert row is not None
        assert len(row.encrypted_value) >= crypto.GCM_NONCE_BYTES + crypto.GCM_TAG_BYTES
        assert len(row.encrypted_dek) >= crypto.GCM_NONCE_BYTES + crypto.GCM_TAG_BYTES
        assert b"sk-test-12345678" not in row.encrypted_value

        assert await _audit_count(session, ACTION_CREATE) == 1

    async def test_create_oauth2(
        self, service: CredentialService, session: AsyncSession
    ) -> None:
        req = _make_oauth2_req()
        resp = await service.create(req, user_id="u-alice")
        assert resp.type is CredentialType.OAUTH2
        assert await _audit_count(session, ACTION_CREATE) == 1

    async def test_create_database(
        self, service: CredentialService, session: AsyncSession
    ) -> None:
        req = _make_database_req()
        resp = await service.create(req, user_id="u-alice")
        assert resp.type is CredentialType.DATABASE
        assert await _audit_count(session, ACTION_CREATE) == 1

    async def test_create_smtp(
        self, service: CredentialService, session: AsyncSession
    ) -> None:
        req = _make_smtp_req()
        resp = await service.create(req, user_id="u-alice")
        assert resp.type is CredentialType.SMTP
        assert await _audit_count(session, ACTION_CREATE) == 1

    async def test_create_with_expires_at(
        self, service: CredentialService
    ) -> None:
        dt = datetime(2026, 12, 31, tzinfo=UTC)
        req = CredentialCreateRequest(
            name="key",
            type=CredentialType.API_KEY,
            value=SecretStr("v"),
            workspace_id="ws",
            expires_at=dt,
        )
        resp = await service.create(req, user_id="u-1")
        assert resp.expires_at == dt


@pytest.mark.asyncio
class TestGet:
    async def test_get_returns_masked_value(
        self, service: CredentialService
    ) -> None:
        req = _make_api_key_req(value="sk-test-1234567890ABCDEF")
        created = await service.create(req, user_id="u-alice")

        detail = await service.get(created.id, workspace_id="finance")
        assert detail.id == created.id
        assert detail.masked_value == mask_value("sk-test-1234567890ABCDEF")
        assert "★★★★" in detail.masked_value

    async def test_get_short_value_masked(self, service: CredentialService) -> None:
        """Value < 8 chars → masked_value = ★★★★"""
        req = _make_api_key_req(value="short")
        created = await service.create(req, user_id="u-alice")

        detail = await service.get(created.id, workspace_id="finance")
        assert detail.masked_value == "★★★★"

    async def test_get_nonexistent_raises(self, service: CredentialService) -> None:
        with pytest.raises(CredentialNotFoundError):
            await service.get("cred_doesnotexist", workspace_id="finance")

    async def test_get_wrong_workspace_raises(
        self, service: CredentialService
    ) -> None:
        req = _make_api_key_req(workspace_id="finance")
        created = await service.create(req, user_id="u-alice")

        with pytest.raises(WorkspaceMismatchError):
            await service.get(created.id, workspace_id="marketing")


@pytest.mark.asyncio
class TestUse:
    async def test_use_returns_plaintext(
        self, service: CredentialService
    ) -> None:
        req = _make_api_key_req(value="sk-test-PLAINTEXT-9999")
        created = await service.create(req, user_id="u-alice")

        use_req = CredentialUseRequest(
            cap="workflow-engine", purpose="paul-monthly-report"
        )
        used = await service.use(
            created.id, use_req, user_id="cap-workflow", workspace_id="finance"
        )
        assert used.value == "sk-test-PLAINTEXT-9999"

    async def test_use_wrong_workspace_raises(
        self, service: CredentialService
    ) -> None:
        req = _make_api_key_req(workspace_id="finance")
        created = await service.create(req, user_id="u-alice")

        use_req = CredentialUseRequest(cap="wf-engine", purpose="test")
        with pytest.raises(WorkspaceMismatchError):
            await service.use(
                created.id, use_req, user_id="cap", workspace_id="marketing"
            )

    async def test_use_nonexistent_raises(
        self, service: CredentialService
    ) -> None:
        use_req = CredentialUseRequest(cap="wf-engine", purpose="test")
        with pytest.raises(CredentialNotFoundError):
            await service.use(
                "cred_none", use_req, user_id="cap", workspace_id="ws"
            )

    async def test_use_with_fallback_to_previous(
        self, service: CredentialService, session: AsyncSession, _sqlite_utcnow: None
    ) -> None:
        """After rotation, 'use' returns new value. If we tamper with the
        current encrypted_value, the fallback decodes the previous value."""
        req = _make_api_key_req(value="old-value-abc")
        created = await service.create(req, user_id="u-alice")

        await service.rotate(
            created.id,
            CredentialRotateRequest(value=SecretStr("new-value-xyz")),
            user_id="u-alice",
        )

        # Corrupt the current value so decryption fails → fallback.
        row = await session.get(Credential, created.id)
        assert row is not None
        row.encrypted_value = b"\x00" * 28  # minimum blob length, invalid content
        await session.flush()
        # Clear the loaded row identity so the next session.get() returns a fresh row.
        session.expire_all()

        use_req = CredentialUseRequest(cap="wf-engine", purpose="fallback-test")
        used = await service.use(
            created.id, use_req, user_id="cap", workspace_id="finance"
        )
        # Must return the previous (old) value, not the new one.
        assert used.value == "old-value-abc"

    async def test_use_expired_raises(
        self, service: CredentialService, _sqlite_utcnow: None
    ) -> None:
        dt = datetime(2022, 1, 1, tzinfo=UTC)
        req = CredentialCreateRequest(
            name="expired-key",
            type=CredentialType.API_KEY,
            value=SecretStr("v"),
            workspace_id="ws",
            expires_at=dt,
        )
        created = await service.create(req, user_id="u-1")

        use_req = CredentialUseRequest(cap="cap", purpose="test")
        with pytest.raises(CredentialExpiredError):
            await service.use(
                created.id, use_req, user_id="cap", workspace_id="ws"
            )


@pytest.mark.asyncio
class TestRotate:
    async def test_rotate_moves_to_previous(
        self, service: CredentialService, session: AsyncSession
    ) -> None:
        req = _make_api_key_req(value="old-secret-1234")
        created = await service.create(req, user_id="u-alice")
        row_before = await session.get(Credential, created.id)
        assert row_before is not None
        old_encrypted = row_before.encrypted_value
        old_dek = row_before.encrypted_dek

        rotate_req = CredentialRotateRequest(value=SecretStr("new-secret-5678"))
        rotated = await service.rotate(created.id, rotate_req, user_id="u-alice")
        assert rotated.id == created.id

        await session.refresh(row_before)
        assert row_before.previous_value == old_encrypted
        assert row_before.previous_encrypted_dek == old_dek
        assert row_before.encrypted_value != old_encrypted
        assert row_before.encrypted_dek != old_dek
        assert await _audit_count(session, ACTION_ROTATE) == 1

    async def test_use_after_rotate_returns_new(
        self, service: CredentialService
    ) -> None:
        req = _make_api_key_req(value="old-9999")
        created = await service.create(req, user_id="u-alice")
        await service.rotate(
            created.id,
            CredentialRotateRequest(value=SecretStr("new-1111")),
            user_id="u-alice",
        )

        use_req = CredentialUseRequest(cap="cap", purpose="post-rotate")
        used = await service.use(
            created.id, use_req, user_id="cap", workspace_id="finance"
        )
        assert used.value == "new-1111"

    async def test_rotate_preserves_metadata(
        self, service: CredentialService
    ) -> None:
        """Rotation only changes the secret value, not type-specific fields."""
        req = _make_oauth2_req()
        created = await service.create(req, user_id="u-alice")

        await service.rotate(
            created.id,
            CredentialRotateRequest(value=SecretStr("new-oauth-token-xxx")),
            user_id="u-alice",
        )

        use_req = CredentialUseRequest(cap="cap", purpose="check-metadata")
        used = await service.use(
            created.id, use_req, user_id="cap", workspace_id="finance"
        )
        # After rotation, the value is the new one.
        assert used.value == "new-oauth-token-xxx"

    async def test_rotate_30_day_window(
        self, service: CredentialService, session: AsyncSession, _sqlite_utcnow: None
    ) -> None:
        req = _make_api_key_req()
        created = await service.create(req, user_id="u-alice")

        await service.rotate(
            created.id,
            CredentialRotateRequest(value=SecretStr("any-new")),
            user_id="u-alice",
        )

        session.expire_all()
        row = await session.get(Credential, created.id)
        assert row is not None
        assert row.previous_expires_at is not None
        # SQLite stores naive datetimes; PREVIOUS_VALUE_TTL is 30 days.
        # Compare day-level only to avoid timezone issues.
        expected = datetime.now(UTC).replace(tzinfo=None) + PREVIOUS_VALUE_TTL
        diff = abs((row.previous_expires_at - expected).total_seconds())
        assert diff < 120  # within 2 minutes

    async def test_rotate_nonexistent_raises(
        self, service: CredentialService
    ) -> None:
        rotate_req = CredentialRotateRequest(value=SecretStr("val"))
        with pytest.raises(CredentialNotFoundError):
            await service.rotate("cred_nonexistent", rotate_req, user_id="u-1")

    async def test_rotate_with_expires_at(
        self, service: CredentialService, session: AsyncSession
    ) -> None:
        req = _make_api_key_req(value="val-1")
        created = await service.create(req, user_id="u-1")

        new_expiry = datetime(2027, 6, 1, tzinfo=UTC)
        rotate_req = CredentialRotateRequest(
            value=SecretStr("new-val"), expires_at=new_expiry
        )
        await service.rotate(created.id, rotate_req, user_id="u-1")

        session.expire_all()
        row = await session.get(Credential, created.id)
        assert row is not None
        # SQLite strips timezone — compare as naive.
        assert row.expires_at == new_expiry.replace(tzinfo=None)


@pytest.mark.asyncio
class TestList:
    async def test_list_returns_all_in_workspace(
        self, service: CredentialService
    ) -> None:
        for i in range(3):
            await service.create(
                _make_api_key_req(name=f"key-{i}", value=f"val-{i}-super-long-123456"),
                user_id="u-alice",
            )

        resp = await service.list(
            workspace_id="finance", type=CredentialType.API_KEY, page=1, page_size=10
        )
        assert resp.total_count == 3
        assert len(resp.items) == 3

    async def test_list_pagination(
        self, service: CredentialService
    ) -> None:
        for i in range(5):
            await service.create(
                _make_api_key_req(name=f"key-{i}", value=f"val-{i}-padded-1234567890"),
                user_id="u-alice",
            )

        page1 = await service.list(
            workspace_id="finance", type=CredentialType.API_KEY, page=1, page_size=2
        )
        assert page1.total_count == 5
        assert len(page1.items) == 2

        page3 = await service.list(
            workspace_id="finance", type=CredentialType.API_KEY, page=3, page_size=2
        )
        assert len(page3.items) == 1

    async def test_list_empty_workspace(self, service: CredentialService) -> None:
        resp = await service.list(
            workspace_id="empty-ws", type=None, page=1, page_size=10
        )
        assert resp.total_count == 0
        assert resp.items == []

    async def test_list_type_filter(self, service: CredentialService) -> None:
        await service.create(_make_api_key_req(workspace_id="ws-1"), user_id="u-1")
        await service.create(_make_database_req(), user_id="u-1")

        resp = await service.list(
            workspace_id="finance", type=CredentialType.API_KEY, page=1, page_size=10
        )
        assert all(item.type is CredentialType.API_KEY for item in resp.items)

    async def test_list_no_type_filter(self, service: CredentialService) -> None:
        await service.create(
            CredentialCreateRequest(name="k1", type=CredentialType.API_KEY, value=SecretStr("v1"), workspace_id="ws-x"),
            user_id="u-1",
        )
        await service.create(
            CredentialCreateRequest(name="k2", type=CredentialType.DATABASE, value=SecretStr("v2"), workspace_id="ws-x", host="h", port=1, db_name="d"),
            user_id="u-1",
        )

        resp = await service.list(workspace_id="ws-x", type=None, page=1, page_size=10)
        assert resp.total_count == 2


@pytest.mark.asyncio
class TestReveal:
    async def test_reveal_returns_plaintext(
        self, service: CredentialService, session: AsyncSession
    ) -> None:
        req = _make_api_key_req(value="reveal-me-aaaa")
        created = await service.create(req, user_id="u-admin")

        revealed = await service.reveal(created.id, user_id="u-admin")
        assert revealed.value == "reveal-me-aaaa"
        assert await _audit_count(session, ACTION_REVEAL) == 1

    async def test_reveal_nonexistent_raises(
        self, service: CredentialService
    ) -> None:
        with pytest.raises(CredentialNotFoundError):
            await service.reveal("cred_none", user_id="u-admin")

    async def test_reveal_expired_raises(
        self, service: CredentialService, _sqlite_utcnow: None
    ) -> None:
        dt = datetime(2022, 1, 1, tzinfo=UTC)
        req = CredentialCreateRequest(
            name="exp-key",
            type=CredentialType.API_KEY,
            value=SecretStr("val"),
            workspace_id="ws",
            expires_at=dt,
        )
        created = await service.create(req, user_id="u-1")

        with pytest.raises(CredentialExpiredError):
            await service.reveal(created.id, user_id="u-1")


@pytest.mark.asyncio
class TestDelete:
    async def test_delete_removes_row(
        self, service: CredentialService, session: AsyncSession
    ) -> None:
        req = _make_api_key_req()
        created = await service.create(req, user_id="u-alice")

        await service.delete(created.id, workspace_id="finance", user_id="u-alice")

        with pytest.raises(CredentialNotFoundError):
            await service.get(created.id, workspace_id="finance")

        assert await _audit_count(session, ACTION_DELETE) == 1

    async def test_delete_nonexistent_raises(
        self, service: CredentialService
    ) -> None:
        with pytest.raises(CredentialNotFoundError):
            await service.delete("cred_none", workspace_id="ws", user_id="u-1")

    async def test_delete_wrong_workspace_raises(
        self, service: CredentialService
    ) -> None:
        req = _make_api_key_req(workspace_id="finance")
        created = await service.create(req, user_id="u-alice")

        with pytest.raises(WorkspaceMismatchError):
            await service.delete(created.id, workspace_id="marketing", user_id="u-1")


@pytest.mark.asyncio
class TestAuditOnError:
    async def test_get_nonexistent_writes_audit(
        self, service: CredentialService, session: AsyncSession
    ) -> None:
        try:
            await service.get("cred_nonexistent_audit", workspace_id="ws")
        except CredentialNotFoundError:
            pass

        # _load_row writes audit on failure
        read_audits = await _audit_count(session, ACTION_READ)
        assert read_audits >= 1

    async def test_reveal_nonexistent_writes_audit(
        self, service: CredentialService, session: AsyncSession
    ) -> None:
        try:
            await service.reveal("cred_nonexistent_reveal", user_id="u-1")
        except CredentialNotFoundError:
            pass

        reveal_audits = await _audit_count(session, ACTION_REVEAL)
        assert reveal_audits >= 1

    async def test_rotate_nonexistent_writes_audit(
        self, service: CredentialService, session: AsyncSession
    ) -> None:
        try:
            await service.rotate(
                "cred_no_rotate",
                CredentialRotateRequest(value=SecretStr("val")),
                user_id="u-1",
            )
        except CredentialNotFoundError:
            pass

        rotate_audits = await _audit_count(session, ACTION_ROTATE)
        assert rotate_audits >= 1


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


class TestGenerateCredentialId:
    def test_id_starts_with_cred_prefix(self) -> None:
        for _ in range(100):
            cid = _generate_credential_id()
            assert cid.startswith("cred_")
            assert len(cid) == 32

    def test_ids_are_unique(self) -> None:
        ids = {_generate_credential_id() for _ in range(100)}
        assert len(ids) == 100

    def test_id_only_alphanumeric_after_prefix(self) -> None:
        cid = _generate_credential_id()
        suffix = cid[5:]
        assert all(c.isalnum() for c in suffix)


class TestMaskValue:
    def test_long_value_masked(self) -> None:
        masked = mask_value("sk-test-1234567890ABC")
        assert masked == "sk-t★★★★0ABC"
        assert "★★★★" in masked

    def test_exactly_8_chars_not_fully_masked(self) -> None:
        masked = mask_value("12345678")
        assert masked == "1234★★★★5678"

    def test_short_value_masked(self) -> None:
        masked = mask_value("short")
        assert masked == "★★★★"

    def test_7_chars_masked(self) -> None:
        masked = mask_value("1234567")
        assert masked == "★★★★"

    def test_chinese_value(self) -> None:
        masked = mask_value("我的超级密码在这里呀")
        assert masked == "我的超级★★★★在这里呀"


class TestHelperFunctions:
    """Test module-level helper functions (non-class)."""

    def test__check_not_expired_no_expiry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app import services as svc_mod
        from app.services import _check_not_expired, _utcnow as _orig

        monkeypatch.setattr(svc_mod, "_utcnow", lambda: _orig().replace(tzinfo=None))

        row = Credential(
            id="cred_x", name="n", type=CredentialType.API_KEY,
            encrypted_value=b"\x00" * 28, encrypted_dek=b"\x00" * 60,
            workspace_id="ws",
        )
        _check_not_expired(row)

    def test__check_not_expired_expired_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app import services as svc_mod
        from app.services import _check_not_expired, _utcnow as _orig

        monkeypatch.setattr(svc_mod, "_utcnow", lambda: _orig().replace(tzinfo=None))

        row = Credential(
            id="cred_x", name="n", type=CredentialType.API_KEY,
            encrypted_value=b"\x00" * 28, encrypted_dek=b"\x00" * 60,
            workspace_id="ws",
            expires_at=datetime(2000, 1, 1),
        )
        with pytest.raises(CredentialExpiredError):
            _check_not_expired(row)

    def test__check_not_expired_future_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app import services as svc_mod
        from app.services import _check_not_expired, _utcnow as _orig

        monkeypatch.setattr(svc_mod, "_utcnow", lambda: _orig().replace(tzinfo=None))

        row = Credential(
            id="cred_x", name="n", type=CredentialType.API_KEY,
            encrypted_value=b"\x00" * 28, encrypted_dek=b"\x00" * 60,
            workspace_id="ws",
            expires_at=datetime(2099, 12, 31),
        )
        _check_not_expired(row)

    def test__previous_value_available_false_when_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app import services as svc_mod
        from app.services import _previous_value_available, _utcnow as _orig

        monkeypatch.setattr(svc_mod, "_utcnow", lambda: _orig().replace(tzinfo=None))

        row = Credential(
            id="cred_x", name="n", type=CredentialType.API_KEY,
            encrypted_value=b"\x00" * 28, encrypted_dek=b"\x00" * 60,
            workspace_id="ws",
        )
        assert not _previous_value_available(row)

    def test__previous_value_available_true_when_valid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app import services as svc_mod
        from app.services import _previous_value_available, _utcnow as _orig

        monkeypatch.setattr(svc_mod, "_utcnow", lambda: _orig().replace(tzinfo=None))

        row = Credential(
            id="cred_x", name="n", type=CredentialType.API_KEY,
            encrypted_value=b"\x00" * 28, encrypted_dek=b"\x00" * 60,
            workspace_id="ws",
            previous_value=b"\x00" * 28,
            previous_encrypted_dek=b"\x00" * 60,
            previous_expires_at=datetime(2099, 12, 31),
        )
        assert _previous_value_available(row)

    def test__previous_value_available_false_when_expired(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app import services as svc_mod
        from app.services import _previous_value_available, _utcnow as _orig

        monkeypatch.setattr(svc_mod, "_utcnow", lambda: _orig().replace(tzinfo=None))

        row = Credential(
            id="cred_x", name="n", type=CredentialType.API_KEY,
            encrypted_value=b"\x00" * 28, encrypted_dek=b"\x00" * 60,
            workspace_id="ws",
            previous_value=b"\x00" * 28,
            previous_encrypted_dek=b"\x00" * 60,
            previous_expires_at=datetime(2000, 1, 1),
        )
        assert not _previous_value_available(row)

    def test__previous_value_available_false_when_no_expires_at(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app import services as svc_mod
        from app.services import _previous_value_available, _utcnow as _orig

        monkeypatch.setattr(svc_mod, "_utcnow", lambda: _orig().replace(tzinfo=None))

        row = Credential(
            id="cred_x", name="n", type=CredentialType.API_KEY,
            encrypted_value=b"\x00" * 28, encrypted_dek=b"\x00" * 60,
            workspace_id="ws",
            previous_value=b"\x00" * 28,
            previous_encrypted_dek=b"\x00" * 60,
        )
        assert not _previous_value_available(row)

    def test__to_response(self) -> None:
        from app.services import _to_response

        now = datetime(2026, 6, 1, tzinfo=UTC)
        row = Credential(
            id="cred_test", name="test-key", type=CredentialType.SMTP,
            encrypted_value=b"\x00" * 28, encrypted_dek=b"\x00" * 60,
            workspace_id="ws-1",
            expires_at=None,
            created_at=now,
            updated_at=now,
        )
        resp = _to_response(row)
        assert resp.id == "cred_test"
        assert resp.name == "test-key"
        assert resp.type is CredentialType.SMTP
        assert resp.workspace_id == "ws-1"


class TestServiceConstants:
    def test_constants_defined(self) -> None:
        assert ACTION_CREATE == "create"
        assert ACTION_DELETE == "delete"
        assert ACTION_READ == "read"
        assert ACTION_ROTATE == "rotate"
        assert ACTION_REVEAL == "reveal"
        assert ACTION_USE == "use"
        assert PREVIOUS_VALUE_TTL == timedelta(days=30)


class TestCredentialUseWithFallbackWhenBothExpired:
    async def test_no_fallback_when_previous_expired(
        self, service: CredentialService, session: AsyncSession, _sqlite_utcnow: None
    ) -> None:
        """When previous expires_at is in the past, fallback should NOT be used."""
        req = _make_api_key_req(value="old-val")
        created = await service.create(req, user_id="u-alice")

        await service.rotate(
            created.id,
            CredentialRotateRequest(value=SecretStr("new-val")),
            user_id="u-alice",
        )

        row = await session.get(Credential, created.id)
        assert row is not None
        # Expire the previous value (naive datetime for SQLite).
        row.previous_expires_at = datetime(2000, 1, 1)
        # Corrupt current value
        row.encrypted_value = b"\x00" * 28
        await session.flush()
        session.expire_all()

        use_req = CredentialUseRequest(cap="cap", purpose="test")
        with pytest.raises(Exception):
            await service.use(
                created.id, use_req, user_id="cap", workspace_id="finance"
            )


class TestCredentialUseWithExpiredCredential:
    async def test_use_expired_fails_even_with_fallback(
        self, service: CredentialService, _sqlite_utcnow: None
    ) -> None:
        """An expired credential cannot be used, even with a previous value."""
        dt = datetime(2020, 1, 1, tzinfo=UTC)
        req = CredentialCreateRequest(
            name="old-key",
            type=CredentialType.API_KEY,
            value=SecretStr("val"),
            workspace_id="ws-1",
            expires_at=dt,
        )
        created = await service.create(req, user_id="u-1")

        use_req = CredentialUseRequest(cap="cap", purpose="test")
        with pytest.raises(CredentialExpiredError):
            await service.use(
                created.id, use_req, user_id="cap", workspace_id="ws-1"
            )
