"""create approval table

Revision ID: 004_approval
Revises: 003_node_event
Create Date: 2026-06-10 00:00:00.000000

Human-approval row. One row per pending or resolved approval attached
to a run. The approver's UI polls (or is pushed to via WebSocket)
using the ``(approver_user_id, status, created_at)`` index. ``status``
is ``pending`` until ``responded_at`` is set; the worker enforces a
24h default timeout and flips the row to ``expired``. The schema is
the source of truth for the ``implement-workflow-engine`` change spec;
the ORM in ``app/models/workflow.py`` (Approval) must stay in lockstep
with this DDL.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "004_approval"
down_revision: str | None = "003_node_event"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "approval",
        sa.Column("approval_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("node_id", sa.Text(), nullable=False),
        sa.Column("approver_user_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["workflow_run.run_id"],
            name="fk_approval_run_id_workflow_run",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("approval_id", name="pk_approval"),
    )
    op.create_index(
        "ix_approval_approver_status_created",
        "approval",
        ["approver_user_id", "status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_approval_approver_status_created", table_name="approval")
    op.drop_table("approval")
