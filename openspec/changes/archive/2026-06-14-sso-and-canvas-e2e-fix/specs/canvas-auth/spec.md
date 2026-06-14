## ADDED Requirements

### Requirement: SSO 回跳 + token 兑换 + refresh

canvas-auth MUST 在 dev mock IAM + JWT + dev fallback 基础上追加 SSO 路径:回跳 URL 处理 + code → token 兑换 + refresh token 续期 + 401 回 IdP 重登。

#### Scenario: 企微扫码 SSO 回跳

- **WHEN** 用户在 portal 点"企业扫码登录" → 假 IM 弹窗点"确认" → 调 `/api/auth/sso/wechat/callback?token=<one-time>`
- **THEN** portal 拿到 `{ jwt, refresh, expires_in }`,写 auth state,跳 `/portal/`
- **THEN** 跟现有 username/password 登录走相同 state 路径(`useAuthStore` 不区分登录方式)

#### Scenario: refresh token 续期

- **WHEN** 前端任意请求返 `401 Unauthorized` 且错误码 `token.expired`
- **THEN** 前端自动调 `POST /api/auth/refresh` 带 `refresh_token`,拿新 `{ jwt, refresh }`,重发原请求
- **THEN** 续期失败时清 auth state + 跳 `/portal/login` + 保留 returnTo URL
