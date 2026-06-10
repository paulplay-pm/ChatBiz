"""Declarative base for every model in the workflow-engine service.

A single ``Base`` keeps ``Base.metadata`` (the autogenerate target for
Alembic) consistent across ``WorkflowDefinition``, ``WorkflowRun``,
``NodeEvent`` and ``Approval``.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
