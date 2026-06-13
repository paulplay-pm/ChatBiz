# infra-compose-fixes

**Frontend Scope: N/A — 纯基础设施层（infrastructure compose + init scripts），无 UI / 业务 / 协议场景**

**Backend Scope: 含后端**（`infrastructure/postgres/init/02-create-databases.sql` + `infrastructure/docker-compose.yml`）

**Impact**（被谁消费）：
- 被 `web-integration-test-suite` change 消费（修后 test stack 启动不再需要 workaround；`web/integration-tests/README.md` Known Issues #1/#2/#3 标记 resolved）
- 被任何干净 dev 机 `docker compose -p chatbiz up` 的人消费（修复 3 个 latent bug）
- 后续 change 接入 CI / 运维 / 测试依赖 production compose healthy

## ADDED Requirements

### Requirement: Postgres 16+ 兼容的 `02-create-databases.sql`

`infrastructure/postgres/init/02-create-databases.sql` MUST NOT 使用 PL/pgSQL `DO $$ ... EXECUTE 'CREATE DATABASE ...' END $$;` 块（Postgres 16 拒绝 `CREATE DATABASE` 在 function 内执行）。MUST 使用 psql `\gexec` 模式：`SELECT 'CREATE DATABASE <name>' WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = '<name>') \gexec`，Postgres 16 允许在脚本顶层动态执行 `CREATE DATABASE`。**保留** `\connect <db>` + `GRANT ALL PRIVILEGES` + `ALTER DEFAULT PRIVILEGES` 步骤不变（这些不依赖 DO block）。

#### Scenario: 干净 dev 机启动 postgres 容器 init 跑通
- **WHEN** 在干净 dev 机（无现存 postgres data volume）`docker compose -p chatbiz up postgres`
- **THEN** postgres 容器日志 MUST 显示 `CREATE DATABASE audit_isolation` + `CREATE DATABASE workflow_engine` 成功（不是 ERROR）
- **AND** `pg_isready -U chatbiz` 退出码 0
- **AND** `docker exec chatbiz-postgres psql -U chatbiz -l` 列出 3 个库：`credential` / `audit_isolation` / `workflow_engine`

#### Scenario: 已存在数据库时幂等
- **WHEN** postgres data volume 已包含 `audit_isolation` 库
- **THEN** `02-create-databases.sql` 重跑 MUST NOT 报 "database already exists" 错误
- **AND** 仅创建缺失的库

#### Scenario: 旧 `DO $$` 块被移除
- **WHEN** `grep -c "DO \\\$\\\$" infrastructure/postgres/init/02-create-databases.sql` 执行
- **THEN** 输出 MUST 为 0

### Requirement: 三个 `*-migrate` 容器设 `PYTHONPATH`

`infrastructure/docker-compose.yml` 的 `credential-migrate` / `audit-and-isolation-migrate` / `workflow-engine-migrate` 三个一次性容器 MUST 在 `environment` 设 `PYTHONPATH: /home/<user>/.local/lib/python3.12/site-packages:/app`（`<user>` 分别是 `credential` / `audit` / `wf`，与各自 Dockerfile `RUN useradd` 一致）。该 env 必须存在，否则 `alembic upgrade head` 报 `ModuleNotFoundError: No module named 'alembic'`。

#### Scenario: credential-migrate 跑 alembic 不再 ModuleNotFoundError
- **WHEN** `docker compose -p chatbiz up credential-migrate`
- **THEN** 容器日志 MUST 不含 `ModuleNotFoundError: No module named 'alembic'`
- **AND** `alembic upgrade head` 成功（exit code 0）

#### Scenario: audit-and-isolation-migrate 跑 alembic 不再 ModuleNotFoundError
- **WHEN** `docker compose -p chatbiz up audit-and-isolation-migrate`
- **THEN** 容器日志 MUST 不含 `ModuleNotFoundError: No module named 'alembic'`
- **AND** 至少 1 个 `Running upgrade ...` 日志行

#### Scenario: workflow-engine-migrate 跑 alembic 不再 ModuleNotFoundError
- **WHEN** `docker compose -p chatbiz up workflow-engine-migrate`
- **THEN** 容器日志 MUST 不含 `ModuleNotFoundError: No module named 'alembic'`
- **AND** 至少 1 个 `Running upgrade ...` 日志行

#### Scenario: 三个 user 路径正确
- **WHEN** `grep -n "PYTHONPATH" infrastructure/docker-compose.yml` 执行
- **THEN** MUST 含 3 个匹配行，分别对应 `/home/credential` / `/home/audit` / `/home/wf` user prefix

### Requirement: credential-migrate 完成后 seed master encryption key

`infrastructure/docker-compose.yml` 的 `credential-migrate` 容器 MUST 在 alembic 升级后用 Python heredoc seed 一条 `encryption_keys` 记录（`status = 'ACTIVE'`, `key_id = uuid`, `encrypted_key = secrets.token_bytes(32)`），与 `infrastructure/docker-compose-dev.yml` 已有实现一致（idempotent guard `if active == 0`）。MUST 用 `command: ["bash", "-c", "alembic upgrade head && python -c '<heredoc>'"]` 模式，不分两步独立 container。

#### Scenario: credential service 启动不再 MasterKeyNotFoundError
- **WHEN** 完整 `docker compose -p chatbiz up credential`（依赖 credential-migrate 已 service_completed_successfully）
- **THEN** credential 容器日志 MUST 不含 `MasterKeyNotFoundError: no active master key in encryption_keys`
- **AND** `lifespan` 不抛 `SystemExit(1)`
- **AND** `curl http://localhost:8000/healthz` 返回 200

#### Scenario: seed 幂等（多次跑不重复）
- **WHEN** 第一次 `docker compose -p chatbiz up credential-migrate` 完成
- **AND** 第二次 `docker compose -p chatbiz up credential-migrate` 跑（idempotent guard）
- **THEN** `psql -U chatbiz -d credential -c "SELECT count(*) FROM encryption_keys WHERE status IN ('ACTIVE', 'active')"` MUST 返回 1（不是 2 或更多）

#### Scenario: seed 步骤在 alembic 之后
- **WHEN** 读 `infrastructure/docker-compose.yml` 的 `credential-migrate.command`
- **THEN** MUST 是 `["bash", "-c", "alembic upgrade head && python -c '<seed>'"]`
- **AND** `alembic` 必须在 `python -c '<seed>'` 之前（保证表已存在）

### Requirement: 验证 — 干净 dev 机全栈 healthy

`make test-integration up` MUST 在干净 dev 机（无 port 8000 冲突 + 无现存 postgres data volume）跑通 7 service 全部 healthy（postgres / redis / credential / audit-and-isolation / mcp / workflow-engine / web）。

#### Scenario: 全栈 healthy
- **WHEN** 干净 dev 机 `docker compose -p chatbiz up --wait` 跑通
- **THEN** `docker compose -p chatbiz ps` 7 service 全部 `State: healthy`
- **AND** `curl http://localhost:5173/healthz` 返回 200（nginx 代理到 mcp）

#### Scenario: 旧 init 失败数据不阻塞
- **WHEN** 旧 dev 机有 bug #1 留下的失败 postgres volume
- **THEN** verify 步骤 MUST 先 `docker compose -p chatbiz down -v` 清空，再 `up`

#### Scenario: test stack 仍可用（不依赖 production fix）
- **WHEN** 干净 dev 机 `make test-integration up`（test project `chatbiz-test`）
- **THEN** 7 service 仍 healthy
- **AND** `infrastructure/postgres-init-test/` workaround 文件保留（不删）
