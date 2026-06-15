## 1. 摸底 + 测试基线

- [x] 1.1 摸底 `app/jwt_utils.py` 当前 15 miss 行分布(命令:`pytest tests/
  --cov=app.jwt_utils --cov-report=term-missing -q`)
- [x] 1.2 读 `app/jwt_utils.py` 全文锁定 3 块结构:`_to_pem` 99-109 /
  `encode_jwt` 112-133 / `decode_jwt` 136-156
- [x] 1.3 确认 `pythonpath = ["."]` 在 `services/sso/pyproject.toml` 已
  生效(commit 5d895e6 锁定)

## 2. 写 `tests/test_jwt_utils_coverage.py` 3 test

> 1 test → 1 pytest verify → 写下一个(micro-cycle,跟
> `sso-routers-coverage` retrospective 锁定)。每写完 1 个 test
> 必须先 `pytest tests/test_jwt_utils_coverage.py -v` 看 pass 再写下一个。

- [x] 2.1 写 test #1 `test_to_pem_private_key_path` — D1 + D5
- [x] 2.2 写 test #2 `test_encode_jwt_happy_path` — D1 + D2
- [x] 2.3 写 test #3 `test_decode_jwt_happy_and_error_paths` — D3(3 子
  路径合一)
- [x] 2.4 摸底补 1:发现 3 error class `__init__` body (45-46 / 53-54 /
  61-62) + `load_or_generate_keypair` 2 分支 (73-77) + `get_jwks` body
  (162-163) 也 miss。补 `test_error_class_init_bodies_assign_code_attribute`
  (1 test 走 3 错类 default+custom code) + `test_load_or_generate_keypair_loads_existing_pem`
  (1 test 走 2 分支) + `test_get_jwks_constructs_jwk_set` (1 test 走
  public_numbers + dict body 不 patch)
- [x] 2.5 实际 6 test 不是原计划 3 test;摸底估 15 miss 实际 13 miss
  (估时 fragility 第 7 次触发;但本 change 仍达成 100% line cov 目标)

## 3. 验证覆盖率

- [x] 3.1 跑 `conda run -n chatbiz pytest tests/test_jwt_utils_coverage.py
  --cov=app.jwt_utils --cov-report=term-missing -v` 必须 3 passed +
  100% line cov
- [x] 3.2 跑全 sso suite:`conda run -n chatbiz pytest tests/ -q`,
  确认无 regression(本 change 不动 prod code,既有 38 + 1 pre-existing
  test 应仍全 PASS)

## 4. Commit + 收尾

- [x] 4.1 `git add services/sso/tests/test_jwt_utils_coverage.py`
- [x] 4.2 `git commit -m "test(sso): close retrospective §4.1 row 2 — 100% line cov on jwt_utils.py"`
  (Co-Authored-By 结尾)
- [x] 4.3 跑 `git log -1 --format='%H %s'` 确认 commit 进 linear history
- [x] 4.4 跑 `git status` 确认 working tree clean
