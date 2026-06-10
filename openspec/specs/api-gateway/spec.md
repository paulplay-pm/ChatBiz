# api-gateway Specification

## Purpose
TBD - created by archiving change add-chatbiz-platform. Update Purpose after archive.
## Requirements
### Requirement: API 服务
系统 MUST 暴露 RESTful API 服务(后端 FastAPI),供前端 + 第三方集成调用;V1.0+ 必含,MVP 仅内部调用。

#### Scenario: API 调用
- **WHEN** 第三方应用通过 HTTPS 调 POST /api/v1/workflows
- **THEN** 系统 MUST:① 验证 Bearer token(从 system-management SSO 拿到) ② 校验权限(RBAC) ③ 执行业务逻辑 ④ 返回 201 + workflow ID

### Requirement: 自动生成 API
系统 MUST 从 workflow / agent 定义自动生成 OpenAPI 3.0 规范,供前端 SDK 生成。

#### Scenario: OpenAPI 生成
- **WHEN** 管理员点击"导出 OpenAPI"
- **THEN** 系统 MUST 生成完整 OpenAPI 3.0 JSON / YAML,含所有 endpoint + request/response schema + auth + 错误码

### Requirement: API Key 鉴权
系统 MUST 支持 API Key 鉴权(为非 SSO 用户);API Key 关联 user + workspace + 权限范围。

#### Scenario: API Key 创建
- **WHEN** 用户创建 API Key(名称 + 权限范围)
- **THEN** 系统 MUST 生成随机 key(显示一次 + 持久化 hash);key 必须含 user_id + workspace + scopes;过期可配置

#### Scenario: API Key 使用
- **WHEN** 第三方应用用 API Key 调 API
- **THEN** 系统 MUST 验证 key 有效 + 在权限范围内;audit log 记录调用

### Requirement: MCP Server 暴露
系统 MUST 把自己作为 MCP server 暴露(V1.0+),让外部 Agent(如 Claude Code)调用本平台的能力。

#### Scenario: 外部 MCP 客户端
- **WHEN** 外部 Claude Code 配置本平台 MCP server (stdio 或 SSE)
- **THEN** 系统 MUST 暴露工具(workflow 列表 / workflow 执行 / knowledge 检索);调用经数据隔离网关 + 凭证 + RBAC 校验

### Requirement: API 限流
API Gateway MUST 实现 per-API-Key / per-user / per-IP 的限流(RPM / 并发数);超限 MUST 返回 429。

#### Scenario: API 超限
- **WHEN** 同一 API Key 1 分钟内 1000 次调用,超过 quota (默认 600 RPM)
- **THEN** 系统 MUST 返回 429 + Retry-After header;audit log 记录

### Requirement: API 文档
系统 MUST 提供 Swagger UI(自动从 OpenAPI 规范渲染)供开发者浏览 API;V1.0+ 必含。

#### Scenario: 访问 API 文档
- **WHEN** 开发者打开 /api/docs
- **THEN** 系统 MUST 渲染 Swagger UI,显示所有 endpoint + 在线试用

