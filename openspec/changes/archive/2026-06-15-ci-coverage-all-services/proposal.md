## Why

`llm-client-retry-coverage/retrospective.md §4.1` 提议的下一条 change:

> | coverage 门槛 (`--cov-fail-under=100`) 的 propagate |
> | name: `ci-coverage-all-services` |
> | scope: audit-and-isolation / gateway-scanner / workflow-engine 等 services
>   pyproject.toml 加 `--cov-fail-under=100`,使 cov 数字真正 enforce |
> | estimated effort: 1 session, ~3 commits, ~50 行 config |

加上 `coverage-improvement/retrospective §4.4` + `gateway-scanner-coverage-matrix
/retrospective §4.3` 同样跟踪项。

**apply 阶段 chat 摸底** 显示 6 service 现状:

| Service | test | 关键 module 100%? | 需补 test? |
|---|---|---|---|
| audit-and-isolation | 384 | 部分(4 module) | **是**(剩 ~41 module) |
| gateway-scanner | 68 | **是** | 否,只加 fail-under |
| workflow-engine | 287 | 未摸 | **是** |
| credential | 4/15 err | 测试跑不动 | **是**(需先修 15 errors) |
| sso | 8 | 未摸 | **是** |
| mcp | 183 | 未摸 | **是** |

retrospective 估的"~3 commits, ~50 行 config" **严重低估**。真实 scope = 6
service × (摸 cov + 补 test + 加 fail-under) ≈ 1-2 周 followup chain。

**源参考**:
- 触发源:3 个 retrospective §4 共同提议
- 模板:`coverage-improvement` / `gateway-scanner-coverage-matrix` / `llm-client-retry-coverage`
  6 artifact 模板

## What Changes

**Orchestrator change — 产出 6 个 sub-change scaffold,不直接改 prod**:

- From: 6 service `pyproject.toml` 0 / 6 设了 `--cov-fail-under=100`
- To: 6 service pyproject 都加 `--cov-fail-under=100` + `--cov-report=term-missing`
  (跟 `audit-and-isolation` 对齐)
- Reason: 关闭 3 个 retrospective §4 共同提议
- Impact: **non-breaking** (本 change),但 6 sub-change apply 时需要补
  test 到 100% 才能让 fail-under 通过(可能短暂 broken state)

**本 change 产出 6 个 sub-change**(openspec 6 个 sub-change 目录,每个待各自
apply 阶段处理):

1. `ci-coverage-audit-isolation` —— 摸 41 module 起点 + 补 test
2. `ci-coverage-gateway-scanner` —— 加 fail-under(已 100%,trivial)
3. `ci-coverage-workflow-engine` —— 摸 63 prod file 起点 + 补 test
4. `ci-coverage-sso` —— 摸 17 prod file 起点 + 补 test
5. `ci-coverage-mcp` —— 摸 13 prod file 起点 + 补 test
6. `ci-coverage-credential` —— 修 15 errors + 摸 18 prod file + 补 test

## Capabilities

### New Capabilities
- `ci-coverage-all-services-orchestrator`: 创建 6 sub-change scaffold,
  写 6 sub-change 提案 + 依赖图 + apply 顺序建议。本 change 是 meta,
  6 sub-change 各自有独立 spec。

### Modified Capabilities
无。本 change 不直接改任何 capability 的 REQUIREMENTS,只 scaffold 6 个
sub-change。

## Impact

**受影响的代码**:
- 新增跟踪:6 个 `openspec/changes/ci-coverage-{svc}/` 目录(本 change apply 阶段)
- 6 service pyproject.toml 后续在各自 sub-change apply 时改

**前端范围 / 后端范围 / 是否豁免前端**:
- 后端范围:是(6 service 都是 Python)
- 前端范围:否
- **豁免前端**:本 change + 6 sub-change 都不涉及前端

**API / DB / 协议层影响**:无。

**依赖**:无新增 PyPI 依赖。`--cov-fail-under=100` + `--cov-report=term-missing`
是 pytest-cov 6.x 内置(已在 dev 依赖)。

**CI 集成**: 本 change 完**不**自动接 CI workflow(因 6 service 现在也没
cov check workflow)。6 service sub-change apply 后,`--cov-fail-under=100`
会在 `pytest` 跑时触发,但 CI workflow 改造是 separate 范畴(可能 followup)。

## Non-goals

- **NG1**: 本 change 不直接 apply 6 service pyproject —— 6 sub-change 各自 apply
- **NG2**: 本 change 不直接补 6 service 的 test —— 6 sub-change 各自 apply
- **NG3**: 本 change 不修 `credential` 15 errors —— sub-change 第一步处理
- **NG4**: 不加 GitHub Actions workflow 让 6 service cov 跑进 CI —— 留后续
- **NG5**: 不动前端或 docs —— 纯 backend config

## Future-Implementation 标注检查

本 change **不**触及 API/DB/前端契约, **不**适用 `[FUTURE-IMPLEMENTATION]` tag。

## eng-review 冲突检查

本 change **不**触及设计 doc "## GSTACK REVIEW REPORT" 中 12 个锁定决策任一条。
