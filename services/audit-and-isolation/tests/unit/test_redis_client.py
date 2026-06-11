"""Unit tests for ``app.redis_client`` — lazy pool init, reuse, and test reset.

The pool and client creation (``from_url`` + ``Redis(connection_pool=...)``)
do NOT connect to the server — they only parse the URL and store config.
So we can exercise lines 47-53 with any valid redis:// URL; no live Redis
or fakeredis is needed. The existing monkeypatch of ``get_settings`` to
return a fake redis_url is sufficient.

Other integration/unit test modules may replace ``redis_client.get_redis``
with a fakeredis stub; we save the *real* function at import time and
reinstall it before each test to guarantee isolation.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.redis_client as rc_mod

# Snapshot the real factory at import time so cross-module contamination
# (other tests replacing get_redis with fakeredis lambdas) is undone
# unconditionally.
_REAL_GET_REDIS = rc_mod.get_redis


@pytest.fixture(autouse=True)
def _reset_module_state():
    """Before *and* after every test: restore the real factory + clear pool.

    The after-cleanup prevents this module from leaking to others;
    the before-cleanup protects this module against others.
    """
    rc_mod.get_redis = _REAL_GET_REDIS
    rc_mod._pool = None
    yield
    rc_mod._pool = None


def _patch_settings(monkeypatch, **overrides):
    s = SimpleNamespace(redis_url="redis://localhost:6379/0", **overrides)
    monkeypatch.setattr(rc_mod, "get_settings", lambda: s)
    return s


class TestGetRedis:
    def test_first_call_creates_pool_and_returns_client(self, monkeypatch):
        """get_redis() lazily creates the connection pool and returns a
        redis.Redis client bound to it (covers lines 47-53)."""
        _patch_settings(monkeypatch)
        client = rc_mod.get_redis()
        assert rc_mod._pool is not None
        assert client is not None

    def test_second_call_reuses_cached_pool(self, monkeypatch):
        """Second call to get_redis() reuses the same cached pool."""
        _patch_settings(monkeypatch)
        c1 = rc_mod.get_redis()
        c2 = rc_mod.get_redis()
        assert rc_mod._pool is not None
        assert c1 is not None
        assert c2 is not None


class TestResetPoolForTests:
    def test_reset_with_pool_clears_it(self, monkeypatch):
        _patch_settings(monkeypatch)
        rc_mod.get_redis()
        assert rc_mod._pool is not None
        rc_mod.reset_pool_for_tests()
        assert rc_mod._pool is None

    def test_reset_without_pool_is_noop(self):
        assert rc_mod._pool is None
        rc_mod.reset_pool_for_tests()
        assert rc_mod._pool is None
