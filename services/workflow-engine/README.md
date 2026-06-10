# ChatBiz Workflow Engine

ChatBiz workflow-engine: 可视化工作流引擎后端,基于 LangGraph 0.2 编译执行,Node Contract (Pydantic BaseModel) 统一驱动 14 类节点。**eng-review Arch #2 / #4 / #6 + Quality #1 / #2 / #3 + Test #2 + Perf #2 锁定 8 个 finding 全部落地。**

> **For agentic workers:** Use `superpowers:subagent-driven-development` to extend this service.

## 启动

### 本地 (开发模式)

```bash
cd services/workflow-engine
uv sync --all-extras                # 安装运行时 + 开发依赖
cp .env.example .env                # 配置环境变量
alembic upgrade head                # 跑数据库迁移
uvicorn app.main:app --reload --port 8001
```

### Docker Compose (集成模式)

```bash
# 在仓库根目录
docker compose up workflow-engine workflow-engine-migrate
# workflow-engine 服务跑在 http://localhost:8001
```

依赖服务(必须先起来):
- `postgres` (port 5432, 提供 `workflow_engine` 数据库)
- `redis` (port 6379)
- `audit-and-isolation` (port 8080, LLM 网关)
- `credential` (port 8000, 凭证服务)

可选依赖(未实现返 503,不会阻塞启动):
- `knowledge-base` (port 8002)
- `agent-runtime` (port 8003)

## API (13 个 endpoint)

| Method | Path | 用途 |
|--------|------|------|
| POST | /workflows | 创建工作流 |
| GET | /workflows/:id | 读 latest version |
| GET | /workflows/:id/versions | 列历史版本 |
| GET | /workflows/:id/versions/:v | 读指定版本 |
| PUT | /workflows/:id | 更新(生成新 version) |
| DELETE | /workflows/:id | 软删除 |
| POST | /workflows/:id/validate | DAG 循环 + config 验证 |
| POST | /workflows/:id:run | 异步启动一次执行(返 202 + run_id) |
| GET | /runs/:run_id | 查询 run 状态 |
| GET | /runs/:run_id/events | SSE 流式节点事件 |
| GET | /approvals/pending?user=X | 查待审批 |
| POST | /approvals/:id:resume | 接收 reentry |
| POST | /approvals/:id:cancel | 取消审批 |
| GET | /api/nodes | 列出 14 类节点 |
| GET | /api/nodes/:type/schema | 节点 config schema(给前端消费) |
| GET | /healthz | 进程存活 |
| GET | /readyz | 依赖健康(PG + Redis + audit + credential) |

**完整 OpenAPI 3.1 schema**: `GET /openapi.json` 或 `python scripts/export_openapi.py > openapi.json`

## 14 类节点

`GET /api/nodes` 列出全部。每类节点通过 Node Contract (Pydantic BaseModel) 统一驱动 4 份产物:
1. **Canvas UI config schema** — `GET /api/nodes/:type/schema` 返 JSON Schema,前端用 `@rjsf/core` 渲染
2. **StateGraph 节点函数** — `wrap_for_langgraph()` 自动包装
3. **I/O JSON schema** — 来自 Pydantic `model_json_schema()`
4. **验证函数** — Pydantic `model_validate()`

| 类型 | 用途 | config 必填字段 |
|------|------|---------------|
| `start` | 工作流入口 | (无) |
| `end` | 工作流出口 | output_keys (可选) |
| `variable_assign` | 变量赋值(Jinja2) | vars (dict) |
| `condition` | if/else 路由 | expression (Jinja2) |
| `llm` | 调 LLM(经 audit-and-isolation 网关) | model, credential_id, prompt |
| `knowledge` | RAG 检索(stub) | knowledge_base_id, query |
| `agent` | Lead/Sub Agent(stub) | agent_id, task |
| `http` | HTTP 请求 | method, url, retry_count |
| `code` | Docker sandbox 跑 Python/Node | language, code, cpu, memory_mb, timeout_s |
| `approval` | 人工审批(eng-review Arch #6) | approver_user_id, timeout_hours, approval_content_template |
| `loop` | 条件循环 | max_iterations, exit_condition |
| `iterate` | 数组批处理 | input_array, concurrency, error_strategy |
| `subflow` | 调用子工作流 | sub_workflow_id, input_mapping, output_mapping |
| `extract` | LLM 结构化提取 | source (Jinja2), schema (dict) |

## 4 错误边界 (eng-review Quality #3)

所有 4xx/5xx 响应格式统一:
```json
{"error_class": "user|security|runtime|internal", "error_message": "<中文>", "request_id": "..."}
```

| 边界 | 触发 | 响应 |
|------|------|------|
| `drag-loop` | POST /workflows/:id/validate 检测到物理环 | 422 + 中文错误 |
| `runtime` | LLM 5xx / HTTP 5xx / timeout | 502(1 次 indexed-backoff retry) |
| `user` | config 缺必填 / 变量未定义 | 422(不重试) |
| `security` | workflow 启动方无凭证访问权 | 403(不重试) |

## 4 critical path (eng-review Test #2)

| Path | 本 change 覆盖 |
|------|---------------|
| paul 财务月报 end-to-end | 完整 7 节点 fixture + 1 完整 e2e 测试 |
| 数据隔离网关 PII 拦截 | audit-and-isolation 负责;本 change 用 mock 网关返 422 验证 workflow 错误处理 |
| 人工审批中断与续接 | 完整 4 设计点(checkpoint + 通知 + reentry + 24h timeout cron) |
| 插件加载失败降级 | HTTP 节点 503 → retry 1 次 → degrade 路径 |

## 测试

```bash
# 单测 + 集成测试(需要 pip install 完成)
cd services/workflow-engine
pytest                              # 全部测试 + 覆盖率报告
pytest tests/e2e/                  # 仅 e2e
pytest tests/security/             # 仅安全测试
pytest --cov=app --cov-fail-under=100  # 强制 100% 覆盖率

# 性能基准
python scripts/perf_bench.py --base-url http://127.0.0.1:8001 --requests 100
# 目标: 所有 endpoint p99 < 500ms
```

## 故障排查

| 症状 | 检查 |
|------|------|
| `GET /readyz` 返 503 | 检查 postgres / redis / audit-and-isolation / credential 是否可达 |
| LLM 节点 always 失败 | 检查 `AUDIT_ISOLATION_URL` + `WORKFLOW_ENGINE_SERVICE_TOKEN` |
| 人工审批 24h 超时未触发 | apscheduler 是否启动?看 lifespan 日志 `cron started` |
| workflow_run 一直 pending | 看 `GET /runs/:run_id` 的 `error_class` / `error_message` |
| docker sandbox 启动失败 | 检查 `DOCKER_SOCKET` 是否挂载 + `DOCKER_SANDBOX_ENABLED=true` |

## 安全注意

1. **代码执行节点**:必须挂 docker socket + 设 `no-new-privileges`(docker-compose 已配置)
2. **凭据访问**:workflow 启动时预检,无权限返 403
3. **多租户**:所有 API 强制检查 `X-User-Id` header(MVP 阶段;V1.0 切 IAM/JWT)
4. **PII 保护**:LLM 节点的所有调用经 audit-and-isolation 网关,Prompt/Response 自动脱敏

## 相关 service

- `services/credential` — 凭证管理 + 权限检查
- `services/audit-and-isolation` — LLM 网关 + PII 脱敏
- `services/knowledge-base` — (待实现) 知识检索真实实现
- `services/agent-runtime` — (待实现) Lead/Sub Agent 真实实现

## License

MIT (see LICENSE at repo root)
