"""create model_routing table

Revision ID: 002_create_model_routing
Revises: 001_create_audit_log
Create Date: 2026-06-10 00:00:00.000000

Routing table for every LLM the gateway is allowed to proxy. Each row
maps a ``model_name`` (the value the caller passes in the OpenAI-style
``model`` field) to the upstream provider's base URL + path.

The runtime caches the enabled rows in Redis + in-memory at startup
(see ``app.routing.table.load_routing_into_cache``); the ``enabled``
flag is the per-row kill switch.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_create_model_routing"
down_revision: str | None = "001_create_audit_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE model_routing (
            model_name TEXT PRIMARY KEY,
            model_kind TEXT NOT NULL,
            upstream_base_url TEXT NOT NULL,
            upstream_path TEXT NOT NULL DEFAULT '/v1/chat/completions',
            timeout_ms INT NOT NULL DEFAULT 30000,
            enabled BOOLEAN NOT NULL DEFAULT true,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.drop_table("model_routing")
