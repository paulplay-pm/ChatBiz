"""add composite audit-log indexes (credential_id_hash, timestamp) and (user_id, timestamp)

Revision ID: 0002_audit_indexes
Revises: 0001_initial
Create Date: 2026-06-10 00:00:00.000000

The ``credential_audit`` table is the hottest table in this service (per
``openspec/specs/credential-management/spec.md`` the audit log is estimated
at 780GB / 3 months). The two most common read patterns are:

* Find every audit event for a given credential in a time window:
    ``SELECT * FROM credential_audit
       WHERE credential_id_hash = :h AND timestamp BETWEEN :t1 AND :t2
       ORDER BY timestamp DESC``

* Find every audit event emitted by a given user in a time window:
    ``SELECT * FROM credential_audit
       WHERE user_id = :u AND timestamp BETWEEN :t1 AND :t2
       ORDER BY timestamp DESC``

Both queries benefit from a composite (col, timestamp) btree index —
the timestamp suffix lets the planner avoid a sort for the ORDER BY and
the composite prefix gives a tight range scan on the predicate. This
migration adds the two missing indexes called out in the change spec
§数据库 schema (see
``openspec/changes/implement-credential-management/specs/credential-management/spec.md``).
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_audit_indexes"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_credential_audit_credential_id_hash_timestamp",
        "credential_audit",
        ["credential_id_hash", "timestamp"],
        unique=False,
    )
    op.create_index(
        "ix_credential_audit_user_id_timestamp",
        "credential_audit",
        ["user_id", "timestamp"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_credential_audit_user_id_timestamp",
        table_name="credential_audit",
    )
    op.drop_index(
        "ix_credential_audit_credential_id_hash_timestamp",
        table_name="credential_audit",
    )
