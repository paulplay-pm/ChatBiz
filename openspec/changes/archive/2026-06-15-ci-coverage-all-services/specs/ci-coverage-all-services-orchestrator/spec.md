<!--
Delta spec for capability `ci-coverage-all-services-orchestrator`.

本 change 是 ADDED-only。apply 完成后被合并到
`openspec/specs/ci-coverage-all-services-orchestrator/spec.md`。

Capability 范围：openspec/changes/ 目录下创建 6 sub-change scaffold + 6
sub-change 各自走 6 artifact 模板。

源：openspec/changes/ci-coverage-all-services/{brainstorm,proposal,design}.md
触发源：3 个 retrospective §4 共同提议
  - coverage-improvement/retrospective.md §4.4
  - gateway-scanner-coverage-matrix/retrospective.md §4.3
  - llm-client-retry-coverage/retrospective.md §4.1
-->

## ADDED Requirements

### Requirement: 6 sub-change scaffold 全部创建 (MUST)
(MUST) 本 change apply 阶段 MUST 创建 6 个 sub-change 目录：
- `openspec/changes/ci-coverage-audit-isolation/`
- `openspec/changes/ci-coverage-gateway-scanner/`
- `openspec/changes/ci-coverage-workflow-engine/`
- `openspec/changes/ci-coverage-sso/`
- `openspec/changes/ci-coverage-mcp/`
- `openspec/changes/ci-coverage-credential/`

每个 sub-change 目录 MUST 含 `.openspec.yaml` (scaffold 默认生成)。

#### Scenario: 6 sub-change 目录存在
- **WHEN** 本 change apply 完成后,`ls openspec/changes/ci-coverage-*/`
- **THEN** 6 个目录全在
- **AND** 每个目录含 `.openspec.yaml`

### Requirement: 每个 sub-change 走完整 6 artifact 模板 (MUST)
(MUST) 6 sub-change 各自 MUST 写 brainstorm / proposal / design / specs / tasks
/ plan 6 个 artifact(verify / retrospective 是 apply 阶段产物)。

模板复用 3 个前 coverage change(`coverage-improvement` /
`gateway-scanner-coverage-matrix` / `llm-client-retry-coverage`)。

#### Scenario: gateway-scanner sub-change 6 artifact 齐
- **WHEN** `ls openspec/changes/ci-coverage-gateway-scanner/`
- **THEN** 6 个 `.md` 文件全在:`brainstorm.md` / `proposal.md` /
  `design.md` / `specs/<capability>/spec.md` / `tasks.md` / `plan.md`

#### Scenario: 6 sub-change 共 36 artifact markdown
- **WHEN** `find openspec/changes/ci-coverage-*/ -name "*.md" | wc -l`
- **THEN** 输出 `>= 36` (6 sub-change × 6 artifact)

### Requirement: sub-change 命名约定一致 (MUST)
(MUST) 6 sub-change 目录名 MUST 严格匹配 `ci-coverage-{service-name}` 格式
(全小写,kebab-case)。

#### Scenario: 6 sub-change 名字列表
- **WHEN** `ls openspec/changes/ | grep ci-coverage-`
- **THEN** 输出 MUST 包含:`ci-coverage-audit-isolation` /
  `ci-coverage-gateway-scanner` / `ci-coverage-workflow-engine` /
  `ci-coverage-sso` / `ci-coverage-mcp` / `ci-coverage-credential`

### Requirement: sub-change 各自独立 apply (MUST)
(MUST) 6 sub-change MUST 互相独立,任何 1 个 apply 失败 MUST **不**影响其他 5
个 apply。

#### Scenario: 1 sub-change apply 失败不影响其他
- **WHEN** `ci-coverage-credential` apply 失败(因 15 errors 修不掉)
- **THEN** 其他 5 sub-change MUST 仍可继续 apply

### Requirement: 6 sub-change 加同 1 套 pyproject config pattern (MUST)
(MUST) 6 sub-change 各自 apply 时 MUST 加 `--cov={module}` +
`--cov-report=term-missing` + `--cov-fail-under=100` 3 个 flag 到对应
service `pyproject.toml` 的 `[tool.pytest.ini_options].addopts`,
`{module}` 是该 service 的 prod python module 顶层包名(例如 `app`)。

#### Scenario: gateway-scanner pyproject 加 3 flag 后
- **WHEN** `ci-coverage-gateway-scanner` apply 完成
- **THEN** `services/gateway-scanner/pyproject.toml` 的
  `[tool.pytest.ini_options].addopts` MUST 含
  `--cov=gateway_scanner --cov-report=term-missing --cov-fail-under=100`

#### Scenario: audit-and-isolation pyproject 加 3 flag 后
- **WHEN** `ci-coverage-audit-isolation` apply 完成
- **THEN** `services/audit-and-isolation/pyproject.toml` 的
  `[tool.pytest.ini_options].addopts` MUST 含
  `--cov=app --cov-report=term-missing --cov-fail-under=100`
  (此 3 flag 已存在 `--cov=app`,只需加 `--cov-report=term-missing`
  + `--cov-fail-under=100`)

### Requirement: 既有 production code 契约不变 (MUST)
(MUST) 本 change **不**修改任何 6 service 的 `app/` 下 production code
或 `pyproject.toml`;本 change 是 orchestrator,只新增 6 sub-change
scaffold。

#### Scenario: prod diff 仅 openspec 目录
- **WHEN** 本 change apply 完成,`git diff HEAD~<N> HEAD --stat | grep "^ services"`
- **THEN** 输出 MUST 为空(0 行 prod / config 改动)
- **AND** `git status --short` MUST 仅含 `openspec/changes/ci-coverage-*/` 文件
