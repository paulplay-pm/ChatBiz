# ci-coverage-credential-cov-enforce Specification

## Purpose
TBD - created by archiving change ci-coverage-credential. Update Purpose after archive.
## Requirements
### Requirement: 15 import errors 修复 (MUST)
(MUST) `services/credential/tests/` 下的 15 个 test file 全部能成功
import `app.crypto` 等 credential-local module，不再因
`ImportError: cannot import name 'crypto' from 'app'` 失败。修法 MUST
是加 `pythonpath = ["."]` 到 `services/credential/pyproject.toml`
的 `[tool.pytest.ini_options]`,不改任何 conftest.py / 测试代码。

#### Scenario: 修 import 后 15 errors 全消
- **WHEN** 加 `pythonpath = ["."]` 到 `services/credential/pyproject.toml`
- **AND** 跑 `cd services/credential && pytest tests/ --collect-only`
- **THEN** MUST 收集到全部 15+ test,**不**出现 15 errors

### Requirement: credential prod code 100% line coverage (MUST)
(MUST) `services/credential/app/` 下 13 个 prod python file 通过 pytest
单元测试达到 100% line coverage。

#### Scenario: `pytest --cov=app` 显示 100%
- **WHEN** 跑 `cd services/credential && pytest tests/ --cov=app
  --cov-report=term-missing --no-header`
- **THEN** `app/services.py` / `app/audit.py` / `app/crypto.py` / 等
  13 个 file MUST 均显示 `100%`

#### Scenario: 加 fail-under 100% 后 pytest exit 0
- **WHEN** 跑 `cd services/credential && pytest tests/ --cov=app
  --cov-fail-under=100 --no-header`
- **THEN** pytest exit code MUST 是 0

### Requirement: pyproject.toml cov config (MUST)
(MUST) `services/credential/pyproject.toml` 的
`[tool.pytest.ini_options]` MUST 含 `--cov=app` +
`--cov-report=term-missing` + `--cov-fail-under=100` 3 个 flag,以及
`pythonpath = ["."]`,让 credential 跟 5 个前 coverage change 对齐
到同一 cov matrix 标准。

#### Scenario: pyproject 含 3 cov flag
- **WHEN** 读 `services/credential/pyproject.toml` 的
  `[tool.pytest.ini_options]`
- **THEN** MUST 含 `--cov=app` + `--cov-report=term-missing` +
  `--cov-fail-under=100`

#### Scenario: pyproject 含 pythonpath
- **WHEN** 读 `services/credential/pyproject.toml` 的
  `[tool.pytest.ini_options]`
- **THEN** MUST 含 `pythonpath = ["."]`

### Requirement: 既有 production code 契约不变 (MUST)
(MUST) 本 change MUST 不修改 `services/credential/app/` 下任何 prod
python file;本 change 是纯测试 + config followup。

#### Scenario: prod diff = 0
- **WHEN** 本 change apply 完成,`git diff HEAD~<N> HEAD --stat
  services/credential/app/`
- **THEN** 输出 MUST 为空(0 行 prod 改动)

