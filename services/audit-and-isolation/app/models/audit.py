"""SQLAlchemy 2.0 ORM models for the chatbiz-audit-and-isolation service.

The schema is the canonical per-column declaration for the
``implement-audit-and-isolation`` change. Authoritative sources:

* Per-column lists and constraints live in the change spec
  ``openspec/changes/implement-audit-and-isolation/specs/audit-and-isolation/spec.md``
  §数据库 schema (audit_log + model_routing Requirement blocks).
* The model-level per-column definitions are spelled out in
  ``openspec/changes/implement-audit-and-isolation/plan.md`` Task 2.4.
* The design rationale (Metadata-Only audit, no prompt body, 16-byte
  hash of messages) is in the eng-review report finding #1 — see
  ``~/.gstack/projects/paulplay-pm-ChatBiz/paulwang-main-design-20260609-230548.md``.

Two tables:

* ``audit_log``      — append-only Metadata-Only audit log (no prompt body).
* ``model_routing``  — per-model upstream routing + enabled kill switch.

Only this module is responsible for the schema; migrations in
``alembic/versions/`` consume the same ``Base.metadata``.

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

Security note: the original prompt body MUST NOT be stored. Only the
SHA-256 hex digest is persisted (``prompt_hash CHAR(64)``), alongside
the count + type-tag list of PII redactions performed.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    DateTime,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Declarative base for every model in the audit-and-isolation service.

    A single ``Base`` keeps ``Base.metadata`` (the autogenerate target for
    Alembic) consistent across both ``AuditLog`` and ``ModelRouting``.
    """


# ---------------------------------------------------------------------------
# audit_log
# ---------------------------------------------------------------------------


class AuditLog(Base):
    """Append-only Metadata-Only audit log row.

    The original prompt body is NEVER persisted — only its SHA-256
    hex digest. PII redactions are recorded as a count plus a tag list;
    the placeholder→original map is held in Redis with a per-trace TTL
    and never reaches the database.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    workflow_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    model_kind: Mapped[str] = mapped_column(Text, nullable=False)
    bypass_isolation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    pii_detected_types: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list
    )
    pii_redacted_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    # CHAR(64) stores exactly 64 hex characters; matches the SHA-256 hex
    # digest the gateway computes over the canonicalised messages list.
    prompt_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    token_input: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_output: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    upstream_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_class: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ---------------------------------------------------------------------------
# model_routing
# ---------------------------------------------------------------------------


class ModelRouting(Base):
    """Routing row: maps a model name to an upstream provider.

    ``enabled`` is the per-row kill switch (the runtime's routing table
    loader filters on this flag at startup, then hot-updates via Redis).
    """

    __tablename__ = "model_routing"

    model_name: Mapped[str] = mapped_column(Text, primary_key=True)
    model_kind: Mapped[str] = mapped_column(Text, nullable=False)
    upstream_base_url: Mapped[str] = mapped_column(Text, nullable=False)
    upstream_path: Mapped[str] = mapped_column(
        Text, nullable=False, default="/v1/chat/completions"
    )
    timeout_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=30000)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


__all__ = ["AuditLog", "Base", "ModelRouting"]
