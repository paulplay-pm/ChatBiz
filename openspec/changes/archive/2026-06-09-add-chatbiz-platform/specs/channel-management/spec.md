# channel-management

> **eng-review refs:** (无强相关)
> **depends on:** [credential-management], [audit-and-isolation]
> **source:** `docs/prd.md` §4.6 (通道), `docs/architecture.md` §4.1 (接入层)

## ADDED Requirements

### Requirement: 通道配置
系统 MUST 支持通道的 CRUD;MVP 阶段 MUST 实现 Web 通道,V1.0+ 补 钉钉 / 企业微信 / 飞书。

#### Scenario: 创建 Web 通道
- **WHEN** 管理员创建 Web 通道(名称、URL、嵌入样式)
- **THEN** 系统 MUST 持久化通道配置,生成可嵌入的 iframe / SDK snippet

#### Scenario: 创建钉钉通道(V1.0+)
- **WHEN** 管理员创建钉钉通道,填入 AppKey / AppSecret / 机器人 webhook
- **THEN** 系统 MUST 验证钉钉连通性,持久化凭证(引用 credential-management),启用后 workflow 输出可推送到钉钉群

### Requirement: 通道消息推送
系统 MUST 支持 workflow / agent 输出推送到指定通道;消息格式 MUST 支持 Markdown + 卡片 + 引用溯源(对应知识库 / workflow 引用)。

#### Scenario: workflow 结束推送
- **WHEN** workflow 完成后配置"完成后推送"通道
- **THEN** 系统 MUST 把 workflow 结果 + 状态 + 链接推送到通道;失败 MUST 写入 audit log 不影响 workflow 状态

#### Scenario: 实时流式输出(chatflow)
- **WHEN** chatflow 在通道中执行
- **THEN** 系统 MUST 流式推送每个节点的输出(typing 效果);节点完成 MUST 单独消息标注

### Requirement: 通道权限
系统 MUST 支持通道的 RBAC 权限(谁能推送 / 谁能接收)。

#### Scenario: 通道推送权限
- **WHEN** workflow 配置了"完成后推送"通道,但 workflow 创建者无该通道推送权限
- **THEN** 系统 MUST 在 workflow 配置时警告,在执行时阻断推送 + 写入 audit log

### Requirement: 通道降级
系统 MUST 在通道不可用时降级(消息缓冲到 Kafka,通道恢复后重试);不能阻塞 workflow 主流程。

#### Scenario: 通道不可达
- **WHEN** workflow 调通道推送,但钉钉 webhook 5xx
- **THEN** 系统 MUST 把消息写入 Kafka 死信队列(3 次重试),workflow 不 fail;通道恢复后异步重投递
