# llm-egress-gateway Specification (Delta — NEW capability)

> 模式: superpowers-bridge
> 阶段: specs
> 类型: ADDED Requirements(全新 capability)
> 关联 proposal: `proposal.md` → New Capabilities → `llm-egress-gateway`
> 关联 design: `design.md` → 15 个 D 决策
> 日期: 2026-06-10
> 状态: [FUTURE-IMPLEMENTATION] — 仓库当前 0 行源代码,本 spec 触及 API/DB/前端

## ADDED Requirements

### Requirement: OpenAI-compatible 代理端点
系统 MUST 提供 OpenAI-compatible API(POST /v1/chat/completions、POST /v1/completions、GET /v1/models),接收标准 OpenAI 请求体,透传到上游 LLM provider。所有出站 LLM 调用 MUST 经本服务,作为 egress 强制点(eng-review Arch #1 锁定)。

#### Scenario: 标准 chat completions 调用
- **WHEN** 调用方发 POST /v1/chat/completions,body 含 `model: "qwen-max"`,`messages: [...]`
- **THEN** 系统 MUST:① 鉴权(svc token)② 取 X-Trace-Id / X-Model-Kind / X-Bypass-Isolation 头 ③ 查 model_routing 表拿到 upstream_base_url ④ 透传到 upstream ⑤ 写 audit_log ⑥ 返回 response 给调用方

#### Scenario: 未知模型
- **WHEN** 调用方请求 `model: "unknown-model"`
- **THEN** 系统 MUST 返 400 + 明确错误"model not found in routing table"

#### Scenario: body 超过 1MB
- **WHEN** 请求体 > 1MB
- **THEN** 系统 MUST 返 413 + 不继续处理

### Requirement: PII 自动检测与脱敏
系统 MUST 在透传前对 request body 中 6 类 PII 进行检测与脱敏:① 中国身份证(18 位 + 校验位)② 手机(11 位 1[3-9] 开头)③ 银行卡(16-19 位 Luhn 校验)④ 邮箱(RFC 5322 简化)⑤ 统一社会信用代码(18 位)⑥ 营收金额(中文风格)。每类命中 MUST 替换为 `[类型_xxxx]` 类型化占位符。

#### Scenario: prompt 含身份证
- **WHEN** request body 含 "客户 110101199001011234 投诉"
- **THEN** 系统 MUST 把身份证号替换为 `[身份证_a1b2]`;命中数写入 audit_log;脱敏 map 写 Redis (key=trace_id, TTL=1800s)

#### Scenario: prompt 含多类 PII
- **WHEN** request body 含 "张三 13800138000 邮箱 zhang@example.com"
- **THEN** 系统 MUST 同时把手机替换为 `[手机_b3c4]`、邮箱替换为 `[邮箱_d5e6]`;audit_log 记 `pii_detected_types=["mobile","email"], pii_redacted_count=2`

#### Scenario: 命中位数不足的边界
- **WHEN** request body 含 "010-12345"(5 位业务号,非手机)
- **THEN** 系统 MUST NOT 命中手机规则(位数不足);audit 不记录 mobile 命中

#### Scenario: detector 内部异常(Fail-Open)
- **WHEN** PII detector 抛 RuntimeException(eg. 正则库 corrupt)
- **THEN** 系统 MUST:① 不阻断 ② 放行原文本到上游 ③ audit_log 记 `error_class="PIIDetectorUnavailable"` + WARN level ④ metric counter `pii_detector_fail_open_total++` ⑤ 触发 PagerDuty 告警

### Requirement: 脱敏可逆(响应侧还原)
系统 MUST 在拿到上游 LLM response 后,按 Redis 中的脱敏 map(Per-Trace, TTL 30min)反向替换占位符为原值,然后返回给调用方。同一 trace 多次调用共享同一 map。

#### Scenario: response 含占位符
- **WHEN** 上游 LLM 返回 "客户 [身份证_a1b2] 投诉已记录"
- **THEN** 系统 MUST 查 Redis 拿 trace 对应 map,把 `[身份证_a1b2]` 替换为原值 "110101199001011234"

#### Scenario: 跨调用占位符一致
- **WHEN** 同一 trace 调 LLM 第一次返回 "[身份证_a1b2]",第二次返回 "就是 [身份证_a1b2] 那位客户"
- **THEN** 系统 MUST 两次都还原为 "110101199001011234",占位符前后一致

#### Scenario: map 过期
- **WHEN** trace 已结束超过 30min(TTL 过期)
- **THEN** 系统 MUST NOT 还原(占位符原样返回);audit 不记错误(过期是预期行为)

### Requirement: 跨服务 trace-id 关联
调用方 MUST 在请求头传 `X-Trace-Id`(MVP 强制,缺失返 422)。系统 MUST:① 把 trace_id 写入 audit_log ② 透传到上游 LLM provider 的 header ③ Redis 脱敏 map 用 trace_id 作 key。eng-review Arch #1 锁定。

#### Scenario: trace_id 缺失
- **WHEN** 请求头无 X-Trace-Id
- **THEN** 系统 MUST 返 422 + 明确错误"X-Trace-Id header is required"

#### Scenario: trace_id 格式错误
- **WHEN** X-Trace-Id 长度 < 8 或 > 128 字符
- **THEN** 系统 MUST 返 422 + 明确错误"X-Trace-Id format invalid"

#### Scenario: trace_id 透传上游
- **WHEN** 请求 X-Trace-Id = "01HX..."
- **THEN** 上游 LLM provider 的请求头 MUST 包含 `X-Trace-Id: 01HX...`

### Requirement: 2 实例 HA(active-active)
系统 MUST 至少部署 2 个实例,前面挂 L4 LB;任一实例 healthcheck fail MUST 30s 内被踢出,流量切到其他健康实例。eng-review Arch #1 锁定。

#### Scenario: 单实例故障
- **WHEN** 实例 A 进程崩溃
- **THEN** K8s healthcheck MUST 30s 内把 A 标记 unhealthy;LB 流量 MUST 切到 B;调用方无感知;audit 不记错误(HA 是预期)

#### Scenario: 双实例同时故障
- **WHEN** A 和 B 都不可用
- **THEN** 系统 MUST 返 503 给调用方;monitoring 触发 P0 告警(eng-review 锁定 P0);audit_log 记 `error_class="GatewayUnavailable"`

#### Scenario: 跨实例 trace 一致性
- **WHEN** 同一 trace 的 map 在实例 A 写入 Redis,后续请求路由到实例 B
- **THEN** 实例 B MUST 能从 Redis 拉到 map,正常做反向还原(Redis 共享状态)

### Requirement: Metadata-Only 审计
系统 MUST 对每条 LLM 调用写 audit_log(Metadata-Only,14 字段):`trace_id, user_id, workflow_id, model, model_kind, bypass_isolation, pii_detected_types[], pii_redacted_count, prompt_hash(SHA-256), token_input, token_output, latency_ms, upstream_status, error_class`。明文 prompt / response MUST NOT 入库。

#### Scenario: 正常调用写入
- **WHEN** 一次 LLM 调用完成,latency=420ms,token_in=240,token_out=180,status=200
- **THEN** audit_log MUST 含完整 14 字段;prompt_hash 是脱敏后 prompt 的 SHA-256

#### Scenario: 失败调用写入
- **WHEN** 上游 LLM 5xx,1 次重试仍失败
- **THEN** audit_log MUST 记 `upstream_status=502, error_class="Upstream5xx"`,latency 含重试时间

#### Scenario: prompt 明文未入库(安全用例)
- **WHEN** 任意调用完成
- **THEN** audit_log 表 MUST NOT 含原始 prompt 文本(grep "110101" 在 audit_log 必须为 0 行)

#### Scenario: prompt_hash 一致性
- **WHEN** 同 prompt 两次调用,脱敏规则不变
- **THEN** 两次 prompt_hash MUST 相等(SHA-256 确定性)

### Requirement: 模型路由透传 + Bypass 机制
调用方 MUST 在请求头声明 `X-Model-Kind: public|private`。当 `X-Model-Kind=private` 时,可声明 `X-Bypass-Isolation: true` 跳过 PII 脱敏。系统 MUST 按 header 决定脱敏路径 + 路由表 base_url。模型选择权在调用方(body.model),系统不参与决策。

#### Scenario: 公有模型 + 走脱敏
- **WHEN** 请求 `X-Model-Kind: public, body.model: "qwen-max"`
- **THEN** 系统 MUST 走 PII 脱敏 + 透传到 model_routing 表中 qwen-max 对应的 public upstream

#### Scenario: 私有模型 + 走脱敏
- **WHEN** 请求 `X-Model-Kind: private, body.model: "internal-vllm-qwen"`
- **THEN** 系统 MUST 走 PII 脱敏 + 透传到 model_routing 表中 internal-vllm-qwen 对应的 private upstream

#### Scenario: 私有模型 + Bypass 跳过脱敏
- **WHEN** 请求 `X-Model-Kind: private, X-Bypass-Isolation: true`
- **THEN** 系统 MUST 跳过 PII 脱敏 + 透传到 private upstream;audit_log 记 `bypass_isolation=true, pii_redacted_count=0`

#### Scenario: Bypass 但 Model-Kind=public
- **WHEN** 请求 `X-Model-Kind: public, X-Bypass-Isolation: true`
- **THEN** 系统 MUST 忽略 Bypass 头(仅 private + Bypass 才生效);audit 记 `bypass_isolation=false`

#### Scenario: Model-Kind 缺失
- **WHEN** 请求头无 X-Model-Kind
- **THEN** 系统 MUST 返 422 + 明确错误"X-Model-Kind header is required"

### Requirement: 限流计数(不限流)
系统 MUST 对每条请求按 (user_id, hour) 维度记 audit 计数,但 MUST NOT 主动阻断。eng-review Perf #1 锁定"3 个性能优化"中限流降级为"只计数"。真正 quota 由上游 LLM provider 控制。

#### Scenario: 单用户高频调用不阻断
- **WHEN** 同一 user_id 1 分钟内 100 次 LLM 调用
- **THEN** 系统 MUST 全部 100 次都正常处理(不限流);audit 记 100 条

### Requirement: Redis 模型路由表缓存
系统 MUST 在启动时从 PostgreSQL `model_routing` 表加载所有启用的路由到 Redis(TTL 60s)。每次请求先查 Redis,未命中则回源 PG 并刷新缓存。

#### Scenario: 启动时加载
- **WHEN** 实例启动
- **THEN** 启动日志 MUST 打印 "loaded N routing entries from PG";Redis MUST 含 N 个 key

#### Scenario: 缓存命中
- **WHEN** 第一次请求 `model: "qwen-max"`
- **THEN** 系统 MUST 从 Redis 拿 upstream_base_url(避免 SQL);latency < 1ms

#### Scenario: 缓存过期回源
- **WHEN** Redis 路由表 key 过期(60s)
- **THEN** 下次请求 MUST 回源 PG 查 model_routing;刷新 Redis TTL;不阻断请求

#### Scenario: Redis 不可达
- **WHEN** Redis 客户端连接失败
- **THEN** 系统 MUST 降级用启动时载入的内存路由表 copy;audit 记 WARN + 触发告警;不阻断请求

### Requirement: 调用 credential service 拿 LLM API Key
系统 MUST 持有 service token 调 credential service 的 `use_credential` API 拿 LLM provider 的 API Key,缓存 5min。eng-review 已锁定 credential service。

#### Scenario: 正常拿到 API Key
- **WHEN** 调 qwen provider
- **THEN** 系统 MUST 先调 credential service 拿 qwen API Key(已存于 credential service);用此 key 调 dashscope.aliyuncs.com

#### Scenario: credential service 不可达
- **WHEN** 调 credential service 超时或 5xx
- **THEN** 系统 MUST 1 次重试 + 仍失败 → 返 503;audit 记 `error_class="CredentialServiceUnavailable"` + 告警

#### Scenario: API Key 缓存 5min
- **WHEN** 同一 provider 1 分钟内 100 次调用
- **THEN** 系统 MUST 只调 1 次 credential service,后续 99 次用缓存(避免每次解密)

### Requirement: 错误处理 4 边界(eng-review Quality #3 锁定)
系统 MUST 处理 4 类错误边界:① security(未授权凭证访问)② user(参数不全)③ runtime(LLM 5xx/timeout/限额)④ canvas drag-loop N/A(本服务不涉及)。

#### Scenario: security — service token 无效
- **WHEN** 请求头无 / 错误 service token
- **THEN** 系统 MUST 返 401 + 写 audit `error_class="AuthFailed"` + 不继续处理(Fail-Closed on auth)

#### Scenario: user — body 解析失败
- **WHEN** request body 不是合法 JSON
- **THEN** 系统 MUST 返 422 + 详细 Pydantic 错误 + 不写 audit

#### Scenario: user — trace_id 缺失(已覆盖 D6 spec,此 scenario 引用)

#### Scenario: runtime — 上游 LLM 5xx
- **WHEN** 上游 LLM 返 5xx
- **THEN** 系统 MUST 1 次重试(指数退避 200ms)+ 仍失败 → 返 502 + audit `error_class="Upstream5xx"`

#### Scenario: runtime — 上游 LLM timeout
- **WHEN** 上游 LLM > 30s 无响应
- **THEN** 系统 MUST 取消请求 + 返 504 + audit `error_class="UpstreamTimeout"`

#### Scenario: runtime — 上游 LLM 429
- **WHEN** 上游 LLM 返 429(quota 用尽)
- **THEN** 系统 MUST 透传 429 给调用方 + audit 记 `error_class="UpstreamRateLimited"`(不重试,业务应减少调用)

#### Scenario: runtime — Redis 不可达(已覆盖 D11 spec)

### Requirement: 性能预算 — P99 网关层 < 50ms
系统 MUST 在 100 RPS × 60s 压测下,网关层(不含上游 LLM 响应)P99 延迟 < 50ms(eng-review Perf #1 P99 < 500ms 是端到端,本服务 P99 < 50ms 是网关内部水位)。perf bench 脚本必跑,失败阻断 release。

#### Scenario: 100 RPS × 60s 压测
- **WHEN** perf bench 发 100 RPS 持续 60s(用假 LLM mock,网络延迟 < 1ms)
- **THEN** 网关层 P99 latency MUST < 50ms;失败率 MUST < 0.1%;超限 MUST 阻断 release

#### Scenario: 假 LLM 延迟 200ms 不计入网关层
- **WHEN** 上游 LLM 返 200ms
- **THEN** 网关层延迟 = httpx 透传 + PII 扫描 + audit 写;不包含 LLM thinking time

### Requirement: 健康检查端点
系统 MUST 暴露 `GET /healthz`(liveness)和 `GET /readyz`(readiness),K8s 用以判定实例健康。

#### Scenario: liveness
- **WHEN** GET /healthz
- **THEN** 系统 MUST 返 200 + JSON `{"status":"ok"}`(永远 200,只要进程活着)

#### Scenario: readiness
- **WHEN** GET /readyz
- **THEN** 系统 MUST 检查:① PG 可连 ② Redis 可连 ③ credential service 可达 ④ 启动时路由表已加载;全 OK → 200;任一失败 → 503

### Requirement: 4 critical path 100% 覆盖(eng-review Test #2)
本服务 = 4 critical path 中的 #2 "数据隔离网关 PII 拦截"。测试 MUST 100% 覆盖 8 个子场景。

#### Scenario: PII 拦截子场景 2.1 — 身份证脱敏 + 还原
- **WHEN** e2e 测试:调用方发含身份证的 prompt → 假 LLM 返回含占位符的 response
- **THEN** 测试 MUST 验证:① 脱敏后 prompt 不含原身份证 ② response 还原后含原身份证 ③ audit_log 记 pii_detected_types=["id_card"]

#### Scenario: PII 拦截子场景 2.2 — 手机/银行卡边界
- **WHEN** 测试发"010-12345"(5 位业务号)+ 真实手机号 13800138000
- **THEN** 测试 MUST 验证:① 业务号未命中 ② 手机号被脱敏

#### Scenario: PII 拦截子场景 2.3 — 邮箱/信用代码/营收
- **WHEN** 测试发邮箱 + 18 位统一社会信用代码 + "营收 1,234,567.89 元"
- **THEN** 测试 MUST 验证:3 类全部脱敏

#### Scenario: PII 拦截子场景 2.4 — 响应侧还原
- **WHEN** 同 trace 2 次 LLM 调用,response 都含占位符
- **THEN** 测试 MUST 验证:2 次都还原为同一原值

#### Scenario: PII 拦截子场景 2.5 — Fail-Open
- **WHEN** PII detector 抛异常(monkey-patch)
- **THEN** 测试 MUST 验证:① 请求 200(不阻断)② 原文本到上游 ③ audit 记 PIIDetectorUnavailable

#### Scenario: PII 拦截子场景 2.6 — 上游 timeout
- **WHEN** 假 LLM mock 30s+ 不响应
- **THEN** 测试 MUST 验证:① 返 504 ② audit 记 UpstreamTimeout

#### Scenario: PII 拦截子场景 2.7 — credential down
- **WHEN** credential service mock 不可达
- **THEN** 测试 MUST 验证:① 返 503 ② audit 记 CredentialServiceUnavailable

#### Scenario: PII 拦截子场景 2.8 — trace 跨实例
- **WHEN** 实例 A 处理后 Redis 写入 map,实例 B 收到同 trace 后续请求
- **THEN** 测试 MUST 验证:实例 B 能从 Redis 拉 map 还原

### Requirement: 凭证 / 密钥安全(对齐 CLAUDE.md 全局约束)
主密钥 / 凭证明文 MUST NOT 入 commit / log / audit / 测试 fixture;LLM provider API Key MUST NOT 出现在源码或环境变量中(通过 credential service 拿)。

#### Scenario: API Key 不在源码(安全用例)
- **WHEN** grep `app|tests` 目录搜 "api[_-]key.*=.*['\"]"(包含明文 API key)
- **THEN** MUST 0 行命中

#### Scenario: API Key 不在 audit_log
- **WHEN** 任何 LLM 调用完成
- **THEN** audit_log MUST NOT 含 LLM provider 的 API Key

#### Scenario: 凭证走 credential service
- **WHEN** 本服务需调 LLM provider
- **THEN** MUST 调 credential service 的 use_credential API 拿 Key;不允许从 env / config 读明文
