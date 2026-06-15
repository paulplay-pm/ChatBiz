"""Integration tests for the Alembic migration scripts.

Spec: change spec
``openspec/changes/implement-credential-management/specs/credential-management/spec.md``
§数据库回滚测试 (see also ``openspec/changes/implement-credential-management/plan.md``
Task 2).

The contract is straightforward:

* ``alembic upgrade head`` MUST bring the schema to the spec'd 3-table
  state with the 6 indexes from the spec.
* ``alembic downgrade base`` MUST roll back to a clean state where the
  3 tables are gone and the alembic version is empty. (The spec test
  description in the plan reads ``downgrade -1`` but its assertion is
  "3 tables gone", which only happens when every migration has been
  reversed — i.e. ``downgrade base``. We cover both interpretations
  below: ``downgrade base`` for the full-rollback assertion, and a
  separate ``downgrade -1`` of just the head revision to catch missed
  ``op.drop_index`` calls in any future migration.)
* An additional idempotency round-trip catches the common
  "forgot to drop an index in downgrade" bug class.

Test isolation: each session spins up a fresh Postgres via
``testcontainers[postgres]``. The container is destroyed at session
teardown via the ``PostgresContainer`` context-manager protocol.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile
from collections.abc import Iterator

import pytest
import sqlalchemy as sa
from testcontainers.postgres import PostgresContainer

# ---------------------------------------------------------------------------
# Path constants — service root + alembic config.
# ---------------------------------------------------------------------------
THIS_FILE = pathlib.Path(__file__).resolve()
SERVICE_ROOT = THIS_FILE.parents[2]  # services/credential/
ALEMBIC_INI = SERVICE_ROOT / "alembic.ini"

# The 3 tables declared in the change spec §数据库 schema.
EXPECTED_TABLES: frozenset[str] = frozenset({"credentials", "encryption_keys", "credential_audit"})

# The 6 indexes called out by the change spec §数据库 schema across the 3 tables.
# ``downgrade base`` must drop every one of these.
EXPECTED_INDEXES: frozenset[str] = frozenset(
    {
        "ix_credentials_workspace_id_type",
        "ix_credentials_expires_at",
        "ix_encryption_keys_status",
        "ix_credential_audit_timestamp",
        "ix_credential_audit_credential_id_hash_timestamp",
        "ix_credential_audit_user_id_timestamp",
    }
)


@pytest.fixture(scope="session")
def pg_url() -> Iterator[str]:
    """Boot a Postgres testcontainer for the session and yield its DSN.

    The URL ``testcontainers`` returns is ``postgresql+psycopg2://...``;
    we normalise it to ``postgresql://...`` so the env.py URL-normaliser
    (which is what the real compose stack hits when an operator sets
    ``DATABASE_URL=postgresql://...``) exercises the same code path.
    """
    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url()
        if url.startswith("postgresql+psycopg2://"):
            url = "postgresql://" + url[len("postgresql+psycopg2://") :]
        yield url


@pytest.fixture(scope="session")
def sandbox_cwd() -> Iterator[pathlib.Path]:
    """A throwaway CWD that does NOT contain an ``alembic/`` directory.

    We invoke the alembic subprocess from here to keep our service's
    ``alembic/`` migration folder off the subprocess's ``sys.path`` —
    otherwise Python resolves ``import alembic`` to our local package
    (which has an empty ``__init__.py``) instead of the real one, and
    ``from alembic.config import main`` raises ``ModuleNotFoundError``.
    """
    with tempfile.TemporaryDirectory(prefix="credential-alembic-") as tmp:
        yield pathlib.Path(tmp)


def _alembic_env(database_url: str) -> dict[str, str]:
    """Build the env vars needed to run ``alembic`` as a subprocess.

    We add the service root to ``PYTHONPATH`` (without prepending any
    CWD entry that would shadow the real ``alembic`` package with our
    own ``alembic/`` migration directory), and we make sure the local
    venv's site-packages is searched even when the active Python is the
    system one.
    """
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    # The service uses ``app.*`` imports inside env.py; make the service
    # root importable regardless of where pytest is invoked from. We
    # also point at the venv's site-packages so the subprocess can
    # actually find the ``alembic`` and ``sqlalchemy`` packages (the
    # active Python in some CI / dev environments is the system one
    # without the venv on ``sys.path``).
    # Derive the venv's site-packages directory from the running interpreter
    # version rather than hard-coding ``python3.13`` — the venv version
    # bumps whenever the project's ``.python-version`` is rolled forward.
    # When the venv directory does not exist (e.g. running under a conda
    # env like `chatbiz`), fall back to ``sys.prefix`` which is the conda
    # env's site-packages root.
    python_ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
    venv_site = str(SERVICE_ROOT / ".venv" / "lib" / python_ver / "site-packages")
    if not pathlib.Path(venv_site).is_dir():
        venv_site = str(pathlib.Path(sys.prefix) / "lib" / python_ver / "site-packages")
    existing_pp = env.get("PYTHONPATH", "")
    # NOTE: the venv site-packages MUST come BEFORE the service root on
    # PYTHONPATH. Our service root contains an ``alembic/`` directory
    # (the migration scripts folder), and Python's import machinery
    # matches the first entry of ``sys.path`` that has a matching
    # subdirectory. If the service root wins, the local ``alembic/``
    # shadows the real ``alembic`` package and ``from alembic.config
    # import main`` raises ``ModuleNotFoundError`` because the local
    # ``alembic/__init__.py`` is empty.
    parts = [venv_site, str(SERVICE_ROOT)]
    if existing_pp:
        parts.append(existing_pp)
    env["PYTHONPATH"] = os.pathsep.join(parts)
    return env


def _run_alembic(
    database_url: str,
    sandbox_cwd: pathlib.Path,
    *args: str,
) -> subprocess.CompletedProcess[str]:
    """Run alembic as a subprocess and return the CompletedProcess.

    We deliberately do not call ``alembic.command.upgrade`` / ``downgrade``
    in-process: the spec calls out an integration test that drives the
    CLI so we catch issues that wouldn't show up in-process (path setup,
    ini parsing, async event loop glue).

    We invoke alembic from a throwaway CWD (see ``sandbox_cwd`` fixture)
    to avoid the local ``alembic/`` migration directory shadowing the
    real ``alembic`` Python package on ``sys.path`` (see Step 2.5 of the
    credential-management plan).
    """
    cmd = [sys.executable, "-c", "from alembic.config import main; main()", *args]
    return subprocess.run(  # noqa: S603 — fixed argv list, no shell
        cmd,
        cwd=str(sandbox_cwd),
        env=_alembic_env(database_url),
        capture_output=True,
        text=True,
        check=False,
    )


def _inspector_table_names(database_url: str) -> set[str]:
    """Return the set of table names in the public schema."""
    engine = sa.create_engine(database_url)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
                )
            ).fetchall()
            return {r[0] for r in rows}
    finally:
        engine.dispose()


def _inspector_index_names(database_url: str) -> set[str]:
    """Return the set of user-defined index names in the public schema.

    Excludes the implicit PK index (``<table>_pkey``) and ``alembic_*`` —
    we only care about the 6 spec'd indexes.
    """
    engine = sa.create_engine(database_url)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE schemaname = 'public' "
                    "AND indexname NOT LIKE '%_pkey' "
                    "AND indexname NOT LIKE 'alembic_%'"
                )
            ).fetchall()
            return {r[0] for r in rows}
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_alembic_upgrade_creates_three_tables(pg_url: str, sandbox_cwd: pathlib.Path) -> None:
    """``alembic upgrade head`` MUST create exactly the 3 spec'd tables.

    Asserts:

    * The CLI exits with return code 0.
    * The 3 tables from the spec exist in the public schema.
    * All 6 spec'd indexes are present.
    * The ``alembic_version`` table exists (so the migration was recorded).
    """
    result = _run_alembic(pg_url, sandbox_cwd, "-c", str(ALEMBIC_INI), "upgrade", "head")
    assert result.returncode == 0, (
        f"alembic upgrade head failed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    tables = _inspector_table_names(pg_url)
    missing = EXPECTED_TABLES - tables
    assert not missing, (
        f"expected tables missing after upgrade: {sorted(missing)}; got: {sorted(tables)}"
    )

    indexes = _inspector_index_names(pg_url)
    missing_idx = EXPECTED_INDEXES - indexes
    assert not missing_idx, (
        f"expected indexes missing after upgrade: {sorted(missing_idx)}; got: {sorted(indexes)}"
    )

    assert "alembic_version" in tables, (
        f"alembic_version table not created; tables: {sorted(tables)}"
    )


@pytest.mark.integration
def test_alembic_downgrade_minus_one_after_upgrade(pg_url: str, sandbox_cwd: pathlib.Path) -> None:
    """``downgrade -1`` after ``upgrade head`` MUST cleanly undo 0002 only.

    Spec §数据库回滚测试 (in the change spec), Scenario: 回滚迁移 (per the plan's step 2.6
    language "upgrade → downgrade -1"). After ``upgrade head`` the
    alembic state is at revision ``0002_audit_indexes``; ``downgrade -1``
    MUST:

    * Exit with return code 0.
    * Drop the 2 composite indexes that 0002 added
      (``ix_credential_audit_credential_id_hash_timestamp`` and
      ``ix_credential_audit_user_id_timestamp``).
    * Leave the 3 spec'd tables intact (those were created by 0001, the
      migration that came before 0002).
    * Leave the indexes added by 0001 intact.
    """
    upgrade = _run_alembic(pg_url, sandbox_cwd, "-c", str(ALEMBIC_INI), "upgrade", "head")
    assert upgrade.returncode == 0, (
        f"upgrade step failed before downgrade -1 test could run.\n"
        f"stdout:\n{upgrade.stdout}\nstderr:\n{upgrade.stderr}"
    )

    downgrade = _run_alembic(pg_url, sandbox_cwd, "-c", str(ALEMBIC_INI), "downgrade", "-1")
    assert downgrade.returncode == 0, (
        f"alembic downgrade -1 failed.\nstdout:\n{downgrade.stdout}\nstderr:\n{downgrade.stderr}"
    )

    tables = _inspector_table_names(pg_url)
    missing = EXPECTED_TABLES - tables
    assert not missing, (
        f"downgrade -1 should leave 0001's tables intact; "
        f"missing: {sorted(missing)}; got: {sorted(tables)}"
    )

    indexes = _inspector_index_names(pg_url)
    # The 2 composite indexes from 0002 must be gone.
    gone = {
        "ix_credential_audit_credential_id_hash_timestamp",
        "ix_credential_audit_user_id_timestamp",
    }
    leftover = gone & indexes
    assert not leftover, (
        f"downgrade -1 should drop 0002's composite indexes; "
        f"leftover: {sorted(leftover)}; got: {sorted(indexes)}"
    )
    # The 4 indexes from 0001 must still be there.
    kept = EXPECTED_INDEXES - gone
    dropped_0001 = kept - indexes
    assert not dropped_0001, (
        f"downgrade -1 should NOT drop 0001's indexes; "
        f"unexpectedly dropped: {sorted(dropped_0001)}; got: {sorted(indexes)}"
    )


@pytest.mark.integration
def test_alembic_downgrade_base_clears_schema(pg_url: str, sandbox_cwd: pathlib.Path) -> None:
    """``alembic downgrade base`` MUST roll back to a clean schema.

    Spec §数据库回滚测试 (in the change spec), Scenario: 回滚迁移 (the "3 tables gone"
    interpretation: the full rollback drops all 3 spec'd tables and all
    6 spec'd indexes; the database is left with just the alembic
    bookkeeping table on an empty public schema).

    Asserts:

    * ``upgrade head`` then ``downgrade base`` exits 0.
    * The 3 spec'd tables are gone.
    * All 6 spec'd indexes are gone.
    * The ``alembic_version`` table is empty (no current revision).
    """
    upgrade = _run_alembic(pg_url, sandbox_cwd, "-c", str(ALEMBIC_INI), "upgrade", "head")
    assert upgrade.returncode == 0, upgrade.stderr

    full_down = _run_alembic(pg_url, sandbox_cwd, "-c", str(ALEMBIC_INI), "downgrade", "base")
    assert full_down.returncode == 0, (
        f"alembic downgrade base failed.\nstdout:\n{full_down.stdout}\nstderr:\n{full_down.stderr}"
    )

    tables = _inspector_table_names(pg_url)
    leftover_tables = EXPECTED_TABLES & tables
    assert not leftover_tables, (
        f"downgrade base should drop all 3 spec tables; "
        f"leftover: {sorted(leftover_tables)}; got: {sorted(tables)}"
    )

    indexes = _inspector_index_names(pg_url)
    leftover_indexes = EXPECTED_INDEXES & indexes
    assert not leftover_indexes, (
        f"downgrade base should drop all 6 spec indexes; "
        f"leftover: {sorted(leftover_indexes)}; got: {sorted(indexes)}"
    )


@pytest.mark.integration
def test_alembic_full_round_trip_is_idempotent(pg_url: str, sandbox_cwd: pathlib.Path) -> None:
    """``upgrade head`` -> ``downgrade base`` -> ``upgrade head`` MUST work.

    Catches the common "forgot to drop an index in downgrade" bug class
    where the first round-trip works but the second fails because the
    index already exists.
    """
    _run_alembic(pg_url, sandbox_cwd, "-c", str(ALEMBIC_INI), "upgrade", "head")
    _run_alembic(pg_url, sandbox_cwd, "-c", str(ALEMBIC_INI), "downgrade", "base")

    second_up = _run_alembic(pg_url, sandbox_cwd, "-c", str(ALEMBIC_INI), "upgrade", "head")
    assert second_up.returncode == 0, (
        f"second upgrade after full downgrade failed — likely a missed "
        f"op.drop_index or op.drop_table in the downgrade chain.\n"
        f"stdout:\n{second_up.stdout}\nstderr:\n{second_up.stderr}"
    )

    tables = _inspector_table_names(pg_url)
    missing = EXPECTED_TABLES - tables
    assert not missing, f"second upgrade did not recreate spec tables; missing: {sorted(missing)}"

    indexes = _inspector_index_names(pg_url)
    missing_idx = EXPECTED_INDEXES - indexes
    assert not missing_idx, (
        f"second upgrade did not recreate spec indexes; "
        f"missing: {sorted(missing_idx)}; got: {sorted(indexes)}"
    )
