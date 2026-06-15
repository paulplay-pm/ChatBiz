## 1. 摸底 + 测试基线

- [x] 1.1 摸底 `app/routers/sso.py` 当前 70 miss 行分布(命令:`pytest
  tests/test_coverage_followup.py --cov=app.routers.sso
  --cov-report=term-missing -q`)
- [x] 1.2 读 `services/sso/tests/test_coverage_followup.py` 已有 12 test
  pattern,锁定 mock 风格(httpx.AsyncClient / pytest.raises match
  误用经验 / upsert_sso_user + fetch_userinfo rename 等)
- [x] 1.3 确认 `pythonpath = ["."]` 在 `services/sso/pyproject.toml` 已
  生效(commit 5d895e6 锁定)

## 2. 写 `tests/test_routers_coverage.py` 12 test

> 1 test → 1 pytest verify → 写下一个(micro-cycle,跟
> `ci-coverage-sso` retrospective §4.5 锁定)。每写完 1 个 test
> 必须先 `pytest tests/test_routers_coverage.py -v` 看 pass 再写下一个。

- [x] 2.1 写 test #1 `test_wechat_initiate_happy` — D1 + D2 决策
- [x] 2.2 写 test #2 `test_wechat_callback_happy` — D1 + D2 + D5
- [x] 2.3 写 test #3 `test_wechat_callback_missing_code_or_state` — D3
- [x] 2.4 写 test #4 `test_wechat_callback_state_mismatch` — D3
- [x] 2.5 写 test #5 `test_wechat_callback_exchange_code_usererror` — D3
- [x] 2.6 写 test #6 `test_wechat_callback_fetch_userinfo_runtime_error` — D3
- [x] 2.7 写 test #7 `test_refresh_token_missing_refresh` — D1
- [x] 2.8 写 test #8 `test_refresh_token_401_branches`(4 路径合一) — D4
- [x] 2.9 写 test #9 `test_refresh_token_happy` — D1
- [x] 2.10 写 test #10 `test_jwks_endpoint` — D6
- [x] 2.11 写 test #11 `test_healthz_happy` — D1
- [x] 2.12 写 test #12 `test_healthz_returns_503_on_db_error` — D1
- [x] 2.13 写 test #13 `test_wechat_initiate_503_when_wechat_unavailable` — 摸底发现 miss line 41,补 1 test 走 wechat_initiate 503 path
- [x] 2.14 写 test #14 `test_wechat_callback_exchange_code_runtime_error` — 摸底发现 miss line 85-86,补 1 test 走 exchange_code WorkflowRuntimeError 502 path
- [x] 2.15 写 test #15 `test_refresh_token_first_returns_coroutine` — 摸底发现 miss line 157,补 1 test 走 `if asyncio.iscoroutine(first):` async session path

## 3. 验证覆盖率

- [x] 3.1 跑 `conda run -n chatbiz pytest tests/test_routers_coverage.py
  --cov=app.routers.sso --cov-report=term-missing --cov-fail-under=100 -v`
  必须 12 passed + 100% line cov
- [x] 3.2 跑全 sso suite:`conda run -n chatbiz pytest tests/ -q`,
  确认无 regression(本 change 不动 prod code,既有 12 + 1 pre-existing
  test 应仍全 PASS)

## 4. Commit + 收尾

- [x] 4.1 `git add services/sso/tests/test_routers_coverage.py`
- [x] 4.2 `git commit -m "test(sso): close retrospective §4.1 row 1 — 100% line cov on routers/sso.py"`
  (Co-Authored-By 结尾)
- [x] 4.3 跑 `git log -1 --format='%H %s'` 确认 commit 进 linear history
- [x] 4.4 跑 `git status` 确认 working tree clean
