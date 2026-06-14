"""V6a SSO service: RS256 JWT 签名 + JWKS + 4 错误边界(eng-review Quality #3 锁定).

- encode_jwt: 用 RSA 私钥签 RS256 JWT
- decode_jwt: 用 RSA 公钥验 RS256 JWT
- get_jwks: 暴露公钥 JWKS(给 V1 OIDC 客户端用)
- 4 错误类:SecurityError / UserError / WorkflowRuntimeError / InternalError
"""
from __future__ import annotations

import base64
import json
import time
import uuid
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt
from jose.utils import long_to_base64

# V4 spec 锁的 issuer + audience(对齐 OIDC v1 / SAML v2 后续)
DEFAULT_ISSUER = "https://sso.chatbiz.local"
DEFAULT_AUDIENCE = "chatbiz-web"
DEFAULT_ACCESS_TOKEN_EXPIRE = 60 * 60  # 1h
DEFAULT_REFRESH_TOKEN_EXPIRE = 7 * 24 * 60 * 60  # 7d
DEFAULT_KEY_SIZE = 2048

ALG = "RS256"


# --- 4 错误边界(eng-review Quality #3 锁定) ---
class SecurityError(Exception):
    """401 / 403 — 验签失败 / state 失配 / token 失效"""

    def __init__(self, message: str, code: str = "security.unauthorized"):
        super().__init__(message)
        self.code = code


class UserError(Exception):
    """400 — 用户参数不全(code 缺失 / state 失配)"""

    def __init__(self, message: str, code: str = "user.invalid_input"):
        super().__init__(message)
        self.code = code


class WorkflowRuntimeError(Exception):
    """502 / 504 — 企微 / OIDC IdP 5xx / timeout"""

    def __init__(self, message: str, code: str = "runtime.upstream_5xx"):
        super().__init__(message)
        self.code = code


class InternalError(Exception):
    """500 — 后端内部错(SQLAlchemy / RSA 生成失败 / 未知)"""

    def __init__(self, message: str, code: str = "internal.server_error"):
        super().__init__(message)
        self.code = code


# --- RSA 密钥加载/生成 ---
def load_or_generate_keypair(
    private_path: Path,
    public_path: Path,
    key_size: int = DEFAULT_KEY_SIZE,
) -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    """首次启动 generate 2048-bit RSA + 持久化;后续启动 load。"""
    if private_path.exists() and public_path.exists():
        private_pem = private_path.read_bytes()
        private_key = serialization.load_pem_private_key(private_pem, password=None)
        public_pem = public_path.read_bytes()
        public_key = serialization.load_pem_public_key(public_pem)
        return private_key, public_key  # type: ignore[return-value]

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    private_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.parent.mkdir(parents=True, exist_ok=True)
    private_path.write_bytes(private_pem)
    public_path.write_bytes(public_pem)
    return private_key, public_key


# --- JWT encode/decode ---
def _to_pem(key: rsa.RSAPrivateKey | rsa.RSAPublicKey) -> bytes:
    if isinstance(key, rsa.RSAPrivateKey):
        return key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    return key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def encode_jwt(
    private_key: rsa.RSAPrivateKey,
    user_id: int,
    user_claims: dict[str, Any],
    expires_in: int = DEFAULT_ACCESS_TOKEN_EXPIRE,
    issuer: str = DEFAULT_ISSUER,
    audience: str = DEFAULT_AUDIENCE,
) -> tuple[str, str, int]:
    """返回 (jwt, jti, expires_in)。"""
    jti = str(uuid.uuid4())
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + expires_in,
        "iss": issuer,
        "aud": audience,
        "jti": jti,
        **user_claims,
    }
    token = jwt.encode(payload, _to_pem(private_key).decode(), algorithm=ALG)
    return token, jti, expires_in


def decode_jwt(
    token: str,
    public_key: rsa.RSAPublicKey,
    issuer: str = DEFAULT_ISSUER,
    audience: str = DEFAULT_AUDIENCE,
) -> dict[str, Any]:
    """decode + 验签 + 验 iss/aud。失败抛 SecurityError。"""
    try:
        claims = jwt.decode(
            token,
            _to_pem(public_key).decode(),
            algorithms=[ALG],
            issuer=issuer,
            audience=audience,
            options={"verify_aud": True, "verify_iss": True, "verify_exp": True},
        )
        return dict(claims)
    except jwt.ExpiredSignatureError as e:
        raise SecurityError("token expired", "security.token_expired") from e
    except jwt.JWTError as e:
        raise SecurityError(f"invalid token: {e}", "security.invalid_token") from e


# --- JWKS 端点(V1 OIDC 客户端用) ---
def get_jwks(public_key: rsa.RSAPublicKey, kid: str = "chatbiz-sso-2026") -> dict:
    """JWK Set 暴露公钥(V6a V1 OIDC 客户端用)。"""
    numbers = public_key.public_numbers()
    return {
        "keys": [
            {
                "kty": "RSA",
                "alg": ALG,
                "use": "sig",
                "kid": kid,
                "n": long_to_base64(numbers.n).decode(),
                "e": long_to_base64(numbers.e).decode(),
            }
        ]
    }
