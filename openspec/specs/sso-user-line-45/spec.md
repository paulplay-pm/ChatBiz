# sso-user-line-45 Specification

## Purpose
TBD - created by archiving change sso-user-line-45. Update Purpose after archive.
## Requirements
### Requirement: `upsert_sso_user` else 分支 email update 必须有测试覆盖

MUST 至少 1 个单元测试覆盖 `app/user.py::upsert_sso_user` 在 `user is
not None` else 分支(line 40-47)下 `if email:` 为 True 时的 `user.email =
email` 赋值路径(行 45)。本要求补充既有
`test_upsert_wechat_user_updates_existing`(覆盖 `if email:` 为 False
分支,验"email NOT provided should NOT be cleared")未走到的 True 分支。

#### Scenario: upsert_sso_user 在已有 user + 提供 email 时更新 email
- **WHEN** `upsert_sso_user(session, corp_external_id="openid-1",
  name="New Name", email="new@example.com")` 在 `session.execute` 返
  existing user MagicMock(name="Old Name", email="old@x.com", role="user",
  last_login_at=...) + `scalar_one_or_none` 返该 user 环境下被 `await`
  调用
- **THEN** 返回的 user.name == "New Name",user.email == "new@example.com"
  (line 45 `user.email = email` 走了),user.last_login_at 被更新;
  `session.flush` 被 await 1 次

---

### Requirement: user.py 100% line cov 必须由 1 个新 test 达成

MUST 至少 1 个新 test 达成 `app/user.py` 100% line cov(23/23 statements,
0 missing)。`pytest tests/test_user_line45_coverage.py --cov=app.user
--cov-report=term-missing` MUST 报告 100% line cov,无 `# pragma: no cover`
标注引入 prod code。

#### Scenario: 1 test PASS + 100% line cov
- **WHEN** `conda run -n chatbiz pytest tests/test_user_line45_coverage.py
  --cov=app.user --cov-report=term-missing -v` 在 chatbiz env 跑
- **THEN** 1 passed, 0 failed, `app/user.py` 报告显示 100% line cov,
  0 missing

