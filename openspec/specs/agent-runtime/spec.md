# agent-runtime Specification

## Purpose
TBD - created by archiving change add-chatbiz-platform. Update Purpose after archive.
## Requirements
### Requirement: Agent 列表
系统 MUST 提供 Agent 列表视图,展示 Agent 名称、类型、版本、最近运行时间;支持搜索、筛选、创建新 Agent。

#### Scenario: 列表加载
- **WHEN** 用户打开 Agent 列表
- **THEN** 系统 MUST 渲染 Agent 卡片,显示名称、类型(Lead / Sub)、版本、最近运行时间;加载时间 < 1s

### Requirement: Lead Agent + Sub Agent 委派
系统 MUST 支持 Lead Agent 委派子任务给 Sub Agent,Sub Agent 完成返回结果给 Lead Agent;委派通过 LangGraph StateGraph 的 node 边定义。

#### Scenario: 单层委派
- **WHEN** Lead Agent 推理决定调用 Sub Agent "数据查询"
- **THEN** 系统 MUST 把 Sub Agent 作为 LangGraph 节点调用,传入上下文参数,Sub Agent 完成返回结果给 Lead Agent 继续推理

#### Scenario: 多层委派
- **WHEN** Lead Agent 委派给 Sub Agent A,A 又委派给 Sub Agent B
- **THEN** 系统 MUST 支持任意深度的委派链;每层 Sub Agent 的状态 MUST 独立持久化(防止链路中一环失败整链崩)

### Requirement: Agent 配置
系统 MUST 支持 Agent 的 system prompt / 工具集 / 技能集 / 模型选择 / 温度 / top-p / max-tokens / 工具调用策略的配置。

#### Scenario: 配置变更
- **WHEN** 用户修改 Agent 的 system prompt 或模型
- **THEN** 系统 MUST 持久化配置变更,创建新版本(不覆盖历史),下次运行时使用新配置

#### Scenario: 配置版本回滚
- **WHEN** 用户选择回滚 Agent 到历史版本 V3
- **THEN** 系统 MUST 把当前活跃版本切到 V3,后续运行使用 V3 配置;V3 仍保留供再次回滚

### Requirement: Agent 自主推理
系统 MUST 支持 Agent 的多步推理循环(thought → action → observation),直到 Agent 决定完成任务或达到 max-iterations 限制。

#### Scenario: 多步推理
- **WHEN** Agent 接收任务"分析本季度销售数据并生成报告"
- **THEN** 系统 MUST 让 Agent 自主推理:① 思考"需要哪些数据"② 调查询工具拿数据 ③ 观察结果 ④ 思考"还需要图表"⑤ 调图表工具 ⑥ 汇总输出报告;每步 MUST 持久化到短期记忆 (Redis)

#### Scenario: max-iterations 终止
- **WHEN** Agent 推理超过 max-iterations 限制(默认 10)
- **THEN** 系统 MUST 终止推理,返回当前 partial 结果,标记为 timeout;audit log 记录终止原因

### Requirement: 工具调用
系统 MUST 支持 Agent 调用 MCP server / 自定义插件;工具调用结果回流到 Agent 推理上下文。

#### Scenario: 工具调用成功
- **WHEN** Agent 推理决定调 "filesystem.read_file" 工具
- **THEN** 系统 MUST 调用对应 MCP server,传参数,获返回,返回结果注入 Agent 推理上下文,Agent 继续推理

#### Scenario: 工具调用失败
- **WHEN** 工具调用超时(默认 30s)或 5xx
- **THEN** 系统 MUST 根据 retry 策略重试(默认 2 次)或 fallback 到替代工具(若配置);失败 MUST 注入错误信息到 Agent 上下文,Agent 决定重试或换工具或放弃

### Requirement: 记忆管理
系统 MUST 实现四层记忆(eng-review [ENG-Arch #3] 待 architecture.md §4.3.X 补详细设计):工作记忆 (in-context) / 短期记忆 (Redis, session-scoped) / 长期记忆 (PostgreSQL, user-scoped) / 语义记忆 (Milvus, topic-scoped)。

#### Scenario: 记忆检索
- **WHEN** Agent 接收用户输入"上次我们讨论的合同"
- **THEN** 系统 MUST 按 L1 → L2 → L3 → L4 顺序检索:① in-context ② Redis 短期(本 session) ③ PostgreSQL 长期(本 user) ④ Milvus 语义相关(top-5 相似度 > 0.7);命中即停

#### Scenario: 记忆更新
- **WHEN** Agent 完成推理
- **THEN** 系统 MUST 异步更新四层记忆:① 工作记忆清理过期 ② 短期记忆保留关键信息 24h ③ 长期记忆写入持久事实 ④ 语义记忆 embedding 新知识

### Requirement: Sub Agent 版本与性能监控
系统 MUST 支持 Sub Agent 的版本管理 + 单 Sub Agent 性能监控(调用次数 / 成功率 / 平均耗时 / P99 耗时)。

#### Scenario: Sub Agent 性能面板
- **WHEN** 用户打开 Sub Agent "数据查询" 的详情页
- **THEN** 系统 MUST 显示该 Sub Agent 的最近 7 天性能:调用次数、成功率、平均耗时、P99 耗时

### Requirement: Agent 网关隔离
所有 Agent 的 LLM 调用 MUST 经过数据隔离网关 (egress 强制点, [ENG-Arch #1])。

#### Scenario: Agent 调用经网关
- **WHEN** Agent 调用 LLM API
- **THEN** 系统 MUST 路由调用经数据隔离网关;网关 MUST 校验凭证、执行 PII 脱敏、记录 audit log、关联 trace-id

