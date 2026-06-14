# admin-data-permission Specification

## Purpose
TBD - created by archiving change frontend-product-shell. Update Purpose after archive.
## Requirements
### Requirement: 数据权限规则 + 共享记录表
admin `/data-permissions` 路由 MUST 渲染两段:上半部"数据权限规则"3 张可点击卡(个人数据/部门数据/跨部门共享),下半部"数据共享记录"表格。

#### Scenario: 3 规则卡
- **WHEN** 访问 `/admin/data-permissions`
- **THEN** 顶部显示 3 张规则卡:个人数据(默认)/部门数据/跨部门共享,每卡含图标 + 标题 + 描述

#### Scenario: 共享记录表
- **WHEN** 渲染页面下半部
- **THEN** 显示共享记录表,至少 4 行 mock(销售数据分析工作流/智能客服 Agent/产品知识库/合同审核工作流),列含资源名称/类型/创建者/所属部门/共享范围/操作

#### Scenario: 顶部标识
- **WHEN** 页面渲染
- **THEN** 右上角显示"基于部门的数据隔离" badge

