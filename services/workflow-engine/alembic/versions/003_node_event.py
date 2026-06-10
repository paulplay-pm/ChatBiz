"""create node_event table

Revision ID: 003_node_event
Revises: 002_workflow_run
Create Date: 2026-06-10 00:00:00.000000

Append-only per-node execution log. One row per node execution
(including retries — ``retry_count`` ticks up). Foreign-keyed to
``workflow_run`` with ``ON DELETE CASCADE`` so dropping a run also
drops its node history. The schema is the source of truth for the
``implement-workflow-engine`` change spec; the ORM in
``app/models/workflow.py`` (NodeEvent) must stay in lockstep with
this DDL.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003_node_event"
down_revision: str | None = "002_workflow_run"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "node_event",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("node_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("input_json", sa.JSON(), nullable=True),
        sa.Column("output_json", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("error_class", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["workflow_run.run_id"],
            name="fk_node_event_run_id_workflow_run",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_node_event"),
    )
    op.create_index(
        "ix_node_event_run_started",
        "node_event",
        ["run_id", "started_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_node_event_run_started", table_name="node_event")
    op.drop_table("node_event")
