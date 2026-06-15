## Why

`ci-coverage-sso` (commit 5d895e6) + `sso-routers-coverage` (commit 23018e8)
apply 后 `app/jwt_utils.py` 仍 **15 missing lines**(占总 sso 24 miss 中的
15)。retrospective §3.1 + §4.1 把 `jwt_utils.py` 列为第 2 大头,估"3-4 test,
~30 min"。

现在处理是为 **sso service cov 推进到 ~95%+(剩 9 miss 仍 followup 但
single module 100% 达成)**,sso cov matrix 收尾序列倒数第 2 步。

参考源:
- `docs/architecture.md` §4.3.2(Lead Agent 委派模式)
- 设计 doc `GSTACK REVIEW REPORT` Quality #3(4 错误边界)
- 仓库内 8 个 archived coverage change 的 6-artifact 模板

## What Changes

**<sso jwt_utils 100% line cov>**
- From: `app/jwt_utils.py` 79% line cov(15/70 miss),`_to_pem` private
  branch + `encode_jwt` body + `decode_jwt` body + 2 error path **未测**
- To: 3 个新 test 走 3 个块共 15 行,`app/jwt_utils.py` 100% line cov
- Reason: 关 retrospective §4.1 row 2;sso cov matrix 推进
- Impact: 0 行 prod code 改动;仅新增
  `services/sso/tests/test_jwt_utils_coverage.py`

## Capabilities

### New Capabilities
- `sso-jwt-utils-coverage`: 3 个新 test 走 `app/jwt_utils.py` 3 个块共
  15 miss 行,达到 100% line cov(0 行 prod code 改动)

### Modified Capabilities
- (无 — 不改 requirement,只补 test)

## Impact

- **后端范围**: `services/sso/tests/test_jwt_utils_coverage.py`(新增,
  ~150 行,3 test)
- **前端范围**: 豁免 — 纯后端 Python 单元测试
- **APIs**: 0 改
- **依赖**: 0 新增
- **0 行 prod code** 改动

## Non-goals

- 不动 `app/jwt_utils.py` 任何 prod code
- 不动 `app/wechat.py` / `app/user.py`(仍 followup)
- 不改 `pyproject.toml` 任何 addopts
- 不改 `app/routers/sso.py`(100% 已达成,见 commit 23018e8)
