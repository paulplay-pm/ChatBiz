## Why

`openspec/specs/credential-management/spec.md` 已经定下 5 个 Requirement(凭证 CRUD / 凭证引用 / 凭证访问审计 / 凭证权限 / 凭证过期)。本 change 实施这个 cap。月 1 Lane A —— 无依赖,所有其他 cap(workflow / agent / model / channel / plugin / knowledge)都引用本 cap 的凭证,**它是 P0 阻塞,越早上线越好**。MVP 阶段 paul / leo / anny 不能用公网 AI 工具的核心限制就是缺凭证 + 数据隔离,这 cap 把凭证部分先做完。

## What Changes

**新代码**
- `services/credential/`(FastAPI 凭证管理服务)
  - `models.py` SQLAlchemy ORM:credentials / encryption_keys / credential_audit 三表
  - `crypto.py` AES-256-GCM 加密/解密 + per-credential DEK + 主密钥管理
  - `routers.py` 6 个 RESTful endpoint(CRUD + rotate + reveal + use)
  - `audit.py` 审计写入(本地表,V1.0 写统一 audit log)
  - `notifications.py` 企微 webhook 过期提醒
  - `migrations/` Alembic 数据库迁移
  - `tests/` 单元 + 集成 + E2E
- `infrastructure/docker-compose.yml` 新增 credential 服务定义
- `infrastructure/postgres/init/` 新增 credential / encryption_keys / credential_audit 三张表的 DDL

**API 暴露**
- 内部 API(供其他 cap 调):`POST /api/v1/credentials/{id}/use` — 返回明文 + 写 audit log
- 外部 API(供管理 UI 调):CRUD + rotate + reveal(限 admin)

**[FUTURE-IMPLEMENTATION]** V1.0+ 增量:SSO 集成(企微/钉钉扫码)、per-user ACL、凭证版本历史(>1)、批量操作、使用频率监控、强制撤销 API。

## Capabilities

### Modified Capabilities

- `credential-management`(引用已存在的 canonical spec)
  - 实施 spec 里的 5 个 Requirement + 5 个 Scenario
  - 不修改 spec 本身,只实施

## Impact

**Affected code/services:**
- `services/credential/`(新增)
- `infrastructure/docker-compose.yml`(新增 credential 服务)
- 未来所有引用凭证的 cap 都会调本服务(workflow / agent / model / channel / plugin / knowledge)

**Affected eng-review decisions(12 锁定决策):**
- 本 cap 不触及任何 [ENG-#N] 决策
- 间接引用:[ENG-Arch #1] 网关 = egress 强制点,本 cap 提供 `use` API 供网关调
- 间接引用:[ENG-Quality #2] 状态双层,本 cap 凭证状态存 PostgreSQL(主层)

**Non-goals:**
- 不实施 SSO(企微/钉钉扫码)— V1.0+ 补,跟随 system-management 的 SSO 集成
- 不实施 per-user ACL — MVP 凭证是 workspace-level 共享
- 不实施凭证版本历史(>1 previous)— MVP 只保留 1 个 previous
- 不实施批量操作 — V1.0+ 补
- 不实施强制撤销 — V1.0+ 补
- 不实施凭证使用频率监控 — V1.0+ 在 monitoring cap 补
- 不实施 multi-region 部署 — 单内网区域
- 不实施 HSM / KMS — 内网无外网,自研 AES-256-GCM 足够
- 不实施 Vault 集成 — 引入新中间件,5-7 FTE 没时间运维
- 不修改 `openspec/specs/credential-management/spec.md`(spec 是契约,实施不动契约)

**Source references:**
- `openspec/specs/credential-management/spec.md` (canonical spec, 5 个 Requirement)
- `docs/prd.md` §8.2 (凭证管理 P0)
- `docs/architecture.md` §4.3 (凭证管理作为 system-management 的横切 concern)
- `~/.gstack/projects/paulplay-pm-ChatBiz/paulwang-main-design-20260609-230548.md` ## GSTACK REVIEW REPORT
- `openspec/config.yaml` `eng-review-decisions` 块
