# audit-and-isolation Specification

## Purpose
TBD - created by archiving change add-chatbiz-platform. Update Purpose after archive.
## Requirements
### Requirement: 数据隔离网关 (egress 强制点)
系统 MUST 在 API Gateway 与外部 LLM API 之间部署数据隔离网关;所有出站 LLM 请求 MUST 经此。网关 = egress 强制点,不是 ingress。

#### Scenario: LLM 调用经网关
- **WHEN** workflow 或 agent 调 LLM API
- **THEN** 系统 MUST:① 路由调用经数据隔离网关 ② 网关验证凭证(从 credential-management) ③ 网关对 prompt 文本执行 PII 脱敏(身份证 / 手机号 / 邮箱 / 银行卡) ④ 网关调用外部 LLM ⑤ 网关对 response 反向脱敏(还原 PII) ⑥ audit log 记录完整调用 ⑦ trace-id 关联

#### Scenario: 网关失败阻断
- **WHEN** 网关不可用(进程崩溃、网络分区)
- **THEN** 系统 MUST 阻断所有 LLM 调用,workflow 节点标记 failed;用户 MUST 看到明确错误"网关不可用"

### Requirement: 网关高可用
网关 MUST 至少 2 实例 + 健康检查;1 实例故障 MUST 自动 failover。

#### Scenario: 实例故障
- **WHEN** 网关实例 1 崩溃
- **THEN** 系统 MUST 在 5s 内把流量切到实例 2;用户无感知;audit log 记录实例切换

#### Scenario: 双实例同时故障
- **WHEN** 网关 2 实例都不可用
- **THEN** 系统 MUST 阻断所有 LLM 调用;monitoring 触发 P0 告警

### Requirement: PII 脱敏
网关 MUST 对出站 prompt 中的 PII 自动检测并脱敏;对入站 response 中的 PII 还原;脱敏规则可配置。

#### Scenario: prompt 含身份证
- **WHEN** prompt 文本含 "张三 110101199001011234"
- **THEN** 网关 MUST 把身份证号替换为 "[REDACTED-ID-1]";response 含相同 ID 时 MUST 还原为 "110101199001011234"

#### Scenario: 脱敏不可逆
- **WHEN** 脱敏算法无法识别 PII(如自定义格式)
- **THEN** 网关 MUST 标记为 unredacted + 警告用户;不静默通过

### Requirement: 审计日志
系统 MUST 完整记录所有 LLM 调用 + 凭证访问 + 权限变更 + 异常;日志含 prompt/response/凭证 ID hash/token/cost/trace-id/时间/用户/cap。

#### Scenario: 完整审计
- **WHEN** 任何 LLM 调用完成
- **THEN** 系统 MUST 写入 audit log(append-only,不可修改):user_id, cap, workflow_id, prompt_hash, response_hash, model, input_tokens, output_tokens, cost, latency_ms, trace_id, pii_redacted_count, timestamp;明文 prompt/response 完整记录(用于合规审计)

#### Scenario: 审计查询
- **WHEN** 管理员按用户 + 时间范围查询审计
- **THEN** 系统 MUST 返回完整调用记录(包含 prompt / response);响应 < 2s

### Requirement: 跨网关 trace 关联
每次 LLM 调用 MUST 带 trace-id,跨 网关 + workflow + agent + LLM API 全程关联;用于故障排查。

#### Scenario: 故障排查
- **WHEN** workflow 执行失败,管理员用 trace-id 查询
- **THEN** 系统 MUST 返回该 trace-id 关联的所有日志(网关进入、网关出去、workflow 节点、agent 推理、LLM 调用)

### Requirement: 错误处理 4 边界 [ENG-Quality #3]
系统 MUST 处理 4 类错误边界:① canvas drag-loop ② runtime(LLM 5xx / timeout / 限额)③ user(参数不全 / 变量未定义)④ security(未授权凭证)。

#### Scenario: canvas drag-loop
- **WHEN** 用户在画布上画了一个循环(A → B → A)
- **THEN** 系统 MUST 在保存前检测并拒绝,提示"工作流存在循环,请使用条件分支或循环节点而非物理循环"

#### Scenario: LLM 5xx
- **WHEN** LLM API 返回 5xx
- **THEN** 系统 MUST 按 retry 策略重试(默认 2 次,指数退避);最终失败 MUST 标记 workflow 节点 failed,audit log 记录

#### Scenario: 用户参数不全
- **WHEN** workflow 节点配置缺少必填参数(如 LLM 节点未指定 model)
- **THEN** 系统 MUST 在画布上显示"未配置"标记,阻止 workflow 运行;不允许保存为可执行状态

#### Scenario: 未授权凭证访问
- **WHEN** workflow 试图用未授权的凭证(如 workflow 创建者无权限访问该凭证)
- **THEN** 系统 MUST 在 workflow 配置时拒绝,在执行时阻断 + audit log 记录未授权访问

### Requirement: 缓存 + 限流 + 批处理 [ENG-Perf #1]
网关 MUST 实现 3 个性能优化:① 缓存(prompt 模板 / 凭证 / 路由表)② 限流(per-user / per-workflow 配额)③ 批处理(独立 workflow 合并到 batch 调用)。

#### Scenario: 凭证缓存
- **WHEN** 同一 workflow 在 1 分钟内 100 次 LLM 调用
- **THEN** 网关 MUST 缓存凭证(避免每次解密);命中凭证缓存 MUST 跳过 decryption 步骤

#### Scenario: 限流
- **WHEN** 用户在 1 分钟内 100 个调用,超过 quota (默认 60 RPM)
- **THEN** 网关 MUST 排队(≤ 30s)或拒绝;超限 MUST 写 audit log

#### Scenario: 批处理
- **WHEN** 10 个独立 workflow 在 1s 内同时调 LLM
- **THEN** 网关 MUST 合并为 batch 调用(如果 LLM provider 支持);降低出站连接数

### Requirement: 网关性能 [ENG-Perf #1]
网关 MUST 保证 P99 延迟 < 500ms(100 RPS 压测下)。

#### Scenario: 100 RPS 压测
- **WHEN** 系统在 100 RPS 持续压力下
- **THEN** 网关 P99 延迟 MUST < 500ms;超限 MUST 触发 monitoring 告警

### Requirement: 4 critical path 测试 [ENG-Test #2]
系统 MUST 提供 4 个 critical path 的 100% 覆盖测试,paul 财务月报 e2e / 网关 PII 拦截 / 人工审批中断续接 / 插件降级。

#### Scenario: 4 critical path 必过
- **WHEN** 测试套件运行
- **THEN** 4 critical path MUST 100% 通过;任何失败 MUST 阻断 release

### Requirement: 可运维端点覆盖
数据隔离网关 MUST 对 `/healthz`、`/readyz` 和 `/v1/models` 提供自动化测试，覆盖成功与依赖失败路径，支撑 eng-review #1 的 HA 与健康检查要求。

#### Scenario: healthz liveness
- **WHEN** 测试调用 `GET /healthz`
- **THEN** 系统 MUST 返回 200 与 JSON `{"status":"ok"}`，且不访问 PostgreSQL、Redis 或 credential service

#### Scenario: readyz 全部依赖可用
- **WHEN** PostgreSQL、Redis、credential service 与内存 routing table 均可用
- **THEN** `GET /readyz` MUST 返回 200，并在 checks 中标记 `postgres`、`redis`、`credential_service`、`routing_table` 为 `ok`

#### Scenario: readyz 任一依赖失败
- **WHEN** PostgreSQL、Redis、credential service 任一检查抛异常或 routing table 为空
- **THEN** `GET /readyz` MUST 返回 503，并在 JSON body 中标出失败依赖

#### Scenario: models 只返回启用路由
- **WHEN** `model_routing` 表包含 enabled 与 disabled 模型
- **THEN** `GET /v1/models` MUST 只返回 enabled 模型，且 MUST NOT 暴露 upstream base_url/path/API key

### Requirement: 生命周期与基础设施封装覆盖
数据隔离网关 MUST 对 FastAPI lifespan、SQLAlchemy lazy engine/session、Redis pool factory 与 dispose/reset 路径提供自动化测试。

#### Scenario: lifespan startup/shutdown
- **WHEN** FastAPI lifespan 启动并关闭
- **THEN** 系统 MUST 尝试加载 routing table，MUST 启动 audit outbox，关闭时 MUST stop outbox 并 dispose SQLAlchemy engine

#### Scenario: routing load 失败仍启动
- **WHEN** startup 阶段 routing table load 抛异常
- **THEN** lifespan MUST 记录 warning 并继续启动，后续请求通过空路由表失败而不是进程崩溃

#### Scenario: database session 成功与异常
- **WHEN** `get_session()` 正常 yield 或内部抛异常
- **THEN** 测试 MUST 验证 session factory lazy init、正常关闭、异常传播与 dispose 行为

#### Scenario: Redis pool 复用
- **WHEN** 多次调用 `get_redis()`
- **THEN** Redis connection pool MUST lazy 初始化并复用；测试 MUST 覆盖 reset/dispose 类测试辅助路径

### Requirement: LLM schema 与 streaming helper 覆盖
数据隔离网关 MUST 对 OpenAI-shaped Pydantic models 与 streaming reverse helper 提供自动化测试，确保 SDK 兼容路径不因未覆盖而回退。

#### Scenario: LLM request/response schema
- **WHEN** 测试构造 chat completion request、message、choice、usage 与 response
- **THEN** Pydantic schema MUST 验证默认值、字段约束、role/content 类型与 token usage 字段

#### Scenario: streaming reverse
- **WHEN** 上游 streaming chunks 含占位符或空 chunk
- **THEN** streaming helper MUST 对非空 chunk 调用 reverse 并 yield，MUST 跳过或正确处理空 chunk

#### Scenario: buffer and reverse
- **WHEN** 上游 async iterator 返回多个 chunks
- **THEN** buffer helper MUST 拼接完整文本并按 trace_id 做一次 reverse，还原后的字符串 MUST 返回给调用方

### Requirement: 产品修复与 pragma 透明记录
本 change 中任何产品代码修复或 `# pragma: no cover` MUST 在 `verify.md` 中逐项记录，说明触发测试、变更原因、风险与后续计划。

#### Scenario: 产品代码修复记录
- **WHEN** 实现改动 `app/**/*.py`
- **THEN** `verify.md` MUST 列出文件、变更摘要、关联测试与是否改变外部行为

#### Scenario: pragma 记录
- **WHEN** 实现新增 `# pragma: no cover`
- **THEN** `verify.md` MUST 说明该分支为什么真实控制流不可达，以及为什么不使用 artificial test

