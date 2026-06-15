<!--
Raw capture of superpowers:brainstorming output for sso-user-line-45.

来源:openspec/changes/archive/2026-06-15-ci-coverage-sso/retrospective.md §3.1 + §4.1
方式:已通过 brainstorming skill 跑完对话,Q1 决策链见下
-->

# Brainstorm: sso-user-line-45

**Date**: 2026-06-15
**Trigger**: `openspec/changes/archive/2026-06-15-ci-coverage-sso/retrospective.md` §3.1 + §4.1 row 4
**Owners**: paul (sponsor) + Claude (apply orchestrator)

---

## 背景

sso service 在 `sso-wechat-coverage` (4be42b9) apply 后,sso 4 module partial
followup **仅剩 1 miss**:

| Module | Missing | 行范围(摸底) |
|---|---|---|
| `app/user.py` | **1 miss** | 45 |

本 change **关闭 `user.py` 1 miss** — sso cov matrix 收尾最后一步。

**Stakeholders**: paul(sponsor)/ sso service owner / CI 维护者。

**Constraints**:
- 0 行 prod code 改动
- 走完本 change 后 sso 总 cov 99% → 100%(**全部 17 module 100%**)
- 沿用既有 test 命名模式

## 决策链

### Q1: line 45 miss 怎么关?

**A (选定)**: 新增 1 test 走 `upsert_sso_user` 已有 user + 提供 email 的 update 路径(line 44 `if email:` 为 True → line 45 `user.email = email` 走)。
- 理由: 业务逻辑必须测,且 else 分支 "user.email 更新" 路径未测。
- 既不影响既有 `test_upsert_wechat_user_updates_existing` 的 "email NOT provided should NOT be cleared" 行为(那个 test 继续验空 case)

**B (拒)**: 修改既有 `test_upsert_wechat_user_updates_existing` 改成提供 email。
- 拒绝: 既有 test 验 "email NOT provided should NOT be cleared" 是关键 behavior,不能改

**C (拒)**: 加 `# pragma: no cover` 走 95%。
- 拒绝: 业务逻辑必须测,`pragma` 只用于 unreachable

## 拒绝的方案总览

| 方案 | 拒绝理由 |
|---|---|
| 改既有 test 走 line 45 | 破坏"email NOT provided should NOT be cleared" 关键 behavior |
| 选 `pragma: no cover` 走 95% | 业务逻辑必须测 |

## Open Questions

(本轮无 — Q1 决策链已穷举,选 A 后无需进一步澄清)
