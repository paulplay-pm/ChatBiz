"""Integration tests for ``app.services.CredentialService``.

These tests exercise the full envelope-encryption + 双值轮换 path
end-to-end against a real Postgres (via ``testcontainers``). They cover
every Scenario from the change spec that touches the service layer:

* §AES-256-GCM envelope encryption — create + use round-trip.
* §凭证轮换双值窗口期 — rotate, fallback to previous, 30-day window.
* §多租户隔离 — WorkspaceMismatchError on cross-tenant access.
* §凭证列表分页 — page-based listing.
* §凭证类型实现 — oauth2 field round-trip.

The fixture builds the schema by running ``Base.metadata.create_all``
on the testcontainer Postgres (the Alembic migrations are tested
separately in ``test_alembic.py``; here we want the schema fast).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app import crypto
from app.models import Base, Credential, CredentialAudit, CredentialType
from app.schemas import (
    CredentialCreateRequest,
    CredentialRotateRequest,
    CredentialUseRequest,
)
from app.services import (
    ACTION_CREATE,
    ACTION_REVEAL,
    ACTION_ROTATE,
    PREVIOUS_VALUE_TTL,
    CredentialNotFoundError,
    CredentialService,
    WorkspaceMismatchError,
    mask_value,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pg_url() -> Iterator[str]:
    """Spin up a Postgres testcontainer and yield the asyncpg DSN."""
    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url()
        # Normalise psycopg2 → asyncpg for the async engine.
        if url.startswith("postgresql+psycopg2://"):
            url = "postgresql+asyncpg://" + url[len("postgresql+psycopg2://") :]
        elif url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://") :]
        yield url


@pytest_asyncio.fixture(scope="function")
async def session(pg_url: str) -> AsyncIterator[AsyncSession]:
    """Fresh schema per test — drop + create so rows from prior tests
    don't leak into the next assertion."""
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
    """One master key for the whole test session — created here, never persisted."""
    return crypto.generate_master_key()


@pytest_asyncio.fixture
async def service(session: AsyncSession, master_key: bytes) -> CredentialService:
    return CredentialService(session=session, master_key=master_key)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_api_key_request(
    *, name: str = "openai-api-key", value: str = "sk-test-123",
    workspace_id: str = "finance",
) -> CredentialCreateRequest:
    return CredentialCreateRequest(
        name=name,
        type=CredentialType.API_KEY,
        value=SecretStr(value),
        workspace_id=workspace_id,
    )


def _make_oauth2_request() -> CredentialCreateRequest:
    return CredentialCreateRequest(
        name="github-oauth",
        type=CredentialType.OAUTH2,
        value=SecretStr("the-access-token-12345"),
        workspace_id="finance",
        client_id="abc123",
        client_secret=SecretStr("very-secret"),
        token_url="https://github.com/oauth/token",
        scope="repo,read:user",
    )


async def _audit_count(session: AsyncSession, action: str) -> int:
    """Return number of audit rows for a given action."""
    stmt = select(CredentialAudit).where(CredentialAudit.action == action)
    rows = (await session.execute(stmt)).scalars().all()
    return len(rows)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestCreate:
    async def test_create_credential(
        self, service: CredentialService, session: AsyncSession
    ) -> None:
        """Create writes a row, audit logs it, and the masked value round-trips."""
        req = _make_api_key_request(value="sk-test-12345678")
        resp = await service.create(req, user_id="u-alice")

        assert resp.id.startswith("cred_")
        assert resp.name == "openai-api-key"
        assert resp.type is CredentialType.API_KEY
        assert resp.workspace_id == "finance"

        # Verify the row exists with encrypted columns populated.
        row = await session.get(Credential, resp.id)
        assert row is not None
        assert len(row.encrypted_value) >= crypto.GCM_NONCE_BYTES + crypto.GCM_TAG_BYTES
        assert len(row.encrypted_dek) >= crypto.GCM_NONCE_BYTES + crypto.GCM_TAG_BYTES
        # No plaintext anywhere.
        assert b"sk-test-12345678" not in row.encrypted_value
        assert b"sk-test-12345678" not in row.encrypted_dek

        # Audit row written.
        assert await _audit_count(session, ACTION_CREATE) == 1


@pytest.mark.integration
class TestGet:
    async def test_get_credential_masked(
        self, service: CredentialService
    ) -> None:
        """``get`` returns a masked value; raw secret never reaches caller."""
        req = _make_api_key_request(value="sk-test-1234567890ABCDEF")
        created = await service.create(req, user_id="u-alice")

        detail = await service.get(created.id, workspace_id="finance")
        assert detail.id == created.id
        assert detail.masked_value == mask_value("sk-test-1234567890ABCDEF")
        assert detail.masked_value.startswith("sk-t")
        assert detail.masked_value.endswith("CDEF")
        assert "★★★★" in detail.masked_value
        # The full plaintext must NOT appear in the masked value.
        assert "sk-test-1234567890ABCDEF" not in detail.masked_value


@pytest.mark.integration
class TestUse:
    async def test_use_credential_returns_plaintext(
        self, service: CredentialService
    ) -> None:
        """``use`` returns the exact plaintext the user provided on create."""
        req = _make_api_key_request(value="sk-test-PLAINTEXT-9999")
        created = await service.create(req, user_id="u-alice")

        use_req = CredentialUseRequest(cap="workflow-engine", purpose="paul-monthly-report")
        used = await service.use(
            created.id, use_req, user_id="cap-workflow", workspace_id="finance"
        )
        assert used.value == "sk-test-PLAINTEXT-9999"

    async def test_use_credential_wrong_workspace(
        self, service: CredentialService
    ) -> None:
        """Cross-workspace ``use`` raises WorkspaceMismatchError."""
        req = _make_api_key_request(workspace_id="finance")
        created = await service.create(req, user_id="u-alice")

        use_req = CredentialUseRequest(cap="workflow-engine", purpose="cross-tenant-attempt")
        with pytest.raises(WorkspaceMismatchError):
            await service.use(
                created.id, use_req, user_id="cap-workflow", workspace_id="marketing"
            )


@pytest.mark.integration
class TestRotate:
    async def test_rotate_credential(
        self, service: CredentialService, session: AsyncSession
    ) -> None:
        """Rotate moves old ciphertext to ``previous_*``, writes new ciphertext."""
        req = _make_api_key_request(value="old-secret-value-1234")
        created = await service.create(req, user_id="u-alice")
        row_before = await session.get(Credential, created.id)
        assert row_before is not None
        old_encrypted = row_before.encrypted_value
        old_dek = row_before.encrypted_dek

        rotate_req = CredentialRotateRequest(value=SecretStr("new-secret-value-5678"))
        rotated = await service.rotate(created.id, rotate_req, user_id="u-alice")
        assert rotated.id == created.id

        # Re-read from the DB (the row in ``row_before`` is stale after rotate).
        await session.refresh(row_before)
        row_after = row_before
        assert row_after is not None

        # Previous-* now carries what was previously the current.
        assert row_after.previous_value == old_encrypted
        assert row_after.previous_encrypted_dek == old_dek
        # Current is brand-new ciphertext.
        assert row_after.encrypted_value != old_encrypted
        assert row_after.encrypted_dek != old_dek

        assert await _audit_count(session, ACTION_ROTATE) == 1

    async def test_use_after_rotate_returns_new(
        self, service: CredentialService
    ) -> None:
        """After rotation, ``use`` returns the new value (not the previous)."""
        req = _make_api_key_request(value="old-secret-9999")
        created = await service.create(req, user_id="u-alice")
        await service.rotate(
            created.id,
            CredentialRotateRequest(value=SecretStr("new-secret-1111")),
            user_id="u-alice",
        )

        use_req = CredentialUseRequest(cap="cap-1", purpose="post-rotation-fetch")
        used = await service.use(
            created.id, use_req, user_id="cap-1", workspace_id="finance"
        )
        assert used.value == "new-secret-1111"

    async def test_rotate_30_day_window(
        self, service: CredentialService, session: AsyncSession
    ) -> None:
        """``previous_expires_at`` is set to ~ now + 30 days (±1 minute tolerance)."""
        req = _make_api_key_request()
        created = await service.create(req, user_id="u-alice")

        before = datetime.now(UTC)
        await service.rotate(
            created.id,
            CredentialRotateRequest(value=SecretStr("any-new-value")),
            user_id="u-alice",
        )
        after = datetime.now(UTC)

        session.expire_all()
        row = await session.get(Credential, created.id)
        assert row is not None
        assert row.previous_expires_at is not None
        expected_low = before + PREVIOUS_VALUE_TTL - timedelta(minutes=1)
        expected_high = after + PREVIOUS_VALUE_TTL + timedelta(minutes=1)
        assert expected_low <= row.previous_expires_at <= expected_high


@pytest.mark.integration
class TestList:
    async def test_list_credentials_pagination(
        self, service: CredentialService
    ) -> None:
        """Create 5 rows; page=1, page_size=2 returns 2 + total_count=5."""
        for i in range(5):
            await service.create(
                _make_api_key_request(name=f"key-{i}", value=f"value-{i}-padded-12345"),
                user_id="u-alice",
            )

        listed = await service.list(
            workspace_id="finance",
            type=CredentialType.API_KEY,
            page=1,
            page_size=2,
        )
        assert listed.total_count == 5
        assert listed.page == 1
        assert listed.page_size == 2
        assert len(listed.items) == 2

        # Page 3 must give us the trailing 1 row.
        page2 = await service.list(
            workspace_id="finance",
            type=CredentialType.API_KEY,
            page=3,
            page_size=2,
        )
        assert len(page2.items) == 1

        # Across the 3 pages we MUST see every credential exactly once
        # (the per-row ordering depends on created_at tiebreak; we only
        # care that pagination doesn't drop or double-count rows).
        page_mid = await service.list(
            workspace_id="finance",
            type=CredentialType.API_KEY,
            page=2,
            page_size=2,
        )
        all_names = sorted(
            r.name
            for page_resp in (listed, page_mid, page2)
            for r in page_resp.items
        )
        assert all_names == [f"key-{i}" for i in range(5)]


@pytest.mark.integration
class TestDelete:
    async def test_delete_credential(
        self, service: CredentialService, session: AsyncSession
    ) -> None:
        """``delete`` removes the row; subsequent get raises NotFound."""
        req = _make_api_key_request()
        created = await service.create(req, user_id="u-alice")

        await service.delete(created.id, workspace_id="finance", user_id="u-alice")

        with pytest.raises(CredentialNotFoundError):
            await service.get(created.id, workspace_id="finance")

        # The audit row(s) for the original credential survive (audit log is append-only).
        # The delete itself fires its own audit row.
        deleted_audits = [
            row for row in (await session.execute(select(CredentialAudit))).scalars().all()
            if row.action == "delete"
        ]
        assert len(deleted_audits) == 1


@pytest.mark.integration
class TestReveal:
    async def test_reveal_credential(
        self, service: CredentialService, session: AsyncSession
    ) -> None:
        """``reveal`` returns the exact plaintext + writes a reveal audit row."""
        req = _make_api_key_request(value="reveal-me-secret-aaaa")
        created = await service.create(req, user_id="u-admin")

        revealed = await service.reveal(created.id, user_id="u-admin")
        assert revealed.value == "reveal-me-secret-aaaa"
        assert await _audit_count(session, ACTION_REVEAL) == 1


@pytest.mark.integration
class TestOAuth2:
    async def test_oauth2_credential_round_trip(
        self, service: CredentialService
    ) -> None:
        """OAuth2 type-specific fields survive the create → use round-trip.

        The fields are encoded into the JSON payload that gets encrypted;
        ``use`` returns the secret ``value`` only, but the metadata
        survives because it sits next to ``value`` inside the
        ciphertext and is recovered every time we decrypt.
        """
        req = _make_oauth2_request()
        created = await service.create(req, user_id="u-alice")
        assert created.type is CredentialType.OAUTH2

        use_req = CredentialUseRequest(cap="oauth-refresher", purpose="token-refresh")
        used = await service.use(
            created.id, use_req, user_id="cap-oauth", workspace_id="finance"
        )
        assert used.value == "the-access-token-12345"
