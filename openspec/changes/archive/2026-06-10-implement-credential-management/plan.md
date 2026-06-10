# credential-management Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实施 `openspec/specs/credential-management/spec.md` 的 5 个 Requirement + 本 change spec 的 12 个 ADDED Requirement,共 17 个 Requirement,跑通全部 Scenario 验证,产出可上线的 `services/credential/` FastAPI 服务。

**Architecture:** 单 FastAPI 服务 + PostgreSQL 单实例(凭证主表 + 主密钥表 + 审计表)+ AES-256-GCM envelope encryption + per-credential DEK;通过 RESTful HTTP API(6 个 endpoint)暴露能力;其他 cap 通过 `use` API 内部调取明文;不引入 K8s / Vault / KMS。

**Tech Stack:** Python 3.12+ / FastAPI / SQLAlchemy 2.0 async / asyncpg / Alembic / Pydantic v2 / cryptography (AES-256-GCM) / httpx / pytest + pytest-asyncio / testcontainers[postgres] / locust / Docker / pre-commit(ruff + mypy + bandit)。

---

## Task 1: 项目骨架与基础设施(1 后端 ~2h,1 全栈 ~1h)

**Files:**
- `services/credential/pyproject.toml`
- `services/credential/Dockerfile`
- `services/credential/requirements.txt`
- `services/credential/Makefile`
- `services/credential/.pre-commit-config.yaml`
- `infrastructure/docker-compose.yml` (新增 credential 服务定义)
- `infrastructure/postgres/init/01-credential-schema.sql` (Alembic 替代品;真正用 Alembic)

- [ ] **Step 1.1:** 创建目录结构
  ```bash
  mkdir -p services/credential/{app,app/routers,app/services,tests,tests/integration,tests/e2e,alembic,alembic/versions,locust}
  ```

- [ ] **Step 1.2:** 写 `pyproject.toml` + `requirements.txt` 配齐依赖
  - FastAPI ≥ 0.110 / uvicorn[standard] ≥ 0.27
  - SQLAlchemy[asyncio] ≥ 2.0 / asyncpg ≥ 0.29 / alembic ≥ 1.13
  - pydantic ≥ 2.6 / cryptography ≥ 42
  - httpx ≥ 0.27(测试 + webhook)
  - pytest ≥ 8 / pytest-asyncio ≥ 0.23 / testcontainers[postgres] ≥ 4
  - locust ≥ 2.30(性能验证)

- [ ] **Step 1.3:** 写 `Dockerfile` 多阶段:builder 阶段装依赖 → runtime 阶段只保留 python + 源码 + non-root user
  ```dockerfile
  FROM python:3.12-slim AS builder
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install --user --no-cache-dir -r requirements.txt
  FROM python:3.12-slim
  RUN useradd --create-home credential
  WORKDIR /app
  COPY --from=builder /root/.local /home/credential/.local
  COPY . /app
  USER credential
  ENV PATH=/home/credential/.local/bin:$PATH
  EXPOSE 8000
  CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
  ```

- [ ] **Step 1.4:** 写 `Makefile`:`dev`(本地 docker-compose up)/ `test`(pytest)/ `migrate`(alembic upgrade head)/ `run`(uvicorn)/ `lint`(ruff + mypy)/ `sec`(bandit)
- [ ] **Step 1.5:** 配 pre-commit:ruff(mypy + bandit)在 commit 时跑

- [ ] **Step 1.6:** 写 `docker-compose.yml` 增量
  ```yaml
  credential:
    build: ../services/credential
    environment:
      DATABASE_URL: postgresql+asyncpg://chatbiz:chatbiz@postgres:5432/credential
      AUDIT_WEBHOOK_URL: http://audit-and-isolation:8001/audit
      WECOM_WEBHOOK_URL: ${WECOM_WEBHOOK_URL}
      REDIS_URL: redis://redis:6379/0
    depends_on: [postgres, redis]
    ports: ["8000:8000"]
  credential-migrate:
    build: ../services/credential
    command: ["alembic", "upgrade", "head"]
    environment: {DATABASE_URL: postgresql+asyncpg://chatbiz:chatbiz@postgres:5432/credential}
    depends_on: [postgres]
  credential-cron:
    build: ../services/credential
    command: ["python", "-m", "app.cron"]
    environment: {DATABASE_URL: postgresql+asyncpg://chatbiz:chatbiz@postgres:5432/credential, WECOM_WEBHOOK_URL: ${WECOM_WEBHOOK_URL}}
    depends_on: [postgres, redis]
  ```

- [ ] **Step 1.7:** 验证基础设施:`docker compose build credential` 成功
- [ ] **Step 1.8:** commit(项目骨架 + 基础设施)

---

## Task 2: 数据库 schema + Alembic 迁移(1 后端 ~3h)

**Files:**
- `services/credential/app/models.py`
- `services/credential/alembic.ini`
- `services/credential/alembic/env.py`
- `services/credential/alembic/versions/0001_initial.py`
- `services/credential/alembic/versions/0002_audit_indexes.py`

- [ ] **Step 2.1:** 写 `models.py`:3 张表的 SQLAlchemy 2.0 异步 ORM(用 `DeclarativeBase` + `Mapped` + `mapped_column`)
  - `Credential`:id (str PK, "cred_<base62>") / name (str) / type (Enum: api_key, oauth2, database, smtp) / encrypted_value (LargeBinary) / encrypted_dek (LargeBinary) / previous_value (LargeBinary, nullable) / previous_encrypted_dek (LargeBinary, nullable) / previous_expires_at (datetime, nullable) / workspace_id (str) / expires_at (datetime, nullable) / created_at / updated_at
  - `EncryptionKey`:id (int PK) / key_id (UUID) / encrypted_key (LargeBinary) / status (Enum: active, retired) / created_at / retired_at
  - `CredentialAudit`:id (bigint PK) / timestamp / user_id (str) / credential_id_hash (LargeBinary, 8 bytes SHA256) / action (str) / cap (str, nullable) / purpose (str, nullable) / success (bool)
  - 索引:per spec §schema

- [ ] **Step 2.2:** 写 `alembic.ini` + `alembic/env.py`(异步,支持 offline + online)
- [ ] **Step 2.3:** 写 `0001_initial.py`:3 张表 + 主键 + 索引(workspace_id, type) + (expires_at)
- [ ] **Step 2.4:** 写 `0002_audit_indexes.py`:补 (credential_id_hash, timestamp) + (user_id, timestamp) 复合索引
- [ ] **Step 2.5:** 跑 `docker compose run --rm credential-migrate` 验证迁移成功
- [ ] **Step 2.6:** 写 spec §数据库回滚测试 验证 `alembic downgrade -1` 完整回滚
- [ ] **Step 2.7:** commit(数据库 schema + 迁移)

---

## Task 3: 加密模块(1 后端 ~3h)

**Files:**
- `services/credential/app/crypto.py`
- `services/credential/tests/unit/test_crypto.py`

- [ ] **Step 3.1:** 写 `generate_dek() -> bytes`(32 字节,`secrets.token_bytes(32)`)
- [ ] **Step 3.2:** 写 `encrypt_with_dek(plaintext: bytes, dek: bytes) -> (nonce, ciphertext, tag)`(AES-256-GCM,96-bit nonce)
- [ ] **Step 3.3:** 写 `decrypt_with_dek(nonce, ciphertext, tag, dek) -> plaintext`
- [ ] **Step 3.4:** 写 `load_master_key() -> bytes`(从 PostgreSQL `encryption_keys` 加载 active 主密钥;如果缺失抛 `MasterKeyNotFoundError`)
- [ ] **Step 3.5:** 写 `encrypt_dek_with_master(dek, master) -> bytes` + `decrypt_dek_with_master(encrypted_dek, master) -> bytes`(主密钥加密 DEK,32 字节 master 派生)
- [ ] **Step 3.6:** 写 `generate_master_key() -> bytes`(部署 / 初始设置用)
- [ ] **Step 3.7:** 写 `rotate_master_key()`(用新 master 重新加密所有 DEK,无停机)
- [ ] **Step 3.8:** 写单元测试 `test_crypto.py`:round-trip、wrong-key fail、short-ciphertext fail、edge cases
- [ ] **Step 3.9:** 跑 `pytest tests/unit/test_crypto.py` 100% 通过
- [ ] **Step 3.10:** commit(加密模块)

---

## Task 4: Pydantic schemas + 业务服务层(1 后端 ~3h)

**Files:**
- `services/credential/app/schemas.py`
- `services/credential/app/services.py`
- `services/credential/app/routers/credentials.py`(空架子,Task 5 填 endpoint)

- [ ] **Step 4.1:** 写 Pydantic v2 schemas
  - `CredentialCreateRequest`:name, type, value (write-only), workspace_id, expires_at, type-specific fields (oauth2: client_id/client_secret/token_url/scope, database: host/port/db_name, smtp: host/port/username)
  - `CredentialResponse`:id, name, type, workspace_id, expires_at, created_at, updated_at(**不含 value**)
  - `CredentialDetailResponse`:同 + masked_value (前 4 后 4 中间 ****)
  - `CredentialRevealResponse`:value (明文,reveal API 专用)
  - `CredentialUseRequest`:cap (str), purpose (str)
  - `CredentialUseResponse`:value (明文,内部 API)
  - `CredentialRotateRequest`:value (write-only), expires_at (optional)

- [ ] **Step 4.2:** 写 `CredentialService` 类:CRUD + rotate + reveal + use + audit
  - 方法:`create() / list() / get() / rotate() / delete() / reveal() / use()`
  - 每个方法都调 `write_audit()`
  - `reveal()` 限 admin(用 `check_credential_reveal` 权限)
  - `use()` 不限角色但限 workspace

- [ ] **Step 4.3:** 写 `permissions.py`:`check_credential_read(user) / check_credential_use(user) / check_credential_reveal(user)`
- [ ] **Step 4.4:** 写 spec §AES-256-GCM envelope + 凭证轮换双值 的 service 层 unit test
- [ ] **Step 4.5:** 跑 unit test 100% 通过
- [ ] **Step 4.6:** commit(schemas + services + permissions)

---

## Task 5: REST API endpoints(1 后端 ~3h,1 全栈 ~2h)

**Files:**
- `services/credential/app/main.py`
- `services/credential/app/routers/credentials.py`
- `services/credential/app/audit.py`
- `services/credential/app/rate_limit.py`
- `services/credential/app/notifications.py`
- `services/credential/app/lifespan.py`
- `services/credential/tests/integration/test_credentials.py`

- [ ] **Step 5.1:** 写 `main.py`:FastAPI app + lifespan(启动加载主密钥,缺失抛 → exit)+ CORS + 错误处理
- [ ] **Step 5.2:** 写 `audit.py`:`write_audit()` 异步写 `credential_audit` 表
- [ ] **Step 5.3:** 写 `rate_limit.py`:Redis-based token bucket(每用户每分钟 ≤ 10 次 reveal)
- [ ] **Step 5.4:** 写 `notifications.py`:`send_wechat_webhook(url, message)` 用 httpx POST
- [ ] **Step 5.5:** 写 6 个 endpoint(全部用 service 层 + 权限 + 频率限制 + audit)
  - `POST /api/v1/credentials` (create, need write)
  - `GET /api/v1/credentials` (list, need read, page 分页)
  - `GET /api/v1/credentials/{id}` (detail, need read, 返 masked)
  - `POST /api/v1/credentials/{id}/rotate` (rotate, need write)
  - `POST /api/v1/credentials/{id}/reveal` (reveal, need reveal = admin, 频率限制)
  - `POST /api/v1/credentials/{id}/use` (use, need use, 内部 API)
  - `DELETE /api/v1/credentials/{id}` (delete, need write)

- [ ] **Step 5.6:** 写 `tests/integration/test_credentials.py`:6 个 endpoint × happy + 失败 path(testcontainers[postgres])
- [ ] **Step 5.7:** 写 spec §凭证 CRUD / 引用 / 权限 / 频率限制 / 多租户隔离 的集成 test
- [ ] **Step 5.8:** 跑 `pytest tests/integration/test_credentials.py` 100% 通过
- [ ] **Step 5.9:** commit(API endpoints + 集成测试)

---

## Task 6: Cron 任务(凭证过期提醒 + 清理)(1 后端 ~2h)

**Files:**
- `services/credential/app/cron.py`
- `services/credential/tests/unit/test_cron.py`

- [ ] **Step 6.1:** 写 `check_expiring_credentials()` 扫 `expires_at` 距今 7/1/0 天的凭证(只发 1 次,避免重复)
- [ ] **Step 6.2:** 写 `cleanup_expired_previous()` 扫 `previous_expires_at < now()` 的行,清空 `previous_*` 列
- [ ] **Step 6.3:** 写 `cron.py` 主入口:每天 0 点跑 2 个 job
- [ ] **Step 6.4:** 写 spec §凭证过期提醒 验证 7/1/0 天各 1 次推送(用 mock webhook server)
- [ ] **Step 6.5:** 写 spec §凭证轮换双值窗口期 的清理 Scenario
- [ ] **Step 6.6:** commit(cron + 单元测试)

---

## Task 7: E2E + 性能测试(1 后端 ~2h,1 全栈 ~2h)

**Files:**
- `services/credential/tests/e2e/test_credential_lifecycle.py`
- `services/credential/locustfile.py`

- [ ] **Step 7.1:** 写 e2e 流程:启动 FastAPI + 临时 PostgreSQL + 创建凭证 → 轮换 → use → 触发 cron → 验证旧值清理
- [ ] **Step 7.2:** 跑 e2e 100% 通过
- [ ] **Step 7.3:** 写 locustfile.py:use API 100 RPS 持续 60s
- [ ] **Step 7.4:** 跑 `locust --headless -u 100 -r 10 --run-time 60s`
- [ ] **Step 7.5:** 验证 P99 < 50ms(spec §性能基线)
- [ ] **Step 7.6:** 不达标时调优(连接池 / async batch)
- [ ] **Step 7.7:** commit(e2e + locustfile)

---

## Task 8: 安全 review(横切,1 后端 ~2h)

- [ ] **Step 8.1:** `bandit -r services/credential/`:0 高危
- [ ] **Step 8.2:** 跑 OWASP 基础检查:SQL 注入(全用 SQLAlchemy ORM)/ XSS / CSRF / SSRF(外部 webhook 用环境变量 URL)
- [ ] **Step 8.3:** 加密模块单独 review:主密钥不在 commit / log / audit / test fixture
- [ ] **Step 8.4:** 凭证使用频率限制实际跑过 11 次 → 429
- [ ] **Step 8.5:** 审计 log 写入不可被绕过(单元测试覆盖每个 endpoint)
- [ ] **Step 8.6:** 修复发现的问题

---

## Task 9: 文档 + 收尾(1 后栈 ~2h)

**Files:**
- `services/credential/README.md`
- `docs/openapi/credential.yaml`(自动生成)
- `openspec/changes/implement-credential-management/REPORT.md`

- [ ] **Step 9.1:** 写 `services/credential/README.md`:启动 / 部署 / 测试 / 故障排查
- [ ] **Step 9.2:** 启动 FastAPI,导出 OpenAPI 3.0 到 `docs/openapi/credential.yaml`
- [ ] **Step 9.3:** 跑 `verify.py` 验证 17 个 Requirement × Scenario 100%
- [ ] **Step 9.4:** 写 `openspec/changes/implement-credential-management/REPORT.md`(什么 shipped / 什么 deferred / 什么 surprising)
- [ ] **Step 9.5:** 写 release notes
- [ ] **Step 9.6:** commit + push + PR

---

## Self-Review (per writing-plans skill)

**Spec coverage check:** spec 有 17 个 Requirement(5 canonical + 12 implementation),每个至少 1 个 Scenario。Plan 任务覆盖全部。
- 凭证 CRUD → Task 5
- 凭证引用(use API) → Task 5
- 凭证访问审计 → Task 4 + 5(audit)
- 凭证权限 → Task 4(permissions)+ 5
- 凭证过期 → Task 6(cron)
- 主密钥加载 → Task 3 + 5
- 主密钥轮换 → Task 3(rotate_master_key)
- AES-256-GCM envelope → Task 3
- 双值窗口期 → Task 4 + 5 + 6
- 频率限制 → Task 5
- 类型实现 → Task 4
- 列表分页 → Task 5
- 审计 → Task 5
- 过期提醒 → Task 6
- 数据库 schema → Task 2
- 数据库回滚测试 → Task 2
- 多租户隔离测试 → Task 5
- 集成测试 → Task 5 + 7
- 性能基线 → Task 7

**Placeholder scan:** 没有 TBD / TODO
**Type consistency:** Python 类型提示一致,async/await 全用
**File path consistency:** 使用 `services/credential/`,符合 openspec config 后端规范

## References

- `openspec/specs/credential-management/spec.md` (canonical 5 Requirements)
- `openspec/changes/implement-credential-management/specs/credential-management/spec.md` (12 implementation Requirements)
- `openspec/changes/implement-credential-management/brainstorm.md` (Q1-Q12 决议)
- `openspec/changes/implement-credential-management/design.md` (D1-D12 设计)
- `openspec/changes/implement-credential-management/proposal.md` (Why + What Changes)
- `openspec/changes/implement-credential-management/tasks.md` (15 task groups, 73 tasks)
- `openspec/config.yaml` (后端规范:SQLAlchemy ORM + 异步 + 审计埋点)
- `docs/architecture.md` §4.4 (技术栈)
- `~/.gstack/projects/paulplay-pm-ChatBiz/paulwang-main-design-20260609-230548.md` ## GSTACK REVIEW REPORT
