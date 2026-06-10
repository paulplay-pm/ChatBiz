"""Audit-log writer for the credential-management service.

Every mutating operation (create / rotate / delete) and every plaintext
exposure (reveal / use) MUST land a row in the ``credential_audit``
table. Spec §凭证访问审计 enumerates the columns and forbids storing
the plaintext id — we hash it (SHA-256 → first 8 bytes) before write.

Design notes
------------
* The audit writer is async and accepts the **same** ``AsyncSession``
  that the surrounding HTTP request is using. The audit row therefore
  lives inside the same transaction as the operation it describes,
  which is what spec §凭证访问审计 means by "成功 / 失败都记": a
  rolled-back operation rolls back its audit row too, so the audit
  table never contains rows for operations that never happened.
* The 8-byte hash prefix is computed via ``hashlib.sha256`` per spec —
  using only the first 8 bytes keeps the column narrow (BYTEA(8)) and
  avoids reversing the credential id, while still providing enough
  collision resistance to disambiguate audit events for billions of
  credentials.
* This module is intentionally tiny and side-effect-free apart from
  the DB write. The external POST to the central audit-and-isolation
  cap webhook is deferred to a later task — the in-DB row is the
  source of truth.
"""

from __future__ import annotations

import hashlib

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CredentialAudit


def hash_credential_id(credential_id: str) -> bytes:
    """Return the first 8 bytes of ``sha256(credential_id)`` per spec.

    Exposed publicly so tests (and the cron job in Task 6) can compute
    the same hash without duplicating the algorithm.
    """
    return hashlib.sha256(credential_id.encode("utf-8")).digest()[:8]


async def write_audit(
    session: AsyncSession,
    *,
    user_id: str,
    credential_id: str,
    action: str,
    success: bool,
    cap: str | None = None,
    purpose: str | None = None,
) -> None:
    """Insert one row into ``credential_audit`` inside the caller's tx.

    The caller (``CredentialService`` for the in-process audit;
    ``routers.credentials`` for the HTTP-level audit) MUST flush /
    commit its own transaction; we only ``session.add`` + ``flush``
    here so the audit row's PK is materialised in case the caller
    wants to read it back in the same request.
    """
    row = CredentialAudit(
        user_id=user_id,
        credential_id_hash=hash_credential_id(credential_id),
        action=action,
        cap=cap,
        purpose=purpose,
        success=success,
    )
    session.add(row)
    await session.flush()


__all__ = ["hash_credential_id", "write_audit"]
