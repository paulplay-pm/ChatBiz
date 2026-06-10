# workflow-engine

> **eng-review refs:** [ENG-Arch #2, #4], [ENG-Quality #1, #2], [ENG-Test #1, #2]
> **depends on:** [credential-management], [audit-and-isolation]
> **source:** `docs/prd.md` §4.1, `docs/architecture.md` §4.3.1

## ADDED Requirements

### Requirement: 工作流列表
系统 MUST 提供工作流列表视图,以卡片形式展示名称、状态、运行次数、共享范围;支持按名称搜索,按状态/共享范围/类型筛选。

#### Scenario: 列表加载
- **WHEN** 用户打开工作流列表页面
- **THEN** 系统 MUST 渲染工作流卡片网格,每卡片显示名称、状态、运行次数、共享范围;加载时间 < 1s (本地数据库 1k workflow 内)

#### Scenario: 按名称搜索
- **WHEN** 用户在搜索框输入关键词
- **THEN** 系统 MUST 实时(<200ms)过滤卡片,只显示名称包含关键词的工作流

### Requirement: 可视化画布
系统 MUST 提供基于 React Flow / X6 的可视化画布编辑器,支持 12 类节点的拖拽、连线、参数配置、调试运行;画布 JSON 可序列化为可执行图。

#### Scenario: 拖拽节点
- **WHEN** 用户从节点面板拖拽一个 LLM 节点到画布
- **THEN** 系统 MUST 在画布上创建该节点实例,位置为释放点;节点 ID 唯一,无重复

#### Scenario: 节点连线
- **WHEN** 用户从一个节点的输出端口拖拽连线到另一个节点的输入端口
- **THEN** 系统 MUST 创建一条带箭头方向的边,自动校验源节点有输出端口、目标节点有输入端口;校验失败 MUST 阻止连线

#### Scenario: 调试运行
- **WHEN** 用户点击"调试运行"按钮
- **THEN** 系统 MUST 序列化画布为 JSON,调用 LangGraph 编译服务,执行工作流,实时流式返回每个节点的执行结果(状态、输出、耗时)

### Requirement: 工作流执行
系统 MUST 将画布 JSON 编译为 LangGraph StateGraph 并执行;支持串行/并行、条件路由、错误处理、结果聚合。

#### Scenario: 顺序执行
- **WHEN** 工作流包含 A → B → C 三个顺序节点
- **THEN** 系统 MUST 按 A → B → C 顺序执行,前一个节点完成后再执行下一个;执行状态持久化到 PostgreSQL

#### Scenario: 条件分支
- **WHEN** 工作流包含条件节点 C 决定 A → B 或 A → D
- **THEN** 系统 MUST 评估 C 的条件表达式,根据结果选择 B 或 D;条件失败 MUST 走配置的默认分支(若有)

#### Scenario: 执行错误处理
- **WHEN** 节点执行抛出异常(LLM 5xx / 代码执行失败)
- **THEN** 系统 MUST 标记该节点为失败状态,根据配置执行 retry(最多 N 次)或 skip 或 fail-fast;执行状态保留失败节点的位置便于用户调试

### Requirement: Workflow + Chatflow 双模式
系统 MUST 在同一 LangGraph StateGraph 上支持 workflow(单轮)和 chatflow(多轮)两种模式,通过 mode 参数区分。

#### Scenario: workflow 模式
- **WHEN** 用户配置 mode = "workflow"
- **THEN** 系统 MUST 按工作流定义执行单次,完成后返回结果,无中间状态保留

#### Scenario: chatflow 模式
- **WHEN** 用户配置 mode = "chatflow"
- **THEN** 系统 MUST 保留对话状态(Redis 短期记忆),支持多轮输入,每轮根据当前状态推进 workflow

### Requirement: 12 类节点类型
系统 MUST 实现 12 类节点:开始 / 结束 / LLM / 知识检索 / Agent / 条件分支 / 循环 / 迭代 / HTTP 请求 / 代码执行 / 人工审批 / 子流程 / 参数提取 / 变量赋值;MVP 阶段 MUST 至少实现开始 / 结束 / LLM / 知识检索 / 条件分支 5 类。

#### Scenario: 节点类型定义
- **WHEN** 用户从节点面板查看可用节点类型
- **THEN** 系统 MUST 列出所有 12 类节点(按 cap 实现进度);MVP 必含的 5 类 MUST 在月 2 前可用

### Requirement: 节点契约 (Node Contract)
系统 MUST 用 1 份 Node Contract (TypedDict) 驱动 12 类节点的 4 份代码(画布 UI 组件 + StateGraph 节点函数 + I/O schema + 验证函数);不允许每节点独立写 4 份。

#### Scenario: 节点定义一致性
- **WHEN** 实施方新增 1 类节点
- **THEN** 系统 MUST 仅需在 Node Contract 中加 1 个 TypedDict 定义,自动生成 UI / StateGraph / schema / validator;不允许手动写 4 份独立代码

### Requirement: 工作流状态持久化
系统 MUST 将工作流执行状态(包括 LangGraph Checkpoint)持久化到 PostgreSQL;画布实时状态(包括节点位置、选中状态)用 Redis 缓存 + event sourcing 支持回滚。

#### Scenario: 状态恢复
- **WHEN** 服务重启后用户打开 workflow instance
- **THEN** 系统 MUST 从 PostgreSQL 恢复 workflow state,从 Redis 恢复画布布局;两者 MUST 一致(不一致时以 PostgreSQL 为准,Redis 重建)

### Requirement: 4 critical path 测试 [ENG-Test #2]
系统 MUST 提供 4 个 critical path 的 100% 覆盖测试:① paul 财务月报 end-to-end ② 数据隔离网关 PII 拦截 ③ 人工审批中断与续接 ④ 插件加载失败降级。

#### Scenario: paul 财务月报 e2e
- **WHEN** 测试运行"paul 财务月报"workflow(创建 → 拖拽开始/LLM/结束节点 → 填参数 → 运行 → 拿到结果)
- **THEN** 系统 MUST 100% 通过;测试时间 < 30s

#### Scenario: 数据隔离网关 PII 拦截
- **WHEN** workflow 中 LLM 节点传入包含 PII(身份证号、手机号)的 prompt
- **THEN** 系统 MUST 阻断该调用并记录到 audit log,workflow 节点标记失败;测试 100% 通过

#### Scenario: 人工审批中断与续接
- **WHEN** workflow 包含人工审批节点,审批人 24h 内未响应
- **THEN** 系统 MUST 触发 timeout escalation(邮件/IM 通知 + workflow 标记 paused);审批人在 24h 后响应 MUST 续接;测试 100% 通过

#### Scenario: 插件加载失败降级
- **WHEN** workflow 调用的 MCP server (filesystem) 启动失败
- **THEN** 系统 MUST 标记该节点为 degraded,workflow 不 fail-fast,继续执行其他节点;测试 100% 通过
