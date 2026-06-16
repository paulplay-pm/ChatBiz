# Spec: workflow-engine-ci-cov-matrix

## ADDED Requirements

### Requirement: ci-cov matrix includes workflow-engine

The repository's `.github/workflows/ci-cov.yml` workflow MUST list
`workflow-engine` in its `matrix.service` array, so that every push to
`main` and every pull request triggers the `pytest --cov-fail-under=100`
step for the `workflow-engine` service in the same way as the existing
five services. The `workflow-engine` entry MUST appear in alphabetical
order (i.e. after `gateway-scanner` and before `mcp`) so that the
`matrix.service` array reads:
`[audit-and-isolation, credential, gateway-scanner, workflow-engine, mcp, sso]`.

#### Scenario: workflow-engine service is in the CI cov matrix
- **WHEN** the CI workflow runs against a push or pull request
- **THEN** a job is dispatched for the `workflow-engine` service which
  executes `conda run -n chatbiz pytest tests/` in `services/workflow-engine/`
  with the `cov-fail-under=100` constraint taken from
  `services/workflow-engine/pyproject.toml`'s
  `[tool.pytest.ini_options].addopts`

#### Scenario: matrix ordering preserves alphabetical sequence
- **WHEN** the file `.github/workflows/ci-cov.yml` is inspected
- **THEN** the lines under `strategy.matrix.service` MUST list the services
  in alphabetical order with `audit-and-isolation` first and `sso` last:
  `audit-and-isolation`, `credential`, `gateway-scanner`, `workflow-engine`,
  `mcp`, `sso`

### Requirement: CLAUDE.md CI matrix documentation includes workflow-engine

The repository's `CLAUDE.md` MUST contain a section `### CI 触发约定(强制)`
whose `当前 matrix 列表` array lists `workflow-engine` in the same
alphabetical position as in the workflow file, so the documentation and
the workflow do not drift. The CLAUDE.md section MUST also remove the
now-stale sentence "**workflow-engine / mcp 2 service 仍是 0% cov,本约定
未触发** — 他们 cov matrix 收尾时一并加" because mcp is already in the
matrix and workflow-engine is being added by this change.

#### Scenario: Documentation matches workflow
- **WHEN** a developer reads the `### CI 触发约定(强制)` section in
  `CLAUDE.md`
- **THEN** the `当前 matrix 列表` array MUST be
  `[audit-and-isolation, credential, gateway-scanner, workflow-engine, mcp, sso]`,
  identical to the `matrix.service` array in `.github/workflows/ci-cov.yml`,
  and the stale "**workflow-engine / mcp 2 service 仍是 0% cov**" sentence
  MUST NOT be present

### Requirement: cov tool false negative is acknowledged in CLAUDE.md

The repository's `CLAUDE.md` MUST contain, in the `### CI 触发约定(强制)`
section after the matrix list, a sentence that acknowledges the
`coverage.py` 7.14.1 false negative on
`services/workflow-engine/app/api/workflows.py` `list_workflows` (the
cov tool reports lines 40-50 / 53-56 as missing despite those lines being
exercised by the existing tests — confirmed by `print` trace in
`coverage-false-negative-investigation`). This acknowledgement is a
living pointer for future contributors; it MUST be removed once the
cov tool bug is fixed (tracked as a follow-up in the retrospective).

#### Scenario: cov tool false negative is documented
- **WHEN** a developer reads the `### CI 触发约定(强制)` section in
  `CLAUDE.md` after this change is applied
- **THEN** the section contains a sentence pointing to
  `coverage-false-negative-investigation` and explaining that the
  workflow-engine CI job is expected to fail until that follow-up is
  resolved
