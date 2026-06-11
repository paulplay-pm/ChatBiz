"""Unit tests for async crypto functions — load_master_key, rotate_master_key, subkey cache.

Uses aiosqlite (in-memory) for the async engine — no testcontainers needed.
"""

from __future__ import annotations

import secrets
from collections.abc import AsyncIterator
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import crypto
from app.crypto import (
    MasterKeyNotFoundError,
    MasterKeyRecord,
    _derive_master_subkey_cached,
    _invalidate_subkey_cache,
    decrypt_dek_with_master,
    encrypt_dek_with_master,
    generate_dek,
    generate_master_key,
    load_master_key,
    rotate_master_key,
)
from app.models import Base, Credential, CredentialType, EncryptionKey, KeyStatus


# ---------------------------------------------------------------------------
# Engine fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def session() -> AsyncIterator[AsyncSession]:
    """Create in-memory SQLite engine + session per test."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


async def _insert_active_key(session: AsyncSession, key: bytes | None = None) -> tuple[int, UUID, bytes]:
    """Insert an ACTIVE EncryptionKey row; return (id, key_id, key_bytes)."""
    if key is None:
        key = generate_master_key()
    kid = UUID(int=secrets.randbits(128))
    row = EncryptionKey(key_id=kid, encrypted_key=key, status=KeyStatus.ACTIVE)
    session.add(row)
    await session.flush()
    return row.id, kid, key


async def _insert_credential(
    session: AsyncSession,
    suffix: str,
    master_key: bytes,
    *,
    prev_dek: bytes | None = None,
    prev_master: bytes | None = None,
) -> Credential:
    """Insert a Credential row with DEK encrypted under master_key."""
    dek = generate_dek()
    enc_dek = encrypt_dek_with_master(dek, master_key)
    enc_val = crypto.encrypt_with_dek(b"test-value-" + suffix.encode(), dek)

    prev_value = None
    prev_enc_dek = None
    if prev_dek is not None and prev_master is not None:
        prev_value = crypto.encrypt_with_dek(b"prev-value-" + suffix.encode(), prev_dek)
        prev_enc_dek = encrypt_dek_with_master(prev_dek, prev_master)

    cred = Credential(
        id=f"cred_async_{suffix}",
        name=f"key-{suffix}",
        type=CredentialType.API_KEY,
        encrypted_value=enc_val,
        encrypted_dek=enc_dek,
        previous_value=prev_value,
        previous_encrypted_dek=prev_enc_dek,
        workspace_id="finance",
    )
    session.add(cred)
    await session.flush()
    return cred


# ---------------------------------------------------------------------------
# load_master_key tests (lines 348-359)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLoadMasterKey:
    async def test_load_master_key_returns_active_key(self, session: AsyncSession) -> None:
        """When an ACTIVE key exists, load_master_key returns it."""
        eid, kid, key = await _insert_active_key(session)

        record = await load_master_key(session)
        assert isinstance(record, MasterKeyRecord)
        assert record.key_id == kid
        assert record.key == key

    async def test_load_master_key_raises_when_no_active_key(
        self, session: AsyncSession
    ) -> None:
        """When no ACTIVE key exists, raises MasterKeyNotFoundError."""
        with pytest.raises(MasterKeyNotFoundError):
            await load_master_key(session)

    async def test_load_master_key_prefers_latest_active(
        self, session: AsyncSession
    ) -> None:
        """When multiple ACTIVE keys exist, returns the latest (highest id)."""
        _, _, key1 = await _insert_active_key(session)
        eid2, kid2, key2 = await _insert_active_key(session)

        record = await load_master_key(session)
        assert record.key_id == kid2
        assert record.key == key2

    async def test_load_master_key_ignores_retired(
        self, session: AsyncSession
    ) -> None:
        """Retired keys are ignored by load_master_key."""
        mk = generate_master_key()
        retired = EncryptionKey(
            key_id=UUID(int=secrets.randbits(128)),
            encrypted_key=mk,
            status=KeyStatus.RETIRED,
        )
        session.add(retired)
        await session.flush()

        with pytest.raises(MasterKeyNotFoundError):
            await load_master_key(session)


# ---------------------------------------------------------------------------
# rotate_master_key tests (lines 386-435)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRotateMasterKey:
    async def test_rotate_with_no_credentials(
        self, session: AsyncSession
    ) -> None:
        """Rotation with zero credentials — old key retired, new key active."""
        eid, old_kid, old_key = await _insert_active_key(session)
        await session.commit()  # commit so rotate can begin its own transaction

        new_record = await rotate_master_key(session)
        assert new_record.key_id != old_kid
        assert len(new_record.key) == 32

        # Old key is now RETIRED (use autoincrement id, not UUID key_id, for SQLite)
        old_row = await session.get(EncryptionKey, eid)
        assert old_row is not None
        assert old_row.status == KeyStatus.RETIRED

    async def test_rotate_rewraps_credential_deks(
        self, session: AsyncSession
    ) -> None:
        """Rotation re-wraps all credential DEKs under the new master."""
        eid, old_kid, old_key = await _insert_active_key(session)
        cred = await _insert_credential(session, "1", old_key)
        await session.commit()  # commit so rotate can begin its own transaction

        new_record = await rotate_master_key(session)

        # Verify DEK can be decrypted with new master
        row = await session.get(Credential, cred.id)
        assert row is not None
        dek = decrypt_dek_with_master(row.encrypted_dek, new_record.key)
        plaintext = crypto.decrypt_with_dek(row.encrypted_value, dek)
        assert plaintext == b"test-value-1"

    async def test_rotate_rewraps_previous_deks(
        self, session: AsyncSession
    ) -> None:
        """Rotation re-wraps previous_encrypted_dek under the new master."""
        eid, old_kid, old_key = await _insert_active_key(session)
        prev_dek = generate_dek()
        await _insert_credential(session, "2", old_key, prev_dek=prev_dek, prev_master=old_key)
        await session.commit()  # commit so rotate can begin its own transaction

        new_record = await rotate_master_key(session)

        # Verify previous_encrypted_dek can be decrypted with new master
        row = await session.get(Credential, "cred_async_2")
        assert row is not None
        assert row.previous_encrypted_dek is not None
        recovered_prev_dek = decrypt_dek_with_master(row.previous_encrypted_dek, new_record.key)
        assert recovered_prev_dek == prev_dek

    async def test_rotate_with_provided_new_master(
        self, session: AsyncSession
    ) -> None:
        """When new_master is provided, use it instead of generating."""
        eid, old_kid, old_key = await _insert_active_key(session)
        await session.commit()  # commit so rotate can begin its own transaction
        custom_key = generate_master_key()

        new_record = await rotate_master_key(session, new_master=custom_key)
        assert new_record.key == custom_key

    async def test_rotate_multiple_credentials(
        self, session: AsyncSession
    ) -> None:
        """Rotation re-wraps DEKs for all credentials in the DB."""
        eid, old_kid, old_key = await _insert_active_key(session)
        await _insert_credential(session, "a", old_key)
        await _insert_credential(session, "b", old_key)
        await _insert_credential(session, "c", old_key)
        await session.commit()  # commit so rotate can begin its own transaction

        new_record = await rotate_master_key(session)

        # All credentials should be decryptable with the new master
        stmt = select(Credential)
        rows = (await session.execute(stmt)).scalars().all()
        assert len(rows) == 3
        for row in rows:
            dek = decrypt_dek_with_master(row.encrypted_dek, new_record.key)
            plaintext = crypto.decrypt_with_dek(row.encrypted_value, dek)
            assert plaintext.startswith(b"test-value-")

    async def test_rotate_clears_subkey_cache(
        self, session: AsyncSession
    ) -> None:
        """After rotation, the subkey cache should be cleared."""
        eid, old_kid, old_key = await _insert_active_key(session)
        await session.commit()  # commit so rotate can begin its own transaction

        # Fill the cache
        subkey1 = _derive_master_subkey_cached(old_key)
        subkey2 = _derive_master_subkey_cached(old_key)
        assert subkey1 == subkey2  # cache hit

        await rotate_master_key(session)

        # Cache should be cleared; new call re-computes
        info = _derive_master_subkey_cached.cache_info()
        assert info.currsize <= 1  # Only new master key in cache


# ---------------------------------------------------------------------------
# Subkey cache tests (line 261)
# ---------------------------------------------------------------------------


class TestSubkeyCache:
    def test_invalidate_subkey_cache_clears_lru(self) -> None:
        """_invalidate_subkey_cache clears the lru_cache."""
        key1 = generate_master_key()

        # Fill cache with key1
        result1 = _derive_master_subkey_cached(key1)
        result1_hit = _derive_master_subkey_cached(key1)
        assert result1 == result1_hit

        info_before = _derive_master_subkey_cached.cache_info()
        assert info_before.hits >= 1
        assert info_before.currsize >= 1

        # Invalidate and verify cleared
        _invalidate_subkey_cache()
        info_after = _derive_master_subkey_cached.cache_info()
        assert info_after.currsize == 0

    def test_cache_hit_on_same_key(self) -> None:
        """Verify lru_cache returns cached value for same key."""
        key = generate_master_key()
        r1 = _derive_master_subkey_cached(key)

        info_before = _derive_master_subkey_cached.cache_info()
        r2 = _derive_master_subkey_cached(key)
        info_after = _derive_master_subkey_cached.cache_info()

        assert r1 == r2
        assert info_after.hits == info_before.hits + 1

    def test_cache_supports_two_keys(self) -> None:
        """lru_cache(maxsize=2) can hold two different keys."""
        key1 = generate_master_key()
        key2 = generate_master_key()

        r1 = _derive_master_subkey_cached(key1)
        r2 = _derive_master_subkey_cached(key2)
        r1_again = _derive_master_subkey_cached(key1)
        r2_again = _derive_master_subkey_cached(key2)

        assert r1 == r1_again
        assert r2 == r2_again
