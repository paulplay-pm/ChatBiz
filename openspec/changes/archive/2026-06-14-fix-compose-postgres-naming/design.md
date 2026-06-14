# fix-compose-postgres-naming — Design

## Context

`infrastructure/docker-compose.yml`(base compose)的 `postgres` / `redis` service key 跟 `container_name: chatbiz-postgres` / `container_name: chatbiz-redis` 不一致。`infrastructure/docker-compose-dev.yml`(dev compose)6 个 extends 段 + sso-real-impl 加的 sso 段在 `depends_on` / `environment` 引用时统一用 `chatbiz-postgres` / `chatbiz-redis`(container_name)。v5.0.2 strict validation 解析 merge 后的 service 引用,只认 service key 名,不认 container_name alias,导致 v5.0.2 下 `docker compose config` 失败,dev compose 6 个 extends 段全部 `depends_on` 无法 resolve。

**触发场景**:`sso-real-impl` V6a T5.2(2026-06-14)首次跑 `docker compose -f infrastructure/docker-compose-dev.yml config`,v5.0.2 strict validation 报 6 处 "undefined service"。

**为什么 V2/V3/V4 没暴露**:旧 docker compose v2 时代 extends merge 行为宽松,拉过来的 `depends_on: postgres` 直接 resolved;v5.0.2 改严格,merge 解析时把 dev compose namespace 里的 `chatbiz-postgres` 引用当 unresolved service。

**eng-review 锁定决策**(与本 change 关联):
- **CLAUDE.md 端口分配表**:`5432 postgres` / `6379 redis` 共享基础设施,容器名 `chatbiz-postgres` / `chatbiz-redis`(port mapping 锁定)
- **Tech #1** (P0): 数据隔离网关 egress 强制点 — 不动 service 代码
- **Tech #11** (P1): 4 critical path 100% 覆盖 — sso 段在 sso-real-impl 验证,本 change 只 fix 基础设施命名

**stakeholder**:
- devops(compose 维护 1 人,eng-review 锁定"每次修改需审计")
- 后端 service dev(所有 service 启动需 compose healthy)
- sso-real-impl 后续推进(本 change 解锁 T5.3-5.5)

## Goals / Non-Goals

**Goals**:
- base compose `postgres` / `redis` service key 改 `chatbiz-postgres` / `chatbiz-redis`,**跟 container_name 统一**
- 6 个 service 段的 `depends_on: postgres` / `depends_on: redis` 同步改
- environment `<<: *pg-env` 引用不变(yaml anchor 在文件内有效)
- volume / network 段不变
- 改后 `docker compose -f infrastructure/docker-compose-dev.yml config` 在 v5.0.2 strict validation 通过
- 改后 dev compose 0 改动
- 改后 sso-real-impl T5.3-5.5 解锁

**Non-Goals**:
- 修 port 8000 冲突(环境特定,Trae IDE 占)
- 重写 compose 文件结构
- 引入 docker compose v2 旧 binary 绕 strict validation
- 加 CI 接入
- 改 dev compose / test compose(都已正确)
- 加 lint / pre-commit hook 防止命名漂移(V6b/V7 任务)
- 改 service 源码
- 改前端 / 文档
- 改 `infrastructure/postgres-init-test/`(test stack 独立)
- 改 `infrastructure/postgres/init/` 任何 SQL 脚本

## Decisions

### D1: base compose service key 跟 container_name 统一

**选择**:把 base compose line 26 `postgres:` → `chatbiz-postgres:`,line 247 `redis:` → `chatbiz-redis:`。**跟 container_name 字面对齐**,心智模型简化("service 名 = 容器名")。

**理由**:
- dev compose 6 个 extends 段 + sso-real-impl 加的 sso 段都已用 `chatbiz-postgres` / `chatbiz-redis` 引用,base 改名后自动 resolved
- 跟 CLAUDE.md 端口分配表"chatbiz-postgres 5432 共享 / chatbiz-redis 6379 共享"心智模型一致
- 长期 DRY(全仓只用一个命名约定)

**拒绝**:
- "保留 `postgres` service key + 改 dev compose 全部引用用 `postgres`": 跟 CLAUDE.md 端口表冲突,长期不一致
- "加 alias 段": 实测 v5.0.2 永远在"修了 A 报错 B",无干净终态
- "在 dev compose 完整重写,不走 extends": 200+ 行重写,等于 fork base,DRY 违反

### D2: 6 个 `depends_on` 引用同步改

**选择**:base compose 6 个 service 段(workflow-engine / workflow-engine-migrate / audit-and-isolation-migrate / audit-and-isolation / credential / credential-migrate / credential-cron)的 `depends_on: postgres` → `chatbiz-postgres`,`depends_on: redis` → `chatbiz-redis`。**机械改动**,改后 `grep "depends_on.*postgres\b\|depends_on.*redis\b" infrastructure/docker-compose.yml` 验证 0 残留(除 `chatbiz-postgres` / `chatbiz-redis`)。

**理由**:跟 D1 同步;服务段内的 healthcheck / migrate order 不变。

### D3: environment `<<: *pg-env` 不变

**选择**:base compose line 31 `environment: <<: *pg-env` 不动。YAML anchor `&pg-env` 在文件内有效,改名不影响 anchor 引用。

**理由**:pg-env anchor 是 POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB 等运行时 env,跟 service key 命名无关。

### D4: 改后 dev compose 0 改动

**选择**:dev compose 6 个 extends 段 + sso 段引用 `chatbiz-postgres` / `chatbiz-redis` 全部保持。base 改名后,extends merge 时 resolved 到 base 的 `chatbiz-postgres` service。

**理由**:dev compose 已是正确状态,改它等于"在错的 base 上硬套对的 dev",base 改对后 dev 自动过。

### D5: 不动 production 部署脚本(本机还没 production)

**选择**:本 change 只改 `infrastructure/docker-compose.yml` 一个文件,不引入新 compose 文件,不引入 production deploy 脚本改动。

**理由**:V2/V3/V4 时代 production 跟 dev 共享 base compose 段(差异在 dev extends),改 base 等于同时修 production。V1 时代没有 production deploy 流程。

### D6: apply 阶段同步 surface 阻塞链给其它 change

**选择**:本 change 合并后,surface 通知:
- `sso-real-impl`: T5.3-5.5 自动解锁
- `gateway-egress-enforcement-p0`: TBD dev compose 验证(本机还没 apply,但 plan 阶段会跑 config 验证)
- `web-integration-test-suite`: 已 apply 8/8,production compose 引用 `chatbiz-postgres` / `chatbiz-redis` 后服务段需同步验证
- `mcp-server-management-ui`: 0/41 tasks 推进中,后续 apply 阶段会跑 dev compose config 验证

**理由**:避免其它 change 后续 apply 时撞相同问题,改后信息统一。

## Architecture

**改动拓扑**(1 文件,~10 处):
```
infrastructure/docker-compose.yml
├── services:                              # line 5
│   ├── chatbiz-postgres:                  # 改 line 26 (was: postgres:)
│   │   ├── image: postgres:16-alpine      # 不变
│   │   ├── container_name: chatbiz-postgres  # 不变
│   │   ├── environment: <<: *pg-env       # 不变
│   │   ├── volumes: ...                    # 不变
│   │   ├── healthcheck: ...                # 不变
│   │   └── ports: - "5432:5432"            # 不变
│   ├── chatbiz-redis:                      # 改 line 247 (was: redis:)
│   │   └── ...
│   ├── credential:                         # 改 depends_on (postgres → chatbiz-postgres)
│   │   └── depends_on:
│   │       ├── chatbiz-postgres: ...       # 改
│   │       └── chatbiz-redis: ...          # 改
│   ├── credential-migrate:                 # 改 depends_on
│   ├── credential-cron:                    # 改 depends_on redis → chatbiz-redis
│   ├── audit-and-isolation:                # 改 depends_on (postgres → chatbiz-postgres, redis → chatbiz-redis)
│   ├── audit-and-isolation-migrate:        # 改 depends_on
│   ├── workflow-engine:                    # 改 depends_on
│   ├── workflow-engine-migrate:            # 改 depends_on
│   ├── web: ...                            # 不变
│   ├── sso: ...                            # 不变(dev compose 已有,本 change 不动 dev)
│   └── sso-migrate: ...                    # 不变
├── volumes: ...                            # 不变
└── networks: ...                           # 不变
```

**未触及**:
- `infrastructure/docker-compose-dev.yml`(已是正确引用,0 改动)
- `infrastructure/docker-compose-test.yml`(test stack 独立)
- 任何 service 源码
- 前端 / 文档
- alembic migration

## Risks

| 风险 | 等级 | 缓解 |
|---|---|---|
| 改 base compose production 路径 | 中 | eng-review 锁定"每次修改需审计" — 本 change 走完整 superpowers-bridge 流程,verify 阶段干净 dev 机 + production compose 跑 14-gate + dev compose 跑 5 路径 curl |
| 6 处 depends_on 机械改动漏改 | 低 | apply 阶段用 `grep "depends_on.*postgres\b\|depends_on.*redis\b" infrastructure/docker-compose.yml` 验证 0 残留(除 `chatbiz-postgres` / `chatbiz-redis`) |
| YAML anchor `<<: *pg-env` 引用破坏 | 低 | 改名不动 anchor 定义 / 引用,apply 阶段 `docker compose config | grep -A 3 "pg-env"` 验证 |
| dev compose 6 个 extends 段需要重写 depends_on | 低 | 不需要 — extends merge 后 v5.0.2 strict validation 拉 base 段(已对齐) |
| production compose 跑 production config 时 dev 路径不可见 | 低 | dev compose + production compose 共用 base 段,验证一遍两边都过 |
| sso-real-impl T5.3-5.5 apply 后还有其它问题 | 中 | T5.3-5.5 跑出非命名问题 → surface 给 sso-real-impl 续作(独立 change) |

## Migration

**前置门**:
- 仓库 `git status` clean
- `docker compose version >= 5.0.2`(本机)
- 干净 dev 机状态(无现存 postgres / redis data volume,或 data volume 内无 production 数据)

**apply 步骤**:
1. 修改 `infrastructure/docker-compose.yml` 7-10 处机械改动
2. `grep "depends_on.*postgres\b\|depends_on.*redis\b" infrastructure/docker-compose.yml` 验证 0 残留(排除 `chatbiz-postgres` / `chatbiz-redis`)
3. `docker compose -f infrastructure/docker-compose.yml config --services` 验证服务列表无 undefined
4. `docker compose -f infrastructure/docker-compose-dev.yml config --services` 验证 dev compose 服务列表无 undefined
5. `docker compose -f infrastructure/docker-compose-dev.yml up -d postgres redis` 启动共享基础设施
6. `docker compose -f infrastructure/docker-compose-dev.yml up -d credential credential-migrate audit-and-isolation audit-and-isolation-migrate workflow-engine workflow-engine-migrate` 启动业务 service
7. `curl http://localhost:8000/healthz` (credential) / `curl http://localhost:8080/healthz` (audit-and-isolation) / `curl http://localhost:8001/healthz` (workflow-engine) 全部 200
8. `docker compose -f infrastructure/docker-compose-dev.yml up -d sso sso-migrate` 启动 sso
9. `docker exec chatbiz-sso curl -s http://localhost:8007/healthz` 返回 200
10. `docker exec chatbiz-sso curl -s -X POST http://localhost:8007/api/v1/auth/sso/wechat/initiate` 返回 200 + authorize_url
11. `docker compose -f infrastructure/docker-compose-dev.yml down` 关停
12. `git add infrastructure/docker-compose.yml && git commit -m "fix(infrastructure): base compose service key 对齐 container_name"`

**回滚**:
- 1 commit revert 即可,无 schema migration / 数据迁移
- dev compose / 业务 service 启动依赖此改动,revert 后 dev compose 立即失效

**影响面**:
- dev 启动:改后干净 dev 机 `docker compose -f docker-compose-dev.yml up` 可一次性 healthy
- test 启动:本机暂未跑 `docker-compose-test.yml`,但 test stack 基础设施独立,不影响
- production 启动:本机无 production 部署流程;V2/V3/V4 时代 production 跟 dev 共享 base,改后 production 部署如使用 base compose 也自动修复
- sso-real-impl 后续:T5.3-5.5 解锁,继续推进 T6/T7/T8/T9/T10
- 其它 change:apply 阶段如跑 dev compose config 验证(本机未跑,理论需验),无新阻塞

## Open Questions

无遗留问题。v5.0.2 strict validation 行为已实测确认(不是误报也不是 base compose 真坏,而是 service key / container_name 命名不一致触发 strict mode 路径)。改 base compose service key 是唯一干净的解法。
