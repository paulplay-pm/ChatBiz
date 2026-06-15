<!--
Raw capture of superpowers:brainstorming output for sso-wechat-coverage.

来源:openspec/changes/archive/2026-06-15-ci-coverage-sso/retrospective.md §3.1 + §4.1
方式:已通过 brainstorming skill 跑完对话,Q1-Q3 决策链见下
-->

# Brainstorm: sso-wechat-coverage

**Date**: 2026-06-15
**Trigger**: `openspec/changes/archive/2026-06-15-ci-coverage-sso/retrospective.md` §3.1 + §4.1 row 3
**Owners**: paul (sponsor) + Claude (apply orchestrator)

---

## 背景

sso service 在 `sso-routers-coverage` (23018e8) + `sso-jwt-utils-coverage`
(a65b3cb) apply 后,2 module partial followup 仍 open:

| Module | Missing | 行范围(摸底) |
|---|---|---|
| `app/wechat.py` | **8 miss** | 71-76, 88, 95, 114-115 |
| `app/user.py` | 1 miss | 45 |

本 change **仅关闭 `wechat.py` 8 miss**。1 miss 留 `sso-user-line-45`
后续 1 个 change。

**Stakeholders**: paul(sponsor)/ sso service owner / CI 维护者。

**Constraints**:
- 0 行 prod code 改动
- 不改 `--cov-fail-under=100`(本 change 触发后 sso 总 cov 涨到
  ~99% — `user.py 1 miss` 仍 followup)
- 沿用既有 test 命名模式(`test_coverage_followup.py` /
  `test_routers_coverage.py` / `test_jwt_utils_coverage.py`)

## 决策链

### Q1: 本 change scope 只走 wechat,还是合并 user-line-45?

**A (选定)**: 只走 `wechat.py`,目标 100% line cov。
- 理由: 跟 `sso-routers-coverage` / `sso-jwt-utils-coverage` 同
  pattern,retrospective 估时纪律拆 2 条

**B (拒)**: 同 change 合并 user-line-45。
- 拒绝: 1 行 trivial,合并是 1-file 2-change 模式反而混乱

### Q2: wechat 100% line cov 是加 `# pragma: no cover` 还是补 test?

**A (选定)**: 补 test 走 8 miss 全 path。
- 理由: 4 path 全部是 error handling 业务逻辑,必须测

**B (拒)**: 选 2-3 行 `pragma: no cover` 走 70-80%。
- 拒绝: error handling 路径必须测,`pragma` 只用于 unreachable

### Q3: 5 test 1 path 1 test 还是合并?

**A (选定)**: 5 test,1 path 1 test(timeout / httperror / 其他 errcode
/ 缺字段 / fetch_userinfo httperror)
- 理由: 4 path 各自不同的 httpx mock 配置,合并会重复 setup
- 已考虑 alternative: 4 test 合并 timeout + httperror → 违反 micro-cycle
  (timeout 跟 httperror 是不同 exception class,行为 family 不一致)

## 拒绝的方案总览

| 方案 | 拒绝理由 |
|---|---|
| 合并 user-line-45 | 1 行 trivial,独立 change 更清晰 |
| 选 `pragma: no cover` 走 70% | error handling 必须测 |
| 4 test 合并 timeout+httperror | 不同 exception class 行为 family 不一致 |

## Open Questions

(本轮无 — Q1-Q3 决策链已穷举,选 A 后无需进一步澄清)
