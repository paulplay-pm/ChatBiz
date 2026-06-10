# canvas-chatflow Specification

## Purpose
TBD - created by archiving change implement-canvas-ui. Update Purpose after archive.
## Requirements
### Requirement: chatflow 对话页加载
`/chatflow` 路由 MUST 显示:左侧 workflow 选择(下拉)+ 右侧对话气泡流(用户消息右对齐 / AI 消息左对齐)+ 底部输入框。eng-review Arch #4 锁定 chatflow 模式。

#### Scenario: 进入 chatflow 页
- **WHEN** 用户访问 `/chatflow`
- **THEN** 系统 MUST 渲染 workflow 选择下拉(默认显示用户最近编辑的 chatflow workflow)+ 空对话气泡流 + 输入框 disabled(无 workflow 选中时)

#### Scenario: 选中 workflow
- **WHEN** 用户从下拉选 1 个 chatflow workflow
- **THEN** 系统 MUST 加载该 workflow definition + 启用输入框;若有历史 session(MUST 用 `X-Session-Id` 续接),自动加载历史气泡

### Requirement: 发送消息 + workflow 触发
用户 MUST消息 + 回车 → 调 `POST /workflows/:id:run` with `mode=chatflow` + `X-Session-Id=session-uuid` + `initial_inputs={user_message: ...}`;返 202 + run_id;前端开始订阅 SSE。

#### Scenario: 首次发送
- **WHEN** 用户输入 "分析 5 月营收" + 回车
- **THEN** 系统 MUST 弹 1 个用户消息气泡 + 调 workflow_run(mode=chatflow);SSE 推送时 AI 消息气泡逐步填充

#### Scenario: 续接 session
- **WHEN** 同一用户选同一 workflow + 新消息
- **THEN** 系统 MUST 用同 X-Session-Id + LangGraph checkpoints 续接;新消息进同一 thread

### Requirement: 对话气泡实时显示
SSE 推 `node_completed` 时,对应节点输出 MUST 出现在对话气泡中(简化版:用 llm 节点的 content 字段)。eng-review Arch #4 Chatflow 端到端。

#### Scenario: AI 响应气泡
- **WHEN** chatflow workflow LLM 节点完成
- **THEN** 系统 MUST 在对话流中插入 AI 消息气泡,内容 = LLM 节点 output.content;若 LLM streaming,逐字填充

#### Scenario: 工具调用展示
- **WHEN** workflow 含 HTTP 节点 + 执行完成
- **THEN** 系统 MUST 在对话流中显示 "调用了 HTTP 节点 [url]" 卡片(简化版),不显示完整 response

### Requirement: 多人协作 stub
chatflow 对话页 MUST 支持 X-Session-Id 区分会话(URL hash 携带);同 session 跨设备 MUST 续接;不允许多人同 session 同时编辑(避免冲突)。

#### Scenario: 新 session
- **WHEN** 用户首次进入 `/chatflow`
- **THEN** 系统 MUST 生成 uuid 作 X-Session-Id + 存 localStorage;URL 变 `/chatflow#session=<uuid>`

#### Scenario: 跨 tab 续接
- **WHEN** 用户在 2 个 tab 都打开同 `/chatflow#session=<uuid>`
- **THEN** 2 tab MUST 都订阅同 SSE 流(同 thread_id);消息同步出现;**last-write-wins 简化策略**

### Requirement: 人工审批 inline
当 chatflow workflow 含 approval 节点,SSE 推 `node_pending` 时 MUST 在对话气泡中显示 "请审批人 X 审批 [内容]" 卡片 + "批准" / "拒绝" 按钮;点按钮调 `POST /approvals/:id:resume`。eng-review Arch #6 + PRD WF-014 锁定。

#### Scenario: 审批 inline
- **WHEN** chatflow workflow 跑到 approval 节点
- **THEN** 系统 MUST 在对话流中显示审批卡片(若当前 user 是 approver_user_id);否则显示 "等待 <approver_user_id> 审批"

#### Scenario: 审批通过
- **WHEN** 当前 user 是 approver + 点 "批准"
- **THEN** 系统 MUST POST `/approvals/:id:resume` decision=approved;SSE 续接 + 后续 AI 消息气泡继续

#### Scenario: 非审批人视角
- **WHEN** chatflow 跑到 approval + 当前 user 不是 approver
- **THEN** 系统 MUST 只显示等待状态(不显示按钮);**MUST NOT** 渲染审批按钮(防止误操作)

### Requirement: chatflow 工作流 vs workflow 区分
workflow 选择下拉 MUST 区分:workflow 类型(mode=workflow)+ chatflow 类型(mode=chatflow);选 chatflow 才发 mode=chatflow,选 workflow 弹提示"该 workflow 不能用于对话"。

#### Scenario: 选 workflow workflow
- **WHEN** user 选 mode=workflow 的 workflow
- **THEN** 系统 MUST 弹提示"该 workflow 是单次执行模式,不能用于对话。请选 chatflow 类型 workflow" + 重新选

#### Scenario: 区分显示
- **WHEN** workflow 下拉渲染
- **THEN** 列表 MUST 标注 mode(workflow / chatflow);chatflow workflow 显示 💬 图标,workflow 显示 ▶ 图标

