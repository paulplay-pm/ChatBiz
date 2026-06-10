"""SQLAlchemy 2.0 ORM models for the workflow-engine service.

Four tables implement the ``workflow-state-storage`` spec:

* ``workflow_definition`` — versioned workflow DAG (immutable per
  ``(id, version)`` row; new edits produce a new version).
* ``workflow_run``        — a single execution of a workflow definition
  by a user. Source of truth for run status, started_by, error class.
* ``node_event``          — append-only per-node execution log row.
  Captures input/output JSON, retry count, error class.
* ``approval``            — human-approval rows; one row per pending or
  completed approval attached to a run. The 24h default timeout
  documented in the eng-review decision #6 lives in the worker, not the
  schema.

Note on column declaration style: we deliberately use the explicit
``mapped_column(...)`` form for every column rather than the
``Annotated[T, mapped_column(...)]`` alias form. The alias form is more
concise, but the Index resolution inside ``__table_args__`` runs at
class body evaluation time and resolves column names against the columns
that are visible on the *parent class* — which at that moment excludes
any columns whose ``mapped_column`` only ships via an ``Annotated``
alias on a sibling class. Keeping every column on an explicit
``mapped_column(...)`` call sidesteps that quirk and keeps the
migration's CREATE TABLE DDL trivially diff-able against the model.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


# ---------------------------------------------------------------------------
# workflow_definition
# ---------------------------------------------------------------------------


class WorkflowDefinition(Base):
    """Versioned workflow DAG definition.

    The ``(id, version)`` composite primary key makes each edit a new
    version row — older versions are never mutated, only the
    ``archived`` flag flips. The full DAG lives in ``definition_json``
    (JSONB) and is parsed by the workflow engine at run time.
    """

    __tablename__ = "workflow_definition"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    definition_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (Index("ix_wf_def_id_version", "id", "version"),)


# ---------------------------------------------------------------------------
# workflow_run
# ---------------------------------------------------------------------------


class WorkflowRun(Base):
    """A single execution of a workflow definition.

    ``run_id`` is the LangGraph ``thread_id`` plus a server-generated
    UUID; the runtime uses ``thread_id`` as the cross-call handle and
    the workflow-engine service writes one row per execution.
    """

    __tablename__ = "workflow_run"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    workflow_version: Mapped[int] = mapped_column(Integer, nullable=False)
    thread_id: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    started_by: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(default=None)
    error_class: Mapped[str | None] = mapped_column(default=None)
    error_message: Mapped[str | None] = mapped_column(default=None)

    __table_args__ = (
        Index("ix_wf_run_workflow_started", "workflow_id", "started_at"),
        Index("ix_wf_run_thread", "thread_id"),
    )


# ---------------------------------------------------------------------------
# node_event
# ---------------------------------------------------------------------------


class NodeEvent(Base):
    """Append-only per-node execution log row.

    One row per node execution (including retries — ``retry_count`` ticks
    up). Foreign-keyed to ``workflow_run`` with ``ON DELETE CASCADE`` so
    dropping a run also drops its node history.
    """

    __tablename__ = "node_event"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_run.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    node_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    input_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    output_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    ended_at: Mapped[datetime | None] = mapped_column(default=None)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_class: Mapped[str | None] = mapped_column(default=None)
    error_message: Mapped[str | None] = mapped_column(default=None)

    __table_args__ = (Index("ix_node_event_run_started", "run_id", "started_at"),)


# ---------------------------------------------------------------------------
# approval
# ---------------------------------------------------------------------------


class Approval(Base):
    """Human-approval row.

    One row per pending or resolved approval attached to a run. The
    approver's UI polls (or is pushed to via WebSocket) using the
    ``(approver_user_id, status, created_at)`` index. ``status`` is
    ``pending`` until ``responded_at`` is set; the worker enforces a
    24h default timeout and flips the row to ``expired``.
    """

    __tablename__ = "approval"

    approval_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_run.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    node_id: Mapped[str] = mapped_column(Text, nullable=False)
    approver_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    responded_at: Mapped[datetime | None] = mapped_column(default=None)
    response_payload: Mapped[dict | None] = mapped_column(JSON, default=None)

    __table_args__ = (
        Index(
            "ix_approval_approver_status_created",
            "approver_user_id",
            "status",
            "created_at",
        ),
    )


__all__ = ["Approval", "NodeEvent", "WorkflowDefinition", "WorkflowRun"]
