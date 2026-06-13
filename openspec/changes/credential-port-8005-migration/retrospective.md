# Retrospective: credential-port-8005-migration

> Written: 2026-06-13 (planning-phase retrospective)
> Commit range: TBD (apply not yet started)
> Worktree: `.worktrees/credential-port-8005` per CLAUDE.md worktree directory convention

---

## 0. Evidence

> apply 阶段完成后由 subagent 填入。

- **Commit range**: TBD
- **Diff size**: TBD（预估 +5/-3 行，4 文件改：docker-compose.yml + README.md + locustfile.py + CLAUDE.md）
- **Tasks done**: TBD
- **Active hours**: TBD
- **Subagent dispatches**: TBD
- **New external dependencies**: 0
- **Bugs encountered post-merge**: TBD
- **OpenSpec validate state at archive**: TBD
- **Test coverage signal**: 7-service up + 3 curl health + inter-service 链路通

Commit chain (时序): TBD

---

## 1. Wins

- [planning-phase] **改动范围最小**（design D1-D4）— 4 文件 + 1 端口表行，零 service 代码改动。
- [planning-phase] **Container-internal 8000 保持**（D2）— 既有 audit-and-isolation / workflow-engine CREDENTIAL_SERVICE_URL 零改动。
- [planning-phase] **CLAUDE.md 8000 行不删**（D4）— 审计追踪完整；新 reader 看备注知道历史。

## 2. Misses

- 🟡 [planning-phase, painful] **本机 Trae IDE 占 8000 是 4 个连续 change 踩到的环境限制**（admin-bootstrap / web-integration-test-suite / fix-production-compose / 本 change）— 4 次都是同一根因。**Mitigation（长期）**：在 CLAUDE.md 加"环境 port 占用诊断"章节。
- 📌 [planning-phase, nit] **Locust 改 --host 是唯一运行时影响**—— release notes 需显式列 "BREAKING: credential host port 8000 → 8005"。

## 3. Plan deviations

| Plan task | What changed | Why |
|-----------|--------------|-----|
| TBD | TBD | TBD |

## 4. Skill / workflow compliance

| Skill                                            | Used (planning) | Used (apply, TBD) |
|--------------------------------------------------|-----------------|-------------------|
| superpowers:brainstorming                        | ✗（fallback 手写）| TBD |
| superpowers:writing-plans                        | ✗（fallback 手写）| TBD |
| superpowers:using-git-worktrees                  | ✓ | TBD |
| superpowers:subagent-driven-development          | n/a | TBD |
| superpowers:finishing-a-development-branch       | n/a | TBD |

### Deliberately Skipped Skills

- **superpowers:brainstorming + writing-plans** — session 未装载（与前 2 change 一致）。`one-off — schema boundary case`。

## 5. Surprises

- [planning-phase] **本机 8005 free**（lsof 已验）— Trae IDE 只占 8000，8001/8004/8005/8080 全部 free。意味着前 3 change 的 7-service 端到端 验证其实可以跑通，本 change 改完即可解锁。

## 6. Promote candidates → long-term learning

- [ ] 📌 **port 8000 持续被 Trae IDE 占** 应纳入 CLAUDE.md "环境 port 占用"章节
  > **Why**: 4 个连续 change 都被这个环境问题影响
  > **How to apply**: 后续 change 需要在干净 env 验证时，第一步跑 `lsof -i :8000/8001/8004/8080/5173/5432/6379`；如有占用，提示停 Trae 或改端口

- [ ] 📌 **CLAUDE.md 端口表的 "migrated from" 备注** 是新模式 — 后续端口迁移应统一
  > **Why**: 本 change 在 8000 行加"已迁移到 8005 (2026-06-13)" + 备注；后续端口迁移应遵循同一格式
  > **How to apply**: 任何 change 改端口表时, 旧行标"已迁移到 <新端口> (<日期>)", 备注列加 "见 change <change-name>"

## 7. 与前 2 change retrospective 的对照

| 前 change §6 candidate | 状态 | 本 change 处理 |
|---|---|---|
| 📌 port 8000 持续被 Trae 占 (web-integration-test-suite) | ✅ **本 change 直接修** | D1 选 8005 + container-internal 不动 |
| 📌 生产 compose latent bugs (web-integration-test-suite) | carry-forward | 不涉及；fix-production-compose 已修 |
| 📌 CI lint 改 compose diff (fix-production-compose) | carry-forward | 不涉及；future change |
