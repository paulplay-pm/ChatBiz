# Retrospective: sso-routers-coverage

> Written: 2026-06-15 (after verify passed)
> Commit range: `c777c00..23018e8` (1 new commit in this change range)
> Worktree: merged to main

---

## 0. Evidence

- **Commit range**: `c777c00..23018e8` (1 new commit: `23018e8`)
- **Diff size**: +384 / -0 lines across 1 file (`services/sso/tests/test_routers_coverage.py`)
- **Tasks done**: 24/24 (`grep -cE '^\s*- \[x\]' tasks.md` → 24,含 2.13-2.15 摸底补 3 test)
- **Active hours**: ~1.5 hours(跟 retrospective §4.1 估"1-1.5 h"一致)
- **Subagent dispatches**: 0
- **New external dependencies**: none(0 改 pyproject.toml)
- **Bugs encountered post-merge**: 0(commit 23018e8 还没 push,本地 PASS)
- **OpenSpec validate state at archive**: pass(spec validation 全 valid)
- **Test coverage signal**:
  - `app/routers/sso.py` 28% → **100%** (97/97 statements)
  - sso total: 82% → **93%**
  - 12 endpoint test (18 effective cases with parametrize) PASS / 0 FAIL
  - 全 sso suite: 38 PASS / 1 SKIPPED / 0 FAILED (pre-existing 1 skip 是 test_wechat_flow.py:204)

Commit chain (時序):

```
23018e8 test(sso): close retrospective §4.1 row 1 — 100% line cov on routers/sso.py
```

---

## 1. Wins

- [evidence: `app/routers/sso.py` 28% → 100%] 摸底估 70 miss 实际 70 miss(完全准),12 test 走完覆盖全部 70 行,无 `# pragma: no cover` 引入
- [evidence: `test_routers_coverage.py` 384 行] 0 行 prod code 改动(retrospective §3.5 锁定 4 module 100% 是 test-driven 优先)
- [evidence: 6 artifact 复用] 跟前 7 个 coverage change 模板一致,6 artifact 写 ~30 min
- [evidence: 1.5 h vs 估时 1-1.5 h] 估时准(第 1 次 **估时 fragility 没触发**)

## 2. Misses

- 🟡 [painful | evidence: 6 轮 debug] mock-heavy test 摸底 6 轮:
  1. `user.name` MagicMock → `{}` 不是 `'Alice'` (改 SimpleNamespace)
  2. `MagicMock + AsyncMock` 组合 `async with` 协议 `__aenter__` return_value 没到 `as` 目标 (改真 class)
  3. `redis_mock.get=AsyncMock(...)` 没设 `delete` → `await MagicMock()` TypeError → 500 (补 `delete=AsyncMock`)
  4. `/healthz` 路径错 (应为 `/api/v1/auth/sso/healthz`)
  5. `asyncio.iscoroutine(first)` Task 是 coroutine? (改 bare coroutine object)
  6. `test_wechat_callback_exchange_code_usererror` 跟 `runtime_error` redis mock 不全
- 📌 [nit | evidence: 2.13-2.15] 摸底发现 3 行额外 miss(41, 85-86, 157)没在原 plan tasks 2.1-2.12 列,补 3 个 test 后才达成 100%
- 📌 [nit | evidence: `audit-and-isolation-full-cov` 同期做] 实际估时跟 retrospective §4.1 估时一致(retrospective 估时准的第 1 次) — 但 sso cov matrix 仍有 24 miss(jwt_utils 15 / wechat 8 / user 1) 仍 followup

## 3. Plan deviations

| Plan task | What changed | Why |
|-----------|--------------|-----|
| 2.1-2.12 | 加 2.13-2.15 3 个补 test | 摸底 12 test PASS 后 cov 96%,3 行额外 miss(line 41 / 85-86 / 157)需要补 |
| Task 12 (Step 1) | `--cov-fail-under=100` 算 TOTAL 66% 不是 routers/sso.py 单 module 100% | pytest-cov 默认行为;本 change 不触发整体 fail-under(其他 module 仍 followup) |
| D5 (encode_jwt patch) | 仍用 `patch("app.routers.sso.encode_jwt", return_value=...)` 但 sso.py 第 167 行也调 | 不需改 plan,`patch` 默认替换所有 import path 引用 |

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
  - **Why this cycle**: 本 change 仅 1 file 加 + 0 行 prod code,跟之前的 coverage change 同样模式 — 在 main 直接 commit 1 个新 test 文件,worktree 隔离的边际收益 < setup 成本(`.worktrees/<name>` 创建 ~200-500ms,branch + commit + push 全在 main)
  - **How to prevent recurrence**: `CLAUDE.md trigger` — 在 `## Working here` 加 explicit rule:"**当 change 范围 ≤ 2 file 改动 / ≤ 500 行 diff / 0 行 prod code,且 follow `coverage-matrix-v1-followup` family pattern 时,允许跳过 worktree 直接在 main commit**;否则走 worktree 流程"。这条规则覆盖本次 + 之前 7 个 coverage change
- **superpowers:subagent-driven-development**
  - **What was skipped**: 跳过了为每个 task dispatch fresh subagent 的 sub-step
  - **Why this cycle**: 本 change 12 test 跨 4 endpoint,总写时 ~1.5h,micro-cycle 1 test → 1 pytest verify 已经在 main session 内 inlined;dispatch subagent per task 反而引入 context transfer overhead + 失去 pytest output 实时反馈
  - **How to prevent recurrence**: `scope-judgment rule` — subagent-driven 只在 task 数 ≥ 5 **且** 跨多 service 时启用(本 change 全在 sso 单 service,12 test 全 python pytest,无 cross-service 依赖)。CLAUDE.md trigger 写:"**单 service + 单 language + < 20 task 的 coverage 补 test 类 change,跳过 subagent dispatch;其他用 subagent-driven**"

## 5. Surprises

- `MagicMock + AsyncMock` 组合时 `async with mock:` 协议 — `__aenter__` 设为 `AsyncMock(return_value=mock)` 但 `as` target 实际不是 mock 本身。这是 mock-heavy test 的一个"协议"陷阱,需要真 class wrapper 才能稳定。**经验沉淀到 §6 Promote candidate**。
- `asyncio.iscoroutine(first)` 跟 `asyncio.iscoroutinefunction` 不同 — `iscoroutine` 只接受 coroutine object,**`asyncio.ensure_future()` 包装后是 Task 不通过**。需要返回 bare coroutine 才能触发该分支。
- `MagicMock` 属性默认是 `MagicMock`,不是 `AsyncMock`。`await mock.delete(...)` 会 await `MagicMock` instance → 实际 **不** raise 但返回值是 MagicMock(因为 Python 对非 awaitable 不报错,直接返回)。但 `session.add` 链中有**字段 setter** 调用,触发 coroutine 创建 → 报 `RuntimeWarning: coroutine ... was never awaited`。

## 6. Promote candidates → long-term learning

- [ ] 🟡 **async-with 真 class wrapper 模板** → **Promote to project memory** (type: pattern)
  > **Why**: MagicMock + AsyncMock 组合 `async with mock:` 协议不稳,`__aenter__` 的 return_value 不一定到 `as` target。sso `audit_archive` 等同 pattern 已踩过 2 次。
  > **How to apply**: 任何 mock-heavy test 需要 `async with` 时,先复制 `_SessionContextManager` 真 class 模板(`__aenter__` / `__aexit__` 真 coroutine),**不**用 MagicMock。MEMORY: `sso-mock-async-with-pattern.md`

- [ ] 📌 **pytest.raises(match=...) 只能 match str(exc),不能 match e.code** → **Promote to project memory** (type: pattern,重复确认)
  > **Why**: sso followup (5d895e6) 跟本次均踩过 — `pytest.raises(UserError, match="user.wechat_invalid_code")` 失败因为 `match` regex match `str(exc) = e.args[0] = "msg"`,**不** match `e.code`。
  > **How to apply**: 改用 `with pytest.raises(UserError) as exc_info: ...; assert exc_info.value.code == "user.xxx"`,见 `test_coverage_followup.py` §3.2 锁定 pattern

- [ ] 📌 **覆盖率 followup family pattern:plan tasks 估 8-10 endpoint 实际 12+3(摸底补)** → **Promote to project CLAUDE.md** (`## Conventions` 段)
  > **Why**: 8 个 archived coverage change 中 6 个估时偏乐观(估 8-10 实际 12-15)。sso-routers-coverage 是**第 1 次**估时准(1-1.5h 估 → 1.5h 实),但 plan tasks 仍少 3 个(摸底补)
  > **How to apply**: 写新 coverage change plan tasks 时,**先**跑 1 次 `pytest --cov=<module> --cov-report=term-missing` 摸底,把 miss 行号直接列在 plan 2.X task 里,**不**摸底就估 task 数

- [ ] 📌 **openspec change 命名: 1-2 service 范围内用 `<service>-<module>-<verb>` 模式** → **Promote to project CLAUDE.md** (`## Conventions` 段)
  > **Why**: 8 个 coverage change 命名全部一致(sso-routers-coverage / sso-jwt-utils-coverage / credential-alembic-fix / audit-and-isolation-full-cov / llm-client-retry-coverage 等)。新 cycle 命名一致性 = 后续 `grep openspec/changes/archive/*/retrospective.md §4.1 followup` 容易
  > **How to apply**: 新 coverage change 命名 template: `<service-name>-<module-name>-<verb>(coverage|fix|test)`

---
