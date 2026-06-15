## Context

sso service 在 `sso-wechat-coverage` (commit 4be42b9) apply 后,sso 4 module
partial followup **仅剩 1 miss**(retrospective §3.1 + §4.1 row 4):

| Module | Missing | 行范围(摸底) |
|---|---|---|
| `app/user.py` | **1 miss** | 45 |

本 change **关闭 `user.py` 1 miss**。sso cov matrix 收尾最后一步。

**Stakeholders**: paul(sponsor)/ sso service owner / CI 维护者。

**Constraints**:
- 0 行 prod code 改动
- 走完本 change 后 sso 总 cov 99% → 100%(**全部 17 module 100%**)
- 沿用既有 pattern(`test_coverage_followup.py` 用 `AsyncMock` session +
  `MagicMock` existing user)

## Goals / Non-Goals

**Goals:**
1. `app/user.py` 从 96% line cov 涨到 100%
2. 1 个新 test 走 line 45(无 `# pragma: no cover`)
3. sso 总 cov 99% → 100%(全部 17 module 100% 达成)
4. 0 行 prod code 改动
5. 不影响既有 `test_upsert_wechat_user_updates_existing` 的"email NOT
   provided should NOT be cleared" 行为

**Non-Goals:**
1. 不动 `app/user.py` 任何 prod code
2. 不写 integration test(纯 unit test)
3. 不改 `pyproject.toml` 任何 addopts

## Decisions

### D1: 新增 1 test 走"已有 user + 提供 email"update 路径

- **选择**: `test_upsert_sso_user_updates_existing_with_email` 调
  `upsert_sso_user(session, corp_external_id="openid-1", name="New Name",
  email="new@example.com")` 走 else 分支 + `if email:` 为 True →
  line 45 走
- **理由**: line 45 `user.email = email` 是 else 分支里 `if email:` 块
  的赋值,必须有 1 test 走 True 路径;既有 test `test_upsert_wechat_user_updates_existing`
  走 False 路径(验 "email NOT provided should NOT be cleared")
- **已考虑 alternative**:
  - 改既有 test 走 True 路径 → 破坏既有 test 的关键 behavior
  - 加 `# pragma: no cover` 走 95% → 业务逻辑必须测

### D2: 沿用既有 test 模式 — AsyncMock session + MagicMock existing user

- **选择**: 复用 `test_coverage_followup.py::test_upsert_wechat_user_updates_existing`
  的 mock 模式(AsyncMock session + `scalar_one_or_none` 返 MagicMock
  user + `session.flush` AsyncMock)
- **理由**: 跟既有 test 一致,无新 mock pattern 引入

## Risks / Trade-offs

**[Trade-off] 1 test 1 line 走 100% line cov,小 change** → 接受:这是
sso cov matrix 最后 1 miss,虽小但属 retrospective 锁定 4 module partial
followup 系列;走完整 6-artifact 流程保持命名 + 决策可追溯

**[Trade-off] 6 artifact 模板对 1 test change 偏重** → 接受:跟之前 10
个 coverage change 模式一致,新 cycle 容易 `grep openspec/changes/archive/`
找回 reference;若改"1 test change 走简化 3-artifact" 模式会引入
schema-internal inconsistency,得不偿失

## Migration Plan

N/A — 本 change **不涉及部署变更**。仅新增
`services/sso/tests/test_user_line45_coverage.py`,pytest 跑通即可。

**部署步骤**: 0
**Rollback 策略**: `git revert <commit>` 即可,纯 test 文件
**验收条件**: `pytest tests/test_user_line45_coverage.py --cov=app.user
--cov-report=term-missing` 1 PASS, `app/user.py` 100% line cov

## Open Questions

(本轮无 — D1-D2 决策链已穷举,选完无需进一步澄清)
