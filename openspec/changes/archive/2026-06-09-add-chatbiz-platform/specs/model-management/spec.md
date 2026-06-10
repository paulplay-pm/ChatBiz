# model-management

> **eng-review refs:** [ENG-Perf #1]
> **depends on:** [credential-management], [audit-and-isolation], [monitoring]
> **source:** `docs/prd.md` §4.5

## ADDED Requirements

### Requirement: 模型配置
系统 MUST 支持多种 LLM 模型的配置(OpenAI / Claude / DeepSeek / 文心 / 通义);每模型含 api_endpoint / api_key(引用 credential) / 默认参数(温度 / top-p / max-tokens)。

#### Scenario: 添加模型
- **WHEN** 用户配置新模型(如 "GPT-4o"),填入 endpoint + 选择已存储的 credential
- **THEN** 系统 MUST 持久化模型配置,api_key 引用 credential-management(明文不存)

#### Scenario: 模型连通性测试
- **WHEN** 用户保存模型配置
- **THEN** 系统 MUST 发送测试请求(1 token 最小调用)验证凭证 + endpoint 可用;失败 MUST 提示具体错误(401 / network / rate limit)

### Requirement: 模型路由
系统 MUST 支持按 workflow / agent 配置选择模型;支持 fallback(主模型失败自动切到 fallback 模型)。

#### Scenario: 静态路由
- **WHEN** workflow 配置 model = "GPT-4o"
- **THEN** 系统 MUST 所有该 workflow 的 LLM 调用都路由到 GPT-4o

#### Scenario: 动态 fallback
- **WHEN** workflow 配置 primary = "GPT-4o" / fallback = "Claude-Sonnet"
- **THEN** 系统 MUST 在 GPT-4o 调用失败(5xx / timeout / rate limit)时自动切到 Claude-Sonnet,重试 1 次;失败 MUST 标记 workflow 节点 failed,audit log 记录切换

### Requirement: 限流与配额
系统 MUST 支持 per-user / per-workflow 的 RPM / TPM 限流(eng-review [ENG-Perf #1]);超限 MUST 排队或拒绝。

#### Scenario: 超限排队
- **WHEN** 用户在 1 分钟内发起 100 个 LLM 调用,超过 quota (默认 60 RPM)
- **THEN** 系统 MUST 把超出部分排队(等待 ≤ 30s);若等待超时 MUST 拒绝并提示用户

### Requirement: 用量统计
系统 MUST 记录每次模型调用的 token 用量(输入 / 输出) + 成本(若有) + 时长;支持按时间 / 用户 / workflow 维度查询。

#### Scenario: 月度用量报表
- **WHEN** 用户打开用量面板,选择时间范围(本月)
- **THEN** 系统 MUST 显示:总调用次数、总 token、总成本(若有)、按模型拆分、按 workflow 拆分、按用户拆分;查询响应 < 2s

### Requirement: 模型调用经网关
所有 LLM 调用 MUST 经过数据隔离网关 ([ENG-Arch #1]);网关 MUST 在调用前后执行 PII 脱敏 + 审计 + 凭证校验。

#### Scenario: 调 OpenAI
- **WHEN** workflow 调 "GPT-4o" 模型
- **THEN** 系统 MUST:① 网关验证凭证(从 credential-management 取) ② 网关对 prompt 文本执行 PII 脱敏(身份证 / 手机号 / 邮箱) ③ 网关调用 OpenAI ④ 网关对 response 反向脱敏(还原 PII) ⑤ audit log 记录完整调用(输入、输出、token、cost、trace-id)
