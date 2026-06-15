## Why

`sso-wechat-coverage` (commit 4be42b9) apply 后 `app/user.py` 仍 **1
missing line**(line 45 — `user.email = email` 赋值)。retrospective §3.1
+ §4.1 row 4 估"1 line 修, line 45 `if email:` edge case"。

现在处理是为 **sso service 100% line cov 全部 17 module**(剩 1 miss
followup,但单 module 100% 达成) — sso cov matrix 收尾最后一步。

参考源:
- `docs/architecture.md` §4.3.2(Lead Agent 委派模式)
- 设计 doc `GSTACK REVIEW REPORT` Quality #3(4 错误边界)
- 仓库内 10 个 archived coverage change 的 6-artifact 模板

## What Changes

**<sso user.py line 45 100% line cov>**
- From: `app/user.py` 96% line cov(1/23 miss),`upsert_sso_user` else
  分支 line 45 `user.email = email` **未测**(既有 test 走 `if email:`
  False 分支)
- To: 1 个新 test 走"已有 user + 提供 email update"路径,`app/user.py`
  100% line cov
- Reason: 关 retrospective §4.1 row 4;sso cov matrix 收尾最后一步
- Impact: 0 行 prod code 改动;仅新增 1 test

## Capabilities

### New Capabilities
- `sso-user-line-45`: 1 个新 test 走 `app/user.py::upsert_sso_user` 已有
  user + 提供 email update 路径,达到 100% line cov(0 行 prod code 改动)

### Modified Capabilities
- (无 — 不改 requirement,只补 test)

## Impact

- **后端范围**: `services/sso/tests/test_user_line45_coverage.py`(新增,
  ~60 行,1 test)
- **前端范围**: 豁免 — 纯后端 Python 单元测试
- **APIs**: 0 改
- **依赖**: 0 新增
- **0 行 prod code** 改动

## Non-goals

- 不动 `app/user.py` 任何 prod code
- 不改 `pyproject.toml` 任何 addopts
- 不改 `app/wechat.py` / `app/jwt_utils.py` / `app/routers/sso.py`(都已
  100% 达成)
- 不影响既有 `test_upsert_wechat_user_updates_existing` 的"email NOT
  provided should NOT be cleared" 行为
