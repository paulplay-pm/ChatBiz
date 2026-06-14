## ADDED Requirements

### Requirement: 用户审核页渲染 pending 行
admin `/users/audit` 路由 MUST 渲染"待审核"用户列表,过滤 status='pending' 的 mock 数据。

#### Scenario: 审核页显示
- **WHEN** 访问 `/admin/users/audit`
- **THEN** 表格只显示 status='pending' 的 mock 用户(至少 1 行,带"12" badge 提示待审核数)

#### Scenario: 通过/拒绝按钮
- **WHEN** 表格行渲染
- **THEN** 每行操作列含"通过"和"拒绝"两个按钮(纯 mock UI,点击不真改状态,V4 接 API 后再实)
