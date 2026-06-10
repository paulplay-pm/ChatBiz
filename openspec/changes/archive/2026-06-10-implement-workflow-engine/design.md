## Context

ChatBiz 当前仓库内已完成 0 行源代码以外的所有产物:`docs/architecture.md`(技术架构,§4 是设计章节,4.3.1 是 workflow engine 章节)+ `docs/prd.md`(产品需求 v1.5,§4.1.1-4.1.5 是 workflow 详细需求)+ 12 个 eng-review finding(`~/.gstack/projects/paulplay-pm-ChatBiz/paulwang-main-design-20260609-230548.md` 的 ## GSTACK REVIEW REPORT)。

**当前 0 行代码,前面 2 个 change 已落地:**
- `implement-credential-management`: 凭证管理 service(port 8000)
- `implement-audit-and-isolation`: 数据隔离网关 service(port 8080,OpenAI-compatible /v1/chat/completions + PII 脱敏 + Metadata-Only 审计)

**本 change 推进到业务编排层。** workflow-engine 是 ChatBiz 的核心组件,后续 `implement-agent-runtime`(Lead/Sub Agent 委派,eng-review Arch #2)+ `implement-canvas-ui`(React Flow / X6 画布,eng-review Quality #1)+ `implement-knowledge-base`(知识检索节点真实实现)全部依赖它。

**eng-review 12 finding 中,本 change 涉及 8 个:**
| Finding | 在本 change 的体现 |
|---------|------------------|
| Arch #2 (Node Contract 共享) | 14 节点共享 Pydantic BaseModel |
| Arch #4 (Workflow + Chatflow 单 StateGraph) | 同一 `compile_state_graph()` + mode dispatch |
| Arch #6 (人工审批 4 设计点) | 完整端到端 + 24h timeout |
| Quality #1 (代码生成 4 产物) | Pydantic-as-truth |
| Quality #2 (PG + Redis 双层) | 本 change 仅 PG,Redis 推迟 |
| Quality #3 (4 错误边界) | drag-loop / runtime / user / security |
| Test #2 (paul 财务月报 critical path) | 1 完整 fixture + e2e |
| Perf #2 (5 存储量预估) | 5 张 PG 表 + 90 天保留策略 |

**eng-review 未覆盖、本 change 新增的决策点:** sandbox 方案(Node Contract Q3) / codegen 风格(Q4) / 双模式拆分(Q8) / 测试技术栈(Q14)。

**3 个具名用户:**
- **paul 财务月报**:MVP 必中。7-8 节点:开始 → HTTP 拉 ERP → 变量赋值 → 条件分支 → LLM 生成月报 → 人工审批 → 结束。
- **leo 数据查询**:V1.0。
- **anny 增值服务**:V1.5。

## Goals / Non-Goals

**Goals:**
1. 实现 workflow-engine 后端 service(port 8001),含 14 类节点 / 13 REST endpoint / 5 PG 表 / LangGraph StateGraph 编译执行
2. 落地 Node Contract(Pydantic BaseModel)统一驱动 4 份产物,eng-review Arch #2 + Quality #1 锁定
3. 实现人工审批节点 4 设计点:LangGraph Checkpointer + 企微通知 + reentry API + 24h timeout,eng-review Arch #6 锁定
4. 错误处理 4 边界全覆盖,eng-review Quality #3 锁定
5. paul 财务月报 end-to-end 1 完整 fixture 跑通,eng-review Test #2 path #1 锁定
6. 暴露 Node Contract schema API 给前端消费(`GET /api/nodes/:type/schema`),支撑下个 `implement-canvas-ui` change
7. 复用 audit-and-isolation 已实现的 OpenAI-compatible 网关 / 凭证权限 / 企微通知,零代码重写

**Non-Goals (本 change 不实现):**
1. 画布 UI(React Flow / X6) — `implement-canvas-ui` change
2. knowledge-base service 真实实现 — 知识检索节点走 stub HTTP(URL `http://knowledge-base:8002/retrieve`),`implement-knowledge-base` 接管
3. agent-runtime service 真实实现 — Agent 节点走 stub HTTP(URL `http://agent-runtime:8003/invoke`),`implement-agent-runtime` 接管
4. MCP server 集成 — `implement-mcp-servers` change
5. 50 个 paul 财务月报 LLM eval baseline — `implement-llm-eval-suite` change
6. Redis canvas 实时状态 + event sourcing — `implement-canvas-ui` change
7. 定时触发 / Webhook 触发 workflow — V1.0
8. 版本回滚 UI — V1.0
9. 14 节点 UI config 面板(前端消费 schema 渲染)— `implement-canvas-ui` change

## Decisions

### D1: scope — 仅后端,不含画布前端
- **选择**: 后端 service 单体;Node Contract 暴露 schema API 给未来前端消费
- **理由**: 前 2 个 service 都是后端单体,subagent-driven 模式跑通;画布前端跨技术栈(React + TS)会拖慢节奏;Node Contract codegen 是画布前置依赖,先稳定后端
- **已考虑 alternative**:
  - B. 后端 + 基础画布:跨 Python + TS 两种语言,subagent context 压力大
  - C. 完整包(14 节点 UI + 双模式 + 对话触发 + 定时 + Webhook + 版本管理):4-6 周,超出单 change 范围

### D2: 节点范围 — 14 节点全干
- **选择**: 14 类节点全干(开始/结束 + LLM/知识检索/Agent/条件分支/循环/迭代/HTTP/代码执行/人工审批/子流程/参数提取/变量赋值)
- **理由**: 用户在 Q2 brainstorm 选中 C;跨 service 依赖(knowledge-base / agent-runtime)走 stub 策略
- **已考虑 alternative**:
  - A. 5 节点(严格按 design doc line 150 锁定):用户拒绝
  - B. 5 节点 + HTTP + 代码执行 + 变量:被 C 取代

### D3: 代码执行节点 sandbox — Docker 外部进程隔离
- **选择**: Python Docker SDK 起 `python:3.12-slim` / `node:20-slim` container,`--cpus=0.5` + `--memory=256m` + `--network=none` + 30s 超时
- **理由**: 工业成熟(Dify / n8n 都用);语言中立(未来加 Go / Rust 节点免选型);强隔离;性能 cold start 500-1000ms 可接受
- **已考虑 alternative**:
  - B. 语言内嵌 sandbox(RestrictedPython):安全依赖库实现质量历史有 CVE;只支持 Python
  - C. wasm sandbox(Pyodide):paul 需要的 pandas / openpyxl 等 wheel 装不上
  - D. 取消代码节点:paul 月报需要透视表计算,不可省

### D4: Node Contract codegen — Pydantic-as-truth
- **选择**: 每类节点 1 个 Pydantic BaseModel + 4 份产物运行时 introspect(UI schema / StateGraph 节点 / I/O schema / 验证)
- **理由**: 单一 source;0 build step;Python 与前端读同一份 JSON schema
- **已考虑 alternative**:
  - B. Pydantic + codegen 脚本(预生成 × 4):生成代码需入库,review 看到双件
  - C. JSON Schema-as-truth(双向生成):手写 JSON schema 体验差,IDE 无提示

### D5: Quality #2 拆分 — 仅 PG,Redis 推迟
- **选择**: 本 change 仅 5 张 PG 表;Redis canvas 实时状态 + event sourcing 留给 `implement-canvas-ui`
- **理由**: 无画布前端不产生 canvas edit 事件;Q5 选 A 锁定
- **已考虑 alternative**:
  - B. PG + Redis stub 同时上:接口提前冻结但 ~3 天工作量未被真使用,违反 YAGNI

### D6: LLM 节点 client — LangChain ChatOpenAI 转接
- **选择**: `langchain_openai.ChatOpenAI(base_url="http://audit-and-isolation:8080/v1", api_key=service_token)`
- **理由**: 复用 LangChain 生态(streaming / retry / tool calling / multi-modal);未来 Agent 节点共用 client
- **已考虑 alternative**:
  - A. httpx 直调 audit-and-isolation:失去 LangChain 生态;未来 Agent 节点要重写

### D7: LangGraph Checkpointer — 官方 langgraph-checkpoint-postgres
- **选择**: 用 `langgraph-checkpoint-postgres` 官方包,自动建 checkpoints 表
- **理由**: 0 自研底层 bug,随升级同步 fix;我们 `workflow_run` 表(高层元数据)+ LangGraph checkpoints(节点级)通过 thread_id 关联
- **已考虑 alternative**:
  - B. 自实现 AsyncCheckpointSaver:200 行 + 每次 LangGraph 升级复检

### D8: Workflow + Chatflow 双模式同时上
- **选择**: 两个 dispatch 入口同时上;Chatflow = StateGraph 末点回 loop 边 + thread_id = session_id
- **理由**: eng-review Arch #4 锁定"单 StateGraph 双 dispatch";实现量 < 20%;一次落地避免下个 change 改 StateGraph 接口
- **已考虑 alternative**:
  - B. 仅 Workflow:下个 change 改 StateGraph 接口风险大

### D9: paul 财务月报 e2e — 1 完整 fixture
- **选择**: 写 1 个 paul 月报 workflow JSON fixture(7-8 节点),端到端测试全程走完
- **理由**: eng-review Test #2 path #1 锁定;LLM eval 50 场景推迟
- **已考虑 alternative**:
  - B. 主路径 + 5 错误路径:增加 ~1-2 小时,价值不高(单测已覆盖)
  - C. 同 B + LLM eval 50 场景:50 财务数据 fixture 准备成本高

### D10: 服务名 + 端口 — 复用 audit-and-isolation 风格
- **选择**: 服务名 `workflow-engine`,端口 `8001`,容器名 `chatbiz-workflow-engine`,依赖 `audit-and-isolation:8080` + `credential:8000` + postgres + redis
- **理由**: 跟前面 2 个 service 风格 100% 一致
- **已考虑 alternative**:
  - B. `/healthz` 报节点 inventory:画布未实现,无消费方;推迟

### D11: 人工审批后端 3 能力全上
- **选择**: 3 个能力:① 节点触发时写 checkpoint + 发企微 + paused 状态 ② REST API:GET /approvals/pending + POST /approvals/:id:resume + POST /approvals/:id:cancel ③ apscheduler 24h timeout cron
- **理由**: eng-review Arch #6 锁定 + Q11 选 A;前端审批 UI 留给 `implement-canvas-ui`
- **已考虑 alternative**:
  - B. 去掉 24h timeout:eng-review Arch #6 锁定

### D12: 错误处理 4 边界全覆盖
- **选择**: ① drag-loop:NetworkX cycle detection ② runtime:1 次 indexed-backoff retry ③ user:Pydantic config schema + 变量引用检查 ④ security:凭证访问权检查
- **理由**: 后端是 source of truth;eng-review Quality #3 锁定
- **已考虑 alternative**:
  - B. 3 边界(drag-loop 推迟):后端是 source of truth 不能省

### D13: MCP 集成 — 本 change 不含
- **选择**: 不含 MCP server 实现;LLM 节点 = 纯 prompt → completion;HTTP 节点可临时替代部分 MCP 功能
- **理由**: MCP 走 `implement-mcp-servers` + `implement-agent-runtime` 后续 change;Q13 选 A
- **已考虑 alternative**:
  - B. LLM 节点加 tool calling stub:接口设计可能不准,后续 change 要重写

### D14: 测试技术栈 — 同 audit-and-isolation + testcontainers 跑真 PG
- **选择**: pytest + pytest-asyncio + httpx ASGITransport + fakeredis + respx + aiosqlite + pytest-cov + testcontainers[postgres,redis]
- **理由**: LangGraph checkpointer 的 SQL 行为(JSONB / index / array)真 PG 才信得过;aiosqlite 仍用于纯单测
- **覆盖门槛**: 单元 ≥ 100% / 接口 100% / 安全全覆盖(同 audit-and-isolation)
- **已考虑 alternative**:
  - A. 不跑真 PG:LangGraph checkpointer SQL 行为与生产不一致,风险高

### D15: Workflow JSON + REST API + DB Schema
- **JSON 格式**: `{nodes: [{id, type, config, position}], edges: [{from, to, condition?}], variables: {...}}`(React Flow / X6 兼容)
- **13 个 REST endpoint**:
  | Method | Path | 用途 |
  |--------|------|------|
  | POST | /workflows | 创建 |
  | GET | /workflows/:id | 读 latest |
  | GET | /workflows/:id/versions | 列历史 |
  | GET | /workflows/:id/versions/:v | 读指定版本 |
  | PUT | /workflows/:id | 更新(生成新 version) |
  | DELETE | /workflows/:id | 软删除 |
  | POST | /workflows/:id/validate | DAG 循环检测 + config schema 验证 |
  | POST | /workflows/:id:run | 异步启动 |
  | GET | /runs/:run_id | 查询 run 状态 |
  | GET | /runs/:run_id/events | SSE 流式节点事件 |
  | GET | /approvals/pending?user=X | 查待审批 |
  | POST | /approvals/:id:resume | 接 reentry |
  | POST | /approvals/:id:cancel | 取消 |
  | GET | /api/nodes/:type/schema | 节点契约给前端 |
  | GET | /healthz, /readyz | 健康检查 |
- **5 张 PG 表**: `workflow_definition` / `workflow_run` / `node_event` / `approval` + LangGraph `checkpoints`
- **理由**: React Flow / X6 原生兼容;eng-review Q15 选 A
- **已考虑 alternative**:
  - B. 加 GraphQL(YAGNI)
  - B. 加 workflow_revision 表(event sourcing 推迟)

## Risks / Trade-offs

**[Risk] R1: LangGraph 0.2 → 0.3 API 变化** → Mitigation: 选 0.2 稳定线(`>=0.2,<0.3`),等 0.3 稳定再升级

**[Risk] R2: 知识检索 / Agent 节点 stub URL 在跨 service 集成时需调整** → Mitigation: 接口固化,URL 通过 env var 配置(`KNOWLEDGE_BASE_URL` / `AGENT_RUNTIME_URL`),default = 文档里写的 URL

**[Risk] R3: Docker sandbox 部署要求 docker socket 挂载** → Mitigation: docker-compose 加 `volumes: [/var/run/docker.sock:/var/run/docker.sock]` + `security_opt: [no-new-privileges:true]` + read-only mount;kaniko/podman 兼容;生产 K8s 换 sidecar 模式

**[Risk] R4: 14 节点同时实现,任何节点子集做错都要回炉** → Mitigation: Node Contract codegen 提供统一模板,降低每个节点实现成本;e2e 跑 paul 月报 7 节点全路径;eng-review Test #2 path #1 100% 覆盖

**[Risk] R5: Pydantic-as-truth 的前端 schema 消费需要 React 端包装层** → Mitigation: 前端用 `@rjsf/core` 直渲染 JSON schema;下个 canvas-ui change 决定具体方案

**[Risk] R6: testcontainers 需要 docker 环境,CI +3-5 分钟** → Mitigation: 单测可跑(不依赖 docker);集成测试在 CI 跑(无 docker 环境 skip);本地开发跑 testcontainers

**[Risk] R7: 24h timeout cron 在多实例部署时同时跑导致重复标 timeout** → Mitigation: 用 `SELECT ... FOR UPDATE SKIP LOCKED` 锁定待处理行;多实例只有 1 个会处理

**[Trade-off] T1: 14 节点全干超过 design doc MVP 锁定的 5 节点** → 接受理由:用户在 brainstorm 选 C;跨 service 依赖走 stub 策略不影响实现,跨 service 集成测试推迟

**[Trade-off] T2: Chatflow 与 Workflow 同时上,实现复杂度 +20%** → 接受理由:eng-review Arch #4 锁定 + 一次落地避免后续改 StateGraph 接口

**[Trade-off] T3: 不含画布 UI,前端集成留给下个 change** → 接受理由:Q1 锁定;Node Contract schema API 已暴露给下个 change 用

## Migration Plan

**部署顺序:**
1. `services/workflow-engine/` 目录 + Dockerfile + pyproject.toml(独立 service)
2. `infrastructure/docker-compose.yml` 加 `workflow-engine` + `workflow-engine-migrate` 服务
3. PostgreSQL `chatbiz` 用户下 `workflow_engine` database
4. Alembic migration:`alembic upgrade head`(4 张业务表)
5. LangGraph `AsyncPostgresSaver.setup()` 启动时自动建 `checkpoints` 表
6. 启动 service,`GET /readyz` 200 即可接入流量

**依赖关系:**
- 强依赖:`services/audit-and-isolation:8080`(LLM 网关)+ `services/credential:8000`(凭证)+ PostgreSQL + Redis
- 跨 service stub:knowledge-base:8002 / agent-runtime:8003(未实现,返 503,workflow 节点 fail-fast 并 audit log)

**rollback 策略:**
- `docker compose down workflow-engine workflow-engine-migrate`
- `alembic downgrade -1` × 4(逐表回滚,保留 checkpoints)
- 不删 audit log(独立存储)

**验收条件:**
- `verify.py` 全过(eng-review 17+ requirement + 18 gate)
- 单元 ≥ 100% / 接口 100% / 安全全覆盖
- 4 critical path 100% 覆盖:paul 月报 / 人工审批 / 网关 PII(stub mock)/ 插件加载降级
- `GET /readyz` 200
- paul 财务月报 e2e < 30s

**生产部署:**
- 3 replicas(eng-review 部署图 4.5)+ L4 LB
- LangGraph checkpointer 共享同一 PG 数据库
- `WORKFLOW_ENGINE_SERVICE_TOKEN` 用 credential service 签发(eng-review Q10 锁定)
- apscheduler 单实例跑(用 PG advisory lock 防重复)

## Open Questions

无。所有决策已锁定,未决项均推迟到后续 change:
- knowledge-base / agent-runtime / MCP server 实际实现:对应 change
- 50 paul 财务月报 LLM eval:`implement-llm-eval-suite`
- 画布 UI:`implement-canvas-ui`
- Redis canvas state + event sourcing:`implement-canvas-ui`
- 定时 / Webhook 触发:V1.0
- 版本回滚 UI:V1.0
