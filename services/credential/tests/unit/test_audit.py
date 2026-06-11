"""Unit tests for ``app.audit`` — hash + write_audit."""

from __future__ import annotations

from unittest.mock import AsyncMock, call

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import hash_credential_id, write_audit


class TestHashCredentialId:
    def test_deterministic(self) -> None:
        """Same input always produces same hash."""
        h1 = hash_credential_id("cred_abc123")
        h2 = hash_credential_id("cred_abc123")
        assert h1 == h2

    def test_different_inputs_produce_different_hashes(self) -> None:
        h1 = hash_credential_id("cred_aaa")
        h2 = hash_credential_id("cred_bbb")
        assert h1 != h2

    def test_output_is_8_bytes(self) -> None:
        h = hash_credential_id("cred_something")
        assert len(h) == 8
        assert isinstance(h, bytes)

    def test_output_is_stable_across_runs(self) -> None:
        """Pinned hash value so we catch any algorithm change."""
        h = hash_credential_id("cred_test_stable")
        # SHA-256 first 8 bytes — must be deterministic across Python versions.
        import hashlib
        expected = hashlib.sha256(b"cred_test_stable").digest()[:8]
        assert h == expected

    def test_hash_is_hex_encodable(self) -> None:
        """The hash must be representable as hex (for display in logs)."""
        h = hash_credential_id("cred_x")
        assert isinstance(h.hex(), str)
        assert len(h.hex()) == 16  # 8 bytes → 16 hex chars


class TestWriteAudit:
    @pytest.mark.asyncio
    async def test_write_audit_adds_and_flushes(self) -> None:
        """``write_audit`` calls session.add + session.flush."""
        session = AsyncMock(spec=AsyncSession)

        await write_audit(
            session,
            user_id="u-1",
            credential_id="cred_abc",
            action="read",
            success=True,
        )

        assert session.add.call_count == 1
        assert session.flush.call_count == 1
        # Verify the row added has the correct fields.
        row_arg = session.add.call_args[0][0]
        assert row_arg.user_id == "u-1"
        assert row_arg.action == "read"
        assert row_arg.success is True

    @pytest.mark.asyncio
    async def test_write_audit_with_cap_and_purpose(self) -> None:
        session = AsyncMock(spec=AsyncSession)

        await write_audit(
            session,
            user_id="u-2",
            credential_id="cred_xyz",
            action="use",
            success=True,
            cap="workflow-engine",
            purpose="monthly-report",
        )

        row_arg = session.add.call_args[0][0]
        assert row_arg.cap == "workflow-engine"
        assert row_arg.purpose == "monthly-report"

    @pytest.mark.asyncio
    async def test_write_audit_failure(self) -> None:
        session = AsyncMock(spec=AsyncSession)

        await write_audit(
            session,
            user_id="u-3",
            credential_id="cred_fail",
            action="rotate",
            success=False,
        )

        row_arg = session.add.call_args[0][0]
        assert row_arg.success is False
        assert row_arg.action == "rotate"
