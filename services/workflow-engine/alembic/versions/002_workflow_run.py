"""create workflow_run table

Revision ID: 002_workflow_run
Revises: 001_workflow_definition
Create Date: 2026-06-10 00:00:00.000000

A single execution of a workflow definition. ``run_id`` is the
LangGraph ``thread_id`` plus a server-generated UUID; the runtime
uses ``thread_id`` as the cross-call handle and the workflow-engine
service writes one row per execution. The schema is the source of
truth for the ``implement-workflow-engine`` change spec; the ORM in
``app/models/workflow.py`` (WorkflowRun) must stay in lockstep with
this DDL.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002_workflow_run"
down_revision: str | None = "001_workflow_definition"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_run",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_version", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("started_by", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("error_class", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("run_id", name="pk_workflow_run"),
    )
    op.create_index(
        "ix_wf_run_workflow_started",
        "workflow_run",
        ["workflow_id", "started_at"],
        unique=False,
    )
    op.create_index(
        "ix_wf_run_thread",
        "workflow_run",
        ["thread_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_wf_run_thread", table_name="workflow_run")
    op.drop_index("ix_wf_run_workflow_started", table_name="workflow_run")
    op.drop_table("workflow_run")
