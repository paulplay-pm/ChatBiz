# fix-compose-postgres-naming — Proposal

## Why

`sso-real-impl` V6a change 在 T5.2 阶段(2026-06-14)首次跑 `docker compose -f infrastructure/docker-compose-dev.yml config` 验证时,被 docker compose **v5.0.2 strict validation** 报:

```
service "sso" depends on undefined service "chatbiz-postgres": invalid compose project
service "sso-migrate" depends on undefined service "chatbiz-postgres": invalid compose project
service "credential-migrate" depends on undefined service "postgres": invalid compose project
service "audit-and-isolation-migrate" depends on undefined service "postgres": invalid compose project
service "workflow-engine-migrate" depends on undefined service "postgres": invalid compose project
service "audit-and-isolation" depends on undefined service "redis": invalid compose project
```

**根因**:`infrastructure/docker-compose.yml`(base compose)用 `postgres` / `redis` 作 service key(用 `container_name: chatbiz-postgres` / `container_name: chatbiz-redis` 起容器),但 dev compose 6 个 extends 段 + sso 段(sso-real-impl)引用时用 `chatbiz-postgres` / `chatbiz-redis`(container_name 而非 service key)。v5.0.2 strict validation 解析 merge 后的 service 引用,只认 service key 名,不认 container_name alias。

**为什么 V2/V3/V4 没暴露**:旧 docker compose v2 时代 extends merge 行为宽松,拉过来的 `depends_on: postgres` 直接 resolved;v5.0.2 改严格,merge 解析时把 dev compose namespace 里的 `chatbiz-postgres` 引用当 unresolved service。

**为什么不能简单"在 dev compose 加 alias 段"**:
- 加 `postgres:` / `redis:` alias → 跟 base compose 同名 service 在 merged config 冲突(`container_name: chatbiz-postgres` 已存在)
- alias 段镜像 base 段全部内容 → v5.0.2 strict validation 又报"undefined volume postgres-data"(alias 段没继承 base 的 volumes)
- `docker compose --compatibility` 模式 dry-run 跑过,但 `config` 仍 FAIL

**不修**:
- 任何干净 dev 机 / CI runner / ops 人员跑 `docker compose -f infrastructure/docker-compose-dev.yml config` 全部失败
- sso-real-impl V6a T5.3-5.5(实际 compose up + 5 路径 curl)阻塞
- `gateway-egress-enforcement-p0` / `web-integration-test-suite` / `mcp-server-management-ui` 三个 change 后续 apply 阶段都会撞

**改**:
- 改 base compose `postgres` / `redis` service key 为 `chatbiz-postgres` / `chatbiz-redis`,**对齐 container_name**
- 同步改 6 个 service 段(credential / audit-and-isolation / workflow-engine / 3 个 migrate / sso-real-impl 已加的 sso 段)的 `depends_on: postgres` → `chatbiz-postgres`, `depends_on: redis` → `chatbiz-redis`
- 改后 v5.0.2 strict validation 通过,dev compose 0 改动
- sso-real-impl T5.3-5.5 自动解锁

**eng-review 决策**(未触及 12 个 eng-review 锁定决策):
- **Tech #1** (P0): "数据隔离网关 = egress 强制点" — 不动(echo stub 不在 infrastructure/ 命名范围)
- **CLAUDE.md 端口分配表**(5432 postgres 共享 / 6379 redis 共享) — 容器名规范已对齐,改后心智模型更清晰
- **Tech #11** (P1): "4 critical path 100% 覆盖" — sso 段在 sso-real-impl 验证,本 change 只 fix 基础设施命名

## What Changes

- **修改** `infrastructure/docker-compose.yml`:
  - line 26 `postgres:` → `chatbiz-postgres:`(service key)
  - line 247 `redis:` → `chatbiz-redis:`(service key)
  - 6 个 `depends_on: postgres` → `chatbiz-postgres`(workflow-engine / workflow-engine-migrate / audit-and-isolation-migrate / audit-and-isolation / credential / credential-migrate 段)
  - 4 个 `depends_on: redis` → `chatbiz-redis`(workflow-engine / audit-and-isolation / credential / credential-cron 段)
  - container_name `chatbiz-postgres` / `chatbiz-redis` 不变
  - environment `<<: *pg-env` 引用不变

- **不改**:
  - `infrastructure/docker-compose-dev.yml`(6 个 extends 段 + sso 段引用 `chatbiz-postgres` / `chatbiz-redis` 已是正确,base 改名后 v5 strict validation 自动通过)
  - `infrastructure/docker-compose-test.yml`(test stack 自带 infrastructure,跟 base compose 隔离)
  - 任何 service 源码(services/ 任何子目录)
  - 前端 (web/ 任何子目录)
  - alembic migration
  - 文档 (docs/architecture.md / docs/prd.md / CLAUDE.md 端口表)
  - sso-real-impl change 自身代码(本 change 合并后 sso T5.3-5.5 自动解锁)

## Capabilities

### New Capabilities

- `infra-compose-naming`:docker compose service key 跟 container_name 一致。**前端范围** = N/A(纯基础设施,零 UI / 业务 / 协议场景);**后端范围** = `infrastructure/docker-compose.yml`;**豁免前端** = 纯基础设施层。

### Modified Capabilities

无。

## Impact

- **代码层**:
  - `infrastructure/docker-compose.yml`(改,~10 处机械改动)
- **依赖**:无新增,无删除
- **CLAUDE.md 端口表**:
  - "5432 postgres 共享基础设施" — 容器名 `chatbiz-postgres`,service key 改后跟容器名一致
  - "6379 redis 共享基础设施" — 容器名 `chatbiz-redis`,service key 改后跟容器名一致
  - 端口分配表 0 改动(端口号不变,只是 service key / container_name 一致)
- **openspec/config.yaml §apply.rules**:
  - "MUST: 服务容器在 infrastructure/docker-compose.yml 注册" — 满足(本 change 改的就是该文件)
  - "MUST: 健康检查用 HTTP GET" — 满足(既有 healthcheck 不动)
  - "MUST: 引用 eng-review Arch #1 egress 强制点" — 不适用(不动 service 代码,echo stub 保持既有)

## Non-goals

- 重写 compose 文件结构
- 引入 docker compose v2 旧 binary 绕 strict validation
- 加 CI 接入
- 改 dev compose(dev compose 已是正确引用)
- 改 production 部署脚本(本机还没 production deploy 流程,V2/V3/V4 时代 production 跟 dev 共享 base compose)
- 修 `docker-compose-test.yml`(test stack 独立基础设施)
- 加 `infra-compose-v5-strict-mode` 工具 / lint
