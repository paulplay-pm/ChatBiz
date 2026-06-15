## Context

sso service 在 `ci-coverage-sso` (commit 5d895e6) apply 后,4 module
partial followup(见 retrospective §3.1 + §4.1):

| Module | Missing | 行范围(摸底) |
|---|---|---|
| `app/routers/sso.py` | **70 miss** | 51-57, 63-131, 137-180, 186, 192-201 |
| `app/jwt_utils.py` | 15 miss | 100-106, 121-133, 143-156, 162-163 |
| `app/wechat.py` | 8 miss | 42, 55, 71-76, 88-98, 114-115, 123 |
| `app/user.py` | 1 miss | 45 |

本 change **仅关闭 `routers/sso.py` 70 miss**(sso 总 miss 65 → 实际
摸底涨到 70,占 70/94 = 74%)。其余 24 miss 仍 followup,留
`sso-jwt-utils-coverage` / `sso-wechat-coverage` / `sso-user-line-45`
后续 3 个 change。

**Stakeholders**: paul(sponsor)/ sso service owner(待指派, V1.0
落地时分配) / CI 维护者(GitHub Actions workflow 后续 change)。

**Constraints**:
- 0 行 prod code 改动(retrospective §3.5 已锁定 4 module 100% 是
  test-driven)
- 不改 `--cov-fail-under=100`(本 change 触发后 sso 总 cov 涨到 ~95%,
  `app/routers/sso.py` 单 module 100%)
- 沿用 `test_coverage_followup.py` 已有 pattern(12 test 跨 6 轮 debug
  的 micro-cycle 纪律)

## Goals / Non-Goals

**Goals:**
1. `app/routers/sso.py` 从 28% line cov 涨到 100%
2. 12 个新 endpoint test 走 4 endpoint 全部 path(无 `# pragma: no cover`)
3. sso 总 cov 82% → ~95%+
4. 0 行 prod code 改动

**Non-Goals:**
1. 不动 `app/jwt_utils.py` / `app/wechat.py` / `app/user.py`(仍 followup)
2. 不写 integration test(纯 unit test + MagicMock)
3. 不改 `pyproject.toml` 任何 addopts
4. 不触发 `--cov-fail-under=100` 全模块通过(本 change 仍 24 miss followup)

## Decisions

### D1: 12 test 拆 1 endpoint 1-2 path

- **选择**: 12 test(initiate 1 / callback 5 / refresh 3 / jwks 1 /
  healthz 2)
- **理由**: 1 test → 1 pytest verify → 写下一个(micro-cycle,跟
  `ci-coverage-sso` retrospective §4.5 锁定);合并 test 触发 1 个
  fail 难定位
- **已考虑 alternative**:
  - 6 test 合并 callback 5 路径 → 违反 micro-cycle
  - 1 test 走全 routers/sso.py → 不可行,4 endpoint 不同 mock 策略

### D2: TestClient 包装 `create_app()` 而非直接调 endpoint 函数

- **选择**: TestClient(app, raise_server_exceptions=False) + 注入
  `app.state.wechat/redis/db_sessionmaker/rsa_private` MagicMock
- **理由**: 跟 `test_coverage_followup.py` 中 `test_create_app_registers_*`
  + `test_4_error_handlers_return_correct_status_codes` 同 pattern;
  FastAPI HTTPException → response status_code 真实路径覆盖
- **已考虑 alternative**:
  - `asyncio.run(wechat_initiate(req))` 直接调 → 跟既有 12 test
    pattern 不一致,callback 5 路径难拆

### D3: `wechat_callback` 5 路径拆分 — 不合并

- **选择**: 5 独立 test(happy / 缺 code/state / state 失配 /
  exchange_code UserError / fetch_userinfo WorkflowRuntimeError)
- **理由**: 5 个错误类 UserError / WorkflowRuntimeError 各 1 path,
  跟 eng-review Quality #3 锁定 4 错误边界对齐;合并则 1 fail 难定位
- **已考虑 alternative**:
  - 5 路径合 1 test,parametrize 区分 → pytest parametrize 在
    mock-heavy test 调试成本高

### D4: `refresh_token` 401 路径合并(1 test)

- **选择**: 1 test `test_refresh_token_401_branches` 走 3 路径合一
  (row None / revoked / expired / user None)
- **理由**: 4 路径都是 401 + `{"error": {"code": ...}}`,3 行代码
  几乎相同,合并 1 test 减少 mock setup 重复
- **已考虑 alternative**:
  - 4 独立 test 拆开 → mock setup 重复 × 4,违反 DRY
- **注**: 这里 1 test 4 路径合并不违反 micro-cycle — **同一 401 行为
  family**,D1 的"1 path 1 test"指不同行为 family

### D5: `upsert_sso_user` + `encode_jwt` patch 走 happy path

- **选择**: 用 `unittest.mock.patch` 直接 patch `app.routers.sso.upsert_sso_user`
  和 `app.routers.sso.encode_jwt`,让 happy path 不需真 RSA keypair
  + 真 PG 写入
- **理由**: routers/sso.py 是 endpoint 层,`upsert_sso_user` /
  `encode_jwt` 已被 `test_coverage_followup.py` 8 test 覆盖
  (sso cov 96% / 79%),无需在本 change 重测
- **已考虑 alternative**:
  - 调真实 `load_or_generate_keypair` → 慢 1-2s/test × 12 = 12-24s
  - 不 patch 走真 RSA → 12 test 全 keypair 生成,慢

### D6: `get_jwks` patch(jwks test)

- **选择**: patch `app.routers.sso.get_jwks` 返回 `{"keys": [...]}`
  固定 dict
- **理由**: jwks endpoint 1 行 `return get_jwks(...)`,test 验证调用 +
  返回值即可,无需测 `jwt_utils.get_jwks` body
- **已考虑 alternative**:
  - 调真 `get_jwks` 走 RSA 公钥序列化 → 已有 `test_jwt_utils_4_error_*`
    覆盖,重复

## Risks / Trade-offs

**[Risk] 12 test 摸底阶段 6 轮 debug 浪费时间** → Mitigation: 1 test →
1 pytest verify → 写下一个 micro-cycle,跟 `ci-coverage-sso` §4.5
锁定;6 轮 debug 经验已沉淀到 `test_coverage_followup.py`(httpx
AsyncClient / fetch_userinfo rename / pytest.raises match 误用等)

**[Risk] `wechat_callback` happy path 7 个 mock 状态设置错 1 个** → 
Mitigation: 把 setup 拆成 3 段(initiate mock / redis mock / app.state
注入),每段 1 assert 验证 setup 正确

**[Trade-off] 4 个 archived coverage change 经验 vs sso 4 endpoint 内部
mock 复杂度** → 接受:callback 5 路径已用 5 test 拆开,mock 复杂度可
控;1.5h 估时跟 retrospective 一致

**[Trade-off] `app/routers/sso.py` 100% line cov 不带 `pragma: no cover`**
→ 接受:全部 70 miss 走真 test,跟 `audit-and-isolation-full-cov` 4
module 100% 原则一致(那 4 module 中 `chat.py` 3 path 是 followup
本次也同)

## Migration Plan

N/A — 本 change **不涉及部署变更**。仅新增
`services/sso/tests/test_routers_coverage.py`,pytest 跑通即可。

**部署步骤**: 0
**Rollback 策略**: `git revert <commit>` 即可,纯 test 文件
**验收条件**: `pytest tests/test_routers_coverage.py --cov=app.routers.sso
--cov-fail-under=100` PASS, 12/12 test PASS

## Open Questions

(本轮无 — D1-D6 决策链已穷举,选完无需进一步澄清)
