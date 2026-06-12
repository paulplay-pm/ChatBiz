# Design:4 错误边界统一契约(eng-review Quality #3)

## Context

eng-review 2026-06-10 锁定的 12 个工程决策中,Quality #3 明确"4 错误边界明说 + 加 Error handling section to design doc"。仓库现状盘点(2026-06-12):

| 边界 | 现有实现位置 | 状态 |
|---|---|---|
| #1 canvas drag-loop | `services/workflow-engine/app/errors/cycle_detection.py` | ✅ 检测已实现,**未**统一进 middleware |
| #2 runtime(LLM 5xx / timeout / 限额) | `audit-and-isolation/app/errors.py`(7-class)+ `workflow-engine/app/errors/classes.py::WorkflowRuntimeError` | ✅ 完整实现 |
| #3 user(参数不全 / 未定义变量) | `services/workflow-engine/app/errors/classes.py::UserError` | ✅ 完整实现 |
| #4 security(未授权凭证) | `audit-and-isolation/app/auth.py::AuthFailed` + `workflow-engine/app/errors/classes.py::SecurityError` | ✅ 完整实现 |

**4 边界 80% 已实现,缺统一契约 + 缺设计文档**。本 spec 走"补差"模式:不抢实现(eng-review 锁定"加 design doc"),只补 §4.3.Z 段 + 1 capability spec + 1 个新错误类(`WorkflowCycleError`)让 Boundary #1 走统一 middleware。

仓库 0 行新错误处理代码改动(只 +10 行 +10 行 +100-150 行文档 + 30 行测试)。

## Goals

- **G1:** §4.3.Z 段存在,内容覆盖 4 边界 + 错误响应体统一格式 + 触发位置 + 错误类映射
- **G2:** 1 个新错误类 `WorkflowCycleError` 让 Boundary #1 走统一 middleware
- **G3:** 1 个新 capability `error-boundary-contract` 锁定 4 边界契约
- **G4:** CLAUDE.md 同步 surface `[FUTURE-IMPLEMENTATION]`
- **G5:** 顶层目录条目加 §4.3.Z 链接

## Decisions

| ID | 决策 | 出处 |
|---|---|---|
| D1 | 4 边界 = canvas drag-loop / runtime / user / security | eng-review Quality #3 |
| D2 | 错误响应体 = `{error_class, error_message, request_id}` | 现有 `middleware.py` 沿用 |
| D3 | Boundary #1 走统一 middleware(本 spec 新增 `WorkflowCycleError` 类) | eng-review Quality #3 4 边界统一 |
| D4 | Boundary #1 错误类 `WorkflowCycleError` 是**独立类**(不继承 `UserError`) | 语义清晰 |
| D5 | Boundary #1 错误响应体的 `error_message` 含 cycle edges 列表 | 便于 reviewer 定位 |
| D6 | Boundary #1 HTTP 状态 = 422 Unprocessable Entity | 语义对齐:cycle 是 validation 失败 |
| D7 | 既有 `SecurityError` / `UserError` / `WorkflowRuntimeError` / 7-class audit-and-isolation 错误类**不动** | 不抢实现 |
| D8 | 既有 `chatbiz_error_handler` **完全不动**;`WorkflowCycleError(error_class="user")` 走既有 handler 自动获 HTTP 422 + 统一响应体(不需要新 handler) | 增量最小化 |
| D9 | §4.3.Z 段标注每边界状态(`[EXISTING]` / `[NEW]`)+ 引用既有错误类 | 跟 §4.3.Y / §4.3.X 风格一致 |

## 与 source of truth 的对应关系

- `services/workflow-engine/app/errors/classes.py` 既有 3 边界类 —— **本 spec 引用**,不改
- `services/audit-and-isolation/app/errors.py` 7-class 异常 —— **本 spec 引用**,不改
- `services/workflow-engine/app/errors/cycle_detection.py` Boundary #1 检测 —— **本 spec 引用**,不重写
- `services/workflow-engine/app/errors/middleware.py` 统一响应 —— **本 spec 引用 + 增量**(加 Boundary #1 handler)
- `docs/architecture.md` §4.3.5 企业安全与权限 —— **本 spec 引用**(Boundary #4 是子集)
- eng-review Quality #3 —— 本 spec 是它锁定的 design doc 落地

## Risks

- **R1:** Boundary #1 错误响应体含 cycle edges 列表,可能含 PII —— 缓解:cycle edges 是 `{"from": "n1", "to": "n2"}` node ID 引用,不涉 PII
- **R2:** Boundary #1 在 canvas save 端的校验留 V1.0+ —— 缓解:本 spec 在 §4.3.Z 段标注 `[FUTURE-IMPLEMENTATION]`
- **R3:** 既有 2 service 的错误类命名不一致(`Upstream5xx` vs `WorkflowRuntimeError`)—— 缓解:本 spec 不统一,只契约化 4 边界的 HTTP 状态 + 响应体格式
- **R4:** Boundary #1 独立类 vs 继承 `UserError` —— 决定 D4:独立类,语义清晰

## 跨 spec 依赖图

```
T11 (本 spec) ─┬─→ T2 Node Contract 每个 node 的执行错误映射到 4 边界
               ├─→ T4 测试架构 4 边界 + 4 critical path 100% 覆盖
               ├─→ (新) WorkflowCycleError 实施 spec 继承本 spec Boundary #1
               └─→ (新) services/error_handling/ 统一 package 留 V1.0+
```

## Migration

不适用。本 spec 是新增 + 增量,不动既有错误类与 middleware 既有 handler。

## Open Questions(交给 apply 阶段)

- **OQ1:** `WorkflowCycleError` 是否需要 `error_class = "user"` 或独立 `error_class = "cycle"` —— 决定:`error_class = "user"`(沿用既有 4 边界的归类,避免引入第 5 类)
- **OQ2:** `request_id` 缺失时是否在响应体里写明 `null` 还是 UUID —— 决定:UUID(现有 middleware 实现已用 `str(uuid.uuid4())`)
- **OQ3:** §4.3.Z 段是否加与 §4.3.5(企业安全)交叉引用 —— 决定:加(Boundary #4 是 §4.3.5 子集)
