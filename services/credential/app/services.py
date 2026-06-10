"""Business service layer for the credential-management service.

The HTTP layer (Task 5) translates incoming requests into calls on a
``CredentialService`` instance, which owns:

* CRUD on the ``credentials`` table.
* Envelope encryption via the ``app.crypto`` primitives from Task 3.
* The rotation 双值窗口 (30-day previous-value fallback).
* Audit-log writes on every mutation / use / reveal.

The service is intentionally HTTP-agnostic: no ``Request`` / ``Response``
objects flow in or out, only the Pydantic DTOs from ``app.schemas``. This
keeps the layer testable without spinning up FastAPI.

Storage layout for type-specific metadata
-----------------------------------------
The schema in Task 2 stores ``encrypted_value`` as a single BYTEA column.
For credentials with type-specific metadata (oauth2 client_id, database
host, smtp username, ...) we encode the metadata + the secret value
into a single JSON document **before** encryption:

    {"value": "<plaintext-secret>", "client_id": "...", ...}

The fields are recovered on ``use`` / ``reveal``. This keeps the schema
flat (1 BYTEA column instead of N nullable plaintext columns) and
keeps every byte of metadata inside the AES-256-GCM envelope.

Audit log
---------
Every method that mutates state or returns plaintext writes a row to
``credential_audit`` via the ``_audit`` helper. The helper is a
placeholder for Task 5: it builds the row and inserts it into the same
session as the operation, but does NOT yet POST to the central
``audit-and-isolation`` cap webhook. That wiring lands in Task 5 when
the HTTP layer is added.
"""

from __future__ import annotations

import json
import secrets
import string
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import delete, select
from sqlalchemy import func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app import crypto
from app.audit import write_audit as _write_audit
from app.models import Credential, CredentialType
from app.schemas import (
    CredentialCreateRequest,
    CredentialDetailResponse,
    CredentialListResponse,
    CredentialResponse,
    CredentialRevealResponse,
    CredentialRotateRequest,
    CredentialUseRequest,
    CredentialUseResponse,
    validate_page,
    validate_page_size,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Length of the random suffix after the ``cred_`` prefix. Base62 × 27 →
#: ~160 bits of entropy. ``cred_`` (5) + 27 = 32, which fits the
#: ``String(32)`` column in ``models.py``.
_ID_SUFFIX_LEN: Final = 27
_BASE62_ALPHABET: Final = string.ascii_letters + string.digits

#: 30 days of previous-value fallback per spec §凭证轮换双值窗口期.
PREVIOUS_VALUE_TTL: Final = timedelta(days=30)

#: Audit action strings — kept as constants so callers (and tests) don't
#: hand-type magic strings that drift.
ACTION_CREATE: Final = "create"
ACTION_LIST: Final = "list"
ACTION_READ: Final = "read"
ACTION_ROTATE: Final = "rotate"
ACTION_DELETE: Final = "delete"
ACTION_USE: Final = "use"
ACTION_REVEAL: Final = "reveal"


# ---------------------------------------------------------------------------
# Exceptions (domain-level; HTTP layer maps these to status codes)
# ---------------------------------------------------------------------------


class CredentialServiceError(Exception):
    """Base class for all errors raised by ``CredentialService``."""


class CredentialNotFoundError(CredentialServiceError):
    """Raised when a credential id does not exist."""


class WorkspaceMismatchError(CredentialServiceError):
    """Raised when a credential exists but belongs to a different workspace."""


class CredentialExpiredError(CredentialServiceError):
    """Raised when ``use`` / ``reveal`` is called on an expired credential."""


# ---------------------------------------------------------------------------
# ID + hash helpers
# ---------------------------------------------------------------------------


def _generate_credential_id() -> str:
    """Return a fresh ``cred_<base62 * 32>`` id.

    Uses ``secrets`` for CSPRNG; the prefix is a static ``cred_`` so the
    id is human-recognisable in logs without leaking the underlying
    secret.
    """
    suffix = "".join(secrets.choice(_BASE62_ALPHABET) for _ in range(_ID_SUFFIX_LEN))
    return f"cred_{suffix}"


# ---------------------------------------------------------------------------
# Type-specific metadata encoding
# ---------------------------------------------------------------------------


def _encode_payload(req: CredentialCreateRequest) -> bytes:
    """Pack value + type-specific metadata into a JSON blob for encryption.

    All credentials encode at least ``{"value": ...}``; oauth2 / database
    / smtp also embed their per-type fields. The bytes returned here are
    fed to ``crypto.encrypt_with_dek``.
    """
    payload: dict[str, str | int] = {"value": req.value.get_secret_value()}
    if req.type is CredentialType.OAUTH2:
        # ``client_secret`` and ``token_url`` aren't None for oauth2 — the
        # model validator in ``CredentialCreateRequest`` already enforced
        # all-or-nothing. Cast through ``assert`` so mypy --strict knows.
        assert req.client_id is not None
        assert req.client_secret is not None
        assert req.token_url is not None
        assert req.scope is not None
        payload["client_id"] = req.client_id
        payload["client_secret"] = req.client_secret.get_secret_value()
        payload["token_url"] = str(req.token_url)
        payload["scope"] = req.scope
    elif req.type is CredentialType.DATABASE:
        assert req.host is not None
        assert req.port is not None
        assert req.db_name is not None
        payload["host"] = req.host
        payload["port"] = req.port
        payload["db_name"] = req.db_name
    elif req.type is CredentialType.SMTP:
        assert req.host is not None
        assert req.port is not None
        assert req.username is not None
        payload["host"] = req.host
        payload["port"] = req.port
        payload["username"] = req.username
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _decode_payload(blob: bytes) -> dict[str, str | int]:
    """Inverse of ``_encode_payload``; returns the full payload dict."""
    result: dict[str, str | int] = json.loads(blob.decode("utf-8"))
    return result


# ---------------------------------------------------------------------------
# Masking helper (test-importable)
# ---------------------------------------------------------------------------


def mask_value(value: str) -> str:
    """Return ``<first 4>★★★★<last 4>`` or ``★★★★`` for short values.

    The 8-char threshold is from the plan spec: any value < 8 chars
    becomes ``★★★★`` to avoid leaking the entire secret when prefix +
    suffix already cover it.
    """
    if len(value) < 8:
        return "★★★★"
    return f"{value[:4]}★★★★{value[-4:]}"


# ---------------------------------------------------------------------------
# CredentialService
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _DecodedCredential:
    """Internal DTO used to pass decoded payloads between methods."""

    payload: dict[str, str | int]
    used_previous: bool


class CredentialService:
    """Business service layer for credential CRUD + envelope encryption.

    A new instance is constructed per request by the HTTP layer (Task 5);
    it holds the open ``AsyncSession`` and the in-memory master key so
    callers don't have to thread either through every method.
    """

    def __init__(self, session: AsyncSession, master_key: bytes) -> None:
        self._session = session
        self._master_key = master_key

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create(
        self, req: CredentialCreateRequest, user_id: str
    ) -> CredentialResponse:
        """Create a new credential row + write the create audit event."""
        cred_id = _generate_credential_id()
        dek = crypto.generate_dek()
        plaintext = _encode_payload(req)
        encrypted_value = crypto.encrypt_with_dek(plaintext, dek)
        encrypted_dek = crypto.encrypt_dek_with_master(dek, self._master_key)

        row = Credential(
            id=cred_id,
            name=req.name,
            type=req.type,
            encrypted_value=encrypted_value,
            encrypted_dek=encrypted_dek,
            workspace_id=req.workspace_id,
            expires_at=req.expires_at,
        )
        self._session.add(row)
        await self._session.flush()
        await self._audit(
            credential_id=cred_id,
            user_id=user_id,
            action=ACTION_CREATE,
            success=True,
        )
        return _to_response(row)

    async def list(
        self,
        workspace_id: str,
        type: CredentialType | None,
        page: int,
        page_size: int,
    ) -> CredentialListResponse:
        """Workspace-scoped, paginated list."""
        validate_page(page)
        validate_page_size(page_size)

        stmt = select(Credential).where(Credential.workspace_id == workspace_id)
        if type is not None:
            stmt = stmt.where(Credential.type == type)

        count_stmt = select(sa_func.count()).select_from(stmt.subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()

        ordered = stmt.order_by(Credential.created_at.desc()).limit(page_size).offset(
            (page - 1) * page_size
        )
        rows = (await self._session.execute(ordered)).scalars().all()
        return CredentialListResponse(
            items=[_to_response(r) for r in rows],
            total_count=int(total),
            page=page,
            page_size=page_size,
        )

    async def get(
        self, credential_id: str, workspace_id: str
    ) -> CredentialDetailResponse:
        """Single-credential read with masked value."""
        row = await self._load_row(credential_id, workspace_id)
        # Decrypt to compute the masked value. We only mask the
        # ``value`` field; type-specific metadata is not echoed back
        # here (the response model has no field for it).
        decoded = self._decrypt_current(row)
        value = str(decoded.payload["value"])
        await self._audit(
            credential_id=credential_id,
            user_id="",  # HTTP layer fills this; read events are best-effort here.
            action=ACTION_READ,
            success=True,
        )
        return CredentialDetailResponse(
            id=row.id,
            name=row.name,
            type=row.type,
            workspace_id=row.workspace_id,
            expires_at=row.expires_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
            masked_value=mask_value(value),
        )

    async def rotate(
        self,
        credential_id: str,
        req: CredentialRotateRequest,
        user_id: str,
    ) -> CredentialResponse:
        """Rotate: move current → previous_*, write new current.

        The previous_*_at columns get ``now() + 30 days``. The whole
        update is a single session.flush() so it lands atomically inside
        the surrounding HTTP request's transaction (the HTTP layer in
        Task 5 wraps each request in ``async with session.begin()``).
        """
        # Workspace check happens at the HTTP layer (Task 5) before
        # rotate is called; we re-check here defensively when the caller
        # passes a workspace_id. The method signature in plan.md does
        # NOT include workspace_id, so we only fetch by id and trust
        # the HTTP layer's RBAC + workspace scoping. Audit-on-failure
        # still fires from ``_load_row``-equivalent below.
        row = await self._session.get(Credential, credential_id)
        if row is None:
            await self._audit(
                credential_id=credential_id,
                user_id=user_id,
                action=ACTION_ROTATE,
                success=False,
            )
            raise CredentialNotFoundError(f"credential {credential_id!r} not found")

        # Decrypt the current payload so we can preserve type-specific
        # metadata (oauth2 client_id, database host, ...). Rotation only
        # changes the secret ``value`` — never the metadata.
        current_dek = crypto.decrypt_dek_with_master(row.encrypted_dek, self._master_key)
        current_plaintext = crypto.decrypt_with_dek(row.encrypted_value, current_dek)
        current_payload = _decode_payload(current_plaintext)

        new_payload = dict(current_payload)
        new_payload["value"] = req.value.get_secret_value()
        new_plaintext = json.dumps(
            new_payload, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")

        new_dek = crypto.generate_dek()
        new_encrypted_value = crypto.encrypt_with_dek(new_plaintext, new_dek)
        new_encrypted_dek = crypto.encrypt_dek_with_master(new_dek, self._master_key)

        # Move current → previous_*; both columns get the existing
        # (already-encrypted) bytes, so we don't re-encrypt the old
        # value during rotation.
        row.previous_value = row.encrypted_value
        row.previous_encrypted_dek = row.encrypted_dek
        row.previous_expires_at = _utcnow() + PREVIOUS_VALUE_TTL

        row.encrypted_value = new_encrypted_value
        row.encrypted_dek = new_encrypted_dek
        if req.expires_at is not None:
            row.expires_at = req.expires_at

        await self._session.flush()
        # Refresh so the server-side ``updated_at`` (onupdate=func.now())
        # is loaded before we access it for the response DTO — without
        # this the attribute is in the "expired" state and the sync
        # access in ``_to_response`` would trigger a lazy load that
        # asyncpg can't satisfy outside an awaitable context.
        await self._session.refresh(row)
        await self._audit(
            credential_id=credential_id,
            user_id=user_id,
            action=ACTION_ROTATE,
            success=True,
        )
        return _to_response(row)

    async def delete(
        self, credential_id: str, workspace_id: str, user_id: str
    ) -> None:
        """Delete a credential. Idempotency: a missing row raises NotFound.

        We DELETE the row outright (no soft-delete) — audit-and-isolation
        keeps the history via the audit log. The ``credential_audit``
        rows are NOT cascade-deleted (the audit table is append-only
        and survives the credential).
        """
        row = await self._load_row(credential_id, workspace_id, action=ACTION_DELETE,
                                   user_id=user_id)
        await self._session.execute(
            delete(Credential).where(Credential.id == credential_id)
        )
        await self._session.flush()
        await self._audit(
            credential_id=credential_id,
            user_id=user_id,
            action=ACTION_DELETE,
            success=True,
        )
        # Reference ``row`` to silence the "unused local" warning — its
        # only purpose was the load-side audit.
        del row

    async def reveal(
        self, credential_id: str, user_id: str
    ) -> CredentialRevealResponse:
        """Return the plaintext value — admin-only at the HTTP layer."""
        row = await self._session.get(Credential, credential_id)
        if row is None:
            await self._audit(
                credential_id=credential_id,
                user_id=user_id,
                action=ACTION_REVEAL,
                success=False,
            )
            raise CredentialNotFoundError(f"credential {credential_id!r} not found")
        _check_not_expired(row)
        decoded = self._decrypt_current(row)
        value = str(decoded.payload["value"])
        await self._audit(
            credential_id=credential_id,
            user_id=user_id,
            action=ACTION_REVEAL,
            success=True,
        )
        return CredentialRevealResponse(value=value)

    async def use(
        self,
        credential_id: str,
        req: CredentialUseRequest,
        user_id: str,
        workspace_id: str,
    ) -> CredentialUseResponse:
        """Return plaintext to an internal cap.

        Tries the current ciphertext first; falls back to ``previous_*``
        if (a) current decryption fails AND (b) ``previous_expires_at >
        now()`` per spec §use API 优先用新值.
        """
        row = await self._load_row(
            credential_id, workspace_id, action=ACTION_USE, user_id=user_id,
            cap=req.cap, purpose=req.purpose,
        )
        _check_not_expired(row)
        decoded = self._decrypt_with_fallback(row)
        value = str(decoded.payload["value"])
        await self._audit(
            credential_id=credential_id,
            user_id=user_id,
            action=ACTION_USE,
            cap=req.cap,
            purpose=req.purpose,
            success=True,
        )
        return CredentialUseResponse(value=value)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _load_row(
        self,
        credential_id: str,
        workspace_id: str,
        *,
        action: str = ACTION_READ,
        user_id: str = "",
        cap: str | None = None,
        purpose: str | None = None,
    ) -> Credential:
        """Fetch a credential by id + workspace; audit on failure.

        Raises ``CredentialNotFoundError`` if the id is absent and
        ``WorkspaceMismatchError`` if the credential exists but is in
        another workspace.
        """
        row = await self._session.get(Credential, credential_id)
        if row is None:
            await self._audit(
                credential_id=credential_id,
                user_id=user_id,
                action=action,
                cap=cap,
                purpose=purpose,
                success=False,
            )
            raise CredentialNotFoundError(f"credential {credential_id!r} not found")
        if row.workspace_id != workspace_id:
            await self._audit(
                credential_id=credential_id,
                user_id=user_id,
                action=action,
                cap=cap,
                purpose=purpose,
                success=False,
            )
            raise WorkspaceMismatchError(
                f"credential {credential_id!r} not in workspace {workspace_id!r}"
            )
        return row

    def _decrypt_current(self, row: Credential) -> _DecodedCredential:
        """Decrypt the current value only — no previous-value fallback."""
        dek = crypto.decrypt_dek_with_master(row.encrypted_dek, self._master_key)
        plaintext = crypto.decrypt_with_dek(row.encrypted_value, dek)
        return _DecodedCredential(payload=_decode_payload(plaintext), used_previous=False)

    def _decrypt_with_fallback(self, row: Credential) -> _DecodedCredential:
        """Try current value; on failure inside the 30-day window, try previous.

        Spec §use API 优先用新值: "优先用新值解密;若新值有损坏(罕见),
        回退到 previous_* 旧值(若仍未过期)".
        """
        try:
            return self._decrypt_current(row)
        except (crypto.CryptoError, ValueError):
            if not _previous_value_available(row):
                raise
            # Below: previous_encrypted_dek + previous_value are non-None
            # because ``_previous_value_available`` only returns True if
            # all three columns are populated and previous_expires_at is
            # in the future. ``assert`` makes mypy --strict happy.
            assert row.previous_encrypted_dek is not None
            assert row.previous_value is not None
            prev_dek = crypto.decrypt_dek_with_master(
                row.previous_encrypted_dek, self._master_key
            )
            plaintext = crypto.decrypt_with_dek(row.previous_value, prev_dek)
            return _DecodedCredential(
                payload=_decode_payload(plaintext), used_previous=True
            )

    async def _audit(
        self,
        *,
        credential_id: str,
        user_id: str,
        action: str,
        success: bool,
        cap: str | None = None,
        purpose: str | None = None,
    ) -> None:
        """Write one row to ``credential_audit`` via :mod:`app.audit`.

        Thin wrapper kept for the in-service callsites; the HTTP layer
        in ``app.routers.credentials`` calls :func:`app.audit.write_audit`
        directly. Both paths land identical rows because they share the
        same writer module.
        """
        await _write_audit(
            self._session,
            user_id=user_id,
            credential_id=credential_id,
            action=action,
            success=success,
            cap=cap,
            purpose=purpose,
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    """Timezone-aware UTC ``datetime.now`` — keeps timezone semantics explicit."""
    return datetime.now(UTC)


def _check_not_expired(row: Credential) -> None:
    """Raise ``CredentialExpiredError`` if ``expires_at`` is in the past."""
    if row.expires_at is None:
        return
    if row.expires_at < _utcnow():
        raise CredentialExpiredError(
            f"credential {row.id!r} expired at {row.expires_at.isoformat()}"
        )


def _previous_value_available(row: Credential) -> bool:
    """Whether the previous-value fallback is populated and not expired."""
    if row.previous_value is None or row.previous_encrypted_dek is None:
        return False
    if row.previous_expires_at is None:
        return False
    return row.previous_expires_at > _utcnow()


def _to_response(row: Credential) -> CredentialResponse:
    """ORM row → slim DTO (no value)."""
    return CredentialResponse(
        id=row.id,
        name=row.name,
        type=row.type,
        workspace_id=row.workspace_id,
        expires_at=row.expires_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


__all__ = [
    "ACTION_CREATE",
    "ACTION_DELETE",
    "ACTION_LIST",
    "ACTION_READ",
    "ACTION_REVEAL",
    "ACTION_ROTATE",
    "ACTION_USE",
    "PREVIOUS_VALUE_TTL",
    "CredentialExpiredError",
    "CredentialNotFoundError",
    "CredentialService",
    "CredentialServiceError",
    "WorkspaceMismatchError",
    "mask_value",
]
