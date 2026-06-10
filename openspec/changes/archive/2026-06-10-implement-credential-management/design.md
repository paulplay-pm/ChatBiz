# design: implement-credential-management

## Context

本 change 实施 `openspec/specs/credential-management/spec.md` 的 5 个 Requirement(凭证 CRUD / 引用 / 审计 / 权限 / 过期)。spec 是契约,本设计说明"如何实现"。

**Stakeholders:**
- paul / leo / anny(凭证消费者)
- C-level sponsor(9-12 月预算承诺)
- 月 2+ 启动的 6 个 cap(凭证消费者):workflow-engine / agent-runtime / model-management / channel-management / plugin-market / knowledge-base
- 5-7 FTE 实施团队(month 1 分配 1 后端 + 1 全栈)

**架构对齐:**
- 后端:Python (FastAPI)+ SQLAlchemy ORM + 异步 + 审计埋点 → 符合 `openspec/config.yaml` §rules + Arch §4.4
- 数据库:PostgreSQL 16+(单租户内网,无物理多租户)→ 符合 [ENG-Quality #2] 状态双层设计
- 加密:自研 AES-256-GCM(无云 KMS / 无 Vault)→ 内网限制
- 部署:单 VM + docker-compose month 1-3,不引入 K8s

## Goals / Non-Goals

**Goals:**
- 实施 5 个 spec Requirement(凭证 CRUD / 引用 / 审计 / 权限 / 过期)
- 暴露 6 个 RESTful HTTP endpoint
- 自研 AES-256-GCM 加密 + per-credential DEK envelope encryption
- 30 天凭证轮换双值窗口期
- 凭证访问审计(本地表,V1.0 写统一 audit log)
- 凭证过期 7 天前企微 webhook 提醒
- 完整 3 层测试金字塔(单元 + 集成 + E2E)
- 跟 spec `credential-management` 的 5 个 Requirement 1:1 对应,Scenario 全部可验证

**Non-Goals:**
- 不实施 SSO(企微/钉钉扫码)— V1.0+ 跟随 system-management 的 SSO 集成
- 不实施 per-user ACL — MVP 凭证是 workspace-level 共享
- 不实施凭证版本历史(>1 previous)— MVP 只保留 1 个 previous
- 不实施批量操作 — V1.0+ 补
- 不实施强制撤销 API — V1.0+ 补
- 不实施凭证使用频率监控 — V1.0+ 在 monitoring cap 补
- 不实施 multi-region / HSM / KMS / Vault — 复杂度超出 MVP 范围
- 不修改 `openspec/specs/credential-management/spec.md`(spec 是契约,实施不动契约)
- 不实施 webhook 签名验证(企微 webhook)— MVP 内网 + API Key 鉴权,签名 V1.0+ 补

## Decisions

### D1: 加密方案 — 自研 AES-256-GCM
- **选择**:用 `cryptography` Python 包(工业级 + FIPS 验证)的 AES-256-GCM(96-bit nonce + 16-byte auth tag)。
- **理由**:
  - GCM 模式自带认证(防篡改),相比 CBC + HMAC 简单 1 个原语
  - `cryptography` 包由 PyCA 维护,OpenSSL 后端,广泛使用
  - MVP 不需要 KMS / HSM,自研 + 工业级库足够
- **被拒 alternative**:
  - Aliyun KMS / AWS KMS — 内网无外网,且企业合规不允许
  - HashiCorp Vault — 引入新中间件,5-7 FTE 没时间运维
  - AES-CBC + HMAC — 比 GCM 复杂,实施易错
  - 简单 XOR — 不安全

### D2: 主密钥存 PostgreSQL 的 `encryption_keys` 表
- **选择**:主密钥元数据(创建时间、用途、状态)存 `encryption_keys` 表,启动时加载到进程内存,运行时全在内存加解密。
- **理由**:
  - 内网无 HSM,PostgreSQL 是最安全可用存储
  - `encryption_keys` 表单独 schema 权限控制(只有 credential 服务账号能读)
  - 启动一次,运行时无磁盘 I/O
- **被拒 alternative**:
  - 主密钥存环境变量 — 重启 / 部署时易泄露
  - 主密钥存文件 — 同上,且易误 commit
  - 主密钥存 Vault — 见 D1 拒绝理由

### D3: Per-credential DEK envelope encryption
- **选择**:每次新建凭证生成 1 个 32-byte 随机 DEK(Data Encryption Key),用主密钥加密 DEK 存到 `encrypted_dek` 列。运行时用主密钥解出 DEK,再用 DEK 解出凭证明文。
- **理由**:
  - 主密钥轮换 = 用新主密钥重新加密所有 DEK,明文凭证不动(无需重新加密所有凭证,几秒完成)
  - 未来可演进:per-tenant DEK、per-resource DEK,加 `dek_metadata` 列即可
- **被拒 alternative**:
  - 单层(全部用主密钥直接加密凭证)— 主密钥轮换时需要重新加密所有凭证,停机时间长

### D4: 主密钥 1 年轮换 1 次
- **选择**:季度手动 + 自动提醒;1 年强制 1 次。
- **理由**:
  - 主密钥轮换代价大(D3 后变小但仍需扫表)
  - 1 年 1 次符合 NIST SP 800-57 推荐(对称密钥 1-2 年)
  - 自动提醒:季度 0 点 job 检查,距 1 年 < 30 天时通知 admin
- **被拒 alternative**:
  - 不轮换 — 合规过不去
  - 每月轮换 — 运营成本过高

### D5: 凭证 ID 格式 = `cred_<32-char-base62>`
- **选择**:34 字符 ID,32 字符 base62 随机 = 190 bits 熵,`cred_` 前缀便于调试。
- **理由**:
  - URL-safe + DB 主键
  - 跨 cap 引用只需一个 string column
- **被拒 alternative**:
  - UUID — 32 字符 hex 可读性差,需要库依赖
  - 整数自增 — 安全风险(可预测,泄露数量)

### D6: 凭证值展示掩码 = `前 4 + **** + 后 4`
- **选择**:前 4 后 4,中间 4 个 `*`。值长度 < 8 字符 → 全部 `****`。
- **理由**:
  - spec Requirement 1 Scenario 明确规定
  - 边界值处理:短凭证全部遮蔽(避免 `1****` 泄露长度信号)
- **被拒 alternative**:
  - 显示中间 N 字符 — 易泄露

### D7: 2 类权限(read vs use)独立
- **选择**:`read`(看到元数据 + 掩码)和 `use`(解密明文)2 类独立。admin 有 read + use,其他角色只有 use(用的时候自动解密,看不到明文)。
- **理由**:
  - spec Requirement 4 明确"凭证值永远 MUST NOT 暴露给非管理员角色"
  - 2 类分离允许更多实施角色(例如 凭证查看员 + 凭证使用员 拆开)
- **API 设计**:
  - `GET /api/v1/credentials` — 列表(need read)
  - `GET /api/v1/credentials/{id}` — 详情 + 掩码(need read)
  - `POST /api/v1/credentials/{id}/reveal` — 明文(need read + admin 角色)
  - `POST /api/v1/credentials/{id}/use` — 内部 API,明文(need use)
  - `POST /api/v1/credentials` / `POST /{id}/rotate` / `DELETE /{id}` — 写操作(need write 角色)

### D8: 30 天轮换双值窗口
- **选择**:旧值标记 `expired_at = now()`,新值立即生效,旧值 30 天后物理清空。
- **理由**:
  - spec Requirement 1 Scenario 明确 30 天
  - 30 天足够回滚期
  - 每天 0 点 cron job 扫 `previous_expires_at < now()` 的行,清空 `previous_*` 列
- **被拒 alternative**:
  - 不保留旧值 — 误轮换无回滚,代价高
  - 永久保留 — 存储 + 合规风险

### D9: 凭证类型 MVP 4 类
- **选择**:api_key(默认)/ oauth2 / database / smtp。V1.0+ 加 ssh_key / jwt / custom。
- **理由**:
  - api_key:覆盖 OpenAI / Claude / DeepSeek / 文心 / 通义
  - oauth2:覆盖飞书 / 钉钉 / 企微
  - database:覆盖 leo 的"提工单查数据库"
  - smtp:覆盖凭证过期邮件通知渠道

### D10: 通知渠道 MVP = 企微 webhook
- **选择**:凭证过期前 7 天 / 1 天 / 当天 各发 1 次,企微 webhook。
- **理由**:
  - 企业内最普及的 IM 通道
  - webhook 简单,无 SDK 依赖
  - 邮件 V1.0+ 补
- **被拒 alternative**:
  - 邮件 — 引入 SMTP 凭证 + 邮件模板,复杂度高
  - 站内信 — 其他 cap 还没就位

### D11: RESTful HTTP API,FastAPI 暴露 6 个 endpoint
- **选择**:FastAPI + JSON,跟 `docs/architecture.md` §4.4 后端技术栈一致。
- **理由**:
  - 内网,HTTP 而非 gRPC 简单
  - Bearer token 鉴权(API Key 模式,MVP)
  - 跟其他 cap 实施 change 接口一致
- **被拒 alternative**:
  - gRPC — MVP 阶段复杂度高,HTTP 够用
  - GraphQL — 不适合 CRUD + 简单查询

### D12: 数据库 schema = 3 张表
- **选择**:`credentials` (主表) + `encryption_keys` (主密钥元数据) + `credential_audit` (审计,跟 audit-and-isolation 隔离)。
- **理由**:
  - 三类职责分离
  - MVP 阶段 credential_audit 独立表,V1.0 写统一 audit log
  - 凭证状态符合 [ENG-Quality #2] 状态双层(凭证状态在 PostgreSQL 主层)
- **被拒 alternative**:
  - 2 张表(凭证 + 审计合并)— 审计写性能 + retention 策略不同
  - 写 audit-and-isolation 统一表 — V1.0 引入,现在没就位

## Risks / Trade-offs

- **[Risk] 主密钥内存泄露** → Mitigation: 进程内存 + 内网 + 无外部攻击面;V1.0+ 演进到 HSM
- **[Risk] 凭证数据被备份带走** → Mitigation: 备份同内网存储 + 静态加密;V1.0+ 备份独立密钥加密
- **[Risk] 凭证使用 API (reveal)被滥用** → Mitigation: 只 admin 可调 + audit 必写 + 频率限制(每用户每分钟 10 次)
- **[Risk] 30 天轮换双值窗口期内旧值被泄露** → Mitigation: 旧值仍按 AES-256-GCM 加密存储,泄露需要 DB + 主密钥同时泄露
- **[Risk] webhook (D10) 调用失败凭证过期提醒丢失** → Mitigation: 失败时写 audit log + 站内信(MVP 用 monitoring cap 的 log;V1.0+ 加重试队列)
- **[Trade-off] 单租户(凭证 workspace-level 共享)** → 接受理由:跟 system-management 一致;V1.0+ 加 per-user ACL
- **[Trade-off] AES-256-GCM nonce 96-bit(随机 32 位 + counter 64 位)** → 接受理由:`cryptography` 库自动处理;2^32 同密钥 nonce 重复概率 0
- **[Trade-off] 凭证值 4096 字符限制** → 接受理由:MVP 阶段无长凭证场景;超长凭证用文件上传(V2.0+)

## Migration Plan

N/A — 本 change 是新功能,无现有服务迁移。实施后:
- 新服务 `services/credential/` 上线到 docker-compose
- PostgreSQL 跑 Alembic 迁移创建 3 张表
- API Key 创建并写入 master credential 表(自举)
- 月 2+ 启动的 cap 通过 HTTP `use` API 调

**Rollback 策略:**
- 删表 / 删服务 → 月 2+ cap 启动前无依赖,rollback 简单
- 数据丢失:凭证是单租户内网,无外部同步,可重建

**验收条件:**
- 5 个 spec Requirement 全部通过对应 Scenario 验证
- 4 critical path 之一("凭证使用审计")可观测
- 性能:`use` API P99 < 50ms(本地 AES-256-GCM 解密 < 10ms + DB 1ms + audit 5ms)
- 集成测试:`use` API 在 100 RPS 压测下 P99 < 50ms

## Open Questions

(沿用 brainstorm.md 的 7 个 Open Questions,不在此重复)

## References

- `openspec/specs/credential-management/spec.md` (canonical spec, 5 Requirements, 5 Scenarios)
- `openspec/specs/credential-management/spec.md` (canonical spec, 5 Requirements, 5 Scenarios)
- `docs/prd.md` §8.2 (凭证管理 P0 MVP)
- `docs/architecture.md` §4.3 (凭证管理作为 system-management 的横切 concern) + §4.4 (技术栈)
- `~/.gstack/projects/paulplay-pm-ChatBiz/paulwang-main-design-20260609-230548.md` ## GSTACK REVIEW REPORT
- `openspec/config.yaml` `eng-review-decisions` 块(12 个锁定决策)
- `brainstorm.md`(本 change 内)Q1-Q12 决议链 + 7 个 Open Questions
