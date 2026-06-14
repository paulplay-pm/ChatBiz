# fix-production-compose Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development
> to implement this plan task-by-task. apply 阶段按本 plan 跑——agent 应在每个 task 落地前**自行展开** micro-step，不机械照抄。

**Goal:** 修 `infrastructure/docker-compose.yml` + `infrastructure/postgres/init/02-create-databases.sql` 的 3 个 latent bug（Postgres 16 DO block / `*-migrate` 缺 PYTHONPATH / credential 缺 master key seed）。完成后干净 dev 机 `docker compose -p chatbiz up` 可一次性 healthy。

**Architecture:** 3 个 fix 全部对齐 `infrastructure/docker-compose-dev.yml` 已有正确实现。SQL fix 用 psql `\gexec` 替代 `DO $$` 块。PYTHONPATH 在 compose env 设。credential seed 用 bash + Python heredoc（与 dev 一致）。

**Tech Stack:**
- Docker 24+ / docker compose 2.20+
- PostgreSQL 16+ (psql \gexec)
- Python 3.12 (alembic in user site-packages)
- bash (heredoc seed)

---

> **OPT — writing-plans skill fallback**：当前 session skills 列表**未**装载 `superpowers:writing-plans`（与 web-integration-test-suite 一致）。按 schema `plan.instruction` 提示手写。模式：节级 micro-step 模板 + 关键 task 完整展开。

---

## Phase 1: 3 个 Fix

### Task 1.1 ★: Bug #1 — 02-create-databases.sql 改 \gexec

**Files:**
- Modify: `infrastructure/postgres/init/02-create-databases.sql`

**Step 1**: Read current 02-create-databases.sql to see exact line numbers
**Step 2**: Replace the `DO $$ ... END $$;` block with two `SELECT 'CREATE DATABASE ...' \gexec` statements (one per database)
**Step 3**: Verify `grep -c "DO \\\$\\\$" infrastructure/postgres/init/02-create-databases.sql` returns 0
**Step 4**: Verify file syntax with `docker run --rm -v $(pwd)/infrastructure/postgres/init:/sql postgres:16-alpine sh -c "psql -f /sql/02-create-databases.sql --set ON_ERROR_STOP=1"` against a test database (skip if too involved; rely on integration test)

### Task 1.2: Bug #2 — 3 个 migrate 容器加 PYTHONPATH

**Files:**
- Modify: `infrastructure/docker-compose.yml` (3 services)

**Step 1**: Read current docker-compose.yml migrate service blocks (line ~100, ~170, ~270)
**Step 2**: For `credential-migrate` (line ~100), add `PYTHONPATH: /home/credential/.local/lib/python3.12/site-packages:/app` to `environment` block
**Step 3**: For `audit-and-isolation-migrate` (line ~170), add `PYTHONPATH: /home/audit/.local/lib/python3.12/site-packages:/app`
**Step 4**: For `workflow-engine-migrate` (line ~270), add `PYTHONPATH: /home/wf/.local/lib/python3.12/site-packages:/app`
**Step 5**: Verify with `docker compose -p chatbiz -f infrastructure/docker-compose.yml config` (syntax check)

### Task 1.3 ★: Bug #3 — credential-migrate command 改 bash + heredoc

**Files:**
- Modify: `infrastructure/docker-compose.yml` `credential-migrate.command`

**Step 1**: Read `docker-compose-dev.yml` line 67-86 to copy the seed heredoc pattern
**Step 2**: In production `docker-compose.yml` `credential-migrate`, replace `command: ["alembic", "upgrade", "head"]` with `command: ["bash", "-c", "alembic upgrade head && python -c '<heredoc>'"]`
**Step 3**: Heredoc content matches dev compose:
```python
import asyncio, os, secrets, uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
async def main():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        active = (await conn.execute(
            text("SELECT count(*) FROM encryption_keys WHERE status IN ('ACTIVE', 'active')")
        )).scalar_one()
        if active == 0:
            await conn.execute(
                text("INSERT INTO encryption_keys (key_id, encrypted_key, status) VALUES (:key_id, :encrypted_key, 'ACTIVE')"),
                {"key_id": uuid.uuid4(), "encrypted_key": secrets.token_bytes(32)},
            )
    await engine.dispose()
asyncio.run(main())
```

**Step 4**: Verify with `docker compose config` syntax check

## Phase 2: 端到端验证

### Task 2.1: 干净 dev 机 production 全栈 up

**Step 1**: 确认 port 8000 / 8080 / 5173 等未被占用（`lsof -i :8000` 等）
**Step 2**: `docker compose -p chatbiz down -v` 清空（destructive，verify 文档中已显式标注）
**Step 3**: `docker compose -p chatbiz up --wait` 启动；最大超时 5min
**Step 4**: `docker compose -p chatbiz ps` 7 service 全 healthy
**Step 5**: `curl http://localhost:5173/healthz` 返回 200

### Task 2.2: test stack 仍可用

**Step 1**: `make test-integration down`
**Step 2**: `make test-integration up`（重新 build dist + 起 test compose）
**Step 3**: 7 service healthy

### Task 2.3: 文档同步

**Step 1**: 修改 `web/integration-tests/README.md` § Known Issues：把 #1-#3 标记为"已修"，但保留 #4-#6
**Step 2**: Add "已修" prefix to #1-#3, link to this change's verify.md

## Critical Path

Phase 1 (3 fixes) → Phase 2 (verification) 串行；Phase 1 内 3 个 fix 可并行 commit。

## 关键依赖

- Docker daemon 运行中
- 本机 port 5173 / 8000 / 8080 / 5432 / 6379 可用（无 Trae IDE 等占）
- 网络可拉 `postgres:16-alpine` / `redis:7-alpine` / `nginx:1.27-alpine` 镜像
- `web/canvas/dist` + `web/admin/dist` 已 build（Makefile 自动化）

## 风险节点

1. **本机 port 8000 被 Trae IDE 占**（与 web-integration-test-suite 同样问题）— verify 阶段拆为可单独验证的子任务（SQL fix / PYTHONPATH fix / seed fix 各自单测）。Full 7-service up 需干净 dev 机。
2. **postgres data volume 已有 bug #1 失败中间态** — verify 第一步 `docker compose down -v`。
3. **PYTHONPATH 路径硬编码** — Python 3.12 是当前；升 Python 需同步改。

## 验收 gate

- [ ] `docker compose -p chatbiz -f infrastructure/docker-compose.yml config` 退出码 0（语法）
- [ ] 干净 dev 机 `docker compose -p chatbiz up --wait` 全栈 healthy
- [ ] `curl http://localhost:5173/healthz` 200
- [ ] test stack 仍可用（`make test-integration up`）
- [ ] `openspec validate fix-production-compose` valid
- [ ] 旧 `DO $$` 块从 init script 移除（grep 输出 0）
- [ ] README Known Issues #1-#3 标记 resolved
