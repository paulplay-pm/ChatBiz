## Why

eng-review 2026-06-10 锁定的 12 个工程决策中,#1 明确将"数据隔离网关 = egress 强制点"标为 P0 单点。仓库 `services/audit-and-isolation/` 已实现 egress 主体(OpenAI 兼容代理 + credential service auth + PII mask-only 可逆 + metadata-only 审计,2335 行 Python,alembic,Dockerfile,100% 覆盖率强制,eng-review Arch #1 引用)。本次 change **不再重建主体**,改为**补差**:在已有实现之上补 HA 拓扑(active-active + L4 LB + preStop 排空)、编译期静态扫描防御(LLM provider import 黑名单)、定时归档(eng-review Perf #2 锁定的 780GB/3mo MinIO 冷存储路径)、`/metrics` 端点暴露、`/v1/traces/{trace_id}` 跨实例查询、4 个 perf contract 桩,以及 `docs/architecture.md` §4.3.Y PII 规则集段落。MVP 2-3 月内让 paul 财务月报工作流跑通,补差完成后无审计空洞、无 HA 单点。

## What Changes

**服务与部署**
- From:`services/audit-and-isolation/` 单实例,无 K8s manifest
- To:补 `deploy/audit-and-isolation/`(Deployment replicas=2 + preStop 30s + terminationGracePeriodSeconds=45s + PodDisruptionBudget minAvailable=1)+ `deploy/audit-and-isolation/nginx.conf`(L4 LB,2 upstream,5s health check)+ `services/gateway-scanner/`(独立静态扫描 CLI,blocklist+allowlist+AST)
- Reason:补 HA 拓扑 + 编译期防御
- Impact:新增 `deploy/audit-and-isolation/` + `services/gateway-scanner/` + CI `gateway-static-scan` job

**HA 切换 + 客户端重试**
- From:无 HA,单实例崩溃 = 全部 LLM 调用挂
- To:2 实例 active-active + NGINX stream L4 LB + 客户端 SDK `RetryWithIdempotency` 装饰器(`Idempotency-Key` = SHA-256 of `user_id + body_hash + 5min_timestamp_bucket`,5s 内最多 3 次重试)
- Reason:eng-review #1 锁定 HA 拓扑,eng-review Failure modes 表标"Data isolation gateway down = CRITICAL"
- Impact:`services/workflow-engine/` `services/agent-runtime/` 等调用方 SDK 升级

**定时归档 + 冷查询**
- From:audit_log 表无 retention,无归档
- To:`services/audit-and-isolation/jobs/archive_audit.py` 每日 02:00 UTC 把超 90 天的行 COPY 到 MinIO `s3://chatbiz-audit-cold/yyyy/mm/dd.parquet`,PG 端 DELETE;新增 `GET /v1/audit/archive?from=...&to=...` 端点从 MinIO 拉 parquet,响应头 `X-Audit-Source: cold`
- Reason:eng-review Perf #2 #1 锁定 780GB/3mo MinIO 冷存储,当前无落点
- Impact:新增 cron job + MinIO bucket + 端点 + 测试

**trace 跨实例查询**
- From:`X-Trace-Id` 透传但无跨实例查询端点
- To:`services/audit-and-isolation/app/api/traces.py` 新增 `GET /v1/traces/{trace_id}` 端点,Redis(`trace:cache:*` namespace,db 0,5min TTL)优先 → PG `audit_log` 表降级 → 404
- Reason:eng-review #1 跨网关 trace-id 关联,eng-review #8 双层状态后端
- Impact:在 audit-and-isolation 内新增端点 + 缓存 + 单元/集成测试

**性能 contract + metrics 端点**
- From:`app/metrics.py` 有 Counter/Histogram 但端点未暴露
- To:暴露 `GET /metrics` Prometheus 端点(5 类指标:requests_total / duration_seconds / pii_hits / active_connections / trace_cache_hits);新增 4 个 perf contract Protocol(RateLimiter / ResponseCache / RequestBatcher / MetricsExporter)+ Noop 默认实现;主流程嵌入调用点,失败降级 Noop
- Reason:eng-review Perf #1 锁定的 3 性能项,contract 在本 spec 落,实现在 T6
- Impact:T6 spec 必须在 apply 完成前出 proposal,实现续接

**LLM 依赖黑名单 + 静态扫描**
- From:无编译期防御,直连 `openai` / `anthropic` import 可绕过
- To:`services/gateway-scanner/` CLI 扫 `services/*` + `libs/*` 目录 AST,匹配 `import` 与 `import ... as` 语句,违规退出码 1,CI job `gateway-static-scan` 阻止合入
- Reason:eng-review #1 egress 强制点需要编译期 + 运行期双层防御;运行期是 credential service 已有,编译期是本 spec 补
- Impact:CI 新增 job,`blocklist.yaml` + `allowlist.yaml` 维护入口

**docs §4.3.Y 补段**
- From:`docs/architecture.md` §4.3 已有 audit/credential 段,无 PII 规则集段
- To:在 §4.3 补 §4.3.Y PII 规则集段落(6 类正则 + 三档策略 + 可逆机制说明)
- Reason:eng-review #1 锁定 PII redaction 是 critical path,architecture 文档需同步
- Impact:`docs/architecture.md` 增量 1 段,**CLAUDE.md 同步 surface**

## Capabilities

### New Capabilities

- `gateway-llm-blacklist`:LLM provider import 黑名单静态扫描(独立 `services/gateway-scanner/` CLI + CI 集成)
- `gateway-ha-topology`:2 实例 active-active 拓扑(K8s manifest + NGINX L4 LB + preStop 排空 + 客户端 `RetryWithIdempotency`)
- `gateway-perf-contracts`:4 个 perf contract Protocol(RateLimiter / ResponseCache / RequestBatcher / MetricsExporter)+ Noop 默认实现 + `/metrics` 端点
- `gateway-trace-cross-instance-query`:`GET /v1/traces/{trace_id}` 端点(在 `services/audit-and-isolation/` 内新增,Redis cache + PG 降级)
- `audit-cold-archive`:90 天 PG 热 + 90 天后 MinIO 冷 + `GET /v1/audit/archive?from=...&to=...` 冷查询端点
- `docs-pii-rules-section`:`docs/architecture.md` §4.3.Y 增量段落(PII 规则集 + 三档策略 + 可逆机制)

### Modified Capabilities

无。已实现的 capability 不动其 REQUIREMENTS(本 spec 仅新增,不改既有 spec.md 任何文字)。

## Impact

- **新增代码:**
  - `services/gateway-scanner/`(独立 Python CLI,约 6 个文件:CLI 入口 / AST 扫描核心 / blocklist 解析 / allowlist 解析 / 报告输出 / 测试)
  - `services/audit-and-isolation/app/api/traces.py` + `app/api/audit_archive.py`(2 端点)
  - `services/audit-and-isolation/jobs/archive_audit.py`(定时归档)
  - `services/audit-and-isolation/app/perf/contracts.py`(4 个 Protocol + Noop)
  - `services/audit-and-isolation/alembic/versions/002_*.py`(trace_cache 表 + 索引,如需;现有 audit_log 表不动)
  - `deploy/audit-and-isolation/deployment.yaml` + `service.yaml` + `poddisruptionbudget.yaml` + `nginx.conf`
- **CI 变更:** GitHub Actions 新增 `gateway-static-scan` job
- **文档变更:** `docs/architecture.md` §4.3.Y 新增 PII 规则集段
- **依赖:** 新增 `services/gateway-scanner/pyproject.toml` 依赖 `pyyaml` + `click`(无 FastAPI / 无 DB 客户端,纯 CLI)
- **K8s:** Deployment + Service + PDB + ConfigMap + Secret(Vault 引用短期)
- **[FUTURE-IMPLEMENTATION]** 实际 4 个 perf contract 实现(eng-review Perf #1 锁定,留 T6)
- **[FUTURE-IMPLEMENTATION]** PII block 档 / log-only 档(本 spec 保留 mask-only,与现有兼容;eng-review Quality #3 security 边界的"凭证未授权"由 T11 实现)

## Non-goals

- **不**重建 `services/gateway/` —— 主体已由 `services/audit-and-isolation/` 实现
- **不**实现 PII block 档 / log-only 档 —— 与现有 mask-only 设计冲突,eng-review 未锁定
- **不**引入 HMAC `X-Gateway-Signature` 头 —— 现有用 `Authorization: Bearer <token>` + credential service,信任链已建立
- **不**实现 4 个 perf contract 实际实现 —— contract 在本 spec,实现在 T6
- **不**实现 `services/gateway-scanner/` 的 Python AST 高级优化(增量扫描、缓存) —— MVP 阶段全量扫
- **不**动 `docs/architecture.md` §4 既有段(只增量 §4.3.Y)
- **不**动 12 个 eng-review 决策中的任何其他 11 项
