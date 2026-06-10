# Tasks — implement-audit-and-isolation

> 模式: superpowers-bridge
> 阶段: tasks
> 关联: `proposal.md` + `design.md` + `specs/llm-egress-gateway/spec.md` (15 Req × 55 Scenario)
> 编码约束: Python FastAPI + SQLAlchemy 2.0 async + Pydantic v2 + 异步 httpx
> 任务粒度: ≤ 2h
> 测试约束: 编码任务必配对验证任务(单元 + 集成 + perf)
> 日期: 2026-06-10

## 1. 项目脚手架

- [ ] 1.1 创建 `services/audit-and-isolation/` 目录结构(app/、tests/、perf/、alembic/、docs/)
- [ ] 1.2 写 `pyproject.toml` — fastapi/uvicorn/httpx/sqlalchemy[asyncio]/asyncpg/alembic/redis/pydantic v2/python-jose + dev: pytest/pytest-asyncio/pytest-cov/testcontainers[fakeredis]/ruff/bandit
- [ ] 1.3 写 `Dockerfile` 多阶段 build(对齐 services/credential/Dockerfile)
- [ ] 1.4 写 `.env.example` 列出全部环境变量
- [ ] 1.5 写 `app/config.py` Pydantic Settings(dataclass 风格)

## 2. 数据库 schema + migration

- [ ] 2.1 写 `alembic.ini` + `alembic/env.py`(async URL)
- [ ] 2.2 写 migration:创建 `audit_log` 表(15 字段)+ 2 个索引(trace_id / user_id+created_at)
- [ ] 2.3 写 migration:创建 `model_routing` 表(5 字段)+ PK on model_name
- [ ] 2.4 写 SQLAlchemy ORM:`app/models/audit.py` AuditLog / ModelRouting dataclass
- [ ] 2.5 写 seed script:预置 3 条 model_routing(qwen-max public / deepseek public / internal-vllm-qwen private)
- [ ] 2.6 **验证任务**:在 docker-compose PG 上跑 `alembic upgrade head` + seed → audit_log/model_routing 表存在,seed 数据可读

## 3. Pydantic 数据模型

- [ ] 3.1 写 `app/models/llm.py`:ChatCompletionRequest / ChatCompletionResponse / Message(对齐 OpenAI schema)
- [ ] 3.2 写 `app/models/common.py`:HeaderSchema(trace_id / model_kind / bypass_isolation)+ ErrorResponse
- [ ] 3.3 **验证任务**:每个 model 写 1 个 pytest(pydantic validation + 边界 case)

## 4. Redis 客户端 + 共享 client

- [ ] 4.1 写 `app/redis_client.py`:异步 redis client(连接池 50)+ key 命名空间(redact:trace:{id} / routing:model:{name})
- [ ] 4.2 **验证任务**:单元测试 — client ping / key 写读 / TTL 设置

## 5. PII 检测器核心(D3 + D4 + D5 决策)

- [ ] 5.1 写 `app/pii/rules.py`:6 类正则(身份证/手机/银行卡/邮箱/信用代码/营收金额)+ 预编译缓存
- [ ] 5.2 写 `app/pii/detector.py`:扫描文本 → 返回 list[(类型, 起始, 终止, 原值)]
- [ ] 5.3 写 `app/pii/redactor.py`:接收 detector 结果 → 生成 `[类型_xxxx]` 占位符 + 写 Redis map
- [ ] 5.4 写 `app/pii/reverser.py`:接收 response + trace_id → 查 Redis map 替换占位符
- [ ] 5.5 **验证任务**:6 类规则各 5 case × 命中/不命中/边界 → 30 个单元测试
- [ ] 5.6 **验证任务**:redactor + reverser 端到端 1 个集成测试(testcontainers[postgres] + fakeredis)

## 6. 模型路由(D6 + D7 + D11 决策)

- [ ] 6.1 写 `app/routing/table.py`:启动时加载 model_routing → Redis cache(TTL 60s)+ 内存 fallback copy
- [ ] 6.2 写 `app/routing/dispatcher.py`:按 X-Model-Kind / X-Bypass-Isolation 决定(走脱敏 / 走 bypass / 选 base_url)
- [ ] 6.3 **验证任务**:单元测试 dispatcher 各分支(public + 脱敏 / public + bypass 应忽略 / private + bypass / private + 不 bypass)
- [ ] 6.4 **验证任务**:集成测试 routing 启动时加载 + Redis 不可达时降级到内存

## 7. LLM 上游调用 + 透传

- [ ] 7.1 写 `app/llm/client.py`:httpx.AsyncClient 透传(连接池 keep-alive,timeout 30s)
- [ ] 7.2 写 `app/llm/streaming.py`:SSE 流式响应处理(可逆脱敏应用每 chunk)
- [ ] 7.3 **验证任务**:单元测试 client 重试(指数退避 200ms)+ timeout 取消
- [ ] 7.4 **验证任务**:集成测试 假 LLM(用 aiohttp 起本地 server mock)→ 透传保真

## 8. 审计写入(D13 决策,outbox 模式)

- [ ] 8.1 写 `app/audit/hash.py`:SHA-256 of redacted prompt
- [ ] 8.2 写 `app/audit/writer.py`:outbox 模式(async 队列 + 写 PG)+ 失败重试(3 次指数退避)
- [ ] 8.3 **验证任务**:单元测试 hash 一致性 + writer 重试
- [ ] 8.4 **验证任务**:集成测试 audit 14 字段完整性 + 明文不入库(grep 验证)

## 9. Service token 鉴权(D9 + Security 边界)

- [ ] 9.1 写 `app/auth.py`:service token 验证(从 credential service 拉公钥 + 验签)
- [ ] 9.2 **验证任务**:单元测试 有效/无效/过期 token(401)
- [ ] 9.3 **验证任务**:集成测试 真实调 credential service 拿 token(maybe 跳过 + mock)

## 10. credential service 集成(D9 决策)

- [ ] 10.1 写 `app/credential_client.py`:httpx async 调 credential service `use_credential` API + 5min cache
- [ ] 10.2 **验证任务**:单元测试 cache 命中/失效
- [ ] 10.3 **验证任务**:集成测试 credential 不可达 → 503 + audit error_class

## 11. 错误处理 4 边界(Quality #3)

- [ ] 11.1 写 `app/errors.py`:统一异常 handler(401/422/413/502/503/504)
- [ ] 11.2 实现 RuntimeError(PIIDetectorUnavailable → Fail-Open + WARN)
- [ ] 11.3 实现 Upstream5xx → 1 次重试 + 仍失败 502
- [ ] 11.4 实现 UpstreamTimeout → 504
- [ ] 11.5 实现 UpstreamRateLimited(429)→ 透传 + audit
- [ ] 11.6 实现 CredentialServiceUnavailable → 503 + 告警
- [ ] 11.7 实现 RedisUnavailable → 内存 fallback + WARN
- [ ] 11.8 **验证任务**:每个错误场景 1 个集成测试(用 mock 触发)

## 12. 核心 API 端点

- [ ] 12.1 写 `app/main.py`:FastAPI app + lifespan(启动时加载路由表 + redis client + 鉴权 setup)
- [ ] 12.2 写 `app/api/chat.py`:POST /v1/chat/completions 端点
- [ ] 12.3 写 `app/api/health.py`:GET /healthz + GET /readyz(PG/Redis/credential 3 检)
- [ ] 12.4 写 `app/api/models.py`:GET /v1/models(列 model_routing 表启用的 model)
- [ ] 12.5 **验证任务**:单元测试 端点参数校验 + 错误码
- [ ] 12.6 **验证任务**:集成测试 端到端 4 个场景(public + PII / private + bypass / PII detector 异常 / 上游 timeout)

## 13. metric + 告警(D2 + R1 + R3 + R4 风险)

- [ ] 13.1 写 `app/metrics.py`:Prometheus counter / histogram(pii_detector_fail_open_total / upstream_5xx_total / latency_seconds)
- [ ] 13.2 写 `app/alerts.py`:webhook 触发(PagerDuty / 企微)— PII fail-open / Redis down / credential down / 双实例挂
- [ ] 13.3 **验证任务**:单元测试 metric counter 累加

## 14. Dockerfile + docker-compose

- [ ] 14.1 写 `services/audit-and-isolation/Dockerfile` 多阶段 builder + runtime non-root user(UID 10001)
- [ ] 14.2 改 `infrastructure/docker-compose.yml`:追加 audit-and-isolation + audit-and-isolation-migrate + healthcheck
- [ ] 14.3 **验证任务**:`docker compose up` 成功,3 容器都 healthy,2 实例 HA 验证(Kill 1 个,另一个接流量)

## 15. OpenAPI 导出

- [ ] 15.1 写 `docs/openapi/audit-and-isolation.yaml`(用 FastAPI 自动生成)
- [ ] 15.2 **验证任务**:OpenAPI yaml 通过 openapi-spec-validator

## 16. 性能基准(D15 + Perf #1)

- [ ] 16.1 写 `perf/bench_proxy.py`:100 RPS × 60s,假 LLM mock,统计 P50/P95/P99 latency
- [ ] 16.2 写 `perf/bench_use_api_smoke.py`:in-process 500 ops P99 smoke test
- [ ] 16.3 **验证任务**:跑 bench_proxy → P99 < 50ms;不达标调优(httpx keep-alive / regex cache)

## 17. 4 critical path 100% 覆盖(eng-review Test #2 #2)

- [ ] 17.1 子场景 2.1:身份证脱敏 + 还原 e2e(testcontainers + 假 LLM)
- [ ] 17.2 子场景 2.2:手机/银行卡边界 e2e
- [ ] 17.3 子场景 2.3:邮箱/信用代码/营收 e2e
- [ ] 17.4 子场景 2.4:响应侧还原(同 trace 多轮)e2e
- [ ] 17.5 子场景 2.5:PII Fail-Open(monkey-patch detector 抛异常)
- [ ] 17.6 子场景 2.6:上游 timeout e2e
- [ ] 17.7 子场景 2.7:credential down e2e
- [ ] 17.8 子场景 2.8:trace 跨实例 e2e(模拟 2 个 instance + 共享 Redis)
- [ ] 17.9 **验证任务**:8 个子场景全部通过,缺一不可

## 18. CI gate / verify 脚本

- [ ] 18.1 写 `verify.py` — 18 项检查(单元 100% / 集成通过 / ruff / bandit / no-plaintext grep / perf bench / 8 critical path)
- [ ] 18.2 **验证任务**:跑 verify.py 全部通过(17/17 Req × Scenario)

## 19. 安全审计(CLAUDE.md 全局约束)

- [ ] 19.1 grep "api[_-]key.*=.*['\"]" app/ tests/ → 必须 0 命中
- [ ] 19.2 grep "BEGIN PRIVATE" . → 必须 0 命中
- [ ] 19.3 audit_log 不含明文 grep("110101" 在 audit 表 → 0 行)
- [ ] 19.4 跑 bandit -r app/ → 0 high
- [ ] 19.5 **验证任务**:4 项全 0 命中

## 20. 文档 + 收尾

- [ ] 20.1 写 `services/audit-and-isolation/README.md`(架构图 + 部署 + 测试)
- [ ] 20.2 写 `openspec/changes/implement-audit-and-isolation/verify.md`(17 Req × Scenario 矩阵)
- [ ] 20.3 写 `openspec/changes/implement-audit-and-isolation/retrospective.md`(经验教训)
- [ ] 20.4 **验证任务**:3 个 markdown 通过 markdownlint

## 任务汇总

| 编号 | 范围 | 任务数 | 编码 | 验证 |
|------|------|--------|------|------|
| 1 | 脚手架 | 5 | 4 | 1 |
| 2 | DB migration | 6 | 5 | 1 |
| 3 | Pydantic 模型 | 3 | 2 | 1 |
| 4 | Redis client | 2 | 1 | 1 |
| 5 | PII 核心 | 6 | 4 | 2 |
| 6 | 模型路由 | 4 | 2 | 2 |
| 7 | LLM 透传 | 4 | 2 | 2 |
| 8 | 审计写入 | 4 | 2 | 2 |
| 9 | 鉴权 | 3 | 1 | 2 |
| 10 | credential 集成 | 3 | 1 | 2 |
| 11 | 错误处理 | 8 | 7 | 1 |
| 12 | API 端点 | 6 | 4 | 2 |
| 13 | metric + 告警 | 3 | 2 | 1 |
| 14 | Docker | 3 | 2 | 1 |
| 15 | OpenAPI | 2 | 1 | 1 |
| 16 | perf 基准 | 3 | 2 | 1 |
| 17 | 4 critical path | 9 | 0 | 9 |
| 18 | verify 脚本 | 2 | 1 | 1 |
| 19 | 安全审计 | 5 | 0 | 5 |
| 20 | 文档收尾 | 4 | 3 | 1 |
| **总计** | — | **85** | **58** | **27** |

**编码:验证比 ≈ 2.15:1**,所有"编码"task 必配至少一条"验证"task(共 27 条验证任务覆盖 58 条编码任务,部分验证覆盖多条编码)。
