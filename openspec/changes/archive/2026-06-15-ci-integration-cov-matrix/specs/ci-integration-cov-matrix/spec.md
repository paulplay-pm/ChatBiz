<!--
Delta spec for ci-integration-cov-matrix change.

Cap: ci-integration-cov-matrix
Source: openspec/changes/archive/2026-06-15-ci-coverage-sso/retrospective.md §4.3

本 change 加 1 个 GitHub Actions workflow 文件 + 1 段 CLAUDE.md 文本。
0 行 prod code 改动。
-->

## ADDED Requirements

### Requirement: ci-cov.yml workflow MUST 存在 + YAML 合法

MUST 新增 1 个 GitHub Actions workflow 文件
`.github/workflows/ci-cov.yml`,YAML 合法 + 含以下结构:
- `name: ci-cov`
- `on: push: branches: [main]` + `on: pull_request: branches: [main]`
- `jobs.cov.strategy.matrix.service` 列表 4 项:
  `audit-and-isolation` / `credential` / `gateway-scanner` / `sso`
- `jobs.cov.strategy.fail-fast: false`
- `jobs.cov.runs-on: ubuntu-latest`
- 每个 service job 含 5 step:checkout / setup-python@v5
  python-version 3.12 / setup-miniconda@v3 / pip install
  `services/<service>` + test deps / pytest

#### Scenario: ci-cov.yml 文件存在 + 4 service matrix + 5 step
- **WHEN** 仓库根 `ls .github/workflows/ci-cov.yml` 跟
  `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci-cov.yml'))"`
  跑
- **THEN** 文件存在 + YAML 解析无错 + matrix 列表 4 service + 每个
  service job 含 5 step

---

### Requirement: ci-cov.yml workflow MUST 跑 `pytest --cov-fail-under=100`

MUST 每个 service job 最后 1 step 跑 `conda run -n chatbiz pytest
services/<service>/tests/`,**不**传额外 cov flag(让 4 service pyproject
`addopts` 的 `--cov=app` 或 `--cov=gateway_scanner` +
`--cov-fail-under=100` 自动生效)。任何 service pytest exit code 非 0
(因 cov 跌破 100% 或 test fail)MUST 让该 job 失败,PR 整体 fail。

#### Scenario: 4 service pytest 100% 闸门
- **WHEN** GitHub Actions 触发 ci-cov.yml 跑 4 service pytest
- **THEN** 每 service job 跑 `conda run -n chatbiz pytest
  services/<service>/tests/`(依赖 4 service pyproject 的
  `--cov-fail-under=100`),4 service 全 PASS 时 PR 通过;任 1 service
  pytest exit code 非 0(因 cov < 100% 或 test fail)时该 job fail,PR
  整体 fail

---

### Requirement: CLAUDE.md MUST 加 CI 触发约定段

MUST 在 `CLAUDE.md` 加 1 段"CI 触发约定",内容:任何新 service 进
`.github/workflows/ci-cov.yml` matrix 时,**必须**同步更新(不允许
addopts `--cov-fail-under=100` 在 pyproject 但不进 workflow matrix)。

#### Scenario: CLAUDE.md 含 CI 触发约定段
- **WHEN** `grep -A 3 "CI 触发约定" CLAUDE.md` 跑
- **THEN** 命中 ≥1 段说明"新 service 进 matrix 时必须同步"

---

### Requirement: 4 service 本地 pytest 100% MUST 仍 PASS

MUST 在本地 `conda run -n chatbiz pytest services/<service>/tests/` 跑
4 service 仍全 PASS(无 regression)。本要求是 CI workflow 行为的本地
proxy verify — 4 service pyproject addopts 已锁定 `--cov-fail-under=100`,
本 verify 确保 workflow 跑得起来 + 100% 仍稳。

#### Scenario: 4 service 本地 pytest 全 PASS
- **WHEN** `for svc in audit-and-isolation credential gateway-scanner sso;
  do conda run -n chatbiz pytest services/$svc/tests/ -q; done` 跑
- **THEN** 4 service 全 PASS,无 service pytest fail

---

### Requirement: ci-integration-cov-matrix 不需要 workflow-engine / mcp 进 matrix (MUST NOT)

MUST NOT 把 `workflow-engine` / `mcp` 2 service 加进 matrix。2 service
仍是 0 行 test / 0% cov,加进 matrix 会立即让该 job fail。本要求把
2 service 进 matrix 留后续 change 触发(他们 cov matrix 收尾时一并加)。

#### Scenario: matrix 只含 4 service 不含 workflow-engine / mcp
- **WHEN** `grep "service:" .github/workflows/ci-cov.yml` 跑
- **THEN** matrix service 列表 = `[audit-and-isolation, credential,
  gateway-scanner, sso]`,**不**含 `workflow-engine` 或 `mcp`
