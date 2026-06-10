# plugin-market

> **eng-review refs:** [ENG-Arch #5, #6], [ENG-Quality #3], [ENG-Test #2]
> **depends on:** [credential-management], [audit-and-isolation], [monitoring]
> **source:** `docs/prd.md` §4.4, `docs/architecture.md` §4.3.5

## ADDED Requirements

### Requirement: MCP server 集成
系统 MUST 支持 Model Context Protocol (MCP) 标准协议 server 集成;MVP 阶段 MUST 至少实现 filesystem / fetch / postgres 三个核心 server。

#### Scenario: 加载 MCP server
- **WHEN** 用户配置一个 MCP server (filesystem) 的 stdio 或 SSE endpoint
- **THEN** 系统 MUST:① 启动 server 进程(或建立 SSE 连接) ② 列出 server 暴露的工具 ③ 注册到 Tool Registry 供 workflow / agent 调用

#### Scenario: MCP server 启动失败降级
- **WHEN** 加载 MCP server (filesystem) 进程启动失败(端口占用、配置错误)
- **THEN** 系统 MUST:① 标记该 server 为 degraded ② workflow 调该 server 工具 MUST 返回降级结果(空集 + 警告),不 fail-fast ③ audit log 记录失败原因 ④ monitoring 告警 ⑤ MCP server 状态可在 UI 重试加载

### Requirement: 自定义插件
系统 MUST 支持用户用 Python 写自定义插件(plugin.py 入口类),自动注册到 Tool Registry。

#### Scenario: 上传自定义插件
- **WHEN** 用户上传 plugin.py 实现 ToolProvider 抽象类
- **THEN** 系统 MUST:① 沙箱内执行验证 ② 列出插件暴露的工具 ③ 注册到 Tool Registry ④ 持久化到 MinIO

#### Scenario: 插件调用超时
- **WHEN** workflow 调用自定义插件,插件执行超过 30s(默认)
- **THEN** 系统 MUST 中断插件执行,返回 timeout 错误,workflow 节点标记失败,根据配置 retry 或 skip 或 fail

### Requirement: 插件浏览与启用
系统 MUST 提供插件市场 UI,展示可用插件列表(描述、版本、作者、评分);支持启用/禁用,启用后该插件的工具可被 workflow / agent 调用。

#### Scenario: 启用插件
- **WHEN** 用户点击"启用"某个插件
- **THEN** 系统 MUST 把插件标记为 enabled,工具注册到 Tool Registry;后续 workflow 创建时可选用该插件的工具

#### Scenario: 禁用插件
- **WHEN** 用户点击"禁用"某个正在被 workflow 引用的插件
- **THEN** 系统 MUST:① 标记 disabled ② 引用该插件的工作流 MUST 收到 deprecation warning ③ 不影响已运行实例,新执行 MUST 失败明确

### Requirement: 插件开发规范
系统 MUST 提供 plugin.py 模板,定义 ToolProvider / Tool / ParameterSchema 三个抽象类;插件代码 MUST 沙箱内执行。

#### Scenario: 沙箱执行
- **WHEN** 插件被 workflow 调用
- **THEN** 系统 MUST 在隔离沙箱 (Docker-in-Docker) 内执行插件;沙箱 MUST 限制 CPU / 内存 / 网络出站;超时 MUST 强制 kill

### Requirement: 插件加载失败降级 [ENG-Test #2 critical path 4]
系统 MUST 在插件加载失败时优雅降级,workflow 不 fail-fast;这是 4 个 critical path 之一。

#### Scenario: workflow 调失败插件
- **WHEN** workflow 包含调用 plugin-fs.read_file 节点,但 plugin-fs 启动失败
- **THEN** 系统 MUST:① 节点标记 degraded ② workflow 继续执行后续节点 ③ 输出包含降级警告 ④ 不 fail 整个 workflow
