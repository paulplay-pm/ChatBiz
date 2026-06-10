"""create audit_log table

Revision ID: 001_create_audit_log
Revises:
Create Date: 2026-06-10 00:00:00.000000

Metadata-Only audit table for every LLM call proxied through the
audit-and-isolation gateway. Schema is the source of truth for the
``implement-audit-and-isolation`` change spec; the ORM in
``app/models/audit.py`` (AuditLog) must stay in lockstep with this DDL.

Security note: the original prompt body MUST NOT be stored. Only the
SHA-256 hex digest is persisted (``prompt_hash CHAR(64)``), alongside
the count + type-tag list of PII redactions performed.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_create_audit_log"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE audit_log (
            id BIGSERIAL PRIMARY KEY,
            trace_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            workflow_id TEXT,
            model TEXT NOT NULL,
            model_kind TEXT NOT NULL,
            bypass_isolation BOOLEAN NOT NULL DEFAULT false,
            pii_detected_types TEXT[] NOT NULL DEFAULT '{}',
            pii_redacted_count INT NOT NULL DEFAULT 0,
            prompt_hash CHAR(64) NOT NULL,
            token_input INT,
            token_output INT,
            latency_ms INT NOT NULL,
            upstream_status INT,
            error_class TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.create_index("idx_audit_trace", "audit_log", ["trace_id"])
    op.create_index(
        "idx_audit_user_time", "audit_log", ["user_id", "created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("idx_audit_user_time", table_name="audit_log")
    op.drop_index("idx_audit_trace", table_name="audit_log")
    op.drop_table("audit_log")
