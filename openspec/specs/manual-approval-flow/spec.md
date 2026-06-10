# manual-approval-flow Specification

## Purpose
TBD - created by archiving change implement-workflow-engine. Update Purpose after archive.
## Requirements
### Requirement: 节点执行触发审批
workflow 节点 `approval` 执行时 MUST 走 4 步:① 写 LangGraph checkpoint(thread_id=workflow_run_id)② 写 `approval` 表(status=pending)③ 发企微 webhook(复用 `audit-and-isolation/app/alerts.py` 的 `send_wecom()` 函数)④ workflow_run 状态转 `paused`。

#### Scenario: 完整触发
- **WHEN** workflow 节点 n3 是 approval 类型,config=`{approver_user_id: "u-1", notify_channels: ["wecom"]}`
- **THEN** 系统 MUST:① `langgraph.checkpoints.put()` 写 thread_id=`run-abc` ② INSERT approval row(approver_user_id=u-1, status=pending)③ `alerts.send_wecom(user=u-1, content="待审批:...")` ④ UPDATE workflow_run.status=paused, ended_at=null

#### Scenario: 节点 config 缺 approver
- **WHEN** approval 节点 config 缺 `approver_user_id`
- **THEN** 系统 MUST 在 workflow_definition 启动阶段拒(`error_class=user`);不允许运行到节点触发再失败

### Requirement: 通知渠道
通知 MUST 通过 audit-and-isolation 已有的 `alerts.py` 模块发(eng-review Q11 锁定);env var `WECOM_WEBHOOK_URL` 未配置时,本地环境不发送但不报错;企业微信 / 邮件 / 站内信至少支持 1 个,MVP 锁企微。

#### Scenario: 企微通知成功
- **WHEN** `WECOM_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx` 已配置 + approval 触发
- **THEN** 系统 MUST POST 到该 URL + 200 返;audit log 写 `approval_notification_sent` + 消息 ID

#### Scenario: 本地环境无配置
- **WHEN** `WECOM_WEBHOOK_URL` 未配置
- **THEN** 系统 MUST skip 通知 + audit log 写 `approval_notification_skipped(reason=no_wecom_webhook_url)`;不允许 throw 异常阻塞 workflow

#### Scenario: 通知失败
- **WHEN** 企微 webhook 返 4xx / 5xx
- **THEN** 系统 MUST retry 1 次(2s 后);仍失败 MUST 写 `approval_notification_failed` + audit log;**MUST NOT** 阻塞 workflow 状态变化(approval 已 pending,审批人可手动查询)

### Requirement: 审批人 reentry
审批人 MUST 通过 `POST /approvals/:id:resume` 提交 decision(approved / rejected)+ payload;系统 MUST 校验权限 + 更新 approval + 续接 LangGraph 续行。eng-review Arch #6 锁定。

#### Scenario: 审批人批准
- **WHEN** approval_id=`apr-1` + approver_user_id=`u-1` POST `/approvals/apr-1:resume` 携带 `{decision: "approved", payload: {comment: "OK"}}`
- **THEN** 系统 MUST 校验 `approval.approver_user_id == u-1`(否则 403);更新 approval(status=approved, responded_at=now, response_payload=...);`langgraph.checkpoints.update_state()` 注入 payload;`compiled_graph.invoke(None, config={"configurable": {"thread_id": "run-abc"}})` 续接;workflow_run.status=pending → running

#### Scenario: 非审批人拒绝
- **WHEN** user_b 试图 POST `/approvals/apr-1:resume`(approval.approver_user_id=u-1)
- **THEN** 系统 MUST 返 403 + `error_class=security` + audit log 写 `unauthorized_approval_access`;不允许 resume

#### Scenario: 重复 resume 拒绝
- **WHEN** approval.status=approved + 再次 POST `/approvals/apr-1:resume`
- **THEN** 系统 MUST 返 409 + `error_class=user` + `error_message="审批已响应,不可重复"`;audit log 写 `duplicate_resume_attempt`

#### Scenario: 审批拒绝
- **WHEN** approval.approver_user_id=u-1 + decision=rejected
- **THEN** 系统 MUST 更新 approval(status=rejected);LangGraph 续接 + workflow_run.status=failed + error_class=user;audit log 写 `approval_rejected`

### Requirement: 取消审批
任何人(workflow 启动方 / 审批人)可 POST `/approvals/:id:cancel`;系统 MUST 更新 approval(status=cancelled)+ workflow_run.status=cancelled + LangGraph thread 标 cancelled。

#### Scenario: 启动方取消
- **WHEN** workflow_run.started_by=user_a + user_a POST `/approvals/apr-1:cancel`
- **THEN** 系统 MUST 校验 user_a == started_by(否则 403);更新 approval(status=cancelled);workflow_run.status=cancelled;LangGraph thread 标 cancelled;audit log 写 `approval_cancelled`

#### Scenario: 审批人取消
- **WHEN** approval.approver_user_id=u-1 + u-1 POST `/approvals/apr-1:cancel`
- **THEN** 系统 MUST 同样允许 + 走相同更新;audit log 写

### Requirement: 待审批列表
`GET /approvals/pending?user=X` MUST 返 user=X 的所有 pending approval(按 created_at 升序);支持分页(page / page_size)。

#### Scenario: 查询有结果
- **WHEN** user=u-1 + 2 个 pending approval(apr-1, apr-2)
- **THEN** 系统 MUST 返 200 + `{"approvals": [{approval_id, run_id, node_id, created_at, ...}, ...], "total": 2}`

#### Scenario: 查询无结果
- **WHEN** user=u-1 + 0 个 pending
- **THEN** 系统 MUST 返 200 + `{"approvals": [], "total": 0}`

#### Scenario: 分页
- **WHEN** `?user=u-1&page=2&page_size=10`
- **THEN** 系统 MUST 返第 11-20 条;总条数 total 正确;索引 `(approver_user_id, status, created_at)` 命中

### Requirement: 24h timeout cron
apscheduler MUST 在 service 启动时注册 1 个 cron job(每 5 分钟扫);扫到 `approval.created_at < now() - 24h` 且 status=pending → 标 timeout + workflow_run.status=failed + error_class=user + audit log 写 `approval_timeout`。eng-review Arch #6 锁定。

#### Scenario: 触发超时
- **WHEN** apscheduler 扫到 approval apr-1(approver_user_id=u-1, status=pending, created_at=25h ago)
- **THEN** 系统 MUST:① UPDATE approval(status=timeout, responded_at=now)② UPDATE workflow_run(status=failed, error_class=user, error_message="approval timeout: 24h exceeded")③ LangGraph thread 标 failed ④ audit log 写 `approval_timeout` event

#### Scenario: 边界情况(24h 之内)
- **WHEN** approval apr-2 created_at=23h ago
- **THEN** 系统 MUST NOT 标 timeout(还在 24h 内);下个 5 分钟 cron 仍会扫

#### Scenario: 已响应的 approval 不超时
- **WHEN** approval apr-3 status=approved(响应过)
- **THEN** 系统 MUST NOT 改 status(已是终态);cron 必须 WHERE status=pending 限定

#### Scenario: cron 启停
- **WHEN** service 重启
- **THEN** apscheduler MUST 重启 cron job;不允许 cron 漏跑导致 timeout 失效

