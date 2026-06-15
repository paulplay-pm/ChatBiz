# sso-routers-coverage Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`)
> syntax for tracking.

**Goal**: 12 个新 endpoint test 走 `app/routers/sso.py` 4 endpoint 全部
70 miss 行,达到 100% line cov,关 `ci-coverage-sso` retrospective
§3.1 + §4.1 第 1 行 followup。

**Architecture**: 1 个新 test 文件 `services/sso/tests/test_routers_coverage.py`
(沿用 `test_coverage_followup.py` 已有 pattern)。12 test 拆 4 endpoint
(initiate 1 + callback 5 + refresh 3 + jwks 1 + healthz 2)。Mock 策略
TestClient 包装 `create_app()` + 注入 `app.state` MagicMock +
patch `upsert_sso_user` / `encode_jwt` / `get_jwks` 跳过已有覆盖
的部分。0 行 prod code 改动。

**Tech Stack**: Python 3.12 + FastAPI + pytest 8.x + pytest-cov 6.x +
unittest.mock (AsyncMock / MagicMock / patch) + conda env `chatbiz`

---

## Task 1: 写 `test_wechat_initiate_happy` (initiate 路径)

**Files:**
- Create: `services/sso/tests/test_routers_coverage.py`
- Test: `services/sso/tests/test_routers_coverage.py::test_wechat_initiate_happy`

- [ ] **Step 1**: 创建 `test_routers_coverage.py` 文件头,import:
  ```python
  """Coverage-gap tests for sso/routers/sso.py.

  Per `openspec/changes/archive/2026-06-15-ci-coverage-sso/retrospective.md`
  §3.1 + §4.1 row 1, `app/routers/sso.py` had 70 missing lines across
  4 endpoints. This file adds 12 endpoint tests to close the gap to
  100% line cov.

  Pattern follows `services/sso/tests/test_coverage_followup.py`
  (commit 5d895e6).
  """
  from __future__ import annotations

  from datetime import datetime, timedelta, timezone
  from unittest.mock import AsyncMock, MagicMock, patch

  import pytest
  from fastapi.testclient import TestClient
  ```

- [ ] **Step 2**: 写 test #1 happy path:
  ```python
  def test_wechat_initiate_happy() -> None:
      """Lines 51-57: wechat_initiate happy path (state gen + redis.setex
      + audit + return authorize_url)."""
      from app.main import create_app
      from app.audit import write_audit_event

      app = create_app()
      # Inject state mocks
      wechat_mock = MagicMock(_available=True, get_authorize_url=MagicMock(return_value="https://wx/auth?state=abc"))
      redis_mock = MagicMock(setex=AsyncMock(return_value=True))
      session_mock = MagicMock()
      session_mock.__aenter__ = AsyncMock(return_value=session_mock)
      session_mock.__aexit__ = AsyncMock(return_value=False)
      sm_mock = MagicMock(return_value=session_mock)
      app.state.wechat = wechat_mock
      app.state.redis = redis_mock
      app.state.db_sessionmaker = sm_mock

      with patch("app.routers.sso.write_audit_event", new=AsyncMock()) as mock_audit:
          client = TestClient(app, raise_server_exceptions=False)
          resp = client.post("/api/v1/auth/sso/wechat/initiate")
          assert resp.status_code == 200
          body = resp.json()
          assert "authorize_url" in body
          assert "state" in body
          assert len(body["state"]) >= 16
          redis_mock.setex.assert_awaited_once()
          args, _ = redis_mock.setex.call_args
          assert args[0].startswith("sso:state:")
          assert args[1] == 300
          mock_audit.assert_awaited_once()
          audit_kwargs = mock_audit.call_args.kwargs
          assert audit_kwargs.get("event_type") == "initiate"
  ```

- [ ] **Step 3**: 跑 test 验证 PASS:
  ```bash
  cd /Users/paulwang/work/ChatBiz/services/sso && conda run -n chatbiz pytest tests/test_routers_coverage.py::test_wechat_initiate_happy -v
  ```
  Expected: 1 passed

---

## Task 2: 写 `test_wechat_callback_happy` (callback 全 path)

**Files:**
- Modify: `services/sso/tests/test_routers_coverage.py`

- [ ] **Step 1**: append test #2:
  ```python
  def test_wechat_callback_happy() -> None:
      """Lines 63-131: wechat_callback full happy path (state match +
      exchange_code + fetch_userinfo + upsert + mint + SsoSession + audit
      + commit + return)."""
      from app.main import create_app

      app = create_app()
      wechat_mock = MagicMock()
      wechat_mock.exchange_code = AsyncMock(return_value=("tok-1", "openid-1"))
      wechat_mock.fetch_userinfo = AsyncMock(return_value={"name": "Alice", "email": "alice@x.com"})

      redis_mock = MagicMock(
          get=AsyncMock(return_value=b"1"),
          delete=AsyncMock(return_value=1),
      )

      session_mock = MagicMock()
      session_mock.__aenter__ = AsyncMock(return_value=session_mock)
      session_mock.__aexit__ = AsyncMock(return_value=False)
      session_mock.add = MagicMock()
      session_mock.commit = AsyncMock()
      sm_mock = MagicMock(return_value=session_mock)

      app.state.wechat = wechat_mock
      app.state.redis = redis_mock
      app.state.db_sessionmaker = sm_mock
      app.state.rsa_private = MagicMock()

      fake_user = MagicMock(id=1, name="Alice", email="alice@x.com", role="user", to_jwt_claims=MagicMock(return_value={"name": "Alice"}))

      with patch("app.routers.sso.upsert_sso_user", new=AsyncMock(return_value=fake_user)) as mock_upsert, \
           patch("app.routers.sso.encode_jwt", return_value=("jwt-xxx", "jti-1", 3600)) as mock_encode, \
           patch("app.routers.sso.write_audit_event", new=AsyncMock()) as mock_audit:
          client = TestClient(app, raise_server_exceptions=False)
          resp = client.post("/api/v1/auth/sso/wechat/callback", json={"code": "valid", "state": "valid"})
          assert resp.status_code == 200
          body = resp.json()
          assert body["jwt"] == "jwt-xxx"
          assert body["expires_in"] == 3600
          assert body["user"]["id"] == 1
          assert body["user"]["name"] == "Alice"
          # SsoSession.add + commit
          assert session_mock.add.call_count == 1
          session_mock.commit.assert_awaited_once()
          # write_audit_event login_success
          mock_audit.assert_awaited_once()
          assert mock_audit.call_args.kwargs.get("event_type") == "login_success"
          # encode_jwt called with (private_key, user_id=1, claims)
          assert mock_encode.call_args.args[1] == 1
  ```

- [ ] **Step 2**: 跑 test 验证 PASS:
  ```bash
  conda run -n chatbiz pytest tests/test_routers_coverage.py::test_wechat_callback_happy -v
  ```
  Expected: 1 passed

---

## Task 3: 写 `test_wechat_callback_missing_code_or_state`

- [ ] **Step 1**: append test #3:
  ```python
  def test_wechat_callback_missing_code_or_state() -> None:
      """Lines 66-70: wechat_callback returns 400 when code or state missing."""
      from app.main import create_app
      app = create_app()
      app.state.wechat = MagicMock()
      app.state.redis = MagicMock(get=AsyncMock(return_value=b"1"))
      app.state.db_sessionmaker = MagicMock()
      app.state.rsa_private = MagicMock()

      client = TestClient(app, raise_server_exceptions=False)
      resp = client.post("/api/v1/auth/sso/wechat/callback", json={"code": "", "state": ""})
      assert resp.status_code == 400
      body = resp.json()
      assert body["detail"]["error"]["code"] == "user.invalid_input"
  ```

- [ ] **Step 2**: 跑 test 验证 PASS。

---

## Task 4: 写 `test_wechat_callback_state_mismatch`

- [ ] **Step 1**: append test #4:
  ```python
  def test_wechat_callback_state_mismatch() -> None:
      """Lines 73-77: returns 401 when state not in redis."""
      from app.main import create_app
      app = create_app()
      app.state.wechat = MagicMock()
      app.state.redis = MagicMock(get=AsyncMock(return_value=None))
      app.state.db_sessionmaker = MagicMock()
      app.state.rsa_private = MagicMock()

      client = TestClient(app, raise_server_exceptions=False)
      resp = client.post("/api/v1/auth/sso/wechat/callback", json={"code": "valid", "state": "stale"})
      assert resp.status_code == 401
      assert resp.json()["detail"]["error"]["code"] == "security.invalid_state"
  ```

- [ ] **Step 2**: 跑 test 验证 PASS。

---

## Task 5: 写 `test_wechat_callback_exchange_code_usererror`

- [ ] **Step 1**: append test #5:
  ```python
  def test_wechat_callback_exchange_code_usererror() -> None:
      """Lines 83-84: returns 400 when exchange_code raises UserError."""
      from app.main import create_app
      from app.jwt_utils import UserError
      app = create_app()
      wechat_mock = MagicMock()
      wechat_mock.exchange_code = AsyncMock(side_effect=UserError("invalid", "user.wechat_invalid_code"))
      app.state.wechat = wechat_mock
      app.state.redis = MagicMock(get=AsyncMock(return_value=b"1"))
      app.state.db_sessionmaker = MagicMock()
      app.state.rsa_private = MagicMock()

      client = TestClient(app, raise_server_exceptions=False)
      resp = client.post("/api/v1/auth/sso/wechat/callback", json={"code": "bad", "state": "valid"})
      assert resp.status_code == 400
      assert resp.json()["detail"]["error"]["code"] == "user.wechat_invalid_code"
  ```

- [ ] **Step 2**: 跑 test 验证 PASS。

---

## Task 6: 写 `test_wechat_callback_fetch_userinfo_runtime_error`

- [ ] **Step 1**: append test #6:
  ```python
  def test_wechat_callback_fetch_userinfo_runtime_error() -> None:
      """Lines 90-91: returns 502 when fetch_userinfo raises WorkflowRuntimeError."""
      from app.main import create_app
      from app.jwt_utils import WorkflowRuntimeError
      app = create_app()
      wechat_mock = MagicMock()
      wechat_mock.exchange_code = AsyncMock(return_value=("tok", "openid"))
      wechat_mock.fetch_userinfo = AsyncMock(side_effect=WorkflowRuntimeError("wechat 5xx", "runtime.wechat_5xx"))
      app.state.wechat = wechat_mock
      app.state.redis = MagicMock(get=AsyncMock(return_value=b"1"))
      app.state.db_sessionmaker = MagicMock()
      app.state.rsa_private = MagicMock()

      client = TestClient(app, raise_server_exceptions=False)
      resp = client.post("/api/v1/auth/sso/wechat/callback", json={"code": "valid", "state": "valid"})
      assert resp.status_code == 502
      assert resp.json()["detail"]["error"]["code"] == "runtime.wechat_5xx"
  ```

- [ ] **Step 2**: 跑 test 验证 PASS。

---

## Task 7: 写 `test_refresh_token_missing_refresh`

- [ ] **Step 1**: append test #7:
  ```python
  def test_refresh_token_missing_refresh() -> None:
      """Lines 139-142: refresh_token returns 400 when refresh missing."""
      from app.main import create_app
      app = create_app()
      app.state.wechat = MagicMock()
      app.state.redis = MagicMock()
      app.state.db_sessionmaker = MagicMock()
      app.state.rsa_private = MagicMock()

      client = TestClient(app, raise_server_exceptions=False)
      resp = client.post("/api/v1/auth/sso/refresh", json={"refresh": ""})
      assert resp.status_code == 400
      assert resp.json()["detail"]["error"]["code"] == "user.invalid_input"
  ```

- [ ] **Step 2**: 跑 test 验证 PASS。

---

## Task 8: 写 `test_refresh_token_401_branches` (4 路径合一)

- [ ] **Step 1**: append test #8:
  ```python
  def test_refresh_token_401_branches() -> None:
      """Lines 160-166: refresh_token returns 401 in 4 cases:
      row None / revoked_at set / expires_at past / user None."""
      from app.main import create_app

      for label, row, expected_code in [
          ("row_none", None, "security.token_expired"),
          ("revoked", MagicMock(revoked_at=datetime(2020, 1, 1), expires_at=datetime(2099, 1, 1), user_id=1), "security.token_expired"),
          ("expired", MagicMock(revoked_at=None, expires_at=datetime(2020, 1, 1), user_id=1), "security.token_expired"),
          ("user_none", MagicMock(revoked_at=None, expires_at=datetime(2099, 1, 1), user_id=999), "security.invalid_token"),
      ]:
          app = create_app()
          app.state.wechat = MagicMock()
          app.state.redis = MagicMock()
          app.state.rsa_private = MagicMock()

          # session.execute → row
          exec_result = MagicMock()
          exec_result.first = MagicMock(return_value=row)
          session_mock = MagicMock()
          session_mock.__aenter__ = AsyncMock(return_value=session_mock)
          session_mock.__aexit__ = AsyncMock(return_value=False)
          session_mock.execute = AsyncMock(return_value=exec_result)
          session_mock.commit = AsyncMock()
          sm_mock = MagicMock(return_value=session_mock)
          app.state.db_sessionmaker = sm_mock

          with patch("app.routers.sso.get_user_by_id", new=AsyncMock(return_value=None if label == "user_none" else MagicMock(id=1))):
              client = TestClient(app, raise_server_exceptions=False)
              resp = client.post("/api/v1/auth/sso/refresh", json={"refresh": "valid"})
              assert resp.status_code == 401, f"label={label}"
              assert resp.json()["detail"]["error"]["code"] == expected_code, f"label={label}"
  ```

- [ ] **Step 2**: 跑 test 验证 PASS。

---

## Task 9: 写 `test_refresh_token_happy`

- [ ] **Step 1**: append test #9:
  ```python
  def test_refresh_token_happy() -> None:
      """Lines 167-180: refresh_token returns new jwt when row valid."""
      from app.main import create_app
      app = create_app()
      app.state.wechat = MagicMock()
      app.state.redis = MagicMock()
      app.state.rsa_private = MagicMock()

      valid_row = MagicMock(revoked_at=None, expires_at=datetime(2099, 1, 1), user_id=1)
      exec_result = MagicMock(first=MagicMock(return_value=valid_row))
      session_mock = MagicMock()
      session_mock.__aenter__ = AsyncMock(return_value=session_mock)
      session_mock.__aexit__ = AsyncMock(return_value=False)
      session_mock.execute = AsyncMock(return_value=exec_result)
      session_mock.add = MagicMock()
      session_mock.commit = AsyncMock()
      app.state.db_sessionmaker = MagicMock(return_value=session_mock)

      fake_user = MagicMock(id=1, to_jwt_claims=MagicMock(return_value={"name": "X"}))
      with patch("app.routers.sso.get_user_by_id", new=AsyncMock(return_value=fake_user)), \
           patch("app.routers.sso.encode_jwt", return_value=("new-jwt", "jti-2", 3600)) as mock_encode:
          client = TestClient(app, raise_server_exceptions=False)
          resp = client.post("/api/v1/auth/sso/refresh", json={"refresh": "valid"})
          assert resp.status_code == 200
          assert resp.json()["jwt"] == "new-jwt"
          assert resp.json()["expires_in"] == 3600
          assert session_mock.add.call_count == 1
          session_mock.commit.assert_awaited_once()
          assert mock_encode.call_args.args[1] == 1
  ```

- [ ] **Step 2**: 跑 test 验证 PASS。

---

## Task 10: 写 `test_jwks_endpoint`

- [ ] **Step 1**: append test #10:
  ```python
  def test_jwks_endpoint() -> None:
      """Line 186: jwks.json returns get_jwks(rsa_public) result."""
      from app.main import create_app
      app = create_app()
      app.state.wechat = MagicMock()
      app.state.redis = MagicMock()
      app.state.db_sessionmaker = MagicMock()
      app.state.rsa_private = MagicMock()
      app.state.rsa_public = MagicMock()

      with patch("app.routers.sso.get_jwks", return_value={"keys": [{"kid": "test"}]}) as mock_jwks:
          client = TestClient(app, raise_server_exceptions=False)
          resp = client.get("/api/v1/auth/sso/jwks.json")
          assert resp.status_code == 200
          assert resp.json() == {"keys": [{"kid": "test"}]}
          mock_jwks.assert_called_once()
          assert mock_jwks.call_args.args[0] is app.state.rsa_public
  ```

- [ ] **Step 2**: 跑 test 验证 PASS。

---

## Task 11: 写 `test_healthz_happy` + `test_healthz_returns_503_on_db_error`

- [ ] **Step 1**: append test #11:
  ```python
  def test_healthz_happy() -> None:
      """Lines 192-196: healthz returns 200 on db success."""
      from app.main import create_app
      from sqlalchemy import text
      app = create_app()
      app.state.wechat = MagicMock()
      app.state.redis = MagicMock()
      app.state.rsa_private = MagicMock()
      app.state.rsa_public = MagicMock()

      session_mock = MagicMock()
      session_mock.__aenter__ = AsyncMock(return_value=session_mock)
      session_mock.__aexit__ = AsyncMock(return_value=False)
      session_mock.execute = AsyncMock(return_value=MagicMock())
      app.state.db_sessionmaker = MagicMock(return_value=session_mock)

      client = TestClient(app, raise_server_exceptions=False)
      resp = client.get("/healthz")
      assert resp.status_code == 200
      assert resp.json() == {"status": "healthy"}
  ```

- [ ] **Step 2**: append test #12:
  ```python
  def test_healthz_returns_503_on_db_error() -> None:
      """Lines 197-201: healthz returns 503 on db error."""
      from app.main import create_app
      app = create_app()
      app.state.wechat = MagicMock()
      app.state.redis = MagicMock()
      app.state.rsa_private = MagicMock()
      app.state.rsa_public = MagicMock()

      session_mock = MagicMock()
      session_mock.__aenter__ = AsyncMock(return_value=session_mock)
      session_mock.__aexit__ = AsyncMock(return_value=False)
      session_mock.execute = AsyncMock(side_effect=Exception("db down"))
      app.state.db_sessionmaker = MagicMock(return_value=session_mock)

      client = TestClient(app, raise_server_exceptions=False)
      resp = client.get("/healthz")
      assert resp.status_code == 503
      body = resp.json()
      assert body["status"] == "unhealthy"
      assert "db down" in body["error"]
  ```

- [ ] **Step 3**: 跑 test 验证 PASS。

---

## Task 12: 全套验证

- [ ] **Step 1**: 跑 12 test 全套 + 100% line cov:
  ```bash
  conda run -n chatbiz pytest tests/test_routers_coverage.py --cov=app.routers.sso --cov-report=term-missing --cov-fail-under=100 -v
  ```
  Expected: 12 passed, `--cov-fail-under=100` 通过,`app/routers/sso.py` 100% line cov

- [ ] **Step 2**: 跑全 sso suite 验证无 regression:
  ```bash
  conda run -n chatbiz pytest tests/ -q
  ```
  Expected: 全部 PASS,无 regression(本 change 不动 prod code)

---

## Task 13: Commit

- [ ] **Step 1**: `git add services/sso/tests/test_routers_coverage.py`
- [ ] **Step 2**: `git commit -m "test(sso): close retrospective §4.1 row 1 — 100% line cov on routers/sso.py"
  ` with Co-Authored-By trailer
- [ ] **Step 3**: `git log -1 --format='%H %s'` 验证 commit 进 linear history
- [ ] **Step 4**: `git status` 验证 working tree clean
