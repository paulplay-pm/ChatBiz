## Why

`openspec/changes/archive/2026-06-15-gateway-egress-enforcement-p0/retrospective.md`
§6.4 row 2 记录了 V1.0+ followup：

> | Add `services/gateway-scanner/tests/` to the coverage matrix | `coverage-improvement` change |

`gateway-scanner` 服务当前**不在覆盖率矩阵内**：`pyproject.toml`
缺 `--cov=gateway_scanner` + `--cov-fail-under=100`（对比
`audit-and-isolation` 已有这俩配置）。`pytest tests/` 40/40 PASS
但**只测了 50% 行**：`scanner.py` 65% / `__main__.py` 0%。

本 change 紧接 `coverage-improvement` archive（commit 7fe8e91）
后立即跟进，把 `gateway-scanner` 拉进跟 `audit-and-isolation` 对齐
的 cov 矩阵：改 `pyproject.toml` 加 2 行 config + 补 ~5-7 个 test
达 100%。

**源参考**：
- 触发源：`gateway-egress-enforcement-p0/retrospective.md §6.4 row 2`
- 模板：`coverage-improvement/retrospective.md §4.1`（本 change 的
  pattern 锁定）

## What Changes

**新增 capability：`gateway-scanner-coverage-100pct`**

- From: `gateway-scanner` 服务 50% line coverage（scanner.py 65%，
  `__main__.py` 0%），`pyproject.toml` 无 `--cov` / `--cov-fail-under`
- To: `gateway-scanner` 服务 100% line coverage（scanner.py 100%，
  `__main__.py` 100%），`pyproject.toml` 加 `--cov=gateway_scanner`
  + `--cov-fail-under=100`
- Reason: 关闭 retrospective §6.4 row 2；让 `gateway-scanner` 跟
  `audit-and-isolation` 对齐到 100% line coverage 标准
- Impact: **non-breaking**。`pyproject.toml` config 变更是 test-time
  行为，prod 行为不变；test 新增是 additive

**新增 1 个 prod 改动**：

**`services/gateway-scanner/pyproject.toml` `[tool.pytest.ini_options]`
addopts 字段**
- From: `addopts = "-v"`
- To: `addopts = "-v --cov=gateway_scanner --cov-fail-under=100"`
- Reason: 把 `gateway_scanner` 模块加入 pytest-cov 收集目标，并设
  fail-under 100%（与 `audit-and-isolation` 对齐）
- Impact: **non-breaking**。`--cov` 跟 `--cov-fail-under` 只在
  pytest 跑测试时生效，不影响 prod 行为；现有 40 PASS 不会因此 fail
  （如果 fail 说明补 test 数量不足，会被 apply Task 3 拦截）

**新增 ~5-7 个 test 函数**（`tests/` 下某个文件，根据具体 missing
lines 决定加在 test_smoke / test_ast_scanner / 新 test_main 哪个）
- From: scanner.py 38 missing + `__main__.py` 35 missing = 73 missing
- To: 0 missing
- Reason: 让 2 个 prod file 100% line coverage
- Impact: **non-breaking**。test 新增是 additive，不改 prod 行为

## Capabilities

### New Capabilities
- `gateway-scanner-coverage-100pct`: 让
  `services/gateway-scanner/gateway_scanner/` 下 2 个目标模块
  （`scanner.py` + `__main__.py`）通过 pytest 单元测试达到
  100% line coverage。配置变更落到
  `services/gateway-scanner/pyproject.toml`。

### Modified Capabilities
无。本 change 不修改任何已存在 capability 的 REQUIREMENTS，仅
新增 1 个 capability。

## Impact

**受影响的代码**：
- 改：`services/gateway-scanner/pyproject.toml`（`[tool.pytest.ini_options].addopts`
  加 2 行）
- 新增：`services/gateway-scanner/tests/` 下 ~5-7 个 test 函数
  （具体文件待 apply 阶段跑 cov 决定）

**前端范围 / 后端范围 / 是否豁免前端**：
- 后端范围：是（`gateway-scanner` 是 Python CLI 工具，跟
  `audit-and-isolation` 同语言栈）
- 前端范围：否
- **豁免前端**：本 change 仅改 `gateway-scanner` Python 测试 + 1 个
  config 文件。`gateway-scanner` 无前端组件（纯静态 AST scanner
  CLI），故前端范围为空

**API / DB / 协议层影响**：无。本 change 是测试 + config followup，
不修改 CLI command、AST scanner 行为、blocklist/allowlist 解析逻辑。

**依赖**：无新增 PyPI 依赖。`click.testing.CliRunner` 是
`click>=8.1`（已锁 prod dep）的内置模块。

**CI 集成**：本 change 完**不**自动接 CI（Non-goal NG2）。`pyproject.toml`
的 `--cov` 配置仅在本地 `pytest` 跑时生效；CI workflow 改造留待
后续 `ci-coverage-all-services` change。

## Non-goals

- **NG1**：不删 `services/gateway-scanner/services/gateway-scanner/tests/`
  nested 空目录 —— 留待 `scaffold-cleanup` change
- **NG2**：不加 GitHub Actions workflow 把 gateway-scanner cov 跑进
  CI —— 留待 `ci-coverage-all-services` change
- **NG3**：不改 `scanner.py` / `__main__.py` 任何生产代码 —— 本
  change 是 test + config followup，不重构
- **NG4**：不引入新 PyPI 依赖 —— `click.testing.CliRunner` 是
  `click` 内置
- **NG5**：不重新打开 `coverage-improvement` change 的范围 —— 本
  change 范围明确限 `gateway-scanner`，不动 `audit-and-isolation`

## Future-Implementation 标注检查

本 change **不**触及 API/DB/前端契约，**不**适用
`[FUTURE-IMPLEMENTATION]` tag。CLAUDE.md config.yaml 规则：
"触及 API/DB/前端的 spec 都要标"——本 change 不属于此范围。

## eng-review 冲突检查

本 change **不**触及设计 doc "## GSTACK REVIEW REPORT" 中 12 个
锁定决策任一条。本 change 是测试 + config followup，不改任何
架构决策。
