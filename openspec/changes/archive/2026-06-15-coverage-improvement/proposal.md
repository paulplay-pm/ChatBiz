## Why

`openspec/changes/archive/2026-06-15-gateway-egress-enforcement-p0/retrospective.md`
§6.4 第 1 条记录了 V1.0+ followup：

> | Item | Trigger |
> |---|---|
> | Raise project-wide coverage from 83% → 100% | `coverage-improvement` change |

`audit-and-isolation` 项目在归档时覆盖率为 83.23%，本 change
在 V1.0+ 阶段关闭该 gap 的 3 个"low-hanging module"小批量：
`app/jobs/archive_audit.py`、`app/llm/client.py` 的
`compute_idempotency_key`、`app/routing/table.py`。这 3 个模块
的测试桩（前会话产物，untracked 状态）已经就位、跑过 PASS，
本 change 的工作是把它们 formalize 进 openspec 审计链，**不**
是写新代码。

预期收益：(1) `pytest tests/unit/test_coverage_gaps_v1_followup.py
tests/unit/test_routing_table_coverage.py` 12 passed / 1 skipped
绿色信号可追溯到 openspec change；(2) 关闭 retrospective §6.4
第 1 条的一部分（剩余 gateway-scanner 矩阵见 Non-goals）。

**源参考**：
- 触发源：`gateway-egress-enforcement-p0/retrospective.md §6.4`
  （P0 已批准 change 的产物，二次源）
- 验证不冲突三件套（`docs/architecture.md` / `docs/prd.md` /
  设计 doc）：本 change 不触及 API/DB/前端契约，仅追加单元
  测试，不修改任何生产代码

## What Changes

**新增 capability：`audit-isolation-coverage-100pct`**

- From: 3 个目标模块在 V1.0+ 阶段覆盖率未达 100%；2 个测试
  文件以 untracked 状态存在于 working tree，**无** openspec
  引用链
- To: 3 个目标模块单元测试覆盖 100%（pytest-cov 数字，本
  change 范围）；2 个测试文件被 `git add` 跟踪；openspec
  change `coverage-improvement` 提供 proposal → design →
  specs → tasks → plan → verify → retrospective 完整审计链
- Reason: 关闭 retrospective §6.4 第 1 条；给后续
  `coverage-improvement-gateway-scanner` change 留模板
- Impact: non-breaking，纯测试 followup，不影响 prod 行为

**修改 1 个 test（已在 working tree 完成）**：

**`test_retry_with_idempotency_raises_unreachable_no_result`**
- From: broken stub，`inspect.getsource(archive_audit)` 测错
  文件，断言永远 False
- To: `pytest.skip(...)` + docstring 解释 `client.py:304`
  是 defensive unreachable 分支（`MAX_ATTEMPTS=3` 保证 loop
  至少跑一次），引用 sibling `retry_with_redis:121` 的
  `# pragma: no cover` 约定
- Reason: stub 不能留作 broken 状态；跳过 + 审计 trail 比硬
  写 monkey-patch 内部状态更安全
- Impact: 1 个 test 从 FAIL 变成 SKIP；其余 5 个 test 状态不变

**删除 1 个 dead code helper（已在 working tree 完成）**：

**`await_archive_old_audit_logs` async helper**（`test_coverage_gaps_v1_followup.py` line 116-118）
- From: 定义的 async helper，**全文件零调用点**——实际测试
  用 `asyncio.run(archive_old_audit_logs(...))`
- To: 整段删除
- Reason: 前会话 debug 残留，mtime 跟本会话 start 吻合；
  dead code 删后覆盖率不变
- Impact: 0；测试结果 12 passed / 1 skipped 不变

## Capabilities

### New Capabilities
- `audit-isolation-coverage-100pct`: 让
  `services/audit-and-isolation/app/` 下 3 个目标模块
  （`jobs/archive_audit`、`llm/client.compute_idempotency_key`、
  `routing/table`）通过 pytest 单元测试达到 100% line coverage。
  测试文件落在 `services/audit-and-isolation/tests/unit/`。

### Modified Capabilities
无。本 change 不修改任何已存在 capability 的 REQUIREMENTS，
仅新增 1 个 capability。

## Impact

**受影响的代码**：
- 新增跟踪：`services/audit-and-isolation/tests/unit/test_coverage_gaps_v1_followup.py`
  （190 行，5 PASS + 1 SKIP）
- 新增跟踪：`services/audit-and-isolation/tests/unit/test_routing_table_coverage.py`
  （7 个 test，7 PASS）

**前端范围 / 后端范围 / 是否豁免前端**：
- 后端范围：是（`audit-and-isolation` 是 Python FastAPI service）
- 前端范围：否
- **豁免前端**：本 change 仅追加 Python 单元测试，`audit-and-isolation`
  无对应前端组件（trace 查询 UI 在 `web/admin`，但本 change 不动）
  ，故前端范围为空

**API / DB / 协议层影响**：无。本 change 是单元测试 followup，
不修改任何 endpoint、ORM model、wire protocol。

**依赖**：无新增 PyPI 依赖。`pytest`、`pytest-asyncio`、
`unittest.mock` 已在 `services/audit-and-isolation/` dev
依赖中（归档的 `implement-audit-and-isolation` change 已落）。

**eng-review 冲突检查**：本 change **不**触及设计 doc
"## GSTACK REVIEW REPORT" 中 12 个锁定决策（决策 #1 数据隔离
网关 / #2 12 节点 Node Contract / #3 四层记忆 / #4 Workflow +
Chatflow 同 StateGraph / #5 MVP 含 MCP / #6 人工审批节点 /
#7 Node Contract 4 份代码生成 / #8 状态双层 PG+Redis / #9
错误处理 4 边界 / #10 三层测试 + LLM eval / #11 4 个 critical
path 100% 覆盖 / #12 5 存储量预估）任一条。本 change 是测试
followup，不改任何架构决策。

**CI 集成**：本 change 完成后，下游 CI 跑 `pytest
services/audit-and-isolation/tests/unit/` 时新增的 2 个 test
file 会自动加入。当前 `services/audit-and-isolation` 是否有
独立 CI workflow 需要在 apply 阶段确认（task 列表待写）。

## Non-goals

- **不** close retrospective §6.4 第 2 条（`gateway-scanner`
  测试矩阵）—— 留待后续 `coverage-improvement-gateway-scanner`
  或类似 change；本 change 范围明确限于 `audit-and-isolation`
- **不** 写新生产代码（FIX / FEAT）—— 本 change 是测试 followup
  ，只追加/修改 test file，不动 `app/` 下任何非 test 文件
- **不** 修补 `app/llm/client.py:304` 的 unreachable 分支
  —— 那是 defensive code，作者已在 sibling `retry_with_redis:121`
  标 `# pragma: no cover`，本 change 跟随约定
- **不** 引入新的覆盖率门槛（`--cov-fail-under=100` 等）——
  那是 CI 配置变更，超出本 change 范围，留待后续 change
- **不** 重构 `archive_audit.py` 或 `routing/table.py` —— 本
  change 假定现有 prod 代码设计正确，只补 test 桩
- **不** 新增或修改 `services/audit-and-isolation/` 之外的
  任何 service（`web/`、`workflow-engine/` 等均不动）

## Future-Implementation 标注检查

本 change **不**触及 API/DB/前端契约，**不**适用
`[FUTURE-IMPLEMENTATION]` tag。CLAUDE.md config.yaml 规则：
"触及 API/DB/前端的 spec 都要标"——本 change 不属于此范围。
