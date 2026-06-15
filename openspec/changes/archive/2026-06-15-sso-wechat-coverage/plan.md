# sso-wechat-coverage Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`)
> syntax for tracking.

**Goal**: 5 个新 test 走 `app/wechat.py` 5 path 共 8 miss 行,达到 100%
line cov,关 `ci-coverage-sso` retrospective §3.1 + §4.1 row 3 followup。

**Architecture**: 1 个新 test 文件 `services/sso/tests/test_wechat_coverage.py`
(沿用 `test_routers_coverage.py` / `test_jwt_utils_coverage.py` 已有
pattern)。5 test 拆 5 path:`exchange_code` 4 path(Timeout / HTTPError /
其他 errcode / 缺字段)+ `fetch_userinfo` 1 path(httpx exception 走真
try/except 块)。`httpx.AsyncClient.get` patch 用 `AsyncMock(side_effect=...)`
或 `AsyncMock(return_value=...)` 配 `MagicMock(spec=httpx.Response)`。0 行
prod code 改动。

**Tech Stack**: Python 3.12 + httpx (AsyncClient / TimeoutException /
HTTPError / Response) + pytest 8.x + pytest-cov 6.x +
unittest.mock (AsyncMock / MagicMock) + conda env `chatbiz`

---

## Task 1: 写 `test_exchange_code_timeout_exception`

**Files:**
- Create: `services/sso/tests/test_wechat_coverage.py`
- Test: `services/sso/tests/test_wechat_coverage.py::test_exchange_code_timeout_exception`

- [ ] **Step 1**: 创建 test 文件头 + shared helper(已有 client fixture 复用)
```python
"""Coverage-gap tests for sso/wechat.py.

Per `openspec/changes/archive/2026-06-15-ci-coverage-sso/retrospective.md`
§3.1 + §4.1 row 3, `app/wechat.py` had 8 missing lines across
5 paths. This file adds 5 endpoint tests to close the gap to 100% line cov.

Pattern follows `services/sso/tests/test_coverage_followup.py` and
`services/sso/tests/test_routers_coverage.py` (commits 5d895e6 / 23018e8).
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


def _make_wechat_client():
    """Build a real WeChatClient instance with placeholder credentials
    (so _available == True)."""
    from app.wechat import WeChatClient
    return WeChatClient(
        corp_id="test_corp", agent_id="test_agent",
        corp_secret="test_secret", redirect_uri="http://x",
    )
```

- [ ] **Step 2**: append test #1
```python
def test_exchange_code_timeout_exception() -> None:
    """Lines 71-74: exchange_code converts httpx.TimeoutException to
    WorkflowRuntimeError(code='runtime.wechat_timeout')."""
    from app.jwt_utils import WorkflowRuntimeError
    client = _make_wechat_client()
    with patch("httpx.AsyncClient") as mock_httpx_client:
        mock_http = MagicMock()
        mock_http.get = AsyncMock(side_effect=httpx.TimeoutException("read timeout"))
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_httpx_client.return_value = mock_http
        with pytest.raises(WorkflowRuntimeError) as exc_info:
            asyncio.run(client.exchange_code("code"))
        assert exc_info.value.code == "runtime.wechat_timeout"
        assert "timeout" in str(exc_info.value)
```

- [ ] **Step 3**: 跑 test 验证 PASS:
```bash
cd /Users/paulwang/work/ChatBiz/services/sso && conda run -n chatbiz pytest tests/test_wechat_coverage.py::test_exchange_code_timeout_exception -v --no-cov
```
Expected: 1 passed

---

## Task 2: 写 `test_exchange_code_http_error`

- [ ] **Step 1**: append test #2
```python
def test_exchange_code_http_error() -> None:
    """Lines 75-77: exchange_code converts httpx.HTTPError to
    WorkflowRuntimeError(code='runtime.wechat_5xx')."""
    from app.jwt_utils import WorkflowRuntimeError
    client = _make_wechat_client()
    with patch("httpx.AsyncClient") as mock_httpx_client:
        mock_http = MagicMock()
        mock_http.get = AsyncMock(side_effect=httpx.HTTPError("connection error"))
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_httpx_client.return_value = mock_http
        with pytest.raises(WorkflowRuntimeError) as exc_info:
            asyncio.run(client.exchange_code("code"))
        assert exc_info.value.code == "runtime.wechat_5xx"
        assert "HTTP error" in str(exc_info.value)
```

- [ ] **Step 2**: 跑 test 验证 PASS。

---

## Task 3: 写 `test_exchange_code_other_errcode`

- [ ] **Step 1**: append test #3
```python
def test_exchange_code_other_errcode() -> None:
    """Lines 88-90: exchange_code converts errcode not in (40029, 40163)
    to WorkflowRuntimeError(code='runtime.wechat_5xx')."""
    from app.jwt_utils import WorkflowRuntimeError
    client = _make_wechat_client()
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.return_value = {"errcode": 50005, "errmsg": "freq limit"}
    mock_response.raise_for_status = MagicMock()
    with patch("httpx.AsyncClient") as mock_httpx_client:
        mock_http = MagicMock()
        mock_http.get = AsyncMock(return_value=mock_response)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_httpx_client.return_value = mock_http
        with pytest.raises(WorkflowRuntimeError) as exc_info:
            asyncio.run(client.exchange_code("code"))
        assert exc_info.value.code == "runtime.wechat_5xx"
        assert "50005" in str(exc_info.value)
        assert "freq limit" in str(exc_info.value)
```

- [ ] **Step 2**: 跑 test 验证 PASS。

---

## Task 4: 写 `test_exchange_code_missing_access_token`

- [ ] **Step 1**: append test #4
```python
def test_exchange_code_missing_access_token() -> None:
    """Lines 95-97: exchange_code raises WorkflowRuntimeError when response
    errcode=0 but access_token or openid field is missing."""
    from app.jwt_utils import WorkflowRuntimeError
    client = _make_wechat_client()
    mock_response = MagicMock(spec=httpx.Response)
    # errcode=0 happy, but missing access_token
    mock_response.json.return_value = {"errcode": 0, "openid": "openid-1"}
    mock_response.raise_for_status = MagicMock()
    with patch("httpx.AsyncClient") as mock_httpx_client:
        mock_http = MagicMock()
        mock_http.get = AsyncMock(return_value=mock_response)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_httpx_client.return_value = mock_http
        with pytest.raises(WorkflowRuntimeError) as exc_info:
            asyncio.run(client.exchange_code("code"))
        assert exc_info.value.code == "runtime.wechat_5xx"
        assert "缺字段" in str(exc_info.value)
```

- [ ] **Step 2**: 跑 test 验证 PASS。

---

## Task 5: 写 `test_fetch_userinfo_httpx_error`

- [ ] **Step 1**: append test #5
```python
def test_fetch_userinfo_httpx_error() -> None:
    """Lines 114-115: fetch_userinfo converts httpx.HTTPError to
    WorkflowRuntimeError(code='runtime.wechat_5xx') via try/except block.

    Note: existing test_coverage_followup.py test mocks WeChatClient.fetch_userinfo
    directly (side_effect on client method) which BYPASSES the try/except block.
    This test mocks httpx.AsyncClient.get instead so the try/except body is hit.
    """
    from app.jwt_utils import WorkflowRuntimeError
    client = _make_wechat_client()
    with patch("httpx.AsyncClient") as mock_httpx_client:
        mock_http = MagicMock()
        mock_http.get = AsyncMock(side_effect=httpx.HTTPError("conn refused"))
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_httpx_client.return_value = mock_http
        with pytest.raises(WorkflowRuntimeError) as exc_info:
            asyncio.run(client.fetch_userinfo("tok", "openid-1"))
        assert exc_info.value.code == "runtime.wechat_5xx"
        assert "userinfo" in str(exc_info.value)
```

- [ ] **Step 2**: 跑 test 验证 PASS。

---

## Task 6: 全套验证

- [ ] **Step 1**: 跑 5 test + 100% line cov:
```bash
conda run -n chatbiz pytest tests/test_wechat_coverage.py --cov=app.wechat --cov-report=term-missing -v
```
Expected: 5 passed, `app/wechat.py` 100% line cov

- [ ] **Step 2**: 跑全 sso suite 验证无 regression:
```bash
conda run -n chatbiz pytest tests/ -q
```
Expected: 全部 PASS,无 regression

---

## Task 7: Commit

- [ ] **Step 1**: `git add services/sso/tests/test_wechat_coverage.py`
- [ ] **Step 2**: `git commit -m "test(sso): close retrospective §4.1 row 3 — 100% line cov on wechat.py"
  ` with Co-Authored-By trailer
- [ ] **Step 3**: `git log -1 --format='%H %s'` 验证 commit 进 linear history
- [ ] **Step 4**: `git status` 验证 working tree clean
