<!--
Raw capture of superpowers:brainstorming output for implement-credential-management.

Captured 2026-06-10 during /openspec-propose.
This change IMPLEMENTS openspec/specs/credential-management/spec.md (5 Requirements, 5 Scenarios).
The spec is the contract; this brainstorm captures implementation design choices.

Reference:
  - 契约: /Users/paulwang/work/ChatBiz/openspec/specs/credential-management/spec.md
  - PRD:   docs/prd.md §8.2 (凭证管理 P0)
  - openspec config: openspec/config.yaml (中文 + 后端 SQLAlchemy ORM + 审计埋点)
  - eng-review: 12 个 locked-in 决策,引用 [ENG-#N]
-->

# Brainstorm: implement-credential-management

## 背景

`openspec/specs/credential-management/spec.md` 已经定下 5 个 Requirement。本 change 实施它,不做 spec 重新设计,只做"如何实现"。

5 个 Requirement:
1. 凭证 CRUD(创建/查询/修改/轮换) — 含加密存储
2. 凭证引用(其他 cap 通过 ID 引用,不解密传明文)
3. 凭证访问审计(每次解密都入 audit log,不含明文)
4. 凭证权限(谁能查看 vs 谁能使用,凭证值不暴露给非管理员)
5. 凭证过期(过期前 7 天提醒,过期后拒绝使用)

这个 cap 是月1 Lane A,**所有其他 cap(workflow-engine / agent-runtime / model-management / channel-management / plugin-market / knowledge-base)**都通过凭证 ID 引用本 cap。**所以本 cap 是 P0 阻塞** —— 越早上线越好,其他 cap 实施时直接调,不需要 mock。

## 决议链

### Q1: 加密方案 — KMS vs 自研 AES-256
- **决议**:**自研 AES-256-GCM**。
- **理由**:
  - 内网部署,没有云 KMS(Aliyun KMS / AWS KMS)可调
  - 自研 AES-256-GCM 用 cryptography Python 包(工业级 + FIPS 验证)+ 32 字节随机密钥存 PostgreSQL 的 encryption_keys 表
  - GCM 模式自带认证,防篡改
  - MVP 阶段不需要 KMS 那种"密钥轮换 + HSM"复杂度
- **被拒方案**:
  - AWS / Aliyun KMS — 内网无外网,且企业合规不允许
  - Vault — 引入新中间件,5-7 FTE 没时间运维它
  - 简单 XOR / DES — 不安全,不可接受

### Q2: 主密钥存哪
- **决议**:**主密钥(master encryption key)存 PostgreSQL 的 `encryption_keys` 表**,启动时加载到进程内存。
- **理由**:
  - 内网部署,没有 HSM 也没 KMS,PostgreSQL 是最安全的可用存储
  - encryption_keys 表单独 schema 权限控制(只有 credential-management 服务账号能读)
  - 启动时加载一次,运行时全部加密/解密在内存
- **风险**:
  - 内存 dump 可能泄露(可接受:内网无外部攻击面)
  - PostgreSQL 备份泄露(可接受:备份同样内网存储)
  - 未来可演进到 Vault 或 HSM,通过把 `encryption_keys` 表换成 Vault lookup 即可,接口不变

### Q3: 密钥轮换
- **决议**:**主密钥 1 年轮换 1 次**(季度手动 + 自动提醒);**数据密钥 per-credential**(KMS-style envelope encryption)。
- **理由**:
  - 主密钥轮换需要重新加密所有 credential,代价大,1 年 1 次足够
  - per-credential 数据密钥:每次新建凭证时生成 1 个 32 字节随机 DEK,用主密钥加密 DEK 存到 `encrypted_dek` 列
  - 使用时:用主密钥解出 DEK → 用 DEK 解出明文
  - 主密钥轮换 = 用新主密钥重新加密所有 DEK,明文凭证不动
- **被拒方案**:
  - 单层(全部用主密钥直接加密凭证) — 主密钥轮换时需要重新加密所有凭证,停机时间长
  - 不轮换 — 合规过不去

### Q4: 凭证 ID 格式
- **决议**:`cred_<32-char-base62>`,共 34 字符。
- **理由**:
  - 32 字符 base62 = 190 bits 熵,碰撞概率可忽略
  - `cred_` 前缀便于在日志/调试时识别
  - URL-safe(无 `_` `-` 之外的特殊字符)
- **使用**:
  - 其他 cap 引用时只存 `cred_xxx` 字符串
  - database 索引(主键)

### Q5: 凭证值展示掩码
- **决议**:`cred_xxxx****xxxx`(前 4 后 4,中间 4 个 `*`)。
- **理由**:
  - spec Requirement 1 Scenario 写明"前 4 后 4 中间 \*\*\*\*"
  - 即使是掩码也不入 audit log(只入"凭证被查看"事件,不含值)
- **边界**:
  - 凭证值长度 < 8 字符 → 全部显示 `****`
  - 凭证值长度 ≥ 8 字符 → `前 4 + **** + 后 4`

### Q6: 访问权限模型
- **决议**:**2 类权限独立**:
  - **查看**(read):看到凭证元数据(名称/类型/关联资源/过期时间/掩码),不含明文
  - **使用**(use):解密凭证值,供其他 cap 调外部服务时使用
- **理由**:
  - Spec Requirement 4 写明"凭证值永远 MUST NOT 暴露给非管理员角色"
  - 实施时:admin 角色有 read + use;其他角色只有 use(用的时候不查看到明文)
  - 凭证值明文只允许在以下场景出现:① 凭证刚被用户填入的瞬间(还在 UI)② 凭证被调外部服务时(通过内部 API 给调用方)
- **API 设计**:
  - `GET /api/v1/credentials` — 列表,含元数据,不含明文
  - `GET /api/v1/credentials/{id}` — 详情,含元数据 + 掩码,不含明文
  - `POST /api/v1/credentials/{id}/reveal` — 返回明文(限 admin + 写 audit log)
  - `POST /api/v1/credentials/{id}/use` — 内部 API,其他 cap 调;返回明文供调用方使用;写 audit log

### Q7: 凭证轮换的实现
- **决议**:**30 天双值窗口期**(旧值标记 `expired_at = now()`,新值立即生效,旧值仍可解密到 30 天后)。
- **理由**:
  - Spec Requirement 1 Scenario 写明"30 天保留"
  - 30 天足够"哦我刚刚轮换了但有依赖方还没切换"的回滚期
  - 30 天后旧值物理删除
- **实施**:
  - `credentials` 表加 `previous_encrypted_value` + `previous_encrypted_dek` + `previous_expires_at` 列
  - 轮换时:新值写 `encrypted_value` / `encrypted_dek`,旧值移到 `previous_*` 列
  - `use` API:优先用 `encrypted_value`,回退到 `previous_*` 如果 `previous_expires_at > now()`
  - 清理 job:每天 0 点扫 `previous_expires_at < now()` 的行,物理清空 `previous_*` 列

### Q8: 凭证类型支持范围
- **决议**:**MVP 支持 4 类**:api_key(默认) / oauth2 / database / smtp。
- **理由**:
  - api_key:OpenAI / Claude / DeepSeek / 文心 / 通义全部用 API Key
  - oauth2:飞书 / 钉钉 / 企微的 OAuth 流程
  - database:leo 的"提工单让研发查数据库"场景
  - smtp:邮件通知渠道(凭证过期提醒)
  - 未来可加(不在 MVP):ssh_key / jwt / custom

### Q9: 通知渠道(凭证过期提醒)
- **决议**:**MVP 用企微 webhook**,其他渠道 V1.0+ 补。
- **理由**:
  - Spec Requirement 5 Scenario 写"企微/邮件/站内信 至少 1 个"
  - 企微 webhook 是企业内最普及的 IM 通道
  - 实施:在 credential-management 服务内嵌一个简单的 webhook 发送器,POST 到配置的 URL
  - 凭证过期前 7 天 / 1 天 / 当天 各发 1 次

### Q10: 凭证服务对其他 cap 的 API
- **决议**:**RESTful HTTP + JSON**,FastAPI 暴露 4 个 endpoint:
  - `POST /api/v1/credentials` — 创建
  - `GET /api/v1/credentials` — 列表(分页 + 筛选)
  - `GET /api/v1/credentials/{id}` — 详情(含掩码)
  - `POST /api/v1/credentials/{id}/rotate` — 轮换
  - `POST /api/v1/credentials/{id}/reveal` — 返回明文(admin only)
  - `POST /api/v1/credentials/{id}/use` — 内部 API,返回明文
  - `DELETE /api/v1/credentials/{id}` — 删除(物理)
- **理由**:
  - 内网,HTTP 而非 gRPC 已经够用,简单
  - 跟其他 cap 实施 change 的接口一致
  - 用 Bearer token 鉴权(API Key 模式,V1.0+ 加完整 SSO)

### Q11: 数据库 schema
- **决议**:**3 张表**:
  - `credentials` (主表)
  - `encryption_keys` (主密钥元数据)
  - `credential_audit` (审计,跟 audit-and-isolation 的 audit 表隔离)
- **理由**:
  - 主表 + 主密钥 + 审计 三类职责分离
  - 审计写 audit-and-isolation 的统一 audit log 表更标准,但 MVP 阶段 credential-management 单独表足够(独立部署 + 独立 retention)
  - 未来可演进:写 audit-and-isolation 的统一表

### Q12: 凭证 ID 跨 cap 引用
- **决议**:**纯字符串 ID**(无类型化,无 namespace)。
- **理由**:
  - 简化:其他 cap 引用 = 一个 string column
  - 不需要引入 UUID 库 / namespace 系统
  - 未来如果需要按 cap 分组,加 `credential_namespace` 列即可

## 设计取捨

### T1: 缓存 vs 不缓存明文
**不缓存明文**。每次 `use` 都从 DB 解密。明文 0 时刻在内存外。

理由:缓存是攻击面,凭证被缓存到 Redis / 内存后,泄露路径多 1 个。不接受。

### T2: 凭证列表分页
**page-based 分页,每页 20 条**。`?page=1&page_size=20&type=api_key&status=active`。

理由:spec 没规定,简单分页足够 MVP。cursor-based 分页 V1.0+ 再考虑(凭证数量预期 < 100)。

### T3: 多租户 vs 单租户
**单租户**。凭证 不按 workspace 隔离(spec 单租户决策)。

理由:跟 system-management 一致(单租户 + workspace_id 列逻辑隔离)。MVP 阶段凭证是 workspace-level 资源,所有 workspace 共享。

### T4: API Key 鉴权 vs 完整 SSO
**MVP 用 API Key 鉴权**。API Key 本身存于本服务的 master credential 表(自举)。

理由:跟 spec system-management 的 §SSO 集成 一致(企微扫码 V1.0+ 补)。MVP 阶段 API Key 够用,因为是服务间调用,不是用户登录。

### T5: 凭证值长度限制
**最长 4096 字符**(对应 RSA private key / 长 OAuth token)。

理由:超过 4096 字符的凭证值罕见(API Key 通常 50-200 字符)。如果真有,用户应该用文件上传(V2.0+)。

## Open Questions

1. **凭证加密 vs 凭证访问授权**:两个权限独立(read vs use),是否要更细粒度(per-resource / per-credential 级别)?MVP 不做,V1.0+ 考虑。
2. **凭证批量操作**(批量创建 / 批量轮换):MVP 不做,V1.0+ 补。
3. **凭证版本历史**(每次轮换保留 N 个历史版本):MVP 只保留 1 个 previous,V1.0+ 考虑 N。
4. **凭证使用频率监控**(每分钟 / 每小时使用次数):MVP 不做,V1.0+ 在 monitoring cap 补。
5. **凭证共享**(其他用户 / 其他 workspace 看同一凭证):MVP 凭证是 workspace-level 共享,V1.0+ 可加 per-user ACL。
6. **凭证撤销**(误填凭证后立即销毁,不等 30 天):MVP 不做,V1.0+ 加强制撤销 API。
7. **凭证加密密钥的物理位置**(encryption_keys 表是否需要单独 PostgreSQL 实例?):MVP 同实例,后续按合规要求拆分。

## 跟 spec 的对应

- Req 1 (凭证 CRUD) ↔ Q4 (ID 格式) + Q5 (掩码) + Q7 (轮换) + Q8 (类型) + Q11 (schema)
- Req 2 (凭证引用) ↔ Q12 (跨 cap ID 引用) + Q6 (use API)
- Req 3 (凭证访问审计) ↔ Q11 (audit 表) + 设计 §T1 (不缓存明文)
- Req 4 (凭证权限) ↔ Q6 (read vs use 分离) + Q10 (API 设计)
- Req 5 (凭证过期) ↔ Q7 (30 天窗口) + Q9 (通知渠道)

## 跟 eng-review 12 决策的对应

- 不触及任何 [ENG-#N] —— 本 cap 是基础能力,没有架构决策依赖。
- 间接引用:本 cap 的 `use` API 被 `audit-and-isolation` 网关调用,符合 [ENG-Arch #1] 网关 = egress 强制点的设计。
- 数据模型:credential 表结构配合 [ENG-Quality #2] 状态双层设计(workflow state in PostgreSQL,这个 cap 也在 PostgreSQL),保证状态一致。
- 测试:[ENG-Test #1] 3 层金字塔,本 cap 实施时单元 + 集成 + E2E(LangGraph 集成不在本 cap)。
