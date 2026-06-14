## ADDED Requirements

### Requirement: 用户列表渲染 3+ mock 行
admin `/users` 路由 MUST 渲染用户列表,包含至少 3 行 mock 数据:张三(技术部/管理员/正常)、李四(产品部/开发者/正常)、王五(运营部/普通用户/待审核)。

#### Scenario: 表格行数
- **WHEN** 访问 `/admin/users`
- **THEN** 表格显示 3 行 mock 数据

#### Scenario: 列定义
- **WHEN** 表格渲染
- **THEN** 列依次为:用户(头像 + 姓名 + 邮箱)、部门、角色(tag)、状态(tag)、最后登录、操作(编辑 + 禁用按钮)

#### Scenario: 工具栏
- **WHEN** 表格上方渲染
- **THEN** 显示搜索输入框、批量导入按钮、导出按钮、添加用户按钮(主操作)

#### Scenario: 数据来源
- **WHEN** 渲染 UsersPage
- **THEN** 数据从 `web/admin/src/data/users.ts` 静态导入,不是从后端 API 拉取
