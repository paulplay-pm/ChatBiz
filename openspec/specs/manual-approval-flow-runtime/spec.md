# manual-approval-flow-runtime Specification

## Purpose
TBD - created by archiving change sso-and-canvas-e2e-fix. Update Purpose after archive.
## Requirements
### Requirement: 人工审批节点 runtime 契约

人工审批节点 MUST 在 LangGraph `interrupt()` 处暂停执行,把 approval context 写入 PostgreSQL checkpointer,触发通知渠道(企微 webhook 至少 1 个),并把待审批状态通过 SSE 推送给 workflow 编辑者。

#### Scenario: 节点暂停 + 通知

- **WHEN** workflow 执行到 `approval` 节点
- **THEN** LangGraph `interrupt()` 暂停 thread,生成 `approval_id = uuid()`,写入 `approvals` 表(`workflow_id, node_id, approver_id, prompt, status=pending, created_at, expires_at = now() + 24h`)
- **THEN** 调企微 webhook 通知审批人:`{approval_id, workflow_name, node_label, prompt, approve_url, reject_url}`
- **THEN** SSE 推 workflow 编辑者:`{"type":"approval_pending","approval_id":"<uuid>","node_id":"...","prompt":"...","expires_at":"<ISO8601>"}`

#### Scenario: 审批通过续接

- **WHEN** 审批人点击 approve_url 或 POST `/api/v1/approvals/<id>/resume?decision=approved`
- **THEN** 后端从 PostgreSQL 加载 thread state,LangGraph 从 `interrupt()` 处恢复执行,把 `decision = approved` 作为节点输入
- **THEN** 更新 `approvals.status = approved` + `resolved_at`,SSE 推 `{type:"approval_resolved", approval_id, decision}`

#### Scenario: 24h 超时 escalation

- **WHEN** `approvals.expires_at` 早于当前时间且 `status` 仍为 `pending`
- **THEN** 后端定时任务扫表标记 `status = expired`,发 escalation 通知给 workflow owner
- **THEN** SSE 推 `{type:"approval_expired", approval_id}`,workflow runtime 走 reject 分支继续(默认)

### Requirement: 审批人重入

审批人 web UI MUST 支持断线/重连后通过 `approval_id` 重新进入审批页,加载原始 prompt + approve/reject 按钮。

#### Scenario: 审批人重入

- **WHEN** 审批人访问 `/approvals/<approval_id>` 页面
- **THEN** 页面加载原始 `prompt` + workflow name + node label,显示"通过"和"拒绝"按钮
- **THEN** 按钮 click 调对应 API,按钮变 disabled 防双击

