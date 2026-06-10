# canvas-workflow-list Specification

## Purpose
TBD - created by archiving change implement-canvas-ui. Update Purpose after archive.
## Requirements
### Requirement: workflow 列表渲染
系统 MUST 用 Ant Design `List` 组件渲染 workflow 卡片网格,每卡片显示:名称、创建时间、版本号、状态、运行次数、共享范围(自己 / 团队 / 公开);每页 20 条,支持分页;加载时间 < 1s(本地 1k workflow 内)。eng-review PRD §4.1.1 WF-000a 锁定。

#### Scenario: 列表加载
- **WHEN** 用户打开 `/workflows`
- **THEN** 系统 MUST 渲染 workflow 卡片网格,每卡片显示 6 字段;加载时间 < 1s(本地数据库 1k workflow 内)

#### Scenario: 空列表
- **WHEN** 用户无 workflow
- **THEN** 系统 MUST 显示空状态("还没有工作流,点击新建")+ "新建工作流" 按钮

### Requirement: 按名称搜索
顶部搜索框 MUST 实时(<200ms)按 workflow 名称过滤;`useQuery` debounce 300ms。eng-review PRD WF-000b 锁定。

#### Scenario: 搜索匹配
- **WHEN** 用户在搜索框输入 "月报"
- **THEN** 系统 MUST 实时(< 200ms)只显示名称含 "月报" 的卡片;不发起额外 query(refetch 即可)

#### Scenario: 搜索清空
- **WHEN** 用户清空搜索框
- **THEN** 系统 MUST 恢复完整列表

### Requirement: 状态 / 类型 / 共享范围筛选
侧栏 MUST 提供 3 个 `Select` 筛选器:状态(draft / published / archived)+ 类型(workflow / chatflow)+ 共享范围(自己 / 团队 / 公开);3 条件 AND 组合。eng-review PRD WF-000b 锁定。

#### Scenario: 单条件筛选
- **WHEN** 用户选 status=draft
- **THEN** 系统 MUST 只显示 status=draft 的卡片;其他卡片隐藏

#### Scenario: 多条件组合
- **WHEN** 用户选 status=draft + type=workflow
- **THEN** 系统 MUST 只显示 status=draft AND type=workflow 的卡片;两个条件都满足

### Requirement: 新建 workflow
"新建工作流" 按钮 MUST 弹 modal,输入 name + mode(workflow / chatflow),点 "创建" → POST `/workflows` 返 201 + workflow_id;前端跳转到画布编辑页。eng-review PRD WF-000c 锁定。

#### Scenario: 创建 workflow
- **WHEN** 用户输入 name="paul 月报" + mode=workflow + 点 "创建"
- **THEN** 系统 MUST POST `/workflows` 返 201 + `{id, version: 1}`;前端路由 push 到 `/workflows/:id/edit`;新 workflow 出现在列表

#### Scenario: 名称必填
- **WHEN** 用户未输入 name 直接点 "创建"
- **THEN** 系统 MUST 阻止提交 + Ant Design `Form` 校验提示"name 必填"

### Requirement: 进入画布编辑
点击 workflow 卡片 MUST 跳转到 `/workflows/:id/edit` 画布编辑页;带当前版本号(从 latest version 取)。eng-review PRD WF-000c 锁定。

#### Scenario: 进入画布
- **WHEN** 用户点击卡片
- **THEN** 系统 MUST 路由 push 到 `/workflows/:id/edit?version=latest`;画布编辑页加载 workflow definition

### Requirement: workflow 收藏(P1)
卡片 MUST 提供 "收藏" 按钮,点击 toggle 收藏状态;收藏的 workflow 在列表顶部 + 单独 "已收藏" tab 显示。eng-review PRD WF-000d 锁定(P1)。

#### Scenario: 收藏 toggle
- **WHEN** 用户点击 "收藏" 按钮
- **THEN** 系统 MUST 调 PATCH `/workflows/:id/favorite` 切到 true;UI 立即变实心星

#### Scenario: 已收藏 tab
- **WHEN** 用户切到 "已收藏" tab
- **THEN** 系统 MUST 只显示 favorite=true 的卡片;支持搜索 / 筛选

### Requirement: workflow 删除 / 归档
卡片 MUST 提供 "删除" 按钮(confirm modal 二次确认),点 "确认" → DELETE `/workflows/:id`(soft delete,`archived=true`);卡片从列表消失,GET `/workflows/:id` 返 410。eng-review Q9 锁定。

#### Scenario: 软删除
- **WHEN** 用户点 "删除" + confirm "确认"
- **THEN** 系统 MUST DELETE `/workflows/:id` 返 204;前端从列表移除卡片;不影响已存在的 workflow_run 历史

#### Scenario: 误删恢复
- **WHEN** 用户误删 (TODO 留作 V1.0:无 UI undo 路径)
- **THEN** 系统 MUST NOT 提示错误;**V1.0+ 提供 "已归档" tab + 恢复按钮**

