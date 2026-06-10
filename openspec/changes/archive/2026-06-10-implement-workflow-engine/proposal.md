## Why

<!--
Explain the motivation for this change. What problem does this solve? Why now?

硬限制：50 ≤ 字元數 ≤ 1000（OpenSpec zod schema 會 validate）
建議結構：現況痛點 → 為什麼現在處理 → 預期收益（各 1-2 句）
-->

ChatBiz 当前 0 行源代码,前两个 change(`implement-credential-management` + `implement-audit-and-isolation`)已落地数据隔离网关 + 凭证管理两个基础设施 service。第三个 change 推进到**业务编排层**:workflow-engine 是后续 `implement-agent-runtime` (Lead/Sub Agent 委派) + `implement-canvas-ui` (可视化画布) 的共同依赖,延迟实现会阻塞所有业务能力。eng-review Test #2 锁定的 4 个 critical path 之一 — **paul 财务月报 end-to-end** — 的核心载体就是本 service(7-8 节点的 LangGraph StateGraph 编译 + 执行 + 人工审批中断续接 + LLM 经网关调)。MVP 必须在 month 2-3 落地以兑现 sponsor 承诺的 9-12 月完整版时间线。

## What Changes

<!--
Describe what will change. Be specific about new capabilities, modifications, or removals.
-->

### 节点范围
- **From**: 当前 spec placeholder 锁 5 节点(开始/结束/LLM/知识检索/条件分支)
- **To**: 14 节点全干(开始/结束 + LLM/知识检索/Agent/条件分支/循环/迭代/HTTP/代码执行/人工审批/子流程/参数提取/变量赋值)
- **Reason**: 用户在 Q2 brainstorm 选中 C(14 节点全干);跨 service 依赖(knowledge-base / agent-runtime)走 stub 策略
- **Impact**: 新增 9 节点的 Node Contract + execute() 实现

### 状态存储
- **From**: 占位 spec 提到 PG + Redis 双层(eng-review Quality #2)
- **To**: 本 change 仅 PG(5 张表);Redis canvas real-time + event sourcing 推迟到 `implement-canvas-ui`
- **Reason**: 无画布前端不产生 canvas edit 事件,Q5 选 A 锁定
- **Impact**: workflow_engine 域内数据全在 PG;画布重建时不会丢数据

### Workflow + Chatflow 双模式
- **From**: 占位 spec 提到 chatflow 模式
- **To**: 两个 dispatch 入口同时上;Chatflow = 在 StateGraph 末点加回 loop 边 + checkpoint thread_id = session_id
- **Reason**: eng-review Arch #4 锁定"单 StateGraph 双 dispatch";Q8 选 A 避免后续返工
- **Impact**: dispatch 层加 mode 参数分流,实现量 < 20%

### Node Contract codegen
- **From**: 占位 spec 写"1 份 TypedDict 驱动 4 份代码"
- **To**: Pydantic BaseModel 单一 source of truth,运行时 introspect 出 4 份产物(UI config schema / StateGraph 节点函数 / I/O schema / 验证函数)
- **Reason**: Q4 选 A(Pydantic-as-truth),0 build step,Python 与前端读同一份 JSON schema
- **Impact**: 12 节点 × 4 = 48 份代码(eng-review Quality #1)从 1 个 Pydantic 源生成;新增端点 `GET /api/nodes/:type/schema` 给前端消费

### 人工审批节点
- **From**: 占位 spec 提到"24h timeout escalation"
- **To**: 4 个设计点全上(eng-review Arch #6):(1) LangGraph Checkpointer → PostgreSQL 官方包 (2) 通知:复用 `audit-and-isolation/app/alerts.py` 发企微 webhook (3) reentry:`POST /approvals/:id:resume` 端点 (4) 24h timeout:apscheduler 启动时注册 cron,超时自动 cancel
- **Reason**: Q11 选 A,eng-review Arch #6 锁定
- **Impact**: 新增 3 个端点 + 后台 cron + 节点执行路径

### 错误处理 4 边界
- **From**: 占位 spec 提到"工作流执行错误处理"
- **To**: 4 边界全覆盖(eng-review Quality #3):(1) canvas drag-loop: NetworkX cycle detection (2) runtime: 1 次 indexed-backoff retry (3) user: config schema + 变量引用检查 (4) security: 凭证访问权检查
- **Reason**: Q12 选 A,后端是 source of truth 不能省
- **Impact**: 新增 `POST /workflows/:id/validate` 端点 + 4 边界各 2-3 单测

### LLM 节点 client 层
- **From**: 占位 spec 写"调用大语言模型"
- **To**: 经 `langchain_openai.ChatOpenAI(base_url="http://audit-and-isolation:8080/v1")` 转接
- **Reason**: Q6 选 B,复用 LangChain 生态,未来 Agent 节点共用 client
- **Impact**: 强依赖 `services/audit-and-isolation` 的 OpenAI-compatible 端点(已实现)

### 代码执行节点 sandbox
- **From**: 占位 spec 写"运行 Python/Node.js 代码"
- **To**: Docker sandbox 外部进程隔离(`--cpus=0.5` / `--memory=256m` / `--network=none` / 30s 超时)
- **Reason**: Q3 选 A,工业成熟;语言中立;强隔离
- **Impact**: service 需 docker socket 挂载;docker-compose 加配置

### paul 财务月报 e2e 测试
- **From**: 占位 spec 提到"paul 财务月报 e2e < 30s"
- **To**: 写完整 7-8 节点 workflow JSON fixture,全程走完 + audit log 验证 + checkpoint 恢复
- **Reason**: Q9 选 A;LLM eval 50 场景推迟到 `implement-llm-eval-suite`
- **Impact**: eng-review Test #2 100% 覆盖 path #1

## Capabilities

### New Capabilities
- `workflow-state-storage`: PostgreSQL 5 表 + LangGraph 官方 checkpointer 集成
- `node-contract-codegen`: 1 份 Pydantic BaseModel 驱动 4 份产物,运行时 introspect
- `workflow-state-machine`: Canvas JSON → LangGraph StateGraph 编译器,支持 14 节点类型
- `workflow-execution`: 同步/异步执行 + retry 策略 + node_event 轨迹
- `manual-approval-flow`: LangGraph Checkpointer 中断 + 企微通知 + reentry 端点 + 24h timeout cron

### Modified Capabilities
- `workflow-engine`: 8 个 Requirement 中的多个被更新:
  - "12 类节点类型" (MVP 5 → 14 全干)
  - "Workflow + Chatflow 双模式" (从占位描述到具体 LangGraph 实现)
  - "工作流状态持久化" (本 change 仅 PG,Redis 推迟)
  - "4 critical path 测试" (paul 月报 e2e 实现细节 + 数据隔离网关 / 插件加载降级留给对应 service)
  - "工作流执行" (新增 drag-loop 验证 + 4 错误边界)
  - "节点契约" (从 "TypedDict" 改为 Pydantic BaseModel)
  - "可视化画布" (本 change 仅后端;画布 UI 留给 implement-canvas-ui)
  - "工作流列表" (前端;本 change 不实现,留 canvas-ui)
  - 补"人工审批" Requirement(eng-review Arch #6 4 设计点)
  - 补"代码执行 sandbox" Requirement
  - 补"错误处理 4 边界" Requirement
  - 补"OpenAPI 3.1 接口" Requirement

## Impact

<!-- Affected code, APIs, dependencies, systems -->

**新增 service 目录**: `services/workflow-engine/` (~5000-7000 行 Python + ~3000-4000 行测试)

**新增 PG 数据库**: `chatbiz` 用户下 `workflow_engine` database(5 张表 + 索引)

**新增 docker-compose 服务**:
- `workflow-engine` (8001, 依赖 audit-and-isolation / credential / postgres / redis)
- `workflow-engine-migrate` (Alembic 一次性)
- `workflow-engine-sandbox` sidecar(可选;docker socket 转发,降低权限)

**新外部依赖**(Python):
- `langgraph>=0.2,<0.3` (核心)
- `langgraph-checkpoint-postgres>=2.0` (官方 checkpointer)
- `langchain-openai>=0.2` (LLM 节点 client)
- `pydantic>=2.8` (Node Contract)
- `networkx>=3.3` (DAG cycle detection)
- `apscheduler>=3.10` (24h timeout cron)
- `docker>=7.0` (Python SDK,sandbox 编排)
- `httpx>=0.27` (向 audit-and-isolation / credential / knowledge-base / agent-runtime HTTP 调)
- `fastapi>=0.115` + `uvicorn[standard]` + `sqlalchemy[asyncio]>=2.0` + `asyncpg` + `alembic` (同 audit-and-isolation)
- `pytest` + `pytest-asyncio` + `pytest-cov` + `httpx` + `fakeredis` + `respx` + `aiosqlite` + `testcontainers[postgres,redis]`

**新增 REST 端点** (13 个):
- `POST /workflows`
- `GET /workflows/:id`
- `GET /workflows/:id/versions`
- `GET /workflows/:id/versions/:v`
- `PUT /workflows/:id`
- `DELETE /workflows/:id`
- `POST /workflows/:id/validate`
- `POST /workflows/:id:run`
- `GET /runs/:run_id`
- `GET /runs/:run_id/events` (SSE)
- `GET /approvals/pending`
- `POST /approvals/:id:resume`
- `POST /approvals/:id:cancel`
- `GET /api/nodes/:type/schema` (Node Contract 暴露给前端)
- `GET /healthz` + `GET /readyz`

**被影响的下游 change**:
- `implement-canvas-ui`: 消费 `GET /api/nodes/:type/schema` 渲染 config 面板,消费 SSE `/runs/:run_id/events` 实时显示
- `implement-agent-runtime`: 复用 LangChain ChatOpenAI client 模式
- `implement-knowledge-base`: 知识检索节点 URL 切换为 `http://knowledge-base:8002/retrieve`

**[FUTURE-IMPLEMENTATION] 标记** (本 change 不实现,只为后续 change 留接口):
- Redis canvas real-time state + event sourcing (Q5 推迟)
- 画布 UI / 节点 UI / React Flow 集成 (Q1 推迟到 implement-canvas-ui)
- knowledge-base 节点的 HTTP 真实实现 (implement-knowledge-base 接管)
- agent-runtime 节点的 HTTP 真实实现 (implement-agent-runtime 接管)
- MCP 集成 / tool calling (implement-mcp-servers 接管)
- 50 个 paul 财务月报 LLM eval scenarios (implement-llm-eval-suite 接管)
