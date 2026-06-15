## 1. 摸底 + 测试基线

- [x] 1.1 摸底 `app/user.py` 当前 1 miss 行分布(命令:`pytest tests/
  --cov=app.user --cov-report=term-missing -q`)
- [x] 1.2 读 `app/user.py` 全文锁定 line 45 = `user.email = email` 在
  `upsert_sso_user` else 分支 `if email:` True 路径(line 40-47)
- [x] 1.3 确认 `pythonpath = ["."]` 在 `services/sso/pyproject.toml` 已
  生效(commit 5d895e6 锁定)
- [x] 1.4 读既有 `test_coverage_followup.py::test_upsert_wechat_user_updates_existing`
  锁定 mock 风格(AsyncMock session + MagicMock existing user +
  `session.flush` AsyncMock),避免新 test 引入新 pattern

## 2. 写 `tests/test_user_line45_coverage.py` 1 test

> 1 test → 1 pytest verify → commit(micro-cycle,跟
> `sso-routers-coverage` retrospective 锁定)。

- [x] 2.1 写 test #1 `test_upsert_sso_user_updates_existing_with_email` — D1

## 3. 验证覆盖率

- [x] 3.1 跑 `conda run -n chatbiz pytest tests/test_user_line45_coverage.py
  --cov=app.user --cov-report=term-missing -v` 必须 1 passed +
  100% line cov
- [x] 3.2 跑全 sso suite:`conda run -n chatbiz pytest tests/ -q`,
  确认无 regression(本 change 不动 prod code,既有 49 + 1 pre-existing
  test 应仍全 PASS,既有 `test_upsert_wechat_user_updates_existing` 仍
  PASS)

## 4. Commit + 收尾

- [x] 4.1 `git add services/sso/tests/test_user_line45_coverage.py`
- [x] 4.2 `git commit -m "test(sso): close retrospective §4.1 row 4 — 100% line cov on user.py (1 line 45 miss)"`
  (Co-Authored-By 结尾)
- [x] 4.3 跑 `git log -1 --format='%H %s'` 确认 commit 进 linear history
- [x] 4.4 跑 `git status` 确认 working tree clean
