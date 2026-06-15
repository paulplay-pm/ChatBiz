## Context

sso service 在 `sso-routers-coverage` (commit 23018e8) apply 后,3 module
partial followup 仍 open(retrospective §3.1 + §4.1):

| Module | Missing | 行范围(摸底) |
|---|---|---|
| `app/jwt_utils.py` | **15 miss** | 100-106, 121-133, 143-156 |
| `app/wechat.py` | 8 miss | 42, 55, 71-76, 88, 95, 114-115 |
| `app/user.py` | 1 miss | 45 |

本 change **仅关闭 `jwt_utils.py` 15 miss**。其余 9 miss 仍 followup,留
`sso-wechat-coverage` / `sso-user-line-45` 后续 2 个 change。

**Stakeholders**: paul(sponsor)/ sso service owner / CI 维护者。

**Constraints**:
- 0 行 prod code 改动(retrospective §3.5 锁定 4 module 100% 是
  test-driven)
- 不改 `--cov-fail-under=100`(本 change 触发后 sso 总 cov 涨到
  ~95%,`jwt_utils.py` 单 module 100%)
- 沿用既有 pattern(`test_coverage_followup.py` /
  `test_routers_coverage.py`)

## Goals / Non-Goals

**Goals:**
1. `app/jwt_utils.py` 从 79% line cov 涨到 100%
2. 3 个新 test 走 3 个块共 15 miss 行(无 `# pragma: no cover`)
3. sso 总 cov 93% → ~95%+
4. 0 行 prod code 改动

**Non-Goals:**
1. 不动 `app/wechat.py` / `app/user.py`(仍 followup)
2. 不写 integration test(纯 unit test)
3. 不改 `pyproject.toml` 任何 addopts
4. 不触发 `--cov-fail-under=100` 全模块通过(本 change 仍 9 miss followup)

## Decisions

### D1: 3 test 拆 1 块 1 test

- **选择**: 3 test(_to_pem private branch / encode_jwt happy / decode_jwt
  happy + 2 error path)
- **理由**: 1 test → 1 pytest verify → 写下一个(micro-cycle,跟
  `sso-routers-coverage` 锁定)

### D2: 用真 RSA keypair(不走 mock)

- **选择**: 用 `load_or_generate_keypair` 拿真 RSA private/public
  keypair(2-3s 一次,3 test 共享 `tmp_path` cache)
- **理由**: encode_jwt/decode_jwt 是 RS256 JWT 签名验签,mock 不可能
  测到"签的 token 能被验签"这条核心 property
- **已考虑 alternative**:
  - 全部 mock → round-trip 走 mock 等于"签 1 个伪 token + 验 1 个
    伪 token",不能验真正的 RS256

### D3: 1 test 走 decode_jwt 3 子路径(round-trip + invalid + expired)

- **选择**: `test_decode_jwt_happy_and_error_paths` 1 test 内含 3
  sub-test(round-trip 成功 / 错公钥 raises "security.invalid_token" /
  过期 token raises "security.token_expired")
- **理由**: 3 子路径都是 `decode_jwt` body 行为,但行为 family 一致
  (decode + 验签/验 iss/aud/exp),合并 1 test 减少 setup 重复
- **已考虑 alternative**:
  - 3 独立 test parametrize → mock setup 重复 × 3,违反 DRY
- **注**: 跟 `sso-routers-coverage` D4 同样原则 — **同一行为 family**,
  D1 的"1 块 1 test"指不同块

### D4: `load_or_generate_keypair` 已 100% 覆盖 — 复用不重测

- **选择**: 直接调 `load_or_generate_keypair` 拿 RSA keypair,不 mock
- **理由**: 已被 `test_coverage_followup.py::test_load_or_generate_keypair_generates_when_missing`
  100% 覆盖,本 change 复用
- **已考虑 alternative**:
  - 手工 `rsa.generate_private_key` + `private_bytes` 重建 → 跟
    `load_or_generate_keypair` 重复

### D5: `_to_pem` 1 test 走 private branch 即可

- **选择**: 1 test 调 `_to_pem(private_key)` 验证返 PEM 含
  `b"-----BEGIN PRIVATE KEY-----"`
- **理由**: `_to_pem` 公开 helper(无下划线 prefix,因模块内可被外部
  import),但 **公钥分支** 已被 `get_jwks` 间接覆盖(100%)+ encode_jwt /
  decode_jwt body 也会调
- **已考虑 alternative**:
  - 加 1 test 走 public branch → 重复覆盖

## Risks / Trade-offs

**[Risk] RSA keypair 生成 2-3s/test × 3 test = 6-9s 总时间** →
Mitigation: 3 test 共享一个 module-level fixture(用 `tmp_path_factory`
生成 + 在 conftest cache),3 test 都用同一 keypair,2-3s 总时间(只生
成 1 次)

**[Risk] `decode_jwt` 过期 token 测试需手工构造 payload with `exp=past`** 
→ Mitigation: 用 `encode_jwt(expires_in=-1)` 即可,自动 `exp=now-1`
(无需手工改 payload)

**[Trade-off] 3 test 跨 2-3s 总测试时间** → 接受: 跟 sso 整体 suite
~1.14s 相比 +2-3s 可忽略;retrospective 估时 30 min 准

## Migration Plan

N/A — 本 change **不涉及部署变更**。仅新增
`services/sso/tests/test_jwt_utils_coverage.py`,pytest 跑通即可。

**部署步骤**: 0
**Rollback 策略**: `git revert <commit>` 即可,纯 test 文件
**验收条件**: `pytest tests/test_jwt_utils_coverage.py --cov=app.jwt_utils
--cov-report=term-missing` 3 PASS, `app/jwt_utils.py` 100% line cov

## Open Questions

(本轮无 — D1-D5 决策链已穷举,选完无需进一步澄清)
