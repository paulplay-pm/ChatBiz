# credential-management (implementation change)

> **eng-review refs:** (无强相关)
> **depends on:** (无,本 cap 是基础)
> **source:** `openspec/specs/credential-management/spec.md` (canonical,5 Requirements,5 Scenarios)
> **本 change 的 spec 是对 canonical 的 ADDED delta** —— 实施时新增的、canonical 没规定的工程要求(部署 / 性能 / 集成测试 / 主密钥轮换等)

## ADDED Requirements

### Requirement: 主密钥加载
系统 MUST 在服务启动时从 PostgreSQL `encryption_keys` 表加载当前主密钥到进程内存;加载失败 MUST 阻断服务启动。

#### Scenario: 启动时主密钥加载成功
- **WHEN** 服务启动且 `encryption_keys` 表含 active 主密钥记录
- **THEN** 系统 MUST 在 5s 内加载主密钥到内存,服务正常启动;启动日志 MUST 写入 audit-and-isolation 的统一 audit log

#### Scenario: 启动时主密钥缺失
- **WHEN** 服务启动且 `encryption_keys` 表无 active 主密钥记录
- **THEN** 系统 MUST 阻断启动,exit code 1,日志明示"主密钥未配置";部署脚本 MUST 引导生成主密钥

### Requirement: 主密钥轮换
系统 MUST 支持 1 年 1 次的主密钥轮换;轮换过程 MUST 在 60s 内完成,不停机。

#### Scenario: 触发主密钥轮换
- **WHEN** 管理员通过 admin API 触发主密钥轮换
- **THEN** 系统 MUST:① 生成新主密钥 ② 用新主密钥重新加密所有 DEK(per-credential 数据密钥) ③ DEK 物理位置不变 ④ 旧主密钥标记 retired ⑤ 整个过程 MUST 在 60s 内完成 ⑥ audit log 记录轮换事件(不含主密钥明文)

### Requirement: 凭证值 AES-256-GCM envelope encryption
系统 MUST 对每个凭证值用 per-credential DEK(32-byte 随机)通过 AES-256-GCM 加密;DEK 本身 MUST 用主密钥加密存储。

#### Scenario: 创建凭证
- **WHEN** 用户通过 API 创建凭证(名称、类型、值)
- **THEN** 系统 MUST:① 生成 32-byte 随机 DEK ② 用 DEK + AES-256-GCM(96-bit nonce)加密凭证明文 ③ 用主密钥加密 DEK 存 `encrypted_dek` 列 ④ 持久化到 PostgreSQL ⑤ 明文 MUST 0 时刻入 audit log 或留内存(除用户填入瞬间外)

#### Scenario: 解密凭证(use API)
- **WHEN** 内部 cap 通过 `POST /api/v1/credentials/{id}/use` 请求明文
- **THEN** 系统 MUST:① 用主密钥解出 DEK ② 用 DEK + AES-256-GCM 解出凭证明文 ③ 写 audit log(user_id / cap / 凭证 ID hash / 调用目的 / 不含明文) ④ 在 < 50ms 内返回明文

### Requirement: 凭证轮换双值窗口期
系统 MUST 在凭证轮换时保留旧值 30 天;旧值 `previous_expires_at` < 当前时间的行由 cron job 物理清空。

#### Scenario: 凭证轮换
- **WHEN** 管理员通过 API 轮换凭证(填入新值)
- **THEN** 系统 MUST:① 用新 DEK 加密新值 ② 把旧值 + 旧 DEK 移到 `previous_*` 列 ③ 设 `previous_expires_at = now() + 30 days` ④ 新值立即生效 ⑤ audit log 记录轮换事件

#### Scenario: use API 优先用新值
- **WHEN** 凭证被轮换且在 30 天窗口期内,内部 cap 调 `use` API
- **THEN** 系统 MUST 优先用新值解密;若新值有损坏(罕见),回退到 `previous_*` 旧值(若仍未过期)

#### Scenario: cron job 清理过期旧值
- **WHEN** 每天 0 点 cron job 运行
- **THEN** 系统 MUST 扫 `previous_expires_at < now()` 的行,物理清空 `previous_value` / `previous_encrypted_dek` / `previous_expires_at` 列;audit log 记录清理条数

### Requirement: 凭证使用频率限制
系统 MUST 对 `reveal` API 实施频率限制(每用户每分钟 ≤ 10 次);超出 MUST 返回 429。

#### Scenario: 频率超限
- **WHEN** 用户在 1 分钟内调 `reveal` API 11 次
- **THEN** 系统 MUST 返回 429 + Retry-After header;audit log 记录频率超限事件(user_id / 凭证 ID / 时间 / 不含明文)

### Requirement: 凭证类型实现
系统 MUST 实现 4 类凭证:api_key / oauth2 / database / smtp;每类 MUST 有类型特定的字段验证。

#### Scenario: api_key 类型验证
- **WHEN** 用户创建类型为 api_key 的凭证,值长度 > 0 且 < 4096
- **THEN** 系统 MUST 接受;api_key 无附加字段

#### Scenario: oauth2 类型验证
- **WHEN** 用户创建类型为 oauth2 的凭证,需填入 client_id / client_secret / token_url / scope
- **THEN** 系统 MUST 验证 4 个字段都非空且 url 格式合法;缺失字段 MUST 返回 400

### Requirement: 凭证列表分页
系统 MUST 对 `GET /api/v1/credentials` 实施 page-based 分页(每页 20 条,page_size 最大 100)。

#### Scenario: 列表分页
- **WHEN** 用户调 `GET /api/v1/credentials?page=1&page_size=20&type=api_key`
- **THEN** 系统 MUST 返回 20 条 api_key 类型凭证 + total_count;page_size > 100 MUST 返回 400

### Requirement: 凭证访问审计
系统 MUST 记录每次凭证的访问(创建 / 轮换 / 删除 / reveal / use / 查看);audit log MUST 含 user_id / 凭证 ID(明文 hash)/ 动作 / 时间 / 成功失败,但 MUST NOT 含凭证明文。

#### Scenario: 创建凭证审计
- **WHEN** 管理员创建凭证
- **THEN** 系统 MUST 写 audit log:user_id + 凭证 ID (SHA256 前 8 字节) + 动作 = "create" + 时间 + 成功;MUST NOT 含凭证明文

#### Scenario: reveal API 审计
- **WHEN** admin 调 `reveal` API
- **THEN** 系统 MUST 写 audit log:user_id + 凭证 ID hash + 动作 = "reveal" + 时间 + 成功;含 "此操作暴露明文" warning 字段供 audit 复查

#### Scenario: use API 审计
- **WHEN** 内部 cap 调 `use` API
- **THEN** 系统 MUST 写 audit log:user_id + 凭证 ID hash + 动作 = "use" + 时间 + 调用目的(由调用方传参);成功 / 失败都记

### Requirement: 凭证过期提醒
系统 MUST 在凭证过期前 7 天 / 1 天 / 当天 各触发 1 次企微 webhook 通知管理员;过期凭证 MUST 拒绝被 use / reveal。

#### Scenario: 凭证过期前 7 天提醒
- **WHEN** 凭证 expiry 距今 7 天
- **THEN** 系统 MUST POST 企微 webhook 推送提醒消息(含凭证名称、ID hash、过期时间、续期操作指引)

#### Scenario: 凭证过期后拒绝
- **WHEN** 凭证 expiry < 当前时间
- **THEN** 系统 MUST 拒绝 `use` / `reveal` API,返回错误 "凭证已过期,请轮换";audit log 记录

### Requirement: 数据库 schema
系统 MUST 在 PostgreSQL 创建 3 张表:`credentials` / `encryption_keys` / `credential_audit`;每张表含必要的索引 + 约束。

#### Scenario: credentials 表结构
- **WHEN** Alembic 迁移运行
- **THEN** 系统 MUST 创建 `credentials` 表含:id (PK) / name / type / encrypted_value / encrypted_dek / previous_value / previous_encrypted_dek / previous_expires_at / workspace_id / expires_at / created_at / updated_at + 索引 on (workspace_id, type), (expires_at)

#### Scenario: encryption_keys 表结构
- **WHEN** Alembic 迁移运行
- **THEN** 系统 MUST 创建 `encryption_keys` 表含:id (PK) / key_id (UUID) / encrypted_key (BYTEA) / status (active / retired) / created_at / retired_at + 索引 on (status)

#### Scenario: credential_audit 表结构
- **WHEN** Alembic 迁移运行
- **THEN** 系统 MUST 创建 `credential_audit` 表含:id (PK) / timestamp / user_id / credential_id_hash (8 字节 SHA256) / action / cap / purpose / success + 索引 on (timestamp), (credential_id_hash, timestamp), (user_id, timestamp)

### Requirement: 数据库回滚测试
系统 MUST 在迁移脚本中包含 `downgrade()` Alembic 步骤,支持完整回滚到迁移前 schema。

#### Scenario: 回滚迁移
- **WHEN** 运维执行 `alembic downgrade -1`
- **THEN** 系统 MUST 删 3 张表(credentials / encryption_keys / credential_audit)的所有索引 + 约束 + 表;数据全丢但 schema 回滚干净

### Requirement: 多租户隔离测试
系统 MUST 验证凭证查询 MUST 仅返回当前 workspace 的凭证;跨 workspace 访问 MUST 拒绝。

#### Scenario: workspace 隔离查询
- **WHEN** 用户 A(workspace=finance)查询凭证列表
- **THEN** 系统 MUST 仅返回 workspace=finance 的凭证;跨 workspace 访问 MUST 拒绝(403)

### Requirement: 集成测试
系统 MUST 在 `tests/integration/` 提供覆盖所有 6 个 endpoint 的集成测试;`tests/e2e/` 提供 1 个 end-to-end 流程(创建 → 轮换 → use → 清理)。

#### Scenario: 6 个 endpoint 集成测试
- **WHEN** pytest 跑集成测试
- **THEN** 系统 MUST 100% 通过 6 个 endpoint 的 happy path + 失败 path 集成测试;PostgreSQL 必须用 testcontainers 临时实例

#### Scenario: end-to-end 流程
- **WHEN** pytest 跑 e2e
- **THEN** 系统 MUST 100% 通过"创建 → 轮换 → use → cron 清理"全流程;新值 + 旧值 + audit 3 个视角都验证

### Requirement: 性能基线
系统 MUST 保证 `use` API P99 < 50ms 在 100 RPS 压测下(单 VM + docker-compose)。

#### Scenario: 100 RPS use API
- **WHEN** locust 跑 100 RPS 持续 60s
- **THEN** 系统 MUST P99 < 50ms;P99 > 50ms MUST 触发 monitoring 告警
