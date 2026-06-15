# Retrospective: sso-wechat-coverage

> Written: 2026-06-15 (after verify passed)
> Commit range: `86d5e16..4be42b9` (1 new commit in this change range)
> Worktree: merged to main

---

## 0. Evidence

- **Commit range**: `86d5e16..4be42b9` (1 new commit: `4be42b9`)
- **Diff size**: +154 / -0 lines across 1 file (`services/sso/tests/test_wechat_coverage.py`)
- **Tasks done**: 14/14
- **Active hours**: ~25 min(retrospective 估"2-3 test, ~20 min",**估时 fragility 第 8 次轻微触发**)
- **Subagent dispatches**: 0
- **New external dependencies**: none
- **Bugs encountered post-merge**: 0
- **OpenSpec validate state at archive**: pass
- **Test coverage signal**:
  - `app/wechat.py` 84% → **100%** (51/51 statements)
  - sso total: 97% → **99%**
  - 5 test PASS / 0 FAIL
  - 全 sso suite: 49 PASS / 1 SKIPPED / 0 FAILED

Commit chain:

```
4be42b9 test(sso): close retrospective §4.1 row 3 — 100% line cov on wechat.py
```

---

## 1. Wins

- [evidence: `app/wechat.py` 84% → 100%] 5 test 一次过,摸底估 8 miss 实际 8 miss(估时准)
- [evidence: 0 行 prod code] 跟 `coverage-matrix-v1-followup` family pattern 一致
- [evidence: ~25 min] 5 test vs 估 2-3 test — 估时 fragility 第 8 次轻微触发但仍可接受
- [evidence: pytest-cov quirk] 5 test 单独跑显示 8 miss,全 sso suite 跑 + `--cov=app.wechat` 报告 100% — pytest-cov 跨 file coverage 累积行为

## 2. Misses

- 📌 [nit | evidence: pytest-cov quirk] 单 test file 跑时 cov 报告与全 suite 跑结果不一致 — 5 test 单独跑 wechat 报告 8 miss(行号不同),全 suite 跑 0 miss。原因:pytest-cov 默认是"行被任何测试触达就算覆盖",单 file 跑时其他 test 不参与累积,行号在 isolated run 下被算成 miss。**这是 cov 工具行为,不是 test bug**。
- 📌 [nit | evidence: 估时 2-3 vs 实际 5] retrospective §4.1 row 3 估"2-3 test, ~20 min"偏乐观 — 实际"5 test, ~25 min"。**估时 fragility 第 8 次触发**。但因 100% line cov 目标达成,影响有限
- 📌 [nit | evidence: 1 miss 仍 followup] `user.py 1 miss` 仍 followup,sso cov 99% 不是 100% — 但本 change 锁定的 `wechat.py` 100% ✓

## 3. Plan deviations

| Plan task | What changed | Why |
|-----------|--------------|-----|
| 2.1-2.5 5 test 跟设计一致 | 无变化 | 一次过 |

## 4. Skill / workflow compliance

| Skill                                            | Used |
|--------------------------------------------------|------|
| superpowers:brainstorming                        | ✓    |
| superpowers:writing-plans                        | ✓    |
| superpowers:using-git-worktrees                  | ✗    |
| superpowers:subagent-driven-development          | ✗    |
| (transitive) superpowers:test-driven-development | ✓    |
| (transitive) superpowers:requesting-code-review  | ✗    |
| superpowers:finishing-a-development-branch       | ✓    |

### Deliberately Skipped Skills

- **superpowers:using-git-worktrees** / **subagent-driven-development**
  - 跟 `sso-routers-coverage` / `sso-jwt-utils-coverage` 同 pattern — 1 file 加 + 0 行 prod code + 单 service + 全 pytest。CLAUDE.md trigger 候选 rule 仍候选,本 change + 之前 9 个 coverage change 全触发

## 5. Surprises

- pytest-cov 在 `pytest tests/test_wechat_coverage.py --cov=app.wechat` 单独跑 vs `pytest tests/ --cov=app.wechat` 全 suite 跑结果不一致。前者报 8 miss,后者报 0 miss。**根因**:pytest-cov 跨测试文件累积 line coverage,单 file 跑时其他 test(尤其 `test_coverage_followup.py` 中 2 个 wechat 2 test + `test_routers_coverage.py` 中 1 个 wechat 503 test)不参与,line 行号在 isolated run 下被算成 miss。**这是 cov 工具行为,不是 test bug**。
- `fetch_userinfo` 现有 test(`test_wechat_get_userinfo_raises_workflowruntimeerror_on_5xx`)虽然名字像 5xx,**但实际**它 mock `client.fetch_userinfo = AsyncMock(side_effect=WorkflowRuntimeError(...))` — 直接在 client method 装 side_effect,**绕过** `wechat.py` 内 try/except 块(line 107-117)。这就是为什么 line 114-115 在 `test_coverage_followup.py` apply 后仍 miss — **现有 test 名字 misleading**。

## 6. Promote candidates → long-term learning

- [ ] 📌 **mock 装在哪一层决定能否触发 try/except 块** → **Promote to project memory** (type: pattern)
  > **Why**: 现有 `test_wechat_get_userinfo_raises_workflowruntimeerror_on_5xx` mock 装在 `client.fetch_userinfo` 上,绕过了 `wechat.py` 内 try/except。本 change D3 决策才补 1 test 走真 `httpx.AsyncClient.get` side_effect。
  > **How to apply**: 测 try/except 转换路径时,必须在最底层 mock(`httpx.AsyncClient.get` / `requests.get` / `cursor.execute`)**不**在 client wrapper method 上。`wechat_test_mock_layer_pattern.md`

- [ ] 📌 **pytest-cov 单 file 跑 vs 全 suite 跑差异** → **Promote to project memory** (type: pattern)
  > **Why**: 5 test 单独跑报 8 miss,全 suite 跑报 0 miss。pytest-cov 默认按 line 触达算覆盖,跨 file 累积。
  > **How to apply**: 验 `--cov=<module>` 是否 100% 时,**必须**跑全 suite(本仓库 `pytest tests/ -q`),不跑单 file。verify.md §5.5 evidence 永远引全 suite 跑结果

- [ ] 📌 **sso cov matrix 收尾仅剩 user-line-45** → **Promote to project CLAUDE.md** (`## Conventions` 段)
  > **Why**: 9 个 coverage change 关闭后,sso 4 module partial 仅剩 1 miss(`user.py` line 45 — `if email:` edge case)
  > **How to apply**: 下条 `sso-user-line-45` change ~5 min,1 test 走 email 缺省不更新分支

---
