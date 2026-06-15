# Design:数据隔离网关补差(eng-review #1 + 周边 P0)

## Context

仓库已实现 `services/audit-and-isolation/`(2335 行 Python,alembic 迁移,Dockerfile,100% 覆盖率强制,eng-review Arch #1 引用)。该服务已覆盖 egress 主体的 **80%**:OpenAI 兼容代理 + credential service auth + PII mask-only 可逆 + metadata-only 审计 + 模型路由 + outbox 异步落 PG + 22 个单元测试 + 13 个集成测试(含 4 个 critical path)。本 spec **不再重建主体**,改为**补差**:HA 拓扑、编译期静态扫描、定时归档、跨实例 trace 查询、`/metrics` 端点暴露、4 个 perf contract 桩、`docs/architecture.md` §4.3.Y PII 规则集段。

`docs/architecture.md` §4 已冻结;`docs/prd.md` v1.5 已就绪;eng-review 12 个工程决策 locked-in。本 design 锁定 **5 个补差决策**,与既有 audit-and-isolation 设计兼容。

仓库 0 行新增 egress 代码(已有实现) → 本 spec 落地后约 **800-1200 行增量**(独立 scanner + 2 端点 + K8s manifest + 文档)。

## Goals

- **G1:** audit-and-isolation 升级为 2 实例 active-active HA,任一实例故障 < 5s 自动切换
- **G2:** 编译期防御:直连 `openai` / `anthropic` 等 import 在 CI 阶段被静态扫描拦截
- **G3:** 定时归档:90 天 PG 热数据,90 天后 MinIO 冷(eng-review Perf #2 锁定的 780GB/3mo 路径落地)
- **G4:** 跨实例 trace 关联可查询:`GET /v1/traces/{trace_id}` 端点,Redis cache 命中 < 100ms
- **G5:** 性能 contract 落地:4 个 Protocol + Noop 默认实现 + `/metrics` 端点暴露
- **G6:** `docs/architecture.md` §4.3.Y 补 PII 规则集段,设计文档与代码同步

## Decisions

| ID | 决策 | 出处 |
|---|---|---|
| D1 | 2 实例 active-active,前置 NGINX stream L4 LB(2 upstream,5s health check) | eng-review #1 |
| D2 | K8s `terminationGracePeriodSeconds=45s`(preStop 30s 排空 + 15s 缓冲,避免 SIGKILL) | H3 修正 |
| D3 | 客户端 `RetryWithIdempotency` 装饰器:`Idempotency-Key` = SHA-256 of `user_id + body_hash + 5min_timestamp_bucket`,5s 内最多 3 次重试 | brainstorm Q4 |
| D4 | 静态扫描独立服务 `services/gateway-scanner/`(纯 CLI,无 FastAPI / 无 DB),blocklist + allowlist yaml 配置,AST 扫描核心用 `ast` 库,违规退出码 1 | brainstorm Q3-A 编译期防御 |
| D5 | 定时归档 `services/audit-and-isolation/jobs/archive_audit.py`:每日 02:00 UTC 把超 90 天的行 COPY 到 MinIO `s3://chatbiz-audit-cold/yyyy/mm/dd.parquet`,PG 端 DELETE | eng-review Perf #2 #1 |
| D6 | trace 跨实例查询端点 `GET /v1/traces/{trace_id}`:Redis(`trace:cache:*` namespace,db 0,5min TTL)优先 → PG 降级 → 404;Redis 失败不阻塞 | eng-review #1 + #8 |
| D7 | 4 个 perf contract Protocol(RateLimiter / ResponseCache / RequestBatcher / MetricsExporter)+ Noop 默认实现,主流程嵌入调用点,失败降级 Noop | eng-review Perf #1 |
| D8 | `/metrics` 端点:Prometheus exposition format,5 类指标(requests_total / duration_seconds / pii_hits / active_connections / trace_cache_hits),HELP + TYPE 注释 | eng-review Perf #1 |
| D9 | 复用现有 credential service 路径(`Authorization: Bearer <token>`),**不**引入 HMAC `X-Gateway-Signature`(避免破坏 service-to-service 信任链) | DC1 决策 |
| D10 | 复用现有 PII mask-only 可逆设计(`app/pii/redactor.py` + `reverser.py`),**不**引入 block 档 / log-only 档(与现有 mask-only 冲突,eng-review 未锁定) | DC2 决策 |
| D11 | trace_id 透传模式:调用方传 `X-Trace-Id`,网关透传;若缺失则生成 UUIDv7 | DC3 决策 |
| D12 | `docs/architecture.md` §4.3.Y 补 PII 规则集段(6 类正则 + 可逆机制),**先在 CLAUDE.md surface** | design 文档同步 |
| D13 | 测试:3 层(单元 pytest + 集成 httpx + e2e docker-compose 启动 2 实例 + NGINX),覆盖率 ≥ 100%(沿用 audit-and-isolation `pyproject.toml` 配置) | eng-review Test #1 |

## 与 source of truth 的对应关系

- `services/audit-and-isolation/` 现有 README.md —— 本 spec 不重写,**链接引为权威**
- `docs/architecture.md` §4.3 既有 audit/credential 段 —— 本 spec **只**增量 §4.3.Y PII 规则集段
- `docs/architecture.md` §4.4 技术栈 —— 已锁 Python 3.12 / FastAPI / asyncpg / Redis 7+ / K8s / Prometheus,**本 spec 不引入新 stack**
- eng-review #1(数据隔离网关 = egress 强制点)—— 主体已实现,本 spec 补周边
- eng-review #8(双层状态后端)—— D6 复用
- eng-review #9 / Quality #3(4 错误边界)—— security 边界的"凭证未授权"由 T11 错误边界实现,PII 拦截已由 audit-and-isolation 实现
- eng-review Perf #1(3 性能项)—— D7 + D8 contract 落地
- eng-review Perf #2 #1(780GB/3mo MinIO)—— D5 落地
- eng-review Test #1(3 层测试)—— D13 沿用

## Risks

- **R1:** 客户端 SDK 重试与现有 LLM 上游重试(1 次 5xx)叠加,可能放大请求数 → 缓解:SDK 重试仅对 `503 HA_FAILOVER` 与连接中断触发,非所有 5xx
- **R2:** 静态扫描漏掉动态 import(`importlib.import_module("openai")`)→ 缓解:扫描 CLI 同时扫 `__import__` / `getattr(__import__("openai"), ...)` 等 pattern,漏报率 < 5%
- **R3:** Redis 击穿阻塞 trace 查询 → 缓解:D6 明确 Redis 失败降级查 PG,db 0 与 canvas realtime db 1 隔离
- **R4:** 定时归档 MinIO 失败 → 缓解:归档任务支持断点续传,失败的 parquet 留在 PG 端,下次重试
- **R5:** 性能 contract 给出但实现留 T6 → T6 spec 必须在 apply 完成前出 proposal(沿用 design.md D7 接口签名)
- **R6:** 仓库已实现 80%,spec 与代码同源对齐需要 0 行重复代码 → 缓解:gap-analysis.md 已写明 25 task 标 done + 12 task 标 todo
- **R7:** 静态扫描误杀正当依赖 → CI 维护 allowlist,扫描器 `services/gateway-scanner/` 规则集可 PR 修改

## 跨 spec 依赖图

```
T1 (本 spec) ─┬─→ T4 测试架构 包含 2 实例 HA failover e2e
              ├─→ T5 4 critical path 中"网关 PII 拦截"已由 audit-and-isolation 实现
              ├─→ T6 性能优化 复用本 spec 留的 4 个 contract
              ├─→ T11 错误边界 security 边界 = audit-and-isolation 已实现的 PII
              └─→ T12 存储预估 校验 audit 780GB(本 spec 5 落地归档路径)
```

## Migration

不适用。本 spec 全部为新增 + 增量,**不动 audit-and-isolation 现有代码的 REQUIREMENTS**。

## Open Questions(交给 apply 阶段)

- **OQ1:** 静态扫描 CI 触发时机(只在 PR 触发 vs 每次 commit) → T1 spike task 验证
- **OQ2:** 归档任务的 cron 调度器(K8s CronJob vs 独立进程) → T1 spike task 验证 K8s CronJob
- **OQ3:** `Idempotency-Key` 的 hash 算法在跨调用方 SDK 的对齐(各 SDK 一致实现) → T1 spike task 验证
