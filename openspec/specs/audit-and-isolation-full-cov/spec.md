# audit-and-isolation-full-cov Specification

## Purpose
TBD - created by archiving change audit-and-isolation-full-cov. Update Purpose after archive.
## Requirements
### Requirement: 4 module 100% line coverage (MUST)
(MUST) `services/audit-and-isolation/app/` 下 4 个 prod python file
(`audit_archive.py` / `chat.py` / `traces.py` / `perf/contracts.py`)通过
pytest 单元测试达到 100% line coverage。

#### Scenario: audit_archive.py 达 100%
- **WHEN** 跑 `cd services/audit-and-isolation && pytest tests/ --cov=app
  --cov-report=term-missing --no-header`
- **THEN** `app/api/audit_archive.py` MUST 显示 `100%`(85 stmts 0 miss)

#### Scenario: chat.py 达 100%
- **WHEN** 跑同上
- **THEN** `app/api/chat.py` MUST 显示 `100%`(142 stmts 0 miss)

#### Scenario: traces.py 达 100%
- **WHEN** 跑同上
- **THEN** `app/api/traces.py` MUST 显示 `100%`(53 stmts 0 miss)

#### Scenario: perf/contracts.py 达 100%
- **WHEN** 跑同上
- **THEN** `app/perf/contracts.py` MUST 显示 `100%`(54 stmts 0 miss)

### Requirement: 既有 384 PASS 不被破坏 (MUST)
(MUST) 现有 384 个 test 在 `services/audit-and-isolation/tests/` MUST 保持
PASS 状态不被新 test 破坏。

#### Scenario: 既有 384 PASS 保持
- **WHEN** 在 `services/audit-and-isolation/` 目录下运行
  `pytest tests/ --no-cov`
- **THEN** 既有 384 个 test MUST PASS
- **AND** MUST 不出现 FAILED 或 ERROR

### Requirement: 既有 production code 契约不变 (MUST)
(MUST) 本 change MUST 不修改 `services/audit-and-isolation/app/` 下任何
prod python file;本 change 是纯测试 followup,0 行 source 改动。

#### Scenario: prod diff = 0
- **WHEN** 本 change apply 完成,`git diff HEAD~<N> HEAD --stat
  services/audit-and-isolation/app/`
- **THEN** 输出 MUST 为空(0 行 prod 改动)

