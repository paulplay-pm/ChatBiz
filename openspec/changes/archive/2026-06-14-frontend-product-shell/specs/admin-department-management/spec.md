## ADDED Requirements

### Requirement: 部门树状渲染
admin `/departments` 路由 MUST 渲染树状部门结构(根节点 + 子部门 + 成员头像 + 数字 badge)。

#### Scenario: 顶级部门
- **WHEN** 访问 `/admin/departments`
- **THEN** 渲染 3 个顶级部门:技术部、产品部、运营部,每部门右侧显示"+N" 成员数

#### Scenario: 子部门
- **WHEN** 渲染技术部
- **THEN** 显示 2 个子部门(后端开发组/前端开发组),子部门缩进显示,各自成员头像

#### Scenario: 添加部门
- **WHEN** 页面渲染
- **THEN** 右上角显示"+ 添加部门"按钮(纯 mock UI,点击不真创建)
