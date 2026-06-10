# system-management Specification

## Purpose
TBD - created by archiving change add-chatbiz-platform. Update Purpose after archive.
## Requirements
### Requirement: 用户管理
系统 MUST 支持用户的 CRUD(创建 / 查询 / 修改 / 禁用);每用户含邮箱、姓名、角色、所属部门、状态。

#### Scenario: 创建用户
- **WHEN** 管理员创建新用户(邮箱 + 姓名 + 角色 + 部门)
- **THEN** 系统 MUST 持久化用户;邮箱 MUST 唯一;初始密码 MUST 强制首次登录修改

#### Scenario: 禁用用户
- **WHEN** 管理员禁用某用户
- **THEN** 系统 MUST 把用户状态置为 disabled,该用户 MUST 无法登录 / API 调用;其创建的 workflow / agent MUST 标记为"原创建者已禁用",不自动删除

### Requirement: 角色管理
系统 MUST 支持角色 CRUD;角色绑定权限(权限粒度 = cap 级别 + cap 内子功能级别)。

#### Scenario: 创建角色
- **WHEN** 管理员创建角色 "财务分析师",勾选权限:[workflow-engine: read, write], [knowledge-base: read], [agent-runtime: execute]
- **THEN** 系统 MUST 持久化角色;用户绑定该角色后 MUST 仅能调用上述权限

### Requirement: 部门管理
系统 MUST 支持部门的 CRUD;部门可嵌套(树形结构);用户属于一个部门。

#### Scenario: 创建子部门
- **WHEN** 管理员在 "财务部" 下创建子部门 "华东财务"
- **THEN** 系统 MUST 持久化子部门;路径 = "财务部 / 华东财务"

### Requirement: RBAC 权限校验
系统 MUST 在每次 API 调用前校验当前用户是否有所需权限;无权限 MUST 返回 403,audit log 记录。

#### Scenario: 无权限访问
- **WHEN** 用户(角色 = 财务分析师)尝试 DELETE /api/workflows/{id}
- **THEN** 系统 MUST 返回 403;audit log 记录用户 id + 资源 + 操作 + 时间

### Requirement: 单租户隔离
系统 MUST 在单租户内网部署,所有数据通过 workspace_id 列进行逻辑隔离(不物理多租户);同一 workspace 内数据共享,跨 workspace 数据 MUST 不可见。

#### Scenario: Workspace 隔离
- **WHEN** 用户 A(workspace=finance)查询 workflow
- **THEN** 系统 MUST 仅返回 workspace=finance 的 workflow;跨 workspace 访问 MUST 拒绝

### Requirement: 配额管理
系统 MUST 支持 per-workspace 配额(用户数 / workflow 数 / agent 数 / 月度 token 用量);超配额 MUST 拒绝并提示。

#### Scenario: 超配额创建
- **WHEN** workspace 已达 max_workflows=10,用户尝试创建第 11 个
- **THEN** 系统 MUST 拒绝并提示 "已达 workflow 上限 10,联系管理员扩容"

### Requirement: SSO 集成
MVP 阶段 MUST 集成企微 / 钉钉扫码登录(任选其一,V1.0+ 完整);SSO MUST 跳过本系统密码,直接信任 IM 平台身份。

#### Scenario: 企微扫码登录
- **WHEN** 用户扫码企微
- **THEN** 系统 MUST 从企微回调获取 user_id,匹配本系统用户(邮箱前缀),登录成功;无匹配 MUST 提示联系管理员开通账号

