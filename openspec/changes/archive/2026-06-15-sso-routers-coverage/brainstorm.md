<!--
Raw capture of superpowers:brainstorming output for sso-routers-coverage.

来源:openspec/changes/archive/2026-06-15-ci-coverage-sso/retrospective.md §3.1 + §4.1
方式:已通过 brainstorming skill 跑完对话,Q1-Q4 决策链见下;followup scope 走完 9-12 test
-->

# Brainstorm: sso-routers-coverage

**Date**: 2026-06-15
**Trigger**: `openspec/changes/archive/2026-06-15-ci-coverage-sso/retrospective.md` §3.1 + §4.1
**Owners**: paul (sponsor) + Claude (apply orchestrator)

---

## 背景

sso service 在 `ci-coverage-sso` (commit 5d895e6) apply 后:

- `app/routers/sso.py` 仍 70 missing lines(占 sso 总 miss 65 中的 41,
  后续摸底涨到 70 — audit 写入 + select execute 内部 + json body parse
  等几行没在 retrospective 估时数)
- `app/jwt_utils.py` 15 miss(JWT encode/decode body)
- `app/wechat.py` 8 miss(error path)
- `app/user.py` 1 miss(line 45 email edge case)

retrospective §4.1 把 `routers/sso.py` 列为最大头,**估"8-10
endpoint test, ~1-1.5 hours"**。本 change 关闭这一条。

---

## 决策链

### Q1: 本 change scope 只走 routers/sso.py,还是合并 4 module partial followup?

**A (选定)**: 只走 `routers/sso.py`,目标 100% line cov。
- 理由: retrospective 估时按"~1-1.5 h / change"拆 4 条,合并 = 单 change
  估时 2-2.5h,触发 V1.0+ scope drift 风险
- 缺点: jwt_utils 15 + wechat 8 + user 1 = 24 miss **仍 followup**

**B (拒)**: 同 change 合并 jwt_utils/wechat/user。
- 理由: 一次到位
- 拒绝: 违反 retrospective 估时纪律,触发 retrospective 估时 fragility
  第 6 次(估 1.5h 实际 2-2.5h)

**C (拒)**: 只做 callback 1 endpoint(~60 line miss 内部)。
- 拒绝: spec claim 拆碎,retrospective 估时缩水一半但 spec claim 偏
  partial 失去意义

### Q2: routers/sso.py 100% line cov 是加 `# pragma: no cover` 还是补 test?

**A (选定)**: 补 test 走 70 miss 全 path。
- 理由: 跟 `audit-and-isolation-full-cov` / `ci-coverage-credential` 模式
  一致,retrospective §5.1 explicit 锁定 "production 模块 ≤100% by
  test 优先"原则
- 缺点: 12 个 mock-heavy test 估时 ~1.5h(摸底 6 轮 debug 浪费时间
  historical pattern)

**B (拒)**: 选 6 行 `pragma: no cover`,只走 60% 部分。
- 拒绝: 70 miss 中只有 4 行是真正的"防御性 unreachable"(`observe_request`
  触发的 4 行可 `pragma`),其余 66 行是业务逻辑必须测

### Q3: 走 TestClient 包装 create_app() 还是直接 unit test 调 endpoint 函数?

**A (选定)**: TestClient 包装 `create_app()` + 注入 `app.state` mock。
- 理由: 跟 `test_coverage_followup.py` 中 `test_create_app_registers_*`
  4 个 handler test 同 pattern;FastAPI HTTPException → response status
  真实路径覆盖比直接调函数强

**B (拒)**: 直接 `asyncio.run(wechat_initiate(req))`。
- 缺点: 跟之前 12 test pattern 不一致;`test_wechat_initiate_returns_503_*`
  已经验证 asyncio.run + MagicMock(state) 模式,但本 change 想加 5
  callback 路径 test,直接调函数 router exception handling 需手工 raise
  跟 TestClient 重复

### Q4: 12 test 拆还是合并?

**A (选定)**: 12 test,按 1 endpoint 1-2 path 拆 1 test。
- 理由: 1 test → 1 pytest verify → 写下一个(micro-cycle,跟
  `ci-coverage-sso` retrospective §4.5 锁定)

**B (拒)**: 6 test,callback 5 路径合 1 test。
- 拒绝: 违反 micro-cycle;1 个 fail 难定位

---

## 拒绝的方案总览

| 方案 | 拒绝理由 |
|---|---|
| 合并 4 module followup | retrospective 估时纪律 |
| 选 `pragma: no cover` 走 60% | 业务逻辑必须测 |
| 直接调 endpoint 函数 | 跟既有 12 test pattern 不一致 |
| 6 test 合并 callback 5 路径 | 违反 micro-cycle |

---

## Open Questions

(本轮无 — Q1-Q4 已穷举,选 A 后无需进一步澄清)
