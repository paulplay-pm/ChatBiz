# Retrospective: fix-production-compose

> Written: 2026-06-13 (planning-phase retrospective; apply-phase retro to be appended after verify)
> Commit range: TBD (apply not yet started)
> Worktree: `.worktrees/fix-production-compose` per CLAUDE.md worktree directory convention
>
> **Status**: Planning-phase retrospective — apply 阶段完成后需追加 §0 Evidence + 修订 §1-§6。

---

## 0. Evidence

> 量化前置数据 — apply 阶段完成后由 subagent 填入。

- **Commit range**: TBD
- **Diff size**: TBD（预估 +40/-20 行，2 个文件改：02-create-databases.sql + docker-compose.yml）
- **Tasks done**: TBD
- **Active hours**: TBD
- **Subagent dispatches**: TBD
- **New external dependencies**: 0（psql \gexec 已在 postgres:16-alpine 镜像内）
- **Bugs encountered post-merge**: TBD
- **OpenSpec validate state at archive**: TBD
- **Test coverage signal**: TBD（每个 fix 都有可观察的命令 + 期望输出；不是 unit test 但可重复）

Commit chain (时序): TBD

---

## 1. Wins

- [planning-phase] **3 个 fix 全部对齐 dev compose 已有正确实现**（design D1/D2/D3）—— DRY 原则；不需要发明新方案，只需要把 dev 的正确做法 backport 到 production。
- [planning-phase] **SQL fix 用 psql `\gexec` 而非 fork 镜像**（design D1）—— 保留 `postgres:16-alpine` 不变；不引入 Python 子进程或新工具。
- [planning-phase] **保留 `infrastructure/postgres-init-test/` workaround**（design D4）—— test stack 不依赖 production fix 落地，test independence 保留。
- [planning-phase] **capability 顶部 `Frontend Scope: N/A` 显式声明**（spec.md）—— 纯基础设施层，豁免前端符合 openspec/config.yaml §apply.rules "前后端同步" 例外。
- [planning-phase] **proposal Non-goals 显式列出 7 项**—— port 8000 / test-iam / canvas tsc 等独立 follow-up 不混入本 change。

## 2. Misses

- 🟡 [planning-phase, painful] **本机无法验证全栈 healthy**（Trae IDE 占 port 8000）—— 与 `web-integration-test-suite` retrospective §2 Misses 同一根因；本 change verify 阶段拆为单 fix 单元验证 + 干净 dev 机集成验证。**Mitigation（apply 阶段）**：在 verify.md § 备注 显式标注本机限制；如可能，停 Trae 跑一次完整验证。
- 📌 [planning-phase, nit] **PYTHONPATH 路径硬编码**（设计决策 D2）—— 升 Python 需同步改 3 处。**Mitigation（future）**：dev compose 也硬编码，drift 同步；future change 升级时一起改。
- 📌 [planning-phase, nit] **plan.md Step 1 "Read current 02-create-databases.sql to see exact line numbers"** —— planning 时未直接 Read 02 文件；apply 阶段需先 Read 才知道 DO 块精确范围。

## 3. Plan deviations

> 暂无（plan 未跑）。apply 阶段实际偏差由 subagent 在此节记录。

| Plan task | What changed | Why |
|-----------|--------------|-----|
| TBD | TBD | TBD |

## 4. Skill / workflow compliance

| Skill                                            | Used (planning) | Used (apply, TBD) |
|--------------------------------------------------|-----------------|-------------------|
| superpowers:brainstorming                        | ✗（fallback 手写）| TBD |
| superpowers:writing-plans                        | ✗（fallback 手写）| TBD |
| superpowers:using-git-worktrees                  | ✓（用 EnterWorktree / git worktree add）| TBD |
| superpowers:subagent-driven-development          | n/a（apply 阶段才用）| TBD |
| (transitive) superpowers:test-driven-development | n/a（apply 阶段才用）| TBD |
| (transitive) superpowers:requesting-code-review  | n/a（apply 阶段才用）| TBD |
| superpowers:finishing-a-development-branch       | n/a（archive 阶段）| TBD |

### Deliberately Skipped Skills

- **superpowers:brainstorming** + **superpowers:writing-plans**
  - **What was skipped**: 两个 skill 的结构化模板
  - **Why this cycle**: session skills 列表**未**装载（与 web-integration-test-suite 一致）
  - **How to prevent recurrence**: `one-off — schema boundary case, no prevention possible`。schema instruction 允许 fallback。

## 5. Surprises

- [planning-phase] **本机 port 8000 阻塞是连续第 2 个 change 踩到的环境限制**（admin-bootstrap / web-integration-test-suite / 本 change）—— 三次都是 Trae IDE 占 port。**Mitigation（长期）**：开独立 follow-up 在 CLAUDE.md 加 "环境 port 占用诊断" 章节；或停 Trae 后跑。
- [planning-phase] **`web-integration-test-suite` 留下的 test stack workaround (`postgres-init-test/`) 与本 change production fix 行为一致**—— 不会冲突；test stack 仍可用。两份 SQL init（production 用 02-create-databases.sql；test 用 postgres-init-test/02-create-databases.sql）写法完全相同，只是路径不同。

## 6. Promote candidates → long-term learning

- [ ] 📌 **生产 compose 缺基础 hygiene（PYTHONPATH、master key seed）** 应纳入 `infrastructure/docker-compose.yml` 的 CI lint
  > **Why**: 3 个 latent bug 中 2 个（PYTHONPATH + master key seed）是 dev compose 已正确但 production 漏的"卫生"问题——CI 应自动比对两份 compose 的差异。
  > **How to apply**: 后续 change 加 `docker compose -f infrastructure/docker-compose.yml config` + `docker compose -f infrastructure/docker-compose-dev.yml config` 输出 diff 到 CI 报告；production 漏任何 env / command 时 fail。

- [ ] 📌 **README Known Issues 的 follow-up tracking** 应统一到 openspec changes 列表
  > **Why**: `web-integration-test-suite/README.md` 列出 6 个 follow-up bug；本 change 修 3 个。后续 3 个（port 8000 / test-iam / canvas tsc）也应是独立 openspec change，不应散落在 README。
  > **How to apply**: 每次 archive change 时检查 README 是否有 "follow-up" 关键词；若是，把它转成 openspec proposal 草案。

- [ ] 📌 **port 8000 持续被 Trae IDE 占** 是 3 个连续 change 的环境阻碍
  > **Why**: admin-bootstrap / web-integration-test-suite / 本 change 都被这个环境问题影响；本机 5173 / 8000 / 8080 都被占。**Mitigation（短期）**：每次起 stack 前停 Trae；**Mitigation（长期）**：开独立 CLAUDE.md fragment 记录"本机环境 port 占用"清单 + 排查步骤。
  > **How to apply**: 后续 change 需要在干净 env 验证时，第一步跑 `lsof -i :8000` 等；如有占用，提示停 Trae。

## 7. 与 web-integration-test-suite retrospective 的对照

| web-integration-test-suite §6 candidate | 状态 | 本 change 处理 |
|---|---|---|
| 📌 vitest 默认吞 e2e | carry-forward | 不涉及 vitest 配置；N/A |
| 📌 TS 不认 CSS side-effect import | 不涉及 | N/A |
| 🟡 5173 端口冲突 | carry-forward | 不再被 5173 阻塞（Trae 占 8000，不占 5173） |
| 📌 docker 容器 5173 占用 | carry-forward | 同样 5173 / 8000 / 8080；本机 8000 仍占 |
| 🟡 production compose latent bugs | ✅ **本 change 直接修** | D1/D2/D3 三个 fix |
| 📌 port 8000 持续被 Trae 占 | carry-forward | 本 change 同样撞；开 CLAUDE.md fragment 提议 |
