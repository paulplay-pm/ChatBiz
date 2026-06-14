# chatflow-runtime Specification

## Purpose
TBD - created by archiving change sso-and-canvas-e2e-fix. Update Purpose after archive.
## Requirements
### Requirement: chatflow runtime 续接契约

`POST /api/v1/workflows/:id/run?mode=chatflow` MUST 接受 `X-Session-Id` header 续接已有会话,无 session 时创建新会话;返 `text/event-stream` SSE 持续推送节点事件。

#### Scenario: 新会话创建

- **WHEN** 客户端 POST `/api/v1/workflows/<wf-id>/run?mode=chatflow` 不带 `X-Session-Id` header
- **THEN** 后端创建新 LangGraph thread,生成 `session_id`,写入 PostgreSQL `chatflow_sessions` 表
- **THEN** 返回 `200 OK` + `X-Session-Id: <uuid>` response header + SSE 流首个 event `{"type":"session_created","session_id":"<uuid>"}`

#### Scenario: 续接已有 session

- **WHEN** 客户端 POST 同一 endpoint 带 `X-Session-Id: <existing-uuid>` header
- **THEN** 后端从 PostgreSQL 加载 thread state,LangGraph checkpointer 恢复 conversation history
- **THEN** SSE 流首个 event `{"type":"session_resumed","session_id":"<uuid>","history_length":N}`

#### Scenario: 节点事件 schema

- **WHEN** workflow 任一节点完成
- **THEN** SSE push 事件 `{"type":"node_completed","node_id":"...","node_type":"llm|agent|...","output":{...},"duration_ms":N,"timestamp":"<ISO8601>"}`
- **THEN** 节点等待人工输入时 push `{"type":"node_pending","node_id":"...","approval_id":"<uuid>","prompt":"..."}` 客户端渲染 inline 审批卡(对齐 canvas-chatflow spec)

### Requirement: 24h session TTL

chatflow session MUST 在 24h 无活动后过期,过期 session 的 `X-Session-Id` 续接请求 MUST 返 `410 Gone` + 提示客户端重开会话。

#### Scenario: 24h TTL 过期

- **WHEN** 客户端 POST 带 `X-Session-Id` 但该 session `last_activity_at` 早于 24h 前
- **THEN** 返 `410 Gone` + `{"error":"session_expired","retry_strategy":"create_new"}`

