# infra-compose-naming Specification

## Purpose
TBD - created by archiving change fix-compose-postgres-naming. Update Purpose after archive.
## Requirements
### Requirement: base compose service key 跟 container_name 统一

`infrastructure/docker-compose.yml` 的 `postgres` / `redis` service key MUST 改名为 `chatbiz-postgres` / `chatbiz-redis`,**跟既有 `container_name: chatbiz-postgres` / `container_name: chatbiz-redis` 字面对齐**。其它属性（image / environment / volumes / healthcheck / ports） MUST 不变。`<<: *pg-env` yaml anchor 引用 MUST 保持工作。

#### Scenario: base compose service key 改名
- **WHEN** 读 `infrastructure/docker-compose.yml` line 22-50 段
- **THEN** service key MUST 是 `chatbiz-postgres`(不是 `postgres`)
- **AND** `container_name: chatbiz-postgres` 不变
- **AND** `image: postgres:16-alpine` 不变
- **AND** `environment: <<: *pg-env` 不变

#### Scenario: redis service key 改名
- **WHEN** 读 `infrastructure/docker-compose.yml` line ~245 段
- **THEN** service key MUST 是 `chatbiz-redis`(不是 `redis`)
- **AND** `container_name: chatbiz-redis` 不变
- **AND** `image: redis:7-alpine` 不变

#### Scenario: 旧 service key 全部移除
- **WHEN** `grep -nE "^  (postgres|redis):" infrastructure/docker-compose.yml` 跑
- **THEN** 输出 MUST 为 0(只允许 `chatbiz-postgres:` / `chatbiz-redis:`)

### Requirement: 6 个 `depends_on` 引用同步改

`infrastructure/docker-compose.yml` 中所有 `depends_on: postgres` MUST 改 `depends_on: chatbiz-postgres`,所有 `depends_on: redis` MUST 改 `depends_on: chatbiz-redis`。涉及 service 段:`workflow-engine` / `workflow-engine-migrate` / `audit-and-isolation` / `audit-and-isolation-migrate` / `credential` / `credential-migrate` / `credential-cron`。healthcheck / depends_on 内部 `condition: service_healthy` 块结构 MUST 保持。

#### Scenario: workflow-engine 段 depends_on 改
- **WHEN** 读 `infrastructure/docker-compose.yml` 的 `workflow-engine` service 段
- **THEN** `depends_on:` 块 MUST 含 `chatbiz-postgres:` + `chatbiz-redis:`(不是 `postgres:` / `redis:`)

#### Scenario: 3 个 migrate 段 depends_on 改
- **WHEN** 读 `credential-migrate` / `audit-and-isolation-migrate` / `workflow-engine-migrate` 三段
- **THEN** 它们的 `depends_on:` 块 MUST 引用 `chatbiz-postgres:`(不是 `postgres:`)
- **AND** condition 块结构不变(`condition: service_healthy`)

#### Scenario: audit-and-isolation + credential + credential-cron 段 depends_on 改
- **WHEN** 读这 3 段
- **THEN** 它们的 `depends_on:` 块 MUST 引用 `chatbiz-postgres:` + `chatbiz-redis:`
- **AND** 旧 `postgres:` / `redis:` MUST 0 残留

#### Scenario: 旧 `depends_on: postgres` / `depends_on: redis` 0 残留
- **WHEN** `grep -nE "depends_on:$|depends_on:[[:space:]]*$" infrastructure/docker-compose.yml` 排除子节点
- **AND** `grep -nE "depends_on:.*\\bpostgres\\b" infrastructure/docker-compose.yml` 跑
- **THEN** 输出 MUST 0 行(所有 postgres 引用都改 chatbiz-postgres)
- **AND** `grep -nE "depends_on:.*\\bredis\\b" infrastructure/docker-compose.yml` 输出 MUST 0 行

### Requirement: dev compose 自动通过 v5.0.2 strict validation

`infrastructure/docker-compose-dev.yml` MUST 0 改动。改 base compose 后,dev compose 6 个 extends 段 + sso-real-impl 加的 sso 段引用 `chatbiz-postgres` / `chatbiz-redis` 自动 resolved(因为 base compose service key 已对齐)。

#### Scenario: dev compose config 跑过
- **WHEN** `docker compose -f infrastructure/docker-compose-dev.yml config --services` 跑
- **THEN** 退出码 MUST 为 0
- **AND** 输出 MUST 含 `sso` / `sso-migrate` / `credential` / `audit-and-isolation` / `workflow-engine` / `workflow-engine-migrate` / `web` / `chatbiz-postgres` / `chatbiz-redis`(跟改 base 之前的 service 列表一致)

#### Scenario: dev compose config 无 undefined service 报错
- **WHEN** `docker compose -f infrastructure/docker-compose-dev.yml config` 跑
- **THEN** stdout MUST 不含 `depends on undefined service` 字符串

#### Scenario: dev compose 文件 0 改动
- **WHEN** `git diff main -- infrastructure/docker-compose-dev.yml` 跑
- **THEN** 输出 MUST 为空(本 change 不动 dev compose)

### Requirement: 验证 — 干净 dev 机 7 service 启动

干净 dev 机(无 port 冲突 + 无现存 postgres / redis data volume)跑 `docker compose -f infrastructure/docker-compose-dev.yml up -d` 后,7 service MUST 全部 `State: healthy`:`chatbiz-postgres` / `chatbiz-redis` / `credential` / `audit-and-isolation` / `workflow-engine` / `web` / `sso`(注:`sso` 是 sso-real-impl 已加的,本 change 不动;但启动验证一并跑通证明 base 改名后 sso 段依赖链修复)。

#### Scenario: 共享基础设施 healthy
- **WHEN** 干净 dev 机 `docker compose -f infrastructure/docker-compose-dev.yml up -d chatbiz-postgres chatbiz-redis`
- **THEN** 2 容器 MUST `State: healthy`
- **AND** `docker exec chatbiz-postgres pg_isready -U chatbiz` 退出码 0

#### Scenario: 业务 service 全部 healthy
- **WHEN** 干净 dev 机 `docker compose -f infrastructure/docker-compose-dev.yml up -d credential credential-migrate audit-and-isolation audit-and-isolation-migrate workflow-engine workflow-engine-migrate`
- **THEN** 6 容器 MUST `State: healthy` 或 `State: exited (0)`(migrate 容器是一次性)
- **AND** `curl http://localhost:8000/healthz` (credential) 返回 200
- **AND** `curl http://localhost:8080/healthz` (audit-and-isolation) 返回 200
- **AND** `curl http://localhost:8001/healthz` (workflow-engine) 返回 200

#### Scenario: sso 服务启动成功（sso-real-impl 集成验证）
- **WHEN** 干净 dev 机 `docker compose -f infrastructure/docker-compose-dev.yml up -d sso sso-migrate`
- **THEN** `sso-migrate` MUST `State: exited (0)`(alembic upgrade head 成功)
- **AND** `sso` MUST `State: healthy`
- **AND** `docker exec chatbiz-sso curl -s http://localhost:8007/healthz` 返回 200
- **AND** `docker exec chatbiz-sso curl -s -X POST http://localhost:8007/api/v1/auth/sso/wechat/initiate` 返回 200 + `authorize_url` 字段

#### Scenario: web 容器启动
- **WHEN** 干净 dev 机 `docker compose -f infrastructure/docker-compose-dev.yml up -d web`
- **THEN** `web` MUST `State: healthy`
- **AND** `curl http://localhost:5173/healthz` 返回 200

### Requirement: 验证 — sso-real-impl T5.3-5.5 阻塞链解锁

`openspec/changes/sso-real-impl/tasks.md` §5.3-5.5 标 `[ ]` 的 3 个 sub-step(5.3 `docker compose up` / 5.4 healthz curl / 5.5 initiate curl) MUST 在本 change apply 后可以无阻碍跑过(sso-real-impl 自己后续推进时填)。

#### Scenario: sso-real-impl T5.3 可执行
- **WHEN** sso-real-impl 后续推进到 T5.3
- **THEN** `docker compose -f infrastructure/docker-compose-dev.yml up -d chatbiz-sso` MUST 不再因 `depends on undefined service` 失败
- **AND** 容器 MUST 正常启动

#### Scenario: sso-real-impl T5.4 可执行
- **WHEN** sso-real-impl 后续推进到 T5.4
- **THEN** `docker exec chatbiz-sso curl -s http://localhost:8007/healthz` MUST 返回 200

#### Scenario: sso-real-impl T5.5 可执行
- **WHEN** sso-real-impl 后续推进到 T5.5
- **THEN** `docker exec chatbiz-sso curl -s -X POST http://localhost:8007/api/v1/auth/sso/wechat/initiate` MUST 返回 200 + `authorize_url`

### Requirement: YAML 语法 + 既有 anchor 引用保持

`infrastructure/docker-compose.yml` 改后 MUST 是合法 YAML(yaml 解析无错)。`<<: *pg-env` yaml anchor MUST 仍 resolved(没有因改名而失去 anchor 定义或引用)。

#### Scenario: YAML 合法性
- **WHEN** `python3 -c "import yaml; yaml.safe_load(open('infrastructure/docker-compose.yml'))"` 跑
- **THEN** 输出 MUST 无异常

#### Scenario: pg-env anchor 解析
- **WHEN** `docker compose -f infrastructure/docker-compose.yml config | grep -A 5 "chatbiz-postgres:"` 跑
- **THEN** 输出 MUST 含 `POSTGRES_USER:` / `POSTGRES_PASSWORD:` / `POSTGRES_DB:`(anchor resolved)

### Requirement: 回滚能力

本 change 是 1 commit 改动 base compose 1 个文件 ~10 处。`git revert` 1 个 commit MUST 完全回滚到改前状态,无 schema 迁移 / 数据迁移副作用。

#### Scenario: revert 不丢数据
- **WHEN** `git revert HEAD -- infrastructure/docker-compose.yml && docker compose -f infrastructure/docker-compose-dev.yml up -d` 跑
- **THEN** 容器 MUST 仍能启动(strict validation 失败但容器仍在 — 旧命名,dev compose 引用旧名也 OK)
- **AND** postgres / redis data volume 内容 MUST 不动(本 change 不改 SQL / 不改 schema)

