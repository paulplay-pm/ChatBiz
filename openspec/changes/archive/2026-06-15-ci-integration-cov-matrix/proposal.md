## Why

11 个 coverage change 累计达成 audit-and-isolation / credential / sso /
gateway-scanner 4 service 100% line cov,但 `ci-coverage-sso` retrospective
§4.3 列"CI workflow 不跑"为 followup。`--cov-fail-under=100` 在 4 service
pyproject 锁了,但**只在本地**有效,GitHub Actions 上无对应 workflow,
PR merge main 时**无 cov 100% 闸门**。

现在处理是为 **加 1 个 GitHub Actions workflow 把 4 service pytest + cov
100% 在 push / PR 时跑**,防回归(regression) — cov 从 100% 滑到 99% 立即
PR 失败。

参考源:
- `docs/architecture.md` §4.4(技术栈:Python 3.12 + conda + FastAPI)
- 设计 doc `GSTACK REVIEW REPORT` Quality #2(测试覆盖率)
- 仓库内 11 个 archived coverage change 6-artifact 模板
- 现有 `.github/workflows/gateway-static-scan.yml`(已存在,本 change
  模式参考)

## What Changes

**<CI cov integration matrix>**
- From: 4 service 100% cov 但 **CI 无 cov 闸门**;PR 合并到 main 时
  无 pytest 跑
- To: 1 个 `.github/workflows/ci-cov.yml` workflow,4 service matrix 跑
  `pytest --cov-fail-under=100`,PR / main push 触发
- Reason: 关 retrospective §4.3 followup,防 cov regression
- Impact: 0 行 prod code 改动;新增 1 个 workflow 文件 + CLAUDE.md 1
  段 trigger rule

## Capabilities

### New Capabilities
- `ci-integration-cov-matrix`: 1 个 GitHub Actions workflow
  `.github/workflows/ci-cov.yml`,4 service matrix(audit-and-isolation /
  credential / gateway-scanner / sso)跑 pytest + cov 100% 闸门
  (push / pull_request on main 触发)

### Modified Capabilities
- (无 — 不改 requirement,只加 CI infrastructure + CLAUDE.md trigger
  rule)

## Impact

- **后端范围**: 0 行 prod code 改动
- **CI 范围**: `.github/workflows/ci-cov.yml` 新增 (~80 行)
- **CLAUDE.md 范围**: 加 1 段"CI 触发约定"(本 change 顺带)
- **APIs**: 0 改
- **依赖**: 0 新增 GitHub Action(用 `actions/checkout@v4` /
  `actions/setup-python@v5` / `conda-incubator/setup-miniconda@v3`)
- **0 行 prod code** 改动

## Non-goals

- 不动 4 service 任何 prod code
- 不动 4 service pyproject.toml
- 不动 现有 `.github/workflows/gateway-static-scan.yml`
- workflow-engine / mcp service 仍是 0% cov,本 change **不**进 matrix
  (留后续 change 触发)
- 不引入新 dev dep / new GitHub Action
- 不写 integration test 触真实 PG / Redis(纯本地 mock 跑)
