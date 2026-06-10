# tasks: implement-workflow-engine

> 子 skill 派发: `superpowers:subagent-driven-development`(fresh subagent per task + spec/quality 两段 review)。
> 单条任务 ≤ 2h,每条编码任务配对一条验证任务。

## 1. 脚手架 + 配置

- [x] 1.1 创建 `services/workflow-engine/` 目录结构 + `pyproject.toml`(langgraph/langchain-openai/networkx/apscheduler/docker/fastapi/sqlalchemy[asyncio]/asyncpg/alembic/pytest/httpx/fakeredis/respx/aiosqlite/testcontainers[postgres,redis])
- [x] 1.2 写 `Dockerfile`(多阶段 builder + non-root + healthcheck)+ `.env.example`(DATABASE_URL / REDIS_URL / AUDIT_ISOLATION_URL / CREDENTIAL_SERVICE_URL / WECOM_WEBHOOK_URL / KAFKA_BOOTSTRAP_SERVERS 等 env)
- [x] 1.3 写 `app/config.py` Pydantic Settings(13+ 字段,含 service token / 模式 default)
- [x] 1.4 写 `app/__init__.py` + `app/main.py` FastAPI 启动入口(暂返 /healthz 200)
- [x] 1.5 验证:docker build 通过 + pytest 空 runner 启动 OK + 第一个 commit "feat(workflow-engine): scaffold + config"

## 2. PostgreSQL ORM + Alembic

- [x] 2.1 写 `app/database.py` SQLAlchemy 2.0 异步 engine + `get_session()` + `dispose_engine()`
- [x] 2.2 写 `app/models/__init__.py` + `app/models/base.py` DeclarativeBase
- [x] 2.3 写 `app/models/workflow.py`:WorkflowDefinition / WorkflowRun / NodeEvent / Approval(SQLAlchemy 异步,字段与 spec 完全对应)
- [x] 2.4 写 alembic `env.py` 异步配置 + `alembic.ini`
- [x] 2.5 写 migration 4 个:`001_workflow_definition.py` / `002_workflow_run.py` / `003_node_event.py` / `004_approval.py`(含索引 + 外键)
- [x] 2.6 写 LangGraph `AsyncPostgresSaver.setup()` 启动钩子(自动建 `checkpoints` 表)
- [x] 2.7 验证:pytest `test_orm.py` 单测覆盖 4 表 CRUD + alembic upgrade/downgrade 双向 OK + commit

## 3. Redis + 服务客户端

- [x] 3.1 写 `app/redis_client.py` get_redis() 单例(同 audit-and-isolation 风格,pool=50 + decode_responses=True)
- [x] 3.2 写 `app/clients/audit_isolation.py` httpx async client(透传到 `http://audit-and-isolation:8080/v1/chat/completions`,带 X-Service-Token + X-Trace-Id)
- [x] 3.3 写 `app/clients/credential.py` httpx async client(调 `/v1/credentials/:id/access?user_id=` 验证权限)
- [x] 3.4 写 `app/clients/knowledge_base.py` + `app/clients/agent_runtime.py`(stub URL,未实现返 503,本 change 集成用 respx mock)
- [x] 3.5 验证:respx mock 3 个 client 单测 + commit

## 4. Node Contract codegen(eng-review Arch #2 / Quality #1)

- [x] 4.1 写 `app/nodes/registry.py`:NODE_REGISTRY 全局字典 + `register(BaseModel)` 装饰器 + `wrap_node(BaseModel) -> LangGraph node function`
- [x] 4.2 写 `app/nodes/contracts/base.py`:`BaseNode` Pydantic BaseModel + `BaseConfig` 通用基类
- [x] 4.3 写 `app/nodes/contracts/start.py` + `end.py` + `variable_assign.py`(最简单的 3 个节点,走通 contract 注册 → execute → 校验)
- [x] 4.4 写 `app/nodes/contracts/condition.py`(Jinja2 表达式解析,边 condition 在 execute 后返回 route 决策)
- [x] 4.5 写 `app/nodes/contracts/llm.py`(调 audit-and-isolation 网关 + langchain-openai)
- [x] 4.6 写 `app/nodes/contracts/knowledge.py` + `agent.py`(HTTP stub,未实现返 503)
- [x] 4.7 写 `app/nodes/contracts/http.py`(httpx 调外部 API,retry + backoff)
- [x] 4.8 写 `app/nodes/contracts/code.py`(Python Docker SDK 起 container,`--cpus` / `--memory` / `--network=none` / 30s 超时)
- [x] 4.9 写 `app/nodes/contracts/approval.py`(写 checkpoint + approval 表 + 发企微 + workflow_run paused)
- [x] 4.10 写 `app/nodes/contracts/loop.py` + `iterate.py` + `subflow.py` + `extract.py`(剩余 4 节点)
- [x] 4.11 验证:每个 contract 单测 + `GET /api/nodes/:type/schema` 14 节点全过 + commit

## 5. StateGraph 编译器(eng-review Arch #4)

- [x] 5.1 写 `app/graph/compiler.py`:`compile_state_graph(workflow_definition: dict) -> CompiledStateGraph`(纯函数,含 cache)
- [x] 5.2 写 `app/graph/jinja.py` Jinja2 渲染 + 变量上下文(`variables` 字段注入)
- [x] 5.3 写 `app/graph/conditional.py`:condition 节点 → `add_conditional_edges()` 桥接
- [x] 5.4 写 `app/graph/dispatcher.py`:workflow mode(随机 thread_id)vs chatflow mode(X-Session-Id 作 thread_id)
- [x] 5.5 验证:7 节点顺序 workflow 编译 OK + condition 真假分支 + 双模式 dispatch 单测 + commit

## 6. 执行引擎 + workflow_run 状态机

- [x] 6.1 写 `app/executor/runner.py`:asyncio.create_task 跑 workflow_run + 状态机 `pending → running → (paused|completed|failed|cancelled)`
- [x] 6.2 写 `app/executor/retry.py`:runtime 错误 1 次 indexed-backoff retry,user/security 不重试
- [x] 6.3 写 `app/executor/node_event.py`:写 node_event(input/output/status/时间/retry_count/error_class)
- [x] 6.4 写 `app/executor/credential_check.py`:workflow 启动时遍历节点 config 调 credential 客户端检查权限
- [x] 6.5 写 `app/executor/sse.py`:SSE `/runs/:run_id/events` 端点(基于 asyncio.Queue per-client + node_event polling)
- [x] 6.6 验证:paul 月报 7 节点端到端跑完(单测 mock 全外部依赖)+ retry 测试 + SSE 多客户端测试 + commit

## 7. REST API(13 个 endpoint)

- [x] 7.1 写 `app/api/workflows.py`:POST /workflows + GET /workflows/:id + GET /versions + GET /versions/:v + PUT + DELETE
- [x] 7.2 写 `app/api/validate.py`:POST /workflows/:id/validate(NetworkX cycle detection + config schema 验证 + Jinja2 语法检查)
- [x] 7.3 写 `app/api/run.py`:POST /workflows/:id:run(异步启动 + 返 202 + run_id)
- [x] 7.4 写 `app/api/runs.py`:GET /runs/:run_id + GET /runs/:run_id/events(SSE)
- [x] 7.5 写 `app/api/approvals.py`:GET /approvals/pending + POST /approvals/:id:resume + POST /approvals/:id:cancel
- [x] 7.6 写 `app/api/nodes.py`:GET /api/nodes/:type/schema(暴露 Node Contract)
- [x] 7.7 写 `app/api/health.py`:GET /healthz + /readyz(检查 postgres + redis + audit-and-isolation + credential)
- [x] 7.8 验证:13 endpoint 全部接口测试(成功 + 错误路径)+ OpenAPI schema 自动生成 OK + commit

## 8. 错误处理 4 边界(eng-review Quality #3)

- [x] 8.1 写 `app/errors/classes.py`:7 个 exception class(SecurityError / UserError / RuntimeError / InternalError / NodeTypeNotRegisteredError / NodeOutputValidationError / CodeExecutionFailed)
- [x] 8.2 写 `app/errors/middleware.py`:统一 4xx/5xx 响应格式 `{error_class, error_message, request_id}`
- [x] 8.3 写 `app/errors/handlers.py`:Pydantic ValidationError → user;httpx 5xx → runtime;权限 → security
- [x] 8.4 写 `app/errors/cycle_detection.py`:NetworkX find_cycle 工具
- [x] 8.5 验证:4 错误边界各 2-3 个单测 + 错误响应格式统一测试 + commit

## 9. 人工审批 cron + 通知(eng-review Arch #6)

- [x] 9.1 写 `app/cron/__init__.py` + `app/cron/approval_timeout.py`:apscheduler AsyncIOScheduler 注册 cron job(每 5 分钟扫)
- [x] 9.2 写 cron 任务:`SELECT ... FOR UPDATE SKIP LOCKED` 锁 24h+ pending approval → 标 timeout + workflow_run failed + audit log
- [x] 9.3 写 `app/cron/cleanup.py`:每周扫 90 天前终态 workflow_run + 关联 node_event(DELETE)
- [x] 9.4 写 `app/cron/lifespan.py`:FastAPI lifespan 启动时启 cron + 关闭时停 cron
- [x] 9.5 验证:approval 24h timeout 测试 + 90 天 cleanup 测试(用 freeze_time)+ cron 启停测试 + commit

## 10. Docker compose + OpenAPI

- [x] 10.1 docker-compose.yml 加 `workflow-engine` + `workflow-engine-migrate` 服务(挂 docker socket + security_opt no-new-privileges)
- [x] 10.2 OpenAPI schema 导出脚本 `scripts/export_openapi.py`(跑出 `openapi.json` 给前端消费)
- [x] 10.3 perf bench 脚本 `scripts/perf_bench.py`(5 个关键 endpoint 压测,记录 p50/p99)
- [x] 10.4 验证:docker compose up 全栈启动 + OpenAPI 完整 + perf bench p99<500ms + commit

## 11. 4 critical path E2E + 安全测试

- [x] 11.1 写 `tests/fixtures/paul_monthly_report.json`:7-8 节点完整 workflow fixture
- [x] 11.2 写 `tests/e2e/test_paul_monthly_report.py`:端到端跑 fixture(mock ERP HTTP + mock 网关 + mock 企微),全 7 节点 100% 走完
- [x] 11.3 写 `tests/e2e/test_manual_approval.py`:触发 approval → paused → resume → 续接完成 + 24h timeout
- [x] 11.4 写 `tests/e2e/test_pii_blocked.py`:mock 网关返 PII 422 → 验证 workflow_run 标 failed + audit log
- [x] 11.5 写 `tests/e2e/test_plugin_degradation.py`:HTTP 节点 downstream 503 → retry 1 次 → degrade → workflow_run 继续
- [x] 11.6 写 `tests/security/test_credential_check.py`:无权限凭证 → 403 + audit log
- [x] 11.7 写 `tests/security/test_cross_user.py`:跨用户访问 → 403
- [x] 11.8 验证:11.x 全部 e2e + security 100% 通过 + 覆盖率 ≥ 100% / 接口 100% + commit

## 12. 文档 + verify.py CI gate

- [x] 12.1 写 `services/workflow-engine/README.md`(启动方式 / env 变量 / 测试 / 故障排查)
- [x] 12.2 写 `verify.py` CI gate 脚本(eng-review 锁定 18 个 gate:17 requirement + 1 集成 smoke)
- [x] 12.3 写 `tests/integration/test_docker_compose.py`:docker compose up + curl /readyz 200 + curl /api/nodes/llm/schema 200
- [x] 12.4 ruff fix 所有 lint + 全部单测 + e2e + 集成测试通过
- [x] 12.5 最终 commit "feat(workflow-engine): complete + verify gate + 4 critical path e2e" + 整理 commit history

---

**统计**: 12 大组 × 子任务 = ~85 条任务。每条 ≤ 2h。编码任务全部配对验证任务(7.1 → 7.8 / 4.x → 4.11 等)。Node Contract(Q4 + 4.3 → 4.10)+ 错误处理(Q12 + 8.x)+ 人工审批(Q11 + 9.x)三组是本 change 的特色工程,优先级最高。
