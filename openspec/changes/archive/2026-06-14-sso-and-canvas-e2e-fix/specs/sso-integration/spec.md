## ADDED Requirements

### Requirement: SSO 三档集成契约

SSO MUST 分 v0/v1/v2 三档落地:
- **v0 (MVP)** MUST 集成企微扫码登录,跳过本系统密码,直接信任 IM 平台身份
- **v1 (V1.0)** [FUTURE-IMPLEMENTATION] MUST 接入 OIDC(对接 Keycloak/Auth0/自建 IdP)
- **v2 (V1.5)** [FUTURE-IMPLEMENTATION] MUST 接入 SAML 2.0(企业 IdP metadata 解析 + assertion 验证)

#### Scenario: v0 企微扫码登录

- **WHEN** 用户在 portal `/login` 页面点击"企业扫码登录"按钮
- **THEN** 浏览器跳转到 `/sso-mock-im?token=<one-time-token>` 模拟 IM 扫码页,用户点"确认登录"后
- **THEN** `/api/auth/sso/wechat/callback?token=<one-time-token>` 返回 `{ jwt, refresh, expires_in }` 并写入 portal auth state

#### Scenario: v1 OIDC code → token 兑换

- **WHEN** OIDC provider 回调到 portal `/api/auth/sso/oidc/callback?code=<authorization-code>&state=<csrf-state>`
- **THEN** 后端用 `code` 兑换 `id_token + access_token + refresh_token`,验证 `state` 与 session 一致
- **THEN** 返回标准 JWT 包含 `sub` (用户 ID) + `email` + `groups` (RBAC 角色) + `iat` + `exp` claims

#### Scenario: v2 SAML assertion 验证

- **WHEN** SAML IdP POST SAMLResponse 到 `/api/auth/sso/saml/acs`
- **THEN** 后端用 IdP certificate 验证 SAML assertion 签名,提取 `NameID` + 属性 statements
- **THEN** 映射 `NameID` → 本地用户,创建 session,返回 JWT

### Requirement: admin SSO 配置页契约

admin `/system/sso` 路由 MUST 渲染 SSO 配置页,支持 3 个 tab(企微/OIDC/SAML),每 tab 含启用开关 + 参数表单 + 测试连接按钮 + 状态指示。

#### Scenario: 3 tab + 启用开关

- **WHEN** admin 访问 `/admin/system/sso`
- **THEN** 显示 3 tab:企微扫码(默认选中)/OIDC/SAML
- **THEN** 每 tab 顶部有启用 toggle,关闭时表单字段 disabled
- **THEN** 表单字段未填时,底部"保存"按钮 disabled
