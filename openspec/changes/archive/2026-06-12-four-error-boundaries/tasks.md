# Tasks: four-error-boundaries

## 1. 文档调研与素材准备(30min,2 个 task)

- [ ] 1.1 读 `services/workflow-engine/app/errors/classes.py` + `cycle_detection.py` + `middleware.py` 全部内容,确认 4 边界既有实现的 class name / HTTP 状态 / 触发位置
- [ ] 1.2 读 `services/audit-and-isolation/app/errors.py` 7-class 异常 + `auth.py` AuthFailed,确认 Boundary #2 + #4 既有错误类

## 2. WorkflowCycleError 类 + middleware handler 新增(1h,2 个 task)

- [ ] 2.1 在 `services/workflow-engine/app/errors/classes.py` 新增 `WorkflowCycleError` 类(独立类,不继承 `UserError`),`error_class = "user"`,构造函数接受 `cycle_edges: list[tuple[str, str]]` 参数
- [ ] 2.2 在 `services/workflow-engine/app/errors/middleware.py` 新增 `workflow_cycle_error_handler`,返回 HTTP 422 + `{"error_class": "user", "error_message": "workflow contains cycle: [...]", "request_id": "..."}`

## 3. §4.3.Z 段撰写(1h,1 个 task)

- [ ] 3.1 写 `docs/architecture.md` §4.3.Z 段(目标 100-150 行),内容结构:
  - **引子**:eng-review Quality #3 锁定;4 边界是 §4.3 设计补充
  - **4 边界详细**:
    - Boundary #1 canvas drag-loop:`[NEW]` 状态(本 spec 新增),触发条件(workflow JSON 含 A→B→A)/ 检测(`cycle_detection.py`)/ 错误类(`WorkflowCycleError`)/ HTTP 422 / 响应体 / 触发位置(workflow 启动 + canvas save 留 V1.0+)
    - Boundary #2 runtime:`[EXISTING]` 状态,引用 `audit-and-isolation/app/errors.py` 7-class + `workflow-engine` WorkflowRuntimeError
    - Boundary #3 user:`[EXISTING]` 状态,引用 UserError
    - Boundary #4 security:`[EXISTING]` 状态,引用 `audit-and-isolation/auth.py` AuthFailed + `workflow-engine` SecurityError
  - **错误响应体统一格式**:`{error_class, error_message, request_id}`
  - **PII 处理**:错误响应体 MUST NOT 含凭证(eng-review 锁定)
  - **交叉引用**:§4.3.5 企业安全(Boundary #4 子集)+ eng-review Quality #3
  - **下游 spec 引用**:T2 Node Contract / T4 测试架构 / (新) WorkflowCycleError 实施 / (新) services/error_handling/ 留 V1.0+
- [ ] 3.2 在 `docs/architecture.md` 顶层目录 §4.3 展开加 `- [4.3.Z 4 错误边界(eng-review Quality #3 锁定)]` 条目

## 4. CLAUDE.md surface 同步(15min,1 个 task)

- [ ] 4.1 在 `CLAUDE.md` `## 已锁定的工程决策` 段之前,加 1 行 `[FUTURE-IMPLEMENTATION] docs/architecture.md §4.3.Z 4 错误边界(eng-review Quality #3 锁定)即将在 four-error-boundaries apply 阶段补全,引用 §4.3.5 + 既有 4 边界错误类`

## 5. verify + 收尾(30min,2 个 task)

- [ ] 5.1 跑 `pytest services/workflow-engine/tests/`,**新增** `tests/test_workflow_cycle_error.py`(~30 行)验证 Boundary #1 走统一响应体,既有覆盖率 ≥ 100% 不破
- [ ] 5.2 写 `verify.md` + `retrospective.md` + `openspec archive` 同步 spec delta

---

**总计 8 个 task**:2 调研 + 2 代码 + 1 文档 + 1 CLAUDE.md + 1 测试 + 1 收尾。每个 task ≤ 1h,无超大 task。

**配对验证**:
- task 2.1 ↔ task 5.1(test 验证)
- task 2.2 ↔ task 5.1(同一 test 验证)
- task 3.1 ↔ task 5.1(verify grep 验证)
- task 4.1 ↔ task 5.1(grep 验证)

无孤儿。任务粒度全部 ≤ 1h(总预估 ~3.5h)。
