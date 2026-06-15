# gateway-perf-contracts Specification

## Purpose
TBD - created by archiving change gateway-egress-enforcement-p0. Update Purpose after archive.
## Requirements
### Requirement: 必须暴露 4 个 perf contract Protocol (MUST)
(MUST)
`services/audit-and-isolation/app/perf/contracts.py` 必须定义 4 个 Protocol / ABC:`RateLimiter.check(user_id: str, model: str) -> bool` / `ResponseCache.get(request_hash: str) -> Optional[CachedResponse]` + `put(request_hash, response, ttl)` / `RequestBatcher.submit(request) -> Future[response]` / `MetricsExporter`(Protocol 或 ABC),每个 Protocol 必须有 1 个 Noop 默认实现类。

#### Scenario: 接口签名稳定
- **WHEN** T6 性能优化 spec 开始实现
- **THEN** 4 个 Protocol 必须已存在且签名稳定,Noop 默认实现可被替换

#### Scenario: Noop 行为
- **WHEN** Noop RateLimiter.check() 被调用
- **THEN** 始终返回 True;Noop ResponseCache.get() 返回 None,put() 接收即丢弃;Noop RequestBatcher.submit() 立即同步调用 LLM;Noop MetricsExporter 接受 metric 但不导出

### Requirement: 必须暴露 `/metrics` Prometheus 端点 (MUST)
(MUST)
`services/audit-and-isolation/app/api/metrics.py` 必须实现 `GET /metrics` 端点,Prometheus exposition format,5 类指标:`chatbiz_gateway_requests_total{method,path,status}` / `chatbiz_gateway_request_duration_seconds_bucket{le,...}` / `chatbiz_gateway_pii_hits_total{pii_type,action}` / `chatbiz_gateway_active_connections` / `chatbiz_gateway_trace_cache_hits_total`。每个指标必须有 HELP + TYPE 注释。

#### Scenario: 指标暴露
- **WHEN** Prometheus scraper 拉取 `/metrics`
- **THEN** 端点返回 200 + `text/plain; version=0.0.4` 内容,包含 5 类指标的最新样本值

#### Scenario: 指标更新
- **WHEN** 网关处理 1 条 LLM 请求(PII mask 1 次,耗时 200ms,HTTP 200)
- **THEN** `/metrics` 在下次拉取时反映:requests_total{status="200"} +1,pii_hits_total{action="mask"} +1,duration_seconds_bucket +1

### Requirement: 主流程必须嵌入 4 个 contract 调用点,失败降级 Noop (MUST)
(MUST)
`services/audit-and-isolation/app/api/chat.py` 主流程必须在限流 → 缓存 → 批处理 → 指标 4 个位置调用 contract,contract 抛出异常时降级到 Noop,**不**阻塞 LLM 调用主流程。

#### Scenario: Noop 路径可跑通完整 e2e
- **WHEN** 4 个 contract 全部是 Noop 实现
- **THEN** 完整 e2e(audit-and-isolation 现有 4 scenarios)必须全部通过,证明 Noop 降级路径不影响主流程

#### Scenario: contract 异常降级
- **WHEN** `RateLimiter.check()` 抛出异常(假设 T6 实现的真 RateLimiter)
- **THEN** 主流程捕获异常,降级到 Noop 行为(返回 True),记录 `contract_degraded{contract="rate_limiter"}` 指标,继续处理请求

#### Scenario: 限流触发
- **WHEN** `RateLimiter.check()` 返回 False(T6 实现的真限流)
- **THEN** 网关返回 HTTP 429,响应体 `{"error": "rate_limited", "retry_after": N}`,不调用 LLM provider

#### Scenario: 缓存命中
- **WHEN** `ResponseCache.get(request_hash)` 返回 CachedResponse(T6 实现的真缓存)
- **THEN** 网关跳过 LLM provider 调用,直接返回缓存响应,PII 扫描必须对缓存响应同样执行

### Requirement: 批量响应必须正确分发到 Future (MUST)
(MUST)
`RequestBatcher.submit()` 返回 `Future[response]`,T6 实现的真批处理可能合并 3 条请求为 1 次 LLM 调用并返回 3 条响应,网关必须将 3 条响应分别 dispatch 到对应的 Future。

#### Scenario: 批量合并
- **WHEN** 3 个并发请求被 RequestBatcher 合并为 1 次 LLM 调用,响应包含 3 个 choices
- **THEN** 网关必须将 3 个 choices 分别 dispatch 到 3 个 Future 持有者,各 Future 按独立请求继续处理(写 audit / PII reverse / 响应)

[FUTURE-IMPLEMENTATION] 本 spec 处于 pre-build 增量阶段,`app/perf/contracts.py` + `app/api/metrics.py` + chat.py 集成改动在 apply 阶段落地。**4 个 contract 实际实现(真限流 / 真缓存 / 真批处理)在 T6 spec 实现**,本 spec 只交付接口与 Noop 默认实现 + `/metrics` 端点。eng-review Perf #1 锁定的"实际性能优化"由 T6 续接。

