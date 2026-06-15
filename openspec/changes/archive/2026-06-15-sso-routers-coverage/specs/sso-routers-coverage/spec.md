<!--
Delta spec for sso-routers-coverage change.

Cap: sso-routers-coverage
Source: openspec/changes/archive/2026-06-15-ci-coverage-sso/retrospective.md §3.1 + §4.1

本 change 只补 test 走 app/routers/sso.py 4 endpoint 全部 70 miss 行,达到
100% line cov。0 行 prod code 改动。
-->

## ADDED Requirements

### Requirement: wechat_initiate 端点必须有 happy path 单元测试覆盖

MUST 至少 1 个单元测试覆盖 `wechat_initiate` 端点的全部 happy path 行(51-57,
`wechat._available == True` 时返回 `{authorize_url, state}`)。Test 通过 TestClient
包装 `create_app()` + 注入 `app.state.wechat` (含 `get_authorize_url=Mock`) +
`app.state.redis` (含 `setex=AsyncMock`) + `app.state.db_sessionmaker()`
返回 AsyncMock session context manager。

#### Scenario: wechat_initiate 在 wechat 可用时返回 authorize_url + state
- **WHEN** `POST /api/v1/auth/sso/wechat/initiate` 在 wechat `_available=True`
  + redis.setex AsyncMock + db session context manager AsyncMock 环境下调用
- **THEN** 响应 200 + body `{"authorize_url": <wechat.get_authorize_url 返回值>,
  "state": <16-byte secrets token_urlsafe>}`;redis.setex 被以
  `("sso:state:{state}", 300, "1")` 等待调用 1 次;write_audit_event 被以
  `event_type="initiate"` 等待调用 1 次

---

### Requirement: wechat_initiate 端点必须有 wechat 不可用 503 测试覆盖

MUST 至少 1 个单元测试覆盖 `wechat_initiate` 端点在 `wechat._available == False`
时返回 503 加 envelope `{"error": {"code": "sso.wechat_unavailable", "message": "企微服务未配置"}}`
(行 41)。

#### Scenario: wechat 不可用时返回 503
- **WHEN** `POST /api/v1/auth/sso/wechat/initiate` 在 `app.state.wechat._available = False` 环境下调用
- **THEN** 响应 503 + body `{"detail": {"error": {"code": "sso.wechat_unavailable",
  "message": "企微服务未配置"}}}`;redis.setex NOT awaited

---

### Requirement: wechat_callback 端点必须有 happy path 单元测试覆盖

MUST 至少 1 个单元测试覆盖 `wechat_callback` 端点的全部 happy path 行
(63-131,含 `code`/`state` 非空 + state 命中 redis + exchange_code 成功 +
fetch_userinfo 成功 + upsert + mint JWT + SsoSession add + audit + commit +
return)。Test 通过 TestClient + 注入 `app.state.wechat` (exchange_code +
fetch_userinfo AsyncMock 返回 `(access_token, openid)` + `{"name": "Alice"}`) +
`app.state.redis` (get+delete AsyncMock) + `app.state.db_sessionmaker`
+ `app.state.rsa_private` MagicMock;`upsert_sso_user` 和 `encode_jwt`
patch 跳过(已由 `test_coverage_followup.py` 覆盖)。

#### Scenario: wechat_callback 全部 mock 命中时返回 jwt + refresh + user
- **WHEN** `POST /api/v1/auth/sso/wechat/callback` body `{"code": "valid", "state": "valid"}`
  在 state 命中 redis + exchange_code 成功 + fetch_userinfo 成功环境下调用
- **THEN** 响应 200 + body `{"jwt": <encode_jwt 返回 token>, "refresh":
  <48-byte secrets token_urlsafe>, "expires_in": 3600, "user": {"id": 1,
  "name": "Alice", "email": ..., "role": "user"}}`;SsoSession 被 add +
  session.commit 被 await 1 次;write_audit_event 被以
  `event_type="login_success", user_id=1` await 1 次

---

### Requirement: wechat_callback 端点必须有缺 code/state 400 测试覆盖

MUST 至少 1 个单元测试覆盖 `wechat_callback` 端点在 body 缺 `code` 或 `state`
时返回 400(行 66-70)。

#### Scenario: 缺 code 或 state 时返回 400
- **WHEN** `POST /api/v1/auth/sso/wechat/callback` body `{"code": "", "state": ""}`
  被调用
- **THEN** 响应 400 + body `{"detail": {"error": {"code":
  "user.invalid_input", "message": "缺 code/state"}}}`;redis.get 和
  wechat.exchange_code 都 NOT awaited

---

### Requirement: wechat_callback 端点必须有 state 失配 401 测试覆盖

MUST 至少 1 个单元测试覆盖 `wechat_callback` 端点在 `redis.get(state_key)`
返回 None/空时返回 401(行 73-77)。

#### Scenario: state 不在 redis 中时返回 401
- **WHEN** `POST /api/v1/auth/sso/wechat/callback` body
  `{"code": "valid", "state": "stale-state"}` 在 redis.get 返回 None 环境下调用
- **THEN** 响应 401 + body `{"detail": {"error": {"code":
  "security.invalid_state", "message": "state 失配或过期"}}}`;
  redis.delete NOT awaited;wechat.exchange_code NOT awaited

---

### Requirement: wechat_callback 端点必须有 exchange_code UserError → 400 测试覆盖

MUST 至少 1 个单元测试覆盖 `wechat_callback` 端点在 `wechat.exchange_code`
raises `UserError` 时返回 400(行 83-84)。

#### Scenario: exchange_code raise UserError → 400
- **WHEN** `POST /api/v1/auth/sso/wechat/callback` body 含有效 code/state
  在 wechat.exchange_code raises `UserError("...", "user.wechat_invalid_code")`
  环境下调用
- **THEN** 响应 400 + body `{"detail": {"error": {"code":
  "user.wechat_invalid_code", "message": "..."}}}`;fetch_userinfo NOT awaited

---

### Requirement: wechat_callback 端点必须有 exchange_code WorkflowRuntimeError → 502 测试覆盖

MUST 至少 1 个单元测试覆盖 `wechat_callback` 端点在 `wechat.exchange_code`
raises `WorkflowRuntimeError` 时返回 502(行 85-86)。

#### Scenario: exchange_code raise WorkflowRuntimeError → 502
- **WHEN** `POST /api/v1/auth/sso/wechat/callback` body 含有效 code/state
  在 wechat.exchange_code raises `WorkflowRuntimeError("...",
  "runtime.wechat_5xx")` 环境下调用
- **THEN** 响应 502 + body `{"detail": {"error": {"code":
  "runtime.wechat_5xx", "message": "..."}}}`;fetch_userinfo NOT awaited

---

### Requirement: wechat_callback 端点必须有 fetch_userinfo WorkflowRuntimeError → 502 测试覆盖

MUST 至少 1 个单元测试覆盖 `wechat_callback` 端点在 `wechat.fetch_userinfo`
raises `WorkflowRuntimeError` 时返回 502(行 90-91)。

#### Scenario: fetch_userinfo raise WorkflowRuntimeError → 502
- **WHEN** `POST /api/v1/auth/sso/wechat/callback` body 含有效 code/state
  在 wechat.fetch_userinfo raises `WorkflowRuntimeError("...",
  "runtime.wechat_5xx")` 环境下调用
- **THEN** 响应 502 + body `{"detail": {"error": {"code":
  "runtime.wechat_5xx", "message": "..."}}}`;upsert_sso_user NOT awaited

---

### Requirement: refresh_token 端点必须有缺 refresh 400 测试覆盖

MUST 至少 1 个单元测试覆盖 `refresh_token` 端点在 body 缺 `refresh` 时
返回 400(行 139-142)。

#### Scenario: 缺 refresh 时返回 400
- **WHEN** `POST /api/v1/auth/sso/refresh` body `{"refresh": ""}` 被调用
- **THEN** 响应 400 + body `{"detail": {"error": {"code":
  "user.invalid_input", "message": "缺 refresh"}}}`;session.execute NOT
  awaited

---

### Requirement: refresh_token 端点必须有 401 测试覆盖

MUST 至少 1 个单元测试覆盖 `refresh_token` 端点在以下 4 情况中任一发生时
返回 401(行 160-166):
1. `session.execute(...).first()` 返回 None
2. row.revoked_at 非 None
3. row.expires_at < datetime.utcnow()
4. `get_user_by_id(session, row.user_id)` 返回 None

可用 parametrize 或单 test 内 sub-test 覆盖全部 4 路径。

#### Scenario: refresh row 缺失/revoked/expired/user 缺失 → 401
- **WHEN** `POST /api/v1/auth/sso/refresh` body `{"refresh": "valid"}`
  在 select 命中 4 路径之一(row=None / revoked_at 已设 / expires_at 已过
  / get_user_by_id 返回 None)环境下调用
- **THEN** 响应 401 + body `{"detail": {"error": {"code":
  "security.token_expired" 或 "security.invalid_token", "message": "..."}}}`;
  encode_jwt NOT patched(无新 JWT 签发)

---

### Requirement: refresh_token 端点必须有 happy path 测试覆盖

MUST 至少 1 个单元测试覆盖 `refresh_token` 端点在 select 命中有效 row +
get_user_by_id 返回有效 user 时返回新 JWT(行 167-180)。

#### Scenario: refresh 命中有效 row 时返回新 jwt
- **WHEN** `POST /api/v1/auth/sso/refresh` body `{"refresh": "valid"}`
  在 select 返回有效 row(revoked_at=None, expires_at > utcnow) +
  get_user_by_id 返回 user 环境下调用
- **THEN** 响应 200 + body `{"jwt": <encode_jwt 返回 token>,
  "expires_in": 3600}`;SsoSession 被 add 1 次;session.commit 被 await 1 次

---

### Requirement: refresh_token 端点必须有 first 返回 coroutine async session 路径测试覆盖

MUST 至少 1 个单元测试覆盖 `refresh_token` 端点在 `session.execute(...).first()`
返回 coroutine object(异步 session 模式)时走 `if asyncio.iscoroutine(first): row = await first`
分支(行 156-158)。Mock MUST 返回 bare coroutine,**不**是 Task(因
`asyncio.iscoroutine` 不通过 Task)。

#### Scenario: first 返回 coroutine 时正确 await
- **WHEN** `POST /api/v1/auth/sso/refresh` body `{"refresh": "valid"}`
  在 select 返回 row 为 valid + `first()` 返回 bare coroutine(resolves to
  valid row)环境下调用
- **THEN** 响应 200 + body `{"jwt": <encode_jwt 返回 token>,
  "expires_in": 3600}`;SsoSession 被 add 1 次;session.commit 被 await 1 次

---

### Requirement: jwks.json 端点必须有 happy path 测试覆盖

MUST 至少 1 个单元测试覆盖 `jwks` 端点返回 `get_jwks(rsa_public)` 的结果
(行 186)。`get_jwks` 本体 patch,test 只验证 routers/sso 中调用 + 返回值。

#### Scenario: jwks.json 返回 jwks dict
- **WHEN** `GET /api/v1/auth/sso/jwks.json` 在 `app.state.rsa_public`
  MagicMock + `app.routers.sso.get_jwks` patched 返回 `{"keys": [{"kid": "..."}]}`
  环境下调用
- **THEN** 响应 200 + body `{"keys": [{"kid": "..."}]}`;get_jwks 被以
  `(<rsa_public>,)` 调用 1 次

---

### Requirement: healthz 端点必须有 happy path + 503 测试覆盖

MUST 至少 2 个单元测试覆盖 `healthz` 端点在 `session.execute(text("SELECT 1"))`
成功时返回 200(行 192-196),失败时返回 503(行 197-201)。

#### Scenario: healthz happy path
- **WHEN** `GET /api/v1/auth/sso/healthz` 在 db_sessionmaker 正常返回 + session.execute
  成功(AsyncMock 不 raise)环境下调用
- **THEN** 响应 200 + body `{"status": "healthy"}`

#### Scenario: healthz 503 on db error
- **WHEN** `GET /api/v1/auth/sso/healthz` 在 session.execute raises `Exception("db down")`
  环境下调用
- **THEN** 响应 503 + body `{"status": "unhealthy", "error": "db down"}`

---

### Requirement: routers/sso.py 100% line cov 必须由 13 个新 test 达成

MUST 至少 13 个新 test 达成 `app/routers/sso.py` 100% line cov(97/97 statements,
0 missing)。`pytest tests/test_routers_coverage.py --cov=app.routers.sso`
MUST 报告 100% line cov,无 `# pragma: no cover` 标注引入 prod code。

#### Scenario: 13 test 全 PASS + 100% line cov
- **WHEN** `conda run -n chatbiz pytest tests/test_routers_coverage.py
  --cov=app.routers.sso --cov-report=term-missing -v`
  在 chatbiz env 跑
- **THEN** 18 passed(13 test + 4 parametrize 子 + 1 init 503), 0 failed,
  `app/routers/sso.py` 报告显示 100% line cov, 0 missing
