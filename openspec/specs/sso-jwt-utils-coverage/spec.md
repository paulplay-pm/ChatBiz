# sso-jwt-utils-coverage Specification

## Purpose
TBD - created by archiving change sso-jwt-utils-coverage. Update Purpose after archive.
## Requirements
### Requirement: `_to_pem` 私有分支必须有测试覆盖

MUST 至少 1 个单元测试覆盖 `app/jwt_utils.py::_to_pem` 对 `RSAPrivateKey`
输入的分支(行 100-105)。Test 直接调 `_to_pem(real_private_key)` 验证
返 PEM bytes 含 `b"-----BEGIN PRIVATE KEY-----"`。公钥分支由 `get_jwks`
间接覆盖(100%)+ encode_jwt/decode_jwt body 调用,本要求不重复覆盖。

#### Scenario: `_to_pem` 接收 RSA private key 返 PKCS8 PEM
- **WHEN** `app.jwt_utils._to_pem(RSAPrivateKey_instance)` 在 chatbiz env
  + 2048-bit 真 RSA private key 环境下调用
- **THEN** 返 bytes 含 `b"-----BEGIN PRIVATE KEY-----"` 跟
  `b"-----END PRIVATE KEY-----"` 标记 + PKCS8 DER 内容可被
  `serialization.load_pem_private_key` 反序列化回原 key

---

### Requirement: `encode_jwt` 必须有 happy path 测试覆盖

MUST 至少 1 个单元测试覆盖 `app/jwt_utils.py::encode_jwt` 完整 body(行
121-133,含 `uuid.uuid4()` jti 生成 + `int(time.time())` now + payload
dict 构造 + `jwt.encode` RS256 签名)。Test 用真 RSA private key +
sample user_id=1 + user_claims={"name": "Alice"} 调 encode_jwt,验证返
`(token, jti, expires_in)` tuple,jti 是 UUID4 格式,token 是 str 用 `.`
分 3 段(JWT header.payload.signature)。

#### Scenario: encode_jwt 返 RS256 JWT tuple
- **WHEN** `app.jwt_utils.encode_jwt(rsa_private_key, user_id=1,
  user_claims={"name": "Alice"}, expires_in=3600)` 在 chatbiz env 调用
- **THEN** 返 `(token, jti, expires_in)` tuple,token 是 str 含 2 个 `.`
  分 3 段,jti 是 36-char UUID4 string(含 `-`),expires_in == 3600;
  payload 解析后含 `sub="1"`, `iss="https://sso.chatbiz.local"`,
  `aud="chatbiz-web"`, `exp == iat + 3600`, `name="Alice"`

---

### Requirement: `decode_jwt` 必须有 happy + 2 error path 测试覆盖

MUST 至少 1 个单元测试(内含 3 子路径)覆盖 `app/jwt_utils.py::decode_jwt`
完整 body(行 143-156,含 `jwt.decode` 验签 + `dict(claims)` 返回 +
`jwt.ExpiredSignatureError` 转换 + `jwt.JWTError` 转换)。3 子路径:
1. **happy**: encode → decode round-trip 返 claims dict 含原 sub/iat/exp
2. **invalid**: 用不同 RSA 公钥 decode 合法 token → raises
   `SecurityError(code="security.invalid_token")`
3. **expired**: encode `expires_in=-1` 获 exp=past → decode raises
   `SecurityError(code="security.token_expired")`

#### Scenario: decode_jwt round-trip 返 claims dict
- **WHEN** `decode_jwt(token_from_encode_jwt, rsa_public_key)` 在
  encode → decode 同 keypair round-trip 环境下调用
- **THEN** 返 dict 含 `sub == "1"`, `iss == "https://sso.chatbiz.local"`,
  `aud == "chatbiz-web"`, `name == "Alice"`, `iat`, `exp`, `jti` 字段

#### Scenario: decode_jwt 错公钥 raises security.invalid_token
- **WHEN** `decode_jwt(token_signed_by_key_A, rsa_public_key_B)` 在
  keypair A 签的 token + keypair B 验签环境下调用
- **THEN** raises `SecurityError`, `exc.code == "security.invalid_token"`,
  `str(exc)` 含 "invalid token"

#### Scenario: decode_jwt 过期 token raises security.token_expired
- **WHEN** `decode_jwt(token_with_exp_in_past, rsa_public_key)` 在
  `encode_jwt(expires_in=-1)` 获 exp=past 的 token 环境下调用
- **THEN** raises `SecurityError`, `exc.code == "security.token_expired"`,
  `str(exc) == "token expired"`

---

### Requirement: jwt_utils.py 100% line cov 必须由 3 个新 test 达成

MUST 至少 3 个新 test 达成 `app/jwt_utils.py` 100% line cov(70/70 statements,
0 missing)。`pytest tests/test_jwt_utils_coverage.py --cov=app.jwt_utils
--cov-report=term-missing` MUST 报告 100% line cov,无 `# pragma: no cover`
标注引入 prod code。

#### Scenario: 3 test 全 PASS + 100% line cov
- **WHEN** `conda run -n chatbiz pytest tests/test_jwt_utils_coverage.py
  --cov=app.jwt_utils --cov-report=term-missing -v` 在 chatbiz env 跑
- **THEN** 3 passed(2 顶层 test + 1 parametrize 3 子), 0 failed,
  `app/jwt_utils.py` 报告显示 100% line cov, 0 missing

