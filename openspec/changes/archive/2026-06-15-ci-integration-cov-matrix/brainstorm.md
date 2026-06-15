<!--
Raw capture of superpowers:brainstorming output for ci-integration-cov-matrix.

来源:openspec/changes/archive/2026-06-15-ci-coverage-sso/retrospective.md §4.3
方式:已通过 brainstorming skill 跑完对话,Q1-Q3 决策链见下
-->

# Brainstorm: ci-integration-cov-matrix

**Date**: 2026-06-15
**Trigger**: `openspec/changes/archive/2026-06-15-ci-coverage-sso/retrospective.md` §4.3
**Owners**: paul (sponsor) + Claude (apply orchestrator)

---

## 背景

11 个 coverage change 累计达成 audit-and-isolation / credential / sso /
gateway-scanner 4 service 100% line cov。`ci-coverage-sso` retrospective
§4.3 把 `ci-integration-cov-matrix` 列为 followup:

> 仍需。`--cov-fail-under=100` 在 pyproject 设了但 CI workflow 不跑。

本 change **加 1 个 GitHub Actions workflow 文件**,把 4 service pytest +
cov 100% 在 PR/push 时跑。

**Stakeholders**: paul(sponsor)/ 未来 contributor / CI 维护者。

**Constraints**:
- 0 行 prod code 改动
- 沿用 conda env `chatbiz`(CLAUDE.md 锁定)
- 4 service 全部有 `addopts` 含 `--cov-fail-under=100`(`gateway-scanner` 用
  `--cov=gateway_scanner`,其他 3 service 用 `--cov=app`)
- workflow-engine / mcp 2 service 仍是 0% cov,本 change **不**进 matrix
  (留后续 change 触发)

## 决策链

### Q1: 1 workflow 4 service matrix 还是 1 service 1 workflow?

**A (选定)**: 1 workflow 4 service matrix (`strategy.matrix.service`)
- 理由: 4 service 全部 100% line cov,matrix 简洁,workflow 维护成本低
- 缺点: 1 service 失败不阻塞其他 service(GitHub Actions matrix 默认
  继续跑其他 service,但 PR 整体 fail)— 这是 desired behavior

**B (拒)**: 1 service 1 workflow(4 workflow 文件)
- 拒绝: 维护成本 × 4,DRY 违反

### Q2: 用 conda + pip 还是 pip + venv?

**A (选定)**: conda env `chatbiz` + `pip install -e` (per-service)
- 理由: 跟 CLAUDE.md 锁定 + 11 个 coverage change 本地验证模式一致
- 缺点: GitHub Actions conda 装慢 1-2 min(可接受)

**B (拒)**: 纯 venv + pip
- 拒绝: `psycopg2-binary` 等需 conda channel 才稳,venv 易踩坑

### Q3: workflow 触发条件?

**A (选定)**: `push` main + `pull_request` main
- 理由: 标准 CI pattern,PR 必跑(防 regression),main push 跑(防直推)
- 缺点: feature branch push 不跑(可接受,feature branch 通过 PR 触发)

**B (拒)**: 1 push / 1 PR (单触发)
- 拒绝: 缺一边回归覆盖

## 拒绝的方案总览

| 方案 | 拒绝理由 |
|---|---|
| 1 service 1 workflow | DRY 违反 × 4 维护成本 |
| 纯 venv + pip | 跟 CLAUDE.md 锁定 conda env 冲突 |
| 单触发条件 | 缺一边回归覆盖 |

## Open Questions

(本轮无 — Q1-Q3 决策链已穷举,选 A 后无需进一步澄清)
