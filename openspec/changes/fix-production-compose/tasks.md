# fix-production-compose — Tasks

> **Scope**：修 `infrastructure/docker-compose.yml` + `infrastructure/postgres/init/02-create-databases.sql` 的 3 个 latent bug（Postgres 16 DO block / `*-migrate` 缺 PYTHONPATH / credential 缺 master key seed）。完成后干净 dev 机 `docker compose -p chatbiz up` 可一次性 healthy。
>
> **不** 改：service 源码 / frontend / `docker-compose-dev.yml`（已正确）/ `docker-compose-test.yml`（已自带 workaround）/ `postgres/init/01-credential-schema.sql`（已正确）/ port 8000 冲突（环境特定）/ test-iam 缺 login 端点（独立 change）/ canvas tsc 预存错误（独立 change）。
>
> **前置门**：仓库处于 post-`web-integration-test-suite` apply 状态；`web/integration-tests/README.md` 详述 3 个 bug；dev compose (`docker-compose-dev.yml`) 已有正确实现作为参考。

## 0. 前置门

- [ ] 0.1 验 `docker --version >= 24` + `docker compose version >= 2.20` + `git --version` + `conda --version`（按 memory 规则，**禁止**用 anaconda3 base / uv，必须 `conda activate chatbiz`）。验：`docker -v` + `docker compose version` + `git --version` + `conda --version`。

## 1. Bug #1：02-create-databases.sql 改 psql \gexec

- [ ] 1.1 修改 `infrastructure/postgres/init/02-create-databases.sql`：把 `DO $$ ... EXECUTE 'CREATE DATABASE ...' END $$;` 块替换为 `SELECT 'CREATE DATABASE <name>' WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = '<name>') \gexec`（与 `infrastructure/postgres-init-test/02-create-databases.sql` 一致）。**编码规范**：保留 `\connect` + `GRANT` 步骤不变。**安全清单**：不引新工具。验：`grep -c "DO \\\$\\\$" infrastructure/postgres/init/02-create-databases.sql` 输出 0。
- [ ] 1.2 **验证**：1.1 改动后 `docker compose -p chatbiz up postgres` 干净启动时 `02-create-databases.sql` 跑通，`psql -U chatbiz -l` 列出 3 个库。**任务配对验证**：与 1.1 编码任务一一对应。

## 2. Bug #2：3 个 *-migrate 容器加 PYTHONPATH

- [ ] 2.1 修改 `infrastructure/docker-compose.yml` `credential-migrate` 容器：在 `environment` 加 `PYTHONPATH: /home/credential/.local/lib/python3.12/site-packages:/app`。**编码规范**：与 `docker-compose-dev.yml` line 65-66 一致。**安全清单**：env 用 `${VAR:-default}` 语法（如有变量）。验：`grep -n "PYTHONPATH.*credential" infrastructure/docker-compose.yml` 至少 1 匹配。
- [ ] 2.2 修改 `audit-and-isolation-migrate`：加 `PYTHONPATH: /home/audit/.local/lib/python3.12/site-packages:/app`。**编码规范**：与 dev 一致。**安全清单**：路径硬编码（dev 也是硬编码）。验：`grep -n "PYTHONPATH.*audit" infrastructure/docker-compose.yml` 至少 1 匹配。
- [ ] 2.3 修改 `workflow-engine-migrate`：加 `PYTHONPATH: /home/wf/.local/lib/python3.12/site-packages:/app`。**编码规范**：与 dev 一致。**安全清单**：路径硬编码。验：`grep -n "PYTHONPATH.*wf" infrastructure/docker-compose.yml` 至少 1 匹配。
- [ ] 2.4 **验证**：2.1-2.3 改动后 `docker compose -p chatbiz up credential-migrate`（单独跑或随全栈）日志 MUST 不含 `ModuleNotFoundError: No module named 'alembic'`，exit code 0。**任务配对验证**：与 2.1-2.3 编码任务一一对应。

## 3. Bug #3：credential-migrate 加 master key seed

- [ ] 3.1 修改 `infrastructure/docker-compose.yml` `credential-migrate` 容器：把 `command: ["alembic", "upgrade", "head"]` 改为 `command: ["bash", "-c", "alembic upgrade head && python -c '<heredoc>'"]`，heredoc 与 `docker-compose-dev.yml` line 67-86 一致（`if active == 0: INSERT INTO encryption_keys (key_id, encrypted_key, status) VALUES (...)`）。**编码规范**：seed 是 idempotent。**安全清单**：用 `secrets.token_bytes(32)` 生成随机 32-byte key（与 crypto.py 一致）。验：`grep "alembic upgrade head && python" infrastructure/docker-compose.yml` 至少 1 匹配。
- [ ] 3.2 **验证**：3.1 改动后 `docker compose -p chatbiz up credential`（依赖 credential-migrate 已 service_completed_successfully）日志 MUST 不含 `MasterKeyNotFoundError`，`curl http://localhost:8000/healthz` 返回 200。**任务配对验证**：与 3.1 编码任务一一对应。

## 4. 端到端验证

- [ ] 4.1 干净 dev 机（无 port 8000 冲突 + 无现存 postgres data volume）跑 `docker compose -p chatbiz down -v && docker compose -p chatbiz up --wait` 全栈 healthy。**安全清单**：清 volume 是 destructive，verify 前确认无 production 数据。验：`docker compose -p chatbiz ps` 7 service 全 healthy。
- [ ] 4.2 `curl http://localhost:5173/healthz` 200（web → mcp proxy）。**安全清单**：无敏感信息泄露。
- [ ] 4.3 `make test-integration down && make test-integration up` 跑通 test stack（保留 `postgres-init-test/` workaround）。**安全清单**：互斥 production + test 端口（本机若冲突需临时停 dev 进程）。验：7 service healthy。
- [ ] 4.4 **验证**：4.1-4.3 跑通。production 与 test stack 都能起。**任务配对验证**：与 4.1-4.3 端到端任务一一对应。

## 5. 文档同步

- [ ] 5.1 修改 `web/integration-tests/README.md`：把 Known Issues #1 / #2 / #3 标记为"已修（`fix-production-compose` change merged 后）"，但保留 Issues #4-#6（port 冲突 / test-iam / canvas tsc 仍 follow-up）。**编码规范**：中文。**安全清单**：不暴露 test 凭据。验：手读通顺。
- [ ] 5.2 **验证**：5.1 改动后 grep README 找不到 `#1-#3` 仍标 "未修" 关键词。**任务配对验证**：与 5.1 编码任务一一对应。

## 任务统计

- 编码任务：6（1.1 / 2.1 / 2.2 / 2.3 / 3.1 / 5.1）
- 验证任务：5（1.2 / 2.4 / 3.2 / 4.4 / 5.2）
- 端到端任务：3（4.1 / 4.2 / 4.3，含 §4 端到端验收）
- **每条任务** 标注了"编码规范"和"安全清单"（openspec/config.yaml §tasks.rules 强制）
- 全部任务 ≤ 2h 粒度

## 与 proposal Non-goals 对齐

| Non-goal | 如何在本 tasks 中豁免 |
|---|---|
| port 8000 冲突 | §0.1 验 + 4.x 文档化为环境限制（需干净 dev 机） |
| test-iam 缺 login | **未触及**（独立 follow-up change） |
| canvas tsc 预存错误 | **未触及**（独立 follow-up change） |
| dev compose 改动 | dev compose 已正确（不写任务） |
| test compose 改动 | test compose 已自带 workaround（不写任务） |
| 删 `postgres-init-test/` | §5.1 文档明确"保留"（不删） |
