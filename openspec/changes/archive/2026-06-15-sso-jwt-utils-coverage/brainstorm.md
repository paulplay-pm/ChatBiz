<!--
Raw capture of superpowers:brainstorming output for sso-jwt-utils-coverage.

来源:openspec/changes/archive/2026-06-15-ci-coverage-sso/retrospective.md §3.1 + §4.1
方式:已通过 brainstorming skill 跑完对话,Q1-Q3 决策链见下
-->

# Brainstorm: sso-jwt-utils-coverage

**Date**: 2026-06-15
**Trigger**: `openspec/changes/archive/2026-06-15-ci-coverage-sso/retrospective.md` §3.1 + §4.1 row 2
**Owners**: paul (sponsor) + Claude (apply orchestrator)

---

## 背景

sso service 在 `ci-coverage-sso` (commit 5d895e6) + `sso-routers-coverage`
(commit 23018e8) apply 后,3 module partial followup 仍 open:

| Module | Missing | 行范围(摸底) |
|---|---|---|
| `app/jwt_utils.py` | **15 miss** | 100-106, 121-133, 143-156 |
| `app/wechat.py` | 8 miss | 42, 55, 71-76, 88, 95, 114-115 |
| `app/user.py` | 1 miss | 45 |

本 change **仅关闭 `jwt_utils.py` 15 miss**。其余 9 miss 仍 followup,
留 `sso-wechat-coverage` / `sso-user-line-45` 后续 2 个 change。

**Stakeholders**: paul(sponsor)/ sso service owner / CI 维护者。

**Constraints**:
- 0 行 prod code 改动
- 不改 `--cov-fail-under=100`(本 change 触发后 sso 总 cov 涨到
  ~95% — `wechat 8 + user 1 = 9 miss` 仍 followup)
- 沿用既有 test 命名模式(`test_coverage_followup.py` /
  `test_routers_coverage.py`)

## 决策链

### Q1: 本 change scope 只走 jwt_utils,还是合并 3 module followup?

**A (选定)**: 只走 `jwt_utils.py`,目标 100% line cov。
- 理由: 跟 `sso-routers-coverage` 同 pattern,retrospective 估时纪律
  拆 3 条(各 ~30 min)
- 缺点: `wechat 8 + user 1 = 9 miss` 仍 followup

**B (拒)**: 同 change 合并 wechat + user。
- 拒绝: 违反 retrospective 估时纪律(估 30 min 实际变 1+ h)

**C (拒)**: 1 test 走 3 个块合成。
- 拒绝: 违反 micro-cycle;1 个 fail 难定位;3 块逻辑独立

### Q2: jwt_utils 100% line cov 是加 `# pragma: no cover` 还是补 test?

**A (选定)**: 补 test 走 15 miss 全 path。
- 理由: `_to_pem` private branch + `encode_jwt` body + `decode_jwt`
  body + 2 error path 全部是业务逻辑,**必须测**;跟
  `audit-and-isolation-full-cov` 4 module 100% 原则一致

**B (拒)**: 选 3 行 `pragma: no cover` 走 80%。
- 拒绝: 业务逻辑必须测,`pragma` 只用于防御性 unreachable

### Q3: encode_jwt + decode_jwt 用真 RSA keypair 还是 mock?

**A (选定)**: 用 `load_or_generate_keypair` 拿真 RSA keypair
(2-3s 一次,3 test 共享 `tmp_path` cache)。
- 理由: encode_jwt/decode_jwt 是 RS256 JWT 签名验签,mock 不可能
  测到"签的 token 能被验签"这条核心 property;`load_or_generate_keypair`
  本身已被 `test_coverage_followup.py` 100% 覆盖,本 change 复用

**B (拒)**: 全部 mock 签名验签。
- 拒绝: round-trip 走 mock 等于"签 1 个伪 token + 验 1 个伪 token"
  不能验真正的 RS256 验签正确

## 拒绝的方案总览

| 方案 | 拒绝理由 |
|---|---|
| 合并 3 module followup | retrospective 估时纪律 |
| 选 `pragma: no cover` 走 80% | 业务逻辑必须测 |
| 全部 mock 签名验签 | round-trip 必须真 RS256 |

## Open Questions

(本轮无 — Q1-Q3 决策链已穷举,选 A 后无需进一步澄清)
