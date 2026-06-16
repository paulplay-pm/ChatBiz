# fix-migrate-hostname — Design

## Context

`8c0df0b fix(infrastructure): base compose service key 对齐 container_name` (2026-06-14 16:38) 把 `postgres:` service key 改名为 `chatbiz-postgres:` 满足 `CLAUDE.md` 强制约定 (service key 必须 `chatbiz-` 前缀)。该 change 把 4 处显式 `postgres:` 段引用 (`credential-migrate` / `audit-and-isolation-migrate` / `workflow-engine-migrate` / `chatbiz-postgres` 段) 都改对了。但**该 change 期间 `infrastructure/docker-compose.yml` 内 9 处 env var hostname `postgres:5432` 没改** — 它们嵌在 4+ service 段的 `environment:` 块内 (`DATABASE_URL` / `CREDENTIAL_DB_URL` 等),属于 baseline 12 service 的"内部"引用,fix-compose change 期间**未触动**。

后果(本 session 2026-06-16 实测): `docker compose -f docker-compose.yml -f docker-compose-dev.yml up -d` 时 `chatbiz-credential-migrate` 报 `ConnectionError: unexpected connection_lost() call` (asyncpg SSL upgrade 阶段,hostname `postgres` 在 compose 内 DNS 不存在)。同理 `chatbiz-audit-isolation-migrate` + `chatbiz-workflow-engine-migrate` + `chatbiz-sso-migrate` 全部 fail,blocking `credential` / `audit-and-isolation` / `workflow-engine` / `sso` 通过 `depends_on: service_completed_successfully` 起来。整个 stack 起不来。

本 change 是 1 个 trivial fix,不是 design 阶段需要 reconcile 的架构决策。

## Goals / Non-Goals

**Goals** (1 条):
1. 改 `infrastructure/docker-compose.yml` 9 处 `postgres:5432` → `chatbiz-postgres:5432`,让 4 个 `*-migrate` 一次性 container 能连到 base compose 的 `chatbiz-postgres` service

**Non-Goals** (4 条,显式 YAGNI):
1. **不** 改 `infrastructure/docker-compose-test.yml` (test compose 隔离网络 by design,`CLAUDE.md` 命名规范段明确 "test compose by design 隔离网络 + 独立命名空间,不归本规范管")
2. **不** 改 `infrastructure/docker-compose-dev.yml` (line 242/264 已用 `chatbiz-postgres:5432`,正确)
3. **不** 改 `infrastructure/docker-compose-e2e-ha.yml` (独立 e2e stack, 用 `chatbiz-e2e-ha-postgres`)
4. **不** 改 service key (`chatbiz-postgres:` 段本身不动,本 change 不重复 `8c0df0b` 的工作)

## Decisions

### D1: sed 替换 9 处,1 个 commit

**Context**: 9 处是简单字符串替换,分布在 4+ service 段。

**选项**:
- **A (已选)**: 1 个 commit,`sed -i '' 's|@postgres:5432|@chatbiz-postgres:5432|g' infrastructure/docker-compose.yml` 一次性改 9 处,commit `fix(infrastructure): rename postgres:5432 → chatbiz-postgres:5432 in *-migrate env vars (fix-compose followup)`
- B: 4 个 commit,每个 service 段一个 — 拒绝理由:over-engineered,1 个 commit 已经足够表达"1 个 fix"
- C: 跑 1 个 openspec change + 1 个 sed — 已选 A,跟 C 等价但 commit message 更具体

**结论**: 选 A。

### D2: 验证方法

**Context**: 修后必须验证 `docker compose up -d` 跑通。

**选项**:
- **A (已选)**: 跑 `docker compose -f docker-compose.yml -f docker-compose-dev.yml up -d`,然后 `docker ps -a --filter name=chatbiz-credential-migrate --filter name=chatbiz-audit-isolation-migrate --filter name=chatbiz-workflow-engine-migrate --filter name=chatbiz-sso-migrate --format "{{.Names}}: {{.Status}}"`,期望 4 个 container 都 `Exited (0)` (成功的 one-shot migrate)
- B: 只跑 `docker compose config` 验证 hostname 替换 — 拒绝理由:不够,不能确认 migrate 真的跑通

**结论**: 选 A。

## Risks / Trade-offs

- **Risk 1 (低)**: sed 误改非 `postgres:5432` 字符串 — 经 grep 确认 9 处全在 base compose,无其他 `postgres:5432` 出现 (test compose 8 处不归本 change 改,grep 验证已做)
- **Risk 2 (低)**: `docker compose config` 不报错但 runtime 仍 fail — 已选 A 方案用 `docker compose up -d` 真实起,跑 migrate container,exit 0 才是真验证

## Migration Plan

| # | Step | 产物 |
|---|---|---|
| 1 | `sed -i '' 's|@postgres:5432|@chatbiz-postgres:5432|g' infrastructure/docker-compose.yml` | base compose 9 处替换 |
| 2 | `grep -c "postgres:5432" infrastructure/docker-compose.yml` 期望输出 0 | 验证 9 处全部替换 |
| 3 | `git diff --stat infrastructure/docker-compose.yml` 期望输出 1 file changed, 9 insertions, 9 deletions | 验证 diff 范围 |
| 4 | `docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose-dev.yml up -d` 跑 ~30s,期望 4 个 `*-migrate` 都 `Exited (0)` | 端到端验证 |
| 5 | `git add infrastructure/docker-compose.yml && git commit -m "..."` | 1 commit |
| 6 | merge to main + push + archive + retrospective | 收尾 |

**Rollback**: 任何步骤失败 → `git revert` 已 push 的 commits。

## Verification

| # | 验证项 | 命令 | 期望 |
|---|---|---|---|
| V1 | base compose 0 处 `postgres:5432` | `grep -c "postgres:5432" infrastructure/docker-compose.yml` | `0` |
| V2 | base compose 9 处 `chatbiz-postgres:5432` | `grep -c "chatbiz-postgres:5432" infrastructure/docker-compose.yml` | `9` |
| V3 | diff 范围正确 | `git diff --stat` (修前) | `1 file changed, 9 insertions(+), 9 deletions(-)` |
| V4 | 4 个 `*-migrate` 都 `Exited (0)` | `docker ps -a --filter name=*-migrate --format "..."` | 4 行 `Exited (0)` |

## Open Questions

无。这是一个 trivial 1-commit fix,没有 Open Questions 段。如果验证 V4 失败,需要回到 D2 重新分析 root cause (可能是 chatbiz-postgres 健康检查没起来、或 credential migration 自身的 Python bug),不阻塞本 change 落地。
