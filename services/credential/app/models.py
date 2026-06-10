"""SQLAlchemy 2.0 ORM models for the credential-management service.

The schema is the canonical per-column declaration for the
``implement-credential-management`` change. Authoritative sources:

* Per-column lists and constraints live in the change spec
  ``openspec/changes/implement-credential-management/specs/credential-management/spec.md``
  §数据库 schema (3 Requirement → Scenario blocks, one per table).
* The model-level per-column definitions are spelled out in
  ``openspec/changes/implement-credential-management/plan.md`` Task 2.
* The design rationale (3-table split, envelope encryption, audit-only
  hash of credential id) is in
  ``openspec/changes/implement-credential-management/design.md`` §D12.

Three tables:

* ``credentials``      — the vault of encrypted credential values.
* ``encryption_keys``  — envelope-encryption master key registry.
* ``credential_audit`` — append-only access log (hashed credential id).

Only this module is responsible for the schema; migrations in
``alembic/versions/`` consume the same ``Base.metadata``.

Note on column declaration style: we deliberately use the explicit
``mapped_column(...)`` form for every column rather than the
``Annotated[T, mapped_column(...)]`` alias form. The alias form is more
concise, but the Index resolution inside ``__table_args__`` runs at class
body evaluation time and resolves column names against the columns that
are visible on the *parent class* — which at that moment excludes any
columns whose ``mapped_column`` only ships via an ``Annotated`` alias on a
sibling class. Keeping every column on an explicit ``mapped_column(...)``
call sidesteps that quirk and keeps the migration's CREATE TABLE DDL
trivially diff-able against the model.
"""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Index,
    LargeBinary,
    String,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Declarative base for every ORM model in this service.

    ``type_annotation_map`` keeps the Postgres column types co-located with
    their Python annotations, so the rest of the file can stay terse and
    declarative.
    """

    type_annotation_map = {
        # ``LargeBinary`` maps to ``BYTEA`` in PostgreSQL and is the column
        # type for every encrypted-blob column in this schema.
        bytes: LargeBinary,
        # Postgres native ``UUID`` is preferred over ``CHAR(36)`` for storage
        # and indexing efficiency. We use the ``UUID`` generic type at the
        # application level so the same column type works for tests against
        # SQLite (testcontainers always uses Postgres here, but this keeps
        # the import surface clean).
        UUID: PG_UUID(as_uuid=True),
    }


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CredentialType(str, enum.Enum):
    """The 4 credential categories supported by the service.

    Values match the strings the API surface expects; keep them stable —
    they are persisted in the database and the audit log filters on them.
    """

    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    DATABASE = "database"
    SMTP = "smtp"


class KeyStatus(str, enum.Enum):
    """Lifecycle status of an ``EncryptionKey`` row.

    At any moment there SHOULD be at most one ``ACTIVE`` row, but the
    schema does not enforce that — Task 6 (master key bootstrap) will add a
    partial unique index when the rotation flow is implemented.
    """

    ACTIVE = "active"
    RETIRED = "retired"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Credential(Base):
    """An encrypted credential entry in the vault.

    The plaintext value NEVER lands on this row: only the AES-256-GCM
    ciphertext (``encrypted_value``) and the per-credential DEK encrypted
    under the active master key (``encrypted_dek``) are stored.

    During the 30-day rotation window the previous value is kept in the
    ``previous_*`` columns; the cron job in Task 7 physically nulls them
    once ``previous_expires_at`` is in the past.
    """

    __tablename__ = "credentials"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    # ID format: ``cred_<base62>`` (16-24 chars). Stored as ``String(32)`` so
    # the prefix + a base62 random suffix comfortably fit.

    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[CredentialType] = mapped_column(
        SAEnum(CredentialType, name="credential_type", native_enum=False, length=16),
        nullable=False,
    )

    encrypted_value: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encrypted_dek: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    # Previous-value window (rotation): nullable; set on rotation, cleared
    # by the cleanup cron once ``previous_expires_at`` is in the past.
    previous_value: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    previous_encrypted_dek: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    previous_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    workspace_id: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        # Listing by tenant + filter by type (the listing endpoint accepts
        # ``type=`` as a filter; the index covers the (workspace_id, type)
        # predicate and the implicit ORDER BY created_at DESC, but we keep
        # the index minimal per spec §schema).
        Index("ix_credentials_workspace_id_type", "workspace_id", "type"),
        # The expiration cron / alert job scans ``expires_at`` to find rows
        # approaching expiry. The index is a single-column btree, which is
        # what PostgreSQL needs for ``WHERE expires_at < now()``.
        Index("ix_credentials_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return f"<Credential id={self.id!r} name={self.name!r} type={self.type!r}>"


class EncryptionKey(Base):
    """Registry of master keys used for envelope encryption.

    The active row's ``encrypted_key`` is the AES-256 master key wrapped
    under the platform's KMS-root key. Loading the active row into process
    memory is the responsibility of the service bootstrap (Task 6).
    """

    __tablename__ = "encryption_keys"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, unique=True)
    encrypted_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    status: Mapped[KeyStatus] = mapped_column(
        SAEnum(KeyStatus, name="key_status", native_enum=False, length=16),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # ``status`` index supports the bootstrap-time "find the active
        # master key" lookup, plus the "list retired keys" admin view.
        Index("ix_encryption_keys_status", "status"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return f"<EncryptionKey key_id={self.key_id!r} status={self.status!r}>"


class CredentialAudit(Base):
    """Append-only access log.

    ``credential_id_hash`` is the first 8 bytes of the SHA-256 of the
    plaintext credential id (e.g. ``cred_abc123``) — enough to correlate
    audit events for a single credential without storing the id itself
    in a table that may be replicated to a less-trusted environment.

    The plaintext credential id is NOT stored here: only its hash.
    """

    __tablename__ = "credential_audit"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(64))

    # 8 bytes from SHA-256(credential_id). Stored as ``LargeBinary(8)`` —
    # SQLAlchemy maps ``LargeBinary`` to ``BYTEA``, and the migration
    # narrows the length to 8 explicitly.
    credential_id_hash: Mapped[bytes] = mapped_column(LargeBinary(length=8), nullable=False)

    action: Mapped[str] = mapped_column(String(32))
    cap: Mapped[str | None] = mapped_column(String(255), nullable=True)
    purpose: Mapped[str | None] = mapped_column(String(255), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)

    __table_args__ = (
        # The migration in 0001 only creates the (timestamp) index; the
        # composite indexes below are added in 0002_audit_indexes.
        Index("ix_credential_audit_timestamp", "timestamp"),
        Index(
            "ix_credential_audit_credential_id_hash_timestamp",
            "credential_id_hash",
            "timestamp",
        ),
        Index("ix_credential_audit_user_id_timestamp", "user_id", "timestamp"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return (
            f"<CredentialAudit id={self.id} action={self.action!r} "
            f"user_id={self.user_id!r} success={self.success}>"
        )


__all__ = [
    "Base",
    "Credential",
    "CredentialAudit",
    "CredentialType",
    "EncryptionKey",
    "KeyStatus",
]
