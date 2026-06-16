# Spec: mcp-cov-matrix-add

## ADDED Requirements

### Requirement: ci-cov matrix includes mcp

The repository's `.github/workflows/ci-cov.yml` workflow MUST list `mcp` in
its `matrix.service` array, so that every push to `main` and every pull
request triggers the `pytest --cov-fail-under=100` step for the `mcp` service
in the same way as the existing four services. The `mcp` entry MUST appear
in alphabetical order (i.e. after `gateway-scanner` and before `sso`) so that
the `matrix.service` array reads:
`[audit-and-isolation, credential, gateway-scanner, mcp, sso]`.

#### Scenario: mcp service is in the CI cov matrix
- **WHEN** the CI workflow runs against a push or pull request
- **THEN** a job is dispatched for the `mcp` service which executes
  `conda run -n chatbiz pytest tests/` in `services/mcp/` with the
  `cov-fail-under=100` constraint taken from `services/mcp/pyproject.toml`'s
  `[tool.pytest.ini_options].addopts`

#### Scenario: matrix ordering preserves alphabetical sequence
- **WHEN** the file `.github/workflows/ci-cov.yml` is inspected
- **THEN** the lines under `strategy.matrix.service` MUST list the services
  in alphabetical order with `audit-and-isolation` first and `sso` last:
  `audit-and-isolation`, `credential`, `gateway-scanner`, `mcp`, `sso`

### Requirement: CLAUDE.md CI matrix documentation includes mcp

The repository's `CLAUDE.md` MUST contain a section `### CI 触发约定(强制)`
whose `当前 matrix 列表` array lists `mcp` in the same alphabetical position
as in the workflow file, so the documentation and the workflow do not drift.

#### Scenario: Documentation matches workflow
- **WHEN** a developer reads the `### CI 触发约定(强制)` section in
  `CLAUDE.md`
- **THEN** the `当前 matrix 列表` array MUST be
  `[audit-and-isolation, credential, gateway-scanner, mcp, sso]`,
  identical to the `matrix.service` array in `.github/workflows/ci-cov.yml`

### Requirement: mcp service retains 100% line cov pre-condition

The change that adds `mcp` to the CI cov matrix MUST be applied only after
the mcp service's local `pytest --cov=app --cov-fail-under=100` reports
100% line coverage for every module under `services/mcp/app/`. If the
local cov is below 100% at apply time, the apply MUST abort and report
the missing coverage to the operator.

#### Scenario: Apply with mcp at 100% local cov
- **WHEN** `bash tools/setup-chatbiz-env.sh --service mcp` has been run
  and `conda run -n chatbiz pytest services/mcp/tests/ --cov=app
  --cov-fail-under=100` reports `Required test coverage of 100% reached`
- **THEN** the change may apply: `mcp` is appended to the CI matrix and
  CLAUDE.md is updated

#### Scenario: Apply with mcp below 100% local cov is refused
- **WHEN** the local `pytest --cov=app --cov-fail-under=100` for `mcp`
  reports any line not covered
- **THEN** the change MUST NOT be applied and the operator MUST be told
  to first close the mcp cov gap
