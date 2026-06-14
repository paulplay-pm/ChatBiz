# fix-production-compose — Brainstorm

> Raw capture of exploration thinking. `superpowers:brainstorming` skill 不可用，按 fallback 手写 decision log。

---

## 背景与现状

`web-integration-test-suite` change 在 apply 阶段发现 `infrastructure/docker-compose.yml` 有 3 个 production compose bug 阻塞 test stack 启动：

1. **Postgres 16 拒绝 `DO $$ ... CREATE DATABASE ... END $$` 块**
   - 文件：`infrastructure/postgres/init/02-create-databases.sql`
   - 现象：`ERROR: CREATE DATABASE cannot be executed from a function` → `pg_isready` healthcheck never passes → 所有依赖 postgres 的 service 不启动
   - 根因：Postgres 16 起 `CREATE DATABASE` 不可在 function/PL/pgSQL 块内执行（之前版本允许）

2. **`*-migrate` 容器缺 `PYTHONPATH`**
   - 文件：`infrastructure/docker-compose.yml` 三个 migrate 服务（`credential-migrate` / `audit-and-isolation-migrate` / `workflow-engine-migrate`）
   - 现象：`ModuleNotFoundError: No module named 'alembic'`（alembic 装在 `~/.local/lib/python3.12/site-packages/`，但环境变量未指向）
   - 根因：dev compose (`docker-compose-dev.yml`) 显式设 `PYTHONPATH=...`，production compose 漏设

3. **credential service 缺 master encryption key seed**
   - 文件：`infrastructure/docker-compose.yml` `credential-migrate` 容器
   - 现象：`MasterKeyNotFoundError: no active master key in encryption_keys` → `lifespan` 抛 `SystemExit(1)` → credential service 不启动
   - 根因：dev compose 在 alembic upgrade 后用 Python heredoc 插入一条 active key；production compose 漏

**test stack 现状**（`docker-compose-test.yml`）：3 个 workaround 已就位
- 自带 `infrastructure/postgres-init-test/02-create-databases.sql` 绕开 bug #1
- 自带 `PYTHONPATH` 修 bug #2
- bug #3 未在 test stack 修复（依然 fail）

**eng-review 决策**（与本 change 关联）：
- **Test #1** (P1)：3 层测试金字塔 — 阻塞在 bug #1/#2/#3
- **Test #2** (P1)：4 critical path — ① paul 财务月报 partial 覆盖，②③④ 留 spec 钩子
- **Arch #1** (P1)：egress 强制点 — echo stub 已实现并通过 7 个单测

**本 change 不修的 3 个独立问题**（已显式 follow-up 在 `web-integration-test-suite/verify.md`）：
- port 8000 冲突（环境特定 — Trae IDE 占）— 不是 production compose bug
- test stack 缺 `/api/auth/login` — 需 test-iam 服务（独立 change）
- canvas `pnpm build` 跑 tsc 报预存类型错误 — 独立 change 修 canvas 源码

---

## 候选方案

### 方案 A：直接修 production compose 三处（推荐）

```text
1. infrastructure/postgres/init/02-create-databases.sql
   把 DO $$ 块改为 psql \gexec（与 postgres-init-test 一致）

2. infrastructure/docker-compose.yml
   三个 migrate 服务各加 PYTHONPATH=/home/<user>/.local/lib/python3.12/site-packages:/app

3. infrastructure/docker-compose.yml credential-migrate
   command 改为 bash -c "alembic upgrade head && python -c '<seed heredoc>'"
   （与 docker-compose-dev.yml 一致）
```

**优点：**
- 修复 production 路径，不引入新文件
- 与 dev compose 对齐（dev 已正确）
- test compose 的 workaround（`postgres-init-test/`）可保留作为回退，不强删

**缺点：**
- 触及 production compose（eng-review 锁定"每次修改需审计"）
- 需在干净 dev 机重跑验证

### 方案 B：让 test stack 不依赖 production compose（独立修复）

不修 production；让 test stack 自带完整修复。

**拒绝理由：** production 路径仍然坏，dev compose 共享同一份 init.sql 也坏。任何用 `docker compose up` 的人都会撞到。

### 方案 C：fork 一份 production 副本

复制 `docker-compose.yml` → `docker-compose-v2.yml`，只改 v2。

**拒绝理由：** 长期维护两份 compose 是 DRY 违反。production compose 应当自带 fix。

---

## Rejected Alternatives

| 方案 | 拒绝理由 |
|---|---|
| B. 只修 test stack 不动 production | dev/prod 共享 init.sql 会同样坏 |
| C. fork 新 compose 文件 | 长期 DRY 违反 |
| 用一次性 alembic 模板 + seed | 偏离 dev compose 的现有 seed 模式 |
| 跳过 production 验证，本地 mock 测试 | 失去"在干净 dev 机跑通"的硬证据 |

---

## 关键决策

### D1：3 个 fix 都对齐 docker-compose-dev.yml 已有正确实现
dev compose 已经把这 3 处做对了，production 落后。Fix 即"backport dev 的正确做法"。

### D2：02-create-databases.sql 改用 psql `\gexec`
不引入新工具（`psql` 已在镜像内）。`\gexec` 把 SELECT 结果当 SQL 执行，Postgres 16 允许。

### D3：PYTHONPATH 加在 compose env 而非 Dockerfile
不改 Dockerfile（每个 service 改 Dockerfile 风险面更大；compose env 一行即可）。三个 user 路径已知（`/home/credential` / `/home/audit` / `/home/wf`）。

### D4：credential-migrate seed 与 dev compose 完全一致
避免引入第二种 seed 模式。命令是 bash + heredoc（与 dev 一致）。**注意**：seed 是幂等的（`if active == 0: insert`），多次跑不重复。

### D5：test stack 的 workaround 保留
`infrastructure/postgres-init-test/` 仍是 test-only 入口。本 change 不删它（保证 test stack 不依赖 production fix；后者 merge 后两边都能跑）。

### D6：openspec/config.yaml §apply.rules "MUST: 服务容器在 production compose 注册"
本 change 显式满足：所有 3 个 fix 都在 `infrastructure/docker-compose.yml` 内。

---

## 风险与 Open Questions

### 风险

1. **本机 port 8000 被 Trae IDE 占** — production compose 启动时 `docker compose up credential` 会 fail。**Mitigation**：在干净 dev 机验证；本机跑测试时临时停 Trae。
2. **postgres data volume 已有数据** — 旧 volume 包含 `CREATE DATABASE` 失败的中间态。**Mitigation**：验证步骤用 `docker compose down -v` 清空。
3. **PYTHONPATH 路径在 image 升级时会变** — 比如 Python 3.13 → 路径变 `/python3.13/`。**Mitigation**：用 `python3 -c "import sys; print(sys.path)"` 在容器内查实际路径；如有更稳的方案用 `pip show alembic | grep Location`。
4. **master key seed 跑两次** — alembic 成功后 Python heredoc 跑；多次重启 `credential-migrate` 不会重复插入（idempotent guard）。

### Open Questions

1. **OQ1**：fix 后是否在干净 dev 机跑完整 `make test-integration up` + `make test-integration test` 验证？**答**：是，作为 verify §5 的 checkable 项。
2. **OQ2**：dev compose 是否同步 fix？**答**：dev compose 已正确（这正是它 work 的原因），不需要改。
3. **OQ3**：test compose 的 `postgres-init-test/` 文件是否在 production fix 合并后删除？**答**：保留，test stack 仍可独立于 production 启动（test independence is a feature）。

---

## 与 eng-review 锁定决策的映射

| eng-review finding | 本 change 如何覆盖/对齐 |
|---|---|
| **Test #1** 3 层测试金字塔 | 解阻塞 ① vitest integration ② playwright integration |
| **Test #2** 4 critical path 100% | 解阻塞 ① paul 财务月报 partial → 后续 change 补 login 端点 |
| **Arch #1** egress 强制点 | 本 change 不动 echo stub（已有 7 个单测） |

---

## 下一步

1. 写 `proposal.md`：scope = 3 production compose fix
2. 写 `design.md`：fix 列表 + 验证矩阵
3. 写 `specs/infra-compose-fixes/spec.md`：3 个 Requirement（每个 fix 一个）
4. 写 `tasks.md`：8-10 个 task（3 编码 + 3 验证 + 文档）
5. 写 `plan.md`、`verify.md`、`retrospective.md`
6. apply 阶段：在干净 dev 机上 `docker compose up` 验证全栈 healthy

---

## 备注

- 本 change **仅** 改 `infrastructure/` 与 `infrastructure/postgres/init/`。**不动** service 代码、不动 frontend、不动 openspec config。
- 本机不能完整跑 production compose 验证（port 8000 冲突），但可以验证 SQL fix + PYTHONPATH fix + master key seed fix 的**单元/集成**效果（如 `docker compose -p chatbiz up postgres` + 检查 init scripts 跑通）。
