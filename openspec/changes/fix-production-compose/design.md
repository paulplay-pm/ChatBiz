# fix-production-compose — Design

## Context

`infrastructure/docker-compose.yml` 3 个 latent bug 阻塞 production 路径启动：

- **Bug #1**：`postgres/init/02-create-databases.sql` 用 `DO $$ ... EXECUTE 'CREATE DATABASE ...' END $$;` 块创建 `audit_isolation` / `workflow_engine` 库。Postgres 16 抛 `ERROR: CREATE DATABASE cannot be executed from a function`，所有依赖 postgres 的 service 不启动。
- **Bug #2**：3 个 `*-migrate` 一次性容器（`credential-migrate` / `audit-and-isolation-migrate` / `workflow-engine-migrate`）在 compose env 只设 `DATABASE_URL`，不指 `~/.local/lib/python3.12/site-packages/`，alembic 跑不起来报 `ModuleNotFoundError: No module named 'alembic'`。
- **Bug #3**：`credential-migrate` alembic 成功但 credential service 启动时 `crypto.py:load_master_key` 在 `encryption_keys` 表空时抛 `MasterKeyNotFoundError`，`lifespan` 抛 `SystemExit(1)`。

**参考基线**（已有正确实现）：
- `infrastructure/docker-compose-dev.yml` line 47-87：三个 migrate 显式设 `PYTHONPATH`；line 67-86：credential-migrate 在 alembic 后跑 Python heredoc seed
- `web-integration-test-suite` 改动的 `infrastructure/postgres-init-test/02-create-databases.sql`：用 psql `\gexec` 替代 `DO $$` 块

**eng-review 锁定决策**：
- **Test #1** (P1)：3 层测试金字塔 — 阻塞在 bug #1/#2/#3
- **Test #2** (P1)：4 critical path — ① paul 财务月报 partial 覆盖，②③④ 留 spec 钩子
- **Arch #1** (P1)：egress 强制点 — 不动（echo stub 已通过 7 个单测）

**stakeholder**：devops（compose 维护 1 人）、后端（service 启动需 compose healthy）

## Goals / Non-Goals

**Goals**：
- `infrastructure/postgres/init/02-create-databases.sql` 用 psql `\gexec` 替代 `DO $$` 块；Postgres 16+ 兼容
- 3 个 `*-migrate` 服务加 `PYTHONPATH` env；alembic upgrade head 跑得通
- `credential-migrate` 加 master encryption key seed；credential service `lifespan` 不再 fail
- 修改与 dev compose 已有正确实现一致（DRY）
- `infrastructure/postgres-init-test/` 保留为 test stack 独立回退

**Non-Goals**：
- 修 port 8000 冲突（环境特定 — Trae IDE）
- 修 test stack 缺 `/api/auth/login`（独立 change）
- 修 canvas `pnpm build` tsc 预存错误（独立 change）
- 重写 compose 文件结构
- 加 CI 接入
- 改 `docker-compose-dev.yml`（已正确）
- 改 `docker-compose-test.yml`（已自带 workaround）
- 改 `postgres/init/01-credential-schema.sql`（已正确）

## Decisions

### D1：02-create-databases.sql 改用 psql `\gexec`

**选择**：把 `DO $$ ... END $$;` 块替换为 `SELECT 'CREATE DATABASE ...' WHERE NOT EXISTS (...) \gexec`。

**理由**：
- `psql` 在 `postgres:16-alpine` 镜像内自带，无需新工具
- `\gexec` 把 SELECT 结果作为 SQL 执行，Postgres 16 允许在脚本顶层调用 `CREATE DATABASE`（仅 PL/pgSQL 块内不允许）
- 与 `web-integration-test-suite/infrastructure/postgres-init-test/02-create-databases.sql` 完全一致
- 保留 `\connect` + `GRANT` 步骤不变（这些没有 DO block 包裹，不受影响）

**已考虑 alternative**：
- **A. 用 `psql -c` 子进程调用** — 拒绝：脚本会失去单事务性 + 复杂度上升
- **B. 用 init container 跑 Python 脚本创建库** — 拒绝：增加镜像依赖；与现有 SQL init 模式偏离
- **C. 改 Postgres 镜像到 14 / 13** — 拒绝：downgrade 安全风险高；不解决根本问题

### D2：PYTHONPATH 在 compose env 而非 Dockerfile

**选择**：3 个 migrate 服务各加 `PYTHONPATH: /home/<user>/.local/lib/python3.12/site-packages:/app`，与 dev compose 一致。

**理由**：
- 一行 env 即可，避免改每个 service 的 Dockerfile（3 个 service × Dockerfile 风险面更大）
- 与 dev compose 已有正确实现一致
- Python 3.12 路径硬编码；若 image 升 Python 需同步改（dev compose 也用同样硬编码，drift 一致）

**已考虑 alternative**：
- **A. 改 Dockerfile 把 site-packages 装到 /usr/lib/python3.12/site-packages** — 拒绝：dev compose 不一致；需要改 3 个 Dockerfile
- **B. 改用 `pip install --break-system-packages --target /app/.libs` 然后 PYTHONPATH=/app/.libs** — 拒绝：偏离现有 Dockerfile 构建模式
- **C. 改用 editable install (pip install -e .)** — 拒绝：dev compose 不一致；MRO 复杂

### D3：credential-migrate command 改为 bash + heredoc seed

**选择**：把 `command: ["alembic", "upgrade", "head"]` 改为 `command: ["bash", "-c", "alembic upgrade head && python -c '<seed heredoc>'"]`，与 dev compose 已有实现完全一致。

**理由**：
- 与 dev compose 一致（DRY 原则）
- seed 幂等（`if active == 0: insert` 守卫）；多次跑不重复
- 用 `secrets.token_bytes(32)` 生成随机 32-byte key（与既有 crypto.py 一致）

**已考虑 alternative**：
- **A. 在 credential service 启动时自动 seed** — 拒绝：模糊了"infra bootstrap" vs "service startup" 边界；dev compose 也不这么做
- **B. 用 init SQL 插入 key** — 拒绝：key 是 32 random bytes，SQL 表达力差
- **C. 跳过 seed + 改 credential 启动逻辑允许 "no key" 状态** — 拒绝：会改变业务逻辑（credential 服务必须有 master key 才能加解密）

### D4：保留 test stack 的 `postgres-init-test/` workaround

**选择**：不删 `infrastructure/postgres-init-test/02-create-databases.sql` 和 `01-credential-schema.sql`。

**理由**：
- test stack 不应依赖 production fix 落地（test independence 是好实践）
- production fix 与 test workaround 共存 = 冗余回退
- 删除需要单独 change 验证 + 跨 service 影响

**已考虑 alternative**：
- **A. 删 test workaround 让 test stack 用 production init** — 拒绝：会让 test stack 在 production fix 前的中间态变脆弱

## Risks / Trade-offs

**[Risk] 干净 dev 机验证需要 port 8000 可用** — Trae IDE 占着。**Mitigation**：本机可单独验证每个 fix 的单元效果（`docker compose up postgres` 看 init 跑通 + `docker compose run audit-and-isolation-migrate` 看 alembic 成功 + 用 `pytest` 风格 stub 跑 seed 逻辑）。完整 `docker compose -p chatbiz up` 在 CI 干净环境跑（后续 change）。

**[Risk] postgres data volume 已有失败中间态** — 旧 volume 含 bug 跑一半状态。**Mitigation**：verify 阶段第一步 `docker compose -p chatbiz down -v` 清 volume；步骤明确写在 verify.md。

**[Risk] PYTHONPATH 路径硬编码** — Python 3.12 是当前生产版本；升 Python 需同步改 compose（3 处）。**Mitigation**：dev compose 也用同样硬编码；future change 一并升级。

**[Risk] master key seed 启动顺序敏感** — `credential-migrate` 必须先于 `credential` 完成（`depends_on: service_completed_successfully`）。**Mitigation**：既有 compose 已用 `service_completed_successfully`，无需改。

**[Trade-off] 不动 dev compose** — 接受。dev compose 是 reference implementation，本 change 对齐它而非反过来。

**[Trade-off] 不动 test compose** — 接受。test compose 已自带 workaround；fix 后两边都能跑是好的冗余。

## Migration Plan

**本 change 不涉及 production 数据迁移** — 仅改 infrastructure 配置。修改后**首次启动需要 `docker compose -p chatbiz down -v`** 清掉 bug #1 失败的旧 volume（verify.md 显式说明）。

**部署顺序**：
1. 修改 `infrastructure/postgres/init/02-create-databases.sql`（\gexec 写法）
2. 修改 `infrastructure/docker-compose.yml`（3 处 PYTHONPATH + 1 处 credential-migrate command）
3. 验证：干净 dev 机（无 port 8000 冲突）`docker compose -p chatbiz down -v && docker compose -p chatbiz up` 全栈 healthy

**rollback**：
- revert commit 即可（无数据迁移）
- 旧 `DO $$` 脚本在 Postgres 14/15 仍可用（仅 Postgres 16+ 报错）

## Open Questions

- **OQ1**：本机能否完整验证？**答**：拆为 unit（每个 fix 单独验）+ 部分 integration（postgres 起来后 init 跑通）。完整 7-service 启动需干净 dev 机。
- **OQ2**：master key seed 幂等吗？**答**：是。`if active == 0: insert` 守卫。
- **OQ3**：fix 后 `postgres-init-test/` 还需要吗？**答**：保留，test independence。
