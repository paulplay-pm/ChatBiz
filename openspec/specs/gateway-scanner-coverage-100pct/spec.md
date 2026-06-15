# gateway-scanner-coverage-100pct Specification

## Purpose
TBD - created by archiving change gateway-scanner-coverage-matrix. Update Purpose after archive.
## Requirements
### Requirement: gateway_scanner.scanner 模块 100% 单元测试覆盖 (MUST)
(MUST) 模块 `gateway_scanner/scanner.py` 的所有 public API
（`Violation` dataclass 的 `__str__` + `ScannerConfig` property +
`load_config` + `scan_path`）MUST 拥有可执行的 pytest 单元测试，
使该模块通过 `pytest-cov` 达到 100% line coverage。

#### Scenario: `Violation.__str__` 返回 `file:line:package` 格式
- **WHEN** 构造 `Violation(file=Path("a/b.py"), line=42, package="openai")`
- **THEN** `str(violation)` MUST 等于 `"a/b.py:42:openai"`

#### Scenario: `ScannerConfig.target` property 返回 Path
- **WHEN** 构造 `ScannerConfig(target=Path("/tmp/x"))`
- **THEN** `config.target` MUST 等于 `Path("/tmp/x")`
- **AND** `config.blocklist` MUST 是空 `frozenset`（default）
- **AND** `config.allowlist` MUST 是空 `frozenset`（default）

#### Scenario: `load_config` 解析 YAML blocklist + allowlist
- **WHEN** 调用 `load_config(target=Path("/tmp"), config_path=Path("cfg.yaml"),
  blocklist_path=Path("bl.yaml"), allowlist_path=Path("al.yaml"))`，
  其中 YAML 含 `blocklist: [openai, anthropic]` + `allowlist: [/tmp/safe.py]`
- **THEN** MUST 返回 `ScannerConfig` 含 `blocklist=frozenset({"openai", "anthropic"})`
  + `allowlist=frozenset({Path("/tmp/safe.py")})`

#### Scenario: `scan_path` 在 blocklist package 出现时返回 `Violation`
- **WHEN** 扫描含 `import openai` 的 fixture 文件，blocklist 含
  `"openai"`
- **THEN** MUST 返回至少 1 个 `Violation`，`violation.package == "openai"`
- **AND** `violation.line` MUST 等于 `import openai` 所在行号
- **AND** `violation.file` MUST 等于 fixture 文件的 `Path`

#### Scenario: `scan_path` 在 allowlisted file 中不报 violation
- **WHEN** 扫描含 `import openai` 的 fixture 文件，但 file 在
  `ScannerConfig.allowlist` 内
- **THEN** MUST 返回空 list（allowlist 抑制 violation）

#### Scenario: `scan_path` 在 blocklist package 不出现时返回空 list
- **WHEN** 扫描 fixture 文件不含 blocklist 中任何 package
- **THEN** MUST 返回空 list

### Requirement: gateway_scanner.__main__ 模块 100% 单元测试覆盖 (MUST)
(MUST) 模块 `gateway_scanner/__main__.py` 的 click CLI 入口
（含 `cli` command 装饰器 + 各 option 解析 + 退出码 0/1/2
三档语义）MUST 拥有可执行的 pytest 单元测试，使该模块通过
`pytest-cov` 达到 100% line coverage。

#### Scenario: `cli` 在 0 violation 时 exit code 0
- **WHEN** 调用 `click.testing.CliRunner().invoke(cli, [str(empty_dir)])`
  其中 `empty_dir` 不含任何 blocklist package import
- **THEN** `result.exit_code` MUST 等于 `0`
- **AND** `result.output` MUST 包含 "no violations" 或等价成功消息

#### Scenario: `cli` 在 ≥1 violation 时 exit code 1
- **WHEN** 调用 `CliRunner().invoke(cli, [str(fixture_dir)])` 其中
  `fixture_dir` 含 `import openai`，且 blocklist 含 `"openai"`
- **THEN** `result.exit_code` MUST 等于 `1`
- **AND** `result.output` MUST 至少 1 个 violation 报告

#### Scenario: `cli` 在 path 不存在时 exit code 2
- **WHEN** 调用 `CliRunner().invoke(cli, ["/nonexistent/path"])`
- **THEN** `result.exit_code` MUST 等于 `2`
- **AND** 错误消息 MUST 提示 path 不存在

#### Scenario: `cli` 接受 `--config` / `--blocklist` / `--allowlist` 选项
- **WHEN** 调用 `CliRunner().invoke(cli, [str(fixture_dir),
  "--config", str(cfg), "--blocklist", str(bl), "--allowlist", str(al)])`
- **THEN** MUST 使用显式传入的 config / blocklist / allowlist 文件
  解析（而非默认值）

#### Scenario: `cli` 默认从 `./gateway_scanner.yaml` 读 config
- **WHEN** 当前目录存在 `gateway_scanner.yaml` 含 blocklist
  `["openai"]`，调用 `CliRunner().invoke(cli, [str(fixture_dir)])`
  不传 `--config`
- **THEN** MUST 自动加载该 config

#### Scenario: `cli` 缺省 config 文件时使用空规则
- **WHEN** 当前目录无 `gateway_scanner.yaml`，调用
  `CliRunner().invoke(cli, [str(empty_dir)])` 不传 `--config`
- **THEN** MUST 不报错（空 blocklist = "no rules"），exit code 0

### Requirement: pyproject.toml coverage matrix 配置 (MUST)
(MUST) `services/gateway-scanner/pyproject.toml` 的
`[tool.pytest.ini_options].addopts` 字段 MUST 包含
`--cov=gateway_scanner` 与 `--cov-fail-under=100` 两个 flag，
使该服务跟 `services/audit-and-isolation/pyproject.toml`
对齐到同一 cov 矩阵标准。

#### Scenario: pyproject.toml 含 `--cov=gateway_scanner`
- **WHEN** 读取 `services/gateway-scanner/pyproject.toml` 第
  `[tool.pytest.ini_options].addopts` 字段
- **THEN** MUST 含 `--cov=gateway_scanner`

#### Scenario: pyproject.toml 含 `--cov-fail-under=100`
- **WHEN** 读取 `services/gateway-scanner/pyproject.toml` 第
  `[tool.pytest.ini_options].addopts` 字段
- **THEN** MUST 含 `--cov-fail-under=100`

#### Scenario: 跑 `pytest tests/` 触发 cov 收集
- **WHEN** 在 `services/gateway-scanner/` 目录下运行
  `pytest tests/`
- **THEN** pytest 输出 MUST 含 `--cov=gateway_scanner` 触发报告
  （即 terminal output 出现 `gateway_scanner/scanner.py ... X%` 等
  覆盖率报告行）
- **AND** 若 coverage < 100%，pytest exit code MUST 非 0

### Requirement: 既有 5 个 test file 40 PASS 不被破坏 (MUST)
(MUST) 现有 5 个 test file（`test_smoke.py` / `test_allowlist.py` /
`test_blocklist.py` / `test_ast_scanner.py` / `test_workflow.py`）MUST
保持 40 PASS 状态不被新 test 或 config 变更破坏。

#### Scenario: 既有 5 个 test file 40 PASS
- **WHEN** 在 `services/gateway-scanner/` 目录下运行
  `pytest tests/ --no-cov`
- **THEN** 既有 40 个 test MUST PASS（具体数字以 `pytest --collect-only` 输出为准）
- **AND** MUST 不出现 FAILED 或 ERROR

### Requirement: 既有生产代码契约不变 (MUST)
(MUST) 本 change MUST 不修改 `gateway_scanner/scanner.py` 或
`gateway_scanner/__main__.py` 任何生产代码；本 change 是测试 +
config followup，唯一 prod 改动是 `pyproject.toml` 的 `addopts` 字段
加 2 行 config。

#### Scenario: prod diff 仅 pyproject.toml
- **WHEN** 本 change apply 完成，`git diff HEAD~<N> HEAD --stat
  services/gateway-scanner/`
- **THEN** 输出 MUST 仅含 `tests/` 下 file 增改 + `pyproject.toml` 改
  动
- **AND** `services/gateway-scanner/gateway_scanner/` 下任何 .py 文件
  MUST 0 改动（diff 为零）

