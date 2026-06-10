# workflow-engine Specification (Delta)

本 change 修改 workflow-engine capability 的多个 Requirement,新增 5 个 Requirement(对应 brainstorm Q11 人工审批 4 设计点 / Q3 代码 sandbox / Q12 错误处理 / Q15 OpenAPI / 调整后的 4 critical path 协调)。

## MODIFIED Requirements

### Requirement: 12 类节点类型
系统 MUST 实现 12 类业务节点 + 2 个控制节点(开始 / 结束) = 共 14 类节点:开始 / 结束 / LLM / 知识检索 / Agent / 条件分支 / 循环 / 迭代 / HTTP 请求 / 代码执行 / 人工审批 / 子流程 / 参数提取 / 变量赋值。所有 14 类节点 MUST 在本 change 落地;跨 service 依赖(知识检索 / Agent)走 stub 策略,接口固化、integration test 用 mock,真实接通在对应 service change 里完成。

#### Scenario: 14 节点全部可用
- **WHEN** 实现方完成本 change
- **THEN** 系统 MUST 列出 14 类节点且每类的 Node Contract + execute() 完整实现;画布前端 change (`implement-canvas-ui`) 可通过 `GET /api/nodes/:type/schema` 拿到所有 14 类的 config schema

#### Scenario: 知识检索节点 stub
- **WHEN** workflow 含知识检索节点 + knowledge-base service 尚未实现
- **THEN** 节点 MUST 走 stub HTTP 调 `http://knowledge-base:8002/retrieve`(未实现返 503),单元测试用 `respx` mock 返回 fixture;knowledge-base change 落地后 URL 不变,实现接管

#### Scenario: Agent 节点 stub
- **WHEN** workflow 含 Agent 节点 + agent-runtime service 尚未实现
- **THEN** 节点 MUST 走 stub HTTP 调 `http://agent-runtime:8003/invoke`(未实现返 503),单元测试用 mock;agent-runtime change 落地后接管

### Requirement: 节点契约 (Node Contract)
系统 MUST 用 1 份 Pydantic BaseModel 驱动每类节点的 4 份产物(画布 UI config schema / StateGraph 节点函数 / I/O schema / 验证函数),运行时 introspect 生成,不允许每节点独立写 4 份。eng-review Arch #2 + Quality #1 锁定。12 × 4 = 48 份组件从 1 个源生成。

#### Scenario: 节点定义一致性
- **WHEN** 实施方新增 1 类节点
- **THEN** 系统 MUST 仅需在 `app/nodes/contracts/<type>.py` 中加 1 个 Pydantic BaseModel;`BaseModel.model_json_schema()` 自动暴露 I/O schema + config schema;StateGraph 节点函数由 `app/nodes/registry.py` 通过 Pydantic `model_validate()` 自动包装;不允许手动写 4 份独立代码

#### Scenario: 节点 schema API
- **WHEN** 前端发 `GET /api/nodes/llm/schema`
- **THEN** 系统 MUST 返回 LLM 节点 config schema(JSON Schema 格式),前端用 `@rjsf/core` 渲染 config 面板;返回 MUST 含 `model` / `prompt` / `temperature` 等 LLM 节点专有字段

#### Scenario: 14 节点 schema 全部可查
- **WHEN** 实施方完成本 change
- **THEN** `GET /api/nodes/{type}/schema` 对 14 类节点 MUST 全部返 200 + 非空 JSON schema

### Requirement: 工作流执行
系统 MUST 将画布 JSON 编译为 LangGraph StateGraph 并执行;支持串行/并行、条件路由、错误处理、结果聚合;4 错误边界 MUST 全覆盖(eng-review Quality #3)。编译 MUST 在请求线程完成(compiled_graph 缓存到内存);执行 MUST 异步(后台 asyncio task);执行事件 MUST 持久化到 `node_event` 表 + SSE 流式推送给前端。

#### Scenario: 顺序执行
- **WHEN** 工作流包含 A → B → C 三个顺序节点
- **THEN** 系统 MUST 按 A → B → C 顺序执行,前一个节点完成后再执行下一个;每个节点的 input / output / status / started_at / ended_at MUST 写入 `node_event` 表(eng-review Test #2 需要 100% 覆盖)

#### Scenario: 条件分支
- **WHEN** 工作流包含条件节点 C,边条件为 `{{n2.output.revenue}} > 1000000`
- **THEN** 系统 MUST 评估条件表达式(基于上节点 output),根据 true/false 选择下一节点;表达式 MUST 用 Jinja2 模板,语法错误在 `POST /workflows/:id/validate` 阶段就 MUST 被拒绝

#### Scenario: canvas drag-loop 验证
- **WHEN** 用户 POST `POST /workflows/:id/validate` 时 workflow 含物理环(A → B → A)
- **THEN** 系统 MUST 用 NetworkX `find_cycle()` 检测并返 422 + 中文错误"工作流存在循环,请使用条件分支或循环节点而非物理循环";不允许通过 validate 也不允许 `:run` 启动

#### Scenario: runtime 错误处理(LLM 5xx)
- **WHEN** LLM 节点调用 audit-and-isolation 网关返 5xx 或超时
- **THEN** 系统 MUST 按 retry 策略重试 1 次(1s indexed backoff);最终失败 MUST 标记 `node_event.status=failed` + `workflow_run.status=failed` + `error_class=runtime`,audit log 记录

#### Scenario: user 错误处理(参数不全)
- **WHEN** workflow_definition 启动时,某节点 config 缺必填字段(如 LLM 节点未指定 model)或引用未定义变量
- **THEN** 系统 MUST 在 `node_event` 写入 `status=skipped` + `error_class=user` 并返 422;不允许启动 workflow_run

#### Scenario: security 错误处理(未授权凭证)
- **WHEN** workflow 启动时 LLM 节点需用 credential_id=`cred-123`,workflow 创建者 user_id=`u-1` 无该凭证访问权限
- **THEN** 系统 MUST 调 `credential:8000/v1/credentials/cred-123/access?user_id=u-1` 检查权限,未授权 MUST 返 403 + `error_class=security` + audit log 记录 `unauthorized_credential_access`;不允许启动

### Requirement: Workflow + Chatflow 双模式
系统 MUST 在同一 LangGraph StateGraph 编译路径上支持 workflow(单轮)和 chatflow(多轮)两种模式;通过 `mode` 参数 + dispatch 路径分流。Chatflow = 在 StateGraph 末点加一条回 loop 边 + `thread_id` 设为 `session_id`(同 LangGraph checkpoints 主键)。eng-review Arch #4 锁定。

#### Scenario: workflow 模式
- **WHEN** `POST /workflows/:id:run` 携带 `mode=workflow`
- **THEN** 系统 MUST 按 workflow_definition 执行单次,完成后 `workflow_run.status=completed`;不保留 thread_id 给下次用(无回跳)

#### Scenario: chatflow 模式
- **WHEN** `POST /workflows/:id:run` 携带 `mode=chatflow` 且 header 含 `X-Session-Id`
- **THEN** 系统 MUST 用 `X-Session-Id` 作 thread_id(同 LangGraph checkpoints 主键),checkpoint 持久化到 PG;同一 session 后续调入 MUST 续接 checkpoints,StateGraph 末点有 loop back 边跳回入口节点

#### Scenario: 双模式共享 StateGraph
- **WHEN** 实施方完成本 change
- **THEN** workflow / chatflow MUST 共享同一份 `compile_state_graph(workflow_definition)` 调用,差异仅在 dispatch + thread_id 处理;不允许 2 套独立编译路径

### Requirement: 工作流状态持久化
系统 MUST 将 workflow_definition / workflow_run / node_event / approval 4 张业务表 + LangGraph 官方 `langgraph_checkpoints` 表 持久化到 PostgreSQL;**MUST NOT** 用 Redis 存 workflow execution state(画布实时状态 + event sourcing 留给 `implement-canvas-ui` change)。eng-review Quality #2 本 change 拆分:仅 PG,Redis 推迟。回滚以 PostgreSQL 为准。

#### Scenario: 状态恢复
- **WHEN** workflow_engine service 重启
- **THEN** 系统 MUST 从 PostgreSQL 恢复所有 workflow_definition / workflow_run(已结束的)/ node_event;进行中的 workflow_run MUST 从 `langgraph_checkpoints` 表恢复 thread state,允许重新启动执行

#### Scenario: 5 张表完整
- **WHEN** 实施方完成本 change
- **THEN** Alembic MUST 创建 5 张表:`workflow_definition` / `workflow_run` / `node_event` / `approval` + LangGraph 官方 `checkpoints`(由 langgraph-checkpoint-postgres 自动创建);所有表 MUST 有 PK + 必要索引

### Requirement: 4 critical path 测试 [ENG-Test #2]
本 change 负责 4 个 critical path 中的 2 个:① paul 财务月报 end-to-end(本 service 完整覆盖)② 人工审批中断与续接(本 service 完整覆盖)。其余 2 个:数据隔离网关 PII 拦截(audit-and-isolation 负责)、插件加载失败降级(plugin-market + workflow-engine 协作,本 change 仅做 1 个 stub 端到端)。所有 critical path 测试 MUST 100% 通过,任何失败 MUST 阻断 release。

#### Scenario: paul 财务月报 e2e
- **WHEN** 测试运行"paul 财务月报"workflow(7-8 节点:开始 → HTTP 拉 ERP → 变量赋值 → 条件分支 → LLM 生成月报 → 人工审批 → 结束)
- **THEN** 系统 MUST 100% 通过(7 节点全部完成 + audit log 14 字段完整 + checkpoint 恢复到人工审批点 + resume 后继续到结束);测试时间 < 30s

#### Scenario: 人工审批中断与续接
- **WHEN** workflow 执行到人工审批节点,审批人 24h 内未响应
- **THEN** apscheduler 定时任务 MUST 检测超时 → `approval.status=timeout` + `workflow_run.status=failed` + audit log;若审批人 24h 内响应(POST /approvals/:id:resume),MUST 从 checkpoint 续接,workflow_run 状态回到 running 并继续

#### Scenario: 数据隔离网关 PII 拦截
- **WHEN** workflow 中 LLM 节点 prompt 含 PII(身份证号、手机号)
- **THEN** audit-and-isolation service MUST 阻断 + PII 脱敏 + 写 audit log,workflow 节点标记失败;本 change 端到端测试用 `respx` mock audit-and-isolation 返 422 PII-detected,验证 workflow_run 正确处理错误

#### Scenario: 插件加载失败降级
- **WHEN** workflow 调用的 HTTP 节点 downstream service 返 503
- **THEN** 系统 MUST 走 retry 1 次后 degrade:`node_event.status=skipped` + `error_class=runtime` + workflow_run 继续(若后续节点不依赖此结果),audit log 记录 degradation;不允许 fail-fast 整个 workflow

## ADDED Requirements

### Requirement: 人工审批节点(eng-review Arch #6)
人工审批节点 MUST 实现 4 个设计点:(1) LangGraph Checkpointer 持久化到 PostgreSQL(官方 langgraph-checkpoint-postgres 包)(2) 通知渠道:复用 `audit-and-isolation/app/alerts.py` 发企微 webhook(env var `WECOM_WEBHOOK_URL`,未配置在本地环境不发)(3) web UI reentry:`POST /approvals/:id:resume` 端点 + `GET /approvals/pending?user=X` 列表(前端 UI 留给 `implement-canvas-ui` change)(4) 24h 默认超时:apscheduler 启动时注册 cron job(每 5 分钟扫),超时自动 cancel。

#### Scenario: 节点执行到人工审批
- **WHEN** workflow 节点为 `approval` 类型,执行到该节点
- **THEN** 系统 MUST 写 `langgraph_checkpoints`(thread_id=workflow_run_id)+ 写 `approval` 表(status=pending)+ 发企微 webhook + return pause;workflow_run 状态变 `paused`

#### Scenario: 审批人 reentry
- **WHEN** 审批人 POST `/approvals/:id:resume` 携带 `{"decision": "approved", "payload": {...}}`
- **THEN** 系统 MUST 校验 `approval.approver_user_id == request.user_id` + 更新 approval(status=approved/responded_at=now)+ `langgraph.checkpoints.update_state()` 注入 reentry payload + 触发 LangGraph 续接 + workflow_run 状态回 running;审计写 `approval_resume` event

#### Scenario: 24h 超时
- **WHEN** apscheduler cron 扫到 `approval.created_at < now() - 24h` 且 status=pending
- **THEN** 系统 MUST 更新 approval(status=timeout)+ workflow_run(status=failed, error_class=user, error_message="approval timeout")+ 审计写 `approval_timeout` event;LangGraph thread 标 failed

#### Scenario: 取消审批
- **WHEN** 审批人或 workflow 启动方 POST `/approvals/:id:cancel`
- **THEN** 系统 MUST 更新 approval(status=cancelled)+ workflow_run 状态变 cancelled;LangGraph thread 标 cancelled

### Requirement: 代码执行节点(Docker sandbox)
代码执行节点 MUST 通过 Docker sandbox 外部进程隔离执行用户代码(Python / Node.js)。资源限制 MUST 由 docker daemon 强制:`--cpus=0.5` + `--memory=256m` + `--network=none` + 超时 30s(default,可在节点 config override)。代码 MUST 通过 stdin 写入 container + stdout 读回结果。eng-review Q3 brainstorm 锁定。

#### Scenario: 节点启动 sandbox
- **WHEN** workflow 节点为 `code` 类型,config 包含 `language: "python"` + `code: "print(sum([1,2,3]))"`
- **THEN** 系统 MUST 用 Python Docker SDK 起 `python:3.12-slim` container,挂载代码到 stdin,捕获 stdout,30s 内 kill + 资源 limit 强制;`node_event.output` 写入 stdout 输出

#### Scenario: 超时 / 资源超限
- **WHEN** 代码执行超 30s 或内存超 256m
- **THEN** docker MUST kill container;系统 MUST 写 `node_event.status=failed` + `error_class=runtime` + `error_message="code execution timeout"`;不允许继续占资源

#### Scenario: 网络隔离
- **WHEN** 代码试图访问外网(例如 `urllib.request.urlopen`)
- **THEN** docker `--network=none` MUST 阻断(网络请求立即失败);系统 MUST 写 `node_event.status=failed` + `error_class=security` + `error_message="code execution network not allowed"`;不允许 silent fail

#### Scenario: Node.js 支持
- **WHEN** 代码节点 config `language: "node"`
- **THEN** 系统 MUST 用 `node:20-slim` image 替换 `python:3.12-slim`;其余流程同 Python

### Requirement: 错误处理 4 边界(eng-review Quality #3)
错误处理 MUST 覆盖 4 类边界:① canvas drag-loop(NetworkX cycle detection)② runtime(LLM 5xx / timeout / rate limit,1 次 indexed-backoff retry)③ user(节点 config 缺必填 / 引用未定义变量)④ security(workflow 启动者无凭证访问权)。后端是 source of truth,即使前端有 validation,后端 MUST 独立验证。

#### Scenario: drag-loop
- **WHEN** POST `/workflows/:id/validate` 检测到物理环
- **THEN** 系统 MUST 返 422 + 中文错误信息"工作流存在循环,请使用条件分支或循环节点而非物理循环",写 `node_event.status=skipped` 不创建 workflow_run

#### Scenario: runtime 错误
- **WHEN** LLM / HTTP 节点 upstream 返 5xx 或 timeout
- **THEN** 系统 MUST 1 次 indexed-backoff retry(1s);最终失败写 `error_class=runtime` + `node_event.status=failed` + workflow_run 标 failed;audit log 含 `error_class=runtime`

#### Scenario: user 错误
- **WHEN** 节点 config 缺必填字段 或 Jinja2 模板引用未定义变量
- **THEN** 系统 MUST 在 workflow_definition 启动阶段拒绝(POST /workflows/:id:run 返 422)+ 写 `error_class=user` 到 `node_event`;audit log 含 `error_class=user` + 缺哪个字段

#### Scenario: security 错误
- **WHEN** workflow 启动者 user_id 无权访问节点 config 引用的 credential_id
- **THEN** 系统 MUST POST /workflows/:id:run 返 403 + 写 `error_class=security` 到 `node_event`;audit log 含 `error_class=security` + `unauthorized_credential_access` event

### Requirement: OpenAPI 3.1 接口契约
workflow-engine MUST 暴露 13 个 REST endpoint + 1 个 Node Contract schema endpoint;全部 MUST 在 `/openapi.json` 自动生成 OpenAPI 3.1 schema,前端可下载用于客户端代码生成 / 文档。所有 endpoint MUST 有 Pydantic request / response 模型,validation 错误 MUST 返 422 + 详细 error_class。

#### Scenario: 13 个 endpoint 全部 200 / 4xx
- **WHEN** 实施方完成本 change
- **THEN** `GET /openapi.json` MUST 列出 13 个 endpoint 的完整 schema;13 个 endpoint 全部 MUST 通过单测接口测试(成功路径 + 错误路径)

#### Scenario: 错误响应格式统一
- **WHEN** 任何 endpoint 返 4xx / 5xx
- **THEN** 响应 MUST 是 `{"error_class": "<security|user|runtime|internal>", "error_message": "<中文>", "request_id": "..."}` 格式;不允许返裸 500 stack trace

### Requirement: paul 财务月报 workflow fixture
本 change MUST 提供 1 个"paul 财务月报"完整 workflow JSON fixture(7-8 节点),固化在 `tests/fixtures/paul_monthly_report.json`;端到端测试 MUST 加载此 fixture 跑完完整路径,作为 eng-review Test #2 critical path #1 的实现。

#### Scenario: fixture 节点完整
- **WHEN** 实施方完成本 change
- **THEN** `tests/fixtures/paul_monthly_report.json` MUST 含 7 节点:开始 → http_erp_fetch → variable_assign → condition_branch → llm_summary → approval → end;每节点 config MUST 完整(模型/凭证 ID/审批人等)

#### Scenario: fixture 端到端通过
- **WHEN** 测试加载 fixture 启动 workflow_run(mock ERP HTTP 200 + mock audit-and-isolation 网关返固定 LLM 响应 + mock 企微 webhook 200)
- **THEN** workflow_run MUST 走完 7 节点全部 status=completed,audit_log 14 字段完整,checkpoint 在 approval 点可被 reentry API resume
