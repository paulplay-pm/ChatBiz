"""create workflow_definition table

Revision ID: 001_workflow_definition
Revises:
Create Date: 2026-06-10 00:00:00.000000

Versioned workflow DAG definition. The ``(id, version)`` composite
primary key makes each edit a new version row — older versions are
never mutated, only the ``archived`` flag flips. The full DAG lives
in ``definition_json`` (JSONB) and is parsed by the workflow engine
at run time. The schema is the source of truth for the
``implement-workflow-engine`` change spec; the ORM in
``app/models/workflow.py`` (WorkflowDefinition) must stay in lockstep
with this DDL.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_workflow_definition"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_definition",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("definition_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", "version", name="pk_workflow_definition"),
    )
    op.create_index(
        "ix_wf_def_id_version",
        "workflow_definition",
        ["id", "version"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_wf_def_id_version", table_name="workflow_definition")
    op.drop_table("workflow_definition")
