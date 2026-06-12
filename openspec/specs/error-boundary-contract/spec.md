# error-boundary-contract Specification

## Purpose
TBD - created by archiving change four-error-boundaries. Update Purpose after archive.
## Requirements
### Requirement: 4 错误边界 MUST 统一契约(eng-review Quality #3 锁定)

`docs/architecture.md` MUST 在 §4.3 之后、§4.4 之前,新增 `#### 4.3.Z 4 错误边界(eng-review Quality #3 锁定)` 段。段内 MUST 覆盖 4 边界(Boundary #1 canvas drag-loop / #2 runtime(LLM 5xx / timeout / 限额)/ #3 user(参数不全 / 未定义变量)/ #4 security(未授权凭证))+ 错误响应体统一格式 + 触发位置 + 错误类映射 + 每边界状态标注(`[EXISTING]` / `[NEW]` / `[FUTURE-IMPLEMENTATION]`)。

#### Scenario: 段标题存在
- **WHEN** 读 `docs/architecture.md`
- **THEN** 文档 MUST 含 `#### 4.3.Z 4 错误边界(eng-review Quality #3 锁定)` 标题

#### Scenario: 4 边界全列
- **WHEN** 读 §4.3.Z 段
- **THEN** 段内 MUST 出现 Boundary #1 / #2 / #3 / #4 全部 4 个边界描述

#### Scenario: 错误响应体统一格式
- **WHEN** 读 §4.3.Z 段
- **THEN** 段内 MUST 出现 `{error_class, error_message, request_id}` 错误响应体格式

#### Scenario: 触发位置明确
- **WHEN** 读 §4.3.Z 段
- **THEN** 段内 MUST 列每边界的触发位置(workflow 启动 / canvas save / 节点执行 / provider 响应 / auth 调用)

#### Scenario: 错误类映射引用既有
- **WHEN** 读 §4.3.Z 段
- **THEN** 段内 MUST 引用既有错误类:`SecurityError` / `UserError` / `WorkflowRuntimeError` / `Upstream5xx` / `UpstreamTimeout` / `UpstreamRateLimited` / `AuthFailed`

### Requirement: Boundary #1 canvas drag-loop MUST 走统一错误响应体

`services/workflow-engine/app/errors/classes.py` MUST 新增 `WorkflowCycleError` 类(独立类,不继承 `UserError`),触发 Boundary #1。`services/workflow-engine/app/errors/middleware.py` MUST 新增 `WorkflowCycleError` handler,返回 HTTP 422 + `{"error_class": "user", "error_message": "workflow contains cycle: [...]", "request_id": "..."}`。

#### Scenario: WorkflowCycleError 触发
- **WHEN** `services/workflow-engine/app/errors/cycle_detection.py::detect_cycle()` 返回非 None(检测到 cycle)
- **THEN** workflow 启动必须 raise `WorkflowCycleError` + `error_message` MUST 含 cycle edges 列表 + HTTP 422

#### Scenario: WorkflowCycleError 走统一 middleware
- **WHEN** 客户端调用 `POST /v1/workflows` 触发 Boundary #1
- **THEN** 响应体 MUST 是 `{error_class, error_message, request_id}` 格式 + HTTP 422

#### Scenario: 既有 3 边界 handler 不动
- **WHEN** 本 spec apply 完成后
- **THEN** 既有 `chatbiz_error_handler` 处理 `SecurityError` / `UserError` / `WorkflowRuntimeError` 的代码 MUST 完全不变

### Requirement: §4.3.Z MUST 引用 §4.3.5(企业安全)+ 既有错误类

§4.3.Z 段 MUST 引用 `§4.3.5 企业安全与权限`(Boundary #4 是子集)+ eng-review Quality #3 决策。**不**实现 `services/error_handling/` 统一 package(留 V1.0+)。

#### Scenario: 交叉引用 §4.3.5
- **WHEN** 读 §4.3.Z 段
- **THEN** 段内 MUST 出现 `§4.3.5` 引用,说明 Boundary #4 是 §4.3.5 的子集

#### Scenario: eng-review 决策引用
- **WHEN** 读 §4.3.Z 段
- **THEN** 段内 MUST 出现 `Quality #3` 引用

#### Scenario: 不实现 services/error_handling/
- **WHEN** 读 §4.3.Z 段
- **THEN** 段内 MUST 标注 `services/error_handling/` 统一 package 为 `[FUTURE-IMPLEMENTATION]`

[FUTURE-IMPLEMENTATION] 本 spec 处于 pre-build 增量阶段,`docs/architecture.md` §4.3.Z 段在 apply 阶段补全;`WorkflowCycleError` 类与 middleware handler 在 apply 阶段新增(总计 ~20 行代码 + 30 行测试);既有 4 边界错误类**不动**。

