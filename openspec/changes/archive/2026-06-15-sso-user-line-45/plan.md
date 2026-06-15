# sso-user-line-45 Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`)
> syntax for tracking.

**Goal**: 1 个新 test 走 `app/user.py` line 45 `user.email = email`,达到
100% line cov,关 `ci-coverage-sso` retrospective §3.1 + §4.1 row 4
followup — sso cov matrix 收尾最后一步。

**Architecture**: 1 个新 test 文件 `services/sso/tests/test_user_line45_coverage.py`
(沿用 `test_coverage_followup.py` 已有 pattern)。1 test 走 `upsert_sso_user`
else 分支 + `if email:` True 路径。Mock 沿用既有 AsyncMock session +
MagicMock existing user pattern。0 行 prod code 改动。

**Tech Stack**: Python 3.12 + SQLAlchemy (AsyncSession) + pytest 8.x +
pytest-cov 6.x + unittest.mock (AsyncMock / MagicMock) + conda env
`chatbiz`

---

## Task 1: 写 `test_upsert_sso_user_updates_existing_with_email`

**Files:**
- Create: `services/sso/tests/test_user_line45_coverage.py`
- Test: `services/sso/tests/test_user_line45_coverage.py::test_upsert_sso_user_updates_existing_with_email`

- [ ] **Step 1**: 创建 test 文件 + 1 test
```python
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

import pytest


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
```

- [ ] **Step 2**: 跑 test 验证 PASS:
```bash
cd /Users/paulwang/work/ChatBiz/services/sso && conda run -n chatbiz pytest tests/test_user_line45_coverage.py -v --no-cov
```
Expected: 1 passed

---

## Task 2: 验 100% line cov

- [ ] **Step 1**: 跑 `--cov=app.user` 验 100%
```bash
conda run -n chatbiz pytest tests/ --cov=app.user --cov-report=term-missing -q
```
Expected: `app/user.py 23 0 100%`

---

## Task 3: 跑全 sso suite 验证无 regression

- [ ] **Step 1**: 全 sso suite
```bash
conda run -n chatbiz pytest tests/ -q
```
Expected: 50 PASS / 1 SKIPPED / 0 FAILED(本 change + 1 新 test = 50 effective)

---

## Task 4: Commit

- [ ] **Step 1**: `git add services/sso/tests/test_user_line45_coverage.py`
- [ ] **Step 2**: `git commit -m "test(sso): close retrospective §4.1 row 4 — 100% line cov on user.py (1 line 45 miss)"
  ` with Co-Authored-By trailer
- [ ] **Step 3**: `git log -1 --format='%H %s'` 验证 commit 进 linear history
- [ ] **Step 4**: `git status` 验证 working tree clean
