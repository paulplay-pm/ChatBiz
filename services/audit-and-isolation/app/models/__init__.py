"""SQLAlchemy 2.0 ORM models for the audit-and-isolation service.

This package re-exports the declarative ``Base`` and the two tables the
service owns. Authoritative sources:

* Per-column lists and constraints live in the change spec
  ``openspec/changes/implement-audit-and-isolation/specs/audit-and-isolation/spec.md``
  (the audit_log + model_routing Requirement blocks).
* The DDL that defines the *exact* storage shape is in
  ``alembic/versions/001_create_audit_log.py`` and
  ``alembic/versions/002_create_model_routing.py``.

Two tables:

* ``audit_log``      — append-only Metadata-Only audit log (no prompt body).
* ``model_routing``  — per-model upstream routing + enabled kill switch.

We keep both classes in a single module (``audit.py``) because they are
the only models the service ships in Phase 1, and the file is small
enough to navigate as a unit. Splitting them across modules is a one-line
refactor when a third table arrives.
"""

from __future__ import annotations

from app.models.audit import AuditLog, Base, ModelRouting

__all__ = ["AuditLog", "Base", "ModelRouting"]
