# 4 Error Boundaries 实施计划(增量 spec)

> **For agentic workers:** Use superpowers:brainstorming-style planning.
> This is an incremental spec: ~20 lines of new code + 100-150 lines of
> documentation + 30 lines of tests. No service refactor, no migration.

**Goal:** 补 eng-review Quality #3 锁定的"4 错误边界 design doc section" + 让
Boundary #1(canvas drag-loop)走统一错误响应体。仓库 4 边界 80% 已实现,
本 spec **不抢实现**,只补设计文档 + 1 个新错误类。

**Architecture:** 既有 4 边界类(`SecurityError` / `UserError` / `WorkflowRuntimeError` /
`audit-and-isolation/errors.py` 7-class)**完全不动**;本 spec 只新增
`WorkflowCycleError` 类(独立类,Boundary #1)+ middleware handler +
`docs/architecture.md` §4.3.Z 段。

**Tech Stack:** 不引入新 stack。引用 §4.4 锁定的 Python 3.12 + FastAPI +
pytest + 100% 覆盖率。

---

## 总体执行顺序

| 阶段 | 任务组 | 阻塞关系 | 并行机会 |
|---|---|---|---|
| Phase A | 1.1 / 1.2 调研 | 无 | 可并行 |
| Phase B | 2.1 / 2.2 代码新增 | 依赖 Phase A | 串行(同一文件) |
| Phase C | 3.1 / 3.2 文档 | 依赖 Phase A(可与 B 并行) | 与 B 并行 |
| Phase D | 4.1 CLAUDE.md surface | 依赖 3.1 | 串行 |
| Phase E | 5.1 / 5.2 测试 + 收尾 | 依赖 Phase B + C | 串行 |

**关键路径:** 1.1 → 2.1 → 2.2 → 5.1 → 5.2
**最大并行窗口:** Phase C(文档)可与 Phase B(代码)并行

---

## 关键 commit 节点

| Commit # | Task | 触发条件 |
|---|---|---|
| C1 | 2.1 + 2.2 | WorkflowCycleError 类 + middleware handler |
| C2 | 3.1 + 3.2 | §4.3.Z 段 + 目录条目 |
| C3 | 4.1 | CLAUDE.md surface |
| C4 | 5.1 | test_workflow_cycle_error.py 通过 + 覆盖率 100% |
| C5 | 5.2 | verify.md + retrospective.md + archive |

---

## Task 2.1 WorkflowCycleError 类(样板)

**Files:**
- Modify: `services/workflow-engine/app/errors/classes.py`

**Steps:**

- [ ] **Step 2.1.1:** 在 `classes.py` 末尾(在 `WorkflowRuntimeError` 之后)新增 `WorkflowCycleError` 类
- [ ] **Step 2.1.2:** `class WorkflowCycleError(ChatBizError):` —— 独立类,不继承 `UserError`
- [ ] **Step 2.1.3:** `error_class = "user"`(沿用既有 4 边界的归类,避免引入第 5 类)
- [ ] **Step 2.1.4:** `def __init__(self, cycle_edges: list[tuple[str, str]]) -> None:`,把 cycle_edges 存到 `self.cycle_edges` + 构造 message `"workflow contains cycle: {cycle_edges}"`
- [ ] **Step 2.1.5:** 验证 `pytest services/workflow-engine/tests/test_errors.py` 仍通过(既有测试不破)

---

## Task 2.2 middleware handler(样板)

**Files:**
- Modify: `services/workflow-engine/app/errors/middleware.py`

**Steps:**

- [ ] **Step 2.2.1:** 在 `middleware.py` 末尾新增 `async def workflow_cycle_error_handler(request: Request, exc: WorkflowCycleError):`
- [ ] **Step 2.2.2:** 返回 `JSONResponse(status_code=422, content={"error_class": "user", "error_message": exc.message, "request_id": request_id})`
- [ ] **Step 2.2.3:** 验证既有 `chatbiz_error_handler` 函数体**完全不变**
- [ ] **Step 2.2.4:** 验证既有 3 handler 注册代码**完全不变**

---

## Task 3.1 §4.3.Z 段撰写(样板)

**Files:**
- Modify: `docs/architecture.md` §4.3 末尾,§4.4 标题前
- Modify: `docs/architecture.md` 顶层目录 §4.3 展开

**Steps:**

- [ ] **Step 3.1.1:** 找 §4.3 末尾位置(line 935 附近,即 §4.3.Y PII 规则集段后)
- [ ] **Step 3.1.2:** 在 `### 4.4 技术栈选型` 标题前,加 `#### 4.3.Z 4 错误边界(eng-review Quality #3 锁定)` 段
- [ ] **Step 3.1.3:** 写引子(eng-review Quality #3 锁定 + 4 边界概念)
- [ ] **Step 3.1.4:** 写 Boundary #1-4 详细段(每边界 ~20 行)
- [ ] **Step 3.1.5:** 写错误响应体统一格式段
- [ ] **Step 3.1.6:** 写 PII 处理段
- [ ] **Step 3.1.7:** 写交叉引用 + eng-review 决策引用 + 下游 spec 引用段
- [ ] **Step 3.1.8:** 在顶层目录 §4.3 展开加 `- [4.3.Z 4 错误边界(eng-review Quality #3 锁定)]` 条目
- [ ] **Step 3.1.9:** 验证文档总长度仍合理(Markdown 渲染 < 2000 行)

---

## Task 4.1 CLAUDE.md surface(样板)

**Files:**
- Modify: `CLAUDE.md`

**Steps:**

- [ ] **Step 4.1.1:** 找 `CLAUDE.md` 中 `## 已锁定的工程决策` 之前的位置
- [ ] **Step 4.1.2:** 加 1 行 `[FUTURE-IMPLEMENTATION] docs/architecture.md §4.3.Z 4 错误边界(eng-review Quality #3 锁定)即将在 four-error-boundaries apply 阶段补全,引用 §4.3.5 + 既有 4 边界错误类`
- [ ] **Step 4.1.3:** 验证 `CLAUDE.md` 总长度 < 320 行(现 ~315,留 5 行空间)

---

## Task 5.1 测试 + 收尾(样板)

**Files:**
- Create: `services/workflow-engine/tests/test_workflow_cycle_error.py`
- Create: `verify.md`
- Create: `retrospective.md`

**Steps:**

- [ ] **Step 5.1.1:** 写 test `test_workflow_cycle_error_raised_on_cycle()`:`detect_cycle()` 返回 cycle 时,workflow 启动必须 raise `WorkflowCycleError` + cycle_edges 存到 exception
- [ ] **Step 5.1.2:** 写 test `test_workflow_cycle_error_middleware_returns_422()`:模拟客户端 POST /v1/workflows 含 cycle,响应体 MUST 是 `{error_class, error_message, request_id}` 格式 + HTTP 422
- [ ] **Step 5.1.3:** 写 test `test_existing_3_boundary_handlers_unchanged()`:验证 `SecurityError` / `UserError` / `WorkflowRuntimeError` 既有 handler 行为完全不变
- [ ] **Step 5.1.4:** 跑 `pytest services/workflow-engine/tests/ --cov=services/workflow-engine/app/errors --cov-fail-under=100` 验证 100% 覆盖
- [ ] **Step 5.1.5:** 跑 `git diff` 看 `chatbiz_error_handler` 函数体是否完全无变化
- [ ] **Step 5.1.6:** 写 verify.md(3 requirement × 实现 + 4 commit 列表)
- [ ] **Step 5.1.7:** 写 retrospective.md(纯增量 spec 反思)
- [ ] **Step 5.1.8:** `openspec archive four-error-boundaries -y` 同步 spec delta

---

## 验证矩阵

| Task | 验证 |
|---|---|
| 2.1 WorkflowCycleError | test_workflow_cycle_error.py + pytest 100% |
| 2.2 middleware handler | test_workflow_cycle_error.py + grep 既有 handler 完整 |
| 3.1 §4.3.Z 段 | grep `#### 4.3.Z 4 错误边界` |
| 4.1 CLAUDE.md surface | grep `[FUTURE-IMPLEMENTATION] docs/architecture.md §4.3.Z` |
| 5.1 测试 + 收尾 | pytest 通过 + openspec archive 成功 |

---

## 风险与回退(对应 design.md Risks)

| 风险 | 触发条件 | 回退方案 |
|---|---|---|
| R1 cycle edges 含 PII | 实测发现 | 改为只含 node ID 列表不含 edge 关系 |
| R2 canvas save 端校验 | reviewer 要求 | 留 V1.0+,在 §4.3.Z 标注 |
| R3 错误类命名不一致 | reviewer 要求统一 | 在 §4.3.Z 段加 cross-reference 表 |
| R4 独立类 vs 继承 | reviewer 反驳 | 改为继承 `UserError`,仍走同一 middleware |

---

## 收尾判定标准

- [ ] 既有 4 边界错误类**完全不变**(`git diff services/audit-and-isolation/app/errors.py services/workflow-engine/app/errors/classes.py` 必须 0 行)
- [ ] 既有 3 boundary middleware handler **完全不变**
- [ ] 新增 1 个 `WorkflowCycleError` 类 + 1 个 middleware handler + 30 行测试
- [ ] `pytest services/workflow-engine/tests/ --cov --cov-fail-under=100` 通过
- [ ] `docs/architecture.md` §4.3.Z 段存在 + 含 4 边界
- [ ] `CLAUDE.md` surface 标记
- [ ] `openspec status --change four-error-boundaries` `isComplete: true`
- [ ] `verify.md` + `retrospective.md` 已写
- [ ] 5 个 commit 都在新 branch `feat/four-error-boundaries` 上
