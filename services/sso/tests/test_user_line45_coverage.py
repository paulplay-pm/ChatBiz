"""Coverage-gap test for sso/user.py line 45 (sso cov matrix final 1 miss).

Per `openspec/changes/archive/2026-06-15-ci-coverage-sso/retrospective.md`
§3.1 + §4.1 row 4, `app/user.py` had 1 missing line: 45
(`user.email = email` in upsert_sso_user else branch when `if email:` is True).
This file adds 1 test to close the gap to 100% line cov.

Pattern follows `services/sso/tests/test_coverage_followup.py`
(commit 5d895e6) — AsyncMock session + MagicMock existing user.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock


async def test_upsert_sso_user_updates_existing_with_email() -> None:
    """Line 45: `upsert_sso_user` else branch + `if email:` True path
    assigns `user.email = email`. Pairs with the existing
    `test_upsert_wechat_user_updates_existing` which covers the False path
    ("email NOT provided should NOT be cleared").
    """
    from app.user import upsert_sso_user
    session = AsyncMock()
    existing = MagicMock(
        name="Old Name", email="old@x.com", role="user",
        last_login_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    result = AsyncMock()
    result.scalar_one_or_none = MagicMock(return_value=existing)
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()

    user = await upsert_sso_user(
        session, corp_external_id="openid-1", name="New Name",
        email="new@example.com",
    )
    # Line 43: user.name = name (updated)
    assert user.name == "New Name"
    # Line 45: user.email = email (updated — this is the missing line)
    assert user.email == "new@example.com"
    # Line 46: last_login_at updated
    assert user.last_login_at != datetime(2020, 1, 1, tzinfo=timezone.utc)
    # Line 47: flush awaited
    session.flush.assert_awaited()
