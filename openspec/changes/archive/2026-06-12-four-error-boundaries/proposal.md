## Why

eng-review 2026-06-10 锁定的 12 个工程决策中,Quality #3 明确"4 错误边界明说 + 加 Error handling section to design doc"。仓库现状:4 边界(Boundary #1 canvas drag-loop / #2 runtime / #3 user / #4 security)均**已散落实现**(`services/workflow-engine/app/errors/` + `services/audit-and-isolation/app/errors.py` + `cycle_detection.py`),但**缺统一契约 + 缺设计文档段**。本次 change **不**抢实现(eng-review 锁定"加 design doc"),只补:`docs/architecture.md` §4.X 错误处理专门段 + 1 个 `error-boundary-contract` capability spec 锁定 4 边界契约,引用既有错误类与 middleware。

## What Changes

**新增 design doc 段**(eng-review Quality #3 锁定)
- From:`docs/architecture.md` 没有 §4.X 错误处理专门段;eng-review 报告里 Quality #3 要求 "Add Error handling section"
- To:在 §4.3 之后、§4.4 之前,新增 `#### 4.3.Z 4 错误边界(eng-review Quality #3 锁定)` 段,覆盖 4 边界(Boundary #1-4)+ 错误响应体统一格式 + 触发位置 + 错误类映射
- Reason:eng-review Quality #3 锁定
- Impact:`docs/architecture.md` 增量 1 段;`CLAUDE.md` 同步 surface `[FUTURE-IMPLEMENTATION]`

**新增 1 capability spec**
- 1 个新 capability `error-boundary-contract` 锁定 4 边界契约:每边界含触发条件 / 错误类 / HTTP 状态 / 响应体 / 触发位置 / 当前实现状态(`[EXISTING]` / `[NEW]`)

**新增 1 个错误类**(本 spec 范围最小化)
- `services/workflow-engine/app/errors/classes.py` 新增 `WorkflowCycleError`(继承 `UserError` 或独立类,本 spec 决定:独立类,语义清晰)
- 触发 Boundary #1(drag-loop),统一进 `middleware.py` 错误响应体
- **不**改既有 `SecurityError` / `UserError` / `WorkflowRuntimeError` / 7-class audit-and-isolation 错误类

**统一错误响应体**
- `{error_class, error_message, request_id}` —— 现有 `services/workflow-engine/app/errors/middleware.py::chatbiz_error_handler` 已有格式
- Boundary #1 走同一 middleware(本 spec 要求新增)
- 顶层目录 §4.3 展开加 `4.3.Z` 链接

## Capabilities

### New Capabilities

- `error-boundary-contract`:4 错误边界统一契约(Boundary #1 canvas drag-loop / #2 runtime / #3 user / #4 security),每边界含触发条件 / 错误类 / HTTP 状态 / 响应体 / 触发位置 / 当前实现状态 + 1 个新增 `WorkflowCycleError` 类让 Boundary #1 走统一 middleware

### Modified Capabilities

无。本 spec **只新增 1 capability**,**不**修改既有 spec 的 REQUIREMENTS。

## Impact

- **新增设计文档段**:`docs/architecture.md` §4.3.Z(预计 100-150 行)
- **新增 1 错误类**:`services/workflow-engine/app/errors/classes.py::WorkflowCycleError`(~10 行)
- **修改 1 middleware**:`services/workflow-engine/app/errors/middleware.py` 加 Boundary #1 handler(~10 行)
- **CLAUDE.md**:加 1 行 `[FUTURE-IMPLEMENTATION] docs/architecture.md §4.3.Z 4 错误边界即将在 four-error-boundaries apply 阶段补全`
- **顶层目录**:`docs/architecture.md` 目录加 `- [4.3.Z 4 错误边界]` 条目
- **新增测试**:`services/workflow-engine/tests/test_workflow_cycle_error.py` 验证 Boundary #1 走统一响应体
- **下游引用**:T2 Node Contract / T4 测试架构 / (新) WorkflowCycleError 实施 spec 引用本段
- **不影响**:`services/audit-and-isolation/app/errors.py` 与 `auth.py` 已有错误类不动
- **[FUTURE-IMPLEMENTATION]** `services/error_handling/` 统一 package 留后续 spec
- **[FUTURE-IMPLEMENTATION]** Boundary #1 在 canvas save(PUT /v1/canvas/{id})端的校验留 V1.0+(MVP 端只验 workflow 启动)

## Non-goals

- **不**合并 2 service 的 errors/ 目录
- **不**重写既有 `SecurityError` / `UserError` / `WorkflowRuntimeError` / 7-class audit-and-isolation 错误类
- **不**改既有 `middleware.py::chatbiz_error_handler` 既有 3 边界 handler,只加 Boundary #1 handler
- **不**实现 `services/error_handling/` 统一 package
- **不**实现 Boundary #1 在 canvas save 端的校验(留 V1.0+)
- **不**改 4 错误响应体格式(沿用 `{error_class, error_message, request_id}`)
- **不**动 12 个 eng-review 决策中的任何其他 11 项
