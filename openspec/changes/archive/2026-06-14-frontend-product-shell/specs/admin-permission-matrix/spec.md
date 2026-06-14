## ADDED Requirements

### Requirement: 权限矩阵大表
admin `/permissions` 路由 MUST 渲染权限矩阵表:7 功能模块 × 11 权限点 × 6 操作(查看/创建/编辑/删除/发布/执行)。

#### Scenario: 矩阵行/列
- **WHEN** 访问 `/admin/permissions`
- **THEN** 表显示 7 行功能模块(工作流/Agent/知识库/对话/模板/插件/系统管理),每行下含多个权限点(如工作流下含"工作流列表" + "工作流画布")

#### Scenario: 顶部角色切换
- **WHEN** 页面渲染
- **THEN** 右上角 dropdown 显示"超级管理员/部门管理员/开发者/普通用户"4 个角色选项,默认选中"超级管理员"

#### Scenario: 只读模式
- **WHEN** 顶部"只读查看"toggle 存在
- **THEN** toggle 默认 ON,所有 checkbox `disabled`,V4 接 API 后才能写

#### Scenario: 单元格渲染
- **WHEN** 渲染权限点行的 6 个操作
- **THEN** 已有权限显示绿色对勾 icon,无权限显示灰色短横线
