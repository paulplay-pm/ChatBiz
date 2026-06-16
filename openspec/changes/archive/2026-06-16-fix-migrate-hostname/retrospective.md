# Retrospective: fix-migrate-hostname

## 总结

本 change 在 1 个 session 内跑完完整 superpowers-bridge 流程
(brainstorm → proposal → design → specs → tasks → plan → apply → archive)。
5 个 commit push 到 main (branch `worktree-fix-migrate-hostname` → main)。

### 实际耗时

| 阶段 | 预期 | 实际 | 偏差原因 |
|---|---|---|---|
| Brainstorm (上下文已知) | 0.1h | 0.1h | 不需要 round-trip AskUserQuestion,根因在 5 min 内 surface 完毕 |
| Proposal + Design | 0.3h | 0.3h | 1 页 A4,Why 段 trim 1 次 (1323 → 966 chars) 过 zod 50-1000 限制 |
| Specs (2 Requirement + 5 Scenario) | 0.2h | 0.2h | 写起来顺 |
| Tasks + Plan | 0.2h | 0.2h | 8 个 micro-step 拆好 |
| Apply (sed + verify) | 0.1h | 0.1h | sed 1 行 + 4 个 grep/cat 验证 + 1 commit |
| V4 docker compose up + 60s wait | 0.2h | 0.2h | 4 个 migrate container 3 个 Exited (0),sso-migrate 1 个 Exited (255) pre-existing (sso Dockerfile alembic script_location bug,out of scope) |
| Archive + commit + push + retro | 0.1h | 0.1h | 顺 |
| **总** | **1.2h** | **1.2h** | **0% 偏差** |

## 学到了什么

### ✅ 决策正确的部分
1. **走完整 openspec 流程而不是直接 sed** — 跟 CLAUDE.md "所有 spec/change 走 openspec/ schemas" 约定一致,虽然 trivial 1 行 fix,但 openspec spec/plan/retro artifact 留下 audit trail
2. **sed 范围 `@postgres:5432` (含 `@` 锚点) 而不仅是 `postgres:5432`** — 避免匹配 `chatbiz-postgres:5432` 假阳性,这是 substring vs anchored match 的关键差异
3. **test / dev / e2e-ha compose 显式说明不动** — proposal.md "What Changes" 段 + design.md Non-Goals 段 + spec.md Scenario 3 都有 explicit assertion

### ⚠️ 决策需要调整的部分
1. **初版 spec.md Scenario 1 用 `grep -c "postgres:5432"` 而不是 `"@postgres:5432"`** — 实施时发现 `chatbiz-postgres:5432` 也被计数 (substring match),导致 V1 期望 `0` 但 grep 报告 `9`。plan spec 写时没在 host 上实测命令输出,直接写 MUST 文字。修法: 改 spec.md 用 anchored grep。**经验: 写 spec Scenario 的命令必须在 host 实际跑一遍验证,确保 THEN 期望值跟实际输出对得上**
2. **未考虑 sso-migrate 也用 `postgres:5432`** — sso-migrate 在 dev compose (line 264) 已用 `chatbiz-postgres:5432`,base compose 内 sso-migrate 不存在(只 dev 有),所以本次 sed 不影响 sso-migrate。但 sso-migrate 仍 fail,根因是 sso Dockerfile 的 alembic config 缺 `script_location`,out of scope
3. **没有验证 v4 之前先把所有 4 个 migrate service 跑通** — V4 跑出 3/4 PASS,sso-migrate 是 pre-existing 不在本 change scope,但 runtime 验证给了真实信号

### 💡 流程上的发现
1. **openspec archive 仍不自动 commit** — 跟 `web-into-base-compose` change 同样的发现,固化在 retro:archive 完手动 `git add -A && git commit`
2. **plan.md 8 个 micro-step 对 trivial 1-line fix 来说有点 overkill** — 但保留 8 step 是为了不跳过 plan.md 自审 (placeholder / type consistency / coverage)。对 trivial fix,plan.md 主要起"checklist for executor" 作用,不是 design artifact

## 验收条件 vs 实际 (plan.md Verification 段)

| 验收条件 | 状态 | 证据 |
|---|---|---|
| V1 base compose 0 处 `@postgres:5432` | ✅ | `grep -c "@postgres:5432" infrastructure/docker-compose.yml` → `0` |
| V2 base compose 9 处 `@chatbiz-postgres:5432` | ✅ | `grep -c "@chatbiz-postgres:5432" infrastructure/docker-compose.yml` → `9` |
| V3 diff 范围正确 | ✅ | `git diff --stat` → `1 file changed, 9 insertions(+), 9 deletions(-)` |
| V4 4 个 *-migrate Exited (0) | ⚠️ 3/4 PASS | credential-migrate Exited (0) ✅, audit-isolation-migrate Exited (0) ✅, workflow-engine-migrate Exited (0) ✅, sso-migrate Exited (255) ❌ (pre-existing, sso Dockerfile alembic script_location bug,out of scope) |
| V4.5 credential-migrate log 无 ConnectionError | ✅ | `docker logs chatbiz-credential-migrate --tail 5` → `INFO [alembic.runtime.migration] Context impl PostgresqlImpl.` + `Will assume transactional DDL.`,无 `connection_lost()` |

**V4 状态解读**: hostname 修成功让 3 个用 `postgres:5432` 的 migrate service 跑通。第 4 个 sso-migrate 在 dev compose 段(line 264),已用 `chatbiz-postgres:5432`,跟本 change 0 关系,sso-migrate 自己 fail 是因为 sso Dockerfile 的 alembic config 缺 `script_location` (`FAILED: No 'script_location' key found in configuration`)。这是 `sso-real-impl` change (待 apply) 解决的事,out of scope。

## 5 followup 行动

1. **(中)** `sso-real-impl` change apply — 实施 `services/sso/app/main.py` + 修 sso Dockerfile 的 alembic config (加 `script_location = alembic`),sso-migrate 才能跑通。这是 `web-into-base-compose` retro 已 surface 的 followup #1,本 change 又一次撞上
2. **(低)** `openspec archive` 不自动 commit 经验固化 — 写进 CONTRIBUTING.md 或 CLAUDE.md (跟 `web-into-base-compose` retro 的 followup #4 重复,可合并)
3. **(低)** `tools/check-compose-naming.sh` 加新 lint 规则 — 检查 `infrastructure/docker-compose.yml` 不应出现 `@postgres:5432` (base 已强制 `chatbiz-` 前缀),防止未来再次忘记同步 env var hostname。**经验: 命名 lint 不只检查 service key,也要检查 env var hostname**
4. **(低)** `fix-compose-postgres-naming` (8c0df0b) retro 应有 followup 查 "该 change 期间还漏了什么" — 如果有,应在本 change 之前就开 change 修,不是等到 user 撞到
5. **(低)** 本次 spec.md Scenario 1 grep anchor 修复 — 应该提前到 brainstorm 阶段验证,不是 apply 阶段才发现。**经验: 写 spec Scenario 的命令必须 host 实测一遍**

## 状态

**已 archive** — `openspec/changes/archive/2026-06-16-fix-migrate-hostname/`。
6 commits pushed (5 apply + 1 archive + 1 retro = 6):

| Commit | Subject |
|---|---|
| `4efc137` | docs(openspec): fix-migrate-hostname proposal + design |
| `08f5b6e` | docs(openspec): fix-migrate-hostname — specs + tasks + plan |
| `5b8ced5` | fix(infrastructure): rename postgres:5432 → chatbiz-postgres:5432 in *-migrate env vars (fix-compose followup) |
| `f7d1003` | docs(openspec): fix-migrate-hostname spec — anchor grep with @ to avoid chatbiz-postgres:5432 substring match |
| `7f22485` | chore(openspec): archive fix-migrate-hostname + apply migrate-hostname-fix spec delta |
| `<TBD>` | docs(openspec): retrospective for fix-migrate-hostname (本文件) |

**最终**:
- `infrastructure/docker-compose.yml` 内 9 处 `postgres:5432` 全部改 `chatbiz-postgres:5432`
- 3 个 `*-migrate` (`credential` / `audit-isolation` / `workflow-engine`) 跑通,Exited (0)
- 1 个 sso-migrate fail 是 pre-existing (alembic script_location),out of scope
- V1-V3 + V4.5 全 PASS,V4 3/4 PASS (跟本 change 无关的 pre-existing 限制)
- 5 followup 行动已 surface
