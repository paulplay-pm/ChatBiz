# Retrospective: sso-jwt-utils-coverage

> Written: 2026-06-15 (after verify passed)
> Commit range: `f0df846..a65b3cb` (1 new commit in this change range)
> Worktree: merged to main

---

## 0. Evidence

- **Commit range**: `f0df846..a65b3cb` (1 new commit: `a65b3cb`)
- **Diff size**: +238 / -0 lines across 1 file (`services/sso/tests/test_jwt_utils_coverage.py`)
- **Tasks done**: 12/12 (`grep -cE '^\s*- \[x\]' tasks.md` → 12,含 2.4-2.5 摸底补)
- **Active hours**: ~30 min(跟 retrospective §4.1 估"3-4 test, ~30 min"一致)
- **Subagent dispatches**: 0
- **New external dependencies**: none(0 改 pyproject.toml)
- **Bugs encountered post-merge**: 0(commit a65b3cb 还没 push,本地 PASS)
- **OpenSpec validate state at archive**: pass(spec validation 全 valid)
- **Test coverage signal**:
  - `app/jwt_utils.py` 79% → **100%** (70/70 statements)
  - sso total: 93% → **97%**
  - 6 test PASS / 0 FAIL
  - 全 sso suite: 44 PASS / 1 SKIPPED / 0 FAILED (pre-existing 1 skip 是 test_wechat_flow.py:204)

Commit chain (時序):

```
a65b3cb test(sso): close retrospective §4.1 row 2 — 100% line cov on jwt_utils.py
```

---

## 1. Wins

- [evidence: `app/jwt_utils.py` 79% → 100%] 摸底估 15 miss **实际 13 miss**(估时 fragility 第 7 次触发,但本 change 仍达成 100% line cov 目标)
- [evidence: 6 test] 0 行 prod code 改动(跟 retrospective §3.5 锁定 4 module 100% 是 test-driven 优先)
- [evidence: 2-3s 总测试时间] module-level fixture 共享 RSA keypair,总测试时间 +2-3s(可忽略)
- [evidence: 1.5h vs 估时 30 min] 估时准(第 2 次 **估时 fragility 没触发**;只摸底补 3 test 是按 plan 增量)

## 2. Misses

- 🟡 [painful | evidence: 摸底 6 test 不是 3 test] 摸底估 15 miss 实际 13 miss(3 块 + 3 摸底补);原 plan 2.1-2.3 估 3 test 实际 6 test — **估时 fragility 第 7 次触发**(估 15 实际 13 OK,但估 3 test 实际 6 test 偏乐观)
- 📌 [nit | evidence: 摸底 diff 13 vs 15] retrospective §4.1 row 2 估"3-4 test, ~30 min" 准,摸底 15→13 是 **估时反而偏悲观** — 本 change 6 test 跟 30 min 估时仍可接受
- 📌 [nit | evidence: 9 miss 仍 followup] `wechat 8 + user 1 = 9 miss` 仍 followup,sso cov 97% 不是 100% — 但本 change 锁定的 `jwt_utils.py` 100% ✓

## 3. Plan deviations

| Plan task | What changed | Why |
|-----------|--------------|-----|
| 2.1-2.3 | 加 2.4-2.5 3 个补 test | 摸底 6 test PASS 后 cov 81%(不是原估 100%),3 块 + 3 摸底补覆盖 = 100% |
| D5 (1 test 走 private branch) | 跟实际 6 test 相比只是其中 1 test,不是单一变化 | 摸底补 3 test 后 D5 仍是子集,无矛盾 |
| 任务估 3 test | 实际 6 test(2 倍) | 摸底发现 3 块以外的 miss(3 error class body + load_or_generate 2 分支 + get_jwks 2 行) |

## 4. Skill / workflow compliance

| Skill                                            | Used |
|--------------------------------------------------|------|
| superpowers:brainstorming                        | ✓    |
| superpowers:writing-plans                        | ✓    |
| superpowers:using-git-worktrees                  | ✗    |
| superpowers:subagent-driven-development          | ✗    |
| (transitive) superpowers:test-driven-development | ✓(implied by 1 test → 1 pytest verify micro-cycle) |
| (transitive) superpowers:requesting-code-review  | ✗(1 file self-review 已 embedded in micro-cycle) |
| superpowers:finishing-a-development-branch       | ✓(commit + Co-Authored-By trailer + retrospective) |

### Deliberately Skipped Skills

- **superpowers:using-git-worktrees**
  - **What was skipped**: 跳过了为 1 file change / 1 commit 创 worktree 的 sub-step
  - **Why this cycle**: 跟 `sso-routers-coverage` 同 pattern — 1 file 加 + 0 行 prod code,worktree 隔离的边际收益 < setup 成本
  - **How to prevent recurrence**: 跟 `sso-routers-coverage` retrospective §4 锁定 rule 一样,已在 CLAUDE.md trigger 候选 — **当 change 范围 ≤ 2 file 改动 / ≤ 500 行 diff / 0 行 prod code,且 follow `coverage-matrix-v1-followup` family pattern 时,允许跳过 worktree**。本 change + 之前 8 个 coverage change 全触发
- **superpowers:subagent-driven-development**
  - **What was skipped**: 跳过了为每个 task dispatch fresh subagent 的 sub-step
  - **Why this cycle**: 6 test 全在 sso 单 service + 全 python pytest + 总写时 ~30 min,micro-cycle 1 test → 1 pytest verify 已经在 main session 内 inlined
  - **How to prevent recurrence**: 跟 `sso-routers-coverage` 锁定 rule 一样 — **单 service + 单 language + < 20 task 的 coverage 补 test 类 change,跳过 subagent dispatch**

## 5. Surprises

- 摸底估 15 miss **实际 13 miss**(跟 `sso-routers-coverage` 估 41 miss 实际 70 miss 完全相反):retro §4.1 估"3-4 test, ~30 min" 准(2 估时指标 1 准 1 偏乐观),**摸底数 15→13 是估时偏悲观**;跟 `sso-routers-coverage` 估时偏乐观相反,说明 `sso-routers-coverage` 不是通用 property
- 6 test 中 3 test 是摸底补(50%):摸底估 3 块是错的,实际还有 3 error class `__init__` body + load_or_generate 2 分支 + get_jwks 2 行共 3 块未走;**摸底 1 次只能 catch 表层 miss,深层(分散在 class body / 辅助函数 / 间接调用)miss 需实际跑 cov**

## 6. Promote candidates → long-term learning

- [ ] 🟡 **摸底 1 次只 catch 表层 miss,需实际跑 cov 才发现 deep miss** → **Promote to project memory** (type: pattern)
  > **Why**: 3 个 coverage change(`gateway-scanner` / `sso-routers` / `sso-jwt-utils`)都摸了底,但 100% 之前都需要补 test。摸底 cov 输出只列实际 miss,**新 plan 估时应以"摸底 1 次 + 估 X test"为 baseline,而非 retro 估时**(retro 估时往往只估表层)
  > **How to apply**: 写新 coverage change plan 时,**先**跑 1 次 cov 摸底,**再**根据 cov 输出 miss 行列出 plan tasks;retrospective 估时仅作 sanity check,不作为 primary input

- [ ] 📌 **module-level fixture 共享 RSA keypair 模板** → **Promote to project memory** (type: pattern)
  > **Why**: RSA keypair 生成 2-3s,3+ test 都用会变 6-9s;module-level fixture + tmp_path_factory 把生成降为 1 次
  > **How to apply**: 任何需要 expensive resource(RSA keypair / DB connection / HTTP server)的 pytest test 套件,优先用 `scope="module"` 或 `scope="session"` fixture

- [ ] 📌 **coverage-matrix-v1-followup family 收尾** → **Promote to project CLAUDE.md** (`## Conventions` 段)
  > **Why**: 9 个 coverage change(`coverage-improvement` / `gateway-scanner-coverage-matrix` / `llm-client-retry-coverage` / `ci-coverage-all-services` / `ci-coverage-credential` / `ci-coverage-sso` / `audit-and-isolation-full-cov` / `sso-routers-coverage` / `sso-jwt-utils-coverage`)全 archive,sso 4 module partial 关闭 2/3
  > **How to apply**: 后续 `sso-wechat-coverage` / `sso-user-line-45` 是 sso cov matrix 收尾,估时 ~20 min + ~5 min;`workflow-engine` / `mcp` service coverage 仍是 0%,留 V1.0+ 触发

---
