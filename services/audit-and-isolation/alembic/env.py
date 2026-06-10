"""Alembic environment for the chatbiz-audit-and-isolation service.

Async template: the connection is opened with ``create_async_engine`` and
then handed to Alembic via ``connection.run_sync(...)``. This lets us
reuse the same ``Base.metadata`` declared in ``app.models.audit`` for
autogenerate without paying the cost of an extra event-loop gymnastics
layer.

Database URL resolution order:

1. ``DATABASE_URL`` environment variable (set by docker-compose).
2. The ``sqlalchemy.url`` entry in ``alembic.ini`` (kept empty by design).

We deliberately do NOT call ``config.set_main_option`` with a hard-coded
DSN — the migration must work the same way locally, in CI and in the
production compose stack. The async engine in ``app.database`` reads
the *same* ``DATABASE_URL`` env var via ``get_settings()``; keeping the
two in sync is enforced by the production compose file, not by code.
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Import the metadata so ``autogenerate`` (and ``upgrade head``) can diff
# against the live ORM models. We import lazily inside a sys.path tweak so
# the migration works regardless of the CWD alembic is invoked from.
import sys
from pathlib import Path

# Ensure the service root is on sys.path so ``from app.models.audit``
# resolves when alembic is run as ``python -m alembic`` or via the
# ``alembic`` CLI from outside the service directory.
_SERVICE_ROOT = Path(__file__).resolve().parent.parent
if str(_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVICE_ROOT))

from app.models.audit import Base  # noqa: E402  (sys.path tweak above)

# ---------------------------------------------------------------------------
# Alembic config object — provides access to alembic.ini values.
# ---------------------------------------------------------------------------
config = context.config

# Configure Python logging from alembic.ini's [loggers] / [handlers] blocks
# (only when invoked by the ``alembic`` CLI, not in offline mode inside tests).
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Metadata target for ``autogenerate``.
# ---------------------------------------------------------------------------
target_metadata = Base.metadata


def _resolve_database_url() -> str:
    """Return the async DSN to use, from env or alembic.ini.

    Async drivers matter: this service uses ``asyncpg`` end-to-end, and
    Alembic's offline mode accepts a sync or async URL, but the online
    path below requires an async one. If a sync URL is provided (e.g. a
    developer sets ``DATABASE_URL=postgresql://...`` for psycopg2) we
    rewrite it to the asyncpg driver so this single env.py supports both.
    """
    url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set and sqlalchemy.url is empty; "
            "export DATABASE_URL or set it in alembic.ini before running alembic."
        )
    # ``postgresql+asyncpg://`` is what the runtime uses; normalise the bare
    # ``postgresql://`` form to asyncpg so the engine factory below works.
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to stdout, no connection).

    Useful for ``alembic upgrade head --sql`` style dry-runs.
    """
    context.configure(
        url=_resolve_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # ``compare_type=True`` is not strictly needed in offline mode, but
        # keeping it consistent with the online path makes the diff output
        # identical regardless of which mode generated it.
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    """Hand the (sync) connection back to Alembic and run the migrations.

    The async engine wraps a sync connection here, so we use the regular
    Alembic API. ``compare_type=True`` enables autogenerate to detect
    column type changes, which is what we want for any future schema diffs.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # ``compare_type=True`` detects column-type drift in autogenerate.
        # We intentionally leave ``compare_server_default=True`` OFF: the
        # ORM models set Python-level ``server_default=`` values (e.g.
        # ``func.now()`` for ``created_at``) that mirror the migration DDL,
        # and enabling server-default comparison produces noisy false
        # positives on every autogenerate run.
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode against an async engine.

    We create the engine from the resolved DSN, then ``run_sync`` to bridge
    into Alembic's sync API — this is the canonical pattern from
    https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio.
    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _resolve_database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
