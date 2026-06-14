# admin-menu-update Specification

## Purpose
TBD - created by archiving change frontend-product-shell. Update Purpose after archive.
## Requirements
### Requirement: admin menu 14 项调整
admin `web/admin/src/config/menuItems.ts` MUST 替换 14 项 menu 为产品形态 5 分组 14 项:工作流 / Agent / 知识库 / 模板广场 / 团队共享 / 插件市场 / 模型管理 / 通道管理 / 凭证管理 / 技能管理 / MCP 工具 / 中间件链 / 监控 / 日志。新增 6 路径:`/users`、`/users/audit`、`/roles`、`/departments`、`/permissions`、`/data-permissions`。

#### Scenario: 14 menu item
- **WHEN** 渲染 admin SideNav
- **THEN** 显示 14 个 menu item(原 14 项保持,系统管理 5 子页独立于 menu,直接挂 router)

#### Scenario: 6 真实路径
- **WHEN** admin router 渲染
- **THEN** 6 个新路径(`/users`、`/users/audit`、`/roles`、`/departments`、`/permissions`、`/data-permissions`)指向真 view,其余 8 个仍指向 PlaceholderView

#### Scenario: SideNav 分组 label
- **WHEN** 渲染 SideNav
- **THEN** 顶部"工作区"label 保留(跟原型图 #8-13 一致)

