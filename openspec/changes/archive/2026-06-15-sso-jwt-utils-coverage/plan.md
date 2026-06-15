# sso-jwt-utils-coverage Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`)
> syntax for tracking.

**Goal**: 3 个新 test 走 `app/jwt_utils.py` 3 个块共 15 miss 行,达到 100%
line cov,关 `ci-coverage-sso` retrospective §3.1 + §4.1 row 2 followup。

**Architecture**: 1 个新 test 文件 `services/sso/tests/test_jwt_utils_coverage.py`
(沿用 `test_routers_coverage.py` 已有 pattern)。3 test 拆 3 块:`_to_pem`
private branch / `encode_jwt` body / `decode_jwt` body + 2 error path。
真 RSA keypair 走 `load_or_generate_keypair`(已 100% 覆盖)共享 1 个
module-level fixture,2-3s 总时间。0 行 prod code 改动。

**Tech Stack**: Python 3.12 + cryptography(rsa / serialization) + python-jose
(jwt / long_to_base64) + pytest 8.x + pytest-cov 6.x + conda env `chatbiz`

---

## Task 1: 写 `test_to_pem_private_key_path`

**Files:**
- Create: `services/sso/tests/test_jwt_utils_coverage.py`
- Test: `services/sso/tests/test_jwt_utils_coverage.py::test_to_pem_private_key_path`

- [ ] **Step 1**: 创建 test 文件头 + module-level fixture(共享 RSA keypair)
```python
"""Coverage-gap tests for sso/jwt_utils.py.

Per `openspec/changes/archive/2026-06-15-ci-coverage-sso/retrospective.md`
§3.1 + §4.1 row 2, `app/jwt_utils.py` had 15 missing lines across
3 blocks. This file adds 3 tests to close the gap to 100% line cov.

Pattern follows `services/sso/tests/test_routers_coverage.py`
(commit 23018e8). Uses REAL RSA keypair via load_or_generate_keypair
(already 100% covered in test_coverage_followup.py) — round-trip
signing/verification is the core property and cannot be tested with
mocks.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization


@pytest.fixture(scope="module")
def rsa_keypair(tmp_path_factory: pytest.TempPathFactory):
    """Generate a real 2048-bit RSA keypair, shared across all tests in
    this module (avoids 2-3s re-generation per test)."""
    from app.jwt_utils import load_or_generate_keypair
    tmp = tmp_path_factory.mktemp("jwt_keys")
    priv_path = Path(tmp) / "private.pem"
    pub_path = Path(tmp) / "public.pem"
    private_key, public_key = load_or_generate_keypair(priv_path, pub_path)
    return private_key, public_key
```

- [ ] **Step 2**: append test #1
```python
def test_to_pem_private_key_path(rsa_keypair) -> None:
    """Lines 100-105: `_to_pem(RSAPrivateKey)` returns PKCS8 PEM bytes."""
    from app.jwt_utils import _to_pem
    private_key, _public_key = rsa_keypair
    pem = _to_pem(private_key)
    assert isinstance(pem, bytes)
    assert b"-----BEGIN PRIVATE KEY-----" in pem
    assert b"-----END PRIVATE KEY-----" in pem
    # Round-trip: load back
    reloaded = serialization.load_pem_private_key(pem, password=None)
    # Same key bytes (compare private_numbers)
    assert reloaded.private_numbers().p == private_key.private_numbers().p
```

- [ ] **Step 3**: 跑 test 验证 PASS:
```bash
cd /Users/paulwang/work/ChatBiz/services/sso && conda run -n chatbiz pytest tests/test_jwt_utils_coverage.py::test_to_pem_private_key_path -v --no-cov
```
Expected: 1 passed

---

## Task 2: 写 `test_encode_jwt_happy_path`

- [ ] **Step 1**: append test #2
```python
def test_encode_jwt_happy_path(rsa_keypair) -> None:
    """Lines 121-133: encode_jwt full body (uuid jti + time now + payload
    dict + jwt.encode RS256)."""
    import uuid as _uuid
    from app.jwt_utils import encode_jwt
    private_key, _public_key = rsa_keypair
    token, jti, expires_in = encode_jwt(
        private_key, user_id=1, user_claims={"name": "Alice"},
        expires_in=3600,
    )
    # Tuple shape
    assert isinstance(token, str)
    assert isinstance(jti, str)
    assert expires_in == 3600
    # JWT 3-segment shape
    assert token.count(".") == 2
    # JTI is UUID4
    _uuid.UUID(jti)  # raises if not valid UUID
    # Decode payload (no signature verification, just structure check)
    import base64
    import json
    payload_b64 = token.split(".")[1]
    # Pad base64
    payload_b64 += "=" * (-len(payload_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    assert payload["sub"] == "1"
    assert payload["iss"] == "https://sso.chatbiz.local"
    assert payload["aud"] == "chatbiz-web"
    assert payload["name"] == "Alice"
    assert payload["jti"] == jti
    assert payload["exp"] - payload["iat"] == 3600
```

- [ ] **Step 2**: 跑 test 验证 PASS。

---

## Task 3: 写 `test_decode_jwt_happy_and_error_paths`

- [ ] **Step 1**: append test #3 (3 子路径合一)
```python
def test_decode_jwt_happy_and_error_paths(rsa_keypair) -> None:
    """Lines 143-156: decode_jwt full body (jwt.decode + dict return +
    ExpiredSignatureError → SecurityError + JWTError → SecurityError)."""
    from app.jwt_utils import (
        SecurityError, decode_jwt, encode_jwt, load_or_generate_keypair,
    )
    private_key, public_key = rsa_keypair

    # --- Sub-test 1: round-trip happy path ---
    token, jti, _exp = encode_jwt(
        private_key, user_id=1, user_claims={"name": "Alice"},
    )
    claims = decode_jwt(token, public_key)
    assert isinstance(claims, dict)
    assert claims["sub"] == "1"
    assert claims["iss"] == "https://sso.chatbiz.local"
    assert claims["aud"] == "chatbiz-web"
    assert claims["name"] == "Alice"
    assert claims["jti"] == jti
    assert "iat" in claims and "exp" in claims

    # --- Sub-test 2: wrong public key → SecurityError("security.invalid_token") ---
    tmp = Path(__file__).parent / "_tmp_different_key"
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        other_priv, other_pub = load_or_generate_keypair(
            tmp / "other_private.pem", tmp / "other_public.pem",
        )
        with pytest.raises(SecurityError) as exc_info:
            decode_jwt(token, other_pub)
        assert exc_info.value.code == "security.invalid_token"
        assert "invalid token" in str(exc_info.value)
    finally:
        for f in tmp.iterdir():
            f.unlink()
        tmp.rmdir()

    # --- Sub-test 3: expired token → SecurityError("security.token_expired") ---
    expired_token, _, _ = encode_jwt(
        private_key, user_id=1, user_claims={"name": "Alice"},
        expires_in=-10,
    )
    with pytest.raises(SecurityError) as exc_info:
        decode_jwt(expired_token, public_key)
    assert exc_info.value.code == "security.token_expired"
    assert str(exc_info.value) == "token expired"
```

- [ ] **Step 2**: 跑 test 验证 PASS。

---

## Task 4: 全套验证

- [ ] **Step 1**: 跑 3 test + 100% line cov:
```bash
conda run -n chatbiz pytest tests/test_jwt_utils_coverage.py --cov=app.jwt_utils --cov-report=term-missing -v
```
Expected: 3 passed, `app/jwt_utils.py` 100% line cov

- [ ] **Step 2**: 跑全 sso suite 验证无 regression:
```bash
conda run -n chatbiz pytest tests/ -q
```
Expected: 全部 PASS,无 regression

---

## Task 5: Commit

- [ ] **Step 1**: `git add services/sso/tests/test_jwt_utils_coverage.py`
- [ ] **Step 2**: `git commit -m "test(sso): close retrospective §4.1 row 2 — 100% line cov on jwt_utils.py"
  ` with Co-Authored-By trailer
- [ ] **Step 3**: `git log -1 --format='%H %s'` 验证 commit 进 linear history
- [ ] **Step 4**: `git status` 验证 working tree clean
