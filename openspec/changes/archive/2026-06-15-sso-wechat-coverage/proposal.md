## Why

`sso-jwt-utils-coverage` (commit a65b3cb) apply 后 `app/wechat.py` 仍
**8 missing lines**(占 sso 9 miss 中的 8)。retrospective §3.1 + §4.1 把
`wechat.py` 列为第 3 大头,估"2-3 test, ~20 min"。

现在处理是为 **sso service cov 推进到 ~99%+(剩 `user.py` 1 miss 仍
followup,但单 module 100% 达成)**,sso cov matrix 收尾倒数第 2 步。

参考源:
- `docs/architecture.md` §4.3.2(Lead Agent 委派模式)
- 设计 doc `GSTACK REVIEW REPORT` Quality #3(4 错误边界)
- 仓库内 9 个 archived coverage change 的 6-artifact 模板

## What Changes

**<sso wechat 100% line cov>**
- From: `app/wechat.py` 84% line cov(8/51 miss),`exchange_code` 2 个
  httpx exception 路径 + 1 个其他 errcode 路径 + 1 个缺字段路径 +
  `fetch_userinfo` 1 个 httpx exception 路径 **未测**
- To: 5 个新 test 走 5 path 共 8 行,`app/wechat.py` 100% line cov
- Reason: 关 retrospective §4.1 row 3;sso cov matrix 推进
- Impact: 0 行 prod code 改动;仅新增
  `services/sso/tests/test_wechat_coverage.py`

## Capabilities

### New Capabilities
- `sso-wechat-coverage`: 5 个新 test 走 `app/wechat.py` 5 path 共 8 miss
  行,达到 100% line cov(0 行 prod code 改动)

### Modified Capabilities
- (无 — 不改 requirement,只补 test)

## Impact

- **后端范围**: `services/sso/tests/test_wechat_coverage.py`(新增,
  ~200 行,5 test)
- **前端范围**: 豁免 — 纯后端 Python 单元测试
- **APIs**: 0 改
- **依赖**: 0 新增
- **0 行 prod code** 改动

## Non-goals

- 不动 `app/wechat.py` 任何 prod code
- 不动 `app/user.py`(仍 followup,留 `sso-user-line-45`)
- 不改 `pyproject.toml` 任何 addopts
- 不改 `app/routers/sso.py` / `app/jwt_utils.py`(都已 100% 达成)
