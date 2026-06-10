"""Auth upgrade test: X-User-Id → Authorization Bearer JWT (with X-User-Id fallback).

Covers the 5 critical paths for the new ``app.api.deps.get_user_id``:

1. ``Authorization: Bearer <jwt>`` is preferred — ``sub`` claim becomes user_id.
2. ``X-User-Id`` header still works as dev fallback.
3. Malformed JWT → 401 ``error_class=security``.
4. Expired JWT → 401 ``error_class=security``.
5. No auth headers → 401 ``error_class=security``.

The tests reuse the hermetic ``client`` fixture from ``conftest.py``
(aiosqlite in-memory + fakeredis + ASGI transport + LifespanManager)
so they are deterministic and require no external services.

The ``Authorization: Bearer <jwt>`` path was not covered by the
pre-upgrade test suite; this module adds that coverage.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest


def _make_jwt(user_id: str, exp_delta_seconds: int = 3600) -> str:
    """Encode an unsigned-friendly JWT with ``sub`` and ``exp`` claims.

    Signature is *not* verified by ``get_user_id`` in MVP, but ``exp``
    IS verified — so we set it explicitly and let the expired-token
    test pass a negative delta.
    """
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(seconds=exp_delta_seconds),
    }
    return jwt.encode(payload, "any-secret", algorithm="HS256")


# ---------------------------------------------------------------------------
# 1. Bearer JWT takes priority
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bearer_jwt_user_id(client):
    """``Authorization: Bearer <jwt>`` decodes ``sub`` → created_by."""
    token = _make_jwt("u-paul")
    r = await client.post(
        "/workflows",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "auth-bearer", "definition_json": {"nodes": [], "edges": []}},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["created_by"] == "u-paul"


# ---------------------------------------------------------------------------
# 2. X-User-Id fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_x_user_id_fallback(client):
    """``X-User-Id`` header still works as dev fallback when no Bearer."""
    r = await client.post(
        "/workflows",
        headers={"X-User-Id": "legacy-user"},
        json={"name": "auth-legacy", "definition_json": {"nodes": [], "edges": []}},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["created_by"] == "legacy-user"


# ---------------------------------------------------------------------------
# 3. Bearer wins over X-User-Id when both present
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bearer_takes_priority_over_x_user_id(client):
    """When both headers are present, Bearer wins."""
    token = _make_jwt("u-jwt")
    r = await client.post(
        "/workflows",
        headers={
            "Authorization": f"Bearer {token}",
            "X-User-Id": "u-legacy",
        },
        json={"name": "auth-priority", "definition_json": {"nodes": [], "edges": []}},
    )
    assert r.status_code == 201, r.text
    assert r.json()["created_by"] == "u-jwt"


# ---------------------------------------------------------------------------
# 4. Malformed JWT → 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_jwt_returns_401(client):
    """Malformed JWT (3 segments of garbage) → 401 security error."""
    r = await client.post(
        "/workflows",
        headers={"Authorization": "Bearer not.a.valid.jwt"},
        json={"name": "x", "definition_json": {"nodes": [], "edges": []}},
    )
    assert r.status_code == 401
    body = r.json()
    assert body["detail"]["error_class"] == "security"


# ---------------------------------------------------------------------------
# 5. Expired JWT → 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expired_jwt_returns_401(client):
    """Expired JWT (exp in the past) → 401 security error."""
    expired = _make_jwt("u-paul", exp_delta_seconds=-10)
    r = await client.post(
        "/workflows",
        headers={"Authorization": f"Bearer {expired}"},
        json={"name": "x", "definition_json": {"nodes": [], "edges": []}},
    )
    assert r.status_code == 401
    body = r.json()
    assert body["detail"]["error_class"] == "security"


# ---------------------------------------------------------------------------
# 6. No auth headers → 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_auth_returns_401(client):
    """No Authorization and no X-User-Id → 401 security error."""
    r = await client.post(
        "/workflows",
        json={"name": "x", "definition_json": {"nodes": [], "edges": []}},
    )
    assert r.status_code == 401
    body = r.json()
    assert body["detail"]["error_class"] == "security"


# ---------------------------------------------------------------------------
# 7. JWT missing 'sub' claim → 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_jwt_without_sub_returns_401(client):
    """A signed token with no ``sub`` claim → 401 security error."""
    payload = {
        "exp": datetime.now(timezone.utc) + timedelta(seconds=3600),
        # intentionally no "sub"
    }
    token = jwt.encode(payload, "any-secret", algorithm="HS256")
    r = await client.post(
        "/workflows",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "x", "definition_json": {"nodes": [], "edges": []}},
    )
    assert r.status_code == 401
    body = r.json()
    assert body["detail"]["error_class"] == "security"
    assert "sub" in body["detail"]["error_message"]
