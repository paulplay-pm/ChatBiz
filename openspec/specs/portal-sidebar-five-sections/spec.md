# portal-sidebar-five-sections Specification

## Purpose
TBD - created by archiving change frontend-product-shell. Update Purpose after archive.
## Requirements
### Requirement: 5 分组 Sidebar
portal Sidebar MUST 渲染 5 个分组(粗灰小字 section title),分组顺序为:工作区 / 探索 / 配置中心 / 运维 / 系统管理。

#### Scenario: Sidebar 渲染 5 分组
- **WHEN** 用户登录后访问 `/portal/`
- **THEN** Sidebar 显示 5 个 section title,顺序与上述一致

#### Scenario: 30+ 项收敛到 ~24 项
- **WHEN** Sidebar 渲染所有 item
- **THEN** 总 item 数 ≤ 25 项(原 30+ 项中与 9 张图不符的项已删除)

### Requirement: 跨 app 跳转
MenuItem MUST 支持 `external: boolean` 字段。`external: true` 的 item 点击后 MUST 走 `window.location.assign(item.href)`,`external: false`(默认)走 `useNavigate(item.href)` 内部路由。

#### Scenario: 系统管理 7 项跳 admin
- **WHEN** 用户点击 Sidebar 中"系统管理"分组的任意 item(用户列表/用户审核/角色/部门/权限/数据权限/设置)
- **THEN** 浏览器跳转到 `http://localhost:5173/admin/<对应 path>`,触发完整页面刷新(因跨 app)

#### Scenario: 工作流跳 canvas
- **WHEN** 用户点击 Sidebar "工作区"分组下的"工作流"item
- **THEN** 浏览器跳转到 `http://localhost:5173/canvas/workflows`

#### Scenario: 控制台走内部
- **WHEN** 用户点击 Sidebar "工作区"分组下的"工作台"item(external=false)
- **THEN** react-router 内部跳到 `/portal/`,无整页刷新

