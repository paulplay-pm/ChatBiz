## 1. 摸底 + 测试基线

- [x] 1.1 摸底 `app/wechat.py` 当前 8 miss 行分布(命令:`pytest tests/
  --cov=app.wechat --cov-report=term-missing -q`)
- [x] 1.2 读 `app/wechat.py` 全文锁定 5 path:`exchange_code`
  TimeoutException(71-74) / HTTPError(75-77) / 其他 errcode(88-90) /
  缺字段(95-97) / `fetch_userinfo` httpx exception(114-115)
- [x] 1.3 确认 `pythonpath = ["."]` 在 `services/sso/pyproject.toml` 已
  生效(commit 5d895e6 锁定)

## 2. 写 `tests/test_wechat_coverage.py` 5 test

> 1 test → 1 pytest verify → 写下一个(micro-cycle,跟
> `sso-routers-coverage` retrospective 锁定)。每写完 1 个 test
> 必须先 `pytest tests/test_wechat_coverage.py -v` 看 pass 再写下一个。

- [x] 2.1 写 test #1 `test_exchange_code_timeout_exception` — D1
- [x] 2.2 写 test #2 `test_exchange_code_http_error` — D1
- [x] 2.3 写 test #3 `test_exchange_code_other_errcode` — D1
- [x] 2.4 写 test #4 `test_exchange_code_missing_access_token` — D1
- [x] 2.5 写 test #5 `test_fetch_userinfo_httpx_error` — D3

## 3. 验证覆盖率

- [x] 3.1 跑 `conda run -n chatbiz pytest tests/test_wechat_coverage.py
  --cov=app.wechat --cov-report=term-missing -v` 必须 5 passed +
  100% line cov
- [x] 3.2 跑全 sso suite:`conda run -n chatbiz pytest tests/ -q`,
  确认无 regression(本 change 不动 prod code,既有 44 + 1 pre-existing
  test 应仍全 PASS)

## 4. Commit + 收尾

- [x] 4.1 `git add services/sso/tests/test_wechat_coverage.py`
- [x] 4.2 `git commit -m "test(sso): close retrospective §4.1 row 3 — 100% line cov on wechat.py"`
  (Co-Authored-By 结尾)
- [x] 4.3 跑 `git log -1 --format='%H %s'` 确认 commit 进 linear history
- [x] 4.4 跑 `git status` 确认 working tree clean
