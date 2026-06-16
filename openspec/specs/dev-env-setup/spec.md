# dev-env-setup Specification

## Purpose
TBD - created by archiving change setup-chatbiz-env. Update Purpose after archive.
## Requirements
### Requirement: 1-shot setup script

The repository MUST provide `tools/setup-chatbiz-env.sh` that, when invoked without
arguments, performs a 1-shot setup of the ChatBiz Python backend development
environment: (a) ensures a conda environment named `chatbiz` exists with Python
3.12, (b) installs shared build tooling (pip / wheel / setuptools) into that
environment, and (c) for each of the four services in the ci-cov matrix
(`audit-and-isolation`, `credential`, `gateway-scanner`, `sso`) runs
`pip install -e ".[dev]"` inside the corresponding `services/<name>/` directory.

The script MUST follow the same conventions as the existing
`tools/check-compose-naming.sh`: `set -euo pipefail`, header docstring documenting
decisions / usage / exit codes, bash 4+ / macOS BSD awk compatibility (use
character classes such as `[^[:space:]]` rather than `\S`).

#### Scenario: New developer runs setup on a clean machine
- **WHEN** `bash tools/setup-chatbiz-env.sh` is invoked on a machine where the
  `chatbiz` conda env does not exist
- **THEN** the script creates the env with `conda create -n chatbiz python=3.12`,
  installs shared build tooling, and exits 0 after installing the dev deps of
  all four ci-cov matrix services

#### Scenario: Setup on a machine that already has the env
- **WHEN** `bash tools/setup-chatbiz-env.sh` is invoked on a machine where the
  `chatbiz` conda env already exists
- **THEN** the script skips env creation, upgrades shared build tooling, and
  re-installs (or refreshes) the dev deps of all four ci-cov matrix services,
  exiting 0

### Requirement: `--check` mode performs dry-run verification

The script MUST support a `--check` flag that performs verification only and
MUST NOT modify the conda environment or any installed packages. In `--check`
mode, for each of the four ci-cov matrix services the script MUST resolve the
PEP 621 `[project].name` from `services/<name>/pyproject.toml` and call
`pip show <name>` inside the `chatbiz` env to obtain the `Location:` field.
The location MUST equal the absolute path of `services/<name>/` for the check
to pass; otherwise the check fails with a remediation message that names the
service and the exact command (`--service <name>`) to repair the installation.

#### Scenario: All four services editable-installed at the expected paths
- **WHEN** `bash tools/setup-chatbiz-env.sh --check` is run from a checkout
  where all four services are editable-installed in the `chatbiz` env at their
  `services/<name>/` paths
- **THEN** the script reports `[OK]` for each service, prints an `OK:` summary
  line, and exits 0

#### Scenario: Service is not editable-installed in this checkout
- **WHEN** `bash tools/setup-chatbiz-env.sh --check` is run from a checkout
  where one or more services are not editable-installed at the expected path
  (e.g. a worktree where the env was installed against a different repository
  path)
- **THEN** the script reports `[FAIL]` for each missing service, prints the
  exact `--service <name>` command to repair, and exits with code 3

#### Scenario: `--check` mode does not modify the environment
- **WHEN** `bash tools/setup-chatbiz-env.sh --check` is run
- **THEN** the script MUST NOT call `pip install`, `pip upgrade`, or any other
  state-modifying command, and MUST NOT recreate or alter the conda env

### Requirement: `--env-only` and `--service <name>` modes

The script MUST support two additional modes for partial operations:

- `--env-only` MUST create / verify the `chatbiz` conda env and install shared
  build tooling, but MUST NOT install any service dev deps.
- `--service <name>` MUST install dev deps for the single named service
  (running `pip install -e ".[dev]"` in `services/<name>/`). The service name
  MUST be one of the four ci-cov matrix services
  (`audit-and-isolation`, `credential`, `gateway-scanner`, `sso`); an unknown
  service name MUST cause the script to exit with code 1 and print a clear error.

#### Scenario: Developer re-installs a single service after pyproject changes
- **WHEN** `bash tools/setup-chatbiz-env.sh --service sso` is run after
  `services/sso/pyproject.toml` has been modified
- **THEN** the script installs `sso` dev deps in editable mode and exits 0,
  without touching the other three services

#### Scenario: Unknown service name is rejected
- **WHEN** `bash tools/setup-chatbiz-env.sh --service does-not-exist` is run
- **THEN** the script prints an error identifying the unknown name and exits 1

### Requirement: Documented exit codes and usage

The script MUST print its docstring (decisions / usage / exit codes) to
standard output when invoked with `-h` or `--help`. The header docstring MUST
document exit codes:
- `0` — setup completed (or `--check` passed)
- `1` — `conda` not in PATH, env creation failure, or unknown CLI argument
- `2` — at least one service's `pip install` failed
- `3` — `--check` reported at least one service as not editable-installed

#### Scenario: Operator runs `--help`
- **WHEN** `bash tools/setup-chatbiz-env.sh --help` is run
- **THEN** the script prints the head of its docstring (decisions / usage /
  exit codes) and exits 0

### Requirement: CLAUDE.md references the setup script

The repository's `CLAUDE.md` MUST contain a `### Python 后端环境设置(强制)`
section that:
- States that the first step for a new developer is to run
  `bash tools/setup-chatbiz-env.sh`
- Cross-references the memory `[[conda-chatbiz-env]]` constraint that the
  `chatbiz` conda env is the only acceptable Python interpreter for ChatBiz
  backend code
- Documents the common invocations: `--check` (dry-run verification),
  `--service <name>` (single service re-install), `--env-only` (env without
  service deps)

#### Scenario: New developer reads CLAUDE.md
- **WHEN** a developer opens `CLAUDE.md` looking for environment setup
  instructions
- **THEN** the `### Python 后端环境设置(强制)` section is present, names
  `bash tools/setup-chatbiz-env.sh` as the entry point, cross-references
  `[[conda-chatbiz-env]]`, and lists `--check` / `--service <name>` /
  `--env-only` invocations

