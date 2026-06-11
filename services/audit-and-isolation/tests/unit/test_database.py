"""Unit tests for ``app.database`` — lazy engine/session-factory init, get_session,
and dispose_engine.

All external I/O is replaced with in-memory mocks via monkeypatch so the tests
never touch a real PostgreSQL instance.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.database as db_mod  # pyright: ignore[reportAttributeAccessIssue]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reset_module_state() -> None:
    """Reset the module-level singletons so each test gets a clean slate."""
    db_mod._engine = None
    db_mod._session_factory = None


def _patch_settings(monkeypatch, **overrides):
    """Patch ``app.database.get_settings`` to return a fake settings object."""
    s = SimpleNamespace(database_url="sqlite+aiosqlite:///test.db", **overrides)
    monkeypatch.setattr(db_mod, "get_settings", lambda: s)
    return s


# ---------------------------------------------------------------------------
# _get_engine
# ---------------------------------------------------------------------------


class TestGetEngine:
    @pytest.fixture(autouse=True)
    def _setup(self):
        _reset_module_state()

    def test_lazy_init_creates_engine_via_create_async_engine(self, monkeypatch):
        fake_engine = MagicMock(name="AsyncEngine")
        create_engine_mock = MagicMock(return_value=fake_engine)
        monkeypatch.setattr(db_mod, "create_async_engine", create_engine_mock)
        _patch_settings(monkeypatch)

        engine = db_mod._get_engine()

        assert engine is fake_engine
        create_engine_mock.assert_called_once()
        _, kwargs = create_engine_mock.call_args
        assert kwargs.get("pool_pre_ping") is True

    def test_reuses_cached_engine(self, monkeypatch):
        fake_engine = MagicMock(name="AsyncEngine")
        create_engine_mock = MagicMock(return_value=fake_engine)
        monkeypatch.setattr(db_mod, "create_async_engine", create_engine_mock)
        _patch_settings(monkeypatch)

        e1 = db_mod._get_engine()
        e2 = db_mod._get_engine()

        assert e1 is e2
        create_engine_mock.assert_called_once()


# ---------------------------------------------------------------------------
# _get_session_factory
# ---------------------------------------------------------------------------


class TestGetSessionFactory:
    @pytest.fixture(autouse=True)
    def _setup(self):
        _reset_module_state()

    def test_lazy_init_creates_factory(self, monkeypatch):
        fake_engine = MagicMock(name="AsyncEngine")
        fake_factory = MagicMock(name="async_sessionmaker")
        monkeypatch.setattr(db_mod, "create_async_engine", MagicMock(return_value=fake_engine))
        _patch_settings(monkeypatch)
        sessionmaker_mock = MagicMock(return_value=fake_factory)
        monkeypatch.setattr(db_mod, "async_sessionmaker", sessionmaker_mock)

        factory = db_mod._get_session_factory()

        assert factory is fake_factory
        sessionmaker_mock.assert_called_once()
        _, kwargs = sessionmaker_mock.call_args
        assert kwargs.get("expire_on_commit") is False

    def test_reuses_cached_session_factory(self, monkeypatch):
        fake_engine = MagicMock(name="AsyncEngine")
        fake_factory = MagicMock(name="async_sessionmaker")
        monkeypatch.setattr(db_mod, "create_async_engine", MagicMock(return_value=fake_engine))
        _patch_settings(monkeypatch)
        sessionmaker_mock = MagicMock(return_value=fake_factory)
        monkeypatch.setattr(db_mod, "async_sessionmaker", sessionmaker_mock)

        f1 = db_mod._get_session_factory()
        f2 = db_mod._get_session_factory()

        assert f1 is f2
        sessionmaker_mock.assert_called_once()


# ---------------------------------------------------------------------------
# get_session — async context manager
# ---------------------------------------------------------------------------


class _FakeBeginCtx:
    """Explicit async context manager standing in for ``session.begin()``."""

    def __init__(self):
        self.enter_count = 0
        self.exit_args: tuple | None = None

    async def __aenter__(self):
        self.enter_count += 1
        return self

    async def __aexit__(self, *args):
        self.exit_args = args
        return False  # don't suppress exceptions


class _FakeSession:
    """Fake ``AsyncSession`` exposing a ``begin()`` that returns a context manager."""

    def __init__(self, begin_ctx: _FakeBeginCtx):
        self._begin_ctx = begin_ctx

    def begin(self) -> _FakeBeginCtx:
        return self._begin_ctx


class _FakeFactoryCtx:
    """Async context manager that yields a fake session on enter.
    Also callable (``__call__`` → self) so ``factory()`` works."""

    def __init__(self, session: _FakeSession):
        self._session = session

    def __call__(self, *args, **kwargs):
        return self

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        return None


class TestGetSession:
    @pytest.fixture(autouse=True)
    def _setup(self):
        _reset_module_state()

    def _install_fakes(self, monkeypatch):
        """Patch ``_get_session_factory`` directly to return a callable
        that yields a fake async session context."""

        fake_engine = MagicMock(name="AsyncEngine")
        monkeypatch.setattr(db_mod, "create_async_engine", MagicMock(return_value=fake_engine))
        _patch_settings(monkeypatch)

        begin_ctx = _FakeBeginCtx()
        fake_session = _FakeSession(begin_ctx)

        def _fake_get_session_factory():
            return _FakeFactoryCtx(fake_session)

        monkeypatch.setattr(db_mod, "_get_session_factory", _fake_get_session_factory)
        return begin_ctx, fake_session

    @pytest.mark.asyncio
    async def test_yields_session_and_commits_on_success(self, monkeypatch):
        begin_ctx, fake_session = self._install_fakes(monkeypatch)

        async with db_mod.get_session() as session:
            assert session is fake_session

        assert begin_ctx.enter_count == 1
        assert begin_ctx.exit_args == (None, None, None)

    @pytest.mark.asyncio
    async def test_rolls_back_on_exception(self, monkeypatch):
        begin_ctx, fake_session = self._install_fakes(monkeypatch)

        class _TestError(Exception):
            pass

        with pytest.raises(_TestError):
            async with db_mod.get_session() as _session:
                raise _TestError("boom")

        assert begin_ctx.enter_count == 1
        assert begin_ctx.exit_args is not None
        assert begin_ctx.exit_args[0] is _TestError
        assert isinstance(begin_ctx.exit_args[1], _TestError)


# ---------------------------------------------------------------------------
# dispose_engine
# ---------------------------------------------------------------------------


class TestDisposeEngine:
    @pytest.fixture(autouse=True)
    def _setup(self):
        _reset_module_state()

    def test_dispose_when_engine_exists(self, monkeypatch):
        fake_engine = MagicMock(name="AsyncEngine")
        fake_engine.dispose = AsyncMock()
        monkeypatch.setattr(db_mod, "create_async_engine", MagicMock(return_value=fake_engine))
        _patch_settings(monkeypatch)

        db_mod._get_engine()
        db_mod._get_session_factory()  # also prime the session factory
        assert db_mod._engine is not None
        assert db_mod._session_factory is not None

        asyncio.run(db_mod.dispose_engine())

        fake_engine.dispose.assert_awaited_once()
        assert db_mod._engine is None
        assert db_mod._session_factory is None

    def test_dispose_when_no_engine_noops(self):
        assert db_mod._engine is None
        assert db_mod._session_factory is None

        asyncio.run(db_mod.dispose_engine())

        assert db_mod._engine is None
        assert db_mod._session_factory is None
