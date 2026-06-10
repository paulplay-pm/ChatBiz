<!--
Raw capture of superpowers:brainstorming output for implement-workflow-engine.

本檔原樣捕捉 brainstorming skill 的產出，不強制結構。
Skill 的自然產出通常是 decision log 格式（背景 → 決議鏈 Q1-Qn → 設計取捨），
但依對話內容可能有不同組織方式。

design.md 從本檔萃取並重新整理為結構化設計文件。
不要將本檔的內容複製到 design.md — design.md 是獨立的重組產物，
兩者互補但不重疊。
-->

# brainstorm: implement-workflow-engine

## 背景

ChatBiz 第三个 OpenSpec change。前面已完成:
- `implement-credential-management`(凭证 + 审计 webhook)
- `implement-audit-and-isolation`(数据隔离网关 + PII 脱敏 + OpenAI-compatible /v1/chat/completions 代理)

下一步进入**业务编排层**。workflow-engine 是 ChatBiz 最核心的业务组件,后续 `implement-agent-runtime`(Lead/Sub Agent) / `implement-chatflow-ui` 全部依赖它。

**eng-review 已锁定的 12 个 finding 中,本 change 涉及 8 个:** Arch #2(Node Contract codegen)/ Arch #4(Workflow+Chatflow 单 StateGraph)/ Arch #6(人工审批持久化)/ Quality #1(代码生成 Node Contract)/ Quality #2(双层状态)/ Quality #3(4 错误边界)/ Test #2(paul 财务月报 critical path)/ Perf #2(存储量预估)。

**Eng-review 未覆盖、本 change 新增的决策点:** sandbox 方案 / Node Contract codegen 风格 / checkpointer 选型 / 双模式拆分 / 测试深度 / 服务名 / MCP 拆分 / 测试技术栈 / API 设计 / DB schema。

**3 个具名用户的 wedge 需求:**
- **paul 财务月报**:MVP 必中。end-to-end 7-8 节点:开始 → HTTP 拉 ERP → 变量赋值 → 条件分支 → LLM 生成月报 → 人工审批 → 结束。eng-review Test #2 锁定 100% 覆盖。
- **leo 数据查询**:V1.0,本 change 留 stub。
- **anny 增值服务**:V1.5,本 change 不触。

## 决策链(Q&A 记录)

### Q1: scope 层面

**A. 仅后端**(选中)。理由:
- 前一个 change 的服务都是后端单体,subagent-driven 模式跑通;画布前端是 React + TS,跨技术栈会拖慢节奏
- Node Contract codegen 是画布的"前置依赖";先稳定后端 + 暴露 schema API,前端 change 只需消费 JSON schema
- 客户已用 prototype.html (docs/prototype.html) 定义 UI 形态,前端 = 实施细节,后端 = 业务骨架,先有骨架
- 画布 UI 单独立 `implement-canvas-ui` change(届时 Node Contract 即可被前端用 JSON schema 渲染 config 面板)

**被拒方案:**
- B. 后端 + 基础画布:跨 Python + TS 两种语言,subagent context 压力大
- C. 完整包(14 节点 UI + 双模式 + 对话触发 + 定时 + Webhook + 版本管理):4-6 周,超出单 change 范围

### Q2: 节点范围

**C. 14 节点全干**(选中)。用户选,与 design doc 锁定基本一致(略有超出 — design doc 写的是 5 节点 MVP)。

**跨 service 依赖的 stub 策略(锁定):**
| 节点 | 真实依赖 | 本 change 落 stub 方式 |
|------|----------|----------------------|
| 知识检索 | knowledge-base service(未实现) | HTTP 调 `http://knowledge-base:8002/retrieve`(暂未实现),mock server 返回 fixture;knowledge-base change 落地后改 URL 即可 |
| Agent | agent-runtime service(未实现) | 节点结构 + 接口齐全,execute() 走 stub 调 `http://agent-runtime:8003/invoke`,integration test 用 mock |
| 人工审批 | 通知服务(企微/邮件) | 复用 audit-and-isolation 的 `alerts.py` 发企微 webhook(env var `WECOM_WEBHOOK_URL` 控制) |
| 人工审批 | reentry UI | 后端提供 11 个 REST endpoint 中的 `GET /approvals/pending` + `POST /approvals/:id:resume` + `POST /approvals/:id:cancel`;前端审批 UI 留给 implement-canvas-ui |
| 代码执行 | sandbox(Docker) | 选定方案(见 Q3) |

**被拒方案:**
- A. 5 节点(严格按 design doc 锁定):用户拒绝
- B. 5 节点 + HTTP + 代码执行 + 变量:被 C 取代

### Q3: 代码执行节点的 sandbox 方案

**A. Docker sandbox(外部进程隔离)**(选中)。理由:
- 工业成熟(Dify / n8n 都用 Docker 跑用户代码)
- 语言中立(Python / Node 同机制,未来加 Go / Rust 节点免选型)
- 强隔离:docker 原生 `--cpus` / `--memory` / `--network=none` 资源限制
- 部署方案:本服务挂载 `/var/run/docker.sock`(UNIX socket,容器内)或 Docker-in-Docker;后期换 kaniko / podman 兼容
- 性能:每次 cold start 500-1000ms,可接受 — 财务月报跑一次十几分钟,sandbox 启动占比 < 1%

**细节待 design 阶段:**
- 镜像选型(`python:3.12-slim` + `node:20-slim`)
- 资源 limit default(`--cpus=0.5` + `--memory=256m` + `--network=none` + 超时 30s)
- 通信:从 `workflow-engine` 写代码到 stdin,读 stdout(规避 mount 复杂性)
- 网络禁止(`--network=none`),允许代码通过白名单 `mcp-fetch` 调用外网(独立 MCP server,见 Q13)

**被拒方案:**
- B. 语言内嵌 sandbox(RestrictedPython):安全依赖库实现质量历史有 CVE;只支持 Python;不能限制 CPU
- C. wasm sandbox(Pyodide):冷启动 200ms 但 Paul 需要的 pandas / openpyxl 等 wheel 装不上,生态未成熟
- D. 取消代码节点:paul 月报需要透视表计算,不可省

### Q4: Node Contract codegen 实现风格

**A. Pydantic-as-truth(运行时 introspect)**(选中)。理由:
- 单一 source of truth:每个节点 = 1 个 Pydantic BaseModel(metadata + I/O + config schema)
- 4 个产物**运行时生成**:
  1. Canvas UI 配置面板 → 前端 GET `/api/nodes/:type/schema` 拿 JSON schema,React 端用 `@rjsf/core` 渲染
  2. StateGraph 节点函数 → `BaseModel.model_json_schema()` 校验 input
  3. I/O JSON schema → 同上
  4. 验证函数 → Pydantic 自身 `model_validate()`
- 0 build step,Python 与前端读同一份 JSON schema
- 缺点:前端拿的是 Pydantic 生成的 JSON schema,需要 React Flow / X6 包装一层 schema-driven form(下个 change 决定)

**被拒方案:**
- B. Pydantic + codegen 脚本(预生成 × 4):生成代码需入库,review 看到双件;多一个 make target
- C. JSON Schema-as-truth(双向生成):手写 JSON schema 体验差,IDE 没提示;双重生成加两个外部依赖

### Q5: Quality #2 锁定的 "PG + Redis 双层" 本 change 怎么拆

**A. 仅 PG,Redis 推迟到 canvas-ui**(选中)。理由:
- 本 change 无画布前端,无"canvas 实时事件"产生 → Redis Streams 没数据可写
- workflow_definition / workflow_run / checkpoints / approval 都是**业务执行数据** → PG 单层足够
- Q1 已决定画布 UI 独立 change,届时一起做 Redis canvas state + event sourcing
- 现在不动 Redis 也避免了"写完不被用" — YAGNI

**被拒方案:**
- B. PG + Redis stub 同时上:接口提前冻结但 ~3 天工作量未被真使用,违反 YAGNI

### Q6: LLM 节点调网关的 client 层

**B. 经 LangChain ChatOpenAI 转接**(选中)。理由:
- `langchain_openai.ChatOpenAI(base_url="http://audit-and-isolation:8080/v1", api_key=service_token)`
- 复用 LangChain 生态:streaming / retry / tool calling / multi-modal 全部开箱即用
- 未来 Agent 节点(`implement-agent-runtime`)同一套 LLM client,**0 重复代码**
- 错误诊断:多一层栈但 LangChain 错误信息相对友好
- 服务间认证:跟 audit-and-isolation 已有的 X-Service-Token 一致

**被拒方案:**
- A. httpx 直调 audit-and-isolation:性能优 1 个抽象层,但失去 LangChain 生态;未来 Agent 节点要再写一遍

### Q7: LangGraph Checkpointer 选型

**A. 官方 langgraph-checkpoint-postgres**(选中)。理由:
- 0 自研底层 bug,随 LangGraph 升级自动同步 fix
- 表 schema 由 LangGraph 定义,我们不能随意加 metadata 列 — 但我们的 `workflow_run.status` + `node_event` 表已经能补 metadata 需求
- 两套 schema(thread_id 关联):`workflow_run` (我们的高层元数据) + `langgraph_checkpoints` (节点级状态序列)
- 自实现 200 行代码不值得,LangGraph 升级兼容性成本高

**被拒方案:**
- B. 自实现 AsyncCheckpointSaver:实现量 200 行 + 每次 LangGraph 升级复检

### Q8: Workflow + Chatflow 双模式(eng-review Arch #4)

**A. Workflow + Chatflow 同时上**(选中)。理由:
- eng-review Arch #4 锁定"两份都上,共用 StateGraph"
- Chatflow = 在 StateGraph 末点加一条回 loop 的边 + checkpoint thread_id = session_id
- 实现量增加 < 20%(一个 dispatch 路由 + 一个循环边),不复杂
- 一次落地避免下个 change 改 StateGraph 接口

**被拒方案:**
- B. 仅 Workflow:范围窄但下个 change 改 StateGraph 接口风险大

### Q9: paul 财务月报 e2e 测试深度

**A. paul workflow JSON fixture + 1 个完整路径 e2e**(选中)。理由:
- 主路径:开始 → HTTP 拉 ERP → 变量赋值 → 条件分支 → LLM 生成月报 → 人工审批 → 结束(7-8 节点)
- mock ERP HTTP(`respx`)+ mock audit-and-isolation(返回固定 LLM 响应)+ 全程 8 节点走完 + 验证 audit log + checkpoint 可恢复
- 30-50 分钟可写
- 4 错误边界各套 2-3 个单测,已覆盖 eng-review Quality #3
- LLM eval baseline 50 场景推迟到 `implement-llm-eval-suite` change

**被拒方案:**
- B. paul 主路径 + 5 错误路径:增加 ~1-2 小时,价值不高(单测已覆盖)
- C. 同 B + LLM eval 50 场景:50 财务数据 fixture 准备成本高,推迟

### Q10: 服务名 + 端口 + 部署 + service token

**A. 复用 audit-and-isolation 同一套**(选中)。细节:
- 服务名: `workflow-engine`
- 端口: `8001`
- 容器名: `chatbiz-workflow-engine`
- 依赖: `audit-and-isolation:8080`(网关)+ `credential:8000`(凭证)+ `postgres` + `redis`
- Alembic migration 服务: `workflow-engine-migrate`
- Service token: `X-Service-Token` 头 + `WORKFLOW_ENGINE_SERVICE_TOKEN` env var
- `/healthz` 仅返回 200(节点 inventory 是 B 选项,YAGNI)

**被拒方案:**
- B. `/healthz` 报节点 inventory:画布未实现,无消费方;等 implement-canvas-ui 时再加

### Q11: 人工审批节点后端能力

**A. 后端 × 3 能力**(选中)。细节:
1. 节点执行到人工审批 → 写 PG checkpoint(官方 langgraph-checkpoint-postgres)+ 发企微 webhook(复用 `audit-and-isolation/app/alerts.py`,env var `WECOM_WEBHOOK_URL`)
2. REST API:
   - `GET /approvals/pending?user=X` — 查待审批
   - `POST /approvals/:id:resume` — 接收 reentry payload
   - `POST /approvals/:id:cancel` — 取消
3. 后台任务 24h timeout 检查:用 `apscheduler` 启动时注册 cron job,每 5 分钟扫 approval 表,超时 `status=timeout` + workflow_run 标 failed + audit log 记录

**被拒方案:**
- B. 去掉 24h timeout(推迟):eng-review Arch #6 锁定 + 风险大(无超时则人工审批会无限期暂停)

### Q12: 错误处理 4 边界

**A. 4 边界全覆盖**(选中)。细节:
1. **Canvas drag-loop**: `POST /workflows/validate` 用 NetworkX `find_cycle()` 检测,返回 422 + 中文提示"工作流存在循环,请使用条件分支或循环节点而非物理循环"
2. **Runtime**: LLM 调用 1 次 indexed-backoff retry(同 audit-and-isolation 逻辑:1s → 2s → fail),最终失败 mark `node_event.status=failed` + `workflow_run.status=failed`,audit log 记 `error_class=runtime`
3. **User**: 节点 config Pydantic schema 验证 + 变量引用存在性检查(在 workflow_definition 启动时遍历所有 `{{var}}` 占位符,缺失返 422 + `error_class=user`)
4. **Security**: workflow_run 启动时调 `credential:8000/v1/credentials/:id/access` 查创建者对凭证的访问权限,未授权返 403 + `error_class=security` + audit log

4 边界各 2-3 个单测。

**被拒方案:**
- B. 3 边界(canvas drag-loop 推迟):后端就是 source of truth,即使前端有 validation 后端必须再校验一次

### Q13: MCP 集成

**A. 本 change 不含 MCP**(选中)。理由:
- 走 `implement-mcp-servers` + `implement-agent-runtime` 2 个后续 change
- Agent 节点才是 MCP tool calling 的逆质场景
- 本 change 的 LLM 节点 = 纯 prompt → completion
- HTTP 节点可临时替代部分 MCP 功能

**被拒方案:**
- B. LLM 节点加 tool calling stub:接口设计可能不准,后续 change 要重写

### Q14: 测试技术栈

**B. 同 audit-and-isolation + testcontainers 跑真 PG**(选中)。理由:
- LangGraph + langgraph-checkpoint-postgres 的 SQL 行为(JSONB / index / array)在真 PG 上才信得过
- aiosqlite 仍可用于纯单测(纯逻辑模块)
- testcontainers 起真 Postgres + Redis(异步 fixture,scope=session)用于集成测试
- CI +3-5 分钟,可接受

**细节:**
- pytest + pytest-asyncio + httpx ASGITransport + fakeredis(单测)+ respx + aiosqlite + pytest-cov + testcontainers[postgres] + testcontainers[redis]
- 覆盖率门槛: 单元 ≥ 100% / 接口 100% / 安全全覆盖(同 audit-and-isolation)

**被拒方案:**
- A. 不跑真 PG:LangGraph checkpointer 的 SQL 行为会与生产不一致,风险高

### Q15: API + DB schema

**A. React Flow 兼容 JSON + 11 个 REST endpoint + 5 张 PG 表**(选中)。

**Workflow JSON 格式**(与 React Flow / X6 兼容):
```json
{
  "nodes": [
    {"id": "n1", "type": "start", "config": {...}, "position": {"x": 0, "y": 0}},
    {"id": "n2", "type": "llm", "config": {"model": "gpt-4", "prompt": "..."}, "position": {...}}
  ],
  "edges": [
    {"from": "n1", "to": "n2"},
    {"from": "n2", "to": "n3", "condition": "{{n2.output.revenue}} > 1000000"}
  ],
  "variables": {"month": "2026-05"}
}
```

**11 个 REST endpoint:**
| Method | Path | 用途 |
|--------|------|------|
| POST | /workflows | 创建 workflow(自动 v1) |
| GET | /workflows/:id | 读 latest version |
| GET | /workflows/:id/versions | 列历史版本 |
| GET | /workflows/:id/versions/:v | 读指定版本 |
| PUT | /workflows/:id | 更新(生成新 version) |
| DELETE | /workflows/:id | 软删除(archived=true) |
| POST | /workflows/:id/validate | DAG 循环检测 + config schema 验证 |
| POST | /workflows/:id:run | 异步启动一次执行 |
| GET | /runs/:run_id | 查询 run 状态 |
| GET | /runs/:run_id/events | SSE 流式节点事件 |
| GET | /approvals/pending?user=X | 查待审批 |
| POST | /approvals/:id:resume | 接收 reentry |
| POST | /approvals/:id:cancel | 取消审批 |

(实际 13 个,列举包含 SSE — 接受这个偏差)

**5 张 PG 表:**
| Table | 关键字段 | 用途 |
|-------|---------|------|
| workflow_definition | id, version, name, created_by, definition_json(JSONB), created_at, archived | workflow 持久化 |
| workflow_run | run_id(主键), workflow_id, workflow_version, thread_id(→ LangGraph checkpoints), mode('workflow'/'chatflow'), status, started_by, started_at, ended_at, error_class, error_message | 执行实例 |
| node_event | id, run_id(外键), node_id, status, input_json, output_json, started_at, ended_at, retry_count | 节点级执行轨迹(eng-review Test #2 需要) |
| approval | id, run_id(外键), node_id, approver_user_id, status(pending/approved/rejected/timeout/cancelled), created_at, responded_at, response_payload(JSONB) | 人工审批队列 |
| langgraph_checkpoints | (官方 schema) | LangGraph 内部状态 |

索引:
- `node_event (run_id, started_at)` — 节点时间线查询
- `approval (approver_user_id, status, created_at)` — 查待审批
- `workflow_run (workflow_id, started_at)` — workflow 历史
- `workflow_run (thread_id)` — chatflow 关联

**被拒方案:**
- B. 加 GraphQL(YAGNI,风格不一致)
- B. 加 workflow_revision 表(event sourcing 推迟)

## Open Questions

无。所有决策已锁定,未决项均推迟到后续 change(知识检索/Agent/MCP 节点为 stub,LLM eval 50 场景为独立 change,画布 UI 为 implement-canvas-ui)。

## 边界与依赖

**上游依赖**(已实现):
- `services/credential`(凭证 + audit webhook 通知)
- `services/audit-and-isolation`(LLM 网关 /v1/chat/completions)

**下游消费者**(本 change 提供接口):
- 暂无可视化前端(Q1 推迟)
- 未来 `implement-canvas-ui`:消费 `GET /api/nodes/:type/schema` + `GET /workflows/:id` + `POST /workflows/:id:run` + SSE `/runs/:run_id/events`

**平行 change**(本 change 不阻塞):
- `implement-knowledge-base` — 知识检索节点通过 stub URL 调,knowledge-base 落地后改 URL
- `implement-agent-runtime` — Agent 节点同上

## 估算

- Python 代码: ~5000-7000 行
- 测试代码: ~3000-4000 行
- Spec / docs: ~1500 行
- 总: ~10000-12500 行
- 实施时间(subagent-driven 3 阶段并发):~8-12 小时
- 验证时间: ~1-2 小时

## 风险

- R1. LangGraph 0.2 升级到 0.3 API 变化风险:低,选 0.2 稳定线
- R2. 知识检索 / Agent 节点的 stub URL 在跨 service 集成时需调整 URL:低,接口固化即可
- R3. Docker sandbox 部署要求 docker socket 挂载:中,需在 docker-compose.yml 标注 `volumes: [/var/run/docker.sock:/var/run/docker.sock]` + `security_opt: [no-new-privileges:true]`
- R4. 14 节点同时实现,任何节点子集做错都要回炉:中,Node Contract codegen 提供统一模板,降低每个节点实现成本
- R5. Pydantic-as-truth 的前端 schema 消费需要 React 端包装层:低,下个 change 决定
