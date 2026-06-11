# workflow-engine-unit-test-coverage Specification

## Purpose
TBD - created by archiving change fix-workflow-engine-100pct-coverage. Update Purpose after archive.
## Requirements
### Requirement: workflow-engine 单元测试覆盖率 100%
`python -m pytest tests/ --cov=app --cov-fail-under=100` MUST 在 workflow-engine 真实运行并通过。覆盖率门槛 MUST 不低于 100%(per CLAUDE.md 锁定)。

#### Scenario: pytest + coverage gate 通过
- **WHEN** 在 `services/workflow-engine` 目录执行 `conda run -n chatbiz python -m pytest tests/`
- **THEN** 命令 MUST 退出码 0,无 `--cov-fail-under=100` 失败;e2e + security + unit + 已有测试 全部通过

#### Scenario: 单元测试 ≥ 30
- **WHEN** 列出 `services/workflow-engine/tests/unit/test_*.py`
- **THEN** MUST 至少 30 个文件,覆盖 `errors/`, `clients/`, `graph/`, `executor/`, `cron/`, `api/`, `nodes/` 所有 module

### Requirement: 不降低 coverage 阈值
CLAUDE.md 锁定的 100% coverage 标准 MUST 不得静默降低。

#### Scenario: 阈值保持
- **WHEN** `pyproject.toml` 中 `addopts = "... --cov-fail-under=100"` 必须保留
- **THEN** 不允许改为 80/90 等更低值

