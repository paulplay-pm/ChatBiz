# canvas-debugger Specification

## Purpose
TBD - created by archiving change implement-canvas-ui. Update Purpose after archive.
## Requirements
### Requirement: 调试器页加载 + 状态总览
调试器页 (`/runs/:run_id`) MUST 显示:workflow 名称、状态徽章(pending/running/paused/completed/failed/cancelled)、启动时间、结束时间(若已结束)、错误信息(若 failed)+ 节点列表(每节点当前 status)+ "重试" / "取消" 按钮。eng-review Quality #3 错误边界可视化。

#### Scenario: 调试器加载
- **WHEN** 用户从画布点 "运行" → 跳到 `/runs/:run_id`
- **THEN** 系统 MUST 调 `GET /runs/:run_id` 拿初始状态 + 渲染调试器页;status=pending 时显示 loading

#### Scenario: workflow 完成状态
- **WHEN** workflow_run.status=completed
- **THEN** 系统 MUST 显示绿色 "已完成" 徽章 + ended_at 时间 + 节点列表全 completed + 显示 "再次运行" 按钮

#### Scenario: workflow 失败状态
- **WHEN** workflow_run.status=failed + error_class=runtime
- **THEN** 系统 MUST 显示红色 "失败" 徽章 + error_class + error_message + 失败节点标红 + 显示 "重试" 按钮

### Requirement: SSE 实时节点状态
系统 MUST 用 `EventSource` 订阅 `GET /runs/:run_id/events`,每个 `node_running` / `node_completed` / `node_failed` / `node_skipped` event MUST 立即更新画布对应节点状态色 + 调试器页节点列表。eng-review Q8 锁定。

#### Scenario: 节点开始执行
- **WHEN** 画布节点 n2 进入 running
- **THEN** SSE MUST 推 `event: node_running\ndata: {...}`;前端 MUST 立即把 n2 节点 wrapper 变蓝色边框 + 调试器页节点列表 n2 状态变 running

#### Scenario: 节点完成
- **WHEN** SSE 推 `event: node_completed` for n2
- **THEN** 前端 MUST n2 变绿色边框 + 调试器页节点列表 n2 状态 completed

#### Scenario: SSE 断线重连
- **WHEN** EventSource 断线(网络抖动)
- **THEN** 前端 MUST 自动重连(浏览器默认行为);重连后 MUST 调 `GET /runs/:run_id` 拿最新状态 + 同步画布

#### Scenario: workflow 终态事件
- **WHEN** SSE 推 `event: run_completed` / `run_failed` / `run_cancelled`
- **THEN** 前端 MUST 关闭 EventSource;调试器页显示终态徽章;不允许重复订阅

### Requirement: node_event 时间线
调试器页 MUST 显示 node_event 时间线(按时间升序):每条记录含 node_id / status / started_at / ended_at / retry_count / error_class / error_message;支持按 status 过滤;可展开看 input_json / output_json 详情。eng-review Test #2 path #1 数据来源。

#### Scenario: 时间线渲染
- **WHEN** workflow_run 完成(7 节点全部 completed)
- **THEN** 系统 MUST 渲染 7 条 node_event 记录按 started_at 升序;每条显示 node_id / status(绿色)/ 持续时间

#### Scenario: 失败节点详情
- **WHEN** 用户点开失败 node_event 详情
- **THEN** 系统 MUST 弹 modal 显示 input_json(原始对象)+ output_json(若有)+ error_class + error_message;**MUST NOT** 包含明文 prompt(eng-review D13 锁定)

### Requirement: 重试 / 取消
"重试" 按钮 MUST 调 `POST /workflows/:id:run` 启动新一次 run(用同一 workflow_id);"取消" 按钮 MUST 调 `POST /workflows/:id:cancel`(workflow-engine 后端暂无 cancel 端点,作为 follow-up)。eng-review Quality #3 4 错误边界。

#### Scenario: 重试
- **WHEN** 用户点 "重试" 按钮
- **THEN** 系统 MUST POST `/workflows/:id:run` 返 202 + 新 run_id;前端跳到 `/runs/<新run_id>`

#### Scenario: 取消(V1.0 follow-up)
- **WHEN** workflow_run.status=running + 用户点 "取消"
- **THEN** 系统 MUST POST `/workflows/:id:cancel`(eng-review 暂未实现该端点);**V1.0 follow-up 补 cancel 端点 + status=cancelled UI**

### Requirement: 实时节点事件 → 画布节点状态同步
调试器页打开时,画布节点(通过 `useCanvasEditStore` 共享)MUST 与 SSE 事件实时同步;调试器关闭时,画布仍保持同步状态(直到下次 :run)。eng-review Quality #3 端到端可视化。

#### Scenario: 画布节点状态同步
- **WHEN** 调试器页 SSE 推 `node_completed` for n3
- **THEN** 画布 n3 节点 wrapper MUST 变绿色边框(状态色同步);用户切回画布编辑页时仍可见绿色边框

#### Scenario: 切换页签不丢失
- **WHEN** 用户从调试器切到侧边栏其他菜单再切回
- **THEN** 画布节点状态 MUST 保持终态色(无闪烁)

### Requirement: 调试器页权限
调试器页 MUST 只允许 `started_by` 或 workflow 拥有者查看;其他用户访问 MUST 跳 403 错误页。eng-review Q10 鉴权 + workflow-engine spec §workflow-state-storage "多租户隔离" 锁定。

#### Scenario: 自己 run 可看
- **WHEN** started_by=user_a + user_a 访问 /runs/:run_id
- **THEN** 系统 MUST 正常渲染调试器

#### Scenario: 他人 run 不可看
- **WHEN** started_by=user_b + user_a 访问 /runs/:run_id
- **THEN** 系统 MUST 跳 403 错误页 + audit log 写 `unauthorized_run_access`

