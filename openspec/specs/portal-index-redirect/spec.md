# portal-index-redirect Specification

## Purpose
TBD - created by archiving change frontend-product-shell. Update Purpose after archive.
## Requirements
### Requirement: 统一入口根路径重定向
统一入口根路径(`/`) MUST 在 0 秒内重定向到 portal 登录页(`/portal/login`)。

#### Scenario: 用户访问根路径
- **WHEN** 用户浏览器 GET `http://localhost:5173/`
- **THEN** 页面在 1 秒内显示 portal 登录页(`/portal/login`),不显示静态跳转卡

#### Scenario: 静态跳转卡已删除
- **WHEN** 查看 `web/index.html` 文件内容
- **THEN** 文件不含 "ChatBiz Web Portal" 标题、portal/canvas/admin 三张跳转卡或任何 `<a class="card">` 元素

#### Scenario: 降级链接
- **WHEN** 浏览器禁用 meta refresh 或 JS
- **THEN** body 内 `<a href="/portal/login">` 链接可见,点击跳登录页

