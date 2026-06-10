# skill-management Specification

## Purpose
TBD - created by archiving change add-chatbiz-platform. Update Purpose after archive.
## Requirements
### Requirement: 技能浏览与安装
系统 MUST 提供技能市场 UI,展示可用技能(类似 plugin 但语义更广——可包含 prompt 模板 / 工具集 / agent 配置);支持安装/卸载到 workspace。

#### Scenario: 浏览技能市场
- **WHEN** 用户打开技能市场
- **THEN** 系统 MUST 渲染技能卡片(名称、描述、作者、版本、评分、已安装数);支持按类别筛选 + 全文搜索

#### Scenario: 安装技能
- **WHEN** 用户点击"安装"某个技能
- **THEN** 系统 MUST 把技能下载到 workspace,版本锁定;安装后该技能可被 agent 引用

### Requirement: 技能绑定 Agent
系统 MUST 支持把技能绑定到 agent(类似 function calling),agent 推理时自动加载。

#### Scenario: 绑定技能
- **WHEN** 用户在 agent 配置页勾选"已安装技能"列表中的某项
- **THEN** 系统 MUST 持久化绑定关系;下次 agent 运行时 MUST 自动加载该技能的 system prompt / 工具集

### Requirement: 自定义技能
系统 MUST 支持用户用 prompt 模板 + 工具集 + agent 配置定义新技能(类似 Dify 的"工作流即技能")。

#### Scenario: 创建技能
- **WHEN** 用户在技能市场点击"创建技能",填入名称 + 描述 + prompt 模板 + 选择工具集
- **THEN** 系统 MUST 持久化技能;技能可在 workspace 内共享

### Requirement: 技能版本
系统 MUST 支持技能版本管理(更新时旧版本保留,用户可选回滚)。

#### Scenario: 技能更新
- **WHEN** 技能作者发布新版本 V2
- **THEN** 系统 MUST 把 V2 标记为 latest;用户已安装 V1 的 workspace 收到更新通知,选择"更新"或"保持 V1"

