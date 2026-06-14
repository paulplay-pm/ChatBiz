# fix-production-compose — Proposal

## Why

`infrastructure/docker-compose.yml` 有 3 个 latent bug 阻塞任何干净启动（不只是 test stack；dev compose 因为自带正确实现所以目前 work）：

1. **Postgres 16 拒绝 `DO $$ ... CREATE DATABASE ... END $$`**：脚本 `infrastructure/postgres/init/02-create-databases.sql` 用 PL/pgSQL 块创建 `audit_isolation` / `workflow_engine` 库，Postgres 16 抛 `CREATE DATABASE cannot be executed from a function`，postgres healthcheck 永远 fail。
2. **`*-migrate` 容器缺 `PYTHONPATH`**：`credential-migrate` / `audit-and-isolation-migrate` / `workflow-engine-migrate` 三个一次性容器只设 `DATABASE_URL`，不指 `~/.local/lib/python3.12/site-packages/`，alembic 跑不起来报 `ModuleNotFoundError: No module named 'alembic'`。dev compose (`docker-compose-dev.yml`) 显式设了；production 漏。
3. **credential service 缺 master encryption key seed**：`crypto.py:load_master_key` 在 `encryption_keys` 表空时抛 `MasterKeyNotFoundError`，`lifespan` 抛 `SystemExit(1)`。dev compose 在 alembic 后用 Python heredoc 插一条 active key；production 漏。

`web-integration-test-suite` change 落地后写 `web/integration-tests/README.md` 详细记录这 3 个 bug 为 `Known Issues`（issue #1 / #2 / #3）。test stack 用 `postgres-init-test/` workaround + 自带 `PYTHONPATH` 绕开，但 full `make test-integration test` 仍 fail 在 credential master key 缺失。

不改：任何在新机器上 `docker compose -p chatbiz up` 的人都会撞 bug #1 → #2 → #3 串行失败；CI 接入（后续 change）需要 production compose 工作。

改：本 change 把 3 个 fix 合并到 production compose，对齐 dev compose 已有正确实现。修完后：
- `docker compose -p chatbiz up` 在干净 dev 机可一次性 healthy
- `make test-integration up` 不再需要 workaround（保留为冗余回退）
- 后续 CI / 运维可基于此启

参考基线：
- `infrastructure/docker-compose-dev.yml`（正确实现，line 47-87 三个 migrate + line 67-86 credential seed）
- `web-integration-test-suite/verify.md` § Known Issues #1-#3
- `docs/architecture.md` §4.4（技术栈：SQLAlchemy / Docker compose）

## What Changes

- **修改** `infrastructure/postgres/init/02-create-databases.sql`：把 `DO $$ ... EXECUTE 'CREATE DATABASE ...'; ... END $$;` 块改为 psql `\gexec`（Postgres 16 允许 `\gexec` 在脚本顶层执行动态 SQL）。
- **修改** `infrastructure/docker-compose.yml` 三个 migrate 服务（`credential-migrate` / `audit-and-isolation-migrate` / `workflow-engine-migrate`）：各加 `PYTHONPATH: /home/<user>/.local/lib/python3.12/site-packages:/app` env（与 dev compose 一致）。
- **修改** `infrastructure/docker-compose.yml` `credential-migrate` 容器：把 `command: ["alembic", "upgrade", "head"]` 改为 `bash -c 'alembic upgrade head && python -c "<seed heredoc>"'`（与 dev compose 一致；seed 是 idempotent）。

**不** 改：
- `infrastructure/docker-compose-dev.yml`（已经正确）
- `infrastructure/postgres/init/01-credential-schema.sql`（已正确）
- 任何 service 源码（仅 infrastructure/ 与 init scripts）
- `infrastructure/postgres-init-test/`（test stack 独立 workaround，保留作为冗余回退）
- `infrastructure/docker-compose-test.yml`（test stack 已自带 workaround）

## Capabilities

### New Capabilities

- `infra-compose-fixes`：production compose 3 个 fix 的 capability 集合。**前端范围** = N/A（纯基础设施，零 UI / 业务 / 协议场景）；**后端范围** = `infrastructure/postgres/init/02-create-databases.sql` + `infrastructure/docker-compose.yml`；**豁免前端** = 纯基础设施层。

### Modified Capabilities

无。

## Impact

- **代码层**：
  - `infrastructure/postgres/init/02-create-databases.sql`（改）
  - `infrastructure/docker-compose.yml`（改，三处）
- **依赖**：无新增
- **CLAUDE.md 端口表**：不修改
- **openspec/config.yaml §apply.rules**：
  - "MUST: 服务容器在 infrastructure/docker-compose.yml 注册" — **满足**（本 change 改的就是该文件）
  - "MUST: 健康检查用 HTTP GET" — 满足（既有 healthcheck 不动）
  - "MUST: 引用 eng-review Arch #1 egress 强制点" — 不适用（不动 service 代码，echo stub 保持既有）

## Non-goals

- **不** 修 port 8000 冲突（环境特定 — Trae IDE 占；不是 code bug）
- **不** 修 test stack 缺 `/api/auth/login`（需 test-iam 服务，独立 change）
- **不** 修 canvas `pnpm build` tsc 预存错误（独立 change 修 canvas 源码）
- **不** 重写 compose 文件结构（仅最小修改）
- **不** 加 CI 接入（仓库 0 CI 仍持续）
- **不** 删 `infrastructure/postgres-init-test/`（test independence 保留）
- **不** 改 `infrastructure/postgres/init/01-credential-schema.sql`（已正确）

## Open Questions

- **OQ1**：本机 port 8000 冲突导致 full `docker compose -p chatbiz up` 跑不通，验证只能用部分 service。**Mitigation**：verify 阶段拆为 unit（SQL/PYTHONPATH/seed 单独验证）+ integration（postgres 起来后 init 跑通）。
- **OQ2**：master key seed 跑两次幂等吗？**答**：dev compose 的 `if active == 0: insert` 守卫已保证。
- **OQ3**：fix 后 `postgres-init-test/` 还需要吗？**答**：保留。test stack 不应依赖 production fix 落地；冗余回退是好实践。
