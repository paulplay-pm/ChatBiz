"""Coverage-gap tests for sso/routers/sso.py.

Per `openspec/changes/archive/2026-06-15-ci-coverage-sso/retrospective.md`
§3.1 + §4.1 row 1, `app/routers/sso.py` had 70 missing lines across
4 endpoints. This file adds 12 endpoint tests to close the gap to
100% line cov.

Pattern follows `services/sso/tests/test_coverage_followup.py`
(commit 5d895e6).
"""
from __future__ import annotations

from types import SimpleNamespace
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# =============================================================================
# Shared helpers
# =============================================================================


def _build_app_with_state(wechat=None, redis=None, db_sessionmaker=None, rsa_private=None, rsa_public=None):
    """Build a FastAPI app and inject mock state for the 4 endpoints."""
    from app.main import create_app

    app = create_app()
    app.state.wechat = wechat if wechat is not None else MagicMock()
    app.state.redis = redis if redis is not None else MagicMock()
    app.state.db_sessionmaker = db_sessionmaker if db_sessionmaker is not None else MagicMock()
    app.state.rsa_private = rsa_private if rsa_private is not None else MagicMock()
    app.state.rsa_public = rsa_public if rsa_public is not None else MagicMock()
    return app


def _make_session_context(execute_return=None, *, raise_on_execute=None, first_return=None):
    """Build a session object that supports `async with db() as session: ...`.

    Returns the session object (not a context manager wrapper).

    Note: We use a real class here instead of MagicMock/AsyncMock combos
    because MagicMock + AsyncMock interaction through `async with` has
    subtle protocol issues — the `__aenter__` return value doesn't always
    become the `as` target. Real class sidesteps this entirely.
    """
    class _Session:
        def __init__(self):
            self.add = MagicMock()
            self.commit = AsyncMock()
            if raise_on_execute is not None:
                self.execute = AsyncMock(side_effect=raise_on_execute)
            else:
                self.execute = AsyncMock(return_value=execute_return)

        def add_one(self, obj):
            self.add(obj)

    sess = _Session()
    return sess


class _SessionContextManager:
    """An async context manager whose `__aenter__` returns `sess`."""

    def __init__(self, sess):
        self._sess = sess

    def __call__(self):
        return self

    async def __aenter__(self):
        return self._sess

    async def __aexit__(self, *a):
        return False


def _make_sm(session):
    """Build a db_sessionmaker that returns `_SessionContextManager(session)`."""
    return MagicMock(return_value=_SessionContextManager(session))


# =============================================================================
# app/routers/sso.py::wechat_initiate — line 51-57
# =============================================================================


def test_wechat_initiate_happy() -> None:
    """Lines 51-57: wechat_initiate happy path (state gen + redis.setex
    + audit + return authorize_url).
    """
    wechat_mock = MagicMock(
        _available=True,
        get_authorize_url=MagicMock(return_value="https://wx/auth?state=abc"),
    )
    redis_mock = MagicMock(setex=AsyncMock(return_value=True))
    session_obj = _make_session_context()
    sm_mock = _make_sm(session_obj)
    app = _build_app_with_state(wechat=wechat_mock, redis=redis_mock, db_sessionmaker=sm_mock)

    with patch("app.routers.sso.write_audit_event", new=AsyncMock()) as mock_audit:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/v1/auth/sso/wechat/initiate")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["authorize_url"] == "https://wx/auth?state=abc"
        assert "state" in body
        assert len(body["state"]) >= 16
        redis_mock.setex.assert_awaited_once()
        args, _ = redis_mock.setex.call_args
        assert args[0].startswith("sso:state:")
        assert args[1] == 300
        mock_audit.assert_awaited_once()
        assert mock_audit.call_args.kwargs.get("event_type") == "initiate"


def test_wechat_initiate_503_when_wechat_unavailable() -> None:
    """Line 41: wechat_initiate returns 503 when wechat._available is False."""
    wechat_mock = MagicMock(_available=False)
    app = _build_app_with_state(wechat=wechat_mock)

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/api/v1/auth/sso/wechat/initiate")
    assert resp.status_code == 503
    body = resp.json()
    assert body["detail"]["error"]["code"] == "sso.wechat_unavailable"


# =============================================================================
# app/routers/sso.py::wechat_callback — line 63-131
# =============================================================================


def test_wechat_callback_happy() -> None:
    """Lines 63-131: wechat_callback full happy path (state match +
    exchange_code + fetch_userinfo + upsert + mint + SsoSession + audit +
    commit + return).
    """
    wechat_mock = MagicMock()
    wechat_mock.exchange_code = AsyncMock(return_value=("tok-1", "openid-1"))
    wechat_mock.fetch_userinfo = AsyncMock(return_value={"name": "Alice", "email": "alice@x.com"})

    redis_mock = MagicMock(
        get=AsyncMock(return_value=b"1"),
        delete=AsyncMock(return_value=1),
    )

    session_obj = _make_session_context()
    sm_mock = _make_sm(session_obj)
    app = _build_app_with_state(wechat=wechat_mock, redis=redis_mock, db_sessionmaker=sm_mock)

    fake_user = SimpleNamespace(
        id=1, name="Alice", email="alice@x.com", role="user",
        to_jwt_claims=MagicMock(return_value={"name": "Alice"}),
    )

    with patch("app.routers.sso.upsert_sso_user", new=AsyncMock(return_value=fake_user)) as mock_upsert, \
         patch("app.routers.sso.encode_jwt", return_value=("jwt-xxx", "jti-1", 3600)) as mock_encode, \
         patch("app.routers.sso.write_audit_event", new=AsyncMock()) as mock_audit:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/v1/auth/sso/wechat/callback", json={"code": "valid", "state": "valid"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["jwt"] == "jwt-xxx"
        assert body["expires_in"] == 3600
        assert body["user"]["id"] == 1
        assert body["user"]["name"] == "Alice"
        # SsoSession.add + commit
        assert session_obj.add.call_count == 1
        session_obj.commit.assert_awaited_once()
        # write_audit_event login_success
        mock_audit.assert_awaited_once()
        assert mock_audit.call_args.kwargs.get("event_type") == "login_success"
        # encode_jwt called with (private_key, user_id=1, claims)
        assert mock_encode.call_args.args[1] == 1


def test_wechat_callback_missing_code_or_state() -> None:
    """Lines 66-70: returns 400 when code or state missing."""
    redis_mock = MagicMock(get=AsyncMock(return_value=b"1"))
    app = _build_app_with_state(redis=redis_mock)

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/api/v1/auth/sso/wechat/callback", json={"code": "", "state": ""})
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"]["code"] == "user.invalid_input"


def test_wechat_callback_state_mismatch() -> None:
    """Lines 73-77: returns 401 when state not in redis."""
    redis_mock = MagicMock(get=AsyncMock(return_value=None))
    app = _build_app_with_state(redis=redis_mock)

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/api/v1/auth/sso/wechat/callback", json={"code": "valid", "state": "stale"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["error"]["code"] == "security.invalid_state"


def test_wechat_callback_exchange_code_usererror() -> None:
    """Lines 83-84: returns 400 when exchange_code raises UserError."""
    from app.jwt_utils import UserError
    wechat_mock = MagicMock()
    wechat_mock.exchange_code = AsyncMock(side_effect=UserError("invalid", "user.wechat_invalid_code"))
    redis_mock = MagicMock(get=AsyncMock(return_value=b"1"), delete=AsyncMock(return_value=1))
    app = _build_app_with_state(wechat=wechat_mock, redis=redis_mock)

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/api/v1/auth/sso/wechat/callback", json={"code": "bad", "state": "valid"})
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"]["code"] == "user.wechat_invalid_code"


def test_wechat_callback_exchange_code_runtime_error() -> None:
    """Lines 85-86: returns 502 when exchange_code raises WorkflowRuntimeError."""
    from app.jwt_utils import WorkflowRuntimeError
    wechat_mock = MagicMock()
    wechat_mock.exchange_code = AsyncMock(side_effect=WorkflowRuntimeError("wechat 5xx", "runtime.wechat_5xx"))
    redis_mock = MagicMock(get=AsyncMock(return_value=b"1"), delete=AsyncMock(return_value=1))
    app = _build_app_with_state(wechat=wechat_mock, redis=redis_mock)

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/api/v1/auth/sso/wechat/callback", json={"code": "valid", "state": "valid"})
    assert resp.status_code == 502
    assert resp.json()["detail"]["error"]["code"] == "runtime.wechat_5xx"


def test_wechat_callback_fetch_userinfo_runtime_error() -> None:
    """Lines 90-91: returns 502 when fetch_userinfo raises WorkflowRuntimeError."""
    from app.jwt_utils import WorkflowRuntimeError
    wechat_mock = MagicMock()
    wechat_mock.exchange_code = AsyncMock(return_value=("tok", "openid"))
    wechat_mock.fetch_userinfo = AsyncMock(side_effect=WorkflowRuntimeError("wechat 5xx", "runtime.wechat_5xx"))
    redis_mock = MagicMock(get=AsyncMock(return_value=b"1"), delete=AsyncMock(return_value=1))
    app = _build_app_with_state(wechat=wechat_mock, redis=redis_mock)

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/api/v1/auth/sso/wechat/callback", json={"code": "valid", "state": "valid"})
    assert resp.status_code == 502
    assert resp.json()["detail"]["error"]["code"] == "runtime.wechat_5xx"


# =============================================================================
# app/routers/sso.py::refresh_token — line 137-180
# =============================================================================


def test_refresh_token_missing_refresh() -> None:
    """Lines 139-142: refresh_token returns 400 when refresh missing."""
    app = _build_app_with_state()

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/api/v1/auth/sso/refresh", json={"refresh": ""})
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"]["code"] == "user.invalid_input"


@pytest.mark.parametrize(
    "label,row,user_return,expected_code",
    [
        # row None → 401 security.token_expired
        ("row_none", None, MagicMock(id=1), "security.token_expired"),
        # row.revoked_at set → 401 security.token_expired
        ("revoked", MagicMock(revoked_at=datetime(2020, 1, 1), expires_at=datetime(2099, 1, 1), user_id=1), MagicMock(id=1), "security.token_expired"),
        # row.expires_at < utcnow → 401 security.token_expired
        ("expired", MagicMock(revoked_at=None, expires_at=datetime(2020, 1, 1), user_id=1), MagicMock(id=1), "security.token_expired"),
        # get_user_by_id → None → 401 security.invalid_token
        ("user_none", MagicMock(revoked_at=None, expires_at=datetime(2099, 1, 1), user_id=999), None, "security.invalid_token"),
    ],
)
def test_refresh_token_401_branches(label, row, user_return, expected_code) -> None:
    """Lines 160-166: refresh_token returns 401 in 4 cases (parametrized)."""
    exec_result = MagicMock(first=MagicMock(return_value=row))
    session_obj = _make_session_context(execute_return=exec_result)
    sm_mock = _make_sm(session_obj)
    app = _build_app_with_state(db_sessionmaker=sm_mock)

    with patch("app.routers.sso.get_user_by_id", new=AsyncMock(return_value=user_return)):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/v1/auth/sso/refresh", json={"refresh": "valid"})
        assert resp.status_code == 401, f"label={label}: {resp.text}"
        assert resp.json()["detail"]["error"]["code"] == expected_code, f"label={label}"


def test_refresh_token_happy() -> None:
    """Lines 167-180: refresh_token returns new jwt when row valid."""
    valid_row = MagicMock(revoked_at=None, expires_at=datetime(2099, 1, 1), user_id=1)
    exec_result = MagicMock(first=MagicMock(return_value=valid_row))
    session_obj = _make_session_context(execute_return=exec_result)
    sm_mock = _make_sm(session_obj)
    app = _build_app_with_state(db_sessionmaker=sm_mock)

    fake_user = SimpleNamespace(id=1, to_jwt_claims=MagicMock(return_value={"name": "X"}))
    with patch("app.routers.sso.get_user_by_id", new=AsyncMock(return_value=fake_user)), \
         patch("app.routers.sso.encode_jwt", return_value=("new-jwt", "jti-2", 3600)) as mock_encode:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/v1/auth/sso/refresh", json={"refresh": "valid"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["jwt"] == "new-jwt"
        assert body["expires_in"] == 3600
        assert session_obj.add.call_count == 1
        session_obj.commit.assert_awaited_once()
        assert mock_encode.call_args.args[1] == 1


def test_refresh_token_first_returns_coroutine() -> None:
    """Lines 156-158: when session.execute(...).first() returns a coroutine
    (async session path), refresh_token awaits it before checking the row.
    """
    import asyncio

    valid_row = MagicMock(revoked_at=None, expires_at=datetime(2099, 1, 1), user_id=1)

    async def _first_coro():
        return valid_row

    # Bare coroutine object (not a Task) so `asyncio.iscoroutine(first)` is True
    coro = _first_coro()
    exec_result = MagicMock(first=MagicMock(return_value=coro))
    session_obj = _make_session_context(execute_return=exec_result)
    sm_mock = _make_sm(session_obj)
    app = _build_app_with_state(db_sessionmaker=sm_mock)

    fake_user = SimpleNamespace(id=1, to_jwt_claims=MagicMock(return_value={"name": "X"}))
    with patch("app.routers.sso.get_user_by_id", new=AsyncMock(return_value=fake_user)), \
         patch("app.routers.sso.encode_jwt", return_value=("new-jwt", "jti-2", 3600)):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/v1/auth/sso/refresh", json={"refresh": "valid"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["jwt"] == "new-jwt"


# =============================================================================
# app/routers/sso.py::jwks — line 186
# =============================================================================


def test_jwks_endpoint() -> None:
    """Line 186: jwks.json returns get_jwks(rsa_public) result."""
    rsa_public_mock = MagicMock()
    app = _build_app_with_state(rsa_public=rsa_public_mock)

    with patch("app.routers.sso.get_jwks", return_value={"keys": [{"kid": "test"}]}) as mock_jwks:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/auth/sso/jwks.json")
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"keys": [{"kid": "test"}]}
        mock_jwks.assert_called_once()
        assert mock_jwks.call_args.args[0] is rsa_public_mock


# =============================================================================
# app/routers/sso.py::healthz — line 192-201
# =============================================================================


def test_healthz_happy() -> None:
    """Lines 192-196: healthz returns 200 on db success."""
    session_obj = _make_session_context(execute_return=MagicMock())
    sm_mock = _make_sm(session_obj)
    app = _build_app_with_state(db_sessionmaker=sm_mock)

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/v1/auth/sso/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy"}


def test_healthz_returns_503_on_db_error() -> None:
    """Lines 197-201: healthz returns 503 on db error."""
    session_obj = _make_session_context(raise_on_execute=Exception("db down"))
    sm_mock = _make_sm(session_obj)
    app = _build_app_with_state(db_sessionmaker=sm_mock)

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/v1/auth/sso/healthz")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "unhealthy"
    assert "db down" in body["error"]
