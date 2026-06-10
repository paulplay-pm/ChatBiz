"""initial schema: credentials, encryption_keys, credential_audit

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-10 00:00:00.000000

This migration creates the three tables declared in the
``implement-credential-management`` change — see the change spec at
``openspec/changes/implement-credential-management/specs/credential-management/spec.md``
§数据库 schema (the 3 Requirement scenarios) and the per-column
definitions in ``openspec/changes/implement-credential-management/plan.md``
Task 2. Composite / lookup indexes that depend on multiple tables are
added in the follow-up migration ``0002_audit_indexes``.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # credentials
    # -------------------------------------------------------------------------
    op.create_table(
        "credentials",
        sa.Column("id", sa.String(length=32), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "api_key",
                "oauth2",
                "database",
                "smtp",
                name="credential_type",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("encrypted_value", sa.LargeBinary(), nullable=False),
        sa.Column("encrypted_dek", sa.LargeBinary(), nullable=False),
        sa.Column("previous_value", sa.LargeBinary(), nullable=True),
        sa.Column("previous_encrypted_dek", sa.LargeBinary(), nullable=True),
        sa.Column("previous_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # Per the change spec §数据库 schema, two indexes on the credentials table:
    #   * (workspace_id, type)  — list-and-filter by tenant
    #   * (expires_at)          — cron job for "approaching expiry" scan
    op.create_index(
        "ix_credentials_workspace_id_type",
        "credentials",
        ["workspace_id", "type"],
        unique=False,
    )
    op.create_index(
        "ix_credentials_expires_at",
        "credentials",
        ["expires_at"],
        unique=False,
    )

    # -------------------------------------------------------------------------
    # encryption_keys
    # -------------------------------------------------------------------------
    op.create_table(
        "encryption_keys",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("key_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("encrypted_key", sa.LargeBinary(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "retired",
                name="key_status",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_encryption_keys_status",
        "encryption_keys",
        ["status"],
        unique=False,
    )

    # -------------------------------------------------------------------------
    # credential_audit
    # -------------------------------------------------------------------------
    op.create_table(
        "credential_audit",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        # 8 bytes from SHA-256(credential_id) — exact length matters for the
        # spec's "8 字节 SHA256" requirement.
        sa.Column("credential_id_hash", sa.LargeBinary(length=8), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("cap", sa.String(length=255), nullable=True),
        sa.Column("purpose", sa.String(length=255), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
    )
    # Per the change spec §数据库 schema, an index on (timestamp) is created
    # The composite (credential_id_hash, timestamp) and (user_id, timestamp)
    # indexes are added in 0002_audit_indexes to keep the audit-log DDL
    # changes isolated from the table creation step.
    op.create_index(
        "ix_credential_audit_timestamp",
        "credential_audit",
        ["timestamp"],
        unique=False,
    )


def downgrade() -> None:
    # Drop in reverse order so the audit table (the most leaf-most) goes first.
    op.drop_index("ix_credential_audit_timestamp", table_name="credential_audit")
    op.drop_table("credential_audit")

    op.drop_index("ix_encryption_keys_status", table_name="encryption_keys")
    op.drop_table("encryption_keys")

    op.drop_index("ix_credentials_expires_at", table_name="credentials")
    op.drop_index("ix_credentials_workspace_id_type", table_name="credentials")
    op.drop_table("credentials")
