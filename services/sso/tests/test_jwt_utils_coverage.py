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

import base64
import json
import uuid as _uuid
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization


@pytest.fixture(scope="module")
def rsa_keypair(tmp_path_factory: pytest.TempPathFactory):
    """Generate a real 2048-bit RSA keypair, shared across all tests in
    this module (avoids 2-3s re-generation per test).
    """
    from app.jwt_utils import load_or_generate_keypair
    tmp = tmp_path_factory.mktemp("jwt_keys")
    priv_path = Path(tmp) / "private.pem"
    pub_path = Path(tmp) / "public.pem"
    private_key, public_key = load_or_generate_keypair(priv_path, pub_path)
    return private_key, public_key


# =============================================================================
# app/jwt_utils.py::_to_pem — line 100-105 (private branch)
# =============================================================================


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


# =============================================================================
# app/jwt_utils.py::encode_jwt — line 121-133
# =============================================================================


def test_encode_jwt_happy_path(rsa_keypair) -> None:
    """Lines 121-133: encode_jwt full body (uuid jti + time now + payload
    dict + jwt.encode RS256).
    """
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


# =============================================================================
# app/jwt_utils.py::decode_jwt — line 143-156
# =============================================================================


def test_decode_jwt_happy_and_error_paths(rsa_keypair) -> None:
    """Lines 143-156: decode_jwt full body (jwt.decode + dict return +
    ExpiredSignatureError → SecurityError + JWTError → SecurityError).
    """
    from app.jwt_utils import (
        SecurityError,
        decode_jwt,
        encode_jwt,
        load_or_generate_keypair,
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
        _other_priv, other_pub = load_or_generate_keypair(
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


# =============================================================================
# app/jwt_utils.py: 4 error class __init__ bodies — line 45-46, 53-54, 61-62
# (SecurityError body at 37-38 already covered by pytest.raises above)
# =============================================================================


def test_error_class_init_bodies_assign_code_attribute() -> None:
    """Lines 45-46, 53-54, 61-62: `__init__` body of UserError,
    WorkflowRuntimeError, InternalError MUST call `super().__init__(message)`
    and set `self.code = code`. (SecurityError body 37-38 already covered
    by pytest.raises assertions in test #3 above.)
    """
    from app.jwt_utils import (
        InternalError,
        UserError,
        WorkflowRuntimeError,
    )

    # UserError default code
    ue = UserError("bad input")
    assert ue.code == "user.invalid_input"
    assert str(ue) == "bad input"
    # UserError custom code
    ue2 = UserError("custom", "user.wechat_invalid_code")
    assert ue2.code == "user.wechat_invalid_code"

    # WorkflowRuntimeError default code
    re = WorkflowRuntimeError("upstream down")
    assert re.code == "runtime.upstream_5xx"
    assert str(re) == "upstream down"
    # WorkflowRuntimeError custom code
    re2 = WorkflowRuntimeError("custom", "runtime.wechat_5xx")
    assert re2.code == "runtime.wechat_5xx"

    # InternalError default code
    ie = InternalError("db error")
    assert ie.code == "internal.server_error"
    assert str(ie) == "db error"
    # InternalError custom code
    ie2 = InternalError("custom", "internal.rsa_failure")
    assert ie2.code == "internal.rsa_failure"


# =============================================================================
# app/jwt_utils.py::load_or_generate_keypair — line 73-77 (load existing PEM)
# =============================================================================


def test_load_or_generate_keypair_loads_existing_pem(tmp_path: Path) -> None:
    """Lines 73-77: when both private and public PEM exist on disk, the
    function loads them via serialization.load_pem_*_key instead of
    regenerating. Verify by comparing private_numbers.p across load+reload.
    """
    from app.jwt_utils import load_or_generate_keypair
    priv_path = tmp_path / "private.pem"
    pub_path = tmp_path / "public.pem"
    # First call: generate (writes PEMs)
    priv1, pub1 = load_or_generate_keypair(priv_path, pub_path)
    # Second call: load (reads PEMs)
    priv2, pub2 = load_or_generate_keypair(priv_path, pub_path)
    # Same key bytes (load returns same RSA object)
    assert priv2.private_numbers().p == priv1.private_numbers().p
    assert pub2.public_numbers().n == pub1.public_numbers().n


# =============================================================================
# app/jwt_utils.py::get_jwks — line 162-163 (numbers + dict construction)
# =============================================================================


def test_get_jwks_constructs_jwk_set(rsa_keypair) -> None:
    """Lines 162-163: `get_jwks(public_key)` reads public_numbers() and
    constructs the JWK Set dict. Test calls the real get_jwks (no patch)
    to cover the public_numbers() and dict body.
    """
    from app.jwt_utils import get_jwks
    _private_key, public_key = rsa_keypair
    jwks = get_jwks(public_key, kid="test-kid-2026")
    assert "keys" in jwks
    assert isinstance(jwks["keys"], list)
    assert len(jwks["keys"]) == 1
    jwk = jwks["keys"][0]
    assert jwk["kty"] == "RSA"
    assert jwk["alg"] == "RS256"
    assert jwk["use"] == "sig"
    assert jwk["kid"] == "test-kid-2026"
    # n + e are base64url-encoded big ints
    assert "n" in jwk and "e" in jwk
    assert isinstance(jwk["n"], str) and len(jwk["n"]) > 100  # 2048-bit n
    assert jwk["e"] == "AQAB"  # 65537 base64url-encoded
