## Why

`ci-coverage-sso` (commit 5d895e6) apply 后 `app/routers/sso.py` 仍 **70
missing lines**(占总 sso miss 65 中的 41,后续摸底涨到 70 — audit 写入
+ select execute 内部 + json body parse 等几行没在 retrospective 估时
数)。retrospective §3.1 + §4.1 把 `routers/sso.py` 列为最大头,估
"8-10 endpoint test, ~1-1.5 hours"。

现在处理是为 **sso service 100% line cov 铺平最后一段路**(`jwt_utils`
+ `wechat` + `user` 24 miss 仍 followup,但本 change 关闭 70/94 = 74%
sso miss)。

参考源:
- `docs/architecture.md` §4.3.2(Lead Agent 委派模式)
- 设计 doc `GSTACK REVIEW REPORT` Quality #3(4 错误边界)
- 仓库内 4 个 archived coverage change(`coverage-improvement` /
  `gateway-scanner-coverage-matrix` / `llm-client-retry-coverage` /
  `audit-and-isolation-full-cov`)的 6-artifact 模板

## What Changes

**<sso routers 100% line cov>**
- From: `app/routers/sso.py` 28% line cov(70/97 miss),4 endpoint
  (`/wechat/initiate` / `/wechat/callback` / `/refresh` / `/jwks.json`
  / `/healthz`)大部分 happy path + 全部 error path **未测**
- To: 12 个新 test 走 4 endpoint 全部 path,`app/routers/sso.py` 100%
  line cov
- Reason: 关 retrospective §4.1 估时 1-1.5h 的 followup;sso cov matrix
  推进到 ~95%+
- Impact: 0 行 prod code 改动;仅新增
  `services/sso/tests/test_routers_coverage.py`

## Capabilities

### New Capabilities
- `sso-routers-coverage`: 12 个 endpoint test 走 `app/routers/sso.py`
  4 endpoint 全部 path(wechat_initiate happy / wechat_callback 5 路径
  / refresh_token 3 路径 / jwks / healthz 2 路径),达到 100% line cov

### Modified Capabilities
- (无 — 不改 requirement,只补 test)

## Impact

- **后端范围**: `services/sso/tests/test_routers_coverage.py`(新增,~250
  行,12 test)
- **前端范围**: 豁免 — 纯后端 FastAPI endpoint test
- **APIs**: 0 改
- **依赖**: 0 新增
- **0 行 prod code** 改动

## Non-goals

- 不动 `app/routers/sso.py` 任何 prod code
- 不动 `app/jwt_utils.py` / `app/wechat.py` / `app/user.py`(仍 followup)
- 不改 `--cov-fail-under=100` 阈值(本 change 不触发)
- 不写 integration test(纯 unit test + MagicMock,沿用既有 pattern)
