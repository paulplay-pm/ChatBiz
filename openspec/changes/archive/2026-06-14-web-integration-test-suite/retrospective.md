# Retrospective: web-integration-test-suite

> Written: 2026-06-13 (planning-phase retrospective; apply-phase retro to be appended after verify)
> Commit range: TBD (apply not yet started)
> Worktree: TBD (`.worktrees/web-integration-test-suite` per CLAUDE.md "worktree 目录" 约定)
>
> **Status**: **Planning-phase retrospective** — apply 阶段完成后需追加 §0 Evidence + 修订 §1-§6。本文件记录 design/specs/tasks 阶段已经产生的学习与风险，apply 阶段结束时由 subagent 补充实际执行数据。

---

## 0. Evidence

> 量化前置数据 — apply 阶段完成后由 subagent 填入。

- **Commit range**: `ccde22e..bc15f6a` (1 commit)
- **Diff size**: +2634 / -11 lines, 29 files (5 modified + 24 new)
- **Tasks done**: 16/30 (53% — see §3 Plan deviations; blocked on production compose pre-existing bugs)
- **Active hours**: ~3h
- **Subagent dispatches**: 0 (single-agent apply)
- **New external dependencies**: 0 (pytest/playwright/vitest/docker compose 全部已存在)
- **Bugs encountered post-merge**: 0 (commits not pushed)
- **OpenSpec validate state at archive**: `valid: true` for this change; `validate --all` shows 2 pre-existing historical failures (unrelated to this change)
- **Test coverage signal**:
  - 7 new unit tests in `services/audit-and-isolation/tests/unit/test_chat_echo.py` — all pass
  - 170/170 total audit-and-isolation unit tests pass (no regression)
  - New vitest integration spec: 4 cases written, types-clean, runtime blocked on test stack
  - New playwright integration spec (canvas paul): 3 cases written, types-clean, runtime blocked
  - New playwright integration spec (admin health): 3 cases written, types-clean, runtime blocked

Commit chain (时序):
```
ccde22e (main) refactor(web): rename admin-web to admin
bc15f6a (HEAD) test(web): integration test suite + LLM echo stub
```

---

## 1. Wins

- [planning-phase] **3 个 capability 顶部都显式声明 Frontend Scope**（含前端 / 含后端 / 不新增后端），完全满足 openspec/config.yaml §specs.rules "前后端同步" 与 §apply.rules "MUST: 每个 capability 必须同时落地后端 + 前端"。**避免** admin-bootstrap retrospective 中 "豁免前端需在 spec 顶部显式声明" 教训重演。
- [planning-phase] **proposal Non-goals 节主动列出 5 个不做的事**（4 critical path ②③④ / LLM eval / 性能压测 / CI 接入 / production compose 改动），让 reviewer 一眼看到 scope 边界，**避免** 月底 scope creep。
- [planning-phase] **LLM echo stub env gating 三重防御**（`INTEGRATION_TEST=1` env + 路由表模型名 `echo-test` 隔离 + verify check 拦截 production 误用），完全沿用 admin-bootstrap §"pnpm.onlyBuiltDependencies 一次性 allowlist" 的"分层防御"思路。
- [planning-phase] **D6 测试数据隔离 = 独立 tenant + truncate** 一次想清楚并发写 workflow 互相干扰的问题（eng-review Quality #2 锁定 PG/Redis 双层 state 写竞争是真实风险），**避免** apply 阶段反复重写 fixture。
- [planning-phase] **D8 test compose 写到 `docker-compose-test.yml` 而非 production compose**，openspec/config.yaml §apply.rules "production compose 注册" 显式豁免（design D8 列理由），**避免** apply 阶段被"未注册 production compose"卡住。

## 2. Misses

- 🟡 [planning-phase, painful] **proposal "Open Questions" 5 个 OQ 全部 ✅ 决定** —— design 阶段一次性敲定，但**没**写"OQ 决定依据引用"（如 D1 互斥理由引用 admin-bootstrap retrospective §2.1 的"5173 端口冲突"案例）。apply 阶段如有人质疑 D1 选 compose 互斥而非新占端口，需要翻 admin-bootstrap retro 才能追溯根因。
  - **Mitigation（apply 阶段）**：在 design D1 的"已考虑 alternative A"加一行 `（参 admin-bootstrap retrospective §2.1 5173 端口冲突）`。
- 📌 [planning-phase, nit] **verify.md §7 "Deferred Manual Dogfood" 整节空白** —— 是因为 plan.md 无 `[~]` 标记，**也**因为 4 critical path ②③④ 显式 Non-goal（proposal 已列）。但**没**在 §7 显式说"4 critical path ②③④ 是 Non-goal，非 deferred"，可能让 archive reviewer 误以为"覆盖率 gap 未声明"。
  - **Mitigation（apply 阶段）**：verify.md §7 顶部加一句"**注意**：本 change 4 critical path ②③④ 是 proposal 显式 Non-goal，由后续 3 个 change 接管——这是 scope 决策，不是 coverage gap"。
- 📌 [planning-phase, nit] **tasks.md "编码任务：15" 写错** —— 实际数 18（含 1.1/1.2/1.3 Makefile 入口 4 条 = 4 条而非合并 1 条），且 2.1 Makefile 不算"编码"算"工具配置"。**apply 阶段重算**。
- 📌 [planning-phase, nit] **CLAUDE.md 端口表**写"不修改"但 design D1 与 D8 反复强调"互斥使用"——可能让未来 contributor 误以为可同时起。**Mitigation**：design D8 末尾加一行"`grep -n '互斥' openspec/changes/web-integration-test-suite/design.md` 给 contributor 入口"。

## 3. Plan deviations

> 暂无（plan 未跑）。apply 阶段实际偏差由 subagent 在此节记录。

| Plan task | What changed | Why |
|-----------|--------------|-----|
| TBD | TBD | TBD |

## 4. Skill / workflow compliance

> apply 阶段实际使用情况由 subagent 填入。本节给出 planning 阶段预判（与 admin-bootstrap retrospective 保持一致——该 change 报告所有 superpowers skill 不可用，走 fallback）。

| Skill                                            | Used (planning) | Used (apply, TBD) |
|--------------------------------------------------|-----------------|-------------------|
| superpowers:brainstorming                        | ✗（fallback 手写）| TBD |
| superpowers:writing-plans                        | ✗（fallback 手写）| TBD |
| superpowers:using-git-worktrees                  | n/a（planning 阶段不开 worktree）| TBD |
| superpowers:subagent-driven-development          | n/a（apply 阶段才用）| TBD |
| (transitive) superpowers:test-driven-development | n/a（apply 阶段才用）| TBD |
| (transitive) superpowers:requesting-code-review  | n/a（apply 阶段才用）| TBD |
| superpowers:finishing-a-development-branch       | n/a（archive 阶段）| TBD |

> **Default expectation**: planning 阶段 2 个 ✗（brainstorming + writing-plans fallback），其余 n/a。apply 阶段 subagent 报告实际使用情况。

### Deliberately Skipped Skills

- **superpowers:brainstorming**
  - **What was skipped**: brainstorming skill 的 Q1-Qn 结构化决策模板；改用 admin-bootstrap 同步落地的"手写 decision log + Open Questions" 模式
  - **Why this cycle**: 当前 session skills 列表**未**装载 `superpowers:brainstorming`（与 `admin-bootstrap` retrospective 记录一致）；schema instruction 允许"fall back to manual"
  - **How to prevent recurrence**: `one-off — schema boundary case, no prevention possible`。reason: superpowers plugin 缓存里有但 session 没 enable，跨 session 不可控；`admin-bootstrap` retrospective §4 已记录此现象为常态。

- **superpowers:writing-plans**
  - **What was skipped**: writing-plans skill 的"每个 task 2-5 分钟 micro-step"完整展开
  - **Why this cycle**: 同上 —— session 没装载该 skill
  - **How to prevent recurrence**: `one-off — schema boundary case, no prevention possible`。本 change plan.md 用"节级 micro-step 模板 + 关键 task 完整展开"fallback 模式（与 admin-bootstrap 一致），apply 阶段 subagent 自行展开 micro-step。

## 5. Surprises

- [planning-phase] **LLM echo stub 必须挂在 audit-and-isolation 之后**（eng-review Arch #1 强制）—— 一开始直觉是"为简化直接 mock workflow-engine 的 LLM 节点"，但 brainstorm.md 早期版本 §"方案 C" 就被 reject，理由是失去 audit log 落地断言。**真正落实**到 design D4 的 env gating 三重防御时，发现 audit-and-isolation 的现有 LLM 路由表结构**未知**（pre-build 阶段无代码可 Read）—— apply 阶段必须先 deep dive `services/audit-and-isolation/app/main.py`。
  - **Mitigation**: plan.md Task 1.2 Step 1-2 加注释"apply 阶段先 Read 既有 main.py 路由表再写注册代码"。

- [planning-phase] **Vitest 默认 include 会吞 `e2e/`**（admin-bootstrap retrospective §2 已记录）—— 本 change 在 web/canvas 也有同样问题：`vitest.integration.config.ts` 必须显式 `include: ['tests/integration/**']` + `exclude: ['e2e']`，否则 vitest 会 import `e2e/*.spec.ts` 报"Playwright Test did not expect test() to be called here"。**tasks.md 5.1 漏了 exclude**。
  - **Mitigation（apply 阶段）**: tasks.md 5.1 加 `exclude: ['e2e', 'node_modules']`。

## 6. Promote candidates → long-term learning

- [ ] 🟡 **openspec/config.yaml §apply.rules "production compose 注册"应区分 prod/test stack** → **Promote to openspec/config.yaml**（rules 增补 test 容器豁免规则）
  > **Why**: 本 change 与 `admin-bootstrap` retrospective §2.1 "5173 端口被占用" 都暴露同一问题——prod compose 端口表 vs test compose 端口表的边界未在 config 中显式。每次新 change 写 test infra 都要"显式豁免" + "design 列理由"，是 schema 漏洞。
  > **How to apply**: 当新 change 写 test infra 涉及 docker compose 时，先 grep `openspec/config.yaml` §apply.rules 看是否有 test stack 豁免；如无，apply 阶段在 change 内 design.md 列豁免理由 + 在 §6 提 promote。

- [ ] 📌 **vitest 默认 include 会吞 `e2e/` 是仓库内常态**（admin-bootstrap 与本 change 都踩过）→ **Promote to web/{canvas,admin}/vitest.config.ts 注释**（每个 vitest config 文件顶部加注释）
  > **Why**: vitest 默认 `include: ['**/*.{test,spec}.{ts,tsx}']` 会吞同仓的 e2e/*，与 playwright `test()` 冲突。两个 change 都重写 fix，浪费约 30 分钟 / change。
  > **How to apply**: 任何 web/ 前端 project 首次配 vitest + playwright 时，**默认**显式 `include: ['tests/unit/**']` + `exclude: ['e2e', 'tests/integration', 'node_modules']`，并在 config 顶部加注释解释 why。

- [ ] 📌 **pre-build 阶段 spec 中"扩展点" Scenario** 是 eng-review Test #2 4 critical path ②③④ 的合理 deferral 机制 → **Promote to schema-level guidance**（在 superpowers-bridge schema 的 specs.instruction 加一段"Non-goal + Extension points 模板"）
  > **Why**: 本 change 三个 spec 的"Extension points 为 4 critical path ②③④ 留 spec 钩子" Scenario 是一种新模式：显式 Non-goal（不实现）但 spec 留接入点（让后续 change 复用基础设施）。当前 schema 模板**没有**这种"留钩子"模板。后续 3 个 change（gateway-pii-e2e / manual-approval-resume / plugin-degradation）可机械复用。
  > **How to apply**: 写涉及 4 critical path 的 spec 时，**强制**在 spec 末尾加 "## Extension points for future changes" 一节，列其他 critical path 的接入点 + 复用本 change 哪些基础设施（compose / echo stub / audit-and-isolation / 等）。

- [ ] 🔴 **proposal.md "Open Questions" 5 个 OQ 全部 ✅ 决定 但缺决定依据引用** → **Promote to one-off feedback**（记入团队 mental model）
  > **Why**: design 阶段决定 OQ 时，**没**同步引用"决定依据在哪"（如 admin-bootstrap retrospective / 既有 spec finding / 等）。apply 阶段如 reviewer 质疑，需翻大量上下文才能追溯。
  > **How to apply**: 任何 future change 在 proposal OQ 节做决定时，**强制**写"**依据**：`<文件:节>`" 一行（如 `依据：admin-bootstrap retrospective §2.1 5173 端口冲突`）。这不是 schema 强制，是 change 自身质量门槛。

---

## 7. 与 admin-bootstrap retrospective 的对照（carry-forward 评估）

> admin-bootstrap §6 "Promote candidates" 提了 4 条 unchecked candidate。本 change 评估是否 carry-forward：

| admin-bootstrap §6 candidate | 状态 | 本 change 处理 |
|---|---|---|
| 📌 vitest 默认吞 e2e（admin-bootstrap §2.2）| carry-forward ✅ | 本 change §5 Surprises 第 2 条再次踩坑；本 retro §6 第 2 条 promote |
| 📌 TS 不认 CSS side-effect import | 不涉及 | 本 change 不改 CSS，N/A |
| 🟡 5173 端口冲突 | carry-forward ✅ | 本 change design D1 显式提互斥；本 retro §2 Misses 第 1 条追溯到此 |
| 📌 docker 容器 5173 占用 | carry-forward ✅ | 本 change D1/D8 互斥决策 + verify §1 显式检查 |
