# monitoring Specification

## Purpose
TBD - created by archiving change add-chatbiz-platform. Update Purpose after archive.
## Requirements
### Requirement: 基础监控面板
系统 MUST 提供基础监控面板(MVP P0);展示关键指标:活跃 workflow 数 / 活跃 agent 数 / 24h LLM 调用次数 / 24h token 用量 / 错误率 / P99 延迟。

#### Scenario: 监控面板加载
- **WHEN** 管理员打开监控面板
- **THEN** 系统 MUST 渲染 6 个核心指标卡片;数据更新周期 ≤ 30s;首屏加载 < 1s

### Requirement: 执行日志
系统 MUST 记录每次 workflow / agent 执行的详细日志(开始时间、结束时间、每个节点的状态 + 输出 + 耗时 + 错误)。

#### Scenario: 查看 workflow 执行历史
- **WHEN** 用户打开 workflow 详情,切换到"执行历史"标签
- **THEN** 系统 MUST 显示该 workflow 的所有历史执行记录(分页),每条 MUST 可点击查看节点级详情

#### Scenario: 节点级详情
- **WHEN** 用户点击某次执行的某节点
- **THEN** 系统 MUST 显示该节点的:输入参数、输出、耗时、retry 次数、错误堆栈(若有)、关联 audit log 链接

### Requirement: 告警配置
系统 MUST 支持告警规则配置(指标 + 阈值 + 通知渠道);V1.0+ 必含。

#### Scenario: 配置告警
- **WHEN** 管理员配置告警规则(指标 = 网关 P99 延迟 / 阈值 > 500ms / 通知 = 企微)
- **THEN** 系统 MUST 持久化规则;触发时 MUST 通过企微推送给指定接收人

#### Scenario: 告警触发
- **WHEN** 网关 P99 延迟持续 5 分钟 > 500ms
- **THEN** 系统 MUST 触发告警(避免单点抖动);audit log 记录告警事件;告警状态持久化避免重复

### Requirement: 日志搜索
系统 MUST 提供日志搜索(按 trace-id / 用户 / workflow / 时间范围 / 关键词)。

#### Scenario: trace-id 搜索
- **WHEN** 管理员用 trace-id 查询
- **THEN** 系统 MUST 返回该 trace 的所有日志条目(网关 / workflow / agent / LLM API);按时间排序

### Requirement: 链路追踪
系统 MUST 集成 OpenTelemetry / Jaeger,跨 服务 + 网关 + workflow + agent + LLM API 全链路 trace;V1.0+ 必含。

#### Scenario: 跨服务 trace
- **WHEN** 一次 workflow 执行跨 5 个服务(API Gateway + Workflow Engine + Agent Runtime + 数据隔离网关 + LLM API)
- **THEN** 系统 MUST 在 Jaeger UI 显示完整调用链(每段耗时 + 父子关系)

### Requirement: 监控数据导出
系统 MUST 支持监控数据导出(Prometheus metrics endpoint + Grafana dashboard JSON)。

#### Scenario: Prometheus 集成
- **WHEN** Prometheus server 抓取 /metrics endpoint
- **THEN** 系统 MUST 返回标准 Prometheus 格式指标(workflow_count / llm_call_count / token_usage / latency_p99 / error_rate)

