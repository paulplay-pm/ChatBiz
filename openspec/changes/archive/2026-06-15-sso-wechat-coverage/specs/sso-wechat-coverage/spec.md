<!--
Delta spec for sso-wechat-coverage change.

Cap: sso-wechat-coverage
Source: openspec/changes/archive/2026-06-15-ci-coverage-sso/retrospective.md §3.1 + §4.1

本 change 只补 test 走 app/wechat.py 5 path 共 8 miss 行,达到 100% line cov。
0 行 prod code 改动。
-->

## ADDED Requirements

### Requirement: `exchange_code` 必须有 TimeoutException → WorkflowRuntimeError 测试覆盖

MUST 至少 1 个单元测试覆盖 `app/wechat.py::WeChatClient.exchange_code`
在 `httpx.AsyncClient.get` raises `httpx.TimeoutException` 时转换为
`WorkflowRuntimeError(code="runtime.wechat_timeout")` 的路径(行 71-74)。

#### Scenario: exchange_code 在 httpx.TimeoutException → runtime.wechat_timeout
- **WHEN** `WeChatClient(corp_id="x", agent_id="y", corp_secret="z",
  redirect_uri="http://r").exchange_code("code")` 在 `_available=True` +
  `httpx.AsyncClient.get = AsyncMock(side_effect=httpx.TimeoutException("read timeout"))`
  环境下被 `asyncio.run` 调用
- **THEN** raises `WorkflowRuntimeError`,`exc.code == "runtime.wechat_timeout"`,
  `str(exc)` 含 "timeout"

---

### Requirement: `exchange_code` 必须有 HTTPError → WorkflowRuntimeError 测试覆盖

MUST 至少 1 个单元测试覆盖 `app/wechat.py::WeChatClient.exchange_code`
在 `httpx.AsyncClient.get` raises `httpx.HTTPError` 时转换为
`WorkflowRuntimeError(code="runtime.wechat_5xx")` 的路径(行 75-77)。

#### Scenario: exchange_code 在 httpx.HTTPError → runtime.wechat_5xx
- **WHEN** `WeChatClient.exchange_code("code")` 在 `_available=True` +
  `httpx.AsyncClient.get = AsyncMock(side_effect=httpx.HTTPError("connection error"))`
  环境下被 `asyncio.run` 调用
- **THEN** raises `WorkflowRuntimeError`,`exc.code == "runtime.wechat_5xx"`,
  `str(exc)` 含 "HTTP error"

---

### Requirement: `exchange_code` 必须有其他 errcode → WorkflowRuntimeError 测试覆盖

MUST 至少 1 个单元测试覆盖 `app/wechat.py::WeChatClient.exchange_code`
在企微响应 `errcode` 非 0 且**不**是 40029/40163 时转换为
`WorkflowRuntimeError(code="runtime.wechat_5xx")` 的路径(行 88-90)。

#### Scenario: exchange_code 在其他 errcode → runtime.wechat_5xx
- **WHEN** `WeChatClient.exchange_code("code")` 在 `_available=True` +
  `httpx.AsyncClient.get` 返 `{"errcode": 50005, "errmsg": "freq limit"}` 环境下
  被 `asyncio.run` 调用
- **THEN** raises `WorkflowRuntimeError`,`exc.code == "runtime.wechat_5xx"`,
  `str(exc)` 含 "50005" 跟 "freq limit"

---

### Requirement: `exchange_code` 必须有响应缺字段 → WorkflowRuntimeError 测试覆盖

MUST 至少 1 个单元测试覆盖 `app/wechat.py::WeChatClient.exchange_code`
在企微响应 `errcode=0` 但缺 `access_token` 或 `openid` 字段时转换为
`WorkflowRuntimeError(code="runtime.wechat_5xx")` 的路径(行 95-97)。

#### Scenario: exchange_code 在响应缺 access_token → runtime.wechat_5xx
- **WHEN** `WeChatClient.exchange_code("code")` 在 `_available=True` +
  `httpx.AsyncClient.get` 返 `{"errcode": 0, "openid": "openid-1"}`(缺
  `access_token`)环境下被 `asyncio.run` 调用
- **THEN** raises `WorkflowRuntimeError`,`exc.code == "runtime.wechat_5xx"`,
  `str(exc)` 含 "缺字段"

---

### Requirement: `fetch_userinfo` 必须有 httpx exception → WorkflowRuntimeError 测试覆盖

MUST 至少 1 个单元测试覆盖 `app/wechat.py::WeChatClient.fetch_userinfo`
在 `httpx.AsyncClient.get` raises `httpx.HTTPError`(或 `TimeoutException`)
时通过 try/except 块转换为 `WorkflowRuntimeError(code="runtime.wechat_5xx")`
的路径(行 114-115)。本要求 MUST 走真 `httpx.HTTPError` side_effect
(让 try/except 块真触发),**不**是 mock `WeChatClient.fetch_userinfo`
直接 raise(那会绕过 try/except 块)。

#### Scenario: fetch_userinfo 在 httpx.HTTPError → runtime.wechat_5xx
- **WHEN** `WeChatClient(corp_id="x", agent_id="y", corp_secret="z",
  redirect_uri="http://r").fetch_userinfo("tok", "openid-1")` 在
  `httpx.AsyncClient.get = AsyncMock(side_effect=httpx.HTTPError("conn refused"))`
  环境下被 `asyncio.run` 调用
- **THEN** raises `WorkflowRuntimeError`,`exc.code == "runtime.wechat_5xx"`,
  `str(exc)` 含 "userinfo"

---

### Requirement: wechat.py 100% line cov 必须由 5 个新 test 达成

MUST 至少 5 个新 test 达成 `app/wechat.py` 100% line cov(51/51 statements,
0 missing)。`pytest tests/test_wechat_coverage.py --cov=app.wechat
--cov-report=term-missing` MUST 报告 100% line cov,无 `# pragma: no cover`
标注引入 prod code。

#### Scenario: 5 test 全 PASS + 100% line cov
- **WHEN** `conda run -n chatbiz pytest tests/test_wechat_coverage.py
  --cov=app.wechat --cov-report=term-missing -v` 在 chatbiz env 跑
- **THEN** 5 passed, 0 failed, `app/wechat.py` 报告显示 100% line cov,
  0 missing
