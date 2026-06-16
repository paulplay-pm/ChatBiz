# fix-migrate-hostname — Proposal

## Why

`8c0df0b fix(infrastructure): base compose service key 对齐 container_name` (2026-06-14) 把 `postgres:` service key 改名为 `chatbiz-postgres:` 满足 `CLAUDE.md` 强制约定。但**该 change 期间基线 12 service 内部引用的 hostname 没同步更新** — `infrastructure/docker-compose.yml` 仍有 9 处 `postgres:5432`,覆盖 `credential` / `credential-migrate` / `credential-cron` / `audit-and-isolation-migrate` / `workflow-engine-migrate` 等 4+ service 段。

后果: 跑 `docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose-dev.yml up -d` 时,4 个 `*-migrate` 一次性 container 全部 fail (`ConnectionError: unexpected connection_lost() call` 在 asyncpg SSL upgrade 阶段 — hostname `postgres` 在 compose 内 DNS 不存在),blocking `credential` / `audit-and-isolation` / `workflow-engine` 通过 `depends_on: service_completed_successfully` 起来。整个 stack 起不来。

## What Changes

- **修改** `infrastructure/docker-compose.yml`: 9 处 `postgres:5432` 全部替换为 `chatbiz-postgres:5432`,覆盖 `credential` (2 处: `DATABASE_URL` + `CREDENTIAL_DB_URL`) + `credential-migrate` (1 处: `DATABASE_URL`) + `credential-cron` (1 处: `CREDENTIAL_DB_URL`) + `audit-and-isolation-migrate` (1 处: `DATABASE_URL`) + `workflow-engine-migrate` (1 处: `DATABASE_URL`) + 其它可能的 env vars (3 处)
- **不** 改 `infrastructure/docker-compose-dev.yml` (line 242/264 已用 `chatbiz-postgres:5432`,正确)
- **不** 改 `infrastructure/docker-compose-test.yml` (test compose 隔离网络 by design,`CLAUDE.md` 命名规范段明确"test compose by design 隔离网络 + 独立命名空间,不归本规范管")
- **不** 改 `infrastructure/docker-compose-e2e-ha.yml` (独立 e2e stack, 用 `chatbiz-e2e-ha-postgres`)
- **不** 改 service key `chatbiz-postgres` (该改名是 `8c0df0b` 完成的,本 change 不重复)
- **不** 改任何 Python 后端源码 (本 change 0 行 Python)

## Capabilities

### New Capabilities

无。这是 base compose env var hostname 修,不是新 capability。

### Modified Capabilities

- `infra-compose-fixes` (existing capability, archive 2026-06-14 `fix-compose-postgres-naming` 创建): **前端范围** = N/A (无前端变更);**后端范围** = 0 (Python 源码不动);**是否豁免前端** = 是 — 纯 base compose env var 替换,跟前端 0 关系。

## Impact

- **新开发者 onboarding**: 跑 `docker compose -f ... -f ... up -d` 后 4 个 `*-migrate` 全部 `Exited (0)`,`credential` / `audit-and-isolation` / `workflow-engine` / `sso` 能起来,stack ready。
- **CI**: 本 change 不动 `.github/workflows/ci-cov.yml` (ci-cov 是 Python 单测 cov gate,跟 compose 无关)
- **生产部署**: 0 影响 (生产 K8s 不引用 compose hostname,直接用 service DNS)
- **被消费的下游**: `credential-cron` 也改 (1 处 `CREDENTIAL_DB_URL` 用 `postgres:5432`,需要 `chatbiz-postgres:5432`),依赖 `chatbiz-postgres:5432` 后 cron job 能连 DB

## Non-goals

1. **不** 改 test / dev / e2e-ha compose
2. **不** 改 service key (`postgres` → `chatbiz-postgres` 是 `8c0df0b` 完成的)
3. **不** 写新 capability (这是 fix-up,不是新功能)
4. **不** 改 Python 后端源码
5. **不** 改 `.github/workflows/ci-cov.yml` matrix
6. **不** 改 `tools/setup-chatbiz-env.sh` (本 change 跟 dev env setup 0 关系)
