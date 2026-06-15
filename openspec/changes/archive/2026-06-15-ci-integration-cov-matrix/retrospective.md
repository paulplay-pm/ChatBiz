# Retrospective: ci-integration-cov-matrix

> Written: 2026-06-15 (after verify passed)
> Commit range: `6516f68..2f538e2` (1 new commit in this change range)
> Worktree: merged to main

---

## 0. Evidence

- **Commit range**: `6516f68..2f538e2` (1 new commit: `2f538e2`)
- **Diff size**: +65 / -0 lines across 2 files
  (`.github/workflows/ci-cov.yml` 新增 + `CLAUDE.md` 1 段)
- **Tasks done**: 14/14
- **Active hours**: ~30 min(跟设计 D 估时一致)
- **Subagent dispatches**: 0
- **New external dependencies**: 3 standard GitHub Actions
  (`actions/checkout@v4` / `actions/setup-python@v5` /
  `conda-incubator/setup-miniconda@v3`)— 全部 GitHub 官方
- **Bugs encountered post-merge**: 0
- **OpenSpec validate state at archive**: pass
- **Test coverage signal**:
  - 4 service 仍 100% line cov(audit-and-isolation 1146/1146,
    credential 567/567, gateway-scanner 170/170, sso 354/354)
  - 4 service 本地 pytest 全 PASS(820 total PASS + 13 SKIP)
  - **GA workflow 实际行为待 push 后验证**(本仓库无 GA runner 模拟)

Commit chain:

```
2f538e2 ci(openspec): add ci-cov workflow + CLAUDE.md CI trigger rule
```

---

## 1. Wins

- [evidence: 4 service 本地全 PASS] workflow 加完后 4 service pytest
  仍 100% cov + 全 PASS,无 regression
- [evidence: 1 workflow 4 service matrix] DRY 模式 — 1 workflow 文件
  cover 4 service 100% 闸门,workflow-engine / mcp 仍 0% cov
  锁定不进 matrix
- [evidence: 0 行 prod code 改动] 纯 CI 文件 + 1 段 CLAUDE.md 文本
- [evidence: ~30 min vs 估时 ~30 min] 估时准(本 change 不是 coverage
  change,属基础设施,估时更稳)

## 2. Misses

- 📌 [nit | evidence: GA 行为待 push 验证] 实际 GA workflow 行为
  不能本地 dry-run,需 push 后由 GitHub Actions 验证。本 change
  verify.md §5.5 标 "N/A — push 后 GA 验证",**不**作为 archive 阻塞
- 📌 [nit | evidence: 2 service 仍 0% cov] workflow-engine / mcp
  不进 matrix(0% cov)会立即 fail — scope 排除,留后续 change 触发

## 3. Plan deviations

| Plan task | What changed | Why |
|-----------|--------------|-----|
| 2.1 写 workflow | 加 `name: ci-cov` + 5 step 完整 | 无变化 |
| 3.1 CLAUDE.md 段 | 加在"### Docker Compose service key" 之后,"### 前端目录" 之前 | 跟"约定"主题分组一致 |

## 4. Skill / workflow compliance

| Skill                                            | Used |
|--------------------------------------------------|------|
| superpowers:brainstorming                        | ✓    |
| superpowers:writing-plans                        | ✓    |
| superpowers:using-git-worktrees                  | ✗    |
| superpowers:subagent-driven-development          | ✗    |
| (transitive) superpowers:test-driven-development | ✗(本 change 是 CI 文件,无 test) |
| (transitive) superpowers:requesting-code-review  | ✗    |
| superpowers:finishing-a-development-branch       | ✓    |

### Deliberately Skipped Skills

- **superpowers:using-git-worktrees**
  - 跟之前 coverage change 同 pattern — 1 file 加 + 0 行 prod code。
    实际本 change 加 2 file (`.github/workflows/ci-cov.yml` + CLAUDE.md),
    但都 < 100 行,仍属"≤ 2 file 改动 / ≤ 500 行 diff"范围,CLAUDE.md trigger
    候选 rule 仍适用
- **superpowers:subagent-driven-development**
  - 跳过了 — 本 change 是 1 workflow 文件 + 1 CLAUDE.md 段,小且 linear
- **superpowers:test-driven-development**
  - 跳过了 — 本 change 是 CI 文件,不是 code。workflow YAML 自身由
    `yaml.safe_load` 验合法性(proxy test)

## 5. Surprises

- workflow-engine / mcp 2 service 加 matrix 会立即 fail(0% cov) — 跟
  sso 之前的"sso cov matrix 收尾"模式一致,**scope 排除**是正确的
- 4 service pyproject `addopts` 4 种格式(2 string inline / 2 multi-line
  array)但都含 `--cov-fail-under=100`,workflow 不需要传额外 flag —
  这就是为什么 11 个 coverage change 把 `--cov-fail-under=100` 加进
  pyproject 是正确的,而不是用 `-c` flag 临时传
- GA workflow 实际行为不能本地 dry-run — 本仓库无 `act` 工具或 GitHub
  local runner 模拟。**accept**这个限制,把"行为"验证推到 push 后的
  GA 实际跑

## 6. Promote candidates → long-term learning

- [ ] 📌 **CI workflow 行为验证推到 push 后** → **Promote to project memory** (type: pattern)
  > **Why**: 本仓库无 `act` 工具或 GitHub local runner,workflow 行为
    只能 push 后由 GA 验证。本 change verify.md §5.5 标"N/A — push 后
    GA 验证",不作为 archive 阻塞
  > **How to apply**: 写新 CI workflow change 时,本地只验 YAML 合法 +
    本地 proxy test,workflow 行为推到 push 后 GA 验证。若 fail,revert
    commit 即可。CLAUDE.md trigger 候选

- [ ] 📌 **CI 加 service 时必须同步 pyproject + matrix** → **Promote to project CLAUDE.md** (已加,本 change)
  > **Why**: 防止"addopts --cov-fail-under=100 在 pyproject 但不进
    workflow matrix" 导致 CI 假阳 / 假阴
  > **How to apply**: 已在 `CLAUDE.md` "CI 触发约定(强制)" 段锁定,
    新 service 跟 pyproject addopts + matrix 必须同步

- [ ] 📌 **chatbiz project cov matrix 收尾 — sso 100% + CI 闸门 100%** → **Promote to project memory** (type: milestone)
  > **Why**: 12 个 coverage change(`coverage-improvement` → `sso-user-line-45`)
    累计关闭 retrospective §4.1 全部 4 row + `ci-integration-cov-matrix`
    加 CI 闸门。sso service 100% line cov + 4 service matrix 100% 闸门
    是 chatbiz project 第一个完整 cov 闭环
  > **How to apply**: 后续 `workflow-engine` / `mcp` service coverage
    触发时,沿用同一 pattern(coverage-matrix-v1-followup family +
    CI 同步 matrix 加新 service)

---
