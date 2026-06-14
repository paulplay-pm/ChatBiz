## ADDED Requirements

### Requirement: Dashboard 渲染 4 个 metric 卡片
portal DashboardPage MUST 渲染 4 个 MetricCard:我的工作流(12)、我的 Agent(5)、今日调用(2,456)、Token 消耗(456K)。

#### Scenario: 登录后访问工作台
- **WHEN** 用户登录后访问 `/portal/`
- **THEN** Dashboard 显示 4 个 metric 卡片,数值分别为 12、5、2,456、456K

#### Scenario: Metric 数据来源
- **WHEN** 渲染 DashboardPage
- **THEN** 数据从 `web/portal/src/data/dashboard.ts` 静态导入,不是从后端 API 拉取

### Requirement: 快速开始 4 卡
Dashboard MUST 显示 4 个"快速开始"卡:新建工作流、创建 Agent、上传知识库、开始对话,每卡有图标 + 主标题 + 副标题。

#### Scenario: 快速开始区块
- **WHEN** Dashboard 渲染
- **THEN** 4 张快速开始卡按 row × col 2×2 排列,标题分别为"新建工作流"/"创建 Agent"/"上传知识库"/"开始对话"

#### Scenario: 跳转到 canvas
- **WHEN** 用户点击"新建工作流"或"创建 Agent"或"上传知识库"
- **THEN** 浏览器跳转到对应 canvas 路径(`/canvas/workflows`、`/canvas/agent`、`/canvas/knowledge`),通过 `window.location.assign('http://localhost:5173/canvas/...')`

### Requirement: 最近访问 + 最近动态
Dashboard MUST 显示"最近访问"列表(智能客服机器人 / 数据分析助手 / 产品知识库,各带 type + 时间)和"最近动态"列表(2 条 mock:工作流执行成功 + Agent 已发布)。

#### Scenario: 最近访问 + 最近动态区块
- **WHEN** Dashboard 渲染
- **THEN** 屏幕右侧显示"最近访问"区块(3 条),下方"最近动态"区块(2 条)
