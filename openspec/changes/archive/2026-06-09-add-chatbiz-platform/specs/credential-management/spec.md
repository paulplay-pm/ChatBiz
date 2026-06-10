# credential-management

> **eng-review refs:** (无强相关)
> **depends on:** [audit-and-isolation]
> **source:** `docs/prd.md` §8.2 (凭证管理 P0)

## ADDED Requirements

### Requirement: 凭证 CRUD
系统 MUST 支持凭证的 CRUD;凭证含名称、类型(api_key / oauth / database / smtp 等)、值(value 加密存储)、关联的资源、过期时间、备注。

#### Scenario: 创建凭证
- **WHEN** 用户填入凭证(名称、类型、值)
- **THEN** 系统 MUST 加密存储值(用 KMS 或自研加密,AES-256);UI 上 MUST 永远只显示掩码(前 4 后 4 中间 \*\*\*\*);凭证明文 MUST 不入 audit log

#### Scenario: 凭证轮换
- **WHEN** 用户轮换某凭证(填入新值)
- **THEN** 系统 MUST:① 新值加密 ② 旧值标记 expired_at 保留 30 天(用于回滚) ③ 新值立即生效

### Requirement: 凭证引用
其他 capability 调用凭证 MUST 通过 credential-management 引用凭证 ID,禁止直接传明文或自行存储。

#### Scenario: model-management 引用凭证
- **WHEN** model-management 创建新模型,选择已存储的凭证
- **THEN** 系统 MUST 只保存凭证 ID 引用,API 调用时由 credential-management 临时解密注入

### Requirement: 凭证访问审计
系统 MUST 记录每次凭证的访问(谁、何时、用于哪个 cap、是否成功);audit log MUST 含凭证 ID 但 MUST NOT 含明文。

#### Scenario: 凭证被使用
- **WHEN** workflow 执行时 credential-management 解密凭证供 gateway 使用
- **THEN** 系统 MUST 写入 audit log:时间 + 用户 + cap + 凭证 ID(明文 hash) + 调用目的;明文 MUST NOT 入 log

### Requirement: 凭证权限
系统 MUST 支持凭证的访问控制(谁能查看 / 谁能使用);凭证值永远 MUST NOT 暴露给非管理员角色。

#### Scenario: 无权限查看
- **WHEN** 财务分析师(无 admin 权限)尝试查看凭证值
- **THEN** 系统 MUST 拒绝并返回 403;audit log 记录尝试

### Requirement: 凭证过期
系统 MUST 在凭证过期前 7 天通过通知渠道提醒管理员;过期凭证 MUST 不能被使用。

#### Scenario: 凭证过期前提醒
- **WHEN** 凭证 expiry 距今 7 天
- **THEN** 系统 MUST 触发通知(企微/邮件/站内信);过期 MUST 拒绝使用并提示"凭证已过期,请轮换"
