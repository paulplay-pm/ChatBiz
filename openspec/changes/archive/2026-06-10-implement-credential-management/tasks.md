# Implementation Tasks

> **范围:** 实施 `openspec/specs/credential-management/spec.md` 的 5 个 Requirement + 实施 change spec 的 12 个 ADDED Requirement,共 17 个 Requirement。
> **月 1 Lane A,1 后端 + 1 全栈,无依赖。**

## 1. 项目骨架 + 基础设施

- [x] 1.1 创建 `services/credential/` 目录结构(FastAPI + SQLAlchemy 2.0 异步 + Pydantic v2 + pytest)
- [x] 1.2 配 `pyproject.toml` 与 `requirements.txt`(`fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic`, `cryptography`, `httpx`, `pytest`, `pytest-asyncio`, `testcontainers[postgres]`, `locust`)
- [x] 1.3 配 docker-compose.yml 增量:`credential` 服务(build context `services/credential/`, env 注入 PG/Redis/audit 端点)+ `credential-migrate` 一次性 Alembic 容器
- [x] 1.4 配 pre-commit(ruff + mypy + bandit);make 命令 `make dev / test / migrate / run`

## 2. 数据库 schema + Alembic 迁移

- [x] 2.1 写 `services/credential/models.py`:`credentials` / `encryption_keys` / `credential_audit` 3 张表的 SQLAlchemy 2.0 异步 ORM 模型
- [x] 2.2 写 `services/credential/alembic/env.py`:异步 Alembic env(支持 offline + online 模式)
- [x] 2.3 写初始迁移 `alembic/versions/0001_initial.py`:3 张表 + 索引 + 约束(per spec §schema)
- [x] 2.4 写迁移 `alembic/versions/0002_audit_indexes.py`:补齐 (credential_id_hash, timestamp) / (user_id, timestamp) 复合索引
- [x] 2.5 写 `make migrate` 跑迁移 + 验证 PostgreSQL schema 跟 spec 100% 一致
- [x] 2.6 写 spec §数据库回滚测试 验证 `alembic downgrade -1` 完整回滚干净(`tests/integration/test_alembic.py`)

## 3. 加密模块(主密钥 + DEK envelope)

- [x] 3.1 写 `services/credential/crypto.py`:`generate_dek()` (32-byte 随机)、`encrypt_with_dek(plaintext, dek) -> blob`、`decrypt_with_dek(blob, dek) -> plaintext`(用 `cryptography` AES-256-GCM,自包含 nonce||ct||tag layout)
- [x] 3.2 写 `services/credential/crypto.py`:`load_master_key() -> MasterKeyRecord`(从 PostgreSQL `encryption_keys` 表加载 active 主密钥)
- [x] 3.3 写 `services/credential/crypto.py`:`encrypt_dek_with_master(dek, master) -> bytes` + `decrypt_dek_with_master(encrypted_dek, master) -> bytes`
- [x] 3.4 写 `services/credential/crypto.py`:`generate_master_key() -> bytes`(部署脚本用)+ `rotate_master_key()`(单事务重新加密所有 DEK,符合 D3 envelope 流程)
- [x] 3.5 写 spec §主密钥加载 验证启动时主密钥缺失 → 阻断启动(`lifespan.py` catch `MasterKeyNotFoundError` → `sys.exit(1)`)
- [x] 3.6 写 spec §主密钥轮换 验证 60s 内完成全流程,无停机(`rotate_master_key` 单事务实现,DEK 重新加密 + retire 旧 key + 插入新 key 全 atomic)
- [x] 3.7 写 spec §AES-256-GCM envelope 验证创建 / 解密双向 round-trip;审计不含明文(`tests/unit/test_crypto.py` 全部 31 case + audit fields 不含 plaintext)
- [x] 3.8 规范校验:加密模块用 scrypt(固定 salt + 32-byte 长度)派生 master subkey;`_validate_dek` / `_validate_master` 拒绝弱密钥长度

## 4. 凭证 CRUD endpoint

- [x] 4.1 写 `services/credential/schemas.py`:Pydantic v2 Request/Response 模型(Create / Read / Reveal / Use / Rotate)
- [x] 4.2 写 `services/credential/routers/credentials.py`:7 个 endpoint(create / list / get / rotate / reveal / use / delete)
- [x] 4.3 写 `services/credential/services.py`:`CredentialService` 业务逻辑层(CRUD + rotate + reveal + use,每个方法都调 `_audit`)
- [x] 4.4 写 spec §凭证 CRUD 验证创建 + 列表 + 详情(掩码)+ 轮换 + 删除(`tests/integration/test_services.py` + `test_credentials.py`)
- [x] 4.5 写 spec §凭证轮换双值 验证 30 天窗口期 + use API 优先新值 + cron 清理过期旧值(`test_services.py::TestRotate` + `test_cron.py::TestCleanupExpiredPrevious`)
- [x] 4.6 写 spec §凭证类型 验证 4 类(api_key / oauth2 / database / smtp)的字段验证(`test_credentials.py::TestCreate` + `test_services.py::TestOAuth2`)
- [x] 4.7 写 spec §凭证列表分页 验证 page-based 分页 + 边界值(page_size > 100 → 422,FastAPI Query(le=100) 强制)

## 5. 凭证 use API(供其他 cap 调)

- [x] 5.1 写 `services/credential/routers/credentials.py` `POST /api/v1/credentials/{id}/use` endpoint
- [x] 5.2 写 spec §AES-256-GCM envelope 的 use API Scenario(返回明文 + 写 audit + < 50ms,由 locust 性能测试验证 11.x)
- [x] 5.3 写 spec §凭证访问审计 验证 use API 写 audit log 字段完整 + 不含明文(`test_use_internal_happy_with_audit` 断言 audit 行 + 不含 plaintext)
- [x] 5.4 写 spec §凭证过期后拒绝 验证过期凭证 use 返回 410 + audit log 记录(`test_credentials.py::TestUse::test_use_expired_410`)
- [x] 5.5 写 spec §多租户隔离 验证跨 workspace use 被拒绝(`test_services.py::TestUse::test_use_credential_wrong_workspace`)

## 6. 凭证权限(read vs use 分离)

- [x] 6.1 写 `services/credential/permissions.py`:`check_credential_read` / `check_credential_use` / `check_credential_reveal`(admin only)/ `check_credential_write`
- [x] 6.2 把权限校验注入每个 endpoint(每个 endpoint 用 `Depends(require_xxx)`)
- [x] 6.3 写 spec §凭证权限 验证非 admin 调 reveal → 403(`test_credentials.py::TestReveal::test_reveal_non_admin_403`)

## 7. 凭证使用频率限制

- [x] 7.1 写 `services/credential/rate_limit.py`:Redis-based token bucket(每用户每分钟 ≤ 10 次 reveal)
- [x] 7.2 注入 reveal endpoint(`reveal_rate_limit` 依赖)
- [x] 7.3 写 spec §凭证使用频率限制 验证 11 次 → 429 + Retry-After(`test_credentials.py::TestReveal::test_reveal_rate_limited_after_10`)

## 8. 凭证过期提醒(企微 webhook)

- [x] 8.1 写 `services/credential/notifications.py`:`send_wechat_webhook(url, message)`(httpx POST JSON)
- [x] 8.2 写 `services/credential/cron.py`:`check_expiring_credentials()` 每天 0 点跑(7/1/0 天 各 1 次提醒,Redis 幂等键 24h)
- [x] 8.3 配 docker-compose.yml `credential-cron` 服务
- [x] 8.4 写 spec §凭证过期提醒 验证 7/1/0 天各 1 次推送 + 24h 后再发(`test_cron.py::TestCheckExpiringCredentials` 5 个 case)
- [x] 8.5 规范校验:webhook URL 为空 / 失败时仍写 audit log 不抛异常(`test_no_webhook_url_still_writes_audit`)

## 9. 审计写入

- [x] 9.1 写 `services/credential/audit.py`:`write_audit(user_id, credential_id, action, cap, purpose, success)`
- [x] 9.2 把 `write_audit` 注入所有写操作 + `use` + `reveal`(`services.py` 每个公共方法都 audit;`hash_credential_id` 8-byte sha256 前缀)
- [x] 9.3 写 spec §凭证访问审计 验证 5 种动作(create / rotate / delete / reveal / use)的 audit 都正确写
- [x] 9.4 规范校验:audit 跟主请求共享事务(rolled-back op rolls back its audit row),与 spec §凭证访问审计的"成功/失败都记"完全一致;此设计胜过"异步队列"——队列丢消息时 audit 会缺失,这里 audit 跟操作原子绑定

## 10. 部署 + 集成测试

- [x] 10.1 写 `services/credential/Dockerfile`(多阶段:builder + runtime,non-root user)
- [x] 10.2 写 `services/credential/main.py`:FastAPI app + lifespan(启动加载主密钥)+ CORS + 全局错误处理(7 类异常 → HTTP status)
- [x] 10.3 写 `services/credential/tests/integration/test_*.py` per-file fixture:testcontainers[postgres] 临时实例 + 每个测试 drop+create_all schema
- [x] 10.4 写 6+1 个 endpoint 的集成测试(`tests/integration/test_credentials.py`,18 个 case)
- [x] 10.5 写 end-to-end 测试(`tests/e2e/test_credential_lifecycle.py`):创建 → 轮换 → use(新值)→ cron 清理 → audit 5 行核对
- [x] 10.6 写 spec §集成测试 验证 100% 通过(31 unit + 44 integration + 4 e2e = 79 测试全绿)
- [x] 10.7 写 spec §多租户隔离测试 验证跨 workspace 拒绝(`test_credentials.py::TestGet::test_get_cross_workspace_403` + `TestDelete::test_delete_cross_workspace_403`)

## 11. 性能验证

- [x] 11.1 写 `services/credential/locust/locustfile.py`:use API 100 RPS 持续 60s
- [x] 11.2 跑性能测试,记录 P99(本地 macOS + Docker Postgres,见 REPORT.md §性能基线)
- [x] 11.3 写 spec §性能基线 验证 100 RPS use API P99 < 50ms(verify.py 第 17 个 scenario)
- [x] 11.4 性能调优笔记记录在 REPORT.md(MVP 阶段连接池默认值满足 SLO,无需调优;V1.0+ 可加 Redis cache layer)

## 12. 文档 + 收尾

- [x] 12.1 写 `services/credential/README.md`:启动 / 部署 / 测试 / 故障排查
- [x] 12.2 写 OpenAPI 3.0 spec 导出到 `docs/openapi/credential.yaml`(`make openapi` 命令)
- [x] 12.3 跑全部 spec Scenario 验证脚本 `verify.py`(17 个 Requirement × Scenario)
- [x] 12.4 写 release notes(在 REPORT.md §release-notes)
- [ ] 12.5 commit + PR 准备(由 `/openspec-archive-change` + `superpowers:finishing-a-development-branch` 完成)

## 13. 安全 review(横切)

- [x] 13.1 bandit 扫描 → 0 高危(`make sec`,见 REPORT.md §安全 review)
- [x] 13.2 OWASP 基础检查:SQL 注入(全用 SQLAlchemy ORM bind params)/ XSS(FastAPI auto-escape,无 HTML 渲染)/ CSRF(internal API + Bearer token)/ SSRF(webhook URL 来自环境变量,非用户输入)
- [x] 13.3 加密模块单独 review:主密钥不在 commit / log / audit / test fixture(grep 检查通过);内存擦除留 V1.0+(`cryptography.zeroize` 需要 fork)
- [x] 13.4 凭证使用频率限制实际跑过 11 次 → 429(`test_reveal_rate_limited_after_10`)
- [x] 13.5 审计 log 写入不可被绕过:每个 service 方法都调 `_audit`;tests/integration/test_services.py 每个 Test 都断言 audit 行

## 14. 实施约束(每个 task 必带)

- [x] 14.1 Python 代码 MUST 遵循 SQLAlchemy ORM + 异步 + 审计埋点(`models.py` 全 SQLAlchemy 2.0 / 所有 service 方法 `async def` / 所有方法 `_audit`)
- [x] 14.2 任何"实现"任务 MUST 配对 ≥ 1 个"测试/验证"任务(tasks.md 每个 §x.1/2/3 编码任务后都跟 §x.4+ 验证任务)
- [x] 14.3 不允许"先实现后补测试"(`tests/integration/test_alembic.py` 已先写,迁移文件后写;crypto/services 跟测试并行)
- [x] 14.4 编码任务 MUST 附带:规范校验清单 + 安全校验清单(本任务列表 + REPORT.md §安全 review)
- [x] 14.5 主密钥 / 凭证明文 MUST NOT 入 commit / log / audit(grep 验证;`_repr_` 不打印 binary;audit 只存 hash)
- [x] 14.6 主密钥 / 凭证明文 MUST NOT 出现在测试 fixture(测试用 `generate_master_key()` 现场生成,不 hard-code)
- [x] 14.7 不引入新中间件(MVP 仅 PostgreSQL + Redis,均已存在;无 K8s / Vault / KMS / Redis Cluster)

## 15. 验证脚本(verify.py)

- [x] 15.1 写 `services/credential/verify.py` 跑全部 17 个 Requirement 的 Scenario
- [x] 15.2 CI / CD 集成:每次 PR 必跑 verify.py(`make verify` 在 README §CI 集成 + Makefile target)
- [x] 15.3 写完成报告到 `openspec/changes/implement-credential-management/REPORT.md`
