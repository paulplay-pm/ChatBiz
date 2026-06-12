<!--
Raw capture of superpowers:brainstorming output for change `four-error-boundaries`.
设计来源:eng-review 2026-06-10 锁定的 Quality #3(locked-in,不再重新讨论)。
eng-review 原始 finding(逐字引用):
> Quality #3 (P2, 6/10) — No error handling design.
> Resolution: 4 个边界明说. (1) canvas drag-loop prevention; (2) runtime errors
> (LLM 5xx / timeout / rate limit); (3) user errors (node param missing /
> undefined variable); (4) security errors (unauthorized credential access).
> Add Error handling section to design doc.
-->

# Brainstorm:4 错误边界统一契约(eng-review Quality #3)

## 背景(来自 eng-review 报告)

eng-review 2026-06-10 锁定的 12 个工程决策中,Quality #3 明确"4 错误边界
明说 + 加 Error handling section to design doc"。

仓库现状盘点(2026-06-12):
- **Boundary #1 canvas drag-loop**:`services/workflow-engine/app/errors/cycle_detection.py` 用 NetworkX `find_cycle()` 检测 DAG 循环,返回 cycle edges 列表(已实现,**不在 audit log**)
- **Boundary #2 runtime(LLM 5xx / timeout / 限额)**:双实现
  - `services/audit-and-isolation/app/errors.py::Upstream5xx/UpstreamTimeout/UpstreamRateLimited` + 7-class exception taxonomy
  - `services/workflow-engine/app/errors/classes.py::WorkflowRuntimeError`
- **Boundary #3 user(参数不全 / 未定义变量)**:
  - `services/workflow-engine/app/errors/classes.py::UserError`(HTTP 400)
- **Boundary #4 security(未授权凭证)**:
  - `services/audit-and-isolation/app/auth.py` 调 credential service,401
  - `services/workflow-engine/app/errors/classes.py::SecurityError`(HTTP 403)
- **统一 middleware**:`services/workflow-engine/app/errors/middleware.py` 把 3 边界(SecurityError/UserError/WorkflowRuntimeError)统一映射为 `{error_class, error_message, request_id}` JSON;`cycle_detection.py` 边界 #1 **未**进同一 middleware,只在 workflow 启动时校验
- **缺设计文档**:`docs/architecture.md` 没有 §4.X 错误处理专门段;eng-review 报告里 Quality #3 要求 "Add Error handling section to design doc"

## 决策链

### Q1:范围边界

- **选项 A** 补差:只补 §4.X 文档段 + 1 个统一契约 spec,**不**改既有实现
- B:把 2 个 service 的 errors/ 合并到 `services/error_handling/`
- C:重写错误处理统一

**选 A**(eng-review 锁定"加 design doc section",不是"重写")。本 spec 跟 T1 gateway spec 同模式:不抢实现,只做契约化 + 文档。

### Q2:统一契约 1 个 vs 4 个

- **选项 A** 1 个 capability `error-boundary-contract` 覆盖 4 边界
- B:4 个 capability 各自 spec(过细)

**选 A**。4 边界是 eng-review Quality #3 锁定的统一概念,1 个 capability 锁定 4 边界的契约。

### Q3:边界 #1(drag-loop)是否进统一契约

- eng-review 明确"canvas drag-loop prevention",所以是 4 边界之一
- 现状:只在 workflow 启动时校验,**未**进统一 middleware
- 选 A:**进**统一契约,要求所有 workflow 启动必须校验 cycle + 把 cycle 错误也走统一 `{error_class, error_message, request_id}` JSON

### Q4:与 §4.3.5(企业安全与权限)关系

- §4.3.5 涵盖 RBAC / 数据安全 / 审计 / 沙箱
- Boundary #4 security(未授权凭证)是 §4.3.5 的子集
- **本 spec 引用 §4.3.5,不重写**

### Q5:实施约束

- **不写代码**:边界 #1-4 已实现,本 spec 只补 §4.X 段 + 1 capability spec
- verify:grep 验证 §4.X 段存在 + 含 4 边界定义 + 引用既有错误类

## 4 边界详细设计(eng-review Quality #3 锁定)

### Boundary #1:canvas drag-loop
- **触发条件**:workflow JSON 含 A→B→A 循环
- **检测**:`services/workflow-engine/app/errors/cycle_detection.py::detect_cycle()`(NetworkX `find_cycle()`)
- **错误类**:`WorkflowCycleError`(**新** — 本 spec 要求新增,与现有 `UserError` 子类型)
- **HTTP 状态**:422 Unprocessable Entity
- **响应体**:`{"error_class": "user", "error_message": "workflow contains cycle: [...]", "request_id": "..."}`
- **触发位置**:workflow 启动时(POST /v1/workflows) + canvas save 时(PUT /v1/canvas/{id})
- **当前状态**:检测已实现,**未**统一进 `middleware.py` 错误响应体

### Boundary #2:runtime(LLM 5xx / timeout / 限额)
- **触发条件**:上游 LLM provider 返 5xx / timeout / 429
- **错误类**:
  - `services/audit-and-isolation/app/errors.py::Upstream5xx` → HTTP 502
  - `services/audit-and-isolation/app/errors.py::UpstreamTimeout` → HTTP 504
  - `services/audit-and-isolation/app/errors.py::UpstreamRateLimited` → HTTP 429
  - `services/workflow-engine/app/errors/classes.py::WorkflowRuntimeError` → HTTP 502
- **响应体**:`{"error_class": "runtime", "error_message": "...", "request_id": "..."}`
- **重试策略**:1 次 5xx 自动重试(已有);T6 perf contract 限流
- **当前状态**:✅ 完整实现

### Boundary #3:user(参数不全 / 未定义变量)
- **触发条件**:workflow 节点 config 缺 `approver_user_id` 等 / 引用未定义变量
- **错误类**:`services/workflow-engine/app/errors/classes.py::UserError` → HTTP 400
- **响应体**:`{"error_class": "user", "error_message": "...", "request_id": "..."}`
- **触发位置**:workflow_definition 启动阶段 + workflow 节点执行时(jinja 模板渲染)
- **当前状态**:✅ 完整实现

### Boundary #4:security(未授权凭证)
- **触发条件**:调用方 service token 缺失 / 失效 / 越权
- **错误类**:
  - `services/audit-and-isolation/app/auth.py::AuthFailed` → HTTP 401
  - `services/workflow-engine/app/errors/classes.py::SecurityError` → HTTP 403
- **响应体**:`{"error_class": "security", "error_message": "...", "request_id": "..."}`
- **PII 处理**:错误响应体**不**含凭证(eng-review 锁定"主密钥 / 凭证明文 MUST NOT 入 log / audit")
- **当前状态**:✅ 完整实现

## 设计取捨

| 取捨点 | 选 A | 选 B | 我们选 | 理由 |
|---|---|---|---|---|
| 错误类 base | `ChatBizError` 单基类 | 各自独立 | 单基类 | 现有已实现,沿用 |
| 错误响应体 | `{error_class, error_message, request_id}` | RFC 7807 Problem Details | 现有格式 | 沿用 |
| request_id 来源 | `X-Request-Id` header | 服务端生成 | 优先 header,缺失则生成 | 现有实现 |
| Boundary #1 错误类 | `UserError` 子类 | 独立 `WorkflowCycleError` | 独立类 | 语义清晰 |
| 跨 service 错误传递 | 各自 class | 共享基类 | 各自 class | 解耦 |

## 被拒方案

1. **合并 2 service 的 errors/** —— 改动过大,eng-review 锁定"加 design doc"
2. **统一 base class 在 services/error_handling/** —— 跨 service 共享需重构 import 链
3. **Boundary #1 不进统一契约** —— eng-review 明确"4 边界",必须含 drag-loop

## 触发 wedge 场景

- **paul 财务月报**:Boundary #3(user config 缺字段,如 `period`)→ 400 + 明确 error
- **leo 数据查询**:Boundary #4(无 service token)→ 401
- **anny 文档审核**:Boundary #2(LLM 5xx)→ 502 + 自动重试 1 次

## 跨 spec 依赖

| 后续 spec | 怎么依赖本 spec |
|---|---|
| T2 Node Contract | 每个 node 的执行错误映射到 4 边界 |
| T4 测试架构 | 4 边界 + 4 critical path 100% 覆盖 |
| T11 自己 | 本 spec 是 eng-review Quality #3 的 design doc 落地 |
| (新) WorkflowCycleError 实施 | 继承本 spec Boundary #1 段 |

## Open Questions(交给 apply 阶段)

- **OQ1:** `WorkflowCycleError` 是新增 class 还是 `UserError` 子类 —— 本 spec 决定:独立类
- **OQ2:** Boundary #1 错误响应体的 `error_message` 是否含 cycle edges 列表 —— 决定:含(便于 reviewer 定位)
- **OQ3:** 是否需 `services/error_handling/` 统一 package —— 本 spec 决定:**不**抢实现,留后续 spec
